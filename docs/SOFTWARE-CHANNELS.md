# Software Channels and WebUI Branch Switching

YWD-Hotspot exposes three approved first-party software channels in the dashboard:

- `main` — the primary supported/public release channel;
- `dev` — active integrated development;
- `dev-plugins` — isolated plugin/runtime development when intentionally needed.

After the 0.2.0-rc3 release, all three approved channels were realigned to the same post-release RC3 documentation baseline. `dev` is the normal place to begin new integrated development. `dev-plugins` should diverge only for deliberate plugin/framework work and should be re-aligned after that work is integrated.

The WebUI intentionally does **not** accept arbitrary branch names. Release, checkpoint, builder, and other engineering refs remain available only through the existing SSH/CLI updater workflow. This preserves release/image acceptance workflows without exposing engineering refs to normal appliance users.

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

The selected branch also gets channel-specific warnings. Development channels are clearly identified as development/experimental lines, and backward/diverged transitions receive stronger warnings.

## Exact-commit channel adoption

Two approved branches can point at the same commit. If the selected branch head is already the exact installed commit, YWD-Hotspot does not reinstall the application. It only:

1. moves the managed checkout to that exact approved branch head;
2. sets the branch upstream to `origin/<branch>`;
3. atomically saves the approved update channel;
4. updates build provenance to reflect the adopted branch/channel.

No RF service restart or application-file replacement is required for that case.

## Real branch transitions

If the selected branch points at a different commit, switching is treated as a full protected software transition rather than merely changing a preference file.

Before the live appliance is touched, the current updater performs a full candidate dry-run against the explicitly selected branch. If validation fails, the saved channel and installed application remain unchanged.

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

Protected rollback significantly reduces risk, but future newer features may create state that an older branch does not understand. For that reason downgrade and diverged-line transitions are explicitly warned as higher-risk operations.

## Authentication and branch allowlist

All branch inventory and branch-switch endpoints require the existing authenticated dashboard control session. Locking the dashboard disables/closes the branch selector.

The privileged WebUI helper accepts exactly:

```text
main
dev
dev-plugins
```

This allowlist is intentionally scoped to the WebUI privilege boundary. The underlying engineering CLI updater continues to accept explicit release refs needed for release/image acceptance testing.

## MMDVM behavior

Changing the application software channel does not mean flashing the physical MMDVM HAT. Normal application branch transitions also do not intentionally compile MMDVM-Host or DMRGateway. Host-runtime rebuild/update and physical HAT firmware maintenance remain separate guarded workflows in the System **MODEM / MMDVM** area.

## Release/history refs

Release branches, immutable tags, and a small number of retained proven checkpoints are audit/rollback references, not user-facing software channels. Redundant intermediate checkpoint branches should be pruned after a later immutable release or final checkpoint supersedes them; the commits remain in Git history.
