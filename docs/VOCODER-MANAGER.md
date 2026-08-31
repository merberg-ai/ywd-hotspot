# DMR Audio Vocoder Manager — RC4 Foundation

[← Docs index](README.md) · [External vocoder](VOCODER.md) · [Passive DMR voice](DMR-VOICE.md)

RC4 is moving DMR RX Monitor audio setup from a manual deployment-kit workflow to a normal YWD-Hotspot System-page manager. This document describes the **first, read-only foundation slice** only.

## What appears under System

The dashboard now has a `DMR AUDIO VOCODER` card. The card reads the appliance state without starting a build, changing MMDVMHost, changing RF services, installing packages, or waking the socket-activated decoder.

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

## No install/build action yet

This foundation intentionally exposes only `REFRESH STATUS`.

`INSTALL VOCODER`, `BUILD YWD EXTENDED`, `TEST VOCODER`, update/repair, enable/disable, and uninstall controls are **not enabled in this slice**. They will be added only after the persistent job runner, staging/verification path, narrow privileged activator, rollback journal, and RF/scanner preservation path pass their own gates.

Until that later slice is accepted, the manual external deployment-kit workflow documented in [VOCODER.md](VOCODER.md) remains the existing installation method for development systems that need it.

## YWD Extended prerequisite

The manager uses the canonical MMDVM runtime identity instead of guessing from service state. Live RX audio requires the current verified `ywd-extended` runtime with all of these capabilities:

```text
passive-dmr-voice
plugin-rx-monitor
demand-gated-dmr-voice
```

If the current runtime does not satisfy that exact contract, the card reports `YWD EXTENDED REQUIRED`. This foundation does not rebuild or replace MMDVMHost.

## Appliance-wide maintenance coordinator

RC4 now has a shared maintenance-lease primitive in `lib/maintenance_coordinator.py`.

The lease records only bounded operational metadata such as:

- job ID and type;
- owning PID/service identity;
- boot identity;
- start/update timestamps;
- phase;
- whether cancellation is currently safe.

It does not contain dashboard passwords, BrandMeister/TGIF credentials, SSH private keys, cookies, arbitrary environment variables, or shell commands.

Claims are serialized with `flock`. A live conflicting job is rejected. A lease from a previous boot or a dead owner is reported as stale and may be recovered explicitly. Read-only status never steals or deletes a live lease.

The vocoder manager is the first consumer. Normal updater/channel changes and plugin package mutations are **not yet migrated onto this coordinator in this foundation slice**; that integration is a later anti-footgun gate before mutating vocoder controls are enabled.

## Approved backend identity

The foundation currently describes the same selected backend baseline already used by the accepted RX Monitor work:

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

## Source-only regression

The focused regression is:

```bash
sudo env PYTHONDONTWRITEBYTECODE=1 \
  python3 /opt/ywd-hotspot/repo/tools/vocoder-manager-foundation-smoke.py
```

It does not transmit RF, compile software, install packages, start the decoder, or replace MMDVMHost. It checks maintenance exclusion/stale recovery, state classification, passive polling, dashboard asset wiring, and the fact that mutation controls remain disabled.
