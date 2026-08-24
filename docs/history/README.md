# YWD-Hotspot Historical Documentation

[← Documentation index](../README.md)

This directory preserves implementation notes, completed release plans, and other records that are useful for provenance but are **not current operating instructions**.

Use the current guides in `docs/` for installation, operation, building, upgrades, security, plugins, vocoder setup, and repository policy.

## Archive contents

| Document | Purpose |
|---|---|
| [ALPHA21-22-DEVELOPMENT-NOTES.md](ALPHA21-22-DEVELOPMENT-NOTES.md) | Alpha21/22 implementation archaeology around passive DMR observation, duplex/RX work, and related hardening |
| [PHASE3H-PRECOMPUTED-TONE-OBSERVATION.md](PHASE3H-PRECOMPUTED-TONE-OBSERVATION.md) | Physical observation that isolated the remaining RX-audio problem above the fake vocoder backend |
| [PHASE3H-NEXT-STREAMING-PLAN.md](PHASE3H-NEXT-STREAMING-PLAN.md) | Historical plan that led to the persistent Phase 3J streamed-audio architecture |
| [RELEASE-PLAN-0.2.0-rc1.md](RELEASE-PLAN-0.2.0-rc1.md) | Completed RC1 release plan / physical acceptance record |

The old standalone `docs/checkpoints/` Phase 3H note was removed after its useful evidence was preserved in the fuller observation document and in retained Git checkpoint refs.

Historical documents intentionally retain terminology and state from the time they were written. They should not be silently rewritten to describe later releases.
