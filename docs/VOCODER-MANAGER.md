# DMR Audio Vocoder Manager — RC4 Development

[← Docs index](README.md) · [External vocoder](VOCODER.md) · [Passive DMR voice](DMR-VOICE.md)

RC4 is moving DMR RX Monitor audio setup from a manual deployment-kit workflow to a normal YWD-Hotspot System-page manager. The manager is being enabled in controlled gates so a browser action cannot accidentally replace a working RF runtime.

## What appears under System

The dashboard has a `DMR AUDIO VOCODER` card. Passive status reads the appliance state without changing MMDVMHost, changing RF services, installing packages, or waking the socket-activated decoder.

It reports:

- operator-facing state such as `NOT INSTALLED`, `READY`, `DISABLED`, `UPDATE REQUIRED`, `REPAIR REQUIRED`, or `YWD EXTENDED REQUIRED`;
- whether the decoder process is active or normally `DORMANT`;
- YWD Vocoder Protocol version expected by this release;
- the YWD-owned backend recipe version;
- the approved pinned mbelib revision;
- socket-unit enablement/runtime state;
- effective `Nice` / `CPUWeight` scheduling policy;
- YWD Extended runtime/capability readiness;
- the last recorded managed self-test when one exists;
- the appliance maintenance lease state;
- the latest bounded managed-job transcript when one exists.

A dormant decoder process is **normal**. The real backend is socket activated and demand driven. The System card deliberately does not send a Protocol `STATUS` request during polling because doing so would wake the decoder just to prove that it can sleep.

The separate `MODEM / MMDVM` System card remains passive inventory. Earlier disabled placeholders for `BUILD / UPDATE YWD-EXTENDED` and HAT firmware maintenance were removed so there is not a second competing runtime-maintenance UI. YWD Extended preparation needed for DMR audio belongs to this Vocoder workflow.

## Guarded install-readiness job

The first real background operation is `CHECK INSTALL READINESS`.

It requires the normal dashboard unlock and starts a persistent systemd worker. The browser request returns immediately; the worker continues if the browser is reloaded or closed. The managed console reconnects to the bounded transcript through the normal status API.

This readiness job checks, without changing the live runtime:

- supported CPU architecture;
- free disk space, with additional headroom required when YWD Extended also needs to be prepared;
- current YWD Extended runtime/capability status;
- required base/package/build tools;
- dpkg consistency;
- whether another apt/dpkg process is already active;
- reachability of GitHub and the approved mbelib source;
- current system temperature where Linux exposes it.

Missing compiler/build tools are reported as work the later managed installer will need to perform. A busy package manager or excessive temperature is treated as a temporary blocker rather than something YWD should force through.

### What the readiness worker is allowed to do

This gated worker may only:

- claim/release the appliance maintenance lease;
- read prerequisite/system state;
- perform a read-only approved-source reachability check;
- write its bounded job state/log and a preflight report under `/var/lib/ywd-hotspot/vocoder/`.

It does **not**:

- run `apt install`;
- clone/download/build mbelib or MMDVMHost source;
- invoke a compiler;
- stop/restart MMDVMHost, DMRGateway, BrandMeister, TGIF, or the scanner;
- replace MMDVMHost or the vocoder backend;
- enable/disable the vocoder socket;
- flash the physical MMDVM HAT.

The worker runs as the unprivileged `ywd-hotspot` account with `NoNewPrivileges`, a read-only system filesystem, a narrow writable `/var/lib/ywd-hotspot` state area, low CPU priority, and idle-class I/O scheduling.

## Install/build actions are still gated

`INSTALL VOCODER`, `BUILD YWD EXTENDED`, `TEST VOCODER`, update/repair, enable/disable, and uninstall controls are **not enabled yet**.

They will be added only after the persistent job runner, source/build staging, narrow privileged activator, rollback/recovery journal, RF-idle activation, and RF/TGIF-scanner preservation paths pass their own gates.

Until the managed installation slice is accepted, the manual external deployment-kit workflow documented in [VOCODER.md](VOCODER.md) remains the existing installation method for development systems that need it.

## YWD Extended prerequisite

The manager uses the canonical MMDVM runtime identity instead of guessing from service state. Live RX audio requires the current verified `ywd-extended` runtime with all of these capabilities:

```text
passive-dmr-voice
plugin-rx-monitor
demand-gated-dmr-voice
```

If the current runtime does not satisfy that exact contract, the card reports `YWD EXTENDED REQUIRED`. The readiness job reports the prerequisite but does not rebuild or replace MMDVMHost.

## Appliance-wide maintenance coordinator

RC4 has a shared maintenance-lease primitive in `lib/maintenance_coordinator.py`.

The lease records only bounded operational metadata such as:

- job ID and type;
- owning PID/service identity;
- boot identity;
- start/update timestamps;
- phase;
- whether cancellation is currently safe.

It does not contain dashboard passwords, BrandMeister/TGIF credentials, SSH private keys, cookies, arbitrary environment variables, or shell commands.

Claims are serialized with `flock`. The coordination lock is group-writable by the trusted YWD service group so the root launcher/recovery helper and the unprivileged worker serialize against the same inode. A live conflicting job is rejected. A lease from a previous boot or a dead owner is reported as stale and may be recovered. Read-only status never steals or deletes a live lease.

The vocoder manager is the first consumer. Normal updater/channel changes and plugin package mutations are **not yet migrated onto this coordinator**; that integration remains an anti-footgun gate before mutating vocoder install/build controls are enabled.

## Approved backend identity

The manager describes the same selected backend baseline already used by the accepted RX Monitor work:

```text
YWD Vocoder Protocol: 1
recipe:               mbelib-v1 / 1
mbelib commit:         9a04ed5c78176a9965f3d43f7aa1b1f5330e771f
socket unit:           ywd-vocoder-mbelib.socket
service unit:          ywd-vocoder-mbelib.service
binary:                /usr/local/libexec/ywd-vocoder-mbelib
socket:                /run/ywd-vocoder.sock
expected Nice:         0
expected CPUWeight:    200
```

YWD-Hotspot still does **not** bundle mbelib source or a prebuilt mbelib decoder in core or in a `.ywdplugin` package.

## State interpretation

`READY` means the backend files/units and YWD scheduling policy look complete, socket activation is available, and the current YWD Extended prerequisite is satisfied. The decoder service itself may say `inactive`; the card renders that as `DORMANT`, not as a failure.

A working external/deployment-kit installation that predates manager provenance can still report `READY`. It is labeled `LEGACY/EXTERNAL` until a later managed repair/reinstall transaction adopts it and writes deterministic install provenance.

`REPAIR REQUIRED` means required backend files/units or scheduling/socket health are incomplete. `DISABLED` means the backend is installed but socket activation is not enabled. `UPDATE REQUIRED` is reserved for a managed installation whose recorded recipe/protocol/mbelib identity no longer matches the approved identity owned by the installed YWD release.

## Regressions

Focused source-only regressions:

```bash
sudo env PYTHONDONTWRITEBYTECODE=1 \
  python3 /opt/ywd-hotspot/repo/tools/vocoder-manager-foundation-smoke.py

sudo env PYTHONDONTWRITEBYTECODE=1 \
  python3 /opt/ywd-hotspot/repo/tools/vocoder-job-preflight-smoke.py
```

These tests do not transmit RF, install packages, access the Internet, compile software, start the decoder, or replace MMDVMHost. The preflight smoke injects synthetic facts and verifies successful and failed-safe job completion, maintenance-lease release, bounded logs, dashboard authorization, and the unprivileged worker sandbox.
