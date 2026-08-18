# YWD-Hotspot `.ywdplugin` packages

YWD-Hotspot supports a persistent local `.ywdplugin` package format and a locked WebUI upload path.

External plugin source/examples are developed in `merberg-ai/ywd-hotspot-plugins`. The canonical package format, verifier, lifecycle and security rules remain defined by YWD-Hotspot core and this document.

The lifecycle deliberately keeps source, installation and activation separate:

```text
UPLOAD     -> package source becomes AVAILABLE
INSTALL    -> package becomes eligible for use
ENABLE     -> operator activates the installed plugin
ACTIVE     -> plugin is effectively active now
```

Uploading never installs, enables, or starts a package.

## Real-hardware validation

The signed uploaded-service lifecycle was exercised successfully on the Raspberry Pi appliance running `0.1.0-alpha18.2.15-dev`, and the Alpha18.2.16 stable development baseline was subsequently physically tested successfully.

```text
UPLOAD signed .ywdplugin
  -> Source: UPLOADED
  -> Signature: VERIFIED
  -> AVAILABLE
  -> INSTALL
  -> ENABLE / ACTIVE
  -> configuration save + restart
  -> DISABLE
  -> UNINSTALL
  -> configuration preserved
  -> REMOVE DATA
  -> REMOVE PACKAGE
```

Plugin UI v1 is new experimental Alpha19 work and is not considered hardware/browser proven until its separate UI smoke-test lifecycle passes.

## Package filename and container

A YWD plugin package is a normal ZIP container using the YWD-specific extension:

```text
my-plugin-1.0.0.ywdplugin
```

Format v1 is deliberately flat. Files must be regular files at archive root; directories, nested paths, symbolic links and duplicate entries are rejected.

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

Typical Plugin UI v1 package:

```text
ywdplugin.json
plugin.json
config.schema.json
ui.js
ui.css
README.md              optional
signature.ed25519
```

Current archive limits:

- maximum compressed upload: 1 MiB
- maximum total unpacked data: 2 MiB
- maximum entries: 32
- maximum individual file: 512 KiB

Plugin UI v1 additionally limits its declared script to 256 KiB and stylesheet to 128 KiB. The package-wide limits still apply.

The core extractor does not call `extractall()` and does not accept archive-controlled destination paths.

## `ywdplugin.json`

The package manifest identifies the package and SHA-256 hashes every payload file.

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

Signed service/UI metadata adds:

```json
"signature": {
  "algorithm": "ed25519",
  "key_id": "example-dev-1"
}
```

`files` values are lowercase SHA-256 digests of the exact archive payload. `ywdplugin.json` and `signature.ed25519` are package metadata and are not included in the payload hash map.

Missing files, unlisted extras, malformed hashes, duplicate entries, or hash mismatches reject the whole upload.

## Uploaded trust label

Uploaded packages must declare:

```json
"trust": "experimental"
```

A WebUI-uploaded package cannot self-assert YWD's core-owned `first-party` label, even when correctly signed. Signature provenance and first-party status are separate concepts.

## Signature policy

| Uploaded package | Unsigned | Trusted Ed25519 signature |
|---|---:|---:|
| declarative/data-only | allowed, shown **UNSIGNED** | allowed, shown **VERIFIED** |
| sandboxed service code | **rejected** | allowed |
| sandboxed browser UI code | **rejected** | allowed |
| RF-mode plugin | rejected by current API | rejected unless future trusted-core RF arbitration explicitly allows it |

A package that declares a signature but has an unknown key, malformed signature, or failed verification is rejected. It never falls back to unsigned mode.

A valid signature establishes publisher provenance; it does not grant arbitrary privilege. Service plugins still run in the shared restricted Pi sandbox. UI plugins receive no Pi-side process and their browser code runs only inside the isolated Plugin UI frame described in **[PLUGIN-UI.md](PLUGIN-UI.md)**.

### Trusted publisher keys

Installing a public key under `/etc/ywd-hotspot/plugin-trust.d` authorizes packages signed by that identity to pass the executable-code signature gate.

Generate a publisher keypair on a development machine with OpenSSL 3:

```bash
openssl genpkey -algorithm Ed25519 -out ywd-plugin-private.pem
openssl pkey -in ywd-plugin-private.pem -pubout -out ywd-plugin-public.pem
```

Never commit, upload, bundle, or share the private signing key.

Choose a stable key ID, for example:

```text
kj6ywd-official-1
```

Install the public half on a hotspot:

```bash
sudo install -d -o root -g root -m 0750 /etc/ywd-hotspot/plugin-trust.d
sudo install -o root -g root -m 0644 \
  ywd-plugin-public.pem \
  /etc/ywd-hotspot/plugin-trust.d/kj6ywd-official-1.pem
```

The filename stem must exactly match the package `key_id`.

## Build packages

Unsigned declarative package:

```bash
python3 tools/ywdplugin-build.py \
  ./my-declarative-plugin \
  ./my-declarative-plugin-1.0.0.ywdplugin \
  --publisher "KJ6YWD"
```

Signed service or UI package:

```bash
python3 tools/ywdplugin-build.py \
  ./my-plugin \
  ./my-plugin-1.0.0.ywdplugin \
  --publisher "KJ6YWD" \
  --sign-key /secure/path/ywd-plugin-private.pem \
  --key-id kj6ywd-official-1
```

For `service` and `ui` packages the builder refuses to proceed without both `--sign-key` and `--key-id`.

The companion `ywd-hotspot-plugins` repository also provides `PLUGIN-DEV.sh`, an interactive/command-mode wrapper that validates source and invokes this canonical builder. It does not implement a second package format.

The builder:

1. hashes all package payload files
2. creates canonical `ywdplugin.json`
3. signs those exact manifest bytes using Ed25519/OpenSSL
4. stores the 64-byte signature as base64 in `signature.ed25519`
5. creates the final `.ywdplugin` ZIP

Changing payload after signing breaks SHA-256 verification. Changing the signed manifest breaks Ed25519 verification.

## Upload through the WebUI

Unlock dashboard controls, open **PLUGINS**, and use **UPLOAD .YWDPLUGIN**.

Validation includes:

- upload and expanded-size limits
- safe flat filenames
- no symlinks/directories
- exact file inventory
- SHA-256 verification
- package-format version
- plugin ID / plugin API validation
- `experimental` uploaded trust label
- capability/dependency/hardware allow lists
- Ed25519 publisher verification when declared
- mandatory trusted signature for service and UI executable code
- duplicate/colliding plugin ID rejection across declarative/service/UI models

A successful upload creates an **AVAILABLE** package card. It remains uninstalled and disabled.

Signed package cards show:

```text
Source     UPLOADED
Signature  VERIFIED · <key-id>
```

Allowed unsigned declarative packages show `Signature  UNSIGNED`.

## Persistent uploaded source

Uploaded package source is stored outside the deployed application tree:

```text
/var/lib/ywd-hotspot/plugin-packages/<plugin-id>/
```

This allows normal YWD application updates to replace `/opt/ywd-hotspot/app` without deleting uploaded package source.

Uploaded service plugins execute only through trusted core:

```text
systemd/ywd-plugin@.service
  -> plugin_service_runner.py
  -> validated installed service entrypoint
```

They cannot install their own service unit.

Uploaded UI plugins have no systemd unit or Pi-side entrypoint. Trusted core serves only their declared UI assets while the package is installed and effectively enabled.

## Runtime containment

A trusted signature does not remove containment.

Service plugins retain restrictions including:

- `User/Group=ywd-hotspot`
- `NoNewPrivileges=true`
- no Linux capabilities
- private device namespace
- `ProtectSystem=strict`
- protected home/kernel/control-group state
- SUID/namespace restrictions
- `MemoryDenyWriteExecute=true`
- `RestrictAddressFamilies=AF_UNIX`
- no direct MMDVM serial/device ownership
- only the exact plugin data path opened for writes

UI plugins instead execute on the browser device inside a sandboxed iframe with a restrictive CSP/Permissions Policy and a narrow trusted MessageChannel bridge. They are never injected into the trusted dashboard DOM.

## INSTALL / UNINSTALL / REMOVE DATA / REMOVE PACKAGE

**INSTALL** registers an AVAILABLE package after core-owned requirement validation. It does not enable or start it.

**ENABLE** activates the installed package under the master Plugin Support switch. A UI-only plugin becomes effectively ACTIVE without creating a Pi-side process; its browser frame is created only when its dashboard section is opened.

**UNINSTALL** stops and boot-disables service runtime when applicable, clears activation/registration, preserves uploaded source, and preserves configuration/data. The plugin returns to AVAILABLE.

**REMOVE DATA** removes only:

```text
/etc/ywd-hotspot/plugins/<id>.json
/var/lib/ywd-hotspot/plugins/<id>
```

**REMOVE PACKAGE** is available only for uploaded packages and requires the plugin to be uninstalled and inert. It removes only:

```text
/var/lib/ywd-hotspot/plugin-packages/<id>/
```

Removing source never silently removes user configuration/data; removing data never silently removes package source.

## Application-update behavior

Before application replacement, trusted core captures plugin intent/runtime state and quiesces service plugins. After target validation, only previously enabled packages that still validate are eligible for restoration. Newly discovered packages remain disabled.

UI plugins participate in the same activation-intent validation but have no service process to quiesce or restart.

When switching to a plugin-free target, service plugins are made inert and plugin activation is cleared. Persistent uploaded package files may remain as inert operator data rather than being silently destroyed.

## Backup / restore relationship

Protected `.ywdsettings` backups preserve package-registration intent, plugin activation intent, per-plugin configuration, and trusted publisher **public** keys.

They do **not** embed uploaded executable `.ywdplugin` package code or signing private keys.

After restoring a fresh system, missing uploaded packages are reported and must be explicitly re-uploaded. YWD does not fetch executable code automatically from backup metadata or the Internet.

See **[BACKUP-RESTORE.md](BACKUP-RESTORE.md)**, **[PLUGINS.md](PLUGINS.md)** and **[PLUGIN-UI.md](PLUGIN-UI.md)**.
