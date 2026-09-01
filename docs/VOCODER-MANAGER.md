# DMR Audio Vocoder Manager — RC4 Development

[← Docs index](README.md) · [External vocoder](VOCODER.md) · [Passive DMR voice](DMR-VOICE.md)

RC4 is moving DMR RX Monitor audio setup from a manual deployment-kit workflow to a normal YWD-Hotspot System-page manager. The manager is being enabled in controlled gates so a browser action cannot accidentally replace a working RF runtime.

## Dashboard-startup boundary

The vocoder manager is **not allowed to redesign or gate normal dashboard startup**. During this work a set of startup/splash experiments made the Pi Zero dashboard substantially slower and, in several iterations, prevented the final UI from assembling. Hardware A/B testing restored `web/app.js` byte-for-byte to the accepted pre-vocoder dashboard startup implementation.

That recovered file is now pinned by the vocoder staging regression. Vocoder work stays inside the System extension and background-job paths. The current dashboard may still finish the hero artwork shortly after the splash closes; that known behavior is intentionally left alone for this RC4 work.

## What appears under System

The dashboard has a `DMR AUDIO VOCODER` card. Passive status reads appliance state without changing MMDVMHost, changing RF services, installing packages, or waking the socket-activated decoder.

It reports operator-facing backend/runtime state, decoder process mode, Protocol version, approved recipe/mbelib pin, socket activation, scheduling policy, YWD Extended readiness, maintenance state, and the latest bounded managed-job transcript.

A dormant decoder process is **normal**. The real backend is socket activated and demand driven. Normal System polling deliberately does not send Protocol `STATUS`, because doing so would wake the decoder just to prove that it can sleep.

The separate `MODEM / MMDVM` card remains passive inventory. YWD Extended work required specifically for DMR audio belongs to this Vocoder workflow, not to a second MMDVM maintenance UI.

## Fast status vs exact background verification

Exact MMDVM runtime verification can take tens of seconds on the reference Pi Zero, so it is never part of normal dashboard polling.

Normal status uses the last verified persisted MMDVM runtime identity bound to the pins expected by the installed YWD release. Before a readiness/build decision, the guarded background worker performs the expensive **exact installed-runtime verification** using the canonical MMDVM helpers.

Idle System polling is slow/lightweight. During a managed job, polling speeds up so phase and console updates are visible without turning ordinary status refresh into a heavyweight operation.

## CHECK INSTALL READINESS — hardware accepted

`CHECK INSTALL READINESS` requires the normal dashboard unlock and starts a persistent systemd worker. The browser request returns immediately and the worker continues if the page is closed or reloaded.

The readiness job checks without changing the live runtime:

- supported CPU architecture;
- free disk space;
- exact installed YWD Extended runtime/capability identity;
- required package/build tools;
- dpkg consistency and active apt/dpkg work;
- reachability of GitHub and the approved mbelib source;
- current CPU temperature where Linux exposes it.

The real Pi Zero readiness job passed on 2026-08-31: `COMPLETE / 100%`, worker exit `0`, maintenance lease released, and zero failed systemd units. See `docs/checkpoints/rc4-vocoder-preflight-job-hardware-pass.md`.

The readiness operation itself still does **not** download source, compile, install packages, stop/restart RF, replace MMDVMHost, or modify the live vocoder backend.

## PREPARE VOCODER CANDIDATE — implemented, hardware build gate pending

The next gated operation is `PREPARE VOCODER CANDIDATE`.

This operation is deliberately **build-only**. It may perform real network and compiler work, but all output stays under YWD state/cache. It cannot install or activate the candidate.

The preparation flow is:

```text
exact preflight
    ↓
fetch approved mbelib commit
    ↓
verify exact source HEAD
    ↓
cmake Release configuration
    ↓
build libmbe.a with one job
    ↓
build YWD Protocol v1 adapter
    ↓
run staged 10-frame decode self-test
    ↓
write verified candidate cache/provenance
    ↓
COMPLETE
```

YWD-owned adapter source now ships in core as:

```text
lib/vocoder_mbelib_adapter.cpp
```

mbelib itself is **not bundled**. The worker fetches only the approved upstream repository and exact commit owned by the installed YWD recipe:

```text
https://github.com/szechyjs/mbelib.git
9a04ed5c78176a9965f3d43f7aa1b1f5330e771f
```

The staged builder is `lib/vocoder_backend_build.py`. It uses a Release build, disables mbelib's test framework for this appliance build, builds the static library with one job for Pi Zero friendliness, then links the YWD adapter against that static library.

The adapter implements YWD Vocoder Protocol v1 over AF_UNIX and provides STATUS, RESET, and AMBE49 DECODE. Its built-in `--self-test` exercises ten AMBE49 frames and must produce the expected 8 kHz mono s16le payload (`10 × 160 × 2 = 3200` PCM bytes) before the candidate can be published as prepared.

### Staging/cache ownership

Preparation writes only below:

```text
/var/lib/ywd-hotspot/vocoder/
```

Candidate/source caches are YWD-owned state. Cache identity includes the recipe, Protocol version, exact mbelib pin, YWD adapter SHA-256, architecture, compiler identity, and build flags. A cache hit is not trusted blindly: the candidate hash and self-test are checked again before reuse.

Only two candidate-cache generations are retained and recent job directories are bounded. The managed console remains bounded to 64 KiB / 80 visible lines.

### What PREPARE is allowed to change

It may:

- claim/update/release the appliance maintenance lease;
- perform the same exact preflight as the readiness operation;
- fetch the approved pinned mbelib source;
- compile mbelib and the YWD adapter as the unprivileged `ywd-hotspot` user;
- write build/source caches, staged files, provenance, and bounded job logs under `/var/lib/ywd-hotspot/vocoder/`;
- self-test the staged candidate;
- safely cancel during cancellable download/build/staging phases.

It does **not**:

- run `apt install` or repair missing packages;
- write `/usr/local/libexec/ywd-vocoder-mbelib`;
- install/replace/enable/disable `ywd-vocoder-mbelib.service` or `.socket`;
- stop/restart MMDVMHost or DMRGateway;
- change BrandMeister, TGIF, or scanner session state;
- replace/build/activate YWD Extended;
- flash MMDVM HAT firmware.

If a compiler/source/self-test error occurs, the managed job reports `FAILED_SAFE`, releases the maintenance lease, and leaves the live backend/runtime untouched. Handled failed-safe/canceled job exits are accepted by the runtime-only worker unit so they do not become misleading failed systemd units.

## Safe cancellation

The root helper exposes no arbitrary process controls. Cancellation accepts only the exact current managed `job_id`, verifies that the appliance lease belongs to a vocoder preflight/prepare job, verifies the current phase is marked cancellable, and then sends SIGTERM only to the main process of `ywd-vocoder-job.service`.

The browser cannot choose a PID, service name, signal, command, source URL, commit, package, compiler, path, or build flag.

The System card shows `CANCEL JOB` only while a matching job is active, and enables it only while cancellation is safe.

## Worker security boundary

The background worker runs as `ywd-hotspot`, not root, with:

- `NoNewPrivileges=true`;
- `ProtectSystem=strict`;
- `ProtectHome=true`;
- restricted namespaces/realtime access;
- `ReadWritePaths=/var/lib/ywd-hotspot`;
- `Nice=10`;
- `CPUWeight=50`;
- idle-class I/O scheduling.

Root authority remains limited to the fixed launch/cancel helper actions and future narrow activation helpers. Compilation and source checkout do not run as root.

## Live install/activation is still gated

The following controls are still **not enabled**:

- `INSTALL VOCODER` / activate prepared candidate;
- package/dependency installation;
- `BUILD YWD EXTENDED` / MMDVM replacement;
- live vocoder update/repair;
- enable/disable;
- uninstall;
- live Protocol/decode test through the installed socket.

Those require the later privileged activation transaction, protected last-known-good rollback, crash/power-loss journal, RF-idle activation, and RF/TGIF-scanner preservation gates.

Until live managed activation is accepted, the existing external/deployment-kit backend can remain installed and continue serving RX Monitor. Preparing a candidate does not overwrite or disturb it.

## YWD Extended prerequisite

Live RX audio requires current verified `ywd-extended` with:

```text
passive-dmr-voice
plugin-rx-monitor
demand-gated-dmr-voice
```

The current preparation gate verifies that runtime exactly. If it is not ready, the job records that YWD Extended work will be required, but this slice does not rebuild or replace MMDVMHost.

## Appliance-wide maintenance coordinator

The shared lease in `lib/maintenance_coordinator.py` serializes managed vocoder jobs and records only bounded operational metadata: job/type/PID/service, boot identity, timestamps, phase, and cancellability. It stores no credentials, private keys, cookies, arbitrary shell commands, or browser-controlled environment data.

A root launch reservation closes the browser-request/systemd-start race; the worker adopts the exact reserved job. Conflicting live maintenance is rejected, and stale previous-boot/dead-owner leases can be recovered safely.

The vocoder manager is currently the first consumer. Updater/channel and plugin-package mutations still need to be migrated onto the shared coordinator before live vocoder activation is enabled.

## Approved backend identity

```text
YWD Vocoder Protocol: 1
recipe:               mbelib-v1 / 1
mbelib commit:         9a04ed5c78176a9965f3d43f7aa1b1f5330e771f
socket unit:           ywd-vocoder-mbelib.socket
service unit:          ywd-vocoder-mbelib.service
live binary:           /usr/local/libexec/ywd-vocoder-mbelib
socket:                /run/ywd-vocoder.sock
expected Nice:         0
expected CPUWeight:    200
```

YWD-Hotspot does not bundle mbelib source or a prebuilt mbelib decoder in core or a `.ywdplugin` package.

## State interpretation

`READY` means the existing live backend files/units and YWD scheduling policy look complete, socket activation is available, and the persisted current-pin YWD Extended prerequisite is satisfied. The service itself may be inactive; the card intentionally renders that as `DORMANT`.

A working pre-manager deployment-kit backend can remain `READY · LEGACY/EXTERNAL`. Preparing a new candidate does not adopt or modify that installation. Managed provenance is written only by a future accepted activation transaction.

`REPAIR REQUIRED`, `DISABLED`, `UPDATE REQUIRED`, and `YWD EXTENDED REQUIRED` keep their existing meanings for the live backend/runtime.

## Regressions

Source-only/offline regressions:

```bash
sudo env PYTHONDONTWRITEBYTECODE=1 \
  python3 /opt/ywd-hotspot/repo/tools/vocoder-manager-foundation-smoke.py

sudo env PYTHONDONTWRITEBYTECODE=1 \
  python3 /opt/ywd-hotspot/repo/tools/vocoder-job-preflight-smoke.py

sudo env PYTHONDONTWRITEBYTECODE=1 \
  python3 /opt/ywd-hotspot/repo/tools/vocoder-build-staging-smoke.py
```

The new staging smoke explicitly pins the exact recovered Pi Zero `web/app.js` Git blob so future vocoder work cannot accidentally re-enter the global dashboard startup path. These source-only tests do not access the Internet, compile mbelib, or modify RF. The real fetch/build/self-test remains a hardware gate on the reference Pi Zero.
