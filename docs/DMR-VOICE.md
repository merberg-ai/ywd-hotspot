# Passive DMR voice-frame bridge

## Proven starting point

`0.1.0-alpha19-dev` Plugin UI v1 is the physically validated foundation for this work. The reference Raspberry Pi Zero W passed the signed `ui-smoke-test` package lifecycle, sandbox/navigation test, configuration bridge test, master Plugin Support test, and normal DMR-operation check.

The immutable repository checkpoint is:

```text
checkpoint-alpha19-plugin-ui-proven
f08d0fcb47ae9c022809bf1262a687d80fa81811
```

Alpha20 begins the RX Monitor work without changing the ownership rule established by earlier plugin phases: MMDVM-Host remains the only process that owns the modem/RF path. Plugin code never opens `/dev/serial0`, never starts a competing MMDVM instance, and never gains TX authority.

## Alpha20 Phase 2A scope

Phase 2A adds only a passive raw DMR voice-frame observation tap. It does **not** yet expose voice frames to a browser plugin and it does **not** decode AMBE audio on the Pi.

The data path is:

```text
MMDVM modem / BrandMeister network
              │
              ▼
        pinned MMDVM-Host
              │
              ├── normal RF/network processing (unchanged)
              │
              └── accepted DMR voice-frame copy
                         │
                         ▼
                 ywd-mmdvm/voice
                 loopback MQTT only
```

The existing low-rate telemetry path remains on `ywd-mmdvm/json`; per-frame voice traffic is deliberately placed on a separate topic so `ywd-mmdvm-telemetry.service` does not parse or rewrite its snapshot for every voice frame.

## MMDVM-Host patch discipline

YWD continues to pin upstream MMDVM-Host commit:

```text
dea6e9b2c35857fe6f904c5092bebadb86cbf079
```

Alpha20 applies one local YWD patch to a clean checkout of that exact commit. The patch is stored at:

```text
lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch
```

The trusted helper `lib/mmdvm_voice_build.py` records the upstream commit, patch SHA-256, and installed binary SHA-256 under:

```text
/var/lib/ywd-hotspot/mmdvm-voice-tap.json
```

Before MMDVM-Host starts, `ywd-mmdvm-voice-build.service` runs the helper. If the recorded patch and installed binary are already current, the check is cheap and no build occurs. When the patch identity changes, the helper resets the MMDVM source tree to the pinned upstream commit, applies the YWD patch, and builds with `make -j1`.

The preparation step is fail-soft for an existing appliance: if the experimental rebuild fails and an earlier MMDVM-Host binary exists, that binary is restored so normal hotspot operation can continue. The marker records `failed-fallback` rather than falsely claiming the voice tap is active.

## Voice frame envelope

Only actual DMR audio frames are mirrored: `DT_VOICE_SYNC` and `DT_VOICE`. Session headers/end events remain on the existing sanitized DMR telemetry/session path.

Each MQTT message is a single JSON envelope:

```json
{
  "DMRVoice": {
    "timestamp": "...",
    "source": "rf",
    "slot": 2,
    "frame_kind": "voice",
    "data_type": 1,
    "src_id": 3196104,
    "dst_id": 9,
    "group": "yes",
    "seq_no": 12,
    "n": 4,
    "ber": 0,
    "rssi": 57,
    "frame_hex": "...66 hexadecimal characters..."
  }
}
```

`source` is `rf` or `network`. The raw frame is the existing 33-byte DMR frame represented as 66 lowercase hexadecimal characters. RF frames are copied after MMDVM-Host has performed its normal validation/FEC regeneration. Network frames are copied only after the normal slot/call-state checks accept them.

The Pi performs no AMBE-to-PCM conversion in this phase.

## Phase 2A physical validation

After updating to `0.1.0-alpha20-dev`, first verify that the normal hotspot still works. The first MMDVM restart may take several minutes because a Pi Zero must compile the patched pinned MMDVM-Host once.

During that first build, another SSH session can follow progress with:

```bash
sudo journalctl -fu ywd-mmdvm-voice-build.service
```

Then inspect the patch marker:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py status
```

Expected key result:

```json
"active": true
```

Confirm core services:

```bash
systemctl is-active ywd-mqtt.service
systemctl is-active ywd-mmdvmhost.service
systemctl is-active ywd-dmrgateway.service
systemctl --failed --no-pager
```

Subscribe to the passive voice topic from the hotspot:

```bash
mosquitto_sub \
  -h 127.0.0.1 \
  -p 18883 \
  -t 'ywd-mmdvm/voice' \
  -v
```

With that command waiting:

1. Receive a BrandMeister/network-originated DMR call. Messages should appear with `"source":"network"`.
2. Key a local radio into the hotspot. Messages should appear with `"source":"rf"`.
3. Verify `frame_hex` is always 66 hexadecimal characters.
4. Verify `src_id`, `dst_id`, slot, group/private state, sequence and burst `n` values track the active call.
5. Stop the subscriber and confirm DMR operation is unchanged; there is no requirement for a subscriber to exist.
6. Reboot once and verify the build helper reports the patch already active instead of recompiling.

A compact capture of ten frames is:

```bash
mosquitto_sub -h 127.0.0.1 -p 18883 -t 'ywd-mmdvm/voice' -C 10
```

## Pass criteria before Phase 2B

Phase 2A is accepted only when all of the following are true:

- patched-build marker reports `active: true`;
- MMDVM-Host and DMRGateway remain healthy;
- ordinary RF-to-network and network-to-RF DMR operation still works;
- network voice produces `source=network` frames;
- RF voice produces `source=rf` frames;
- frames stop when voice traffic stops;
- no additional LAN/WAN listener is created;
- reboot does not trigger an unnecessary rebuild;
- Pi CPU/temperature remain reasonable during normal operation after the one-time compile.

## Phase 2B direction

After Phase 2A is physically proven, trusted YWD core will consume `ywd-mmdvm/voice` into a bounded cursor/ring transport and add the explicit `read:dmr-voice` Plugin UI capability. The sandboxed RX Monitor will receive only that capability through the existing MessageChannel bridge. Browser-side AMBE/audio work comes after the bounded bridge itself is proven.
