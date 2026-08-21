# 🎧 Passive DMR Voice / RX Monitor Core Path

[← Docs index](README.md) · [Building](BUILDING.md) · [Architecture](ARCHITECTURE.md) · [Plugins](PLUGINS.md) · [Plugin UI](PLUGIN-UI.md)

YWD-Hotspot's passive DMR voice path exists to let an isolated browser plugin observe received DMR voice without ever becoming the modem owner.

> [!IMPORTANT]
> RX Monitor's passive voice-frame path uses a **patched build of the exact pinned MMDVM-Host commit**. Normal hotspot operation does not require RX Monitor, and ordinary YWD-Hotspot application updates do **not** recompile MMDVM-Host or DMRGateway.

## Safety invariant

**MMDVM-Host remains the only process that owns the MMDVM serial/RF path.**

RX Monitor/plugin code never:

- opens `/dev/serial0`;
- starts a competing MMDVM process;
- obtains RF TX authority;
- receives arbitrary MQTT/network access;
- writes canonical radio configuration.

## Current path

```text
MMDVM modem / BrandMeister
          │
          ▼
      MMDVM-Host
          │ normal DMR processing continues unchanged
          ├──────────────────────────────────────────────► DMRGateway / RF
          │
          └─ accepted voice-frame copy
                    │
                    ▼
             ywd-mmdvm/voice
             loopback MQTT only
                    │
                    ▼
          trusted voice bridge
          bounded state / cursor transport
                    │
                    ▼
          read:dmr-voice capability
                    │
                    ▼
          sandboxed RX Monitor iframe
                    │
                    ├─ DMR A/B/C deinterleave
                    ├─ Golay/FEC correction
                    ├─ AMBE+2 descrambling
                    ├─ 49-bit vocoder recovery
                    └─ browser-side AMBE→PCM playback
```

The Pi performs no AMBE speech synthesis. Expensive decode/playout work happens on the browser device.

## Upstream pin and YWD patch

Pinned MMDVM-Host repository/commit:

```text
https://github.com/g4klx/MMDVM-Host.git
dea6e9b2c35857fe6f904c5092bebadb86cbf079
```

YWD patch:

```text
lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch
```

The patch mirrors accepted `DT_VOICE_SYNC` / `DT_VOICE` frames to the loopback observation topic while normal MMDVM processing continues.

This patch is intentionally narrow: it is an observation tap, not a second RF stack and not permission for a plugin to transmit.

## Build / activation model

Preparing the patched MMDVM binary is deliberately **not** part of ordinary RF startup or normal application-update critical path.

On an installed hotspot:

```bash
sudo systemctl start ywd-mmdvm-voice-build.service
```

Follow progress:

```bash
sudo journalctl -fu ywd-mmdvm-voice-build.service
```

Status helper:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py status
```

The service runs:

```text
/usr/bin/python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py ensure
```

and is configured as a low-priority one-shot job with a long timeout because the original Pi Zero W is a single-core ARMv6 machine.

The helper verifies the pinned source and exact patch identity before reusing an interrupted build tree, performs the build conservatively, guards activation, and retains a fallback to the previously working MMDVM-Host binary if activation fails.

Normal application updates do **not** recompile MMDVM-Host.

See **[BUILDING.md](BUILDING.md)** for the step-by-step build guide.

## Voice-frame envelope

The passive copy carries metadata plus the existing 33-byte DMR voice burst, for example:

```json
{
  "DMRVoice": {
    "source": "rf",
    "slot": 2,
    "src_id": 3196104,
    "dst_id": 9,
    "group": "yes",
    "seq_no": 12,
    "n": 4,
    "ber": 0,
    "rssi": 57,
    "frame_hex": "...66 lowercase hex characters..."
  }
}
```

`source` is `rf` or `network`. Headers/end/session events stay on the separate telemetry/session path.

## Trusted bridge

`lib/mmdvm_voice_bridge.py` consumes the loopback topic into bounded runtime state. It never owns the modem.

A key Pi Zero optimization is that ingestion and whole-ring JSON snapshot writing are separated: the foreground process drains/parses incoming voice data, while a lower-priority writer process coalesces `voice.json` snapshots. This removed the large shared delivery stalls seen in earlier live-audio tests.

Runtime snapshot:

```text
/run/ywd-hotspot-voice/voice.json
```

Core exposes only a bounded capability-gated view through the Plugin UI bridge.

## Browser recovery path

RX Monitor recovers three AMBE+2 codewords per DMR voice burst.

Browser work includes:

1. DMR A/B/C bit deinterleave;
2. Golay correction of protected words;
3. C1 descrambling seeded from corrected C0 data;
4. recovery of the 49-bit AMBE+2 2450 vocoder frame;
5. bounded capture/continuity diagnostics;
6. browser-side vocoder decode and Web Audio playback.

A clean continuous DMR call produces roughly:

```text
~16.67 DMR bursts/sec
3 AMBE frames/burst
≈50 AMBE frames/sec
1 AMBE frame = 20 ms
```

So 500 recovered AMBE frames represent approximately 10 seconds of nominal voice.

## Live-audio player

The proven player architecture keeps vocoder state at 20 ms frame cadence but coalesces decoded PCM into 100 ms chunks before Web Audio scheduling.

Key behavior:

- adaptive 100 ms plugin polling while audio is running;
- 5 AMBE frames / 100 ms PCM chunks;
- configurable jitter target, with the useful tested region around 140–170 ms;
- maintained playout reservoir rather than startup-only buffering;
- tiny playback-rate correction to prevent long-term browser/audio-clock drift;
- AUTO call locking so simultaneous duplex timeslots do not thrash the decoder;
- bridge timestamps used for call/handoff decisions rather than JavaScript callback delay alone;
- non-destructive call handoff so scheduled old-call audio is not abruptly discarded.

The browser's AudioContext may run at 44.1/48 kHz; the recovered voice PCM remains 8 kHz speech data and is resampled by the browser audio stack.

## Physical validation status

The passive RX path has been exercised on the reference Pi Zero + duplex MMDVM setup with normal MMDVM-Host/DMRGateway ownership preserved, including duplex TS1/TS2 operation, RF/network voice-frame recovery, browser-side frame recovery, and live browser audio tests.

The core observation architecture is therefore established. RX Monitor packaging/browser decoder distribution remains a separate concern from the RF ownership model and from normal hotspot operation.

## Capture diagnostics

RX Monitor can export a bounded JSON ring of recovered AMBE frames with route/timestamp/FEC metadata. Because the ring is shared by observed traffic, a long network return can replace earlier RF frames before export; capture source filtering/polish is a diagnostics concern rather than an RF correctness issue.

## Licensing / distribution boundary

Development has used an mbelib-based browser decoder built locally from a pinned upstream source. The repository intentionally does **not** treat a generated decoder artifact as automatically safe to publish merely because local development works.

Before promoting RX Monitor from a local signed development candidate to a canonical public package, review the upstream licensing/patent notice and decide what source/binary distribution model the project will support.

Private signing keys remain outside both repositories and never belong on the hotspot.
