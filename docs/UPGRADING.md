# 🔄 Upgrading YWD-Hotspot

[← Docs index](README.md) · [Installation](INSTALL.md) · [Project README](../README.md) · [Security](../SECURITY.md)

---

> [!IMPORTANT]
> **Update invariant:** an update must never unexpectedly enable RF.

Normal YWD application updates do **not** rebuild the pinned MMDVM-Host or DMRGateway binaries.

## Managed layout

```text
/opt/ywd-hotspot/repo    root-owned managed Git checkout
/opt/ywd-hotspot/app     deployed runtime copy; no .git directory
/etc/ywd-hotspot         canonical config + build provenance
/var/backups/ywd-hotspot protected pre-update backups
```

The live runtime is deliberately separated from Git/network activity.

## Update channels

YWD-Hotspot currently recognizes three first-party channels:

| Channel | Purpose |
|---|---|
| `main` | promoted/conservative project line |
| `dev` | physically accepted integrated development baseline |
| `dev-plugins` | next-development / experimental integration line |

Show or change the saved channel:

```bash
ywd-hotspotctl update-channel
sudo ywd-hotspotctl update-channel main
sudo ywd-hotspotctl update-channel dev
sudo ywd-hotspotctl update-channel dev-plugins
```

A successful explicit branch update to one of those branches becomes the saved channel. Updating to a specific tag does **not** change the saved channel.

Channel file:

```text
/etc/ywd-hotspot/update-channel
```

## About-page updater

On GitHub-managed installs, the About page exposes software-update controls when WebUI controls are unlocked.

The browser can:

1. check the saved channel;
2. show current and candidate version/commit;
3. refuse installation when canonical config has saved-but-not-applied changes;
4. request an update through the narrow authenticated admin action;
5. display stage-driven update progress;
6. reconnect after the dashboard restarts.

The browser does **not** pass arbitrary branch names, URLs, filesystem paths, or shell commands to root.

The actual install runs as the detached one-shot service:

```text
ywd-update.service
```

## Check or dry-run

```bash
sudo ywd-hotspotctl update --check
sudo ywd-hotspotctl update --dry-run
```

A dry run fetches and stages the candidate outside the live application, performs required-file and syntax checks, and exits without replacing the runtime or changing RF/service state.

### Capability-based candidate validation

Candidate safety is based on the runtime capabilities actually present in the staged tree, not merely on its branch name.

For example, if a candidate contains the Plugin UI/package-update runtime, the validator requires the complete matching plugin/admin/UI/sandbox set. If it contains the passive DMR voice runtime, the bridge/build/service pieces must all be present. Telemetry receives the same coherence check.

This matters after promotion: a plugin-capable `dev` or future `main` receives the same validation previously associated only with `dev-plugins`.

## Apply an update

Follow the saved channel:

```bash
sudo ywd-hotspotctl update
```

Or use **ABOUT → SOFTWARE UPDATE → INSTALL UPDATE**.

Explicit branch/tag examples:

```bash
sudo ywd-hotspotctl update --branch main
sudo ywd-hotspotctl update --branch dev
sudo ywd-hotspotctl update --branch dev-plugins
sudo ywd-hotspotctl update --tag <checkpoint-or-release-tag>
```

## What the updater protects

`GITHUB-UPDATE.sh` handles source/network work first while the current hotspot keeps running:

1. acquires the update lock;
2. verifies the managed checkout and canonical repository origin;
3. refuses local content modifications;
4. fetches branches/tags;
5. resolves the selected target commit/version;
6. stages the candidate outside the live app;
7. validates candidate runtime coherence and syntax;
8. calls the transactional application updater;
9. advances the managed checkout only after successful deployment.

The incoming `UPDATE.sh` repeats the capability/source preflight **before** it quiesces plugin services or touches live service/config state.

`UPDATE.sh` / `UPDATE-core.sh` then:

- capture active/enabled service policy;
- capture plugin activation/runtime intent;
- create protected config/app backups;
- quiesce plugin services for replacement;
- deploy the new YWD application layer;
- reinstall CLI/admin/sudoers/systemd pieces;
- migrate/normalize canonical config;
- regenerate radio INIs;
- write build provenance;
- preserve RF autostart policy;
- reconcile previously valid plugin state;
- restart only services that are supposed to come back;
- restore exact RF enabled/disabled policy.

## Plugin behavior across application updates

Uploaded package source, plugin config/data, and trusted publisher **public** keys live outside `/opt/ywd-hotspot/app`, so ordinary application replacement does not delete them.

Before replacement, service plugins are made inert. After replacement, only previously installed/enabled packages that still validate against the new runtime are eligible for restoration. UI-only plugins participate in activation reconciliation but have no Pi-side process to stop.

Newly discovered packages never auto-enable.

## In-place `.ywdplugin` updates

Plugin package replacement is separate from a YWD application update.

When a newly uploaded `.ywdplugin` has the same plugin ID as an installed uploaded package, Plugin Manager verifies/reviews the candidate and classifies it as an update, reinstall, downgrade, or replacement as appropriate. A confirmed update preserves config/data and prior installed/enabled intent, performs an atomic package swap, and rolls back the old package/state if the transaction fails.

Executable UI/service replacement still requires valid trusted signing provenance and cannot silently change plugin kind or inherit arbitrary new privileges.

See **[PLUGIN-PACKAGES.md](PLUGIN-PACKAGES.md)**.

## RF behavior

Examples:

| Before update | After update |
|---|---|
| RF stopped + disabled | remains stopped + disabled |
| RF running + enabled | restarted only as required, then enabled policy restored |
| dashboard stopped | update does not treat that as permission to start RF |

Always verify afterward:

```bash
ywd-hotspotctl status
```

## OLED ownership

YWD-Hotspot OS keeps `ywd-headless-oled.service` as the sole SSD1306/I2C owner. Generic installations use `ywd-oled.service`. Update/config paths preserve that ownership split so two renderers are not intentionally active against the same display.

## Existing archive install → GitHub management

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./MIGRATE-TO-GITHUB.sh
```

Migration adopts the promoted `main` line first and does **not** rebuild the RF binaries. Switch to `dev` afterward only if desired.

## Recovery and rollback

Before live application replacement, a protected backup is created under a path similar to:

```text
/var/backups/ywd-hotspot/pre-VERSION-YYYYMMDD-HHMMSS/
```

It contains previous application/config state. Configuration backups can contain reusable credentials and must remain private.

If runtime replacement fails, the updater attempts to restore the prior application/configuration, repair the trusted admin bridge, and restore prior plugin/RF service policy.

For a failed WebUI update:

```bash
sudo cat /var/lib/ywd-hotspot/update-status.json
sudo journalctl -u ywd-update.service -n 150 --no-pager
```

### Dirty managed checkout

The updater intentionally refuses content changes in:

```bash
git -C /opt/ywd-hotspot/repo status --short
```

Do not `git reset --hard` blindly. Runtime configuration belongs under `/etc/ywd-hotspot` and `/var/lib/ywd-hotspot`, not in the managed checkout.

### Legacy single-branch checkout

Early appliance images could have a restricted single-branch refspec. Current source-management wrappers widen a verified canonical checkout so first-party update channels can be fetched before target resolution.

## Build/source information

```bash
ywd-hotspotctl source
```

The same provenance appears in the WebUI header/About page and is stored without secrets in:

```text
/etc/ywd-hotspot/build-info.json
```

## Manual development apply

A clean development checkout can still be applied manually:

```bash
cd ~/ywd-hotspot
git pull --ff-only
sudo ./UPDATE.sh
```

Normal appliances should prefer `ywd-hotspotctl update` so canonical-origin checks, candidate staging, saved-channel behavior, provenance, and managed-checkout finalization stay in the loop.

## Upstream RF pins

Do not move `pins.env` during unrelated UI/docs/plugin work merely because newer upstream commits exist. An upstream RF-stack pin change alters the calibration/stability baseline and deserves its own regression-test build.
