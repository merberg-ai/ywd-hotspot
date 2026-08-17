# 🧱 YWD-Hotspot Architecture

[← Docs index](README.md) · [Project README](../README.md) · [Display](DISPLAY.md) · [OS Image Build](OS-IMAGE-BUILD.md) · [Security](../SECURITY.md) · [Development notes](GITHUB-SETUP.md)

---

YWD-Hotspot keeps the actual DMR transport path deliberately small and separates presentation/admin features from RF operation.

## 📡 RF path

```text
DMR radio
   │
   ▼
MMDVM HAT
   │
   ▼
MMDVM-Host
   │
   ▼
DMRGateway
   │
   ▼
BrandMeister
```

The core RF path does not depend on the dashboard, OLED, or activity presentation continuing to run.

## 🧩 Side services

| Service | Role |
|---|---|
| `ywd-activity.service` | Parses MMDVM-Host activity into bounded cached state / Last Heard data |
| `ywd-dashboard.service` | Python stdlib HTTP dashboard/API; reads cached state and routes validated writes through the admin helper |
| `ywd-headless-oled.service` | YWD-Hotspot OS authoritative SSD1306/I2C owner using the unified renderer |
| `ywd-oled.service` | Generic/non-OS OLED unit; kept disabled on YWD-Hotspot OS |
| `ywd-update.service` | Detached one-shot software update job started only through authenticated update control |
| `ywd-setup.service` | YWD-Hotspot OS secure first-boot setup server; disabled/irrelevant after setup completes |
| `ywd-dmrid-update.timer` | Periodically refreshes lightweight RadioID data when due |

## 📟 OLED ownership invariant

YWD-Hotspot OS must have **exactly one process owning the physical OLED**.

```text
YWD-Hotspot OS
  ywd-headless-oled.service
           │
           └── /opt/ywd-hotspot/app/lib/oled.py --os-owner

Generic install
  ywd-oled.service
           │
           └── /opt/ywd-hotspot/app/lib/oled.py
```

`lib/oled_owner.sh` installs a systemd drop-in on YWD-Hotspot OS so the existing headless daemon remains the sole owner while using the shared runtime renderer. The duplicate app OLED service is disabled there.

Config apply/revert and manual OLED restart paths serialize ownership so the two services are never intentionally active against the same I2C device at once.

The OLED renderer is a passive consumer. It may read local config/activity/network/update files and write the display. It must not control RF, networking, BrandMeister, or canonical configuration. OLED failure must not interrupt DMR.

## 🔐 Privilege boundary

The dashboard runs as the restricted `ywd-hotspot` user.

Privileged browser operations are funneled through:

```text
/usr/local/libexec/ywd-hotspot-admin
```

with the restricted sudo policy:

```text
/etc/sudoers.d/ywd-hotspot
```

The dispatcher routes only named actions to dedicated helpers. Software update, first-boot finalization and OS OLED-owner transitions do not expose arbitrary branch names, shell commands, URLs, or paths to browser input.

The browser must never directly execute arbitrary shell text or directly edit generated MMDVM-Host/DMRGateway INI files.

## ⚙️ Canonical configuration

Source of truth:

```text
/etc/ywd-hotspot/config.json
```

Generated outputs:

```text
/etc/ywd-hotspot/MMDVM-Host.ini
/etc/ywd-hotspot/DMRGateway.ini
```

Configuration flow:

```text
browser / CLI input
        │
        ▼
validate + normalize
        │
        ▼
transactional canonical JSON update
        │
        ▼
regenerate temporary INIs
        │
        ▼
atomic apply / scoped service action
```

Current canonical configuration schema is **5**. Schema 5 includes the unified OLED runtime-presentation controls plus the LIVE DMR instrumentation/history/measurement-hold settings introduced in the Alpha12.x line. Older configurations normalize forward with conservative defaults.

Normal configuration history is retained separately for rollback.

## 🔑 Credential separation

YWD-Hotspot treats these as different secrets:

1. BrandMeister Hotspot Security password — used by DMRGateway
2. BrandMeister API v2 key — server-side BM control actions
3. local WebUI control password — unlocks LAN write/admin controls

Reusable secret material must not appear in browser-readable config, support summaries, or public diagnostic bundles.

## 🥧 YWD-Hotspot OS factory/setup path

A generated YWD-Hotspot OS image intentionally starts from a factory placeholder rather than pretending to be a configured transmitter:

```text
image build
  ↓
NOCALL / 00000 / BrandMeister disabled
RF services disabled
  ↓
network onboarding
  ↓
secure HTTPS first-boot wizard
  ↓
validated canonical config + dashboard credential
  ↓
optional explicit RF enable
```

Without station Wi-Fi, the OS network manager uses the single Pi Zero Wi-Fi interface to create `YWD-Hotspot-XXXX` at `10.42.0.1`. Once station Wi-Fi is online, the OLED supplies a short-lived six-digit setup code for `https://ywd-hotspot.local:8443/`.

The current builder can optionally preseed Wi-Fi, but it does not provide a supported full radio/BrandMeister credential preseed. See **[OS-IMAGE-BUILD.md](OS-IMAGE-BUILD.md)**.

## 📁 Runtime/state layout

```text
/etc/ywd-hotspot/
  config.json
  MMDVM-Host.ini
  DMRGateway.ini
  bm-api.key
  web-auth.json
  build-info.json
  update-channel

/var/lib/ywd-hotspot/
  DMRIds.dat
  lastheard.json
  calibration.json
  calibration-baseline.json
  geocode-cache.json
  talkgroup-directory.json
  update-status.json
  setup-state.json          # YWD-Hotspot OS after first-boot completion
  config-history.json
  audit.json
  private/

/run/ywd-hotspot/
  activity.json
  setup.json                # temporary YWD-Hotspot OS setup state/code

/var/backups/ywd-hotspot/
```

Private runtime/config backups can contain credentials and must not be published.

## 🌿 GitHub source vs live runtime

```text
/opt/ywd-hotspot/repo    root-owned managed Git checkout
/opt/ywd-hotspot/app     deployed application copy; no .git
```

Update flow:

```text
GitHub fetch
   │
   ▼
resolve target commit
   │
   ▼
stage + validate candidate
   │
   ▼
protected app/config backup
   │
   ▼
transactional UPDATE.sh
   │
   ▼
restore prior RF/service policy
   │
   ▼
advance managed checkout after success
```

WebUI installs start a detached `ywd-update.service`, allowing the dashboard to restart without killing its own updater. A sanitized status file provides stage/progress information to the browser and optionally to the OLED.

Network failure, dirty source, or candidate-validation failure occurs before the live application is touched.

## 🌐 WebUI layers

The browser side intentionally stays small:

```text
style.css                    base dashboard theme
app-core.js                  established dashboard behavior
talkgroups.js                Talkgroup Manager layer
ui-polish.css/js             lightweight UX/polish
update.css/js                About-page software update controls
update-progress.js           stage-driven update progress modal
instrumentation.css/js       optional LIVE DMR gauges/traces/settings
instrumentation-bootstrap.js initialization hook; no poll loop
app.js                       tiny loader
```

The enhanced LIVE DMR panel reuses the dashboard's existing status payload. It does not add a new daemon or a second server polling loop. When enhanced instrumentation is disabled, the established Basic LIVE DMR renderer remains in use.

The UI uses same-origin external assets so the dashboard can retain a restrictive Content-Security-Policy without `unsafe-inline` styling in the normal dashboard.

## 🥧 Pi Zero performance budget

Prefer:

- Python standard library
- small long-running collectors
- cached/event state over repeated expensive shelling
- plain HTML/CSS/JS
- CSS/SVG animation in the browser
- bounded local files
- explicit Basic/low-power modes

Avoid turning a Pi Zero into infrastructure cosplay:

- no Node.js runtime
- no React/Vue requirement
- no SQL server
- no Redis
- no Docker dependency
- no heavyweight graphing framework without a real need

## 📡 RF safety invariant

Install, image first boot, update, config-apply, runtime-control, display, and UI paths must preserve explicit operator intent.

A UI change, OLED restart, Git pull, dashboard restart, software update, Wi-Fi handoff, or completed setup wizard page is **never** permission to unexpectedly start a transmitter. RF begins only when the operator deliberately requests it through the supported RF-enable path.
