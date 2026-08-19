# 🌿 Repository Policy

[← Docs index](README.md) · [Development](GITHUB-SETUP.md) · [Project README](../README.md)

YWD-Hotspot keeps Git history useful without letting temporary development branches become permanent clutter.

## Long-lived branches

Only three core branches are intended to remain active:

| Branch | Role |
|---|---|
| `main` | conservative/promoted line |
| `dev` | physically accepted integrated development baseline |
| `dev-plugins` | next-development / experimental integration line |

`dev-plugins` may move ahead. Once a state is physically exercised and intentionally accepted, it can be fast-forwarded into `dev`. Promotion from `dev` to `main` remains a separate deliberate decision.

## Companion plugin repository

Standalone/open-source plugin development lives in:

```text
merberg-ai/ywd-hotspot-plugins
```

Core remains authoritative for package verification, lifecycle management, capability isolation, updater integration, sandboxing, and RF ownership. Private signing keys belong in neither repository.

## Checkpoint policy

The desired long-term form of a known-good historical milestone is an immutable tag:

```text
checkpoint/<name>
```

Checkpoint tags never move and are created only after the relevant hardware/runtime behavior has actually been exercised.

### Legacy checkpoint branches

Rapid Alpha development created a number of historical `checkpoint-*` **branches** before the tag policy was standardized. They are not active development lines.

Cleanup rule:

1. verify the exact commit represented by the branch;
2. verify or create an immutable checkpoint/archive tag pointing to that commit;
3. only then remove the redundant branch.

Never delete a legacy checkpoint branch merely because its name looks old if its commit has not first been preserved by an immutable reference.

## Archive policy

Superseded or divergent historical work that is worth retaining should use:

```text
archive/<name>
```

A particularly important case is a temporary work branch that contains commits not merged into the active line. Preserve its tip as an archive reference before deleting the branch.

## Temporary branches

Feature, audit, recovery, and hotfix work should be temporary:

```text
work/<topic>
audit/<topic>
hotfix/<topic>
```

Normal lifecycle:

1. branch from an exact verified parent;
2. make the smallest scoped change;
3. run static/source validation;
4. compare exact changed-file scope;
5. test on real hardware when runtime behavior changed;
6. publish to the intended active line;
7. create a checkpoint only after acceptance when warranted;
8. remove temporary scaffolding/branch references once useful history is preserved.

## Promotion model

```text
dev-plugins
    ↓ physical validation + explicit acceptance
dev
    ↓ separate soak/release decision
main
```

Promotion is not automatic.

## Repository layout

Operational top-level layout:

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

## Manifest and candidate-validation policy

`MANIFEST.txt` is the current repository/runtime inventory used for release auditing. It must track current trusted runtime pieces rather than lagging behind newly promoted subsystems.

The managed updater additionally performs capability-based candidate validation. If a staged tree contains plugin UI/package-update, passive voice, or telemetry markers, the complete corresponding runtime set must be present regardless of branch name.

Repository cleanup must not weaken this invariant.

## Branding assets

Canonical source artwork belongs under `assets/branding/`. Lightweight runtime derivatives may also exist under `web/` when atomic WebUI deployment needs them.

Duplicated derivatives should come from the same validated source and be documented rather than treated as accidental duplicates.

## Compatibility fixtures

Apparently obsolete source may remain temporarily when an update/migration path still needs it to safely retire older installed state. Such fixtures should be documented and hidden/inert rather than mistaken for active operator features.

Once candidate/install/update self-tests no longer depend on a proof package, that package may be retired in a separate hardware-tested cleanup change.

## Cleanup checklist

Periodic cleanup should verify:

- only `main`, `dev`, and `dev-plugins` are intended long-lived active branches;
- legacy checkpoint branches have immutable preserved references before removal;
- divergent work branches are archived before deletion;
- temporary CI/scaffolding is absent;
- `MANIFEST.txt` matches current trusted runtime files;
- README/install/architecture/plugin/update docs describe the current product rather than an old Alpha phase;
- generated/local plugin decoder artifacts remain ignored unless an explicit distribution decision is made;
- reference/proof plugins are not presented as user features once their validation purpose has ended;
- no secrets, runtime config, backups, SSH private keys, or signing private keys are tracked.

## Safety rule

Repository cleanup is not a reason to change RF behavior. Branch/docs/asset/fixture organization stays isolated from MMDVM-Host/DMRGateway pins, calibration, frequencies, modem ownership, and normal DMR service behavior.
