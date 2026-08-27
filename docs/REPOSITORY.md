# 🌿 Repository Policy

[← Docs index](README.md) · [Development](GITHUB-SETUP.md) · [Historical records](history/README.md)

YWD-Hotspot keeps public release history trustworthy by separating immutable release evidence from moving development branches.

## Current roles after 0.2.0-rc3 publication

| Ref | Role |
|---|---|
| `main` | public/update line carrying accepted RC3 code plus intentional post-release documentation |
| `dev` | active integrated development; aligned with `main` immediately after the RC3 documentation refresh |
| `dev-plugins` | specialized plugin/framework experiment line; may intentionally diverge |
| `v0.2.0-rc3` | immutable tag for the physically accepted RC3 source |
| `release/0.2.0-rc3` | frozen exact RC3 source branch |
| `checkpoint-release-0.2.0-rc3-final-ui-wiring-proven-pre-image` | immutable final RC3 pre-image checkpoint |
| `v0.2.0-rc2` | immutable updater-proven RC2 tag |
| `release/0.2.0-rc2` | frozen RC2 source branch |
| `checkpoint-release-0.2.0-rc2-image-updater-proven` | exact source checkpoint for the accepted RC2 image/updater transition |
| `v0.2.0-rc1` | immutable physically tested RC1 tag |
| `release/0.2.0-rc1` | frozen RC1 source branch |
| `checkpoint-release-0.2.0-rc1-image-proven` | exact source checkpoint for the accepted RC1 factory image |
| `checkpoint-builder-0.1.0-image-boot-proven` | earlier physically proven builder/appliance baseline |

## Accepted RC3 identity

```text
v0.2.0-rc3
3823140b9fd4d6e73fe9066af4b2280628f62f5e

release/0.2.0-rc3
3823140b9fd4d6e73fe9066af4b2280628f62f5e

checkpoint-release-0.2.0-rc3-final-ui-wiring-proven-pre-image
3823140b9fd4d6e73fe9066af4b2280628f62f5e

published image
  ywd-hotspot-0.2.0-rc3.img.xz

image SHA256
  5c3151b2a39f5a800b703d8925c53cddcf7bf49d8fcb59eda6bed30afc4413cc
```

The exact RC3 factory image passed fresh-flash acceptance. The published RC2 -> RC3 application updater path also passed. The public image asset uploaded to GitHub reports the same SHA-256 as the exact physically accepted compressed artifact.

Post-release documentation commits may move `main` and `dev` beyond the immutable tag without redefining the accepted RC3 source/image identity.

## Release-history policy

For an already-published release:

- never move its tag;
- never move its frozen release branch or proven checkpoint;
- never rebuild/recompress a different image under the same release identity;
- keep exact tested source/image hashes in release notes and historical acceptance records;
- ordinary documentation after publication may advance `main`/`dev`, provided it does not claim the new branch head is the tested release source.

This keeps the public/update branch useful while preserving exact release evidence.

## Promotion policy

A normal future release flow is:

```text
dev
  ↓ scoped candidate/release branch when needed
source/static/factory validation
  ↓
exact artifact build
  ↓
physical acceptance of exact artifact
  ↓
proven checkpoint
  ↓
main promotion
  ↓
immutable release tag
  ↓
publish exact tested artifact
  ↓
optional post-release documentation on main/dev
```

For updater-focused releases, also exercise the supported prior-release -> candidate transition before calling the updater path proven.

## Public image policy

A GitHub release image is not a developer image. It must be built through the fail-closed public release path and contain factory/default onboarding state only—no operator Wi-Fi, radio identity, secrets, imported backup, RF autostart, builder SSH client key, or reusable SSH server host identity.

The exact artifact tested is the artifact published. Renaming a tested compressed artifact for a cleaner GitHub-facing filename is acceptable only when byte identity is verified by SHA-256; recompressing/rebuilding it after acceptance is not.

## Checkpoint policy

Create a checkpoint only when it carries real rollback or audit value. Checkpoints are evidence, not update channels.

Release/builder anchors intentionally retained include:

```text
checkpoint-builder-0.1.0-image-boot-proven
checkpoint-release-0.2.0-rc1-image-proven
checkpoint-release-0.2.0-rc2-image-updater-proven
checkpoint-release-0.2.0-rc3-final-ui-wiring-proven-pre-image
```

Plugin/RX/vocoder anchors with durable architectural value may also remain. Intermediate `needs-testing`, failed, superseded and one-off observation labels should not accumulate once later evidence supersedes them; their commits remain in normal Git history.

## Plugin branch separation

`dev-plugins` exists for intentional plugin/framework experimentation and may diverge from `dev`. Integration from future `dev-plugins` work into `dev` should be explicit, scoped, reviewed against runtime capability boundaries, and hardware-tested where RF/passive-voice behavior is involved.

Do not silently force `dev-plugins` to follow ordinary core/docs changes when it is intentionally carrying isolated work.

## Temporary branches

Normal lifecycle:

1. branch from the exact verified parent;
2. make the scoped change;
3. run source/candidate validation;
4. compare exact changed-file scope;
5. hardware-test runtime changes;
6. create a checkpoint only if the result has durable audit value;
7. promote intentionally;
8. delete temporary working branches after their commits are safely reachable from a retained ref.

## MMDVM runtime policy

The current RC3 release supports:

```text
ywd-extended   default/recommended; verified YWD extension patch
upstream       exact pinned stock upstream
```

Current accepted identity:

```text
MMDVM-Host upstream
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

YWD patch SHA256
  77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994

Extension API
  2

DMRGateway upstream
  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

RC1/RC2 Extended remains recognized as legacy-compatible rather than silently rebuilt by an ordinary application update.

## Manifest / candidate validation

`MANIFEST.txt` inventories trusted runtime/release/documentation files. Capability-based candidate validation requires coherent core/plugin/voice/streamed-audio/vocoder/telemetry/runtime-variant/UI payloads regardless of branch name.

Release-critical UI wiring includes the startup theme bundle, software-channel UI/backend, MODEM/MMDVM inventory UI/API and CSP-safe external styling. A candidate missing a required piece must fail before live services are touched.

Do not weaken validation to make an incomplete candidate easier to deploy.

## Documentation history

Current operating/development instructions stay directly under `docs/`. Completed release plans and implementation archaeology belong under `docs/history/` so they remain available without being mistaken for current instructions.

Final RC3 publication evidence is preserved in [`history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md`](history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md).

Historical documents intentionally retain terminology/state from their time and should not be rewritten merely to make them sound current.

## Secrets

Never commit runtime config, protected backups, API/password state, SSH private client/server keys, raw authorized-key files, plugin signing private keys, or unsanitized diagnostics. `os/local/`, work trees, runtime caches and deploy artifacts remain local/ignored unless explicitly attached to a GitHub Release.
