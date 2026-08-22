# YWD-Hotspot encrypted backup / restore

[← Docs index](README.md) · [Installation](INSTALL.md) · [SSH / SFTP](SSH.md) · [Upgrading](UPGRADING.md) · [Security](../SECURITY.md)

YWD-Hotspot provides a portable `.ywdsettings` format for rebuilding a hotspot after a fresh OS flash without manually re-entering the appliance configuration.

The design goal is:

```text
working hotspot
  -> EXPORT SETTINGS
  -> keep .ywdsettings + passphrase safe
  -> flash fresh YWD-Hotspot OS
  -> complete network onboarding
  -> RESTORE FROM .YWDSETTINGS BACKUP
  -> verify preview
  -> explicitly choose RF state
  -> restored appliance
```

## What a backup contains

The encrypted payload can contain:

- canonical `/etc/ywd-hotspot/config.json` configuration
  - callsign / DMR identity / ESSID
  - radio frequency, color code, offsets, levels, inversion and timing
  - BrandMeister master and Hotspot Security password
  - location / description / coordinates
  - display/OLED and WebUI instrumentation preferences
  - normal maintenance/config values
- BrandMeister API key, when configured
- the local WebUI authentication record, so the same control password can survive migration
- saved calibration baseline
- plugin master/per-plugin activation intent
- normalized plugin package-registration intent
- per-plugin configuration files
- trusted plugin publisher public keys
- optionally, the currently active Wi-Fi SSID/security profile when NetworkManager can read it

The backup deliberately excludes volatile appliance state such as logs, Last Heard, MMDVM telemetry/session history, update progress, diagnostics, downloaded caches and RadioID data.

### SSH state is deliberately separate

`.ywdsettings` v1 does **not** contain:

- SSH client private keys;
- `/home/ywd/.ssh/authorized_keys`;
- OpenSSH `ssh_host_*` server identity keys.

A newly flashed public image therefore returns to factory SSH state: disabled, port 22 closed, no client key authorized by YWD, and no reusable server identity shipped. After restoring normal YWD settings, create a new client login key and enable SSH from **SYSTEM -> SSH ACCESS** if needed.

The separate **EXPORT SERVER IDENTITY** action in the SSH card is recovery-only for preserving an SSH server fingerprint. It is not part of `.ywdsettings` and its archive contains unencrypted private server host keys. See **[SSH.md](SSH.md)**.

Uploaded `.ywdplugin` executable/package source is **not embedded** in `.ywdsettings` v1. If a backup refers to an uploaded plugin whose package is not present on the fresh OS, its configuration is preserved and the restore reports the missing package. Re-upload the package, then install/enable it as appropriate.

## Encryption and integrity

A `.ywdsettings` file is an authenticated encrypted envelope, not plaintext configuration.

The current `.ywdsettings` v1 format uses:

```text
passphrase
  -> scrypt (N=16384, r=8, p=1, random 16-byte salt)
  -> 64 bytes of key material
       first 32 bytes  -> AES-256-CBC encryption key
       second 32 bytes -> HMAC-SHA256 authentication key

random 16-byte IV
AES-256-CBC ciphertext
HMAC-SHA256 over canonical envelope header + ciphertext
```

The HMAC is verified before decryption. A wrong passphrase, modified ciphertext, modified KDF metadata or modified IV causes the whole import to fail before settings are applied.

The backup passphrase is not stored by YWD-Hotspot. If it is lost, the backup cannot be recovered.

> Normal YWD dashboard administration is HTTP for a trusted LAN. Export/import therefore protects the backup file at rest, but a passphrase entered through the normal dashboard still traverses the trusted LAN connection. The first-boot restore page uses the appliance's HTTPS setup service on port 8443.

## Export from an existing hotspot

Unlock WebUI controls, then open:

```text
SETTINGS -> BACKUP / RESTORE -> EXPORT SETTINGS
```

Enter and confirm a passphrase of at least 10 characters.

Optional:

```text
Include current Wi-Fi profile when available
```

The browser receives only the completed encrypted envelope and downloads a file similar to:

```text
KJ6YWD-ywd-hotspot-20260817-153000.ywdsettings
```

Keep both the file and its passphrase private.

## Import on an already configured hotspot

Unlock controls and choose:

```text
SETTINGS -> BACKUP / RESTORE -> IMPORT SETTINGS
```

The flow is deliberately two-phase:

1. choose the `.ywdsettings` file
2. enter the passphrase
3. **DECRYPT & VERIFY**
4. inspect a redacted preview
5. choose optional Wi-Fi-profile restore
6. explicitly choose whether RF may be started/enabled after restore
7. confirm with the YWD restore dialog
8. restore transactionally

The preview shows identity, source version/commit, RF frequency/color code, BrandMeister master, whether credentials are present, plugin counts, Wi-Fi inclusion and the old backup's RF-autostart intent. Secret values are not displayed.

The **Start RF after successful restore** checkbox always begins unchecked. The old backup's RF intent is informational only; every restored appliance requires a new explicit operator choice before RF starts or is enabled at boot.

## Fresh YWD-Hotspot OS restore

A factory image still starts with the existing network safety flow.

If no usable Wi-Fi profile exists on the new image:

```text
1. join YWD-Hotspot-XXXX
2. browse http://10.42.0.1/
3. select/enter Wi-Fi
4. the Pi hands wlan0 to station mode
5. OLED displays the six-digit secure setup code
6. browse https://<LAN-IP>:8443/
   (ywd-hotspot.local is optional when mDNS works)
```

The secure setup page then provides:

```text
RESTORE FROM .YWDSETTINGS BACKUP
```

The restore page still requires the six-digit OLED code. After it is unlocked:

1. select the backup
2. enter the backup passphrase
3. decrypt/authenticate it
4. inspect the redacted preview
5. optionally recreate included Wi-Fi as a saved profile
6. explicitly opt in to RF if desired
7. check the final restore confirmation box
8. press **RESTORE HOTSPOT**

A successful first-boot restore writes the normal setup-complete state and then shuts down the temporary setup service. The resulting dashboard uses the restored WebUI authentication record from the old hotspot.

SSH remains independent of that restore and stays off until explicitly configured from the dashboard.

### Why Wi-Fi onboarding still comes first

The existing OS architecture intentionally gives the network manager ownership of the temporary setup AP and does not expose the privileged appliance-restore service there. The current restore design keeps that boundary intact.

An included Wi-Fi profile is useful when importing on an already-running system or retaining another saved profile, but it does not currently eliminate the initial network-onboarding step on a completely blank image.

## Transaction and rollback behavior

Before applying an import, YWD creates a root-only snapshot under a path similar to:

```text
/var/backups/ywd-hotspot/pre-settings-restore-20260817T223000Z/
```

The protected snapshot covers the current canonical configuration, BM API key, WebUI authentication record, plugin state/package state, calibration baseline, setup state, plugin configs and trusted plugin keys.

Restore sequencing is intentionally conservative:

```text
authenticate/decrypt/validate entire backup
  -> snapshot old protected state
  -> force RF off
  -> quiesce plugins
  -> write validated core settings/secrets
  -> restore plugin config/package intent
  -> apply/regenerate core MMDVM/DMRGateway config
  -> restore eligible plugin runtime
  -> write first-boot completion state when applicable
  -> apply the explicit new RF policy
  -> optionally create a saved Wi-Fi profile without switching the live request
```

If a core restore step fails, YWD restores the protected files, reapplies the old core configuration and makes a best-effort reconstruction of the previous plugin and RF runtime policy. Ambiguous failures remain fail-closed rather than starting new RF/plugin activity.

## Plugin migration behavior

Backup state and package source are intentionally separate.

For each plugin referenced by a backup:

- package available on the target + previously installed -> registration can be restored
- previously enabled + master enabled + package still valid/installed -> activation can be restored
- package absent -> configuration is preserved and the package is reported missing
- package newly introduced by the target OS/update -> it is not enabled merely because it exists

Restoring a backup never downloads plugin code from the Internet.

## Support / recovery

After a restore, check:

```bash
ywd-hotspotctl status
ywd-hotspotctl source
systemctl --failed --no-pager
```

For plugin state:

```text
WebUI -> PLUGINS
```

For a failed restore, retain the protected `pre-settings-restore-*` snapshot and collect a normal sanitized YWD diagnostic bundle. Do not publish the protected snapshot; it can contain reusable credentials.
