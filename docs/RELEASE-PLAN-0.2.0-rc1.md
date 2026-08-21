# YWD-Hotspot 0.2.0-rc1 Release Plan

This release is based on the physically proven builder checkpoint:

- `checkpoint-builder-0.1.0-image-boot-proven`
- commit `a5a6d9483a7cad519ee5288661447875f346b4e7`

## Public prebuilt image policy

The GitHub release image must be a true factory image. It must not contain any operator or builder-specific configuration.

Required public-image state:

- no saved Wi-Fi SSID or password;
- no callsign;
- no DMR ID or hotspot ID;
- no BrandMeister Hotspot Security password;
- no BrandMeister API key;
- no dashboard/control password;
- no imported settings backup;
- RF disabled on first boot;
- only application defaults and first-boot onboarding state.

On first boot, a device with no usable Wi-Fi profile starts the temporary YWD-Hotspot setup AP. The user configures Wi-Fi, reconnects to the LAN, then completes the OLED-code protected first-boot hotspot wizard.

A release build must fail closed if any preconfiguration is detected in the public release profile.

## 0.2.0-rc1 scope

1. MMDVM runtime variants
   - `ywd-extended` is the recommended/default variant.
   - `upstream` is supported as an explicit opt-out.
   - YWD Extended uses the pinned MMDVM-Host upstream commit plus the verified YWD extension patch.
   - Stock Upstream uses the exact pinned upstream source without YWD extensions.
   - cache identities must be distinct between variants.
   - installed runtime variant and provenance persist across normal updates.
   - plugin capability checks may require YWD extension API/capabilities.

2. First-boot setup hardening
   - visible inline finish errors;
   - visible apply/progress state;
   - success page reports configured dashboard URL and port;
   - automatic dashboard handoff;
   - canonical schema-preserving setup submission;
   - explicit simplex/duplex controls and separate duplex RX/TX frequencies.

3. Public image distribution
   - clean factory image;
   - `.img.xz`, `.bmap`, `.info`, SHA256 sums, build metadata, and first-start notes;
   - publish as a GitHub prerelease after physical smoke testing the exact release artifact.

4. Documentation refresh
   - README prioritizes the prebuilt image for testers;
   - install/build/OS/repository/plugin/DMR voice documentation reflects runtime variants and factory onboarding;
   - changelog records the physical acceptance baseline and release artifact provenance.

## Promotion sequence

1. Work on `release/0.2.0-rc1` derived from the proven checkpoint.
2. Validate candidate source and public factory profile.
3. Build the public image.
4. Verify SHA256 and XZ integrity.
5. Physically boot and smoke-test the exact public release image.
6. Freeze an RC checkpoint.
7. Fast-forward `dev` and `main` to the accepted release tree.
8. Tag/publish `v0.2.0-rc1` as a GitHub prerelease with the verified image assets.

Historical checkpoint and RC refs remain immutable.
