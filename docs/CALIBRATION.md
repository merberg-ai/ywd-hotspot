# 🧪 DMR Calibration

[← Docs index](README.md) · [Project README](../README.md) · [Display](DISPLAY.md) · [Telemetry](TELEMETRY.md) · [Architecture](ARCHITECTURE.md)

---

The calibration workflow is designed around one rule:

> **Change one variable at a time and use repeatable transmissions.**

Randomly sweeping RXOffset, TXOffset, and levels together produces impressive-looking numbers and useless conclusions.

## 🎯 Current baseline

Before testing, preserve the current known baseline:

```text
RXOffset = 0 Hz
TXOffset = 0 Hz
RXLevel  = 50%
TXLevel  = 50%
RFLevel  = 100%
TXInvert = 1
RXInvert = 0
```

Use **SAVE CALIBRATION BASELINE** before changing values.

## 📥 RX comes first

The hotspot can objectively measure RF BER for:

```text
HT → hotspot
```

That makes **RXOffset** the first calibration target.

Recommended setup:

- use BrandMeister Parrot for repeatable voice tests;
- keep the handheld on low power;
- keep distance/orientation/location unchanged between runs;
- use several similar 5–10 second transmissions per offset;
- avoid touching RXLevel until RXOffset behavior is understood.

## 📊 Sample rule

Recorded calls are grouped by RXOffset and summarized with the measurements actually available, including:

```text
sample count
average BER
best BER
average RSSI (only when supplied by modem firmware)
```

A single low-BER call is not enough to produce an apply recommendation.

Current threshold:

```text
3 samples per RX offset
```

Until an offset has enough samples, the UI can show a provisional best but should not treat it as the supported recommendation.

The ranking uses lowest **average BER** first. Sample count and distance from zero are tie-breakers; RSSI is context rather than the optimization target.

## RSSI is optional

A compatible MMDVM HAT can operate normally and report useful BER while its firmware provides no usable RSSI. The `0.2.0-rc1` reference duplex HAT behaved exactly that way: RF/Parrot/BER worked, but RSSI values were zero/unavailable.

Therefore:

- calibration does **not** require RSSI;
- missing RSSI does not invalidate a BER sample;
- BER remains the primary objective receive-quality measurement;
- YWD does not estimate dBm from BER;
- any RSSI column/average should be treated as optional context.

If your modem firmware does provide real RSSI, use it to detect obvious receive-level/environment changes between runs—not as a substitute for BER optimization.

## 🧭 Controlled RXOffset sequence

1. Save the calibration baseline.
2. Start a new calibration session.
3. Record at least three similar Parrot transmissions at RXOffset `0`.
4. Note average BER, best BER, and RSSI only if available.
5. Change **only RXOffset** by a controlled step.
6. Repeat the same number/approximate duration of transmissions.
7. Compare average BER across repeated samples.
8. Continue around the improving region until the minimum is bracketed.
9. Confirm the apparent best region with additional repeated tests.
10. Use **USE BEST RX OFFSET** only after enough samples support the recommendation.
11. Consider RXLevel only afterward if BER is still poor.

Quick controls include ±100, ±250, and ±500 Hz changes. Each change uses the normal configuration/apply path and restarts only the active RF stack as required.

## ✅ Manual confirmation remains mandatory

YWD-Hotspot does not silently tune the modem.

When **USE BEST RX OFFSET** becomes available, the UI shows the recommended offset, sample count, and average BER. Applying it requires explicit confirmation and uses the normal config-save/config-apply path.

There is deliberately no automatic TX recommendation because the hotspot cannot measure the handheld receiver's BER.

## 💻 CLI summary

```bash
ywd-hotspotctl calibration
```

The command may transparently request sudo because calibration/config data lives in protected appliance paths.

On RSSI-capable firmware a summary may look like:

```text
RX OFFSET    N   AVG BER   BEST BER   AVG RSSI
      -250    3    0.700%     0.300%      -53.0
         0    3    2.100%     1.600%      -53.0
```

On firmware without usable RSSI, the RSSI value may be blank/unavailable while BER statistics remain valid.

## 📤 Export results

Calibration exports do not contain the BrandMeister password, API key, or WebUI control password.

CLI:

```bash
sudo ywd-hotspotctl calibration export json > calibration.json
sudo ywd-hotspotctl calibration export csv  > calibration.csv
```

The WebUI also provides **EXPORT JSON** and **EXPORT CSV**.

- JSON: raw samples + aggregate groups + recommendation metadata;
- CSV: individual recorded samples for external analysis.

## 📶 RSSI vs BER

When present, RSSI is useful context. BER is the primary objective receive-quality measurement for this workflow.

A strong-looking RSSI does not automatically mean modem slicing/offset is optimal, and an unavailable RSSI does not mean DMR receive quality is unknown when BER is available.

## 🎚️ RXLevel

Do not tune RXLevel merely because the control exists.

First establish a repeatable RXOffset minimum. If BER remains unacceptable or behavior suggests a level/slicer problem, change RXLevel separately and repeat the same controlled procedure.

## 📤 TX calibration is different

The hotspot cannot directly measure the handheld's receive BER for:

```text
hotspot → HT
```

TXOffset/TXLevel therefore require evidence from the receiving side, such as:

- a handheld that exposes useful BER/error information;
- a second suitable receiver/instrument;
- carefully controlled subjective playback when no better measurement exists.

Do not mix TX conclusions into the RX BER table.

## 🛡️ Stability during calibration

Keep RF tests controlled, especially on compact Pi Zero/HAT builds:

- use the HT at low power;
- initially keep some physical separation from the Pi/HAT;
- keep a ping running if practical;
- watch uptime/temperature/throttling;
- if the Pi reboots, inspect the previous persistent journal before continuing.

Useful commands:

```bash
uptime
ping PI-IP
sudo journalctl --list-boots
sudo journalctl -b -1 -e
sudo journalctl -b -1 -k -e
vcgencmd get_throttled
```

If a test gets weird, restore the saved calibration baseline rather than trying to reconstruct which variables changed.
