# 🌿 GitHub / Development Notes

[← Docs index](README.md) · [Project README](../README.md) · [Building](BUILDING.md) · [Repository Policy](REPOSITORY.md)

Canonical repository:

```text
https://github.com/merberg-ai/ywd-hotspot
```

## Current refs after 0.2.0-rc3 publication

| Ref | Purpose |
|---|---|
| `main` | public/update line carrying RC3 code plus post-release documentation |
| `dev` | active integrated development; aligned with `main` immediately after RC3 documentation refresh |
| `dev-plugins` | specialized plugin/framework development; may intentionally diverge |
| `v0.2.0-rc3` | immutable physically accepted RC3 tag |
| `release/0.2.0-rc3` | frozen exact RC3 source branch |
| `checkpoint-release-0.2.0-rc3-final-ui-wiring-proven-pre-image` | immutable final RC3 pre-image checkpoint |
| `v0.2.0-rc2` | immutable updater-proven RC2 tag |
| `release/0.2.0-rc2` | frozen RC2 source branch |
| `checkpoint-release-0.2.0-rc2-image-updater-proven` | exact source checkpoint for accepted RC2 image/updater test |
| `v0.2.0-rc1` | immutable physically tested RC1 tag |
| `release/0.2.0-rc1` | frozen RC1 source branch |
| `checkpoint-release-0.2.0-rc1-image-proven` | exact source checkpoint for accepted RC1 image |

Exact accepted RC3 source:

```text
3823140b9fd4d6e73fe9066af4b2280628f62f5e
```

Accepted public image:

```text
ywd-hotspot-0.2.0-rc3.img.xz
SHA256 5c3151b2a39f5a800b703d8925c53cddcf7bf49d8fcb59eda6bed30afc4413cc
```

## Clone

Current public line:

```bash
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Exact RC3 source reproduction:

```bash
git clone --branch v0.2.0-rc3 https://github.com/merberg-ai/ywd-hotspot.git ywd-hotspot-0.2.0-rc3
cd ywd-hotspot-0.2.0-rc3
git rev-parse HEAD
```

Expected tagged commit:

```text
3823140b9fd4d6e73fe9066af4b2280628f62f5e
```

Frozen release branches can be inspected explicitly, but new development should not be committed onto them merely because they still exist.

For ongoing development/housekeeping:

```bash
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
git switch dev
```

## Post-release documentation rule

Release tags, release branches and proven checkpoints stay immutable. `main` and `dev` may move beyond an accepted release tag for intentional documentation or future development commits, provided release documentation continues to identify the exact tested source/image separately.

A docs-only commit after publication is not a new factory-image acceptance event and does not redefine the source represented by `v0.2.0-rc3`.

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

## Pinned RC3 radio/runtime identity

```text
MMDVM-Host  dea6e9b2c35857fe6f904c5092bebadb86cbf079
DMRGateway  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
YWD patch   77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994
Patch API   2
```

`ywd-extended` is default/recommended; `upstream` is the explicit stock opt-out. RC1/RC2 Extended is recognized as a legacy-compatible generation and ordinary application updates do not silently rebuild it.

## Public image workflow

Only use:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

for an artifact intended for GitHub Releases. The wrapper enforces factory state, disables SSH/no builder authorized key or reusable host identity, selects the default Extended runtime, creates provenance files, and restores the developer's private builder profile afterward.

Never publish a personalized development image.

## Accepted RC3 workflow

```text
proven RC3 integrated dev baseline
  ↓
release/0.2.0-rc3
  ↓ exact source/static/factory validation
published RC2 -> exact RC3 updater acceptance
  ↓
final UI wiring physical acceptance
  ↓
checkpoint-release-0.2.0-rc3-final-ui-wiring-proven-pre-image
  ↓
exact RC3 public factory image build
  ↓ fresh-image physical acceptance
main promotion to exact accepted source
  ↓
tag v0.2.0-rc3
  ↓
publish exact tested image bytes
  ↓
post-release docs may advance main/dev without moving immutable release refs
```

Accepted image SHA256:

```text
5c3151b2a39f5a800b703d8925c53cddcf7bf49d8fcb59eda6bed30afc4413cc
```

Final evidence: **[history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md](history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md)**.

## Plugin-line handling

`dev-plugins` and its related plugin/RX/voice/vocoder checkpoints are intentionally separate from ordinary core/docs cleanup. Do not delete, rewrite, or silently merge them as part of repository housekeeping.

Integration from that line must be explicit and scoped.

## Update trust boundary

Keep canonical origin, dirty-tree refusal, staged candidate validation, protected backup, RF/service preservation, coherent privileged bridge, plugin quiesce/restore, and post-deploy managed-source advancement. Normal application updates also preserve the selected MMDVM runtime instead of silently rebuilding/switching it.

See **[SSH.md](SSH.md)** for maintenance access, **[UPGRADING.md](UPGRADING.md)** for update channels, and **[REPOSITORY.md](REPOSITORY.md)** for immutable release/checkpoint policy.
