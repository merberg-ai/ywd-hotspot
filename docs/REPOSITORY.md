# 🌿 Repository Policy

[← Docs index](README.md) · [Development](GITHUB-SETUP.md) · [Project README](../README.md)

YWD-Hotspot keeps Git history useful without letting temporary development branches become permanent clutter.

## Active branch roles

| Branch | Role |
|---|---|
| `main` | conservative/promoted releases |
| `dev` | physically accepted integrated development baseline |
| `dev-builder` | isolated OS image/builder work |
| `dev-plugins` | plugin/framework development line |

Temporary release branches such as `dev-release-0.1.0` are cut from an exact accepted parent and are removed or archived after their accepted work is merged forward.

## Promotion model

For the 0.1.0 release:

```text
dev
  └── dev-release-0.1.0
          ↓ physical RC acceptance
        dev
          ↓ separate release decision
        main
```

`dev-builder` remains isolated during release hardening. After the final release state is proven, release changes can be intentionally synchronized forward into builder work before image development resumes.

Promotion is never automatic.

## Companion plugin repository

Standalone/open-source plugin development lives in:

```text
merberg-ai/ywd-hotspot-plugins
```

Core remains authoritative for package verification, lifecycle management, capability isolation, updater integration, sandboxing, and RF ownership. Private signing keys belong in neither repository.

## Checkpoint policy

A known-good checkpoint is created only after the relevant hardware/runtime behavior has actually been exercised.

Current release hardening uses named `checkpoint-release-*` references as rollback anchors. They are historical safety references, not active development lines.

Do not delete a checkpoint merely because its name looks old until its commit has been intentionally preserved by the repository's long-term archive/tag policy.

## Temporary branches

Feature, release, audit, recovery, and hotfix work should be scoped and temporary. Normal lifecycle:

1. branch from an exact verified parent;
2. make the smallest scoped change;
3. run static/source validation;
4. compare exact changed-file scope;
5. test on real hardware when runtime behavior changed;
6. freeze an accepted rollback checkpoint when useful;
7. merge/promote intentionally;
8. remove temporary scaffolding only after useful history is preserved.

## Repository layout

```text
assets/     source artwork and optimized branding derivatives
bin/        operator CLI
docs/       operator/development documentation
lab/        explicit diagnostic utilities
lib/        trusted application core
os/         reproducible image builder
sudoers/    privilege policy
systemd/    service units/sandbox templates
tools/      trusted development/package utilities
web/        static WebUI payload
```

Do not move runtime paths merely for aesthetics. Installer/updater/image-builder behavior depends on stable layout. Path moves are migrations and require candidate-validation/manifest coverage plus hardware testing.

Root install/update/migration wrappers remain at repository root as public operator entry points.

## RF / RX Monitor boundary

Repository cleanup is not a reason to move the tested radio baseline.

Current RF pins remain:

```text
MMDVM-Host  dea6e9b2c35857fe6f904c5092bebadb86cbf079
DMRGateway  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

The optional passive RX Monitor voice path uses:

```text
lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch
```

That patch is part of a narrow observation capability while MMDVM-Host stays the sole modem owner. Pin/patch changes require isolated RF regression testing.

## Manifest and candidate-validation policy

`MANIFEST.txt` is the current repository/runtime inventory used for release auditing. It must track current trusted runtime pieces rather than lag behind newly promoted subsystems.

The managed updater performs capability-based candidate validation. If a staged tree contains plugin UI/package-update, passive voice, or telemetry markers, the complete corresponding runtime set must be present regardless of branch name.

Repository cleanup must not weaken this invariant.

## Cleanup checklist

Periodic cleanup should verify:

- `main` and `dev` retain clear release/integration roles;
- specialized `dev-builder` and `dev-plugins` work stays isolated from unrelated release changes;
- temporary release/feature branches are removed or archived after promotion;
- checkpoint history is preserved before cleanup;
- `MANIFEST.txt` matches current trusted runtime files;
- README/install/build/architecture/plugin/update docs describe the current product rather than an old Alpha phase;
- generated/local plugin decoder artifacts remain ignored unless an explicit distribution decision is made;
- no secrets, runtime config, backups, SSH private keys, or signing private keys are tracked.

## Safety rule

Repository cleanup and documentation work stay isolated from MMDVM-Host/DMRGateway pins, calibration, frequencies, modem ownership, and normal DMR service behavior unless that radio change is explicitly the scoped task.
