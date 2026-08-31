# 🛰️ TGIF Control Center

[← Docs index](README.md) · [TGIF architecture](TGIF.md) · [Talkgroup Manager](TALKGROUPS.md)

The TGIF Control Center is YWD-Hotspot's network-specific operating page for TGIF Network. The **TGIF** tab appears only when TGIF is enabled in Settings.

It does not replace the existing BrandMeister Talkgroup Manager and it does not change the proven DMRGateway routing model. In the dashboard navigation the BrandMeister page is labeled **BM TALKGROUPS** so it is visually distinct from the dedicated TGIF page.

## What the page provides

The Control Center combines:

- TGIF connection/master/hotspot-ID status;
- the current YWD `5xxxxxx` RF namespace reminder;
- TGIF-only live and recent activity;
- the TGIF public talkgroup directory;
- appliance-persistent TGIF favorites;
- an appliance-persistent scanner watchlist of up to 10 TGIF talkgroups;
- one-click **TUNE** and **DISCONNECT TGIF** session controls;
- a YWD watchlist scanner with dwell, post-call hold, manual HOLD/RESUME/NEXT, and explicit START/STOP.

## YWD scanner versus TGIF Custom Scan

TGIF Network has its own server-side **Custom Scan** feature in SelfCare. YWD-Hotspot does **not** impersonate that feature and does not claim to configure it.

The YWD scanner is a hotspot-side client feature. It uses TGIF's public session-update mechanism to change which TGIF talkgroup the hotspot session is listening to. This is the same class of TGIF session change historically used by hotspot release/change-TG helpers.

That distinction matters:

```text
TGIF Custom Scan
  server-side TGIF/SelfCare feature

YWD Watchlist Scanner
  local YWD service
  changes the hotspot's TGIF session
  does not transmit/key RF to request a talkgroup
```

The scanner never rewrites DMRGateway rules, never takes ownership of the modem, and never generates a synthetic DMR transmission.

## Radio requirement

Changing the TGIF network session does not change your radio's receive-group filtering.

To hear arbitrary talkgroups while the scanner moves through its watchlist, the radio normally needs a receive mode such as:

- **Open RX**;
- **Promiscuous**;
- **Digital Monitor**;
- or the manufacturer's equivalent feature that accepts group traffic not explicitly present in the channel's receive group.

Without that, the hotspot may correctly transmit a scanned TGIF call as RF `5xxxxxx` while the radio silently rejects it.

## RF namespace

The existing YWD TGIF routing remains unchanged:

```text
TGIF TG 31665
     ↓
RF group destination 5031665
```

Supported scanner/directory talkgroups are TGIF `1..999999`, except TG `4000`, which is reserved in the Control Center as the TGIF disconnect command.

Talkgroups above `999999` are still outside the current fixed seven-digit RF prefix scheme and are not fabricated into false RF destinations.

TGIF's public directory can omit service destinations such as Parrot. YWD supplements the directory with its small known-service list and permits an exact numeric search to produce a usable row for an otherwise valid TGIF talkgroup. For example:

```text
TGIF Parrot       9990
Radio destination 5009990
```

## Favorites

Favorites are saved on the hotspot rather than in browser `localStorage`.

Current state file:

```text
/var/lib/ywd-hotspot/tgif-control.json
```

This means phone and desktop browsers see the same TGIF favorites/watchlist on that appliance, and normal YWD application updates preserve them.

The first scanner hardware slice intentionally did **not** add this new state file to `.ywdsettings`. Portable backup/restore support remains a separate follow-up so scanner validation is not mixed with restore-transaction changes.

## Watchlist

The scanner supports up to 10 enabled talkgroups. The displayed P1/P2/... order is the local scan order/priority:

```text
P1 → P2 → P3 → ... → P10 → P1
```

Reorder the list with the up/down controls.

The initial defaults are:

```text
Dwell              5 seconds
Post-call hold     3 seconds
Simplex slot       TS2
Scanner at boot    OFF
```

Dwell may be set from 2 to 60 seconds. Post-call hold may be set from 0 to 30 seconds.

On a duplex hotspot, TS1 or TS2 can be selected. On a simplex hotspot YWD always uses TGIF TS2.

## Traffic hold behavior

The scanner watches YWD's existing MMDVM activity state. It recognizes a scanner hit only when all of the following match:

- activity came from the **network**, not a local RF transmission;
- the timeslot matches the scanner slot;
- the destination is a group call;
- the RF destination is the current TGIF-prefixed destination (`5000000 + TGIF TG`);
- the activity began after YWD tuned the session to that talkgroup.

While a matching TGIF call is active, the scanner remains on that talkgroup. When the call ends, the configured post-call hold is honored before scanning continues.

Local RF transmissions do not masquerade as scanner hits.

## Controls

### START SCAN

Saves the current dwell/hold/slot/watchlist settings and starts the runtime scanner.

At least one enabled watchlist entry is required. TGIF must be enabled and DMRGateway must already be running.

### HOLD

Manually holds the currently tuned scanner talkgroup indefinitely.

### RESUME

Releases manual hold and resumes normal dwell/scanning.

### NEXT

Immediately moves to the next watchlist entry.

### STOP

Stops the YWD scanner but deliberately leaves the TGIF session on the currently selected talkgroup. This makes STOP useful when the scanner lands somewhere you want to keep listening.

### TUNE

Stops the scanner and pins the TGIF session to the selected talkgroup. The UI also shows the corresponding radio-side `5xxxxxx` destination.

### DISCONNECT TGIF

Stops the scanner and sends TGIF talkgroup `4000` through the session-update mechanism.

This changes TGIF session state only. It does not disable TGIF in YWD Settings and does not disconnect BrandMeister.

## Pi Zero control feedback

Scanner/session actions can take long enough on an original Pi Zero that a button with no immediate visual change feels broken even when the request is working normally.

The Control Center therefore gives immediate presentation feedback for these buttons:

```text
SAVE SETTINGS    → SAVING…
START SCAN       → STARTING…
HOLD             → HOLDING…
RESUME           → RESUMING…
NEXT             → NEXT…
STOP             → STOPPING…
DISCONNECT TGIF  → DISCONNECTING…
```

A small spinner appears immediately and duplicate clicks are suppressed while that request is in flight. The existing toast remains the completion/error notification. This feedback layer observes the already-existing authenticated API calls; it does not own or change scanner/network behavior.

## Status-page scanner display

While `ywd-tgif-scanner.service` is actively scanning, the main **STATUS** page displays a TGIF SCANNER card using the existing read-only scanner-status endpoint.

During normal scanning the card shows:

- **SCANNING** state;
- current TGIF talkgroup and friendly name;
- current RF `5xxxxxx` destination and timeslot;
- dwell time remaining;
- a cyan moving scanner/scope sweep.

When the scanner holds, the card changes to **HOLDING**, identifies traffic, post-call, or manual hold, and changes the moving sweep into an amber lock/pulse presentation. The card hides when the scanner service is not active so the Status page is not permanently occupied by an idle scanner.

Status polling runs only when the browser is visible and the Status page is selected. The animation includes a `prefers-reduced-motion` fallback.

This is a presentation-only layer. It reads `/api/tgif/control/status` and does not call the TGIF session-update endpoint, privileged helper, DMRGateway, MMDVM-Host, or RF controls.

## Boot/update behavior

The watchlist and favorites persist, but the scanner itself is **runtime-only** and is not enabled at boot.

A reboot therefore does not silently restart an old scan. The operator explicitly starts scanning from the authenticated dashboard each time.

Before RC4 freeze, the updater path will also be checked so an active scanner is quiesced cleanly while DMRGateway/application files are being updated.

## Security boundary

The dashboard cannot execute arbitrary scanner commands.

All mutations route through one narrow privileged action:

```text
ywd-hotspot-admin tgif-control
```

The operation is validated server-side. The scanner daemon itself runs unprivileged as `ywd-hotspot` and receives no modem/RF transmit authority.

Read-only scanner status and TGIF directory search remain available without unlocking controls. Starting/stopping/tuning, changing favorites/watchlist, forced directory refreshes, and other mutations require an unlocked WebUI control session.

## Hardware validation status

The scanner runtime has been physically accepted on the mature simplex appliance. Validation included:

- TGIF Parrot `9990` TUNE/session control with RF destination `5009990`;
- two-entry watchlist rotation;
- five-second dwell behavior;
- manual HOLD/RESUME/NEXT;
- automatic hold on watched TGIF network traffic;
- three-second post-call hold;
- simultaneous BrandMeister and TGIF connectivity;
- active MMDVMHost and DMRGateway services;
- zero failed systemd units.

The responsive-button and Status-page animation layer is a later presentation-only polish slice and receives its own browser acceptance without reopening the already-proven scanner routing/runtime contract.
