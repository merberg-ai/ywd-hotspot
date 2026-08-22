# 🌿 GitHub / Development Notes

[← Docs index](README.md) · [Project README](../README.md) · [Building](BUILDING.md) · [Repository Policy](REPOSITORY.md)

Canonical repository:

```text
https://github.com/merberg-ai/ywd-hotspot
```

## Current refs after 0.2.0-rc2 acceptance

| Ref | Purpose |
|---|---|
| `main` | frozen public/update line at the accepted RC2 source while releases are frozen |
| `dev` | active integrated development and repository housekeeping |
| `dev-plugins` | specialized plugin/framework development kept independent unless intentionally integrated |
| `v0.2.0-rc2` | immutable updater-proven RC2 tag |
| `release/0.2.0-rc2` | frozen RC2 source branch |
| `checkpoint-release-0.2.0-rc2-image-updater-proven` | exact source checkpoint for accepted RC2 image/updater test |
| `v0.2.0-rc1` | immutable physically tested RC1 tag |
| `release/0.2.0-rc1` | frozen RC1 source branch |
| `checkpoint-release-0.2.0-rc1-image-proven` | exact source checkpoint for accepted RC1 image |
| `checkpoint-builder-0.1.0-image-boot-proven` | earlier immutable physically proven builder/appliance baseline |

Plugin-development checkpoints related to `dev-plugins` are intentionally preserved. Checkpoint/tag/release refs are audit/rollback references, not persistent update channels.

Exact accepted RC2 source:

```text
5f0d2967ce0ed728169f7819d2bc227687d6a9b2
```

## Clone

Current public line:

```bash
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Exact RC2 source reproduction:

```bash
git clone --branch v0.2.0-rc2 https://github.com/merberg-ai/ywd-hotspot.git ywd-hotspot-0.2.0-rc2
cd ywd-hotspot-0.2.0-rc2
git rev-parse HEAD
```

Expected tagged commit:

```text
5f0d2967ce0ed728169f7819d2bc227687d6a9b2
```

Frozen release branches can be inspected explicitly, but new development should not be committed onto them merely because they still exist.

For ongoing development/housekeeping:

```bash
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
git switch dev
```

## Release freeze rule

While releases are frozen, keep `main` at the exact accepted public commit. Put normal docs/repository/development work on `dev` so appliances following the `main` update channel do not see unpublished work as an available update.

`main` should advance only as part of an intentional future release/update event.

## Source vs deployed runtime

```text
/opt/ywd-hotspot/repo    managed Git source
/opt/ywd-hotspot/app     deployed runtime copy; no .git
```

Do not use the managed appliance checkout as a casual development tree. Non-secret provenance is recorded in `/etc/ywd-hotspot/build-info.json`.

Source branch/ref and persistent update channel are intentionally separate concepts. A release/checkpoint test can report its exact source ref while the appliance's long-term update channel remains `main` or `dev`.

## Never commit runtime secrets

Do not commit/attach:

```text
/etc/ywd-hotspot/config.json
/etc/ywd-hotspot/bm-api.key
/etc/ywd-hotspot/web-auth.json
/var/lib/ywd-hotspot/private/
/var/backups/ywd-hotspot/
/home/ywd/.ssh/authorized_keys
/etc/ssh/ssh_host_*_key
SSH client private keys / server-identity archives
plugin signing private keys
unsanitized diagnostics
os/local private builder profiles
```

## Validation before pushing/building

```bash
python3 lib/candidate_validate.py .
python3 -m py_compile lib/*.py os/builder/*.py

bash -n \
  INSTALL.sh INSTALL-core.sh \
  UPDATE.sh UPDATE-core.sh \
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh \
  MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh \
  os/builder/BUILD.sh os/builder/RUN-BUILD.sh \
  os/builder/BUILD-PUBLIC-RELEASE.sh \
  os/pi-gen/stage2/20-ywd-runtime/01-run.sh \
  os/pi-gen/stage2/25-ywd-firstboot/01-run.sh
```

If Node.js is present:

```bash
for js in web/*.js; do node --check "$js"; done
```

Builder host preflight:

```bash
bash os/builder/DOCTOR.sh
```

Runtime/systemd/sudoers/updater/plugin/OLED/SSH/RF/image changes still require real hardware acceptance.

## Pinned radio/runtime identity

```text
MMDVM-Host  dea6e9b2c35857fe6f904c5092bebadb86cbf079
DMRGateway  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
YWD patch   f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
Patch API   2
```

`ywd-extended` is default/recommended; `upstream` is the explicit stock opt-out. Do not combine a pin/patch move with unrelated release cleanup.

## Public image workflow

Only use:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

for an artifact intended for GitHub Releases. The wrapper enforces factory state, disables SSH/no builder authorized key or reusable host identity, selects the default Extended runtime, creates provenance files, and restores the developer's private builder profile afterward.

Never publish a personalized development image.

## Accepted RC2 workflow

```text
accepted RC1 baseline
  ↓
post-RC1 documentation candidate
  ↓
release/0.2.0-rc2
  ↓ source/static/factory validation
exact RC2 factory image
  ↓ fresh-image physical test
main/dev at exact candidate source
  ↓
published RC1 appliance dashboard update
  ↓
0.2.0-rc2 / clean main source
  ↓ reboot / zero failed units
checkpoint-release-0.2.0-rc2-image-updater-proven
  ↓
tag v0.2.0-rc2
  ↓
publish exact tested image bytes
```

Accepted image SHA256:

```text
60f74d4c6d25d6a7d9ec35aea24b97bae7a50d35f103a21dc50ee1cbe80f1649
```

## Plugin-line handling

`dev-plugins` and its related plugin/RX/voice/vocoder checkpoints are intentionally separate from ordinary core/docs cleanup. Do not delete, rewrite, or silently merge them as part of repository housekeeping.

Integration from that line must be explicit and scoped.

## Update trust boundary

Keep canonical origin, dirty-tree refusal, staged candidate validation, protected backup, RF/service preservation, coherent privileged bridge, plugin quiesce/restore, and post-deploy managed-source advancement. Normal application updates also preserve the selected MMDVM runtime instead of silently rebuilding/switching it.

See **[SSH.md](SSH.md)** for the dashboard-managed maintenance-access model, **[UPGRADING.md](UPGRADING.md)** for update channels, and **[REPOSITORY.md](REPOSITORY.md)** for immutable release/checkpoint policy.
