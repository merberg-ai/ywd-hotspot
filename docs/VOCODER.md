# 🎙️ External YWD Vocoder Backend

[← Docs index](README.md) · [Passive DMR Voice](DMR-VOICE.md) · [Architecture](ARCHITECTURE.md) · [Plugins](PLUGINS.md)

DMR RX Monitor Phase 3J uses a **separately installed** AMBE49 → PCM backend through **YWD Vocoder Protocol v1**. YWD-Hotspot core and the RX Monitor plugin deliberately do not bundle mbelib, a software AMBE decoder, or an AMBE Wasm module.

## Where the backend sits

```text
MMDVM accepted DMR voice
        ↓
trusted YWD voice bridge
        ↓ direct AF_UNIX datagram
trusted audio streamer
  DMR recovery / FEC
  10 AMBE frames / 200 ms
        ↓
YWD Vocoder Protocol v1
/run/ywd-vocoder.sock
        ↓
separately installed mbelib backend
        ↓
8 kHz mono s16le PCM
        ↓
trusted NDJSON PCM stream
        ↓
sandboxed RX Monitor / Web Audio
```

The plugin receives PCM only. It never loads mbelib and never opens the vocoder socket directly.

## Current `dev` baseline

The physically selected Phase 3J baseline, now integrated into `dev`, is:

```text
protocol                 YWD Vocoder Protocol v1
preferred batch          10 AMBE49 frames / 200 ms
core decode timeout      400 ms
core live burst tail     12 DMR bursts (~720 ms)
backend socket           /run/ywd-vocoder.sock
backend service          ywd-vocoder-mbelib.service
backend socket unit      ywd-vocoder-mbelib.socket
service Nice             0
service CPUWeight        200
browser target reservoir 400 ms
browser emergency depth  700 ms
```

`Nice=0` and `CPUWeight=200` are enforced by YWD-Hotspot's managed systemd drop-in:

```text
/etc/systemd/system/ywd-vocoder-mbelib.service.d/20-ywd-hotspot-normal-priority.conf
```

No negative nice value or realtime scheduling is used. MMDVM/RF remains the priority workload.

## Prerequisites

Before installing a real backend:

1. Install/update the current `dev` YWD-Hotspot build.
2. Use the **YWD Extended** MMDVM runtime so passive DMR voice is available.
3. Confirm `/opt/ywd-hotspot/app/lib/vocoder_client.py` and `vocoder_protocol.py` exist.
4. Confirm the managed scheduling policy exists.
5. Have Internet access during backend installation so the installer can fetch the pinned mbelib source and Debian build dependencies.

Useful checks:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py status
ls -l /opt/ywd-hotspot/app/lib/vocoder_{client,protocol}.py
cat /etc/systemd/system/ywd-vocoder-mbelib.service.d/20-ywd-hotspot-normal-priority.conf
```

## Quick setup with the deployment kit

Extract the current external backend deployment bundle on the hotspot, then:

```bash
cd ywd-vocoder-mbelib-backend-0.1.0-alpha1
chmod +x INSTALL.sh STATUS.sh TEST.sh BENCHMARK.sh UNINSTALL.sh
sudo ./INSTALL.sh
./STATUS.sh
./TEST.sh
```

The installer:

- verifies current YWD Vocoder Protocol v1 constants before changing anything;
- requires YWD-Hotspot's managed `Nice=0 / CPUWeight=200` policy;
- preserves the original fake-vocoder socket enable state across reinstalls;
- fetches mbelib from upstream at the pinned commit;
- builds mbelib in Release mode with one build job for Pi Zero friendliness;
- builds the small YWD Protocol v1 native adapter;
- installs a socket-activated backend at `/usr/local/libexec/ywd-vocoder-mbelib`;
- enables `ywd-vocoder-mbelib.socket`;
- verifies the effective scheduling policy;
- runs a cold Protocol v1 STATUS probe.

Pinned mbelib source for the current deployment kit:

```text
https://github.com/szechyjs/mbelib.git
9a04ed5c78176a9965f3d43f7aa1b1f5330e771f
```

The deployment archive contains the YWD adapter/installer only; it does **not** contain mbelib source or a prebuilt mbelib binary.

## Verify the backend

```bash
./STATUS.sh
```

Expected core scheduling policy:

```text
Nice=0
CPUWeight=200
```

Protocol transport/decode sanity test:

```bash
./TEST.sh
```

Optional 60-batch latency benchmark:

```bash
./BENCHMARK.sh
```

On the reference Pi Zero, the standalone 10-frame backend benchmark completed a 200 ms speech batch far faster than real time; live scheduling latency is therefore monitored separately in RX Monitor with `DECODE RTT`, `MAX`, `DROPPED BURSTS`, `UNDERRUNS`, and `ERRORS`.

## Runtime lifecycle

The socket unit stays available, but the backend process is intentionally demand-driven:

```text
RX audio stopped
  -> backend may be dormant

START AUDIO / Protocol request
  -> systemd socket activates backend
  -> trusted core keeps a persistent AF_UNIX session while active

idle backend
  -> process exits after its idle window
  -> next request activates it again
```

This keeps the external decoder out of the steady-state CPU budget when it is not needed.

## Troubleshooting

Check units and effective policy:

```bash
systemctl status ywd-vocoder-mbelib.socket --no-pager -l
systemctl status ywd-vocoder-mbelib.service --no-pager -l
systemctl show ywd-vocoder-mbelib.service -p Nice -p CPUWeight -p CPUSchedulingPolicy
```

Check Protocol v1 directly:

```bash
sudo -u ywd-hotspot python3 /opt/ywd-hotspot/app/lib/vocoder_client.py status
sudo -u ywd-hotspot python3 /opt/ywd-hotspot/app/lib/vocoder_client.py reset
sudo -u ywd-hotspot python3 /opt/ywd-hotspot/app/lib/vocoder_client.py decode-test --frames 10
```

Check the socket:

```bash
ls -l /run/ywd-vocoder.sock
ss -xlp | grep ywd-vocoder || true
```

A backend can be healthy while its process is currently `inactive`: socket activation is intentional.

## Uninstall

From the deployment-kit directory:

```bash
sudo ./UNINSTALL.sh
```

The uninstaller removes the separately installed backend, its socket/service units, binary, and build tree. It intentionally leaves YWD-Hotspot's managed scheduling drop-in in place because that policy belongs to core and is harmless when the external unit is absent.

## Distribution boundary

The deployment kit is separate from the `.ywdplugin` package and from the normal YWD-Hotspot application payload. It fetches pinned upstream mbelib source at install time rather than redistributing mbelib inside the plugin/core package.

Review upstream licensing and any applicable codec/patent requirements for your jurisdiction before redistribution or deployment. This project documentation is not legal advice.
