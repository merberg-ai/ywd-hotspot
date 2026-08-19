# Alpha22.2 — RX Monitor live-audio browser support

This development step is layered directly on the proven Alpha22.1 duplex BrandMeister talkgroup fix. It does not change MMDVM-Host, DMRGateway, modem ownership, RF frequencies, the passive voice tap, or the RX Monitor frame bridge.

## Purpose

RX Monitor Phase 3D proved that the pinned mbelib AMBE+2 decoder can run successfully in a browser and produce intelligible Web Audio playback from a known capture. Phase 3E begins live playback inside the sandboxed RX Monitor UI.

The browser decoder is WebAssembly. Ordinary Plugin UI v1 frames keep the original strict `script-src 'self'` CSP. Only an installed/enabled UI plugin that already holds the trusted `read:dmr-voice` capability receives the narrower `wasm-unsafe-eval` allowance required for WebAssembly compilation.

This does **not** grant JavaScript `unsafe-eval`, direct network access, same-origin access, device access, forms, popups, microphone/camera, serial/USB, filesystem access, or Pi-side execution.

## Safety baseline

- Parent/proven core: Alpha22.1 TG fix (`aa8f03e60860ec7bd0ff6d96462e7d3b5e26fcfd`).
- The duplex TG routing fix remains in the ancestry of this build.
- No MMDVM rebuild.
- No RX voice-tap rebuild.
- MMDVM-Host remains sole modem owner.
- Audio decode remains browser-side.
