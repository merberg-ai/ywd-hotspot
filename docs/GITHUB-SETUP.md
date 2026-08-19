# 🌿 GitHub / Development Notes

[← Docs index](README.md) · [Project README](../README.md) · [Repository Policy](REPOSITORY.md) · [Upgrading](UPGRADING.md)

Canonical repository:

```text
https://github.com/merberg-ai/ywd-hotspot
```

## Branch model

| Branch | Purpose |
|---|---|
| `main` | promoted/conservative project line |
| `dev` | physically accepted integrated development baseline |
| `dev-plugins` | next-development / experimental integration line |

`dev-plugins` may advance with scoped work. A physically accepted state can be fast-forwarded into `dev`; `main` moves only through a separate release decision.

Some historical Alpha checkpoints still exist as legacy `checkpoint-*` branches. The long-term policy is to preserve known-good/divergent history using immutable checkpoint/archive references and remove redundant temporary branches only after their commit is safely preserved.

## Clone

Promoted line:

```bash
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Tested development line:

```bash
git clone --branch dev https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Next-development line:

```bash
git clone --branch dev-plugins https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

## Source vs deployed runtime

```text
/opt/ywd-hotspot/repo    managed Git source
/opt/ywd-hotspot/app     deployed runtime; no .git
```

Do not use the managed appliance checkout as a casual development tree. Develop in a normal clone and let the updater keep its dirty-tree safety guard.

Non-secret source provenance is recorded in `/etc/ywd-hotspot/build-info.json` and exposed by `ywd-hotspotctl source` plus the WebUI.

## Never commit runtime secrets

Do not commit or attach real appliance credentials/config/private state, including:

```text
/etc/ywd-hotspot/config.json
/etc/ywd-hotspot/bm-api.key
/etc/ywd-hotspot/web-auth.json
/var/lib/ywd-hotspot/private/
/var/backups/ywd-hotspot/
plugin signing private keys
SSH private keys
unsanitized diagnostics
```

## Basic validation before pushing

Shell:

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

Current source also includes:

```bash
python3 lib/candidate_validate.py .
```

That check is capability-based: plugin UI/package-update, passive voice, and telemetry runtime markers require their complete companion sets regardless of branch name.

If Node.js is available on the development machine:

```bash
for js in web/*.js; do node --check "$js"; done
```

OS-builder preflight:

```bash
bash os/builder/DOCTOR.sh
```

Changes touching systemd, sudoers, config generation, updater/install behavior, plugin lifecycle, OLED ownership, passive voice/telemetry, or RF behavior still require a real Pi test before being called known-good.

## Development workflow

```text
choose active parent
   ↓
make scoped change on next-development line / temporary branch
   ↓
static + capability validation
   ↓
compare exact changed-file scope
   ↓
Pi Zero hardware test when runtime behavior changed
   ↓
publish/promote intentionally
   ↓
preserve accepted checkpoint when useful
   ↓
clean temporary history only after preservation
```

## Update trust boundary

Keep these protections unless a stronger replacement is demonstrated:

- canonical-origin verification;
- dirty-content refusal;
- candidate staging outside the live app;
- capability-based required-file validation;
- shell/Python syntax validation;
- protected pre-update backup;
- RF-state preservation;
- plugin quiesce/restore safety;
- managed checkout advanced only after successful deployment.

Convenience is not a reason to make update failures destructive.

## Upstream RF pins

Do not combine an MMDVM-Host/DMRGateway pin move with unrelated UI/docs/plugin work. Current pins live in:

```text
pins.env
```

A radio-stack pin change alters the calibration/stability baseline and should be isolated and regression-tested.

## Repository layout

```text
assets/     branding source/derivatives
bin/        operator CLI
docs/       operator/developer documentation
lab/        diagnostics
lib/        trusted application core
os/         image builder
sudoers/    privilege policy
systemd/    units/sandbox templates
tools/      package/development utilities
web/        static WebUI
```

Root `INSTALL.sh`, `UPDATE.sh`, `GITHUB-UPDATE.sh`, migration, and uninstall wrappers are stable public entry points and intentionally remain at repository root.

## Suggested repository metadata

Description:

```text
Lightweight Raspberry Pi + MMDVM DMR hotspot stack with simplex/duplex BrandMeister controls, sandboxed plugins, browser RX monitoring, diagnostics and safe updates.
```

Topics:

```text
ham-radio dmr mmdvm raspberry-pi raspberry-pi-zero brandmeister hotspot amateur-radio
```

## License

The repository uses the **[Unlicense](../LICENSE)** / public-domain dedication.
