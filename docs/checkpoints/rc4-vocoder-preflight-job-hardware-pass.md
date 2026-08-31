# RC4 Vocoder Preflight Background Job — Hardware PASS

Date: 2026-08-31

The mature Pi Zero W YWD-Hotspot hardware gate accepted the first guarded DMR Audio Vocoder background-job path.

Observed real-appliance result:

- job type: `vocoder-preflight`;
- final state: `COMPLETE`;
- progress: `100`;
- worker result: `success`, `ExecMainStatus=0`;
- worker returned to `inactive/dead` after completion as intended;
- maintenance lease released cleanly (`IDLE — no active maintenance lease`);
- zero failed systemd units;
- YWD Extended was verified ready on `armv6l`;
- free space was healthy;
- required build tools were present;
- package manager was idle and dpkg clean;
- approved pinned mbelib source was reachable;
- system temperature was healthy;
- no package install, source build, RF restart, runtime activation, or backend replacement occurred.

The bounded persistent transcript proved browser-independent job execution under `/var/lib/ywd-hotspot/vocoder/`.

A presentation defect was found during this gate: the dashboard provided poor visible feedback while the approximately 30-second exact runtime/source preflight checks were running. That did **not** invalidate the backend job pass. The follow-up implementation moves heavyweight exact runtime verification exclusively into the background worker, keeps normal dashboard polling on the persisted current-pin runtime identity, uses a short active-job cache, and renders an immediate local `CHECKING / JOB ACCEPTED` state after launch.

This checkpoint accepts the background-job/maintenance-lease mechanics only. Actual package installation, mbelib source checkout/build, YWD Extended build/activation, and vocoder installation remain gated off until later hardware acceptance.
