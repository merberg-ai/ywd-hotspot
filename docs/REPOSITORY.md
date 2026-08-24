# 🌿 Repository Policy

[← Docs index](README.md) · [Development](GITHUB-SETUP.md) · [Historical records](history/README.md)

YWD-Hotspot keeps public release history trustworthy by separating immutable release evidence from moving development branches.

## Current roles after 0.2.0-rc2 acceptance

| Ref | Role |
|---|---|
| `main` | public/update line, intentionally frozen at the accepted RC2 commit while releases are frozen |
| `dev` | active integrated development and RC3 preparation line; includes the physically proven Phase 3J plugin/RX/vocoder integration |
| `dev-plugins` | specialized plugin/framework experiment line; currently aligned with `dev` and allowed to diverge only for intentional isolated plugin work |
| `v0.2.0-rc2` | immutable tag for the physically tested and updater-proven RC2 source |
| `release/0.2.0-rc2` | frozen RC2 source branch |
| `checkpoint-release-0.2.0-rc2-image-updater-proven` | exact source checkpoint for the accepted RC2 image and RC1 -> RC2 updater transition |
| `v0.2.0-rc1` | immutable tag for the physically tested RC1 source |
| `release/0.2.0-rc1` | frozen RC1 source branch |
| `checkpoint-release-0.2.0-rc1-image-proven` | exact source checkpoint for the accepted RC1 factory image |
| `checkpoint-builder-0.1.0-image-boot-proven` | earlier physically proven builder/appliance baseline |

Only plugin/RX/vocoder checkpoints with durable rollback or architectural audit value are retained. Intermediate `needs-testing`, failed, superseded and one-off observation branch labels are pruned once later evidence supersedes them; their commits remain in normal Git history.

## Accepted RC2 identity

```text
v0.2.0-rc2
5f0d2967ce0ed728169f7819d2bc227687d6a9b2

checkpoint-release-0.2.0-rc2-image-updater-proven
5f0d2967ce0ed728169f7819d2bc227687d6a9b2

published image
  ywd-hotspot-0.2.0-rc2.img.xz

image SHA256
  60f74d4c6d25d6a7d9ec35aea24b97bae7a50d35f103a21dc50ee1cbe80f1649
```

RC2 passed both a fresh-image physical test and an in-place `0.2.0-rc1 -> 0.2.0-rc2` dashboard update. The upgraded appliance then rebooted cleanly with zero failed systemd units.

## Release freeze policy

When releases are frozen:

- keep `main` at the exact accepted public release commit so normal `main`-channel appliances do not see unpublished housekeeping as an available update;
- perform ordinary development, integration, documentation and repository cleanup on `dev`;
- use `dev-plugins` only when intentionally isolating plugin/framework experiments;
- keep release tags, release branches and retained proven checkpoints unchanged;
- do not rebuild or republish a different artifact under an existing version/tag;
- move `main` only as part of an intentional future release/update event.

This supersedes the older practice of putting post-release wording fixes directly on `main`.

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
```

For updater-focused releases, also exercise the supported prior-release -> candidate transition before calling the updater path proven.

## Public image policy

A GitHub release image is not a developer image. It must be built through the fail-closed public release path and contain factory/default onboarding state only—no operator Wi-Fi, radio identity, secrets, imported backup, RF autostart, builder SSH client key, or reusable SSH server host identity.

The exact artifact tested is the artifact published. Renaming a tested compressed artifact for a cleaner GitHub-facing filename is acceptable only when byte identity is verified by SHA-256; recompressing/rebuilding it after acceptance is not.

## Checkpoint policy

Create a checkpoint only when it carries real rollback or audit value. Checkpoints are evidence, not update channels.

Release/builder anchors intentionally retained:

```text
checkpoint-builder-0.1.0-image-boot-proven
checkpoint-release-0.2.0-rc1-image-proven
checkpoint-release-0.2.0-rc2-image-updater-proven
```

Plugin/RX/vocoder anchors intentionally retained:

```text
checkpoint-dev-plugins-demand-gated-voice-proven
checkpoint-dev-plugins-vocoder-protocol-v1-proven
checkpoint-dev-plugins-phase3h-pre-real-vocoder
checkpoint-dev-plugins-phase3i-mbelib-protocol-sanity-proven
checkpoint-dev-plugins-phase3i-real-speech-partial-proven
checkpoint-dev-plugins-phase3j-pre-stream-core
checkpoint-dev-plugins-phase3j-stream-core-proven
```

Do not accumulate per-step checkpoint branches once the same history is fully contained by a later accepted release/checkpoint. Intermediate cleanup should preserve commits through normal Git history while removing redundant branch labels.

## Plugin branch separation

The proven Phase 3J plugin/RX/vocoder work is integrated into `dev`. `dev-plugins` starts from the same clean baseline and exists for future isolated plugin/framework experiments, not as a second long-lived copy of ordinary development.

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
8. delete temporary working branches after their commits are safely reachable from a retained ref.

Intentionally invalid/audit candidates should normally be deleted once the refusal behavior has been proven and recorded; they are test scaffolding, not release history.

## MMDVM runtime policy

The accepted release supports:

```text
ywd-extended   default/recommended; verified YWD extension patch
upstream       exact pinned stock upstream
```

The radio upstream pin remains fixed unless an isolated RF regression task intentionally changes it. YWD Extended patch identity is likewise pinned/hash-verified.

Runtime-variant support requires coherent canonical builders/dispatcher/capability files in candidate validation and `MANIFEST.txt`.

## Manifest / candidate validation

`MANIFEST.txt` inventories trusted runtime/release/documentation files. Capability-based candidate validation requires coherent core/plugin/voice/streamed-audio/vocoder/telemetry/runtime-variant/UI payloads regardless of branch name.

The streamed RX path is part of the trusted dashboard generation, so candidate validation explicitly requires its audio-stream bridge, AMBE recovery helper, vocoder protocol/runtime policy and dashboard wrapper integration. A candidate missing one of those pieces must fail before live services are touched.

Do not weaken validation to make an incomplete candidate easier to deploy.

## Documentation history

Current operating/development instructions stay directly under `docs/`. Completed release plans and implementation archaeology belong under `docs/history/` so they remain available without being mistaken for current instructions.

See [Historical Documentation](history/README.md).

## Secrets

Never commit runtime config, protected backups, API/password state, SSH private client/server keys, raw authorized-key files, plugin signing private keys, or unsanitized diagnostics. `os/local/`, work trees, runtime caches and deploy artifacts remain local/ignored unless explicitly attached to a GitHub Release.
