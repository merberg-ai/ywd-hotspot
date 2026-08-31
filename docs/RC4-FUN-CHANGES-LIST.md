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

Vocoder installation/distribution model:

- Retire the manual `.tar.gz` upload/extract/chmod/installer workflow as the normal operator path. The WebUI manager must be the standard installation path.
- Move the YWD-owned adapter source, installer/build recipe, unit templates, backend-management logic, and Protocol v1 test tooling into the normal version-controlled YWD-Hotspot application tree.
- Keep third-party mbelib outside the shipped application/plugin payload. On explicit operator approval, fetch the exact YWD-approved upstream mbelib repository and pinned commit defined by the installed YWD release.
- Do not expose arbitrary source URLs, branches, commits, compiler flags, or shell commands in the normal WebUI. The installed YWD release owns the approved recipe and source pin.
- Record backend recipe version, mbelib commit, architecture, compiler/build identity, installed binary hash, protocol version, and installation/test provenance so status/update/repair decisions are deterministic.
- Installation starts as a persistent managed background job rather than a long HTTP request. Closing/reloading the browser must not interrupt it; reopening System reconnects to the same phase/state/transcript.
- The install confirmation explains that Internet access is required, the approved mbelib source will be downloaded and built locally, and RF will remain online during preparation whenever safe.
- Preflight checks should include architecture/support, free disk space, required YWD core/protocol files, YWD Extended capability status, Internet/source access, package-manager availability/lock state, and build prerequisites before changing runtime state.
- Missing approved Debian build dependencies may be installed by the managed job. If apt/dpkg is already busy, wait/report truthfully rather than forcing or corrupting package-manager state. Do not automatically remove shared build dependencies during vocoder uninstall.
- Build locally with Pi-friendly scheduling and cache successful verified artifacts using an identity that includes at least architecture, mbelib commit, YWD adapter/backend recipe version, protocol version, compiler identity, and relevant build flags. A compatible verified cache hit may skip an expensive rebuild.
- Build/stage/test the vocoder candidate alongside any currently working backend. Do not replace the active backend until the candidate and Protocol v1 sanity checks pass.
- Successful final install places the YWD adapter/backend binary and managed socket/service units in their canonical locations, enables the socket-activation unit, verifies effective scheduling policy, runs Protocol v1 STATUS and decode sanity tests, and then reports `READY` even when the decoder process itself is dormant.
- Backend update uses the same transactional model: fetch/build/test the recommended candidate while the current backend remains available, switch only after validation, and restore the prior backend if final activation fails.
- Backend uninstall disables/stops socket activation and removes the managed external backend binary/units, but does not remove RX Monitor, YWD Extended, shared build dependencies, or unrelated core state.
- If YWD Extended must be built first, the single managed job chains `CHECK APPLIANCE -> BUILD/STAGE YWD EXTENDED -> BUILD/STAGE VOCODER -> ACTIVATE REQUIRED RUNTIME -> VERIFY RF/SCANNER -> ENABLE/TEST VOCODER -> COMPLETE` rather than making the operator run separate manual procedures.
- Safe preparation phases (download/build/stage) may offer cancellation. Once final runtime/backend activation begins, cancellation is disabled; the job must either finish successfully or automatically roll back.
- Normal YWD application updates preserve the external vocoder backend and only check/report compatibility; they must never surprise the operator by downloading/compiling mbelib as a side effect of an ordinary hotspot update.

Anti-footgun / recovery guardrails:

- Add an appliance-wide exclusive maintenance coordinator for state-changing operations. Vocoder install/update/repair, YWD Extended activation, normal YWD update/channel changes, plugin package mutations, and other conflicting privileged maintenance actions must not run concurrently. Read-only status remains available while the active job owns the maintenance lease.
- Enforce maintenance exclusion server-side with persistent job ownership metadata (job ID/type, PID or service identity, start timestamp, phase). Detect/recover stale leases after crashes or reboot; never rely only on disabled browser buttons.
- Use a strict two-phase model: build/download/test into dedicated staging paths first, then activate only an already-verified candidate. Never compile or unpack directly over the live MMDVM/vocoder binary or managed systemd unit files.
- Before replacing MMDVMHost or an installed vocoder backend, create a protected last-known-good rollback set containing the exact live binary/binaries, unit enablement/state, provenance, and relevant runtime intent. Do not assume a generic build cache is sufficient rollback protection.
- Persist an atomic transaction/recovery journal with durable phases such as `preparing`, `building`, `candidate-ready`, `waiting-for-rf-idle`, `activation-started`, `verifying`, `rolling-back`, and `complete`. On boot, detect interrupted maintenance and deterministically discard an incomplete staging job or verify/roll back an interrupted activation rather than leaving an ambiguous half-installed appliance.
- Once a YWD Extended candidate is fully prepared, prefer `WAITING FOR RF IDLE` before disruptive activation. Do not interrupt active MMDVM TX/RX or a traffic-held TGIF scanner session merely because compilation finished. An unlocked, clearly warned `ACTIVATE NOW` override may be offered if implementation proves it safe and useful.
- Run source checkout, dependency-independent preparation, and C/C++ compilation under a dedicated unprivileged/low-priority build identity wherever practical. Keep root authority confined to a narrow final activator that installs prevalidated files, manages units, and reconciles runtime state.
- The privileged activator accepts fixed operation/job identifiers only. Never accept a browser-provided shell command, executable path, arbitrary source URL, branch/commit override, package name, compiler flag, or destination path.
- Maintain an explicit compatibility contract/matrix covering the installed YWD release/backend recipe, YWD Vocoder Protocol version, YWD Extended extension API and required capabilities, architecture, and approved mbelib pin. Refuse unknown/incompatible combinations instead of attempting best-effort activation.
- Treat installation success as an end-to-end health gate, not merely `systemctl active`: verify socket ownership/permissions, Protocol STATUS, real decode sanity test, scheduling policy, YWD Extended capabilities, MMDVMHost recovery, configured DMR network recovery, TGIF scanner restoration when applicable, and relevant failed-unit state before committing the transaction.
- Keep an owned-file manifest for backend install/repair/uninstall. Remove only files/units/directories explicitly owned by the backend manager; never use broad guessed cleanup. Uninstall must not remove YWD Extended, RX Monitor, unrelated configuration, other runtime binaries, or shared package dependencies.
- Bound persistent console logs, staging areas, source trees, rollback sets, and build caches. Define pruning rules that preserve the current installed artifact and at least the required protected rollback artifact while preventing repeated builds from filling a small SD card.
- Cancellation is a state-machine permission, not a generic kill button. Download/build/staging may be cancellable; once activation starts, the only legal outcomes are successful verification/commit or successful rollback.
- Dashboard lock/unlock is enforced both in the UI and at the mutation API/admin-helper boundary. A handcrafted HTTP request must not bypass locked controls.
- Sanitize the embedded console environment/output. Do not expose dashboard auth material, network passwords, SSH private keys, cookies/tokens, or arbitrary environment variables; the console remains read-only and non-interactive.
- Keep ordinary YWD updates non-surprising: they may preserve/check the external backend and mark `VOCODER UPDATE REQUIRED`, but must never silently fetch/compile/install third-party decoder code as part of a normal hotspot update.
- Use one authoritative vocoder-maintenance state machine consumed by System, RX Monitor, terminal/status surfaces, and updater compatibility reporting rather than deriving contradictory state independently. Representative states include `NOT_INSTALLED`, `READY`, `DISABLED`, `UPDATE_REQUIRED`, `REPAIR_REQUIRED`, `CHECKING`, `WAITING_FOR_APT`, `DOWNLOADING`, `BUILDING`, `STAGING`, `WAITING_FOR_RF_IDLE`, `ACTIVATING`, `VERIFYING`, `ROLLING_BACK`, `COMPLETE`, and `FAILED_SAFE`.

RX Monitor integration:

- When live audio is unavailable, RX Monitor should present a simple actionable reason (`VOCODER NOT INSTALLED`, `VOCODER DISABLED`, `YWD EXTENDED REQUIRED`, `VOCODER UPDATE REQUIRED`, etc.) and offer `OPEN VOCODER SETUP` instead of exposing backend implementation jargon.
- RX Monitor remains sandboxed and does not gain package-management, compiler, socket, or root authority.

Update/restore behavior:

- Normal YWD updates preserve an installed backend and report protocol compatibility afterward; do not silently compile/download third-party decoder code during an ordinary application update.
- If an application/runtime update makes the installed backend incompatible, report `VOCODER UPDATE REQUIRED` and leave core RF operation healthy.
- Document what settings/state are or are not included in `.ywdsettings`; no downloaded source/build cache needs to be treated as user configuration.

Acceptance intent:

- A normal operator can go from RX Monitor installed to working browser audio through the WebUI without downloading/uploading/extracting a deployment archive or manually invoking compiler/build/backend commands.
- When YWD Extended is already present, backend installation does not interrupt live hotspot RF/network service.
- When YWD Extended must be built, RF continues during download/compile and is interrupted only for the shortest verified activation window, with automatic rollback on failure.
- Closing/reloading the dashboard during a long Pi Zero build does not lose or duplicate the job.
- Reinstall/update can use a verified cache when the exact backend build identity matches instead of recompiling unnecessarily.
- Power loss, browser disconnect, duplicate clicks, conflicting maintenance requests, or an interrupted activation must resolve to either the previous known-good appliance state or a fully verified new state; never a knowingly half-installed runtime.
- Activation should wait for RF idle by default when disruptive runtime replacement is required, while background preparation continues without disturbing normal hotspot operation.
- Build/source work should not require broad root execution; privileged activation remains narrowly scoped and accepts only prevalidated YWD-owned artifacts/operations.
- Dashboard lock, updater preservation, RF priority, and existing plugin sandbox boundaries remain intact.
