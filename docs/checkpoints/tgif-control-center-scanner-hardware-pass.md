# TGIF Control Center Scanner Hardware Acceptance

Date: 2026-08-30

This checkpoint records real-hardware acceptance of the YWD-Hotspot TGIF Control Center watchlist scanner on the mature RC4 test appliance.

## Accepted implementation

Scanner implementation source tested on the appliance:

- `fdd175846c14c0c2184ede942b5bb0f1f6a3c2c0`

The later branch checkpoint commits up through this document are documentation-only relative to that tested scanner implementation.

## Hardware/runtime acceptance

The following behavior was physically exercised and accepted:

- dedicated TGIF tab renders when TGIF is enabled;
- TGIF directory search resolves service talkgroups omitted by the public export, including Parrot `9990`;
- Parrot is presented as TGIF `9990` with RF destination `5009990`;
- `TUNE` changes the TGIF network session without starting the scanner and leaves visible `TUNED` state;
- appliance-persistent TGIF favorites work;
- watchlist scanner starts only on explicit operator request and remains a static/non-boot-enabled systemd service;
- two-entry watchlist scanned successfully between TGIF `31665` (`TGIF The Mothership`, RF `5031665`) and TGIF `9990` (`Parrot`, RF `5009990`);
- configured dwell was 5 seconds;
- configured post-call hold was 3 seconds;
- scanner rotated sessions as expected;
- scanner held the watched talkgroup when matching TGIF network traffic was received;
- post-call hold behavior worked as expected;
- BrandMeister and TGIF remained connected simultaneously while scanning;
- MMDVMHost and DMRGateway remained active;
- no failed systemd units were present.

Observed accepted runtime snapshot included:

```text
Service active : True
State          : scanning
Current TG     : 31665
Current RF TG  : 5031665
Hold reason    : None
Watch entries  : [(31665, 'TGIF The Mothership'), (9990, 'Parrot')]
Dwell          : 5
Post-call hold : 3

BrandMeister : connected
TGIF         : connected
MMDVMHost    : active
DMRGateway   : active

0 loaded units listed.
```

The scanner journal showed normal explicit start/stop/start lifecycle with no service failure.

## Accepted safety boundary

This checkpoint preserves the intended scanner boundary:

- scanner changes the TGIF network session through the TGIF session-update mechanism;
- scanner does not synthesize an RF key-up to change talkgroups;
- MMDVM-Host remains the only modem/RF owner;
- DMRGateway routing remains the proven BrandMeister + TGIF routing model;
- incoming matching TGIF network traffic takes precedence over the dwell timer;
- favorites/watchlist are appliance state, not browser-local state;
- active scanning does not automatically start at boot.

## Follow-up work

The scanner itself is hardware-accepted at this checkpoint. Follow-up work may add backup/restore preservation for TGIF Control Center preferences and UI/behavior polish, but should preserve this accepted network/RF boundary unless a later hardware-tested design explicitly replaces it.
