# 🌿 GitHub / Development Notes

[← Docs index](README.md) · [Project README](../README.md) · [Building](BUILDING.md) · [Repository Policy](REPOSITORY.md)

Canonical repository:

```text
https://github.com/merberg-ai/ywd-hotspot
```

## Current refs after 0.2.0-rc1 acceptance

| Ref | Purpose |
|---|---|
| `main` | promoted public line; current documentation/maintenance baseline |
| `dev` | accepted integration line |
| `v0.2.0-rc1` | immutable physically tested RC1 tag |
| `release/0.2.0-rc1` | frozen RC1 source/hardening branch |
| `checkpoint-release-0.2.0-rc1-image-proven` | exact source checkpoint for the tested public image |
| `checkpoint-builder-0.1.0-image-boot-proven` | earlier immutable physically proven starting point |
| `dev-builder` | isolated builder history/future work |

Checkpoint/tag/release refs are audit/rollback references, not persistent update channels.

Exact RC1 tested source:

```text
1575344d732994a7b54d5afc7f15a88040a274ec
```

## Clone

Current promoted line:

```bash
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Exact RC1 source reproduction:

```bash
git clone --branch v0.2.0-rc1 https://github.com/merberg-ai/ywd-hotspot.git ywd-hotspot-0.2.0-rc1
cd ywd-hotspot-0.2.0-rc1
git rev-parse HEAD
```

Expected tagged commit:

```text
1575344d732994a7b54d5afc7f15a88040a274ec
```

The frozen release branch can also be inspected explicitly, but new development should not be committed onto it merely because it still exists.

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

for an artifact intended for GitHub Releases. The wrapper enforces factory state, disables SSH/no builder authorized key or reusable host identity, selects the default Extended runtime, creates provenance files and restores the developer's private builder profile afterward.

Never publish a personalized development image.

## 0.2.0-rc1 completed workflow

```text
proven checkpoint
  ↓
release/0.2.0-rc1
  ↓ static/candidate/factory validation
factory image build
  ↓ SHA/xz verification
physical test of exact image
  ↓
checkpoint-release-0.2.0-rc1-image-proven
  ↓
fast-forward dev
  ↓
fast-forward main
  ↓
tag v0.2.0-rc1
  ↓
publish exact tested prerelease assets
```

Tested image SHA256:

```text
f15232ec599cef550a23dd462ee0f30839cdde6cdf45b7e4b4b1fa929605190c
```

After the tag/checkpoint is frozen, documentation-only corrections may land on moving branches. They must not be represented as changes to the already-tested RC artifact.

## Update trust boundary

Keep canonical origin, dirty-tree refusal, staged candidate validation, protected backup, RF/service preservation, coherent privileged bridge, plugin quiesce/restore, and post-deploy managed-source advancement. Normal app updates also preserve the selected MMDVM runtime instead of silently rebuilding/switching it.

See **[SSH.md](SSH.md)** for the current dashboard-managed maintenance-access model and **[REPOSITORY.md](REPOSITORY.md)** for immutable release/checkpoint policy.
