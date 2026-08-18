# 🌿 GitHub / Development Notes

[← Docs index](README.md) · [Project README](../README.md) · [Repository Policy](REPOSITORY.md) · [Contributing](../CONTRIBUTING.md) · [Upgrading](UPGRADING.md)

---

Canonical repository:

```text
https://github.com/merberg-ai/ywd-hotspot
```

## Branch model

YWD-Hotspot keeps long-lived branches intentionally small:

| Branch | Purpose |
|---|---|
| `main` | promoted/conservative project line |
| `dev` | unified application + OS-builder baseline |
| `dev-plugins` | experimental plugin, telemetry and integration work |

Historical known-good builds belong in immutable `checkpoint/*` tags. Superseded development lines worth retaining belong in `archive/*` tags. Temporary feature/audit branches should disappear after their tested result is published.

See **[Repository Policy](REPOSITORY.md)** for the lifecycle rules.

## Clone

Promoted line:

```bash
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Unified development line:

```bash
git clone --branch dev https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Experimental plugin/telemetry line:

```bash
git clone --branch dev-plugins https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Normal Git clones preserve executable modes. If source came through a ZIP/Windows copy and modes were lost, running entry scripts through Bash is sufficient for recovery, for example:

```bash
sudo bash ./INSTALL.sh
```

`.gitattributes` keeps important text/source on LF endings.

## Source vs deployed runtime

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

and shown by `ywd-hotspotctl source` plus the WebUI header/About page.

## Never commit runtime secrets

Do not commit or attach:

- real `/etc/ywd-hotspot/config.json`
- `/etc/ywd-hotspot/bm-api.key`
- `/etc/ywd-hotspot/web-auth.json`
- `/var/lib/ywd-hotspot/private/`
- protected `/var/backups/ywd-hotspot/` archives
- arbitrary unsanitized diagnostics
- plugin signing private keys

Runtime configuration belongs outside the repository under `/etc/ywd-hotspot` and `/var/lib/ywd-hotspot`.

## Basic validation before pushing

Shell entry points:

```bash
bash -n \
  INSTALL.sh INSTALL-core.sh \
  UPDATE.sh UPDATE-core.sh \
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh \
  MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh \
  UNINSTALL.sh \
  bin/ywd-hotspotctl bin/ywd-hotspotctl-core bin/ywd-ui.sh \
  lab/mmdvm-diag.sh
```

Python:

```bash
python3 -m py_compile lib/*.py
```

If Node.js is available in the development environment:

```bash
for js in web/*.js; do node --check "$js"; done
```

OS-builder preflight:

```bash
bash os/builder/DOCTOR.sh
```

Changes touching systemd, sudoers, config generation, install/update, plugin lifecycle, OLED ownership, or RF behavior still require a real Pi test before being called known-good.

## Development workflow

A normal change should look like:

```text
choose the correct active branch
   ↓
create temporary feature/audit branch
   ↓
make the smallest scoped change
   ↓
static/syntax validation
   ↓
compare exact changed-file scope
   ↓
Pi Zero hardware test when runtime behavior changed
   ↓
publish to active line
   ↓
create checkpoint tag only after operator confirmation
   ↓
delete temporary branch
```

Do not use `/opt/ywd-hotspot/repo` as a casual hacking tree. Work in a normal clone and let the managed updater keep its dirty-tree safety guard.

## Checkpoints

A checkpoint is an immutable tag, not another development branch. Example naming:

```text
checkpoint/dev-alpha12.2-os-integrated-known-good
checkpoint/dev-plugins-alpha18.2.4-known-good
```

The important property is the commit, not the branch name that originally led to it. Never move an existing checkpoint tag to a different commit.

Tags are useful for explicit recovery/testing too:

```bash
sudo ywd-hotspotctl update --tag <tag>
```

Only label a checkpoint known-good after the relevant hardware/runtime behavior has actually been exercised.

## Update trust boundary

Keep these protections unless a stronger replacement is demonstrated:

- canonical-origin verification
- dirty-content refusal
- candidate staging outside the live app
- required-file/syntax validation
- protected pre-update backup
- RF-state preservation
- plugin quiesce/restore safety on `dev-plugins`
- managed checkout advanced only after successful deploy

Convenience is not a good reason to make update failures destructive.

## Upstream RF pins

Do not combine an MMDVM-Host/DMRGateway pin move with unrelated UI/docs/plugin work. A radio-stack pin change changes the calibration baseline and should be isolated and regression-tested.

Current pins live in:

```text
pins.env
```

## Repository layout

The top-level layout is intentionally operational rather than package-manager clever:

```text
assets/     source branding and lightweight derivatives
bin/        operator CLI entry points
docs/       project/operator/development documentation
lab/        explicit diagnostics/experimental tools
lib/        trusted Python/shell application core
os/         image builder and pi-gen stages
sudoers/    narrow privilege policy
systemd/    service units and sandbox templates
tools/      development/package-building tools
web/        static WebUI payload
```

Root `INSTALL.sh`, `UPDATE.sh`, `GITHUB-UPDATE.sh`, migration and uninstall wrappers are stable public entry points and intentionally remain at repository root.

## Repository metadata

Suggested description:

```text
Lightweight Raspberry Pi + MMDVM DMR hotspot stack with BrandMeister controls, responsive WebUI, calibration, diagnostics and safe GitHub updates.
```

Suggested topics:

```text
ham-radio dmr mmdvm raspberry-pi raspberry-pi-zero brandmeister hotspot amateur-radio
```

## License

The repository uses the **[Unlicense](../LICENSE)** / public-domain dedication.
