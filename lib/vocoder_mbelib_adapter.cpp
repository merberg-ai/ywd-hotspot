// YWD-Hotspot mbelib backend adapter for YWD Vocoder Protocol v1.
//
// This file is YWD-owned glue only. mbelib itself is fetched separately from
// its approved upstream repository/pin by the managed vocoder build job.

#include <arpa/inet.h>
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <iostream>
#include <string>
#include <vector>

extern "C" {
#include "mbelib.h"
}

namespace {

constexpr uint8_t kProtocolVersion = 1;
constexpr uint8_t kKindRequest = 0;
constexpr uint8_t kKindResponse = 1;
constexpr uint8_t kStatus = 1;
constexpr uint8_t kReset = 2;
constexpr uint8_t kDecode = 3;
constexpr uint8_t kOk = 0;
constexpr uint8_t kBadRequest = 1;
constexpr uint8_t kUnsupported = 2;
constexpr uint8_t kBackendError = 3;
constexpr uint8_t kCodecAmbe49 = 1;
constexpr uint8_t kSampleFormatS16Le = 1;
constexpr uint16_t kSampleRate = 8000;
constexpr uint16_t kSamplesPerFrame = 160;
constexpr size_t kHeaderSize = 16;
constexpr size_t kMaxPayload = 64 * 1024;
constexpr size_t kFrameBytes = 7;
constexpr size_t kFrameBits = 49;
constexpr size_t kMaxFrames = 10;
constexpr int kListenIdleMs = 30000;
constexpr int kClientIdleMs = 45000;

volatile sig_atomic_t g_stop = 0;

void signal_handler(int) { g_stop = 1; }

bool read_exact(int fd, uint8_t* out, size_t size) {
  size_t done = 0;
  while (done < size && !g_stop) {
    const ssize_t n = ::read(fd, out + done, size - done);
    if (n == 0) return false;
    if (n < 0) {
      if (errno == EINTR) continue;
      return false;
    }
    done += static_cast<size_t>(n);
  }
  return done == size;
}

bool write_all(int fd, const uint8_t* data, size_t size) {
  size_t done = 0;
  while (done < size && !g_stop) {
    const ssize_t n = ::write(fd, data + done, size - done);
    if (n < 0) {
      if (errno == EINTR) continue;
      return false;
    }
    done += static_cast<size_t>(n);
  }
  return done == size;
}

uint32_t read_be32(const uint8_t* p) {
  uint32_t v = 0;
  memcpy(&v, p, sizeof(v));
  return ntohl(v);
}

void append_be16(std::vector<uint8_t>& out, uint16_t value) {
  const uint16_t v = htons(value);
  const auto* p = reinterpret_cast<const uint8_t*>(&v);
  out.insert(out.end(), p, p + sizeof(v));
}

std::vector<uint8_t> json_bytes(const std::string& text) {
  return std::vector<uint8_t>(text.begin(), text.end());
}

bool send_response(int fd, uint8_t opcode, uint8_t status, uint32_t request_id,
                   const std::vector<uint8_t>& payload) {
  if (payload.size() > kMaxPayload) return false;
  std::array<uint8_t, kHeaderSize> h{};
  h[0] = 'Y'; h[1] = 'V'; h[2] = 'C'; h[3] = 'P';
  h[4] = kProtocolVersion;
  h[5] = kKindResponse;
  h[6] = opcode;
  h[7] = status;
  const uint32_t rid = htonl(request_id);
  const uint32_t len = htonl(static_cast<uint32_t>(payload.size()));
  memcpy(h.data() + 8, &rid, sizeof(rid));
  memcpy(h.data() + 12, &len, sizeof(len));
  return write_all(fd, h.data(), h.size()) &&
         (payload.empty() || write_all(fd, payload.data(), payload.size()));
}

struct Decoder {
  mbe_parms current{};
  mbe_parms previous{};
  mbe_parms enhanced{};

  Decoder() { reset(); }
  void reset() { mbe_initMbeParms(&current, &previous, &enhanced); }
};

bool decode_payload(Decoder& decoder, const std::vector<uint8_t>& payload,
                    std::vector<uint8_t>& response, std::string& error) {
  if (payload.size() < 4) {
    error = "decode payload is truncated";
    return false;
  }
  const uint8_t codec = payload[0];
  const uint8_t frame_count = payload[1];
  const uint8_t frame_bytes = payload[2];
  const uint8_t reserved = payload[3];
  if (codec != kCodecAmbe49) {
    error = "unsupported codec";
    return false;
  }
  if (frame_count < 1 || frame_count > kMaxFrames || frame_bytes != kFrameBytes || reserved != 0) {
    error = "invalid AMBE49 decode header";
    return false;
  }
  const size_t expected = 4 + static_cast<size_t>(frame_count) * kFrameBytes;
  if (payload.size() != expected) {
    error = "decode payload length mismatch";
    return false;
  }

  response.clear();
  response.reserve(8 + static_cast<size_t>(frame_count) * kSamplesPerFrame * 2);
  append_be16(response, kSampleRate);
  append_be16(response, kSamplesPerFrame);
  response.push_back(1);  // mono
  response.push_back(kSampleFormatS16Le);
  append_be16(response, frame_count);

  for (uint8_t frame_index = 0; frame_index < frame_count; ++frame_index) {
    const uint8_t* packed = payload.data() + 4 + static_cast<size_t>(frame_index) * kFrameBytes;
    if ((packed[6] & 0x7fU) != 0) {
      error = "AMBE49 padding bits are non-zero";
      return false;
    }
    char bits[kFrameBits]{};
    for (size_t bit = 0; bit < kFrameBits; ++bit) {
      bits[bit] = (packed[bit / 8] & (1U << (7U - (bit % 8U)))) ? 1 : 0;
    }

    short pcm[kSamplesPerFrame]{};
    int errs = 0;
    int errs2 = 0;
    char err_str[128]{};
    mbe_processAmbe2450Data(pcm, &errs, &errs2, err_str, bits,
                            &decoder.current, &decoder.previous, &decoder.enhanced, 3);
    for (size_t sample = 0; sample < kSamplesPerFrame; ++sample) {
      const uint16_t u = static_cast<uint16_t>(static_cast<int16_t>(pcm[sample]));
      response.push_back(static_cast<uint8_t>(u & 0xffU));
      response.push_back(static_cast<uint8_t>((u >> 8U) & 0xffU));
    }
  }
  return true;
}

int handle_client(int fd) {
  Decoder decoder;
  while (!g_stop) {
    pollfd pfd{fd, POLLIN, 0};
    const int pr = poll(&pfd, 1, kClientIdleMs);
    if (pr == 0) return 0;
    if (pr < 0) {
      if (errno == EINTR) continue;
      return 1;
    }
    if (!(pfd.revents & POLLIN)) return 0;

    std::array<uint8_t, kHeaderSize> h{};
    if (!read_exact(fd, h.data(), h.size())) return 0;
    const bool magic = h[0] == 'Y' && h[1] == 'V' && h[2] == 'C' && h[3] == 'P';
    const uint8_t opcode = h[6];
    const uint32_t request_id = read_be32(h.data() + 8);
    const uint32_t payload_len = read_be32(h.data() + 12);
    if (!magic || h[4] != kProtocolVersion || h[5] != kKindRequest || h[7] != 0 ||
        payload_len > kMaxPayload) {
      send_response(fd, opcode, kBadRequest, request_id,
                    json_bytes("{\"error\":\"invalid protocol header\"}"));
      return 1;
    }

    std::vector<uint8_t> payload(payload_len);
    if (payload_len && !read_exact(fd, payload.data(), payload.size())) return 0;

    if (opcode == kStatus) {
      const std::string status =
          std::string("{\"backend\":\"mbelib\",\"codec\":\"ambe49\",\"mbelib_version\":\"") +
          MBELIB_VERSION + "\",\"protocol\":1,\"sample_rate\":8000,\"samples_per_frame\":160}";
      if (!send_response(fd, opcode, kOk, request_id, json_bytes(status))) return 1;
      continue;
    }
    if (opcode == kReset) {
      decoder.reset();
      if (!send_response(fd, opcode, kOk, request_id, {})) return 1;
      continue;
    }
    if (opcode == kDecode) {
      std::vector<uint8_t> decoded;
      std::string error;
      if (!decode_payload(decoder, payload, decoded, error)) {
        if (!send_response(fd, opcode, kBadRequest, request_id,
                           json_bytes(std::string("{\"error\":\"") + error + "\"}"))) return 1;
      } else if (!send_response(fd, opcode, kOk, request_id, decoded)) {
        return 1;
      }
      continue;
    }

    if (!send_response(fd, opcode, kUnsupported, request_id,
                       json_bytes("{\"error\":\"unsupported opcode\"}"))) return 1;
  }
  return 0;
}

int systemd_listener() {
  const char* pid_text = getenv("LISTEN_PID");
  const char* fds_text = getenv("LISTEN_FDS");
  if (!pid_text || !fds_text) return -1;
  const long pid = strtol(pid_text, nullptr, 10);
  const long fds = strtol(fds_text, nullptr, 10);
  if (pid != static_cast<long>(getpid()) || fds < 1) return -1;
  return 3;
}

int local_listener(const std::string& path) {
  int fd = socket(AF_UNIX, SOCK_STREAM, 0);
  if (fd < 0) return -1;
  sockaddr_un addr{};
  addr.sun_family = AF_UNIX;
  if (path.size() >= sizeof(addr.sun_path)) {
    close(fd);
    return -1;
  }
  memcpy(addr.sun_path, path.c_str(), path.size() + 1);
  unlink(path.c_str());
  if (bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0 || listen(fd, 8) != 0) {
    close(fd);
    unlink(path.c_str());
    return -1;
  }
  chmod(path.c_str(), 0660);
  return fd;
}

int self_test() {
  Decoder decoder;
  std::vector<uint8_t> payload(4 + 10 * kFrameBytes, 0);
  payload[0] = kCodecAmbe49;
  payload[1] = 10;
  payload[2] = kFrameBytes;
  std::vector<uint8_t> out;
  std::string error;
  if (!decode_payload(decoder, payload, out, error)) {
    std::cerr << "{\"ok\":false,\"error\":\"" << error << "\"}\n";
    return 2;
  }
  const size_t pcm_bytes = out.size() >= 8 ? out.size() - 8 : 0;
  const bool ok = pcm_bytes == 10U * kSamplesPerFrame * 2U;
  std::cout << "{\"ok\":" << (ok ? "true" : "false")
            << ",\"protocol\":1,\"frames\":10,\"pcm_bytes\":" << pcm_bytes
            << ",\"mbelib_version\":\"" << MBELIB_VERSION << "\"}\n";
  return ok ? 0 : 3;
}

}  // namespace

int main(int argc, char** argv) {
  signal(SIGTERM, signal_handler);
  signal(SIGINT, signal_handler);
  signal(SIGPIPE, SIG_IGN);

  if (argc == 2 && std::string(argv[1]) == "--self-test") return self_test();

  int listen_fd = systemd_listener();
  bool owns_path = false;
  std::string path;
  if (listen_fd < 0) {
    path = getenv("YWD_VOCODER_SOCKET") ? getenv("YWD_VOCODER_SOCKET") : "/run/ywd-vocoder.sock";
    if (argc == 3 && std::string(argv[1]) == "--socket") path = argv[2];
    listen_fd = local_listener(path);
    owns_path = listen_fd >= 0;
  }
  if (listen_fd < 0) {
    std::cerr << "could not acquire vocoder listening socket\n";
    return 2;
  }

  int rc = 0;
  while (!g_stop) {
    pollfd pfd{listen_fd, POLLIN, 0};
    const int pr = poll(&pfd, 1, kListenIdleMs);
    if (pr == 0) break;
    if (pr < 0) {
      if (errno == EINTR) continue;
      rc = 2;
      break;
    }
    if (!(pfd.revents & POLLIN)) continue;
    const int client = accept(listen_fd, nullptr, nullptr);
    if (client < 0) {
      if (errno == EINTR) continue;
      rc = 2;
      break;
    }
    const int client_rc = handle_client(client);
    close(client);
    if (client_rc != 0) rc = client_rc;
  }

  if (owns_path) {
    close(listen_fd);
    unlink(path.c_str());
  }
  return rc;
}
