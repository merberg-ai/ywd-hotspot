# 🌿 GitHub / Development Notes

[← Docs index](README.md) · [Project README](../README.md) · [Contributing](../CONTRIBUTING.md) · [OS image build](OS-IMAGE-BUILD.md) · [Upgrading](UPGRADING.md)

---

Canonical repository:

```text
https://github.com/merberg-ai/ywd-hotspot
```

## 🌳 Branch model

| Branch / checkpoint | Purpose |
|---|---|
| `main` | promoted/conservative appliance line carrying the Alpha12.2 integrated runtime baseline plus any later main-only docs/metadata commits |
| `dev` | normal core/application + OS development line; currently retains the same Alpha12.2 runtime baseline |
| `dev-alpha12.2-os-integrated-known-good` | physically proven unified application + OS-builder checkpoint |
| `dev-plugins` | separate experimental plugin/MMDVM line; intentionally not included in `main` |
| `dev-plugins-alpha18.1-known-good` | current physically proven plugin/MMDVM framework checkpoint |
| temporary feature / `dev-os-*` branches | isolated work before deliberate integration/promotion |

Current promoted **runtime baseline**:

```text
0.1.0-alpha12.2-dev
41f1cf9fcf94b3880d5cf11fb35e2cccb6fd3afd
```

Documentation-only commits may sit above that runtime commit on `main` without changing the installed application version or RF/runtime payload. Plain `dev` currently remains at the tested runtime baseline itself.

During normal core development, new non-plugin work lands on `dev` first. A build is promoted to `main` only after deliberate hardware validation. Experimental plugin work remains isolated on `dev-plugins` until there is an explicit decision to promote any of it into core.

The historical long-lived `dev-os` branch is reference/history; do not merge it wholesale into current development.

## 📥 Clone

Promoted line:

```bash
git clone --branch main https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

The branch argument is optional because `main` is the repository default:

```bash
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Normal development line:

```bash
git clone --branch dev https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Normal Git clones preserve executable modes. If source came through a ZIP/Windows copy and modes were lost, running entry scripts through Bash is sufficient for recovery, for example:

```bash
sudo bash ./INSTALL.sh
```

`.gitattributes` keeps important text/source on LF endings.

## 🧱 Source vs deployed runtime

A hotspot does not run directly from a mutable Git tree:

```text
/opt/ywd-hotspot/repo    managed Git source checkout
/opt/ywd-hotspot/app     deployed runtime copy
```

This separation lets YWD-Hotspot fetch and validate a candidate before touching the running application.

Non-secret source provenance is recorded in:

```text
/etc/ywd-hotspot/build-info.json
```

and displayed by:

```bash
ywd-hotspotctl source
```

as well as the WebUI header/About page.

## 🥧 Application + OS source relationship

The unified image builder under `os/` packages the root application from the **same Git commit that runs the builder**. Normal application development must therefore treat root runtime files and image-builder expectations as one source tree rather than maintaining duplicate app snapshots.

For the supported build flow:

```bash
bash os/builder/DOCTOR.sh
bash os/builder/BUILD.sh
```

See **[OS-IMAGE-BUILD.md](OS-IMAGE-BUILD.md)** for host requirements, factory/Wi-Fi-preseed image modes, output and first-boot validation.

Images built from `main` follow the `main` application update channel. Images built from `dev` follow `dev`. Experimental build branches fall back to `dev` rather than becoming permanent appliance channels.

## 🔐 Never commit runtime or builder secrets

Do not commit or attach:

- real `/etc/ywd-hotspot/config.json`
- `/etc/ywd-hotspot/bm-api.key`
- `/etc/ywd-hotspot/web-auth.json`
- `/var/lib/ywd-hotspot/private/`
- protected `/var/backups/ywd-hotspot/` archives
- arbitrary unsanitized diagnostics
- `os/local/provision.env`
- `os/local/ywd-os-dev_ed25519`

Runtime configuration belongs outside the repository under `/etc/ywd-hotspot` and `/var/lib/ywd-hotspot`. Builder-local credentials/keys belong only in ignored `os/local/` state.

## ✅ Basic validation before pushing

Shell entry points:

```bash
bash -n \
  INSTALL.sh INSTALL-core.sh \
  UPDATE.sh UPDATE-core.sh \
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh \
  MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh \
  UNINSTALL.sh \
  bin/ywd-hotspotctl bin/ywd-hotspotctl-core bin/ywd-ui.sh \
  lib/admin_dispatch.sh lib/setup_entry.sh lib/oled_owner.sh \
  lab/mmdvm-diag.sh \
  os/builder/BUILD.sh os/builder/DOCTOR.sh os/builder/CONFIGURE-WIFI.sh
```

Python:

```bash
python3 -m py_compile lib/*.py
```

If Node.js is available in the development environment:

```bash
for f in web/*.js; do node --check "$f"; done
```

Image-builder changes should also run:

```bash
bash os/builder/DOCTOR.sh
```

Changes touching systemd, sudoers, config generation, install/update, image first boot, RF behavior, or OLED ownership still require a real Pi test before being considered known-good.

## 🧪 Test-build workflow

A practical normal-development cycle is:

```text
dev change
   ↓
static validation
   ↓
update --check / --dry-run where relevant
   ↓
Pi Zero hardware test
   ↓
checkpoint branch when confirmed
   ↓
promote to main only when deliberately approved
```

For image work, insert `DOCTOR.sh` + a real image build/flash/first-boot test before the checkpoint/promotion step.

Do not use `/opt/ywd-hotspot/repo` as a casual hacking tree. Work in a normal clone and let the managed updater keep its dirty-tree safety guard.

## 🛡️ Update trust boundary

Keep these protections unless a stronger replacement is demonstrated:

- canonical-origin verification
- dirty-content refusal
- candidate staging outside the live app
- required-file/syntax validation
- protected pre-update backup
- RF-state preservation
- managed checkout advanced only after successful deploy

Convenience is not a good reason to make update failures destructive.

## 📌 Upstream RF pins

Do not casually combine an MMDVM-Host/DMRGateway pin move with unrelated UI/docs work. A radio-stack pin change changes the calibration baseline and should be isolated and regression-tested.

Current pins live in:

```text
pins.env
```

The OS image builder also consumes those exact pins when compiling the RF stack inside the image.

## 🏷️ Checkpoints, tags and releases

A checkpoint branch is useful while alpha builds are moving quickly because it preserves the exact hardware-tested commit before the next experiment starts.

The updater also supports explicit tags, for example:

```bash
sudo ywd-hotspotctl update --tag <tag>
```

A release/tag should only be described as known-good after actual hardware testing.

Do not move/rewrite a named known-good checkpoint after it has been used as a rollback anchor.

## 🧾 Repository metadata

Suggested description:

```text
Lightweight Raspberry Pi + MMDVM DMR hotspot stack with BrandMeister controls, responsive WebUI, calibration, diagnostics, safe GitHub updates and an integrated appliance-image builder.
```

Suggested topics:

```text
ham-radio dmr mmdvm raspberry-pi raspberry-pi-zero brandmeister hotspot amateur-radio
```

## 📄 License

The repository uses the **[Unlicense](../LICENSE)** / public-domain dedication.
