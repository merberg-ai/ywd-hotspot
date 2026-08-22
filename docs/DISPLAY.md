# 📟 Display + Live DMR Instrumentation

[← Docs index](README.md) · [Project README](../README.md) · [Telemetry](TELEMETRY.md) · [Architecture](ARCHITECTURE.md)

---

YWD-Hotspot keeps display features outside the RF-critical path. The enhanced WebUI instrument panel and OLED runtime screens are optional presentation layers; MMDVM-Host and DMRGateway do not depend on them.

## 🌐 LIVE DMR WebUI modes

The Status page supports two broad behaviors:

- **Basic** — preserves the lightweight LIVE DMR status/animation.
- **Enhanced instrumentation** — adds the animated RX/TX energy display, BER/quality presentation, optional modem-reported RSSI, configured TX/RF drive context, and bounded history traces.

Enhanced instrumentation uses the same normal dashboard status payload. Browser-side presentation does not open the modem or create another RF owner.

### Presets

| Preset | Behavior |
|---|---|
| `basic` | Enhanced instrumentation disabled; lightweight status UI |
| `balanced` | restrained animation with signal/quality/TX instrumentation where measurements exist |
| `instrument` | instrumentation plus bounded RSSI/BER histories when available |
| `maximum` | full animation/history/peak/status-strip presentation |
| `custom` | selected after changing individual instrumentation controls |

### Instrumentation controls

Configuration is stored under `display.instrumentation` in the canonical config and includes:

- enable/disable enhanced instrumentation
- RSSI meter style/scale/segment count
- peak hold and hold duration
- BER quality thresholds
- TX/RF drive meter
- post-call measurement hold
- RSSI and BER histories
- sample-count or time-window history
- maximum sample age
- browser render-rate target: 5, 10, or 20 fps
- animation intensity: off, subtle, normal, or high
- idle animation
- live top status-strip details
- numeric values and label density
- reduced-motion policy

Controls may exist even when a particular modem firmware does not provide the corresponding measurement. The runtime presentation remains data-aware.

## 📡 RX behavior

YWD has two passive observation sources:

1. the bounded activity/journal collector used for normal RX/TX/Last Heard state;
2. YWD Extended's loopback MQTT telemetry/voice path, which can carry structured BER/RSSI/DMR information without taking modem ownership.

During an RF → hotspot call, the panel shows the RX state and animated radio-energy visualization. BER is displayed when the current/completed MMDVM activity supplies it.

### RSSI is optional hardware/firmware data

RSSI/dBm is **not guaranteed by the MMDVM protocol/hardware combination**. Compatible MMDVM_HS firmware may provide RSSI, but many builds omit or disable that firmware feature. A board can therefore work perfectly for DMR and report valid BER while every RSSI field remains zero/unavailable.

YWD-Hotspot follows these rules:

```text
usable RSSI supplied by modem   -> show dBm meter/history/peak
no usable RSSI supplied         -> hide RSSI-only presentation
BER supplied                    -> show BER/quality normally
BER only                        -> never estimate/fake dBm from BER
```

The reference duplex HAT used for `0.2.0-rc1` physical testing produced valid BER and voice telemetry but reported `rssi=0` for RF frames. The accepted dashboard therefore hides the unavailable dBm meter on that hardware instead of leaving a permanent fake/sampling gauge.

MMDVM_HS firmware can be built with optional RSSI reporting on hardware/firmware combinations that support it. That is **HAT firmware**, not a setting that can be fixed merely by recompiling MMDVM-Host on the Pi. YWD-Hotspot does not automatically flash modem firmware.

See **[TELEMETRY.md](TELEMETRY.md)** for the RSSI mapping/transport details.

### BER / quality layout

When RSSI is unavailable, the enhanced LIVE DMR card deliberately reflows around the data it does have:

- animated RX/TX radio visualization centered as the primary state indicator;
- horizontal BER/quality meter beneath the animation;
- BER history across the lower card when history is enabled;
- no empty/dead RSSI column.

If a later modem/firmware starts providing usable RSSI, the RSSI presentation can return automatically.

## 📤 TX behavior

During network → RF transmission there is no incoming RF RSSI to measure, so the enhanced panel does not pretend there is an RX signal measurement.

TX mode prioritizes:

- configured TX/DMR level
- configured RF level
- source and destination
- slot / elapsed time
- completed network quality information when supplied

TX Level and RF Level are configured drive values, **not measured RF output power**.

## 📈 History modes

History is built only from measurements actually present in completed RF activity.

### Last samples

The recommended/default mode keeps the last N completed RF measurements up to a configurable maximum age:

```text
history_mode       samples
history_samples    20
history_max_age_s  900
```

### Time window

Time mode retains completed RF samples within a configured number of seconds:

```text
history_mode       time
history_seconds    60
```

BER history can remain useful even on hardware with no RSSI support. RSSI history stays hidden/empty when no real RSSI exists.

## 🔐 Strict CSP behavior

The dashboard retains its restrictive `style-src 'self'` Content Security Policy. Instrumentation uses same-origin external CSS/JS rather than weakening CSP with `unsafe-inline`.

Dynamic meter levels are represented with bounded states and styled by same-origin CSS. The RC1 layout-specific stylesheet is also served through an explicit trusted dashboard static route and is part of candidate validation.

## 🎛️ Data honesty

The instrument panel distinguishes measured data from presentation:

- RSSI appears only when the modem/runtime provides a usable RSSI value;
- RSSI value `0`/missing is treated as unavailable, not `0 dBm`;
- BER appears only when captured from MMDVM activity/telemetry;
- BER is not converted into a guessed signal strength;
- TX/RF levels are configured drive values, not a wattmeter;
- network loss/BER values appear only when supplied for completed network-originated transmissions;
- animated RF energy is an activity visualization, **not** an audio VU meter or spectrum analyzer.

## ⚡ Performance behavior

The original Pi Zero W remains the performance budget.

- Basic mode avoids the optional enhanced presentation.
- Enhanced drawing/animation runs in the browser.
- The local MQTT broker is loopback-only and exists as shared trusted YWD telemetry infrastructure, not as a browser charting framework.
- Telemetry/voice snapshots are bounded and written conservatively.
- History arrays are small and bounded.
- Render-rate choices are 5, 10, or 20 fps.
- Reduced-motion can follow the browser/OS preference or be forced from YWD settings.
- No SQL database, Node runtime, Docker, React/Vue, or chart framework is required.

## 📟 OLED architecture

On YWD-Hotspot OS, **`ywd-headless-oled.service` is the sole SSD1306/I2C owner**.

The unified renderer in `lib/oled.py` provides runtime display behavior. The legacy `ywd-oled.service` remains disabled on YWD-Hotspot OS so two processes never write the same display concurrently.

Generic/non-OS installs may continue using `ywd-oled.service` because they do not have the headless OS owner.

The OLED renderer is deliberately passive. It may read local config/state and write the SSD1306, but it must not:

- start/stop RF
- change networking
- call BrandMeister APIs
- modify canonical configuration
- become a dependency of MMDVM-Host or DMRGateway

If the OLED process fails, DMR operation should continue normally.

## 🧭 OLED screen priority

The unified daemon uses state priority so operational/recovery information wins over cosmetic runtime pages:

1. shutdown/status-critical screen
2. first-boot setup/code
3. setup/recovery AP and network failure states
4. software-update progress
5. active RX/TX activity
6. short post-call hold
7. normal idle runtime pages

## 🎙️ OLED runtime modes

### Basic

Preserves the compact status layout.

### Enhanced

Uses a larger auto-fit callsign and configurable live DMR fields during RX/TX.

### Minimal

Prioritizes RX/TX direction, source callsign/DMR ID, and destination with reduced secondary information.

## 🔤 Callsign display

`large_callsign` enables scaled bitmap rendering. `callsign_size` can be:

- `auto`
- `normal`
- `large`
- `huge`

Auto-fit chooses the largest scale that fits the 128×64 panel rather than clipping long callsigns.

If MMDVM activity contains only a numeric DMR ID, the OLED may resolve it from the local RadioID cache. No Internet request is made by the OLED process.

## 📻 Destination / talkgroup display

The OLED can show group or private-call destinations. `talkgroup_format` supports:

- `number`
- `name`
- `name_number`

Talkgroup names are resolved only from existing local/cached data. If a name is unavailable, the numeric destination remains the fallback.

## 📊 Optional OLED live fields

The runtime display can independently show:

- slot
- elapsed call time
- BER
- RSSI when genuinely available
- network packet loss

Completed-call values may remain visible for `post_call_hold_s` seconds before the display returns to idle. An unavailable RSSI source should remain absent/blank rather than guessed.

## 🔄 Rotation

`display.rotation` supports `0` and `180` degrees. Rotation uses SSD1306 controller orientation commands rather than software-rotating every frame.

## 💤 Idle behavior

The existing brightness and display timeout settings remain supported.

Optional idle-page cycling can rotate through compact appliance information such as:

- callsign / RF / BrandMeister state
- Wi-Fi/IP/system status
- recent DMR activity

The cycle is disabled by default so the OLED can remain a stable status display.

## ⬆️ Software-update display

When the detached updater is active, the OLED may consume the sanitized local update-status file and show the update phase/progress. This is display-only; the OLED does not control the update.

The WebUI progress modal reconnects after the intentional dashboard restart. Brief browser connection-refused messages during that restart can be expected while the detached update continues outside the dashboard process.

## ⚙️ Canonical configuration

Display settings live under `display` in `/etc/ywd-hotspot/config.json`. Normalization/defaulting preserves older display settings as schema evolves.

Important defaults remain conservative:

```text
OLED runtime mode             basic
WebUI enhanced instruments    disabled
Instrumentation preset        basic
Instrument history mode       samples
Instrument history samples    20
Instrument sample max age     900 sec
Measurement hold              5 sec
Idle page cycling             disabled
Rotation                      0°
```

An update therefore keeps the lightweight presentation until the operator opts into enhanced modes.

---

**See also:** [📡 Telemetry](TELEMETRY.md) · [🧱 Architecture](ARCHITECTURE.md) · [🔄 Upgrading](UPGRADING.md)
