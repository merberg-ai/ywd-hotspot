# TGIF Control Center — single-TG hardware acceptance

Date: 2026-08-30

This checkpoint records the first real-appliance acceptance of the RC4 TGIF Control Center session-control slice on the mature YWD-Hotspot appliance.

Accepted implementation source before this checkpoint:

`fdd175846c14c0c2184ede942b5bb0f1f6a3c2c0`

## Hardware/browser results

- TGIF Control Center tab rendered when TGIF was enabled.
- BrandMeister and TGIF remained connected simultaneously.
- TGIF public directory remained available from the local cache.
- The directory omission of TGIF Parrot was corrected by YWD's built-in/synthesized known-talkgroup fallback.
- Searching TGIF `9990` returned `Parrot` with radio destination `5009990`.
- The directory row exposed Favorite, Watch, Tune, and Copy RF actions.
- Appliance-persistent TGIF Favorite state worked in the browser UI.
- `TUNE` successfully pinned the TGIF session to network TG `9990` / RF destination `5009990` on TS2 while leaving the watchlist scanner daemon stopped.
- The Control Center truthfully displayed `TUNED`, `TG 9990`, `Radio destination 5009990 · TS2`, and `TGIF session pinned · scanner stopped`.
- The scanner service remained runtime-only (`inactive` / `static`) until explicitly started.
- MMDVMHost and DMRGateway remained active and zero failed units were reported before the directory fix.

## Regression findings closed in this slice

1. TGIF's public directory export may omit valid service destinations such as Parrot. YWD now supplements known TGIF service talkgroups and synthesizes exact numeric searches for valid TGs that lack directory metadata.
2. `tools/tgif-ui-smoke.py` had a stale literal assertion for the pre-Control-Center two-field dashboard route table. The smoke now accepts the current three-field `(action, timeout, operation)` route representation.
3. TGIF directory refresh still fails closed if the remote export contains no real recognized rows; built-in synthetic service rows do not make an empty remote response look healthy.

## Scope of this acceptance

This closes the single-talkgroup TGIF network-session control gate. It does **not** yet close full watchlist scanning/automatic hold/next/resume behavior. The next hardware gate should exercise a small 2–3 talkgroup watchlist and verify session rotation, traffic hold, post-call hold, manual hold/resume/next, stop, and BrandMeister isolation.

No MMDVM-Host, DMRGateway routing, firmware, or RF ownership change is part of this checkpoint.
