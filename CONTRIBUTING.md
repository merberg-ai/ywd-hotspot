# 🤝 Contributing to YWD-Hotspot

[Project README](README.md) · [Docs](docs/README.md) · [Development notes](docs/GITHUB-SETUP.md) · [Security](SECURITY.md)

---

Thanks for helping with YWD-Hotspot. The priority order is intentionally unglamorous:

> **RF safety and stability beat feature count.**

## 🧭 Current phase

- active line: `dev` / `0.1.0-alpha10-dev`
- latest user-tested checkpoint: `dev-alpha9.2-known-good`
- promoted line: `main`

Alpha10 is primarily a documentation/GitHub presentation and lightweight WebUI micro-polish pass. It deliberately does not move the MMDVM-Host or DMRGateway pins.

## 🥧 Design constraints

The performance target is the original Raspberry Pi Zero W.

Prefer:

- Python standard library where practical
- small bounded files/caches
- plain HTML/CSS/JS
- event/cached state over expensive repeated polling
- CSS animation over canvas/WebGL/framework animation
- optional side services that cannot take down the DMR path

Avoid introducing Node.js runtime dependencies, SQL/Redis, Docker, or a heavy frontend/server framework without a compelling architectural reason.

## 📡 RF safety

Do not introduce install/update/config behavior that starts RF merely because source or service definitions changed.

Starting RF must remain obvious and deliberate. Installers/updaters must preserve the operator's prior active/enabled policy.

## 🔄 GitHub update architecture

Keep managed source separate from deployed runtime:

```text
/opt/ywd-hotspot/repo    managed source
/opt/ywd-hotspot/app     deployed application
```

Keep canonical-origin verification, dirty-content refusal, candidate staging/validation, protected backups, rollback behavior, and RF-state preservation unless a stronger replacement is demonstrated.

## ⚙️ Configuration rules

Canonical configuration:

```text
/etc/ywd-hotspot/config.json
```

Generated MMDVM-Host/DMRGateway INI files are outputs, not independent sources of truth.

Configuration changes should retain:

- normalization/validation
- transactional apply
- rollback/history behavior
- secret redaction
- appropriate service-impact classification

## 📌 Upstream pins

Do not casually update `pins.env` in the same change as unrelated UI/docs/application work.

An upstream radio-stack pin move changes the calibration/stability baseline and should be isolated and hardware-tested.

## ✅ Basic checks

Before a PR or checkpoint, run at least:

```bash
bash -n \
  INSTALL.sh INSTALL-core.sh \
  UPDATE.sh UPDATE-core.sh \
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh \
  MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh \
  UNINSTALL.sh \
  bin/ywd-hotspotctl bin/ywd-hotspotctl-core bin/ywd-ui.sh \
  lab/mmdvm-diag.sh

python3 -m py_compile lib/*.py
```

If Node.js is available:

```bash
node --check web/app.js
node --check web/app-core.js
node --check web/talkgroups.js
node --check web/ui-polish.js
```

Remove generated `__pycache__` before committing; `.gitignore` excludes it.

Changes touching systemd, sudoers, config generation, install/update, or RF behavior still need a real Pi test before being called known-good.

## 🎨 WebUI changes

The dashboard intentionally uses plain HTML/CSS/JS and a restrictive CSP.

For UI polish:

- prefer same-origin external CSS/JS
- do not weaken CSP just to make styling easier
- keep animations small and browser-side
- preserve responsive behavior on narrow mobile screens
- avoid new polling loops for purely visual features
- preserve `prefers-reduced-motion` where practical

## 🐛 Bug reports

Useful reports include:

- version + branch/commit (`ywd-hotspotctl source`)
- Raspberry Pi model / OS
- MMDVM HAT + firmware
- browser/device for WebUI issues
- what changed immediately before the problem
- expected vs actual behavior
- sanitized diagnostics when relevant

Never attach a raw protected backup or reusable credential.

## 🌿 Development workflow

New work normally lands on `dev`, gets validated, then is exercised on the test hotspot. When a build is explicitly confirmed, a checkpoint branch can preserve that exact state before the next experiment begins.

See **[docs/GITHUB-SETUP.md](docs/GITHUB-SETUP.md)** for the branch/update model.
