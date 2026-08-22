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
- receive arbitrary MQTT/network/sudo access.

## Runtime variants

### YWD Extended — default/recommended

Exact pinned upstream source plus the verified YWD extension patch.

```text
MMDVM-Host upstream
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

Patch
  lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch

Extension API
  2

Patch SHA256
  f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
```

Advertised runtime capabilities include:

```text
passive-dmr-voice
plugin-rx-monitor
```

### Stock Upstream

Exact same pinned upstream source, no YWD extension patch. Normal hotspot RF/DMR operation remains available, but passive-voice/extension-dependent plugins do not satisfy their runtime requirements.

## Runtime state

The selected variant is persisted in:

```text
/etc/ywd-hotspot/mmdvm-runtime.json
```

Build provenance is recorded in:

```text
/etc/ywd-hotspot/mmdvm-build.json
```

Check it with:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py status
```

Normal application updates preserve the selected runtime and do not rebuild MMDVM-Host or DMRGateway.

## Extended observation path

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
          trusted bounded voice bridge
                    │
                    ▼
          read:dmr-voice capability
                    │
                    ▼
          sandboxed RX Monitor iframe
                    │
                    └─ browser FEC / AMBE recovery / PCM playback
```

The Pi does not perform AMBE speech synthesis. Browser-side decode/playout keeps the expensive work off the Pi Zero.

## Compile/cache behavior

YWD Extended and Stock Upstream use different cache signatures/namespaces. The Extended signature includes the extension API/hash plus upstream commit, target architecture, compiler and build flags. A stock cached binary therefore cannot satisfy an Extended lookup.

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

Plugins may declare trusted requirement tokens in their normal `dependencies` list:

```text
mmdvm-ywd-extended
mmdvm-extension-api-2
mmdvm-cap-passive-dmr-voice
```

Install/enable/runtime-start checks resolve these against `/etc/ywd-hotspot/mmdvm-runtime.json`. If a requirement is not met, trusted core refuses the operation with a readable missing-requirement result. A plugin cannot switch the MMDVM runtime by itself.

An RX Monitor package can therefore declare, for example:

```json
"dependencies": [
  "mmdvm-host",
  "mmdvm-ywd-extended",
  "mmdvm-extension-api-2",
  "mmdvm-cap-passive-dmr-voice"
]
```

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

Enabling real RSSI may require a compatible MMDVM_HS **HAT firmware** build with its optional RSSI reporting support. Recompiling only MMDVM-Host on the Pi cannot create a measurement the modem firmware does not send. YWD-Hotspot does not automatically flash HAT firmware.

See **[TELEMETRY.md](TELEMETRY.md)** and **[DISPLAY.md](DISPLAY.md)**.

## Trusted voice bridge

`ywd-mmdvm-voice.service` subscribes only to the local `ywd-mmdvm/voice` topic and writes a bounded runtime ring under:

```text
/run/ywd-hotspot-voice/voice.json
```

The bridge validates/normalizes frame fields, uses bounded capacity, and coalesces snapshot writes to remain suitable for the Pi Zero. It does not own the modem or transmit.

A long call plus network playback can exceed the in-memory frame capacity, so the voice ring is a recent-frame transport rather than permanent call history. Session/history consumers should use the normalized telemetry/activity layers for durable-enough bounded summaries.

## Browser recovery path

RX Monitor's browser path performs DMR burst recovery/FEC/AMBE+2 preparation and browser-side audio playback. The architecture keeps AMBE/audio work on the browser device and the trusted Pi-side bridge narrow.

The path has been physically exercised on the reference Pi Zero + duplex MMDVM setup while normal MMDVM-Host/DMRGateway ownership remained intact.

## Distribution boundary

Development has used an mbelib-based browser decoder built from pinned upstream source. Publishing generated decoder artifacts remains a separate licensing/distribution decision from the YWD Extended MMDVM patch and from normal hotspot operation.
