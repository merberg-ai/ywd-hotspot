# 📻 Talkgroup Manager

[← Docs index](README.md) · [Project README](../README.md) · [Security](../SECURITY.md)

---

YWD-Hotspot's BrandMeister Talkgroup Manager is built around one safety rule:

> **Browsing and planning do not change BrandMeister.**

Static talkgroup changes happen only after the operator reviews a change plan, presses **APPLY PLAN**, and confirms it.

## 🎛️ BrandMeister behavior

BrandMeister distinguishes between:

- **Static** talkgroups — remain subscribed until removed;
- **Dynamic** talkgroups — created by RF activity and can be cleared with **DROP ALL DYNAMIC**.

YWD-Hotspot uses the BrandMeister API v2 key configured with:

```bash
sudo ywd-hotspotctl bm-api-key
```

The API key stays on the Pi and is never returned to browser JavaScript.

### Simplex vs duplex slot routing

YWD-Hotspot supports both radio modes:

```text
simplex
  one RF frequency
  BrandMeister static-TG API operations use the simplex slot convention (0)

duplex
  separate hotspot RX/TX frequencies
  TS1 + TS2 available
  talkgroup operations are slot-aware and preserve the selected TS1/TS2 routing
```

The dashboard/configuration is the source of the hotspot's operating mode. Do not assume a duplex HAT should be treated as simplex merely because one timeslot happens to be active.

## 🧭 Talkgroup Manager page

The dedicated **TALKGROUPS** tab includes:

| Area | Purpose |
|---|---|
| Current Static | Live BrandMeister static subscriptions |
| Current Dynamic | Live dynamic subscriptions |
| Directory Search | Search public BrandMeister TG IDs/names |
| Favorites | Browser-local quick-access TGs |
| Saved Static Sets | Browser-local named desired plans |
| Static Change Plan | Preview desired adds/removals before apply |
| Drop All Dynamic | Clear dynamic subscriptions with confirmation |

Quick **DROP QSO** / **DROP ALL DYNAMIC** actions are also surfaced with the live BrandMeister status area when controls are unlocked.

## 🔎 Directory search + Pi Zero performance

The browser searches through the local YWD dashboard; it does not talk directly to BrandMeister.

To stay lightweight on the original Pi Zero W:

- the full directory is downloaded only on demand;
- normalized data is cached at `/var/lib/ywd-hotspot/talkgroup-directory.json`;
- normal cache lifetime is 24 hours;
- repeated searches use the local cache;
- **REFRESH DIRECTORY** is available while control mode is unlocked;
- a stale cache can still be used if BrandMeister directory lookup is temporarily unavailable.

The cache contains public TG IDs/names only. It contains no API key or hotspot password.

## 📝 Static change plan

Opening the manager initializes the desired plan from the hotspot's current static subscriptions for the relevant routing context.

Adding/removing a TG in the manager edits only the local browser plan.

Example:

```text
ADD    3106, 31073
REMOVE 91
```

Nothing is sent upstream until **APPLY PLAN** is pressed and the confirmation dialog is accepted.

### Apply order

YWD-Hotspot sends **additions first**.

That means existing statics are not removed merely because BrandMeister rejected a new addition. Removals are attempted only after additions succeed.

If an API operation fails partway through, the batch stops and live BrandMeister state is refreshed rather than pretending the whole plan succeeded.

## ⭐ Favorites

Search results can be starred for quick access.

Favorites live in browser `localStorage` and are convenience metadata only. They never change BrandMeister on their own.

Because they are browser-local, a favorite saved on one phone/browser does not automatically appear on another device.

## 💾 Saved static sets

A desired plan can be saved with names such as:

```text
Local
Travel
Nets
Experiment
```

Saved sets are also browser-local.

Loading a set changes the **plan only**. It does not alter BrandMeister until **APPLY PLAN** is confirmed.

On duplex systems, review the intended timeslot before applying a saved plan.

## 💻 CLI controls

Direct BrandMeister controls remain available:

```bash
sudo ywd-hotspotctl bm profile
sudo ywd-hotspotctl bm addtg 3100
sudo ywd-hotspotctl bm deltg 3100
sudo ywd-hotspotctl bm dropqso
sudo ywd-hotspotctl bm dropdyn
```

Use the WebUI when you need the full duplex/slot-aware planning presentation.

## 🔐 Security boundary

Directory search is read-only and does not require exposing the BrandMeister API key to the browser.

Changing subscriptions or clearing dynamic routes requires:

1. a configured BrandMeister API key;
2. an unlocked YWD-Hotspot control session;
3. the authenticated local dashboard API;
4. explicit confirmation for destructive/batch actions.

The Talkgroup Manager never returns the BrandMeister API key to browser JavaScript.

## 🧪 Good test flow

When testing a new build:

1. verify simplex/duplex mode and, for duplex, both slot contexts;
2. verify Current Static/Dynamic state;
3. search a known TG by number;
4. search a TG by name;
5. add/remove TGs from the plan and verify live state does not change;
6. cancel an **APPLY PLAN** confirmation;
7. apply a harmless intended change on the intended slot;
8. confirm live BrandMeister state refreshes correctly;
9. save/load a named set and verify it changes the plan only.
