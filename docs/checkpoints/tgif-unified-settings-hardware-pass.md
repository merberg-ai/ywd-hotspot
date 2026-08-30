# TGIF unified Settings hardware checkpoint

Checkpoint baseline before TGIF talkgroup-intelligence and dashboard-wide control-focus styling work.

Implementation commit under test: `9aad248932927bdc7b847e0ddbdcf8662f9ac6a3`.

Documentation-only branch head immediately before this checkpoint marker: `0e270f3932b7230aee7d61534a2e64e2b96ccf4c`.

Real-hardware acceptance on the Pi 5 simplex test hotspot:

- TGIF routing smoke: PASS.
- TGIF UI/admin smoke: PASS.
- TGIF dashboard-status smoke: PASS.
- Separate BrandMeister and TGIF indicators: PASS.
- BrandMeister Parrot: PASS.
- TGIF Parrot through RF destination `5009990`: PASS.
- TGIF disable using ordinary Settings `SAVE & APPLY`: PASS.
- TGIF re-enable using ordinary Settings `SAVE & APPLY`: PASS.
- TGIF credential preserved across ordinary Settings saves: PASS.
- Repeated disable/re-enable cycles did not disturb BrandMeister operation.

Treat this as the preferred rollback point for the complete dual-network + unified-Settings feature set before the next TGIF UI/data slice.
