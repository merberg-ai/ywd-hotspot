# 🌿 Repository Policy

[← Docs index](README.md) · [Development notes](GITHUB-SETUP.md) · [Project README](../README.md)

This document defines how YWD-Hotspot keeps Git history useful without letting temporary development branches become permanent clutter.

## Long-lived branches

Only three branches are intended to be permanent in the core repository:

| Branch | Role |
|---|---|
| `main` | conservative/promoted line |
| `dev` | unified application + OS-builder baseline |
| `dev-plugins` | experimental plugin/telemetry/integration line |

A new long-lived core branch should be exceptional and documented here before it is created.

## Companion plugin repository

Standalone/open-source plugin development lives outside the appliance/core repository in:

```text
merberg-ai/ywd-modem-plugins
```

That repository may contain plugin source, examples, plugin-specific documentation, and development helpers. It must not duplicate or fork the trusted YWD-Hotspot package verifier, lifecycle manager, sandbox, updater, or RF ownership logic. Those contracts remain canonical in this repository.

Private signing keys must never be committed to either repository.

## Checkpoint tags

Physically tested known-good builds are preserved as immutable annotated tags:

```text
checkpoint/<historical-checkpoint-name>
```

Examples:

```text
checkpoint/dev-alpha12.2-os-integrated-known-good
checkpoint/dev-plugins-alpha18.2.4-known-good
```

Rules:

- checkpoint tags never move
- create one only after the relevant build has actually been tested
- the tag points directly to the tested commit
- deleting the old checkpoint branch does not delete the commit once the tag exists
- rollback/recovery may target an explicit checkpoint tag when needed

## Archive tags

Superseded long-lived development lines or historically useful snapshots use:

```text
archive/<name>
```

An archive tag preserves the final commit without keeping an inactive branch visible forever.

## Temporary branches

Feature, audit, recovery and hotfix work should use temporary branches. Common patterns are:

```text
work/<topic>
audit/<topic>
hotfix/<topic>
```

Lifecycle:

1. branch from an exact verified parent
2. make the scoped change
3. run syntax/static/audit checks
4. compare changed-file scope
5. test on hardware when runtime behavior changed
6. publish/squash/fast-forward the intended active line
7. remove temporary CI scaffolding
8. delete the temporary branch

Temporary branches are not release history. The commit graph and checkpoint/archive tags preserve useful history.

## Promotion model

```text
dev-plugins experiments
        ↓ intentionally selected/stabilized work
       dev
        ↓ deliberate promotion
       main
```

Promotion is never automatic.

## Repository layout policy

The current top-level structure is intentional:

```text
assets/     source artwork and optimized branding derivatives
bin/        operator CLI
docs/       documentation
lab/        explicit diagnostic/experimental utilities
lib/        trusted application core
os/         reproducible image builder / pi-gen stages
sudoers/    privilege policy
systemd/    service units
tools/      trusted development/package utilities
web/        static WebUI payload
```

Do not reorganize runtime paths only for aesthetics. Installer/updater/builder code relies on stable paths. Directory moves are migrations and require manifest, updater, candidate-validation and OS-builder coverage.

Root install/update/migration wrappers remain at repository root because they are public operator entry points.

## Branding assets

Master/source artwork belongs under `assets/branding/`. Lightweight runtime derivatives may also exist under `web/` when the dashboard updater needs them in the atomically deployed WebUI payload.

When a runtime derivative is duplicated, both copies should be generated from the same validated source and documented in `assets/branding/README.md`.

## Compatibility fixtures

Not every apparently obsolete file can be deleted immediately. A source manifest or package may remain temporarily when the updater/migration path still needs it to safely retire old installed state.

Retired proof plugins must remain hidden from the operator catalog and inert, but compatibility fixtures should not be removed until old package-state migration no longer requires resolving them.

## Cleanup checklist

Periodic cleanup should verify:

- only intended long-lived branches remain
- known-good points have immutable checkpoint tags
- obsolete long-lived lines have archive tags before branch deletion
- no temporary CI workflow remains
- `MANIFEST.txt` contains current required files
- README/docs do not advertise an obsolete active version/branch
- branding docs match shipped assets
- compatibility fixtures are documented rather than mistaken for active features
- no secrets, runtime config, backups, SSH private keys, or signing private keys are tracked
- temporary feature branches are deleted after publication

## Safety rule

Repository cleanup is not a reason to change RF behavior. Branch/tag/docs/asset organization stays isolated from MMDVM-Host/DMRGateway pins, calibration, modem settings and normal DMR service behavior.
