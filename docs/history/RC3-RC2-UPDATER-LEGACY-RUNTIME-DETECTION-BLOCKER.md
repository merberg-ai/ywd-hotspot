# RC3 Published-RC2 Updater Acceptance — Legacy Runtime Detection Blocker

**Date:** 2026-08-24  
**Release:** `0.2.0-rc3`  
**Starting image:** published `0.2.0-rc2`

## What the physical updater test proved

The published RC2 image updated successfully to the frozen RC3 candidate without recompiling or replacing either radio binary.

Untouched RC2 binary hashes before and after the app update were identical:

```text
MMDVM-Host
f0b9c468c2832c784497e2843eeb84eaaf929a6c2eb140da5e9d1f6fc2dca480

DMRGateway
decc20692f75f4eb6fcf943a17acf66f1fe2632b86971cc89f89fef4c48537f2
```

RF services returned active and `systemctl --failed` reported zero failed units.

## Blocker found

RC3 failed to classify the untouched accepted RC2 YWD Extended runtime. The observed runtime was reported as `unknown` even though persisted RC2 provenance correctly identified:

```text
patch_sha256 = f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
upstream_commit = dea6e9b2c35857fe6f904c5092bebadb86cbf079
capabilities = passive-dmr-voice, plugin-rx-monitor
```

The intended RC3 result is:

```text
runtime_generation = legacy
upgrade_required = true
capabilities = passive-dmr-voice, plugin-rx-monitor
```

The legacy runtime must not gain `demand-gated-dmr-voice` by inference.

## Root cause

`mmdvm_runtime_state.py` contains an explicit allowlist and correct legacy-classification logic, but it expected the full historical marker to arrive in the JSON returned by `mmdvm_voice_build.py status`.

The helper deliberately summarizes marker metadata in its public status output and does not expose the full marker object. The unit smoke passed because it injected a synthetic marker directly into `classify_runtime()`, so the real helper-to-classifier transport seam was not covered.

## Fix

`mmdvm_runtime_state.py` now reads the same root-owned marker file directly when helper status does not provide a full marker:

```text
/var/lib/ywd-hotspot/mmdvm-voice-tap.json
```

The existing safeguards remain authoritative:

- historical patch SHA must be explicitly allowlisted;
- marker binary SHA must match the exact installed MMDVM-Host binary;
- marker upstream commit must match the pinned upstream commit;
- marker status must be `installed` or `active`;
- marker extension API must match the accepted legacy generation.

This change does not rebuild MMDVM-Host, alter the MMDVM patch, restart RF, or grant any new legacy capability.

## Regression coverage

Added:

```text
tools/mmdvm-runtime-marker-transport-smoke.py
```

The regression reproduces the actual RC2 -> RC3 seam: helper status omits the full marker while the root-owned historical marker remains present. It requires the accepted RC1/RC2 Extended generation to be classified as legacy and to require an explicit runtime refresh.

## Acceptance status

The original frozen candidate is superseded by this blocker fix. RC3 remains unaccepted until the published-RC2 updater path is rerun/continued against the corrected release candidate and the exact final factory image passes the remaining physical gates.

`main`, the public RC3 tag, and the immutable RC3 proven checkpoint remain frozen until final acceptance.
