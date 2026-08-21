# 🌿 GitHub / Development Notes

[← Docs index](README.md) · [Project README](../README.md) · [Building](BUILDING.md) · [Repository Policy](REPOSITORY.md)

Canonical repository:

```text
https://github.com/merberg-ai/ywd-hotspot
```

## Active refs during 0.2.0-rc1

| Ref | Purpose |
|---|---|
| `main` | promoted public release/testing line |
| `dev` | physically accepted integration line |
| `release/0.2.0-rc1` | current release/factory-image hardening |
| `checkpoint-builder-0.1.0-image-boot-proven` | immutable physically proven starting point |
| `dev-builder` | isolated builder history/future work |

Checkpoint and historical RC refs are audit/rollback references, not update channels.

## Clone

Promoted line:

```bash
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Current RC preparation line:

```bash
git clone --branch release/0.2.0-rc1 https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

## Source vs deployed runtime

```text
/opt/ywd-hotspot/repo    managed Git source
/opt/ywd-hotspot/app     deployed runtime copy; no .git
```

Do not use the managed appliance checkout as a casual development tree. Non-secret provenance is recorded in `/etc/ywd-hotspot/build-info.json`.

Source branch/ref and persistent update channel are intentionally separate concepts. A release/checkpoint test may report its exact source ref while the appliance's long-term channel remains `main` or `dev`.

## Never commit runtime secrets

Do not commit/attach:

```text
/etc/ywd-hotspot/config.json
/etc/ywd-hotspot/bm-api.key
/etc/ywd-hotspot/web-auth.json
/var/lib/ywd-hotspot/private/
/var/backups/ywd-hotspot/
plugin signing private keys
SSH private keys
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
  os/pi-gen/stage2/20-ywd-runtime/01-run.sh
```

If Node.js is present:

```bash
for js in web/*.js; do node --check "$js"; done
```

Builder host preflight:

```bash
bash os/builder/DOCTOR.sh
```

Runtime/systemd/sudoers/updater/plugin/OLED/RF/image changes still require real hardware acceptance.

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

for an artifact intended for GitHub Releases. The wrapper enforces factory state, disables SSH/no builder authorized key, selects the default Extended runtime, creates provenance files and restores the developer's private builder profile afterward.

Never publish a personalized development image.

## 0.2.0-rc1 release workflow

```text
proven checkpoint
  ↓
release/0.2.0-rc1
  ↓ static/candidate validation
factory image build
  ↓ SHA/xz verification
physical test of exact image
  ↓
freeze image-proven checkpoint
  ↓
fast-forward dev
  ↓ sanity
fast-forward main
  ↓
publish v0.2.0-rc1 prerelease + exact tested assets
```

Release candidate work does not absorb unrelated new features merely because a temporary release branch exists.

## Update trust boundary

Keep canonical origin, dirty-tree refusal, staged candidate validation, protected backup, RF/service preservation, coherent privileged bridge, plugin quiesce/restore, and post-deploy managed-source advancement. Normal app updates also preserve the selected MMDVM runtime instead of silently rebuilding/switching it.
