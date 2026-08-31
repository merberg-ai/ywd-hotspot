# RC4 Fun Changes List

Status: list-building only. Do not implement these items until the list is explicitly approved for implementation.

## 1. Clean up SSH client-key export UI

- Remove the normal-WebUI `Export Server Identity` action. Keep the underlying server host-key/recovery implementation unless there is a separate reason to remove it.
- Keep the useful client-side SSH key export flow for operators who want to log in with a key.
- Rename the action to a clearer operator-facing label. Preferred wording: `CREATE & EXPORT SSH CLIENT KEY` if the action creates a fresh key; otherwise use `EXPORT SSH CLIENT KEY`.
- Fix the mobile button layout so the action does not overflow its card or clip text.
- Make the remaining SSH key-export action responsive/full-width where appropriate and consistent with other Settings/System controls.
- Add immediate busy feedback on the Pi Zero: spinner/animation plus a temporary working label such as `CREATING KEY…` / `EXPORTING…`, with duplicate-click protection until the request completes.
- Preserve existing access-control/lock requirements and do not expose private-key material through status APIs or logs.

## 2. RC4 documentation sweep

Perform a repository-wide documentation pass so the public/operator documentation matches the actual RC4 implementation instead of the older RC3 behavior.

At minimum review and update:

- top-level `README.md`;
- installation/source-install documentation;
- factory-image / first-boot documentation;
- update/channel/rollback documentation;
- settings backup/import/restore documentation;
- SSH/key-authentication documentation;
- TGIF/network documentation;
- plugin/runtime documentation where RC4 behavior changed;
- troubleshooting/help pages and any docs linked directly from the WebUI;
- screenshots/examples/text that still describe retired RC3 behavior.

RC4 features/changes that must be represented accurately include:

- simultaneous BrandMeister + TGIF support;
- dedicated conditional TGIF Control Center tab;
- TGIF talkgroup directory/search with RF `5xxxxxx` mapping and built-in numeric fallback/Parrot handling;
- appliance-persistent TGIF favorites and watchlist;
- TGIF watchlist scanner: max 10 TGs, priority/order, dwell, manual HOLD/RESUME/NEXT/STOP, post-call hold, traffic-aware hold, TUNE and DISCONNECT controls;
- scanner state/activity projection on the main Status page;
- scanner-aware updater/channel-switch behavior, including temporary quiesce and restore of active/manual-HOLD state;
- TGIF-aware terminal/login/update presentation;
- TGIF in source/GitHub install configuration and first-boot setup;
- first-boot setup portal uses normal HTTP in RC4 instead of the RC3 self-signed HTTPS flow;
- restore/import confirmation includes redacted TGIF intent without exposing credentials;
- encrypted `.ywdsettings` preservation of BrandMeister/TGIF credentials and canonical config behavior already accepted for RC4;
- SSH password-or-key configuration, managed `AllowUsers`, root/interactive-login restrictions, and client-key export workflow;
- Digital Waterfall as the fresh-install/default loading animation while preserving explicit existing theme choices;
- mobile/navigation polish including `BM TALKGROUPS` labeling and hidden native horizontal scrollbar while retaining swipe/scroll access;
- persistent RSSI mapping and truthful OLED/I2C handling/health where those are operator-relevant;
- current updater preservation guarantees for config, plugins, SSH identity/keys, RF runtime/boot policy, network state, OLED ownership, and TGIF scanner state.

Documentation rules for this pass:

- distinguish published RC3 behavior from RC4 candidate behavior when history matters;
- do not claim the RC4 first-boot HTTP image path has been physically accepted until the actual RC4 image gate is complete;
- clearly distinguish YWD's TGIF Watchlist Scanner from BrandMeister static talkgroups and from TGIF's own network-side features;
- never document or print network passwords/private keys/secrets;
- keep instructions older-ham-friendly and practical, with concrete UI labels, examples, and troubleshooting steps;
- update docs in the same implementation slice whenever a user-visible RC4 behavior changes after this sweep.

## 3. System-managed DMR Audio Vocoder + YWD Extended prerequisite

Add a dashboard-managed `DMR AUDIO VOCODER` section under System so RX Monitor live audio can be brought online without requiring the operator to manually assemble the backend from shell instructions.

Ownership and security:

- Treat the vocoder backend as an appliance/runtime capability, not as a sandboxed plugin setting.
- All mutating controls are governed by the normal dashboard lock/unlock state and must also be rejected server-side when controls are locked.
- Do not expose a generic root shell or arbitrary command execution through the WebUI. The privileged helper exposes only narrow operations such as status, prepare/build, install/update, test, enable, disable, repair, and uninstall.
- Keep the current distribution boundary: YWD-Hotspot does not bundle mbelib source/binaries in core or the `.ywdplugin`; the manager fetches the YWD-approved pinned upstream source when explicitly requested by the operator.

Operator status card:

- Show human-readable backend state such as `NOT INSTALLED`, `READY`, `DORMANT`, `DISABLED`, `BUILDING`, `UPDATE REQUIRED`, `REPAIR REQUIRED`, or `ERROR` rather than presenting socket-activated `service=inactive` as a failure.
- Show YWD Vocoder Protocol compatibility, backend recipe/version, pinned mbelib source revision, socket enablement, effective scheduling policy, and latest self-test result without exposing secrets.
- Explain that a dormant process is normal because the backend is socket activated and demand driven.

Controls:

- `INSTALL VOCODER`
- `TEST VOCODER`
- `UPDATE VOCODER` when the approved recipe/backend is newer
- `REPAIR / REINSTALL` when compatibility, installed files, units, socket, or scheduling policy are wrong
- `ENABLE VOCODER` / `DISABLE VOCODER`, operating on the socket-activation availability rather than trying to keep the decoder process permanently running
- `UNINSTALL VOCODER`, with an explicit confirmation and without uninstalling RX Monitor itself

YWD Extended prerequisite:

- Before vocoder installation, inspect the canonical MMDVM runtime/provenance and verify the `ywd-extended` runtime plus required capabilities (`passive-dmr-voice`, `plugin-rx-monitor`, `demand-gated-dmr-voice`).
- If the appliance is already on a verified compatible YWD Extended runtime, do not rebuild it.
- If YWD Extended is missing/out-of-sync, explain why live audio needs it and offer a clear `BUILD YWD EXTENDED` / `PREPARE YWD EXTENDED` action.
- Reuse the existing canonical runtime-build/pin/cache/provenance machinery. Do not create a second source checkout, compiler recipe, or binary ownership path.
- Add a MMDVM-only ensure/build operation to the canonical runtime subsystem rather than unnecessarily rebuilding/replacing DMRGateway when the vocoder prerequisite alone is being satisfied.

Background/staged build behavior:

- Downloads, dependency preparation, source verification, compile work, and backend staging should run as a managed background job while the hotspot continues normal RF/network operation whenever technically safe.
- Pi Zero build work must remain conservative: one build job, low scheduling priority/CPU weight, and low I/O priority where practical so MMDVM/RF stays the priority workload.
- Do not stop RF merely to download or compile.
- For an upstream -> YWD Extended transition, build and fully verify the candidate first. Only the final binary activation/service reconciliation is allowed to interrupt RF.
- Immediately before that final activation, snapshot RF state and TGIF scanner state using the same preservation model as the updater, quiesce only what is required, atomically install/switch the verified runtime, restart/reconcile, run health/capability checks, and restore the prior RF/scanner intent.
- If activation fails, automatically restore the protected prior runtime/state and report rollback clearly.
- Vocoder backend compilation/installation itself should not interrupt RF unless a specific proven technical requirement is discovered during implementation.

Embedded build/install console:

- Provide an embedded read-only console/log panel inside the Vocoder section showing the actual bounded job transcript: prerequisite checks, downloads, dependency install, source pin verification, cache hit/miss, compile progress, staging, activation, socket/unit install, protocol checks, test results, rollback, and final status.
- The console is a view of a managed background job log, not an interactive shell.
- Show an immediate spinner/progress state on action buttons and a higher-level phase indicator such as `CHECKING`, `DOWNLOADING`, `BUILDING YWD EXTENDED`, `BUILDING VOCODER`, `STAGING`, `ACTIVATING`, `TESTING`, `ROLLING BACK`, `COMPLETE`, or `FAILED`.
- Poll/stream efficiently enough for a Pi Zero and allow the browser to be closed/reopened without losing job state or the transcript.
- Prevent duplicate conflicting jobs. Allow cancellation only during safe/pre-activation phases; once final activation begins, finish or roll back rather than leaving a half-installed runtime.

RX Monitor integration:

- When live audio is unavailable, RX Monitor should present a simple actionable reason (`VOCODER NOT INSTALLED`, `VOCODER DISABLED`, `YWD EXTENDED REQUIRED`, `VOCODER UPDATE REQUIRED`, etc.) and offer `OPEN VOCODER SETUP` instead of exposing backend implementation jargon.
- RX Monitor remains sandboxed and does not gain package-management, compiler, socket, or root authority.

Update/restore behavior:

- Normal YWD updates preserve an installed backend and report protocol compatibility afterward; do not silently compile/download third-party decoder code during an ordinary application update.
- If an application/runtime update makes the installed backend incompatible, report `VOCODER UPDATE REQUIRED` and leave core RF operation healthy.
- Document what settings/state are or are not included in `.ywdsettings`; no downloaded source/build cache needs to be treated as user configuration.

Acceptance intent:

- A normal operator can go from RX Monitor installed to working browser audio through the WebUI without manually invoking compiler/build/backend commands.
- When YWD Extended is already present, backend installation does not interrupt live hotspot RF/network service.
- When YWD Extended must be built, RF continues during download/compile and is interrupted only for the shortest verified activation window, with automatic rollback on failure.
- Closing/reloading the dashboard during a long Pi Zero build does not lose or duplicate the job.
- Dashboard lock, updater preservation, RF priority, and existing plugin sandbox boundaries remain intact.
