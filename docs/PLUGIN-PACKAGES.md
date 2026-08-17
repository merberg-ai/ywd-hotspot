# YWD-Hotspot `.ywdplugin` packages

Alpha18.2 adds a persistent local plugin-package format and locked WebUI upload path.

The design keeps four existing lifecycle concepts separate:

```text
UPLOAD     -> package source becomes AVAILABLE
INSTALL    -> package becomes eligible for use
ENABLE     -> operator activates the installed plugin
ACTIVE     -> plugin is effectively running now
```

Uploading a file never installs, enables or starts it.

## Package filename and container

A YWD plugin package is a normal ZIP container with the YWD-specific extension:

```text
my-plugin-1.0.0.ywdplugin
```

Package format v1 is deliberately flat. Files must be regular files at archive root; directories, nested paths and symbolic links are rejected.

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

The archive is intentionally small:

- maximum compressed upload: 1 MiB
- maximum total unpacked data: 2 MiB
- maximum entries: 32
- maximum individual file: 512 KiB

The core extractor does not call `extractall()` and does not accept archive-controlled destination paths.

## `ywdplugin.json`

The package manifest identifies the package and hashes every payload file.

Example unsigned declarative package:

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

Example signed service-package metadata adds:

```json
"signature": {
  "algorithm": "ed25519",
  "key_id": "example-dev-1"
}
```

Each `files` value is the lowercase SHA-256 digest of that exact archive payload. `ywdplugin.json` and `signature.ed25519` are package metadata and are not included in the payload hash map.

Any missing file, unlisted extra file, duplicate entry, malformed hash or hash mismatch rejects the whole upload.

## Uploaded-plugin trust label

Uploaded packages must declare:

```json
"trust": "experimental"
```

in `plugin.json`.

A WebUI-uploaded package is never allowed to self-assert YWD's core-owned `first-party` label, even when the package is correctly signed. Signature provenance and YWD first-party status are separate concepts.

Bundled YWD plugins shipped inside the application remain first-party packages.

## Signature policy

Alpha18.2 supports Ed25519 package signatures.

Policy:

| Uploaded package | Unsigned | Trusted Ed25519 signature |
|---|---:|---:|
| declarative/data-only | allowed, shown as **UNSIGNED** | allowed, shown as **VERIFIED** |
| sandboxed service code | **rejected** | allowed |
| RF-mode plugin | rejected by the current plugin API | rejected unless a future core API explicitly adds RF arbitration |

A package that declares a signature but has an unknown key, malformed signature or failed cryptographic verification is rejected. It never falls back to an unsigned warning.

### What a trusted signing key means

Installing a publisher key under `/etc/ywd-hotspot/plugin-trust.d` authorizes packages signed by that key to pass the executable-service signature gate. That is a meaningful trust decision.

It does **not** grant arbitrary root access. Signed service plugins still run through the shared YWD sandbox, but a trusted service publisher is allowed to supply Python code that runs as the restricted `ywd-hotspot` account and can use only capabilities allowed by the plugin manifest/core API.

Only add keys from publishers you intend to trust.

## Generate an Ed25519 publisher keypair

On a development machine with OpenSSL 3:

```bash
openssl genpkey -algorithm Ed25519 -out ywd-plugin-private.pem
openssl pkey -in ywd-plugin-private.pem -pubout -out ywd-plugin-public.pem
```

The private key is the publisher signing identity.

> **Never commit, upload, bundle or share the private key.** Losing control of it means losing control of that publisher identity.

Choose a stable key ID, for example:

```text
kj6ywd-official-1
```

The key ID is not cryptographic by itself; it selects the matching trusted public key on the hotspot.

## Trust a publisher key on a hotspot

Alpha18.2 intentionally keeps trusted-key installation as a local root/operator action. There is no WebUI button that silently expands executable-code trust.

Copy the public key to the hotspot and install it as:

```bash
sudo install -d -o root -g root -m 0750 /etc/ywd-hotspot/plugin-trust.d
sudo install -o root -g root -m 0644 \
  ywd-plugin-public.pem \
  /etc/ywd-hotspot/plugin-trust.d/kj6ywd-official-1.pem
```

The filename stem must exactly match the package `key_id`.

List trusted keys:

```bash
sudo ls -l /etc/ywd-hotspot/plugin-trust.d/
```

Removing a key prevents future uploads using that signing identity from verifying. It does not automatically delete already uploaded package source.

## Build an unsigned declarative package

A source directory must contain flat regular files including a valid `plugin.json` and its referenced configuration schema.

Example:

```bash
python3 tools/ywdplugin-build.py \
  ./my-declarative-plugin \
  ./my-declarative-plugin-1.0.0.ywdplugin \
  --publisher "KJ6YWD"
```

The tool calculates the SHA-256 inventory and creates the ZIP container.

Unsigned packages are accepted only when the plugin is declarative/data-only under the current API.

## Build a signed service package

```bash
python3 tools/ywdplugin-build.py \
  ./my-service-plugin \
  ./my-service-plugin-1.0.0.ywdplugin \
  --publisher "KJ6YWD" \
  --sign-key ./ywd-plugin-private.pem \
  --key-id kj6ywd-official-1
```

For service packages, `tools/ywdplugin-build.py` refuses to build without both `--sign-key` and `--key-id`.

The signing tool:

1. hashes all package payload files
2. creates canonical `ywdplugin.json`
3. signs those exact manifest bytes using Ed25519/OpenSSL
4. writes the 64-byte signature as base64 in `signature.ed25519`
5. creates the final `.ywdplugin` ZIP

Changing a payload file after signing causes its SHA-256 verification to fail. Changing the signed package manifest causes the Ed25519 verification to fail.

## Upload through the WebUI

Unlock YWD-Hotspot controls, open **PLUGINS**, then use:

```text
UPLOAD .YWDPLUGIN
```

The server validates the archive before it becomes part of the persistent local catalog.

Validation includes:

- upload and expanded-size limits
- safe flat filenames
- no symlinks/directories
- exact file inventory
- SHA-256 verification
- package-format version
- plugin ID and plugin API validation
- `experimental` uploaded trust label
- capability/dependency/hardware allow lists
- Ed25519 publisher verification when declared
- mandatory trusted signature for service code
- duplicate/colliding plugin ID rejection

A successful upload produces an **AVAILABLE** package card. It remains uninstalled and disabled.

The package card reports:

```text
Source     UPLOADED
Signature  VERIFIED · <key-id>
```

or, for an allowed unsigned declarative package:

```text
Source     UPLOADED
Signature  UNSIGNED
```

## Persistent package source

Uploaded package source is stored outside the deployed application tree:

```text
/var/lib/ywd-hotspot/plugin-packages/<plugin-id>/
```

This is intentional. `/opt/ywd-hotspot/app` is replaced by normal YWD application updates; uploaded package source should survive those updates.

The runtime catalog overlays these persistent packages onto the built-in catalogs at discovery time. Uploaded service plugins still execute through:

```text
systemd/ywd-plugin@.service
  -> plugin_service_runner.py
  -> validated installed service entrypoint
```

They do not install their own systemd units.

## Service sandbox

A signed uploaded service does **not** receive arbitrary system privileges.

The shared YWD service template retains the existing restrictions, including:

- user/group `ywd-hotspot`
- `NoNewPrivileges=true`
- no Linux capabilities
- private device namespace
- `ProtectSystem=strict`
- protected home/kernel/control-group state
- SUID/namespace restrictions
- `MemoryDenyWriteExecute=true`
- `RestrictAddressFamilies=AF_UNIX`
- no direct MMDVM serial/device ownership
- only its exact `/var/lib/ywd-hotspot/plugins/<id>` data path is opened for writes

Package signatures establish publisher provenance. The sandbox remains the runtime containment boundary.

## INSTALL vs UNINSTALL vs REMOVE PACKAGE vs REMOVE DATA

These actions are intentionally independent.

### INSTALL

Registers an AVAILABLE package as installed after core-owned dependency/hardware validation.

It does not enable or start the plugin.

### UNINSTALL

- stops and boot-disables a service plugin when applicable
- clears activation
- removes package registration
- preserves uploaded package source
- preserves plugin configuration/data

The plugin therefore returns to **AVAILABLE** and can be reinstalled later.

### REMOVE PACKAGE

Only uploaded packages have this action.

Requirements:

- package must already be uninstalled
- service must be inactive/boot-disabled

It physically removes:

```text
/var/lib/ywd-hotspot/plugin-packages/<id>/
```

Built-in YWD application packages cannot be physically removed this way; uninstall them instead. Application updates own `/opt/ywd-hotspot/app`.

### REMOVE DATA

This remains a separate destructive action and removes only the exact core-derived paths:

```text
/etc/ywd-hotspot/plugins/<id>.json
/var/lib/ywd-hotspot/plugins/<id>
```

Removing package source does not silently erase user configuration/data, and removing data does not silently remove package source.

## Application update behavior

The plugin update-safety helper includes persistent uploaded service packages when it captures and quiesces service state.

Before application replacement:

```text
capture built-in + uploaded plugin intent/service state
  -> disable/stop plugin services
  -> replace/validate core application
  -> load target built-in + persistent catalogs
  -> restore only packages that still validate and were previously enabled
```

New packages never auto-enable merely because an application update discovers them.

When switching to a non-plugin `main`/`dev` runtime, plugin services are made inert. Persistent uploaded package files may remain on disk as inert operator data so they are not silently destroyed by a channel change.

## Backup / restore relationship

`.ywdsettings` Alpha18.2 backups preserve:

- plugin package registration intent
- plugin master/per-plugin activation intent
- per-plugin configuration
- trusted publisher public keys

They do **not** embed uploaded `.ywdplugin` package code.

After restoring to a fresh OS, missing uploaded packages are reported. Re-upload the required `.ywdplugin` package; YWD does not fetch executable code automatically from a backup or from the Internet.

See **[BACKUP-RESTORE.md](BACKUP-RESTORE.md)**.
