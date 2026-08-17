# 🥧 Building a YWD-Hotspot OS image

[← Docs index](README.md) · [Installation](INSTALL.md) · [OS development notes](OS-DEVELOPMENT.md) · [OS builder source](../os/README.md)

---

This guide covers the supported `main`-branch workflow for building a complete Raspberry Pi OS image containing the exact YWD-Hotspot application revision you checked out.

The image builder is for producing a fresh SD-card appliance image. It is **not** the normal application update path. After first boot and setup, the hotspot continues to update through the managed Git checkout just like a normal installation.

## ✅ What the builder currently supports

The unified builder targets:

- original Raspberry Pi Zero W / Zero WH
- Raspberry Pi OS Lite / trixie
- `armhf`
- MMDVM HAT on `/dev/serial0`
- SSD1306-style 128×64 OLED on I2C bus 1 / `0x3c`
- pinned MMDVM-Host + DMRGateway builds
- setup/recovery Wi-Fi AP
- secure HTTPS first-boot setup wizard
- managed `main` / `dev` application updates after imaging

The builder packages the root application from the **same Git commit that runs `os/builder/BUILD.sh`**. It does not maintain a second application snapshot under `os/`.

## 🔐 Factory safety behavior

Every supported image build starts in a safe factory state:

- MMDVM-Host and DMRGateway are disabled
- RF is off
- factory callsign is `NOCALL`
- factory DMR ID is `00000`
- BrandMeister is disabled until setup
- WebUI control credentials are not pre-created
- BrandMeister API credentials are not pre-created
- `ywd-headless-oled.service` is the sole OLED owner
- the secure first-boot setup must complete before RF may be enabled

Do not bypass those rules merely to make image testing faster.

## ⚠️ Current preconfiguration support

There are currently **two supported image-build modes**:

1. **Factory/unconfigured image** — no Wi-Fi is embedded. The Pi starts the setup AP and walks the operator through Wi-Fi plus the secure first-boot wizard.
2. **Wi-Fi-preseeded image** — the builder embeds one private Wi-Fi profile from ignored `os/local/` state. The Pi attempts that network first, then still requires the secure first-boot wizard for station/radio/BrandMeister configuration.

Current `main` does **not** provide a supported builder helper for preseeding every radio, callsign, DMR ID, BrandMeister, WebUI-password, or API-key setting into an image. The runtime stage deliberately writes a factory placeholder and the first-boot stage clears control/API credentials.

If full appliance preseeding is added later, it should be an explicit validated builder feature rather than an undocumented edit to staged rootfs files.

## 🖥️ Build-machine requirements

Use a Linux build machine capable of running Raspberry Pi `pi-gen` and armhf chroot tools. The builder doctor requires a **4096-byte kernel page size**.

Check the host first:

```bash
getconf PAGE_SIZE
uname -m
```

Expected page size:

```text
4096
```

Then install the normal Debian/Ubuntu/Raspberry Pi OS build dependencies if needed:

```bash
sudo apt update
sudo apt install -y \
  coreutils quilt parted qemu-user qemu-user-binfmt debootstrap zerofree zip \
  dosfstools e2fsprogs libarchive-tools libcap2-bin grep rsync xz-utils file \
  git curl bc gpg pigz xxd arch-test bmap-tools kmod openssh-client
```

`DOCTOR.sh` is authoritative; if it reports a missing requirement, fix that before building.

## 📥 Clone the promoted `main` line

For a main-line image:

```bash
cd ~
git clone --branch main https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
```

Confirm exactly what will be packaged:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
cat VERSION
```

The tracked source tree must be clean. `BUILD.sh` refuses tracked uncommitted changes so the image provenance can identify a reproducible source commit.

A `main` build stores `main` as the appliance's future application update channel. A `dev` build stores `dev`. Experimental branches fall back to `dev` rather than becoming permanent appliance update channels.

## 🩺 Run the builder doctor

From the repository root:

```bash
bash os/builder/DOCTOR.sh
```

The doctor checks, among other things:

- required host commands
- 4K kernel page size
- pinned pi-gen commit
- required YWD OS stages
- current application source required by the image
- clean tracked Git state

Do not proceed until it ends with:

```text
Doctor checks passed.
```

## 🅰️ Build a factory/unconfigured image

This is the cleanest image to distribute or test as a first-time appliance.

Make sure no builder-local Wi-Fi provisioning file exists:

```bash
rm -f os/local/provision.env
```

Then build:

```bash
bash os/builder/BUILD.sh
```

The builder will:

1. verify the current application source and provenance
2. clone/reuse the local pinned `pi-gen` checkout
3. stage the YWD headless/network/runtime/firstboot/polish layers
4. inject current root application/OLED/console assets
5. run Python/shell and optional JavaScript preflight checks
6. create or reuse a builder-local development SSH key
7. run `DOCTOR.sh`
8. build Raspberry Pi OS Lite + the current YWD source
9. build the pinned MMDVM-Host and DMRGateway inside the armhf rootfs
10. compress the image
11. generate SHA-256 checksums
12. run `xz -t` against `.img.xz` output

The original Pi Zero is the appliance target, but the image itself is normally built on a faster Linux machine.

## 🅱️ Build with Wi-Fi preseeded

For a development image that should try a known Wi-Fi network immediately:

```bash
bash os/builder/CONFIGURE-WIFI.sh
```

The helper writes only to:

```text
os/local/provision.env
```

`os/local/` is ignored by Git. Protect it because it contains the Wi-Fi credential used for that image.

Then build normally:

```bash
bash os/builder/BUILD.sh
```

On first boot the network manager tries the embedded Wi-Fi profile. If the network is unavailable or the connection fails, the appliance falls back to the setup AP.

**Wi-Fi preseeding does not complete hotspot setup.** Callsign, DMR ID, RF settings, BrandMeister credentials, dashboard password, optional BM API key, and the RF-enable choice still go through the secure first-boot wizard.

To return to a factory/no-Wi-Fi build:

```bash
rm -f os/local/provision.env
```

## 🔧 Optional builder variables

`BUILD.sh` supports a few environment overrides for build organization:

```bash
YWD_IMG_NAME=my-ywd-hotspot \
YWD_OS_VERSION=my-build-label \
YWD_OS_WORK_DIR=/path/to/work \
YWD_OS_DEPLOY_DIR=/path/to/deploy \
bash os/builder/BUILD.sh
```

If omitted, the builder uses its normal paths under `os/`.

These variables change build/output labeling and locations; they do not bypass the first-boot RF safety gate.

## 🔑 Builder-local SSH key

The builder creates or reuses:

```text
os/local/ywd-os-dev_ed25519
os/local/ywd-os-dev_ed25519.pub
```

Only the public key is embedded for the `ywd` account. The private key remains builder-local and must not be committed or casually distributed.

For development access after the image joins the LAN:

```bash
ssh -i os/local/ywd-os-dev_ed25519 ywd@ywd-hotspot.local
```

Treat the current image builder as a development/appliance-build tool. If images are distributed to unrelated operators, review the SSH-key provisioning policy before distribution.

## 📦 Build output

Successful output is written under:

```text
os/deploy/
```

or the `YWD_OS_DEPLOY_DIR` override.

Look for:

```text
*ywd-hotspot-os*.img.xz
SHA256SUMS-YWD-HOTSPOT-OS
```

The builder verifies `.img.xz` integrity before reporting completion.

You can re-check manually:

```bash
cd os/deploy
sha256sum -c SHA256SUMS-YWD-HOTSPOT-OS
xz -t ./*.img.xz
```

## 💾 Flash the image

Use Raspberry Pi Imager's **Use custom** image option or another image-writing tool that accepts the generated `.img.xz` / `.img` file.

Double-check the destination device before writing an image. The build system intentionally stops at producing/verifying the image; it does not automatically overwrite an SD card.

## 📶 First boot — no Wi-Fi preseed

With no saved station profile, the Pi waits briefly and then starts a setup AP named similar to:

```text
YWD-Hotspot-ABCD
```

The suffix is derived from the Wi-Fi interface MAC address.

Connect a phone/computer to that AP and browse to:

```text
http://10.42.0.1/
```

Choose/enter the desired Wi-Fi network. The single Pi Zero Wi-Fi interface switches from AP mode to station mode when the handoff succeeds.

## 🔒 Secure first-boot wizard

Once station Wi-Fi is online, the OLED shows a six-digit setup code and the secure setup service becomes available at:

```text
https://ywd-hotspot.local:8443/
```

The service uses a locally generated self-signed certificate, so the browser may show a certificate warning on first access. Verify you are connecting to the local hotspot before continuing.

The setup code is short-lived (roughly 30 minutes) and the setup session also expires.

The wizard finalizes the canonical configuration and control credentials. It requires a real callsign and DMR ID before completion and can configure the normal station/radio/BrandMeister settings, including the local dashboard password and optional BrandMeister API key.

On the final step, the operator chooses whether RF should be enabled. RF remains disabled unless setup explicitly requests it.

After completion the normal dashboard is available at the configured port, normally:

```text
http://ywd-hotspot.local:8080/
```

## ✅ First-boot verification

After setup, verify from SSH or the local console:

```bash
ywd-hotspotctl status
ywd-hotspotctl source

systemctl is-active ywd-dashboard.service
systemctl is-active ywd-headless-oled.service
systemctl is-active ywd-oled.service
systemctl --failed --no-pager
```

On YWD-Hotspot OS, expected OLED ownership is:

```text
ywd-headless-oled.service  active
ywd-oled.service           inactive
```

RF service state depends on the final setup choice.

If RF was enabled, also verify BrandMeister and real radio traffic before calling the image known-good.

## 🔄 Updates after imaging

The image contains both:

```text
/opt/ywd-hotspot/app
/opt/ywd-hotspot/repo
```

The packaged runtime identifies the source commit used for the image. Future application updates use the saved `main` or `dev` channel and do **not** require rebuilding or reflashing the image.

CLI:

```bash
sudo ywd-hotspotctl update --check
sudo ywd-hotspotctl update --dry-run
sudo ywd-hotspotctl update
```

Or use **ABOUT → SOFTWARE UPDATE** after unlocking WebUI controls.

## ♻️ Rebuilding

Normal repeated builds may reuse the builder's pinned `os/.pi-gen/` checkout and builder-local SSH key. `BUILD.sh` resets/cleans the pi-gen tree to the pinned revision and recreates the work directory for each build.

Private/local paths are ignored by Git:

```text
os/.pi-gen/
os/work/
os/deploy/
os/local/
os/build/
os/cache/
```

If a build behaves strangely, run the doctor again before deleting caches blindly.

## 🧪 Physical acceptance checklist

A successful compile is not enough. Before calling an image known-good, verify:

```text
[ ] DOCTOR.sh passes
[ ] BUILD.sh completes
[ ] checksum verification passes
[ ] xz integrity test passes
[ ] Pi Zero boots
[ ] OLED boot/network/setup screens work
[ ] factory image creates setup AP when expected
[ ] Wi-Fi-preseed build joins Wi-Fi or cleanly falls back to AP
[ ] http://10.42.0.1/ Wi-Fi handoff works
[ ] OLED six-digit secure setup code appears
[ ] https://ywd-hotspot.local:8443/ wizard works
[ ] real callsign/DMR ID/config apply successfully
[ ] dashboard password works
[ ] optional BrandMeister API key works if configured
[ ] RF remains off until explicitly enabled
[ ] dashboard loads after setup
[ ] BrandMeister connects when configured
[ ] handheld → hotspot RF works
[ ] hotspot → handheld RF works
[ ] Parrot works
[ ] ywd-headless-oled.service is active
[ ] ywd-oled.service is inactive
[ ] reboot preserves setup/config
[ ] CLI update check/dry-run works
[ ] About-page update works
[ ] systemctl --failed is clean
```

## 🧯 Common build problems

### Doctor reports the wrong page size

The armhf builder requires a 4K-page host kernel. Fix the host kernel selection, reboot, and verify:

```bash
getconf PAGE_SIZE
```

returns `4096`.

### Tracked source is dirty

Commit or stash intended source changes before building:

```bash
git status --short
git diff
git diff --cached
```

The builder intentionally refuses a dirty tracked tree.

### No image appears

Inspect the pi-gen output and `os/deploy/`. `BUILD.sh` fails if pi-gen finishes without finding a matching deploy image.

### Wi-Fi preseed is wrong

Re-run:

```bash
bash os/builder/CONFIGURE-WIFI.sh
```

or remove it for a factory build:

```bash
rm -f os/local/provision.env
```

The setup AP remains the recovery path if station Wi-Fi cannot be established.

---

**Related:** [Installation](INSTALL.md) · [OS development notes](OS-DEVELOPMENT.md) · [OS builder source](../os/README.md)
