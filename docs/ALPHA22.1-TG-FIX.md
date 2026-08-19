# 0.1.0-alpha22.1-dev

Duplex BrandMeister talkgroup-control fix layered on the physically proven Alpha22 RX Monitor Phase 3B checkpoint.

- static TG add/remove now carries explicit BrandMeister timeslots in duplex mode
- Talkgroup Manager plans track `(timeslot, talkgroup)` routes instead of TG numbers alone
- multiple static TGs can coexist on a duplex timeslot without the last add replacing the previous route
- the same TG can be planned independently on TS1 and TS2
- current static/dynamic pills show their timeslot
- Control-page static add gets TS1/TS2 selection in duplex mode
- DROP QSO and DROP ALL DYNAMIC target both duplex timeslots
- simplex behavior remains slot 0
- no MMDVM-Host, DMRGateway, voice-tap, or RX Monitor code changes
