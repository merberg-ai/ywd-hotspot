# Alpha22.4 — RX Monitor adaptive-poll test baseline

Alpha22.4 is intentionally a core-behavior carry-forward release for the RX Monitor v0.4.0-alpha2 test.

## Core behavior

No RF-path, modem, DMRGateway, BrandMeister, voice-tap, plugin-host, WebAssembly-policy, or passive voice-bridge behavior changes are introduced beyond Alpha22.3.

The Alpha22.3 passive voice-bridge pacing fix remains unchanged. The proven duplex BrandMeister talkgroup fix remains in ancestry and saved static talkgroup state continues to be preserved by normal updates.

## Paired RX Monitor test

RX Monitor v0.4.0-alpha2 changes browser-side polling only:

- 250 ms while live audio is stopped;
- 100 ms while START AUDIO is active;
- returns to 250 ms on STOP AUDIO;
- decoder, FEC recovery, fixed 20 ms AMBE audio clock, and Pi-side trusted bridge remain unchanged.

The first comparison test should use NETWORK, the active timeslot, and a 240 ms jitter target. If stable, step down through 200 ms and 160 ms while watching underruns and intelligibility.

RF-side live-audio validation is still pending.
