# RC4 change list

This file tracks the additional changes selected for YWD-Hotspot `0.2.0-rc4` after the appliance-hardening acceptance checkpoint.

## Baseline / rules

- Canonical development branch: `dev`.
- RC4 hardening checkpoint before this list: `b6198635b8cd6e3d0fbf365161597b0fb4605f66`.
- Synchronized implementation baseline for `dev` + `dev-plugins`: `79b1afc4a984ee06008f22d50622f6f350910683`.
- `VERSION` intentionally remains `0.2.0-rc3` until the RC4 candidate is frozen.
- `main` remains the public/known-good RC3 line until final RC4 acceptance.
- Do not rebuild or repin MMDVM-Host/DMRGateway for these presentation/UI changes.
- Do not change proven BrandMeister/TGIF routing semantics merely to satisfy presentation work.
- The five-item list below was agreed before implementation began.

## RC4 changes — implemented on `dev`, awaiting appliance acceptance

### 1. Bring system/login/update presentation up to date with TGIF support

The appliance still had presentation surfaces that reflected the older BrandMeister-only network model.

Implemented scope:

- `/etc/issue` authoritative YWD branding template;
- `/etc/motd` authoritative YWD branding template;
- GitHub updater banner/status text;
- console-help first-boot wording;
- normal branding ownership remains centralized through `lib/system_branding.sh` so updates and installs use the same templates.

Acceptance intent:

- BrandMeister and TGIF are represented as supported integrated networks where the surface describes network capability;
- no credentials are exposed;
- login/update presentation remains concise and readable on Pi Zero terminals;
- source install, update, and factory-image paths do not drift from one another.

### 2. Show TGIF in the Confirm Import Settings / restore preview

The encrypted `.ywdsettings` payload already preserved TGIF configuration and credentials, and live restore acceptance had passed. The human-readable confirmation/preview now has TGIF parity with BrandMeister.

Implemented redacted preview fields:

- TGIF enabled/disabled;
- TGIF master/host;
- TGIF port;
- TGIF password configured: yes/no only.

The same network intent is shown by the normal WebUI restore flow and the first-boot restore page.

Rules retained:

- never display the TGIF password itself;
- preserve existing BrandMeister preview behavior;
- keep preview read-only and redacted;
- do not change the `.ywdsettings` format or restore transaction semantics.

### 3. Use plain HTTP for the first-time setup portal

RC3 field testing showed that the first-time setup portal's self-signed TLS behavior created a disproportionate usability problem. Browsers could refuse, block, or heavily discourage access to the page required to configure the device.

Implemented behavior:

- first-boot setup remains on setup port `8443` but is served as ordinary HTTP;
- runtime/setup URLs use `http://...:8443/`;
- the setup-only TLS certificate generation/socket wrapping was removed;
- the setup session cookie remains `HttpOnly` + `SameSite=Strict` but no longer carries the incompatible `Secure` flag on HTTP;
- the six-digit OLED physical-access code, timeout, rate limiting, same-origin protection, and RF-off safety gate remain in place;
- first-boot restore uses the same HTTP listener/security model;
- the factory-image stage no longer creates obsolete `setup-tls` state and its shipped safety text points to the HTTP setup URL.

This change is intentionally limited to first-time provisioning. It does not redesign normal post-setup WebUI authentication or the previously accepted SSH policy.

### 4. Add optional TGIF configuration to first-time setup

TGIF is now a first-class optional network in the first-boot wizard.

Implemented behavior:

- `Enable TGIF` choice/toggle;
- when disabled, TGIF-specific fields remain hidden/inactive and TGIF stays disabled;
- when enabled, the wizard presents:
  - master/host;
  - port;
  - masked TGIF security password;
- defaults reuse the canonical TGIF values (`tgif.network`, port `62031`);
- privileged setup injects the TGIF password into the canonical candidate before normal `config_model` validation;
- enabled TGIF requires a password;
- passwords are never echoed in setup review/restore preview text;
- BrandMeister and TGIF remain independently configurable using the already-proven integrated routing model.

### 5. Make Digital Waterfall the stronger/default loading animation

The Digital Waterfall startup animation was revised to look more like an SDR display with a clearly visible strong on-frequency transmission.

Implemented visual direction:

- top spectrum pane with a strong center peak;
- centered VFO/reference line;
- deep-blue scrolling waterfall/noise floor;
- broad high-energy center signal with blue/cyan/yellow/white intensity;
- bright narrow center core plus weaker side activity;
- lightweight SVG/CSS implementation suitable for the Pi Zero dashboard;
- reduced-motion behavior retained.

Default policy:

- `digital_waterfall` is now the canonical default for fresh/missing configuration;
- the browser theme engine uses the same default;
- an existing explicit theme choice such as `rf_sweep` remains preserved rather than being silently migrated.

## Source regression gate for this batch

`tools/rc4-ui-setup-smoke.py` verifies, without touching live appliance state:

- integrated BrandMeister + TGIF branding/update presentation;
- HTTP-only setup/restore source policy with no self-signed TLS socket path;
- factory-image HTTP setup ownership/instructions;
- optional TGIF first-boot fields and privileged validation;
- TGIF redacted restore previews;
- fresh Digital Waterfall default plus preservation of explicit existing theme choices;
- strong centered waterfall markup/styling.

The existing encrypted backup smoke now also validates TGIF preview redaction, and the startup-theme config smoke has been updated for the new default. The consolidated `tools/rc4-hardening-smoke.py` includes these checks.

## Completed RC4 hardening gates before this feature/UI batch

- persistent RSSI mapping: accepted;
- source-install I2C/OLED handling: accepted;
- truthful OLED health/status: accepted;
- BrandMeister + TGIF live RF regression: accepted;
- SSH password-or-key policy and live password/key login: accepted;
- encrypted settings crypto round trip: accepted;
- real `.ywdsettings` export/import preservation: accepted;
- plugin restore/config preservation: accepted;
- normal GitHub updater state preservation: accepted;
- zero failed systemd units through final hardening acceptance tests.

## Remaining acceptance for this batch

1. Run the expanded RC4 source smoke on the mature Pi Zero after updating to current `dev`.
2. Visually inspect the revised Digital Waterfall using the normal preview control before changing the mature appliance's saved theme.
3. Verify updated `/etc/issue` and `/etc/motd` after the app update.
4. Verify BrandMeister + TGIF remain connected and zero systemd units fail after the update.
5. Exercise the HTTP/TGIF first-boot workflow on the eventual fresh RC4 factory image; the already-provisioned mature appliance cannot meaningfully prove a factory first-boot browser flow.
6. After all RC4 work is accepted, freeze the candidate, bump `VERSION`, test the real RC3 -> RC4 release update, and physically accept the exact RC4 image.
