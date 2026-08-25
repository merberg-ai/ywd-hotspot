# YWD-Hotspot RC3 development checkpoint — 2026-08-25

This checkpoint records the accepted pre-final-release-testing development state after the RC3 UI-polish batch was installed and physically exercised on the configured hotspot.

## Status

- Development line: `dev`
- Version string: `0.2.0-rc3`
- This checkpoint is a solid development baseline, **not final RC3 release acceptance**.
- The final published RC2 -> exact final RC3 updater acceptance is still pending.
- The exact final RC3 factory-image acceptance is still pending.
- `release/0.2.0-rc3` and `main` must remain frozen until final acceptance resumes.

## UI / support additions present at this checkpoint

- Settings remain visible but become read-only while dashboard controls are locked.
- Shared cyber-style boolean switches are used consistently for Settings/OLED/instrumentation controls on mobile and desktop.
- System SSH client-key creation is fixed to the managed `ywd` login; the fake username input is removed.
- Diagnostics were modernized with an expanded fail-soft support summary and a much broader sanitized diagnostic bundle.
- Plain-LAN/mobile clipboard fallback is present for Copy Support Summary.
- System includes a read-only MODEM / MMDVM inventory card with physical HAT/firmware identity, compiled MMDVM-Host runtime identity, YWD Extended generation/API/capabilities, hashes, source/build/cache provenance, and journal identity lines.
- The modem card reserves future guarded maintenance actions but exposes no compile/install, RF restart, or firmware-flash action in this RC3 UI-polish state.
- Software Update includes an authenticated custom Change Channel modal for approved WebUI channels only: `main`, `dev`, and `dev-plugins`.
- Branch switching uses the protected update path rather than arbitrary `git checkout`; release/checkpoint branches remain CLI-only engineering targets.
- Branch modal reports current/target version, commit, ancestry relationship, schema, plugin-runtime presence, and downgrade/divergence warnings.
- New modem/branch dashboard root-helper actions are narrowly added to the existing sudoers NOPASSWD allowlist.
- Modem and branch UI styling is shipped through first-party CSS files so it remains compatible with the dashboard Content-Security-Policy.
- The Settings-lock MutationObserver startup-loop regression is fixed; the dashboard startup fail-safe can run normally again.

## Physical observations accepted during this UI pass

- Dashboard successfully updates from the `dev` channel through the WebUI.
- Dashboard reloads normally after the startup-loop fix.
- MODEM / MMDVM inventory loads successfully and reports the installed duplex MMDVM HAT plus the current `ywd-extended` MMDVM-Host runtime.
- Change Channel inventory loads successfully and reports `main`, `dev`, and `dev-plugins` with correct version/commit/transition information.
- The final CSP-safe modem and branch layouts are visually accepted on the mobile browser and match the rest of the dashboard theme.

## Still pending before RC3 promotion

Do **not** treat this checkpoint as release acceptance. Before advancing `release/0.2.0-rc3`, `main`, or creating the final RC3 tag, resume the previously defined acceptance sequence:

1. Freeze the exact final RC3 source commit.
2. Advance `release/0.2.0-rc3` to that exact commit only when ready for release testing.
3. Fresh-flash the published RC2 image.
4. Prove untouched RC2 RF/Parrot and capture RC2 radio hashes.
5. Run the published RC2 -> exact final RC3 GitHub updater acceptance.
6. Confirm normal app update preserves MMDVM-Host/DMRGateway binaries.
7. Confirm RC3 classifies the untouched accepted RC2 Extended runtime as `legacy` with `upgrade_required=true` and without demand-gated capability.
8. Prove Parrot before the explicit runtime refresh.
9. Explicitly refresh YWD Extended and require the accepted current runtime generation, API/capabilities, patch identity, and in-sync state.
10. Re-prove TS1 and TS2 Parrot, BrandMeister/RF health, and zero failed units.
11. Build the factory image from the same exact accepted source commit.
12. Fresh-flash and physically accept that exact image artifact, including setup, UI, RF/network, plugin/vocoder, reboot, and persistence gates.
13. Only after all final gates pass may the release checkpoint, `main`, and `v0.2.0-rc3` be moved to the exact accepted source.

This file intentionally keeps the final RC2 -> RC3 updater test marked **PENDING** so later development does not accidentally treat the current UI checkpoint as a promoted release candidate.
