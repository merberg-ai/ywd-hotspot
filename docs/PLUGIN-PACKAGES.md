# 📦 YWD-Hotspot `.ywdplugin` Packages

[← Docs index](README.md) · [Plugins](PLUGINS.md) · [Plugin UI](PLUGIN-UI.md) · [Security](../SECURITY.md)

YWD-Hotspot supports persistent local `.ywdplugin` packages with strict archive/hash/signature verification and an authenticated WebUI review flow.

External plugin source/examples are developed in `merberg-ai/ywd-hotspot-plugins`. Core remains authoritative for the package format, verifier, lifecycle, sandbox, update transaction, and security rules.

## Lifecycle

New package:

```text
UPLOAD
  → verify archive / hashes / signature
  → review candidate
  → INSTALL
  → ENABLE
  → ACTIVE
```

Existing uploaded plugin ID:

```text
UPLOAD newer/same/older package
  → verify without mutating installed state
  → classify UPDATE / REINSTALL / DOWNGRADE / REPLACE
  → review current → candidate details
  → explicit confirmation
  → transactional package swap + rollback on failure
```

Uploading never silently enables or starts a plugin.

## Container and filename

A `.ywdplugin` is a ZIP container using a YWD-specific extension:

```text
my-plugin-1.2.3.ywdplugin
```

Format v1 is intentionally flat. Payload entries must be regular files at archive root. Nested paths, symlinks, duplicate names, and archive-controlled extraction destinations are rejected.

Typical declarative package:

```text
ywdplugin.json
plugin.json
config.schema.json
README.md              optional
```

Typical service package:

```text
ywdplugin.json
plugin.json
config.schema.json
service.py
README.md              optional
signature.ed25519
```

Typical browser-UI package:

```text
ywdplugin.json
plugin.json
config.schema.json
ui.js
ui.css
README.md              optional
signature.ed25519
```

Current package limits include a 1 MiB compressed upload ceiling, 2 MiB total unpacked ceiling, bounded entry count/file size, and additional Plugin UI script/style limits.

## `ywdplugin.json`

Package metadata identifies the plugin/publisher and SHA-256 hashes every payload file.

Example:

```json
{
  "format": "ywdplugin",
  "version": 1,
  "id": "example-status",
  "publisher": "Example Developer",
  "files": {
    "plugin.json": "012345...",
    "config.schema.json": "abcdef..."
  }
}
```

Signed executable packages also declare:

```json
"signature": {
  "algorithm": "ed25519",
  "key_id": "example-dev-1"
}
```

Changing payload after signing breaks file hashes. Changing the signed package manifest breaks Ed25519 verification.

## Trust and signatures

Uploaded packages declare uploaded/experimental trust. They cannot self-assert YWD's core-owned `first-party` status.

| Uploaded package | Unsigned | Trusted Ed25519 signature |
|---|---:|---:|
| declarative/data-only | allowed, visibly UNSIGNED | allowed |
| service code | rejected | allowed |
| browser UI code | rejected | allowed |
| independent RF-mode package | rejected | rejected by current API |

A signature proves publisher provenance. It does **not** grant arbitrary sudo, device access, network access, or RF authority.

Trusted publisher public keys live at:

```text
/etc/ywd-hotspot/plugin-trust.d/<key-id>.pem
```

Private signing keys must never be committed or copied to the hotspot.

## Build packages

Canonical builder:

```bash
python3 tools/ywdplugin-build.py SOURCE OUTPUT.ywdplugin \
  --publisher "Publisher Name"
```

Signed executable package:

```bash
python3 tools/ywdplugin-build.py SOURCE OUTPUT.ywdplugin \
  --publisher "KJ6YWD" \
  --sign-key /secure/path/private.pem \
  --key-id kj6ywd-official-1
```

The companion plugin repo's `PLUGIN-DEV.sh` is orchestration around this core builder; it does not define a competing format.

## Upload/review flow

Unlock dashboard controls, open **PLUGINS**, and choose **UPLOAD .YWDPLUGIN**.

The WebUI shows real upload progress, then a review modal while trusted core validates:

- archive size/shape;
- safe flat filenames;
- exact file inventory;
- SHA-256 payload hashes;
- package/API version;
- plugin ID/kind/provider/schema;
- dependency/hardware tokens;
- capability declarations;
- signature/key identity where required;
- collisions with protected built-in plugin IDs;
- relationship to an existing uploaded package with the same ID.

Review is non-mutating. The operator must explicitly choose INSTALL/UPDATE/etc. or CANCEL.

## New-plugin install

For a new ID, successful verification presents package details and **INSTALL PLUGIN**. Installation registers the package but does not enable it.

Configuration/data paths remain separate from package source.

## Same-ID update classification

For an existing uploaded plugin ID, core compares installed and candidate metadata/version.

Typical actions:

```text
newer parseable version  → UPDATE PLUGIN
same version             → REINSTALL PLUGIN
older parseable version  → DOWNGRADE PLUGIN
unusual/unordered version→ REPLACE VERSION
```

Version ordering is a presentation/safety aid; archive/signature/API checks remain authoritative.

The review modal shows current → candidate version plus type/signature/capabilities and whether config/data/install/enable state will be preserved.

### Update restrictions

An ordinary same-ID update does not silently allow:

- replacement of a built-in/core-owned plugin ID;
- plugin kind change such as UI → service;
- bypass of executable-code signature policy;
- unreviewed privilege/capability expansion;
- arbitrary package-controlled migration commands.

Signer/provenance continuity is checked for executable uploaded plugins.

## Transactional apply

A confirmed package update:

1. re-verifies the uploaded archive;
2. captures package registration, activation, and service runtime/boot state;
3. preserves plugin configuration/data;
4. quiesces service runtime when applicable;
5. stages the new package separately;
6. swaps package source atomically;
7. validates new manifest/config compatibility;
8. restores prior valid installed/enabled/runtime intent;
9. removes transaction staging only after success.

If any apply step fails, core restores the old package and prior state where possible and reports the update failure.

## Persistent uploaded source

Uploaded package source lives outside the deployed application tree:

```text
/var/lib/ywd-hotspot/plugin-packages/<plugin-id>/
```

Normal application updates can replace `/opt/ywd-hotspot/app` without deleting uploaded package source.

Per-plugin state is separate:

```text
/etc/ywd-hotspot/plugins/<id>.json
/var/lib/ywd-hotspot/plugins/<id>/
```

## Runtime containment

Service plugins execute only through trusted `ywd-plugin@.service` and retain the shared hardened sandbox.

UI plugins have no Pi-side daemon and execute in an isolated dashboard iframe. They communicate only through declared trusted capability methods.

A trusted publisher signature does not remove these containment rules.

## Uninstall / data / package removal

**UNINSTALL** clears runtime eligibility/registration while preserving uploaded source and config/data.

**REMOVE DATA** removes only plugin configuration/data.

**REMOVE PACKAGE** removes uploaded package source only after the plugin is uninstalled/inert. It does not silently delete user configuration/data.

The old manual update sequence:

```text
Disable → Uninstall → Remove Package → Upload → Install → Enable
```

is no longer required for a normal same-plugin update.

## Application updates vs plugin updates

A YWD-Hotspot application update and a `.ywdplugin` package update are separate transactions.

Application updates capture/quiesce plugin runtime before replacing core and restore only prior plugin intent that still validates. Plugin package source/data remains outside the app tree.

Plugin package updates replace one uploaded plugin package without replacing the YWD core application or RF stack.

## Backup / restore

Protected `.ywdsettings` backups can preserve plugin registration/activation intent, configuration, and trusted publisher **public** keys. Uploaded executable package code and private signing keys are not silently embedded.

A restored fresh appliance reports missing package source and requires explicit re-upload rather than downloading executable code automatically.
