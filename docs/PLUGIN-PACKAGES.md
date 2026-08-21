# 📦 YWD-Hotspot `.ywdplugin` Packages

[← Docs index](README.md) · [Plugins](PLUGINS.md) · [Plugin UI](PLUGIN-UI.md) · [Security](../SECURITY.md)

YWD-Hotspot supports persistent local `.ywdplugin` packages with strict archive/hash/signature verification and an authenticated review/apply flow. Core remains authoritative for package format, lifecycle, containment, dependency/runtime checks and update transactions.

## Lifecycle

```text
UPLOAD
  → archive/hash/signature validation
  → non-mutating review
  → INSTALL
  → ENABLE
  → ACTIVE
```

Same-ID uploads are classified as update/reinstall/downgrade/replacement and use a transactional swap with rollback.

Uploading never silently installs, enables or starts code.

## Container

`.ywdplugin` is a strict flat ZIP container. Nested paths, symlinks, duplicate names and package-controlled extraction destinations are rejected.

Typical UI package:

```text
ywdplugin.json
plugin.json
config.schema.json
ui.js
ui.css
README.md
signature.ed25519
```

Executable service/UI packages require trusted Ed25519 signatures. Declarative/data-only packages may be unsigned but are visibly treated as such.

## `ywdplugin.json`

Package metadata identifies the package and SHA-256 hashes every payload file. Signed packages declare an Ed25519 algorithm/key ID and include `signature.ed25519`.

A signature proves publisher provenance; it does not grant arbitrary sudo, device/network access, MMDVM ownership or RF authority.

Trusted publisher **public** keys live in:

```text
/etc/ywd-hotspot/plugin-trust.d/<key-id>.pem
```

Private signing keys never belong on the hotspot or in Git.

## `plugin.json` requirements

Dependencies/hardware are safe declarative tokens interpreted by core. A package cannot supply custom `apt`, `pip`, shell, download or hardware-probe commands.

General examples:

```json
"dependencies": ["python3", "mmdvm-host"],
"hardware": ["mmdvm-serial"]
```

### MMDVM runtime requirements

`0.2.0-rc1` adds tokens tied to the persistent MMDVM runtime:

```text
mmdvm-ywd-extended
mmdvm-extension-api-2
mmdvm-cap-passive-dmr-voice
```

Example passive RX package:

```json
{
  "dependencies": [
    "mmdvm-host",
    "mmdvm-ywd-extended",
    "mmdvm-extension-api-2",
    "mmdvm-cap-passive-dmr-voice"
  ]
}
```

Core resolves these against `/etc/ywd-hotspot/mmdvm-runtime.json` during install and again during enable/start paths. A Stock Upstream appliance therefore reports the missing runtime requirement instead of activating a plugin that cannot work.

Plugins cannot switch/rebuild the MMDVM runtime themselves.

## Package build

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

The companion plugin repository may wrap this builder but does not define a competing package format.

## Upload/review

The dashboard review verifies:

- archive size/shape and safe filenames;
- exact file inventory and SHA-256 hashes;
- package/API version;
- plugin ID/kind/provider/schema;
- dependency/hardware/runtime requirements;
- capability declarations;
- signature/key identity where required;
- protected ID collisions;
- same-ID update relationship.

Review does not mutate installed state.

## Transactional update

A confirmed same-ID update:

1. re-verifies archive/signature;
2. captures registration/activation/runtime state;
3. preserves config/data;
4. quiesces service runtime where applicable;
5. stages candidate separately;
6. atomically swaps package source;
7. revalidates manifest/config/requirements;
8. restores only prior valid intent;
9. rolls back old package/state if apply fails.

A same-ID update cannot silently change plugin kind, bypass signing policy, replace protected built-ins, or gain arbitrary new privileges.

## Persistent locations

```text
/var/lib/ywd-hotspot/plugin-packages/<id>/   uploaded package source
/etc/ywd-hotspot/plugins/<id>.json           plugin config
/var/lib/ywd-hotspot/plugins/<id>/           plugin data
```

Ordinary YWD application updates replace core separately and do not delete uploaded package source/config/data.

## Containment

Service plugins use the shared hardened `ywd-plugin@.service`. UI plugins run in isolated iframes and communicate only through declared trusted capability methods. A trusted signature or satisfied MMDVM requirement does not remove containment.

## Uninstall / removal

- **UNINSTALL** removes runtime/package-registration eligibility while preserving source/config/data.
- **REMOVE DATA** removes plugin config/data only.
- **REMOVE PACKAGE** removes uploaded source only after the plugin is inert/uninstalled.

## Backup / restore

Protected `.ywdsettings` backups may preserve plugin registration/activation intent, configuration and trusted publisher public keys. Uploaded executable package code and private signing keys are never silently embedded/fetched during restore.
