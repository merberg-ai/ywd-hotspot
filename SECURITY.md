# 🔐 Security Policy

[Project README](README.md) · [Installation](docs/INSTALL.md) · [Upgrading](docs/UPGRADING.md) · [Contributing](CONTRIBUTING.md)

---

YWD-Hotspot controls radio/network services and stores reusable credentials. Treat a deployed hotspot as an appliance, not a disposable static website.

## 🧭 Current development state

- active development line: `dev` / `0.1.0-alpha10-dev`
- latest user-tested checkpoint: `dev-alpha9.2-known-good`
- promoted line: `main`

Security fixes may land on the active development line before a later promotion.

## 🌐 Network exposure

The built-in dashboard uses plain HTTP and is intended for a trusted LAN.

> [!CAUTION]
> **Do not directly expose the dashboard TCP port to the public Internet.**

If remote administration is required, place the hotspot behind an appropriate authenticated/encrypted access layer rather than forwarding the YWD dashboard port itself.

## 🔑 Secrets

YWD-Hotspot deliberately separates:

1. BrandMeister Hotspot Security password
2. BrandMeister API v2 key
3. local WebUI control password

The API key stays server-side. Browser JavaScript does not receive it back.

Never post real credentials in GitHub issues, screenshots, terminal pastes, logs, or support conversations.

## 📁 Sensitive paths

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

## 🛡️ Browser policy

The dashboard uses a restrictive Content-Security-Policy. UI polish should use same-origin external CSS/JS rather than weakening CSP with broad `unsafe-inline` allowances.

The custom confirmation/toast layer is browser-side presentation only; it does not create a new privileged backend path.

## 🩺 Diagnostics

Prefer the sanitized support exporter:

```bash
sudo ywd-hotspotctl diagnostics
```

It is designed to exclude/redact reusable passwords and API keys. Still review any bundle before publishing it.

Do not upload raw protected config/update backups.

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
- changes that can unexpectedly enable RF
