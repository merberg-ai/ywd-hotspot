# 🌿 Repository Policy

[← Docs index](README.md) · [Development](GITHUB-SETUP.md) · [Release plan](RELEASE-PLAN-0.2.0-rc1.md)

YWD-Hotspot keeps release history trustworthy: active branches move deliberately, while checkpoint refs remain evidence of what was actually tested.

## Current roles

| Ref | Role |
|---|---|
| `main` | promoted public release/testing line |
| `dev` | physically accepted integrated development baseline |
| `release/0.2.0-rc1` | current prerelease hardening/factory-image line |
| `checkpoint-builder-0.1.0-image-boot-proven` | immutable physically proven builder/appliance baseline |
| `dev-builder` | isolated builder development history/future work |
| `dev-plugins` | specialized plugin/framework development when needed |

Historical `checkpoint-*` refs and prior RC refs are not rewritten merely because a newer release exists.

## 0.2.0-rc1 promotion model

```text
checkpoint-builder-0.1.0-image-boot-proven
        ↓
release/0.2.0-rc1
        ↓ source/static validation
clean public factory image
        ↓ physical acceptance of exact artifact
checkpoint-release-0.2.0-rc1-image-proven
        ↓
dev (fast-forward)
        ↓ promotion sanity
main (fast-forward)
        ↓
v0.2.0-rc1 GitHub prerelease
```

The accepted release branch is currently a clean descendant of the prior `dev` and `main`, so the intended promotion is fast-forward rather than an unrelated merge.

Promotion is never automatic.

## Public image policy

A GitHub release image is not a developer image. It must be built through `os/builder/BUILD-PUBLIC-RELEASE.sh` and contain factory/default onboarding state only—no operator Wi-Fi, radio identity, secrets, imported backup, RF autostart, or builder SSH key.

The exact artifact tested is the artifact published. Do not rebuild another image after physical acceptance and reuse the same release identity.

## Checkpoint policy

Create a known-good checkpoint only after the relevant behavior has been exercised. Checkpoints are rollback/audit anchors, not update channels.

Current critical anchor:

```text
checkpoint-builder-0.1.0-image-boot-proven
a5a6d9483a7cad519ee5288661447875f346b4e7
```

## MMDVM runtime policy

The active release supports:

```text
ywd-extended   default/recommended; verified YWD extension patch
upstream       exact pinned stock upstream
```

The radio upstream pin remains fixed unless an isolated RF regression task intentionally changes it. YWD Extended patch identity is likewise pinned/hash-verified.

Runtime-variant support requires both canonical builders/dispatcher in candidate validation and `MANIFEST.txt`.

## Plugin requirement policy

Plugins may use trusted declarative requirement tokens for the selected MMDVM runtime. Requirement handling remains core-owned; plugins cannot run custom dependency installers or switch the MMDVM runtime themselves.

## Temporary branches

Normal lifecycle:

1. branch from exact verified parent;
2. make the scoped change;
3. run source/candidate validation;
4. compare exact changed-file scope;
5. hardware-test runtime changes;
6. freeze accepted checkpoint when useful;
7. promote intentionally;
8. clean temporary branches only after history is preserved.

## Manifest/candidate validation

`MANIFEST.txt` inventories trusted runtime/release files. Capability-based candidate validation requires coherent core/plugin/voice/telemetry/runtime-variant payloads regardless of branch name.

Do not weaken this to make an incomplete candidate easier to deploy.

## Secrets

Never commit runtime config, backups, API/password state, SSH private keys, plugin signing private keys, or unsanitized diagnostics. `os/local/`, work trees, runtime caches and deploy artifacts remain local/ignored unless explicitly attached to a GitHub Release.
