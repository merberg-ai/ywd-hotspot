# RC4 SSH Client-Key UI Hardware Pass

Date: 2026-08-31

Accepted development checkpoint for the RC4 System/SSH cleanup.

## Accepted behavior

The mature Raspberry Pi Zero hardware gate passed with the RC4 SSH UI cleanup applied:

- the normal System/SSH card exposes only `CREATE & EXPORT SSH CLIENT KEY`;
- the normal WebUI no longer exposes `EXPORT SERVER IDENTITY`;
- the underlying SSH server host-key recovery implementation remains intact;
- the client-key action stays within the card on the mobile dashboard layout;
- the action is governed by the normal dashboard lock/unlock state;
- the action shows bounded `CREATING SSH CLIENT KEY…` busy feedback and blocks duplicate clicks;
- creating/exporting the client login key still completes successfully;
- existing SSH behavior remains healthy;
- the focused SSH policy/UI smoke passed on the appliance;
- no failed systemd units were introduced by this slice.

## Source checkpoint

Accepted source commit before this checkpoint document:

`53ecebd320e00f997c6b8cd80c356ec8cbdfd9d8`

This checkpoint does not move `main`, does not bump `VERSION`, and does not imply RC4 release/factory-image acceptance.
