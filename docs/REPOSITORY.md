# 🌿 Repository Policy

[← Docs index](README.md) · [Development](GITHUB-SETUP.md) · [Historical records](history/README.md)

YWD-Hotspot keeps public release history trustworthy by separating immutable release evidence from moving development branches.

## Current roles after 0.2.0-rc3 publication

| Ref | Role |
|---|---|
| `main` | public/update line carrying accepted RC3 code plus intentional post-release documentation |
| `dev` | active integrated development; normally aligned with `main` immediately after a release cleanup |
| `dev-plugins` | isolated plugin/framework experiment line; normally aligned after integration and allowed to diverge only for deliberate plugin work |
| `v0.2.0-rc3` | immutable tag for the physically accepted RC3 source |
| `release/0.2.0-rc3` | frozen exact RC3 source branch |
| `v0.2.0-rc2` | immutable updater-proven RC2 tag |
| `release/0.2.0-rc2` | frozen RC2 source branch |
| `v0.2.0-rc1` | immutable physically tested RC1 tag |
| `release/0.2.0-rc1` | frozen RC1 source branch |

## Accepted RC3 identity

```text
v0.2.0-rc3
3823140b9fd4d6e73fe9066af4b2280628f62f5e

release/0.2.0-rc3
3823140b9fd4d6e73fe9066af4b2280628f62f5e

published image
  ywd-hotspot-0.2.0-rc3.img.xz

image SHA256
  5c3151b2a39f5a800b703d8925c53cddcf7bf49d8fcb59eda6bed30afc4413cc
```

The exact RC3 factory image passed fresh-flash acceptance. The published RC2 -> RC3 application updater path also passed. The public image asset uploaded to GitHub reports the same SHA-256 as the exact physically accepted compressed artifact.

Post-release documentation commits may move `main`, `dev`, and `dev-plugins` beyond the immutable release tag without redefining the accepted RC3 source/image identity.

## Release-history policy

For an already-published release:

- never move its tag;
- never move its frozen release branch;
- never rebuild/recompress a different image under the same release identity;
- keep exact tested source/image hashes in release notes and historical acceptance records;
- ordinary documentation after publication may advance the moving channels, provided it does not claim the new branch head is the tested release source.

A release tag plus its frozen `release/<version>` branch are sufficient durable refs for a published release. Temporary/pre-image checkpoint branches may be deleted once the final release is published and their commits are reachable from retained history.

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
main promotion
  ↓
immutable release tag
  ↓
publish exact tested artifact
  ↓
optional post-release documentation / channel realignment
```

For updater-focused releases, also exercise the supported prior-release -> candidate transition before calling the updater path proven.

## Public image policy

A GitHub release image is not a developer image. It must be built through the fail-closed public release path and contain factory/default onboarding state only—no operator Wi-Fi, radio identity, secrets, imported backup, RF autostart, builder SSH client key, or reusable SSH server host identity.

The exact artifact tested is the artifact published. Renaming a tested compressed artifact for a cleaner GitHub-facing filename is acceptable only when byte identity is verified by SHA-256; recompressing/rebuilding it after acceptance is not.

## Checkpoint / temporary-ref policy

Create a checkpoint only when it carries real rollback or audit value during active development. Checkpoints are evidence, not update channels.

After a release is published, prune intermediate checkpoint branches when all of the following are true:

1. the checkpoint commit is reachable from `main`/the published release history;
2. a release tag or frozen release branch supersedes its acceptance role;
3. any durable testing evidence is already recorded in `docs/history/` or release notes.

Duplicate checkpoint names pointing to the same commit should not be retained. Intentionally invalid/test branches such as one-off branch-management fixtures should be deleted after the refusal/behavior test is recorded.

Older milestone tags may also be pruned when they are not public releases and their commits remain reachable from retained Git history. Public version tags (`v...`) are immutable and are never part of routine cleanup.

## Plugin branch separation

`dev-plugins` exists for intentional plugin/framework experimentation. It should normally be realigned to `dev` after integrated work lands, then diverge again only when a new isolated plugin task begins.

Integration from future `dev-plugins` work into `dev` should be explicit, scoped, reviewed against runtime capability boundaries, and hardware-tested where RF/passive-voice behavior is involved.

## Temporary branches

Normal lifecycle:

1. branch from the exact verified parent;
2. make the scoped change;
3. run source/candidate validation;
4. compare exact changed-file scope;
5. hardware-test runtime changes;
6. create a checkpoint only if the result has durable audit value;
7. promote intentionally;
8. delete temporary working/checkpoint branches after their commits are safely reachable from retained refs.

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
