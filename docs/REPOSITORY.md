# 🌿 Repository Policy

[← Docs index](README.md) · [Development](GITHUB-SETUP.md) · [RC1 acceptance record](RELEASE-PLAN-0.2.0-rc1.md)

YWD-Hotspot keeps release history trustworthy: active branches move deliberately, while release tags/checkpoints remain evidence of what was actually tested.

## Current roles after 0.2.0-rc1 acceptance

| Ref | Role |
|---|---|
| `main` | promoted public line; may receive post-release documentation/maintenance commits |
| `dev` | accepted integrated development baseline |
| `v0.2.0-rc1` | immutable tag for the physically tested RC1 source |
| `release/0.2.0-rc1` | frozen RC1 hardening/source branch |
| `checkpoint-release-0.2.0-rc1-image-proven` | exact source checkpoint for the accepted public RC1 image |
| `checkpoint-builder-0.1.0-image-boot-proven` | earlier physically proven builder/appliance baseline |
| `dev-builder` | isolated builder development history/future work |
| `dev-plugins` | specialized plugin/framework development when needed |

Historical `checkpoint-*`, release tags and accepted release branches are not rewritten merely because moving branches later advance.

## Exact RC1 release identity

```text
v0.2.0-rc1
1575344d732994a7b54d5afc7f15a88040a274ec

checkpoint-release-0.2.0-rc1-image-proven
1575344d732994a7b54d5afc7f15a88040a274ec

image SHA256
f15232ec599cef550a23dd462ee0f30839cdde6cdf45b7e4b4b1fa929605190c
```

The image associated with that identity was built, flashed and physically tested before promotion/tagging.

## 0.2.0-rc1 promotion record

```text
checkpoint-builder-0.1.0-image-boot-proven
        ↓
release/0.2.0-rc1
        ↓ source/static/factory validation
clean public factory image
        ↓ physical acceptance of exact artifact
checkpoint-release-0.2.0-rc1-image-proven
        ↓
dev fast-forward
        ↓
main fast-forward
        ↓
v0.2.0-rc1
```

Both `dev` and `main` were clean descendants of the accepted release source, so promotion was performed as non-forced fast-forwards.

## Post-release documentation rule

Documentation can discover wording drift only after the exact appliance is exercised—especially around UI paths, optional hardware telemetry and recovery behavior.

After a release is frozen:

- fix current documentation on moving `main`/`dev`;
- do **not** retag or rewrite the physically tested commit;
- do **not** silently rebuild a different image under the same release identity;
- clearly distinguish release-source facts from later documentation corrections.

That lets public docs improve without corrupting the audit trail for the actual RC artifact.

## Public image policy

A GitHub release image is not a developer image. It must be built through `os/builder/BUILD-PUBLIC-RELEASE.sh` and contain factory/default onboarding state only—no operator Wi-Fi, radio identity, secrets, imported backup, RF autostart, builder SSH client key, or reusable SSH server host identity.

The exact artifact tested is the artifact published. Do not rebuild another image after physical acceptance and reuse the same release identity.

## Checkpoint policy

Create a known-good checkpoint only after the relevant behavior has been exercised. Checkpoints are rollback/audit anchors, not update channels.

Critical anchors:

```text
checkpoint-builder-0.1.0-image-boot-proven
a5a6d9483a7cad519ee5288661447875f346b4e7

checkpoint-release-0.2.0-rc1-image-proven
1575344d732994a7b54d5afc7f15a88040a274ec
```

## MMDVM runtime policy

The active release supports:

```text
ywd-extended   default/recommended; verified YWD extension patch
upstream       exact pinned stock upstream
```

The radio upstream pin remains fixed unless an isolated RF regression task intentionally changes it. YWD Extended patch identity is likewise pinned/hash-verified.

Runtime-variant support requires coherent canonical builders/dispatcher/capability files in candidate validation and `MANIFEST.txt`.

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

## Manifest / candidate validation

`MANIFEST.txt` inventories trusted runtime/release/documentation files. Capability-based candidate validation requires coherent core/plugin/voice/telemetry/runtime-variant/UI payloads regardless of branch name.

Do not weaken this to make an incomplete candidate easier to deploy.

## Secrets

Never commit runtime config, protected backups, API/password state, SSH private client/server keys, raw authorized-key files, plugin signing private keys, or unsanitized diagnostics. `os/local/`, work trees, runtime caches and deploy artifacts remain local/ignored unless explicitly attached to a GitHub Release.
