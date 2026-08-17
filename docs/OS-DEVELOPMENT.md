# YWD-Hotspot OS development

[Project README](../README.md) · [Detailed image build guide](OS-IMAGE-BUILD.md) · [OS builder source](../os/README.md) · [Architecture](ARCHITECTURE.md)

YWD-Hotspot keeps the application and appliance-image source in one repository while preserving a strict runtime boundary: normal installs and updates do not depend on `os/`, but fresh images are built from the exact application commit that contains the OS builder.

## Current state

The unified application + OS-builder work is no longer an isolated integration experiment. It was physically validated, preserved at:

```text
dev-alpha12.2-os-integrated-known-good
41f1cf9fcf94b3880d5cf11fb35e2cccb6fd3afd
```

and that exact commit is now the promoted `main` baseline as well as the current plain `dev` baseline.

Experimental plugin/MMDVM work remains on `dev-plugins` and is intentionally separate from the `main` image-builder/runtime described here.

## Branch model

```text
main        promoted stable appliance/image line
  │
  └─ dev    normal application + OS development
       ├─ known-good checkpoints
       ├─ temporary dev-os-* / feature integration branches
       └─ dev-plugins is maintained separately for experimental plugin work
```

The historical long-lived `dev-os` branch is reference/history. Do not merge it wholesale into current `dev` or `main`.

## Unified builder rules

The current builder follows these rules:

- `os/builder/BUILD.sh` is the canonical image-build entry point.
- `BUILD-M4.sh` is only a compatibility alias.
- tracked uncommitted source blocks a reproducible build.
- root `VERSION`, application code, WebUI, services and helper layout are packaged from the current commit.
- root `lib/oled.py` is injected as the headless OLED renderer.
- root console/branding assets are injected into the image polish stage.
- factory config is generated from current `lib/config_model.py` rather than a hand-maintained old schema copy.
- first boot installs the current split admin/setup/update helper layout.
- the managed Git checkout uses a full branch refspec.
- images built from `main` follow `main`; images built from `dev` follow `dev`; experimental branches fall back to `dev` as the normal future application channel.
- RF services remain disabled until secure first-boot setup explicitly enables them.

## Build workflow

For the complete operator/builder walkthrough—including host packages, Wi-Fi-preseeded vs factory builds, output validation, flashing, first boot, and acceptance tests—use:

**[OS-IMAGE-BUILD.md](OS-IMAGE-BUILD.md)**

The short developer loop is:

```bash
cd ~/ywd-hotspot
git status --short
git branch --show-current
bash os/builder/DOCTOR.sh
bash os/builder/BUILD.sh
```

The builder runs syntax/preflight checks before pi-gen and caps MMDVM-Host/DMRGateway compilation at four jobs.

Optional builder-local Wi-Fi provisioning:

```bash
bash os/builder/CONFIGURE-WIFI.sh
```

Credentials, SSH keys, work directories, pi-gen checkout and deploy images are ignored under `os/local`, `os/work`, `os/.pi-gen` and `os/deploy`.

### Supported preconfiguration boundary

Current `main` supports optional **Wi-Fi** preseeding only. It does not provide a supported full station/radio/BrandMeister preseed mechanism.

The image runtime stage deliberately creates a factory placeholder (`NOCALL`, `00000`, BrandMeister disabled) and the first-boot layer clears control/API credentials. Real station/radio settings are finalized through the secure first-boot wizard.

If full factory provisioning is added later, design it as a validated explicit builder interface with secret-handling rules; do not rely on undocumented rootfs edits.

## Physical acceptance checklist

Do not promote an image-related change merely because the image compiled. Validate the target appliance:

```text
[ ] builder doctor passes
[ ] image build completes
[ ] checksum + xz integrity tests pass
[ ] Pi Zero boots
[ ] OLED boot/network screens work
[ ] setup AP appears without station Wi-Fi
[ ] Wi-Fi handoff works
[ ] Wi-Fi-preseed build either joins Wi-Fi or falls back to AP
[ ] secure :8443 wizard accepts OLED code
[ ] current WebUI loads
[ ] unlock/auth works
[ ] settings/config apply works
[ ] BrandMeister connects
[ ] RF can be explicitly enabled
[ ] handheld -> hotspot RX works
[ ] hotspot -> handheld TX works
[ ] Parrot succeeds
[ ] normal talkgroup RX succeeds
[ ] ywd-headless-oled.service active
[ ] ywd-oled.service inactive
[ ] reboot preserves setup/config
[ ] CLI update check/dry-run works
[ ] About-page application update works
[ ] systemctl --failed is clean
```

An image build is an installation artifact, not the ongoing application update mechanism. Once installed, YWD-Hotspot should continue receiving normal application updates from the saved `main` or `dev` channel without another SD-card image build.

## Development / promotion workflow

For future OS changes:

1. cut a focused temporary branch from the current `dev` baseline
2. make the smallest source/builder change needed
3. run `DOCTOR.sh` and build a candidate image
4. physically validate it on the Pi Zero using the checklist above
5. freeze a known-good checkpoint when appropriate
6. merge/fast-forward the focused change back to `dev`
7. promote `dev` to `main` only by deliberate approval after normal application and image behavior are proven

Keep experimental plugin/MMDVM work on its own line unless there is an explicit decision to promote those capabilities into the core appliance.
