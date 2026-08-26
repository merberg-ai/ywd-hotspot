# RC3 final source-install and first-boot restore fixes

This note records the narrow final fixes being validated before the YWD-Hotspot 0.2.0-rc3 factory image is built.

## Source installer terminal prompts

`INSTALL.sh` must leave the interactive `INSTALL-core.sh` attached directly to the operator terminal. The interactive configuration wizard must not be piped through the normal output colorizer because doing so can break terminal input/echo behavior over SSH or console sessions.

Expected source-install behavior:

- entered values are visible for normal non-secret prompts;
- displayed defaults remain visible;
- prompts without a usable default are marked `[required]`;
- secret values use `getpass` and therefore intentionally do not echo;
- the configuration banner reports the current YWD-Hotspot version rather than an old alpha label.

## Dashboard control password

A fresh source install must not finish with WebUI write controls impossible to unlock.

After the canonical hotspot configuration is saved/generated, `lib/configure.py` checks the separate dashboard credential. If no dashboard control password exists, it prompts for one and confirmation using `lib/web_auth.py`.

The dashboard password is separate from:

- the BrandMeister Hotspot Security password; and
- the optional BrandMeister API key.

If a dashboard credential already exists, configuration/recovery preserves it rather than forcing a replacement.

Existing installs can set or replace it at any time with:

```text
sudo ywd-hotspotctl web-password
```

or from the interactive control console using **Web control password**.

## First-boot `.ywdsettings` restore feedback

The secure first-boot restore page now provides explicit feedback for both restore phases.

### Decrypt & Verify

The browser shows:

- a busy spinner on the verify button;
- actual HTTP upload progress for the encrypted backup request;
- percentage/progress-bar feedback while bytes are uploading;
- status text after upload while the Pi decrypts/authenticates/validates the backup;
- visible success or failure feedback.

### Restore Hotspot

The apply phase similarly shows:

- a busy spinner on the restore button;
- upload progress for the verified encrypted backup request;
- status text while the Pi applies settings and service state;
- explicit success/failure feedback.

These are presentation/progress changes around the existing authenticated restore endpoints. They do not alter the backup encryption format, restore transaction semantics, RF permission policy, MMDVM runtime, or DMRGateway behavior.

## RC3 validation scope

Before freezing the final RC3 source candidate:

1. source install on the Pi 5 must complete with usable terminal prompts;
2. a fresh source configuration must create a dashboard control password and unlock WebUI controls;
3. first-boot restore must visibly report upload, verify/process, and apply phases;
4. candidate syntax/source validation must pass;
5. the final factory image is built only after these fixes are accepted.
