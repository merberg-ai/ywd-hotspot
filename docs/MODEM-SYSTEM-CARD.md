# System Modem / MMDVM Inventory

RC3 adds a read-only **MODEM / MMDVM** card under **System**. The card is intentionally designed as the future home for guarded MMDVM runtime maintenance while keeping the current RC3 UI-polish build informational only.

## Two separate layers

The card distinguishes two things that are easy to confuse:

1. **Physical MMDVM HAT / modem firmware** — firmware running on the STM32/modem board itself. Identity is learned passively from the existing MMDVMHost journal/activity state. The dashboard does not open the UART or probe the modem directly.
2. **Compiled MMDVM-Host runtime** — the Linux binary at `/usr/local/bin/MMDVM-Host`, including whether it is the exact accepted `ywd-extended` build or pinned upstream build.

Rebuilding/installing YWD-Extended MMDVM-Host does **not** flash the physical HAT firmware.

## Information shown

The always-visible inventory includes, where available:

- modem/HAT firmware description reported by MMDVMHost;
- MMDVM protocol version;
- configured UART path and resolved Linux serial device;
- UART speed, simplex/duplex RF mode, color code, and TX/RX inversion;
- MMDVMHost service active/sub-state, PID, restart count, last result, and exit status;
- runtime variant (`ywd-extended`, `upstream`, or `unknown`);
- runtime generation (`current`, accepted `legacy`, or `unknown`);
- YWD extension API;
- observed-vs-persisted runtime-state synchronization;
- whether an explicit runtime refresh is required;
- exact upstream commit, binary SHA-256, YWD patch SHA-256, and marker state;
- published runtime capability tokens such as passive DMR voice, RX Monitor support, and demand-gated DMR voice.

Expandable **BUILD / PROVENANCE DETAILS** also show:

- binary path, size, mtime, executable format, and full SHA-256;
- pinned MMDVM-Host repository and commit;
- pinned YWD patch API/hash;
- build architecture and availability/version of `git`, `make`, and `g++`;
- MMDVM source-checkout path, HEAD, dirty state, and changed-file count;
- build/install timestamps, cache-hit state, cache key, and build-cache inventory;
- persisted runtime-generation selection metadata.

Expandable **MODEM JOURNAL IDENTITY LINES** provides only the current-boot MMDVMHost lines relevant to modem protocol/description/open/version identity. It does not perform an active serial probe.

## Future maintenance area

The card reserves a **RUNTIME MAINTENANCE** area. In the RC3 UI-polish build only **REFRESH INFO** is active.

The following controls are deliberately visible but disabled placeholders:

- **BUILD / UPDATE YWD-EXTENDED**
- **HAT FIRMWARE TOOLS**

Future implementation should keep those as separate guarded workflows. Host-runtime rebuild/install must use the existing pinned/cached runtime-build machinery and preserve RF/Gateway state. Physical HAT firmware update requires a separate hardware-specific detection/bootloader workflow and must never be implied by a YWD-Extended host build.

## Safety properties

Reading the modem card must never:

- open or take ownership of the modem UART;
- stop/restart MMDVMHost or DMRGateway;
- compile or replace a binary;
- refresh persisted MMDVM capability state;
- alter RF/configuration/plugin state;
- flash physical HAT firmware.

The read-only `/api/system/modem` endpoint is intentionally available while dashboard controls are locked because it contains support/provenance information but no credentials or mutation capability.

## Physical acceptance

1. Load **System** with the dashboard locked and confirm the modem card still populates.
2. Confirm the HAT/firmware description and MMDVM protocol match the current MMDVMHost startup identity when available.
3. Confirm configured `/dev/serial0` and its resolved device are shown correctly.
4. Confirm the current RF mode and UART speed match Settings.
5. Confirm the host runtime shows the expected `ywd-extended` variant, `current` generation, extension API `2`, and `Observed / saved sync = YES` on the accepted RC3 runtime.
6. Confirm the exact binary/upstream/patch identities agree with `mmdvm_runtime_state.py status`.
7. Confirm all expected capability pills are present for current YWD-Extended.
8. Expand build/provenance details and confirm source/cache/tool state is plausible for the appliance.
9. Expand modem journal identity lines and confirm only passive current-boot identity/version/open lines are shown.
10. Select **REFRESH INFO** and confirm the card refreshes without interrupting RF.
11. Confirm **BUILD / UPDATE YWD-EXTENDED** and **HAT FIRMWARE TOOLS** remain disabled in this RC3 UI-polish build.
12. Confirm MMDVMHost/DMRGateway remain active and `systemctl --failed` remains clean after viewing/refreshing the card.
