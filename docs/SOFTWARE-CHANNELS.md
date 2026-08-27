# Software Channels and WebUI Branch Switching

YWD-Hotspot exposes three approved first-party software channels in the dashboard:

- `main` — the primary supported public/update line;
- `dev` — active YWD-Hotspot development;
- `dev-plugins` — plugin/runtime integration development.

The WebUI intentionally does **not** accept arbitrary branch names. Release, checkpoint, builder, and other engineering refs remain available only through the existing SSH/CLI updater workflow.

## Current RC3 branch state

After `0.2.0-rc3` publication, `main` and `dev` are intentionally aligned on RC3 code plus the post-release documentation refresh. The immutable release identity remains:

```text
v0.2.0-rc3
3823140b9fd4d6e73fe9066af4b2280628f62f5e
```

Future development may move `dev` ahead again. A moving channel head never changes the source represented by an existing release tag.

`dev-plugins` may intentionally diverge for isolated plugin/framework work and should not be silently forced to follow ordinary docs/core housekeeping.

## Change Channel UI

When dashboard controls are unlocked, the **Software Update** card provides **CHANGE CHANNEL**. The custom modal shows:

- installed version and exact current commit;
- saved update channel;
- managed Git checkout branch and source state;
- the current GitHub head of each approved channel;
- target version, commit, date, latest commit subject, config schema, and whether that target contains plugin runtime support;
- the ancestry relationship between the installed commit and selected branch head.

Relationships are presented as:

- **CURRENT BUILD** — selected branch head is the exact installed commit;
- **FORWARD** — selected branch head descends from the installed commit;
- **DOWNGRADE** — selected branch head is an ancestor of the installed commit;
- **DIFFERENT LINE** — installed and selected heads have diverged;
- **UNKNOWN** — ancestry cannot be proven from the managed checkout.

Development channels are clearly identified as development/experimental lines, and backward/diverged transitions receive stronger warnings.

## Exact-commit channel adoption

Two approved branches can temporarily point at the same commit. If the selected branch head is already the exact installed commit, YWD-Hotspot does not reinstall the application. It only:

1. moves the managed checkout to that exact approved branch head;
2. sets the branch upstream to `origin/<branch>`;
3. atomically saves the approved update channel;
4. updates build provenance to reflect the adopted branch/channel.

No RF service restart or application-file replacement is required for that case.

## Real branch transitions

If the selected branch points at a different commit, switching is treated as a full protected software transition rather than merely changing a preference file.

Before the live appliance is touched, the updater performs a full candidate dry-run against the explicitly selected branch. If validation fails, the saved channel and installed application remain unchanged.

After successful preflight, a detached root-owned transient systemd service re-validates the same selected branch and runs the canonical GitHub updater with an explicit `--branch` argument. The existing updater remains responsible for:

- clean/canonical Git source checks;
- candidate validation;
- protected pre-update backup;
- configuration/credential preservation;
- plugin transition safety where applicable;
- service-policy preservation;
- rollback on failure;
- moving the managed checkout and saving the new channel only after a successful installation.

The shared update-status document is used, so the existing staged update/reconnect progress UI continues to work during a branch switch.

## Downgrades and diverged branches

A branch switch can be a downgrade. The UI must never describe branch selection as harmless channel metadata when the selected branch contains older application code.

Protected rollback significantly reduces risk, but future newer features may create state that an older branch does not understand. Downgrade and diverged-line transitions are therefore explicitly warned as higher-risk operations.

## Authentication and branch allowlist

All branch inventory and branch-switch endpoints require the existing authenticated dashboard control session. Locking the dashboard disables/closes the branch selector.

The privileged WebUI helper accepts exactly:

```text
main
dev
dev-plugins
```

This allowlist is intentionally scoped to the WebUI privilege boundary. The engineering CLI updater continues to accept explicit release refs needed for release/image acceptance testing.

## MMDVM behavior

Changing the application software channel does not mean flashing the physical MMDVM HAT. Normal application branch transitions also do not intentionally compile MMDVM-Host or DMRGateway. Host-runtime rebuild/update and physical HAT firmware maintenance remain separate guarded workflows in System **MODEM / MMDVM**.

RC3 specifically proved that the application updater can move a published RC2 appliance onto RC3 application code while correctly recognizing the historical Extended runtime rather than silently rebuilding it.

## RC3 acceptance

The software-channel UI was physically accepted before RC3 publication with controls both locked and unlocked. Acceptance confirmed:

- only `main`, `dev`, and `dev-plugins` are offered;
- current installed version/commit, saved channel and checkout branch are shown correctly;
- live branch inventory/relationship metadata loads correctly;
- the already-active branch cannot trigger an unnecessary switch;
- opening/refreshing the modal does not alter channel, checkout, RF state, configuration, plugins or services;
- release bootstrap/CSP wiring is present in the exact accepted RC3 source;
- MMDVMHost, DMRGateway and dashboard remain healthy with zero failed units.

A true future branch transition should still be acceptance-tested when it introduces new runtime behavior, especially across downgrade/diverged lines.
