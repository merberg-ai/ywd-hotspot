# RC4 Vocoder Staged Build — Hardware Pass

Date: 2026-08-31

This checkpoint records physical Raspberry Pi Zero acceptance of the RC4 managed DMR Audio Vocoder staged-build gate.

## Accepted behavior

The System-page `PREPARE VOCODER CANDIDATE` workflow successfully:

- ran the guarded exact-runtime/appliance preflight;
- verified the installed current YWD Extended runtime;
- fetched the approved upstream mbelib source at commit `9a04ed5c78176a9965f3d43f7aa1b1f5330e771f`;
- configured and built mbelib in Release mode with one build job;
- compiled the YWD Vocoder Protocol v1 native adapter as the unprivileged background worker;
- ran the staged 10-frame decode self-test;
- produced 3200 bytes of PCM for the self-test;
- cached the verified candidate under `/var/lib/ywd-hotspot/vocoder/build-cache/candidates/`;
- released the appliance maintenance lease cleanly;
- exited the worker successfully with zero failed systemd units.

## Candidate identity

Prepared candidate:

```text
SHA-256: af7679ae4ba405ca09986cd71eeb778f56450259749ca23d6e45b7ffc5161c41
architecture: armv6l
compiler: g++ (Raspbian 14.2.0-19+rpi1) 14.2.0
recipe: mbelib-v1 / 1
protocol: 1
mbelib: 9a04ed5c78176a9965f3d43f7aa1b1f5330e771f
self-test: PASS · 10 frames · 3200 PCM bytes · mbelib 1.3.0
```

The direct staged binary self-test also passed independently after the managed job completed.

## Live-runtime preservation proof

The installed live vocoder binary SHA-256 before preparation was:

```text
9e48c7f64cce9389eb757ebba7cacdded9c2042fe710cb02c70cec9e6bdcca33
```

The installed live vocoder binary SHA-256 after preparation was identical:

```text
9e48c7f64cce9389eb757ebba7cacdded9c2042fe710cb02c70cec9e6bdcca33
```

Live services remained in their expected states throughout/following the build:

```text
ywd-vocoder-mbelib.socket   active
ywd-vocoder-mbelib.service  inactive (normal dormant socket-activated backend)
ywd-mmdvmhost.service       active
ywd-dmrgateway.service      active
```

The maintenance lease returned to `IDLE`, the worker reported `Result=success / ExecMainStatus=0`, and `systemctl --failed` reported zero failed units.

## UI follow-up discovered during the pass

The hardware pass exposed one presentation defect: the generic dashboard `.ctl` refresh could briefly re-enable `CHECK INSTALL READINESS` while the staged prepare/build job was still active. The backend correctly rejected conflicting maintenance, but the UI should never present that control as available.

The follow-up fix removes vocoder job controls from the generic `.ctl` ownership path and leaves their enabled/disabled state under the vocoder manager's combined dashboard-auth + maintenance/job state machine. Dashboard lock/unlock changes are observed separately so the controls still react immediately to authentication state.

## Gate status

The staged-build safety gate is **accepted**.

This checkpoint does **not** accept live backend activation, installation, rollback, YWD Extended replacement, package installation, socket-unit mutation, or RF service interruption. Those remain separate future hardware gates.
