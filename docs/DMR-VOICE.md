# Passive DMR voice-frame bridge

## Proven starting point

`0.1.0-alpha19-dev` Plugin UI v1 is the physically validated foundation for this work. The reference Raspberry Pi Zero W passed the signed `ui-smoke-test` package lifecycle, sandbox/navigation test, configuration bridge test, master Plugin Support test, and normal DMR-operation check.

Frozen checkpoints:

```text
ywd-hotspot:
  checkpoint-alpha19-plugin-ui-proven
  f08d0fcb47ae9c022809bf1262a687d80fa81811

ywd-hotspot-plugins:
  checkpoint-alpha19-plugin-ui-proven
  e5376fee6be8833d4524a8c4d7d49c62bf703865
```

MMDVM-Host remains the only process that owns the modem/RF path. Plugin code never opens `/dev/serial0`, never starts a competing MMDVM instance, and never gains TX authority.

## Alpha20 Phase 2A

Phase 2A adds only a passive raw DMR voice-frame observation tap. It does **not** yet expose voice frames to a browser plugin and does **not** decode AMBE audio on the Pi.

```text
MMDVM modem / BrandMeister network
              │
              ▼
        pinned MMDVM-Host
              │
              ├── normal RF/network processing
              │
              └── accepted DMR voice-frame copy
                         │
                         ▼
                 ywd-mmdvm/voice
                 loopback MQTT only
```

The existing low-rate telemetry remains on `ywd-mmdvm/json`. Per-frame voice traffic uses the separate `ywd-mmdvm/voice` topic so the telemetry snapshot service does not parse/rewrite state for every voice frame.

## Alpha20.2 build safety model

The first Alpha20 attempt proved that an original Pi Zero W can take longer than thirty minutes to compile MMDVM-Host. It also exposed an important lifecycle problem: a compiler job must never sit in the dependency chain that starts MMDVM-Host or the detached application updater.

Alpha20.2 therefore uses these rules:

- `ywd-mmdvmhost.service` has the same startup dependencies as the proven Alpha19 unit. It does **not** require or want the voice-build service.
- `ywd-mmdvm-voice-build.service` is started separately and may run while normal hotspot services remain online.
- the compile is heavily de-prioritized (`Nice=15`, idle I/O scheduling) because the Pi Zero is a single-core RF appliance first and a build machine second;
- the voice-build service has a two-hour guardrail, but its timeout cannot prevent normal MMDVM-Host startup;
- an interrupted build is resumed only when the source tree is provably the exact pinned upstream commit with exactly the YWD voice patch applied;
- otherwise the helper resets to a clean pinned tree before building;
- `/usr/local/bin/MMDVM-Host` is replaced only after the complete compile succeeds;
- the previously working binary is retained as a fallback until the patched binary has passed a guarded activation restart;
- activation preserves whether MMDVM-Host/DMRGateway were running and rolls the MMDVM binary back if the patched host does not restart cleanly.

The compile helper is:

```text
/opt/ywd-hotspot/app/lib/mmdvm_voice_build.py
```

## MMDVM-Host patch discipline

YWD continues to pin upstream MMDVM-Host commit:

```text
dea6e9b2c35857fe6f904c5092bebadb86cbf079
```

The YWD patch is:

```text
lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch
```

The helper records the upstream commit, patch identity and installed binary identity in:

```text
/var/lib/ywd-hotspot/mmdvm-voice-tap.json
```

## Voice-frame envelope

Only actual DMR audio frames are mirrored: `DT_VOICE_SYNC` and `DT_VOICE`. Headers/end/session events remain on the existing sanitized DMR telemetry/session path.

Each MQTT message contains one envelope similar to:

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

`source` is `rf` or `network`. `frame_hex` is the existing 33-byte DMR frame represented as 66 lowercase hexadecimal characters. The Pi performs no AMBE-to-PCM conversion.

## Alpha20.2 physical validation

### 1. Update the YWD application first

The application update should complete with ordinary MMDVM-Host and DMRGateway service behavior. It should **not** compile MMDVM-Host as part of the update transaction.

Confirm:

```bash
cat /opt/ywd-hotspot/app/VERSION
systemctl is-active ywd-mmdvmhost.service
systemctl is-active ywd-dmrgateway.service
```

Expected version:

```text
0.1.0-alpha20.2-dev
```

### 2. Start the experimental build separately

```bash
sudo systemctl reset-failed ywd-mmdvm-voice-build.service
sudo systemctl start --no-block ywd-mmdvm-voice-build.service
```

Watch it without affecting the build:

```bash
sudo journalctl -fu ywd-mmdvm-voice-build.service
```

If an earlier interrupted compile is reusable, the log should include:

```text
YWD voice build: exact patched source tree found; resuming existing object build.
```

Otherwise the helper deliberately prepares a fresh pinned tree.

Normal hotspot services should remain online during this compile.

### 3. Confirm build completion

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py status
```

After compilation succeeds but before activation, expect roughly:

```json
{
  "installed": true,
  "active": false,
  "marker_status": "installed"
}
```

The currently running MMDVM process is still the old proven executable at this point.

### 4. Activate with the guarded restart

When ready for a brief RF interruption:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py activate
```

Then:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py status
systemctl is-active ywd-mmdvmhost.service
systemctl is-active ywd-dmrgateway.service
```

Expected voice status:

```json
"installed": true,
"active": true
```

### 5. Observe frames

```bash
mosquitto_sub -h 127.0.0.1 -p 18883 -t 'ywd-mmdvm/voice' -v
```

A Parrot test conveniently exercises both directions:

- local radio TX into the hotspot should produce `"source":"rf"`;
- the BrandMeister Parrot response should produce `"source":"network"`.

Every `frame_hex` value should contain 66 hexadecimal characters.

A compact ten-frame capture is:

```bash
mosquitto_sub -h 127.0.0.1 -p 18883 -t 'ywd-mmdvm/voice' -C 10
```

## Pass criteria before Phase 2B

Phase 2A is accepted when all of these are true:

- Alpha20.2 application update completes independently of the compiler;
- ordinary MMDVM-Host/DMRGateway operation stays healthy during the background compile;
- interrupted compatible object files can be resumed safely;
- build status reaches `installed: true`;
- guarded activation reaches `active: true`;
- RF-to-network and network-to-RF DMR still work;
- network voice produces `source=network` frames;
- RF voice produces `source=rf` frames;
- frames stop when voice traffic stops;
- no additional LAN/WAN listener is created;
- reboot does not cause an unnecessary rebuild;
- CPU/temperature remain reasonable after the one-time compile.

## Phase 2B direction

After Phase 2A is physically proven, trusted YWD core will consume `ywd-mmdvm/voice` into a bounded cursor/ring transport and add the explicit `read:dmr-voice` Plugin UI capability. The sandboxed RX Monitor will receive only that capability through the existing MessageChannel bridge. Browser-side AMBE/audio work comes after the bounded bridge itself is proven.
