# RC3 final dashboard wiring fix

## Scope

During the final factory-image build window, the already-updated Raspberry Pi Zero appliance was used as a live audit target. The appliance was confirmed to be running the exact accepted RC3 source commit, but two late-RC3 dashboard features were not visible:

- the About-page software channel switcher for `main`, `dev`, and `dev-plugins`;
- the System-page MODEM / MMDVM inventory card.

This was not a stale checkout or stale deployed application. The managed checkout, `/opt/ywd-hotspot/app`, and build provenance all matched. The MMDVM inventory API was live, while `/modem-ui.js` returned 404.

## Root cause

Both feature modules existed in the source tree, but their browser wiring was implicit and fragile. `dashboard_backup.py` concatenated `ssh-key-export.js`, `modem-ui.js`, and `update-branch.js` onto the unrelated `/backup-restore.js` response. The main dashboard bootstrap did not explicitly load the MMDVM or software-channel modules, and they did not have explicit static routes in the normal release UI path.

Both modules also created `<style>` elements at runtime. YWD-Hotspot's dashboard CSP uses `style-src 'self'`, so late-RC3 feature styling must be shipped as external same-origin CSS rather than inline style injection.

## RC3 correction

The final RC3 candidate now:

- serves `/modem-ui.js` and `/update-branch.js` explicitly;
- bootstraps those modules explicitly from the normal `/app.js` release response;
- moves their styles into `web/modem-ui.css` and `web/update-branch.css` and bundles those same-origin styles into `/style.css`;
- makes `/backup-restore.js` single-purpose again instead of using backup/restore as a hidden carrier for unrelated UI modules;
- preserves the existing authenticated branch inventory/check/switch backend and read-only MMDVM inventory API;
- extends candidate validation so missing release UI modules, routes, backend dispatch, or CSP-safe styles fail the candidate gate;
- audits the other intentional non-obvious UI compositions: startup-theme bundling, transactional plugin-package overlay, and sandboxed plugin UI runtime;
- refreshes `MANIFEST.txt` so late-RC3 runtime/UI helpers are represented in release provenance.

## Safety boundary

This correction is dashboard/static-route/validation/documentation only. It does not change:

- MMDVM-Host source, extension patch, or build behavior;
- DMRGateway source/build behavior;
- RF frequencies, modem configuration semantics, or RF service policy;
- BrandMeister transport behavior;
- plugin/vocoder runtime behavior;
- first-boot provisioning semantics;
- the normal GitHub updater transaction implementation.

The software-channel switcher exposes the already-existing guarded branch-switch backend; it does not add a new update mechanism.

## Required pre-image acceptance

Before advancing the RC3 release branch again, verify on an updated appliance:

1. candidate validation and syntax checks pass;
2. `/modem-ui.js`, `/update-branch.js`, `/modem-ui.css`, and `/update-branch.css` return HTTP 200;
3. `/api/system/modem` continues returning HTTP 200;
4. System shows the MODEM / MMDVM card and REFRESH INFO works;
5. About shows CHANGE CHANNEL in SOFTWARE UPDATE;
6. CHANGE CHANNEL is unavailable while controls are locked and active after unlock;
7. the channel modal lists `main`, `dev`, and `dev-plugins` and can inspect their heads;
8. no actual branch switch is required merely to accept the presentation/wiring fix;
9. dashboard and RF services remain healthy with zero failed units.

After that appliance acceptance, freeze a new immutable RC3 pre-image checkpoint at the exact tested commit and build the public factory image from that same commit.
