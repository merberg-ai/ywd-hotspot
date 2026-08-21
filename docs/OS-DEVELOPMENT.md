# YWD-Hotspot OS development

[Project README](../README.md) · [Building](BUILDING.md) · [OS builder](../os/README.md) · [Architecture](ARCHITECTURE.md)

YWD-Hotspot keeps the application and appliance-image source in one repository while preserving a strict runtime boundary: normal installs and updates do not depend on `os/`, but fresh images are built from the exact application commit that contains the OS builder.

## Current branch model

Application release work and image-builder work stay separated:

```text
main                     stable/promoted release line
  ↑
dev                      physically accepted app integration line


dev-builder              isolated image/builder line
```

The completed `dev-release-0.1.0` RC branch is historical release-hardening context. Do not merge builder/image experimentation into a release merely because both ultimately ship the same application. After the final 0.1.0 release state is proven, synchronize it forward into `dev-builder` intentionally before resuming image work.

## Current builder entry points

- `os/builder/DOCTOR.sh` — preflight the builder machine/source tree
- `os/builder/BUILD.sh` — canonical image build
- `os/builder/CONFIGURE-WIFI.sh` — optional local build-time Wi-Fi settings

Root `VERSION`, application code, WebUI, systemd units, console/branding assets, and canonical config generation are consumed from the same source tree.

## Easy image build

On the Linux builder machine:

```bash
cd ~/ywd-hotspot

git status --short
git branch --show-current

bash os/builder/DOCTOR.sh
```

Do not start a long image build until the doctor passes.

Then:

```bash
bash os/builder/BUILD.sh
```

Build-time Wi-Fi is optional:

```bash
bash os/builder/CONFIGURE-WIFI.sh
```

The builder performs syntax/preflight checks before pi-gen and uses bounded parallelism for the heavier radio-source builds.

Local credentials, SSH keys, work directories, pi-gen checkout and deploy images are ignored under the builder's local/work/deploy paths and should not be committed.

## Radio build baseline inside the image

The image consumes the same exact pins as a normal source install:

```text
MMDVM-Host  dea6e9b2c35857fe6f904c5092bebadb86cbf079
DMRGateway  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

The optional RX Monitor/passive voice tap uses the same YWD patch shipped by the application:

```text
lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch
```

That optional patched binary is still treated as passive observation infrastructure and must not become a second modem owner. Normal application updates remain independent of long MMDVM compilation.

## Physical acceptance checklist

Do not call an image known-good merely because it compiled. Validate the actual target appliance:

```text
[ ] builder doctor passes
[ ] image build completes
[ ] xz integrity test passes
[ ] Pi Zero boots
[ ] OLED boot/network screens work
[ ] setup AP appears without station Wi-Fi
[ ] Wi-Fi handoff works
[ ] secure :8443 wizard accepts OLED code
[ ] current WebUI loads
[ ] unlock/auth works
[ ] settings/config apply works
[ ] BrandMeister connects
[ ] RF can be explicitly enabled
[ ] handheld -> hotspot RX works
[ ] hotspot -> handheld TX works
[ ] Parrot succeeds
[ ] duplex TS1 succeeds when using duplex hardware
[ ] duplex TS2 succeeds when using duplex hardware
[ ] ywd-headless-oled.service active
[ ] legacy ywd-oled.service inactive on YWD-Hotspot OS
[ ] reboot preserves setup/config
[ ] CLI update check/dry-run works
[ ] About-page application update works
[ ] another reboot preserves the fully configured state
```

If the image is intended to ship the passive RX voice feature as ready-to-use, separately verify the guarded voice-tap build/status and normal RF operation while the observer infrastructure is present.

## Image vs application updates

An image build is an installation artifact, not the ongoing application update mechanism. Once installed, YWD-Hotspot should receive normal application updates from its saved update channel without another SD-card image build.

The runtime split remains:

```text
/opt/ywd-hotspot/repo    managed Git source
/opt/ywd-hotspot/app     deployed runtime
```

## Promotion

After an image build is physically validated:

1. record the exact application/builder commit;
2. freeze a known-good builder/image checkpoint;
3. keep release/app promotion decisions separate from image experiments;
4. only merge/synchronize the focused builder changes into the intended active line after acceptance.

This keeps risky image work away from the daily-driver release path while still producing an image from the same canonical application source.
