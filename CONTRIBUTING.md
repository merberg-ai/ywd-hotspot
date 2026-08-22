# 🤝 Contributing to YWD-Hotspot

[Project README](README.md) · [Docs](docs/README.md) · [Development notes](docs/GITHUB-SETUP.md) · [Repository policy](docs/REPOSITORY.md) · [Security](SECURITY.md)

---

Thanks for helping with YWD-Hotspot. The priority order is intentionally unglamorous:

> **RF safety and stability beat feature count.**

## 🧭 Current phase

The physically tested `0.2.0-rc1` source is preserved by:

```text
v0.2.0-rc1
checkpoint-release-0.2.0-rc1-image-proven
```

`main` is the promoted public line and `dev` is the accepted integration baseline. Post-release documentation-only corrections may move `main`/`dev` beyond the immutable RC tag without changing the source/image that was physically accepted.

New runtime/RF work should branch deliberately from the appropriate current baseline and earn its own hardware acceptance before being described as known-good.

## 🥧 Design constraints

The performance target is the original Raspberry Pi Zero W.

Prefer:

- Python standard library where practical;
- small bounded files/caches;
- plain HTML/CSS/JS;
- event/cached state over expensive repeated polling;
- CSS animation over canvas/WebGL/framework animation;
- browser-side expensive audio/presentation work;
- optional side services that cannot take down the DMR path.

Avoid introducing Node.js runtime dependencies, SQL/Redis, Docker, or a heavy frontend/server framework without a compelling architectural reason.

The local loopback Mosquitto broker is a deliberate trusted telemetry transport, not a general LAN service or invitation to add a distributed backend stack.

## 📡 RF safety

Do not introduce install/update/config/restore/plugin/SSH behavior that starts RF merely because source or service definitions changed.

Starting RF must remain obvious and deliberate. Installers/updaters must preserve the operator's prior active/enabled policy unless the operator explicitly changes it.

MMDVM-Host remains the sole modem/RF owner. No plugin/dashboard/SSH helper gets direct RF TX authority merely because it can observe state or run privileged maintenance actions.

## 🔄 GitHub update architecture

Keep managed source separate from deployed runtime:

```text
/opt/ywd-hotspot/repo    managed source
/opt/ywd-hotspot/app     deployed application
```

Keep canonical-origin verification, dirty-content refusal, candidate staging/validation, protected backups, rollback behavior, privileged-bridge coherence, plugin quiesce/restore, and RF-state preservation unless a stronger replacement is demonstrated.

## ⚙️ Configuration rules

Canonical configuration:

```text
/etc/ywd-hotspot/config.json
```

Generated MMDVM-Host/DMRGateway INI files are outputs, not independent sources of truth.

Configuration changes should retain:

- normalization/validation;
- transactional/scoped apply;
- rollback/history behavior;
- secret redaction;
- appropriate service-impact classification.

Simplex/duplex is explicit. Duplex uses separate hotspot RX/TX frequencies and TS1/TS2-aware behavior.

## 📌 Upstream/runtime pins

Do not casually update `pins.env` in the same change as unrelated UI/docs/application work.

An upstream radio-stack pin move or YWD extension patch/API move changes the calibration/stability baseline and should be isolated and hardware-tested.

Current RC1 identities are documented in `README.md`, `docs/DMR-VOICE.md`, and `docs/BUILDING.md`.

## 🔑 SSH changes

Public YWD-Hotspot OS images intentionally ship SSH OFF. Current dashboard-managed SSH enforces public-key-only authentication, password/root login disabled, unique appliance host keys, and one-time client-private-key export.

Changes touching any of these require extra scrutiny:

- OpenSSH package/factory state;
- `ywd` login-user behavior;
- passwordless sudo interaction;
- authorized-key enrollment/revocation;
- host-key generation/export;
- sshd policy;
- boot enable/disable semantics;
- public exposure guidance.

Never introduce a default/reusable SSH password or builder-private key into a public image.

See **[docs/SSH.md](docs/SSH.md)** and **[SECURITY.md](SECURITY.md)**.

## ✅ Basic checks

Before a PR/checkpoint/release candidate, run at least:

```bash
python3 lib/candidate_validate.py .
python3 -m py_compile lib/*.py os/builder/*.py

bash -n \
  INSTALL.sh INSTALL-core.sh \
  UPDATE.sh UPDATE-core.sh \
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh \
  MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh \
  UNINSTALL.sh \
  bin/ywd-hotspotctl bin/ywd-hotspotctl-core bin/ywd-ui.sh \
  lab/mmdvm-diag.sh \
  os/builder/BUILD.sh os/builder/RUN-BUILD.sh \
  os/builder/BUILD-PUBLIC-RELEASE.sh \
  os/pi-gen/stage2/20-ywd-runtime/01-run.sh \
  os/pi-gen/stage2/25-ywd-firstboot/01-run.sh
```

If Node.js is available:

```bash
for js in web/*.js; do node --check "$js"; done
```

Remove generated `__pycache__` before committing; `.gitignore` excludes it.

Changes touching systemd, sudoers, SSH, config generation, install/update/restore, telemetry ownership, first boot or RF behavior still need a real Pi test before being called known-good.

## 🎨 WebUI changes

The dashboard intentionally uses plain HTML/CSS/JS and a restrictive CSP.

For UI polish:

- prefer same-origin external CSS/JS;
- add explicit static routes for new standalone assets when the dashboard server requires them;
- keep candidate validation aware of release-critical dynamic assets/routes;
- do not weaken CSP just to make styling easier;
- keep animations small and browser-side;
- preserve responsive behavior on narrow mobile screens;
- avoid new Pi polling loops for purely visual features;
- preserve `prefers-reduced-motion` where practical;
- never invent missing telemetry values merely to animate a meter.

RSSI in particular is optional modem-firmware data; a UI must work cleanly with BER and no RSSI.

## 🐛 Bug reports

Useful reports include:

- version + branch/commit (`ywd-hotspotctl source`);
- Raspberry Pi model / OS;
- MMDVM HAT + firmware;
- selected MMDVM runtime variant;
- browser/device for WebUI bugs;
- what changed immediately before the problem;
- expected vs actual behavior;
- sanitized diagnostics when relevant.

Never attach a raw protected backup, reusable credential, SSH private key/server-identity archive, or unsanitized runtime state.

## 🌿 Development workflow

A typical runtime change should:

1. start from the intended verified parent;
2. stay scoped;
3. pass source/candidate validation;
4. be compared for exact changed-file scope;
5. be exercised on real hardware if it affects runtime/RF/system behavior;
6. gain a checkpoint when the known-good state is valuable;
7. be promoted intentionally.

Release tags/checkpoints remain immutable evidence. Documentation fixes after a release belong on moving branches and do not rewrite what was actually flashed/tested.

See **[docs/GITHUB-SETUP.md](docs/GITHUB-SETUP.md)** for the branch/update model.
