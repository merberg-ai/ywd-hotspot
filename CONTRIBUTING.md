# 🤝 Contributing to YWD-Hotspot

[Project README](README.md) · [Docs](docs/README.md) · [Development notes](docs/GITHUB-SETUP.md) · [OS image build](docs/OS-IMAGE-BUILD.md) · [Security](SECURITY.md)

---

Thanks for helping with YWD-Hotspot. The priority order is intentionally unglamorous:

> **RF safety and stability beat feature count.**

## 🧭 Current phase

- promoted line: `main` / `0.1.0-alpha12.2-dev`
- normal core/application development line: `dev` / currently the same Alpha12.2 integrated baseline
- proven integrated checkpoint: `dev-alpha12.2-os-integrated-known-good`
- experimental plugin/MMDVM work: `dev-plugins`, kept separate from `main`

The promoted Alpha12.2 baseline includes the unified application + OS image builder, secure first boot, single-owner OLED architecture, detached WebUI updater and current LIVE DMR instrumentation. Plugin/MMDVM experiments are intentionally not part of the core `main` runtime unless deliberately promoted later.

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

Do not introduce install/update/image/config behavior that starts RF merely because source, services, Wi-Fi, or setup state changed.

Starting RF must remain obvious and deliberate. Installers/updaters must preserve the operator's prior active/enabled policy. Factory OS images must keep RF disabled until secure first-boot setup explicitly enables it.

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

Current canonical schema is **5**.

Generated MMDVM-Host/DMRGateway INI files are outputs, not independent sources of truth.

Configuration changes should retain:

- normalization/validation
- transactional apply
- rollback/history behavior
- secret redaction
- appropriate service-impact classification

## 🥧 OS image-builder rules

The builder under `os/` packages the current root application revision. Do not create a second drifting application copy inside the OS stages.

Before image work is considered proven:

```bash
bash os/builder/DOCTOR.sh
bash os/builder/BUILD.sh
```

and physically validate the image on the Pi Zero.

Current supported builder preseeding is **Wi-Fi only** through ignored `os/local/provision.env`. Do not document or depend on ad-hoc full radio/BrandMeister rootfs edits as if they were a supported provisioning interface.

Keep builder-local secrets private, especially:

```text
os/local/provision.env
os/local/ywd-os-dev_ed25519
```

See **[docs/OS-IMAGE-BUILD.md](docs/OS-IMAGE-BUILD.md)**.

## 📌 Upstream pins

Do not casually update `pins.env` in the same change as unrelated UI/docs/application work.

An upstream radio-stack pin move changes the calibration/stability baseline and should be isolated and hardware-tested. The OS image builder consumes the same pins, so a pin change affects both in-place installs and future images.

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
  lib/admin_dispatch.sh lib/setup_entry.sh lib/oled_owner.sh \
  lab/mmdvm-diag.sh

python3 -m py_compile lib/*.py
```

If Node.js is available:

```bash
for f in web/*.js; do node --check "$f"; done
```

For OS changes:

```bash
bash -n os/builder/BUILD.sh os/builder/DOCTOR.sh os/builder/CONFIGURE-WIFI.sh
bash os/builder/DOCTOR.sh
```

Remove generated `__pycache__` before committing; `.gitignore` excludes it.

Changes touching systemd, sudoers, config generation, install/update, OS first boot, OLED ownership, or RF behavior still need a real Pi test before being called known-good.

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
- install type: repository install or YWD-Hotspot OS image
- browser/device for WebUI issues
- what changed immediately before the problem
- expected vs actual behavior
- sanitized diagnostics when relevant

Never attach a raw protected backup, builder-local private key, or reusable credential.

## 🌿 Development workflow

New normal/core work lands on `dev`, gets validated, then is exercised on the test hotspot. When a build is explicitly confirmed, a checkpoint branch can preserve that exact state before the next experiment begins. Promotion to `main` is deliberate.

Experimental plugin/MMDVM work remains on `dev-plugins` until there is an explicit decision to integrate any of it into core.

See **[docs/GITHUB-SETUP.md](docs/GITHUB-SETUP.md)** for the branch/update model.
