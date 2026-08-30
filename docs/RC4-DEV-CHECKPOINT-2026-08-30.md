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

The source-only SSH smoke also verifies the separate key-only contract. A final client-side acceptance can exercise one fresh password login and one fresh key login from a second terminal while preserving the current administrative session.

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

Before RC4 freeze:

1. optionally complete client-side SSH acceptance with one fresh password login and one fresh public-key login from a second terminal;
2. perform a real encrypted settings export/preview/restore preservation test covering TGIF, BrandMeister, and installed plugin intent;
3. verify normal update preserves SSH/config/plugin/network state;
4. complete the additional planned RC4 feature/UI work;
5. freeze the candidate and only then change `VERSION` to `0.2.0-rc4`;
6. test the published RC3 -> frozen RC4 updater path;
7. build and physically accept the exact RC4 factory image before publication.

Do not expand TGIF routing semantics, rebuild MMDVM-Host/DMRGateway, or modify the proven RF routing path merely as part of this hardening checkpoint.
