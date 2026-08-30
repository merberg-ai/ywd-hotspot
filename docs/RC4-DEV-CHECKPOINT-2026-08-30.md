# RC4 development checkpoint — 2026-08-30

This checkpoint records the first YWD-Hotspot `0.2.0-rc4` hardening pass on the canonical `dev` line. `VERSION` intentionally remains `0.2.0-rc3` until the RC4 candidate is frozen.

## Hardware acceptance completed

The mature Raspberry Pi Zero hotspot was updated from the integrated `dev` line and physically tested with the normal RF stack running.

Accepted results:

- BrandMeister Parrot passed.
- TGIF Parrot passed.
- MMDVMHost, DMRGateway, dashboard, and activity services remained active.
- zero failed systemd units.
- Save & Apply completed with no unintended service restart when configuration was unchanged.
- generated `MMDVM-Host.ini` references the persistent RSSI map at `/etc/ywd-hotspot/mmdvm-hs-rssi.dat`.
- the installed INI contains no `/tmp/ywd-config-*` RSSI path.
- RSSI map ownership/mode is suitable for the appliance runtime (`root:ywd-hotspot`, `0640`).
- YWD-Hotspot OS uses `ywd-headless-oled.service` as the authoritative OLED owner; legacy `ywd-oled.service` remains inactive.
- OLED runtime health reported `state=open`, `device_open=true`, bus `1`, address `0x3c`, and no error.
- `/api/status` and `/api/health` agree on the authoritative OLED owner after removing the stale dashboard owner cache.
- the consolidated RC4 hardening smoke passed on the mature Pi Zero, including RSSI, source-install OLED/I2C, truthful OLED health, SSH policy, encrypted TGIF/BM backup round trip, TGIF regressions, and plugin restore/runtime regressions.

## Live SSH policy acceptance

The mature appliance reports a managed, active SSH service with the expected existing normal account and password-or-key policy:

```text
active                  true
enabled_at_boot         true
port                    22
auth_mode               password+key
password_authentication true
root_login              false
policy_managed          true
login_user              ywd
login_user_exists       true
password_status         set
authorized_key_count    7
```

Effective `sshd -T` policy on the appliance:

```text
permitrootlogin no
pubkeyauthentication yes
passwordauthentication yes
kbdinteractiveauthentication no
permitemptypasswords no
allowusers ywd
authenticationmethods any
```

`authenticationmethods any` is expected for password-or-key mode: no extra multi-factor method chain is imposed, while the explicitly enabled password and public-key mechanisms remain available and keyboard-interactive/root login remain disabled.

Client-side physical acceptance is complete:

- a fresh forced password-authentication SSH login to `ywd` succeeded;
- a fresh forced public-key SSH login to `ywd` succeeded;
- the existing administrative session remained usable throughout testing.

The source-only SSH smoke separately verifies the key-only contract. Live password-or-key SSH acceptance is therefore closed for RC4 unless a later regression is observed.

## Real encrypted settings restore acceptance

A real `.ywdsettings` export/import was exercised on the mature Pi Zero, not merely the source-only crypto smoke.

Baseline state before export included:

```text
station description   YWD Hotspot RC3
RF autostart          true
BrandMeister          enabled / connected
TGIF                  enabled / connected
plugin master         enabled
enabled plugins       dmr-contact-intelligence, dmr-rx-monitor
installed plugins     dmr-contact-intelligence, dmr-rx-monitor
SSH                   active, password+key, 7 authorized keys
failed systemd units  0
```

The live appliance recorded SHA-256 fingerprints for the BrandMeister and TGIF passwords without printing either secret. The encrypted settings file exported successfully.

To prove the restore actually replaced live state, the operator deliberately changed only safe visible/plugin state:

- station description changed from `YWD Hotspot RC3` to an RC4 restore mutation marker;
- `dmr-contact-intelligence` was disabled while `dmr-rx-monitor` and the plugin master remained enabled;
- BrandMeister and TGIF credentials were left untouched.

The mutation was confirmed before restore: canonical config hash changed, Contact Intelligence disappeared from the enabled set, both network secret fingerprints remained unchanged, both networks remained connected, and there were zero failed units.

The exported `.ywdsettings` file was then imported with explicit RF restart/autostart approval. Post-restore acceptance passed every comparison:

```text
[OK] canonical config
[OK] description
[OK] RF autostart
[OK] BM enabled
[OK] BM master
[OK] BM password fingerprint
[OK] TGIF enabled
[OK] TGIF master
[OK] TGIF port
[OK] TGIF password fingerprint
[OK] plugin master
[OK] enabled plugins
[OK] installed plugins
[OK] plugin configs
```

Runtime after restore:

```text
Restored description  YWD Hotspot RC3
Enabled plugins       dmr-contact-intelligence, dmr-rx-monitor
Installed plugins     dmr-contact-intelligence, dmr-rx-monitor
BrandMeister          connected
TGIF                  connected
MMDVMHost             active
DMRGateway            active
SSH active            true
SSH boot enabled      true
SSH auth mode         password+key
SSH login user        ywd
SSH authorized keys   7
failed systemd units  0
```

This closes the real encrypted settings preservation gate for canonical configuration, BrandMeister, TGIF, plugin intent/config, RF policy, and the intentionally independent SSH state.

## Normal GitHub update preservation acceptance

A real normal GitHub update was exercised on the same mature Pi Zero after the restore acceptance. This was not an `up to date` no-op: the installed source advanced from:

```text
bed5123ef5dcf6a68ef9aa7ab685ca32e5265acf
```

to:

```text
0aca740cba6b89b8b9a69d29d8738c43d7b861a6
```

Before the update the appliance recorded fingerprints/state for canonical config, BrandMeister/TGIF passwords, plugin state/configuration, SSH managed policy, `authorized_keys`, SSH host public identities, Linux password state, and RF active/boot policy.

Post-update comparison passed every preservation check:

```text
[OK] canonical config
[OK] BM enabled
[OK] BM master
[OK] BM password
[OK] TGIF enabled
[OK] TGIF master
[OK] TGIF port
[OK] TGIF password
[OK] plugin master
[OK] enabled plugins
[OK] installed plugins
[OK] plugin configs
[OK] SSH managed policy
[OK] SSH authorized keys
[OK] SSH host identity
[OK] SSH password state
[OK] SSH active
[OK] SSH boot enabled
[OK] MMDVM active
[OK] DMRGateway active
[OK] MMDVM boot policy
[OK] DMRGateway boot policy
```

Runtime after the update remained healthy:

```text
BrandMeister  connected
TGIF          connected
MMDVMHost     active
DMRGateway    active
OLED          active
OLED owner    ywd-headless-oled.service
SSH           password+key; ywd only; root/interactive/empty-password disabled
failed units  0
```

This closes the normal GitHub updater state-preservation gate for RC4. It does not replace the later published `0.2.0-rc3` -> frozen `0.2.0-rc4` release-updater acceptance, which must use the final frozen candidate.

## RC4 hardening implemented

### Persistent RSSI mapping

Save & Apply may stage candidate INI files under `/tmp/ywd-config-*`, but the installed MMDVM configuration must always reference persistent appliance state. RC4 keeps `RSSIMappingFile` at:

```text
/etc/ywd-hotspot/mmdvm-hs-rssi.dat
```

The regression suite fails if the final generated MMDVM INI leaks a temporary staging path.

### Source-install I2C / OLED behavior

Generic/source installation now treats I2C enablement and OLED detection separately:

- Raspberry Pi boot configuration is enabled for I2C when required.
- a newly enabled controller is reported as requiring reboot rather than misdiagnosed as failed hardware.
- OLED probing uses the configured I2C bus.
- SSD1306 addresses `0x3c` and `0x3d` are accepted.
- an alternate detected address can be persisted to canonical configuration.
- OLED failure never controls RF state.

Factory-image I2C enablement remains owned by the pi-gen image stage and is not duplicated by runtime hacks.

### Truthful OLED health

The OLED renderer publishes bounded runtime health including:

```text
opening
open
waiting-for-device
io-error
runtime-error
disabled
stopping
```

Dashboard health combines the renderer's device-open report with the authoritative systemd owner. A process that is alive but retrying failed I2C access is no longer presented as healthy hardware.

## Source-only RC4 hardening gate

`tools/rc4-hardening-smoke.py` consolidates the non-RF regression set. At this checkpoint it covers:

- persistent RSSI mapping;
- source-install I2C/OLED behavior;
- OLED device-open/status projection;
- SSH key-only and password-or-key policy contract;
- encrypted TGIF/BrandMeister settings backup round trip;
- TGIF routing/UI/status/directory behavior;
- plugin settings restore and feature-runtime behavior.

The smoke is intentionally read-only with respect to the managed source checkout and live hotspot configuration.

## Next RC4 gates

Before RC4 freeze/publication:

1. complete the additional planned RC4 feature/UI work;
2. freeze the candidate and only then change `VERSION` to `0.2.0-rc4`;
3. test the published RC3 -> frozen RC4 updater path;
4. build and physically accept the exact RC4 factory image before publication.

Do not expand TGIF routing semantics, rebuild MMDVM-Host/DMRGateway, or modify the proven RF routing path merely as part of this hardening checkpoint.
