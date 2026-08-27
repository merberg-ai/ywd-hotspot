# 🔄 Upgrading YWD-Hotspot

[← Docs index](README.md) · [Installation](INSTALL.md) · [Project README](../README.md) · [Security](../SECURITY.md)

> [!IMPORTANT]
> **Update invariant:** an application update must never unexpectedly enable RF or silently switch/recompile the selected MMDVM runtime.

## Managed layout

```text
/opt/ywd-hotspot/repo                  managed Git source
/opt/ywd-hotspot/app                   deployed runtime
/etc/ywd-hotspot/config.json           canonical hotspot config
/etc/ywd-hotspot/update-channel        persistent app update channel
/etc/ywd-hotspot/mmdvm-runtime.json    persistent MMDVM variant/capabilities
/etc/ywd-hotspot/mmdvm-build.json      MMDVM build provenance
/var/backups/ywd-hotspot/              protected pre-update backups
```

## Update channels

Persistent first-party channels are:

```text
main         promoted public/release line
dev          active integrated development
dev-plugins  plugin/runtime integration development
```

`main` is the normal public channel. `dev` and `dev-plugins` are development channels and may contain changes that have not completed a release-image acceptance cycle.

The dashboard's **CHANGE CHANNEL** UI exposes only the approved first-party channels above. Release/checkpoint refs remain engineering targets through the explicit CLI updater path.

```bash
ywd-hotspotctl update-channel
sudo ywd-hotspotctl update-channel main
sudo ywd-hotspotctl update-channel dev
```

## Current proven release transitions

Published updater acceptance now includes:

```text
0.2.0-rc1
  -> normal dashboard update
  -> 0.2.0-rc2
  -> reboot
  -> zero failed systemd units

0.2.0-rc2
  -> exact 0.2.0-rc3 application candidate
  -> protected normal updater
  -> no silent MMDVM/DMRGateway rebuild
  -> current/legacy runtime classification preserved correctly
  -> services healthy / zero failed units
```

Accepted RC3 source:

```text
v0.2.0-rc3
3823140b9fd4d6e73fe9066af4b2280628f62f5e
```

The separately built RC3 factory image also passed fresh-flash acceptance before publication.

## Check / dry-run / apply

```bash
sudo ywd-hotspotctl update --check
sudo ywd-hotspotctl update --dry-run
sudo ywd-hotspotctl update
```

The dashboard provides the same saved-channel update workflow when WebUI controls are unlocked.

## Candidate validation

Before live replacement, the updater verifies canonical origin, refuses dirty managed source, stages the target outside the live app, and runs capability-based validation/syntax checks.

A candidate containing plugin, passive-voice, telemetry, streamed RX audio, vocoder, software-channel, MODEM/MMDVM, startup-theme or MMDVM-runtime-variant pieces must contain the complete matching trusted runtime/UI set. Branch name is not used as a substitute for runtime coherence.

## MMDVM runtime preservation

Ordinary YWD application updates do **not** rebuild MMDVM-Host or DMRGateway. They preserve the operator's selected runtime:

```text
ywd-extended
upstream
```

The runtime choice is not inferred from the incoming application branch. Moving from one app version to another does not silently convert Stock Upstream to Extended or Extended to Stock.

Changing or refreshing MMDVM runtime is a separate explicit full/recovery/runtime-build action with its own verification and RF-safety handling.

## RC1/RC2 Extended runtime on RC3 application code

RC1/RC2 and RC3 use the same pinned upstream MMDVM-Host commit and YWD extension API 2, but the YWD patch generation changed.

Historical RC1/RC2 Extended patch:

```text
f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
```

Current RC3 Extended patch:

```text
77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994
```

The historical patch is explicitly recognized as **legacy-compatible YWD Extended** instead of being reported as unknown or silently rebuilt. It keeps its historical feature set but does not gain RC3-only demand-gated/current capability identity merely because the application code was updated.

Inspect exact runtime identity:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_runtime_state.py status
```

A recognized legacy Extended runtime reports its legacy generation plus `upgrade_required: true` when the current capability set is needed.

Refresh YWD Extended explicitly when desired:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py \
  install --mmdvm-variant ywd-extended

sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_runtime_state.py refresh
```

That rebuild/activation is an explicit operator action; the normal application updater never performs it silently.

Current RC3 release identity:

```text
MMDVM-Host upstream
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

YWD patch SHA256
  77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994

Extension API
  2

DMRGateway upstream
  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

## Plugin behavior across updates

Uploaded package source, config/data and trusted publisher public keys live outside the deployed app. Before replacement, service plugins are made inert. After replacement, only packages that still validate and satisfy current requirements are eligible for restoration.

Requirement checks resolve against the exact installed MMDVM runtime metadata. A recognized legacy Extended runtime receives a specific runtime-refresh requirement instead of accidentally satisfying the current capability generation or failing as an unidentified binary.

A previously enabled extension-dependent plugin also does not get blindly restarted on an incompatible Stock runtime.

## RF behavior

The updater captures/restores explicit service policy. Examples:

| Before | After |
|---|---|
| RF stopped + disabled | remains stopped + disabled |
| RF running + enabled | restarted only as needed; enabled policy restored |
| dashboard stopped | does not imply permission to start RF |

Verify after an update:

```bash
ywd-hotspotctl status
ywd-hotspotctl source
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py status
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_runtime_state.py status
systemctl --failed --no-pager
```

## OLED ownership

YWD-Hotspot OS keeps `ywd-headless-oled.service` as the authoritative physical display owner. Generic installs may use `ywd-oled.service`. Update paths preserve that split.

## Existing install -> GitHub management

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./MIGRATE-TO-GITHUB.sh
```

Migration preserves configuration, credentials, plugin state, RF policy and the installed MMDVM runtime; it does not rebuild radio binaries.

## Recovery

Protected pre-update backups are stored under `/var/backups/ywd-hotspot/`. They may contain reusable credentials and must remain private.

For a failed detached update:

```bash
sudo cat /var/lib/ywd-hotspot/update-status.json
sudo journalctl -u ywd-update.service -n 150 --no-pager
```

Do not blindly reset a dirty managed checkout; inspect it first.

## Provenance

```bash
ywd-hotspotctl source
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py status
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_runtime_state.py status
```

Application provenance and MMDVM runtime provenance are deliberately separate, so an application update cannot disguise a radio-runtime change.

See **[REPOSITORY.md](REPOSITORY.md)** for current branch/release policy and **[history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md](history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md)** for final RC3 acceptance evidence.
