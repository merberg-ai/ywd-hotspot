# Experimental TGIF + BrandMeister support

This document describes the first `dev-tgif` core foundation for running BrandMeister and TGIF Network at the same time through the single YWD-owned DMRGateway instance.

This is experimental development work. TGIF is **off by default**, and upgrading an existing schema-6 hotspot to schema 7 does not enable a second network or change its normal BrandMeister routing.

## Design goals

- MMDVM-Host remains the only modem/RF owner.
- DMRGateway remains the only DMR network-routing owner.
- BrandMeister and TGIF may be connected simultaneously.
- No DMR traffic is bridged from one network to the other.
- Normal BrandMeister talkgroups keep their ordinary radio numbers.
- TGIF gets a distinct RF destination namespace so the operator chooses the network by the destination programmed in the radio.
- TGIF credentials are separate from BrandMeister credentials and are redacted from public configuration/status data.
- No MMDVM firmware, MMDVM-Host patch, or DMRGateway rebuild is required for this routing model.

## RF namespace

The first implementation reserves the seven-digit `5xxxxxx` group-call namespace for TGIF. This follows the convention commonly used by multi-network hotspot configurations.

Example:

```text
TGIF network talkgroup 31665
        ^
        | add RF prefix 5
        v
radio destination 5031665
```

DMRGateway removes the leading namespace by arithmetic rewrite:

```text
RF 5000001..5999999  <->  TGIF 1..999999
```

The reverse rewrite also means TGIF network traffic for talkgroup `31665` is presented to the radio as destination `5031665`.

### Current limitation

This first slice supports TGIF group talkgroups `1..999999`. A seven-digit TGIF talkgroup cannot be represented inside the fixed seven-digit prefixed RF namespace and is therefore not supported by this routing mode yet. Private-call rewriting is also deliberately not enabled in the first slice.

## BrandMeister isolation

When TGIF is disabled, BrandMeister keeps the existing YWD pass-all group/private-call behavior.

When TGIF is enabled, BrandMeister group `PassAllTG` is replaced by identity rewrite ranges that cover the DMR destination space **except** `5000000..5999999`. Private calls continue using the existing BrandMeister pass-all rule.

For a simplex hotspot on slot 2 the effective intent is:

```text
RF TG 1..4999999        <-> BrandMeister same TG
RF TG 5000000..5999999      reserved for TGIF namespace
RF TG 6000000..16777215 <-> BrandMeister same TG

RF TG 5000001..5999999  <-> TGIF TG 1..999999
```

This is intentionally stricter than relying only on DMRGateway rule ordering. It prevents BrandMeister group traffic in the reserved namespace from appearing on RF as if it were TGIF traffic.

`TrunkingEnabled` remains `0`.

## Schema 7

Schema 7 adds a separate top-level TGIF configuration:

```json
{
  "tgif": {
    "enabled": false,
    "master": "tgif.network",
    "port": 62031,
    "password": ""
  }
}
```

Existing schema-6 configuration is migrated with TGIF disabled.

TGIF enablement fails closed if no TGIF security password is configured. The password is validated separately from the BrandMeister Hotspot Security password, is never returned by `config_model.public()`, and is excluded from secret-insensitive configuration hashes.

YWD does not synthesize or recommend the legacy shared `passw0rd` credential. Use the TGIF Network security credential associated with the operator account.

## Generated DMRGateway layout

BrandMeister remains `[DMR Network 1]`. TGIF is `[DMR Network 2]`. Networks 3 through 5 remain disabled.

TGIF never receives `PassAllTG` or `PassAllPC` in this design. It only receives the explicit group rewrite for the reserved RF namespace.

The same namespace is generated independently on slots 1 and 2 for a duplex HAT. A simplex HAT emits only the slot-2 rules.

## First test sequence

Use a non-production hotspot for this experimental branch.

1. Update/install `dev-tgif` with TGIF still disabled.
2. Verify ordinary BrandMeister operation and Parrot are unchanged.
3. Configure the TGIF security password and enable TGIF.
4. Apply the configuration and verify DMRGateway reports successful connections to both BrandMeister and TGIF.
5. Verify a normal BrandMeister destination still reaches BrandMeister.
6. Key radio destination `5031665` and verify DMRGateway sends TGIF destination `31665` only to TGIF.
7. Verify an inbound TGIF call to `31665` is emitted to RF as `5031665`.
8. Verify no TGIF call is forwarded to BrandMeister and no BrandMeister group call in the reserved `5xxxxxx` namespace is emitted to RF.
9. Disable TGIF and apply; verify BrandMeister returns to its original pass-all group behavior.

`tools/tgif-routing-smoke.py` covers schema migration, credential redaction/validation, simplex/duplex generated rules, namespace isolation, and TGIF-off compatibility without requiring RF or network access.

## Next slices

The backend routing foundation intentionally lands before the dashboard controls. Planned follow-on work can add:

- safe TGIF credential/enable controls in Settings;
- per-network connection state in the dashboard;
- TGIF-aware activity labels that display the real TGIF talkgroup instead of only the prefixed RF destination;
- a signed TGIF UI plugin for richer TGIF-specific features without giving plugin code direct modem or arbitrary network access;
- a deliberate solution for seven-digit TGIF talkgroups rather than silently creating ambiguous routing.
