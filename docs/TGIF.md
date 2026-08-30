# Experimental TGIF + BrandMeister support

This document describes the `dev-tgif` core foundation for running BrandMeister and TGIF Network at the same time through the single YWD-owned DMRGateway instance.

This is experimental development work. TGIF is **off by default**, and upgrading an existing schema-6 hotspot to schema 7 does not enable a second network or change its normal BrandMeister routing.

## Proven dual-network checkpoint

Real-hardware acceptance passed on the Pi 5 simplex test hotspot using the shared MMDVM-Host + DMRGateway stack:

- BrandMeister and TGIF authenticated simultaneously.
- RF group destination `9990` reached BrandMeister Parrot and returned audio successfully.
- RF group destination `5009990` was rewritten to TGIF `9990`, reached TGIF Parrot, and returned audio successfully through the reverse rewrite.
- BrandMeister Parrot remained functional after TGIF was enabled.
- TGIF password/config UI and polling guard were functional.

This checkpoint proves the core routing architecture before adding richer dashboard presentation. Routing behavior below this checkpoint should remain unchanged unless a later change explicitly revises the network model.

Checkpoint commit: `bed1a521e345de0b9e6c931b202f4fbda771ac84`.

## Proven dashboard-aware checkpoint

After the network-aware dashboard slice was installed on real hardware:

- separate BM and TGIF status-strip indicators reported their links independently;
- disabling and re-enabling TGIF updated the TGIF indicator correctly without disturbing BrandMeister;
- BrandMeister Parrot passed after the disable/re-enable cycle;
- TGIF Parrot passed after the disable/re-enable cycle;
- the underlying routing rules remained unchanged from the routing checkpoint.

Dashboard-aware checkpoint commit: `0a0c910da05e1a4edc77076a9925fb81e1dc3ea3`.

## Proven unified Settings checkpoint

The unified Settings transaction was then validated on the same Pi 5 test hotspot:

- all TGIF routing, UI/admin, and dashboard-status smoke tests passed;
- TGIF enable/master/port used the normal global Settings dirty state rather than a TGIF-specific apply control;
- disabling TGIF with the ordinary `SAVE & APPLY` flow completed successfully while BrandMeister remained usable;
- re-enabling TGIF with the same ordinary `SAVE & APPLY` flow completed successfully;
- the stored TGIF security credential survived normal Settings saves and did not need to be re-entered;
- BrandMeister Parrot passed after the disable/re-enable/apply cycle;
- TGIF Parrot passed after the disable/re-enable/apply cycle;
- the separate BM and TGIF status indicators continued to report correctly throughout the cycle.

This is the preferred hardware-proven baseline for the complete dual-network + unified-Settings implementation.

Unified Settings implementation checkpoint: `9aad248932927bdc7b847e0ddbdcf8662f9ac6a3`.

A separate checkpoint marker was committed immediately before beginning TGIF directory/control-theme work:

`12605fd27571e65c6b3d40efa9bd209d9ae9214f`.

## Proven TGIF directory + control-theme checkpoint

The TGIF talkgroup-directory and dashboard-control-theme slice was then accepted as a solid working version on real hardware/browser testing:

- all TGIF routing, UI/admin, dashboard-status, and directory smoke tests passed;
- the Talkgroups page retained the existing BrandMeister manager behavior while adding TGIF directory search alongside it;
- TGIF directory lookup correctly exposed the real TGIF talkgroup and the radio-side `5xxxxxx` destination;
- TGIF favorites behaved as browser-local conveniences only and did not create pending configuration or restart network services;
- focused/active dashboard inputs and controls remained in the YWD dark/cyan theme instead of falling back to bright browser-native white/yellow styling;
- BrandMeister Parrot and TGIF Parrot both continued to pass after the directory/UI changes;
- no routing, schema, MMDVM-Host, or DMRGateway generation changes were part of this slice.

This is the preferred checkpoint for continuing `dev-tgif` work unless a later hardware-proven baseline supersedes it.

TGIF directory + control-theme implementation checkpoint: `9f87631b1885dae9d239fc7fc847a516561d63ce`.

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

This routing slice supports TGIF group talkgroups `1..999999`. A seven-digit TGIF talkgroup cannot be represented inside the fixed seven-digit prefixed RF namespace and is therefore not supported by this routing mode yet. Private-call rewriting is also deliberately not enabled.

The TGIF directory UI does not hide larger/legacy IDs. It labels them as unsupported by the current prefix scheme and does not generate a false RF destination.

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

## Dashboard controls

The experimental branch adds a `TGIF NETWORK — EXPERIMENTAL` card to Settings. It contains:

- TGIF master hostname;
- UDP port;
- network enable/disable toggle;
- TGIF security-password status and a separate password-change dialog;
- a talkgroup helper that converts a real TGIF talkgroup to the radio-side `5xxxxxx` destination.

TGIF enable/master/port are ordinary Settings fields. Editing any of them marks the same global Settings form as unsaved, participates in the normal leave-page warning, and is saved through the existing `SAVE` or `SAVE & APPLY` controls. There is no separate TGIF Save & Apply button.

The normal browser configuration remains redacted. `config-save` on `dev-tgif` is routed through `lib/tgif_admin.py`, which delegates the existing sections to the core merger and accepts only TGIF `enabled`, `master`, and `port`. Browser-visible `password` and `password_configured` placeholders are explicitly ignored, preserving the stored TGIF credential during ordinary Settings saves.

The TGIF security password remains a separate privileged action. The current dashboard uses:

```text
POST /api/tgif/password
```

The older experimental endpoint below remains available temporarily for compatibility with prior `dev-tgif` dashboard revisions, but the current UI does not call it:

```text
POST /api/tgif/configure
```

Both routes require an unlocked WebUI control session. The TGIF password change is snapshotted and audited without recording the password. If TGIF is disabled, changing the password does not bounce the active BrandMeister connection. If TGIF is already enabled, changing the password reapplies the DMR network stack so TGIF reconnects with the new credential.

Because TGIF fields now use the global Settings dirty state, normal dashboard polling does not overwrite in-progress TGIF edits. Runtime status continues to reflect the currently applied link until the operator uses the normal Settings Save & Apply action.

The shared Save & Apply reconciler keeps DMRGateway running whenever **either** BrandMeister or TGIF is enabled. It still does not start a stopped MMDVM/RF stack just because a network was enabled in configuration.

## Dashboard network presentation

The dashboard presentation layer treats BM and TGIF as separate runtime links without changing DMRGateway routing or the activity collector.

`lib/dashboard_tgif.py` projects the existing journal/config/activity state into dashboard-only metadata:

- BrandMeister and TGIF login state are parsed independently by DMRGateway network name, so a TGIF authentication error cannot make BM appear down and vice versa.
- The status strip displays separate `BM` and `TGIF` indicators.
- Group destinations in the reserved `5000001..5999999` RF namespace are identified as TGIF and translated back to the real TGIF talkgroup for presentation.
- Ordinary group destinations remain identified as BrandMeister.
- The raw RF destination is preserved as `rf_id`; presentation never destroys the modem-facing value used for diagnostics.

For example, an RF-side TGIF Parrot call is represented as:

```text
raw RF destination: 5009990
network:             TGIF
network talkgroup:   9990
friendly label:      TGIF · TG 9990 · Parrot
```

Live DMR and Last Heard use the friendly network-aware label. Last Heard also includes the raw RF destination for TGIF calls, for example `TGIF · TG 9990 · Parrot · RF 5009990`.

This interpretation happens only when the dashboard reads activity state. `ywd-activity.service` continues recording the modem's original destination exactly as received.

## TGIF talkgroup directory

The Talkgroups page now includes a TGIF directory section alongside the existing BrandMeister manager.

The source is TGIF Network's public JSON talkgroup export:

```text
https://api.tgif.network/dmr/talkgroups/json
```

YWD fetches that list server-side, normalizes it to small id/name metadata rows, and stores a local cache in `/var/lib/ywd-hotspot/tgif-talkgroup-directory.json`. The normal cache lifetime is 24 hours, matching the low-churn behavior already used by the BrandMeister directory. If refresh fails and a previous cache exists, YWD serves the stale cache with an error/stale indication instead of making the Talkgroups page unusable.

Dashboard endpoint:

```text
GET /api/tgif/talkgroups/search?q=<id-or-name>&limit=50
GET /api/tgif/talkgroups/search?ids=9990,31665
```

A forced remote refresh uses `refresh=1` and requires unlocked control mode. Ordinary cached searches remain read-only.

The UI intentionally mirrors the useful parts of the BrandMeister directory workflow:

- search by TG number or name;
- directory cache age/count display;
- explicit refresh control;
- browser-local favorites;
- real TGIF number and radio-side `5xxxxxx` destination shown together;
- one-click copy of the RF destination when the current routing model supports it.

TGIF does **not** currently expose BrandMeister-style static talkgroups, so YWD does not show `APPLY PLAN`, static-set, or static-route mutation controls for TGIF. Favorites are local browser conveniences only and never change hotspot/network state.

The same cache is used by dashboard presentation to resolve TGIF talkgroup names when available, while retaining the original raw RF destination for diagnostics.

`tools/tgif-directory-smoke.py` tests JSON normalization, name/ID search, `5xxxxxx` RF math, and the guard that refuses to fabricate an RF destination for TGIF IDs above the current `999999` routing ceiling.

## Dashboard control focus/active theme

`web/control-theme.css` adds a dashboard-wide guard for interactive controls. Text inputs, textareas, selects, buttons, file selectors, focused fields, active controls, and Chrome/WebKit autofill states stay in the dark YWD theme instead of falling back to bright native white/yellow UI.

Custom toggle switches remain owned by the existing checkbox/toggle styling; the global rules deliberately exclude checkbox/radio/range/color chrome so this polish cannot damage the existing mobile/desktop switch design.

The control-theme stylesheet is bundled into the normal `/style.css` response so it is present on first paint across every dashboard section, including dynamically injected Talkgroups, plugin, update, SSH, modem, and TGIF controls.

## Hardware / acceptance sequence

Use a non-production hotspot for this experimental branch.

1. Update/install `dev-tgif` and confirm BM + TGIF remain enabled as expected.
2. Verify all four TGIF smokes: routing, UI/admin, dashboard status, and directory.
3. Verify BrandMeister Parrot and TGIF Parrot still pass.
4. Open Talkgroups and search the TGIF directory by a known ID/name such as `31665`.
5. Verify the result reports TGIF `31665` and RF `5031665`.
6. Add/remove a TGIF favorite and confirm no network/config apply occurs.
7. Force-refresh the TGIF directory while controls are unlocked and verify cache metadata updates.
8. Focus/type in the BM search box, TGIF search box, Settings fields, dialogs, and other visible controls; none should turn bright white/yellow.
9. Disable/re-enable TGIF with the ordinary Settings Save & Apply flow and repeat both Parrot tests if any regression is suspected.

`tools/tgif-routing-smoke.py` covers schema migration, credential redaction/validation, simplex/duplex generated rules, namespace isolation, and TGIF-off compatibility without requiring RF or network access.

`tools/tgif-ui-smoke.py` checks the unified Settings transaction, TGIF credential separation, directory route/UI wiring, control-theme bundling, dispatcher/sudo wiring, polling guard, and dashboard presentation wiring. It also fails if a TGIF-specific Save & Apply control or browser call to `/api/tgif/configure` is reintroduced.

`tools/tgif-status-smoke.py` exercises independent BM/TGIF journal-state parsing and verifies that RF `5009990` projects to `TGIF · TG 9990 · Parrot` while ordinary RF `9990` remains `BM · TG 9990 · Parrot`.

## Next slices

With core routing, unified Settings controls, network-aware dashboard presentation, and TGIF directory intelligence in place, follow-on work can add:

- richer activity hydration/metadata from the TGIF cache where useful;
- a signed TGIF UI plugin for richer TGIF-specific features without giving plugin code direct modem or arbitrary network access;
- a deliberate solution for seven-digit TGIF talkgroups rather than silently creating ambiguous routing.
