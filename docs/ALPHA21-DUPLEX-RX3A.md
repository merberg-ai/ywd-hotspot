# Alpha21 — Duplex HAT + RX Monitor Phase 3A

## Proven parent checkpoint

Alpha21 is layered on the physically proven Alpha20.3 checkpoint:

```text
ywd-hotspot
  checkpoint-alpha20.3-dmr-rx-proven
  0e414b16aebaf1fa1cae843cd024eb68bd091f2a

ywd-hotspot-plugins
  checkpoint-alpha20.3-dmr-rx-proven
  2638a0cd3571a836d1b4547fdf170dadbe7d0f18
```

That checkpoint was physically tested on the Raspberry Pi Zero W with the newly
installed duplex-capable MMDVM HAT while still configured in simplex mode. OLED,
normal DMR/BrandMeister traffic, Parrot RF/network paths, and the signed
`dmr-rx-monitor` v0.1.0 capability bridge all worked normally.

## Core build

Version:

```text
0.1.0-alpha21-dev
```

Alpha21 does not change the proven MMDVM voice-frame patch or trusted raw-frame
bridge. It adds configuration/UI behavior around that foundation.

### Simplex / duplex HAT mode

Canonical config schema 6 adds:

```json
{
  "radio": {
    "mode": "simplex",
    "frequency_hz": 446525000,
    "rx_frequency_hz": 446525000,
    "tx_frequency_hz": 446525000
  }
}
```

Migration is intentionally conservative: every pre-schema-6 installation
migrates to `mode=simplex`, with the current simplex frequency copied into the
new duplex RX/TX fields. An update therefore cannot silently switch an existing
hotspot into duplex mode.

Simplex rendering remains:

- MMDVM `Duplex=0`
- one RX/TX frequency
- DMR network slot 1 off
- DMR network slot 2 on
- BrandMeister pass-all TG/PC on slot 2

Duplex rendering becomes:

- MMDVM `Duplex=1`
- separate hotspot RX and hotspot TX frequencies
- DMR network slots 1 and 2 on
- DMRGateway `[Info]` reports duplex + both slots + matching frequencies
- BrandMeister pass-all TG/PC rules cover slots 1 and 2

The WebUI shows only the fields relevant to the selected HAT mode. Duplex mode
must always be an explicit operator choice; hardware detection never silently
changes RF mode.

### Hero branding

The live `YWD//HOTSPOT` / version overlay remains real DOM text, but its dark
rounded panel background/border/shadow are removed so it sits transparently over
the hero artwork.

## RX Monitor Phase 3A

Plugin version:

```text
dmr-rx-monitor 0.2.0
```

Phase 3A stays entirely browser-side after the proven `read:dmr-voice` bridge.
It uses the same DMR A/B/C bit-position tables as the pinned MMDVM-Host
`AMBEFEC.cpp` implementation to de-interleave each 33-byte DMR voice burst into
three 72-bit coded AMBE+2 channel/FEC blocks.

This phase validates structure and timing only:

- three coded AMBE blocks per DMR burst
- zero extraction errors during clean traffic
- approximately one DMR burst every 60 ms during continuous voice
- approximately 50 coded AMBE blocks/sec
- optional display of the three latest 72-bit block values as hex

It does **not** yet Golay/FEC-decode the blocks into 49-bit vocoder payloads and
does not produce PCM/browser audio.

## Physical validation plan

1. Update core to `0.1.0-alpha21-dev` while leaving HAT mode at Simplex.
2. Confirm MMDVMHost, DMRGateway, OLED and dashboard remain healthy.
3. Confirm the migrated config still says `radio.mode=simplex` and generated
   MMDVM config still says `Duplex=0` / slot 2 only.
4. Build/sign/install `dmr-rx-monitor-0.2.0.ywdplugin`.
5. Make a sustained Parrot test in Simplex mode. Validate RF + NET frames,
   `3 × 72-bit`, zero extraction errors and near-60 ms cadence.
6. In Settings select Duplex. Confirm only duplex RX/TX fields are exposed.
7. Enter appropriate duplex frequencies and SAVE & APPLY.
8. Confirm generated MMDVM/DMRGateway configs show `Duplex=1`, both slots and
   the selected RX/TX frequencies.
9. Program/test radios against the duplex frequency pair before considering the
   duplex path physically proven.
10. Return to Simplex if any RF behavior is unexpected; the Alpha20.3 checkpoint
    remains available as the frozen rollback foundation.
