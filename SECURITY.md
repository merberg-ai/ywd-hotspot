# 🔐 Security Policy

[Project README](README.md) · [Installation](docs/INSTALL.md) · [OS Image Build](docs/OS-IMAGE-BUILD.md) · [Upgrading](docs/UPGRADING.md) · [Contributing](CONTRIBUTING.md)

---

YWD-Hotspot controls radio/network services and stores reusable credentials. Treat a deployed hotspot as an appliance, not a disposable static website.

## 🧭 Current development state

- promoted line: `main` / `0.1.0-alpha12.2-dev`
- normal core/application development line: `dev`, currently aligned with promoted Alpha12.2
- proven integrated checkpoint: `dev-alpha12.2-os-integrated-known-good`
- experimental plugin/MMDVM work remains separate on `dev-plugins`

Security fixes may land on an active development line before a later promotion, but `main` documentation describes only capabilities actually present on the promoted non-plugin runtime.

## 🌐 Network exposure

The built-in dashboard uses plain HTTP and is intended for a trusted LAN.

> [!CAUTION]
> **Do not directly expose the dashboard TCP port to the public Internet.**

If remote administration is required, place the hotspot behind an appropriate authenticated/encrypted access layer rather than forwarding the YWD dashboard port itself.

YWD-Hotspot OS uses a separate HTTPS service on port `8443` only during secure first-boot setup. It uses a locally generated self-signed certificate and a short-lived six-digit code shown on the OLED.

## 🔑 Secrets

YWD-Hotspot deliberately separates:

1. BrandMeister Hotspot Security password
2. BrandMeister API v2 key
3. local WebUI control password

The API key stays server-side. Browser JavaScript does not receive it back.

Never post real credentials in GitHub issues, screenshots, terminal pastes, logs, or support conversations.

## 📁 Sensitive runtime paths

Treat these as sensitive on a real installation:

```text
/etc/ywd-hotspot/config.json
/etc/ywd-hotspot/bm-api.key
/etc/ywd-hotspot/web-auth.json
/var/lib/ywd-hotspot/private/
/var/backups/ywd-hotspot/
```

`/etc/ywd-hotspot/build-info.json` is intentionally non-secret provenance containing source/version/commit information only.

Protected backups can contain reusable configuration credentials and are intentionally restricted on disk.

## 🥧 Sensitive builder-local paths

The OS image builder keeps private/local build state under ignored `os/local/`.

Treat at least these as secrets:

```text
os/local/provision.env
os/local/ywd-os-dev_ed25519
```

`provision.env` can contain a Wi-Fi password. `ywd-os-dev_ed25519` is the builder-local SSH private key whose public key is embedded for development access to generated images.

Do not commit, publish, archive with release artifacts, or casually distribute those private files.

Current `main` intentionally does **not** support preseeding the full hotspot/BrandMeister credential set into an image. Factory images use placeholder identity, clear control/API credentials and keep RF disabled until secure first-boot setup completes.

## 🔄 GitHub update trust boundary

GitHub-managed deployments use:

```text
/opt/ywd-hotspot/repo
```

The updater:

- accepts only the canonical `merberg-ai/ywd-hotspot` origin forms
- refuses real local content changes in the managed checkout
- stages a target commit separately before deploy
- validates required runtime files and shell/Python syntax
- applies through the transactional updater
- advances the managed checkout only after deployment succeeds
- preserves the prior RF active/enabled policy

Do not weaken those checks merely to make local experimentation more convenient.

## 🧱 Web privilege boundary

The WebUI service runs as the restricted `ywd-hotspot` account.

Root-required browser actions are constrained through:

```text
/usr/local/libexec/ywd-hotspot-admin
/etc/sudoers.d/ywd-hotspot
```

The browser must not gain arbitrary shell execution or direct write access to generated MMDVM-Host/DMRGateway INI files.

The YWD-Hotspot OS first-boot server also runs unprivileged and delegates only its narrow setup-finalization action through the same restricted privilege boundary.

## 🛡️ Browser policy

The normal dashboard uses a restrictive Content-Security-Policy. UI polish should use same-origin external CSS/JS rather than weakening CSP with broad `unsafe-inline` allowances.

The custom confirmation/toast layer is browser-side presentation only; it does not create a new privileged backend path.

The first-boot setup page is a separate short-lived appliance onboarding service and should not be treated as the normal dashboard security model.

## 📡 RF safety

Install, update, image build/first boot, configuration, Wi-Fi onboarding and WebUI activity must not unexpectedly enable the transmitter.

Factory OS images explicitly disable MMDVM-Host and DMRGateway. Secure first-boot setup requires real station identity/config and only enables RF when the operator explicitly requests it on the final setup path.

## 🩺 Diagnostics

Prefer the sanitized support exporter:

```bash
sudo ywd-hotspotctl diagnostics
```

It is designed to exclude/redact reusable passwords and API keys. Still review any bundle before publishing it.

Do not upload raw protected config/update backups or builder-local private keys.

## 🚨 Reporting a security issue

Do not open a public issue containing exploit details plus working credentials/private deployment data.

If GitHub private security reporting is enabled, use it. Otherwise open a minimal public issue asking the maintainer for a private contact path without including secrets or sensitive reproduction data.

## 🔍 Changes requiring extra scrutiny

Treat these as security-sensitive:

- broader sudo permissions
- user-controlled shell execution
- secrets exposed to browser JavaScript
- weakened canonical-repository checks
- bypassed dirty-tree/update validation
- browser direct edits to generated INIs
- public-Internet exposure features
- image-builder changes that embed new secrets by default
- setup changes that can unexpectedly enable RF
- changes that can unexpectedly enable RF anywhere else
