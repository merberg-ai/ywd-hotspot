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
main   promoted public/release line
dev    development/preview line
```

`main` is the normal public channel. While releases are frozen it stays at the exact accepted public commit so stable testers do not receive unpublished development work.

`dev` may move ahead of `main` and should be treated as a development channel; a `dev` commit is not automatically hardware-accepted merely because it exists.

Temporary release/checkpoint/feature refs are explicit test targets, not persistent channels.

```bash
ywd-hotspotctl update-channel
sudo ywd-hotspotctl update-channel main
sudo ywd-hotspotctl update-channel dev
```

## Current proven transition

`0.2.0-rc2` established the first published-image updater proof:

```text
0.2.0-rc1
  -> normal dashboard update on main
  -> 0.2.0-rc2
  -> clean managed source
  -> reboot
  -> zero failed systemd units
```

Accepted RC2 source:

```text
5f0d2967ce0ed728169f7819d2bc227687d6a9b2
```

RC3 acceptance will separately prove both the fresh-image path and the published RC2 -> RC3 application-update path.

## Check / dry-run / apply

```bash
sudo ywd-hotspotctl update --check
sudo ywd-hotspotctl update --dry-run
sudo ywd-hotspotctl update
```

The dashboard provides the same saved-channel update workflow when WebUI controls are unlocked.

## Candidate validation

Before live replacement, the updater verifies canonical origin, refuses dirty managed source, stages the target outside the live app, and runs capability-based validation/syntax checks.

A candidate containing plugin, passive-voice, telemetry, streamed RX audio, vocoder, or MMDVM-runtime-variant pieces must contain the complete matching trusted runtime set. Branch name is not used as a substitute for runtime coherence.

## MMDVM runtime preservation

Ordinary YWD application updates do **not** rebuild MMDVM-Host or DMRGateway. They preserve the operator's selected runtime:

```text
ywd-extended
upstream
```

The runtime choice is not inferred from the incoming application branch. Moving from one app version to another does not silently convert Stock Upstream to Extended or Extended to Stock.

Changing or refreshing MMDVM runtime is a separate explicit full/recovery/runtime-build action with its own verification and RF-safety handling.

### RC2 Extended runtime on RC3 application code

RC1/RC2 and current RC3 development use the same pinned upstream MMDVM-Host commit and YWD extension API 2, but the YWD patch generation changed.

The accepted RC1/RC2 Extended patch publishes the same passive `DMRVoice` envelope used by current core, but it predates the `YWD_DMR_VOICE_TAP=1` demand gate. Current RC3 development therefore recognizes that exact historical patch as **legacy-compatible YWD Extended** instead of reporting an unknown runtime.

A legacy RC2 Extended runtime retains its older capabilities:

```text
passive-dmr-voice
plugin-rx-monitor
```

It intentionally does **not** receive:

```text
demand-gated-dmr-voice
```

A plugin requiring the demand-gated capability, including the current streamed-audio RX Monitor candidate, remains blocked until the operator explicitly refreshes YWD Extended.

Inspect exact runtime identity:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_runtime_state.py status
```

A recognized RC1/RC2 Extended binary reports `runtime_generation: legacy`, `upgrade_required: true`, and the explicit refresh command rather than being misclassified as unknown.

Refresh YWD Extended when desired:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py \
  install --mmdvm-variant ywd-extended

sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_runtime_state.py refresh
```

That rebuild/activation is an explicit operator action; the normal application updater never performs it silently.

## Plugin behavior across updates

Uploaded package source, config/data and trusted publisher public keys live outside the deployed app. Before replacement, service plugins are made inert. After replacement, only packages that still validate and satisfy current requirements are eligible for restoration.

MMDVM requirement tokens include:

```text
mmdvm-ywd-extended
mmdvm-extension-api-2
mmdvm-cap-passive-dmr-voice
mmdvm-cap-demand-gated-dmr-voice
```

Control-plane plugin mutations verify the exact installed MMDVM binary/patch identity. A recognized legacy Extended runtime therefore receives a specific runtime-refresh requirement instead of accidentally satisfying the newer capability or failing as an unidentified binary.

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

See **[REPOSITORY.md](REPOSITORY.md)** for the current release-freeze and branch-promotion policy.
