# 🌿 GitHub / Development Notes

[← Docs index](README.md) · [Project README](../README.md) · [Building](BUILDING.md) · [Repository Policy](REPOSITORY.md) · [Upgrading](UPGRADING.md)

Canonical repository:

```text
https://github.com/merberg-ai/ywd-hotspot
```

## Current branch model

| Branch | Purpose |
|---|---|
| `main` | promoted/conservative release line |
| `dev` | physically accepted integrated development baseline |
| `dev-builder` | isolated OS image/builder work |
| `dev-plugins` | plugin/framework development line |
| `dev-release-0.1.0` | temporary 0.1.0 release hardening / RC branch |

The release branch is temporary. During RC testing it may be installed directly while the appliance's persistent update channel remains `dev`. After acceptance, release work flows back through `dev` and then to `main`. Builder/image work remains isolated until intentionally synchronized.

Historical `checkpoint-*` branches are rollback/history references, not active development lines.

## Clone

Promoted line:

```bash
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Current 0.1.0 RC line:

```bash
git clone --branch dev-release-0.1.0 https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Accepted development line:

```bash
git clone --branch dev https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Builder/image line:

```bash
git clone --branch dev-builder https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

## Source vs deployed runtime

```text
/opt/ywd-hotspot/repo    managed Git source
/opt/ywd-hotspot/app     deployed runtime; no .git
```

Do not use the managed appliance checkout as a casual development tree. Develop in a normal clone and let the updater keep its dirty-tree safety guard.

Non-secret source provenance is recorded in `/etc/ywd-hotspot/build-info.json` and exposed by `ywd-hotspotctl source` plus the WebUI.

Important provenance distinction:

```text
branch/ref       where this exact candidate came from
update channel   persistent operator-selected update line
```

A release candidate may therefore correctly report:

```text
Branch  : dev-release-0.1.0
Channel : dev
```

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
python3 lib/candidate_validate.py .
```

If Node.js is available:

```bash
for js in web/*.js; do
  node --check "$js"
done
```

OS-builder preflight:

```bash
bash os/builder/DOCTOR.sh
```

See **[BUILDING.md](BUILDING.md)** for the complete easy-to-follow build paths.

Changes touching systemd, sudoers, config generation, updater/install behavior, plugin lifecycle, OLED ownership, passive voice/telemetry, or RF behavior still require a real Pi test before being called known-good.

## Pinned RF and RX Monitor patch

Current pins live in `pins.env`:

```text
MMDVM-Host  dea6e9b2c35857fe6f904c5092bebadb86cbf079
DMRGateway  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

The optional RX Monitor/passive voice path uses:

```text
lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch
```

Do not combine a radio-stack pin or patch move with unrelated UI/docs/plugin work. The voice patch mirrors accepted DMR voice frames to the trusted loopback observation path; it does not transfer modem ownership to the plugin.

Normal application updates do **not** recompile MMDVM-Host or DMRGateway. The optional patched voice binary is prepared through `ywd-mmdvm-voice-build.service` and its guarded helper.

## Development workflow

```text
choose exact verified parent
   ↓
make one scoped change on the appropriate development/release branch
   ↓
static + capability validation
   ↓
compare exact changed-file scope
   ↓
Pi Zero hardware test when runtime behavior changed
   ↓
freeze a rollback checkpoint after acceptance
   ↓
promote intentionally
   ↓
clean temporary history only after preservation
```

## Release workflow

The 0.1.0 release-hardening pattern is:

```text
main
  ↑
dev
  └── dev-release-0.1.0
          release hardening / RC only
          ↓
       physical RC acceptance
          ↓
       merge → dev
          ↓
       promote → main


dev-builder
  stays isolated during release hardening
```

Release candidate work should not absorb new feature development merely because a temporary release branch exists.

## Update trust boundary

Keep these protections unless a stronger replacement is demonstrated:

- canonical-origin verification;
- dirty-content refusal;
- candidate staging outside the live app;
- capability-based required-file validation;
- shell/Python syntax validation;
- protected pre-update backup;
- RF/service-state preservation;
- coherent privileged admin-dispatch generation before dashboard restart;
- plugin quiesce/restore safety;
- managed checkout advanced only after successful deployment.

Convenience is not a reason to make update failures destructive.

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

## License

The repository uses the **[Unlicense](../LICENSE)** / public-domain dedication.
