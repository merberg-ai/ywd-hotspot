# 🎧 YWD Extended MMDVM / Passive DMR Voice

[← Docs index](README.md) · [Building](BUILDING.md) · [Telemetry](TELEMETRY.md) · [Architecture](ARCHITECTURE.md) · [Plugins](PLUGINS.md)

YWD-Hotspot supports two explicit MMDVM-Host runtime variants. Passive DMR voice and RX Monitor use the **YWD Extended** variant; Stock Upstream intentionally omits that observation capability.

## Safety invariant

**MMDVM-Host remains the only process that owns the MMDVM serial/RF path in both variants.**

Plugins never:

- open `/dev/serial0`;
- start a competing MMDVM instance;
- receive RF TX authority;
- write canonical radio configuration;
- receive arbitrary MQTT/network/sudo access;
- open the trusted live-audio AF_UNIX socket directly.

## Runtime variants

### YWD Extended — default/recommended

Exact pinned upstream source plus the verified YWD extension patch.

Current `dev` identity:

```text
MMDVM-Host upstream
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

Patch
  lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch

Extension API
  2

Patch SHA256
  77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994
```

Advertised current capabilities include:

```text
passive-dmr-voice
plugin-rx-monitor
demand-gated-dmr-voice
```

The accepted RC1/RC2 Extended patch used the same upstream MMDVM-Host commit and API 2 with patch SHA256:

```text
f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
```

That historical patch is explicitly recognized as a **legacy-compatible YWD Extended** generation. It retains `passive-dmr-voice` and `plugin-rx-monitor`, but it does not receive the newer `demand-gated-dmr-voice` capability because it predates the `YWD_DMR_VOICE_TAP=1` gate. See **[UPGRADING.md](UPGRADING.md)** for the explicit refresh path.

### Stock Upstream

Exact same pinned upstream source, no YWD extensions. Normal hotspot RF/DMR operation remains available, but passive-voice/extension-dependent plugins do not satisfy their runtime requirements.

## Runtime state

The selected variant is persisted in:

```text
/etc/ywd-hotspot/mmdvm-runtime.json
```

Build provenance is recorded in:

```text
/etc/ywd-hotspot/mmdvm-build.json
```

Check exact installed identity with:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_runtime_state.py status
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py status
```

Normal application updates preserve the selected runtime and do not rebuild MMDVM-Host or DMRGateway. A known RC1/RC2 Extended binary remains positively identified after an application update and reports that an explicit runtime refresh is required before a plugin may claim the newer demand-gated capability.

## Phase 3J observation and live-audio paths

The accepted DMR voice copy is split into two consumers with different jobs:

```text
MMDVM modem / BrandMeister
          │
          ▼
      MMDVM-Host
          │ normal DMR processing continues
          ├────────────────────────────────────► DMRGateway / RF
          │
          └─ accepted voice-frame copy
                    │
                    ▼
             ywd-mmdvm/voice
             loopback MQTT only
                    │
                    ▼
          trusted voice bridge
             │             │
             │             └─ direct nonblocking AF_UNIX datagram live path
             │                    /run/ywd-hotspot-voice/live-audio.sock
             │                              │
             │                              ▼
             │                     trusted audio streamer
             │                     DMR recovery / FEC
             │                     10 AMBE frames / 200 ms
             │                              │
             │                              ▼
             │                     external YWD Vocoder
             │                     Protocol v1 backend
             │                              │
             │                              ▼
             │                     one NDJSON PCM stream
             │                              │
             │                              ▼
             │                     sandboxed RX Monitor
             │                     Web Audio playout only
             │
             └─ bounded JSON diagnostic ring
                    /run/ywd-hotspot-voice/voice.json
                    diagnostics/capture only
```

The JSON ring is **not** the live audio transport. Phase 3J moved real-time voice to the local AF_UNIX datagram path after physical testing showed whole-ring JSON snapshotting was unsuitable as a low-latency bus on the Pi Zero.

The live sender is nonblocking. If the consumer cannot keep up, audio may be dropped, but the bridge never backpressures MMDVM-Host or the normal RF path.

## Selected Phase 3J tuning baseline

The physically selected development baseline, now integrated into `dev`, is intentionally conservative:

```text
trusted core chunk       10 AMBE frames / 200 ms
live burst tail          12 DMR bursts (~720 ms)
vocoder request timeout  400 ms
diagnostic ring default  32 frames
diagnostic snapshots     1 Hz
browser target reservoir 400 ms
browser emergency depth  700 ms
browser clock correction gentle +/-1%
```

Normal decoder-state resets do not require already-buffered browser PCM to be discarded. Explicit stream drop/error events still rebuffer.

The external decoder service is separately installed. YWD-Hotspot does not bundle mbelib source/binaries or an AMBE Wasm decoder. Core owns only the scheduling policy used for the known external service:

```text
Nice=0
CPUWeight=200
```

No negative nice value or realtime scheduler is used; MMDVM/RF remains the priority workload.

## Compile/cache behavior

YWD Extended and Stock Upstream use different cache signatures/namespaces. The Extended signature includes the extension API/hash plus upstream commit, target architecture, compiler and build flags. A stock cached binary therefore cannot satisfy an Extended lookup, and an RC1/RC2 Extended cache entry cannot satisfy the current demand-gated Extended identity.

Extended build helper:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py canonical
```

Stock helper:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_upstream_build.py canonical
```

Normal dispatch:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py install --mmdvm-variant ywd-extended
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py install --mmdvm-variant upstream
```

## Plugin requirement tokens

Plugins may declare trusted requirement tokens in their normal `dependencies` list. Current RX Monitor development uses demand-gated passive DMR voice capability so the optional high-rate bridge exists only while a valid enabled plugin requires it.

Tokens include:

```text
mmdvm-ywd-extended
mmdvm-extension-api-2
mmdvm-cap-passive-dmr-voice
mmdvm-cap-demand-gated-dmr-voice
```

Requirement checks resolve against the exact installed runtime metadata. Control-plane install/enable/start checks verify the live binary/patch identity; a plugin cannot switch the MMDVM runtime by itself.

## Voice-frame envelope

The passive copy carries metadata plus the existing 33-byte DMR voice burst. A representative envelope is:

```json
{
  "DMRVoice": {
    "source": "rf",
    "slot": 2,
    "src_id": 3196104,
    "dst_id": 9990,
    "group": "no",
    "seq_no": 12,
    "n": 4,
    "ber": 1,
    "rssi": 0,
    "frame_hex": "...66 lowercase hex characters..."
  }
}
```

`source` is `rf` or `network`. Session/header/end events stay on the separate low-rate telemetry/session path.

### RSSI field semantics

The voice envelope carries the RSSI value MMDVM-Host receives from the modem data path; YWD does not manufacture it.

On compatible HAT firmware with RSSI reporting enabled, an RF frame may contain a positive RSSI magnitude that the normal MMDVM mapping converts to dBm context. On firmware that does **not** report RSSI, the field may remain `0` even while BER and DMR voice data are healthy.

That behavior was physically proven during RC1 acceptance: the reference duplex HAT delivered hundreds of valid voice frames with zero bridge parse errors and valid BER, while every RF/network voice RSSI field was `0`. This is treated as **RSSI unavailable**, not `0 dBm`.

Enabling real RSSI may require compatible MMDVM_HS HAT firmware with optional RSSI reporting support. Recompiling only MMDVM-Host on the Pi cannot create a measurement the modem firmware does not send. YWD-Hotspot does not automatically flash HAT firmware.

See **[TELEMETRY.md](TELEMETRY.md)** and **[DISPLAY.md](DISPLAY.md)**.

## Trusted voice bridge lifecycle

`ywd-mmdvm-voice.service` subscribes only to the local voice topic. It validates/normalizes frame fields and publishes the bounded diagnostics ring while offering the nonblocking live datagram copy when an audio consumer exists.

With the current demand-gated Extended runtime:

- RX Monitor absent/disabled: no plugin-driven voice runtime requirement and the MMDVM voice tap remains dormant;
- RX Monitor enabled, audio stopped: passive bridge may remain available for diagnostics while the external vocoder is dormant;
- audio running: the dashboard binds the live datagram receiver and the external vocoder activates on demand;
- audio stopped/disconnected: the live socket is removed and the vocoder may idle-exit.

The updater preserves/restarts the voice bridge when it was active so new bridge code is not left behind an old long-running Python process. It does not silently rebuild MMDVM-Host.

## Distribution boundary

The Phase 3J plugin receives PCM only. External speech synthesis stays outside the plugin package and outside the YWD-Hotspot core distribution. This keeps the plugin sandbox narrow while allowing an operator-installed YWD Vocoder Protocol v1 backend to provide speech decode.
