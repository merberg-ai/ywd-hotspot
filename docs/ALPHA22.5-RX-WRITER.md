# Alpha22.5 — RX voice snapshot writer isolation

Alpha22.5 is a narrow live-RX transport build. It does not change MMDVM-Host,
DMRGateway, RF configuration, duplex talkgroup routing, the MMDVM voice tap, or
plugin capabilities.

## Change

The trusted `mmdvm_voice_bridge.py` no longer serializes/replaces the complete
bounded `voice.json` ring in the MQTT ingestion interpreter.

- The foreground process remains responsible for the non-blocking
  `mosquitto_sub` drain, validation, timestamping, and sequence assignment.
- A separate nice'd Python writer process owns the bounded runtime ring.
- Ingest forwards compact frame/status events to that writer.
- The writer coalesces snapshots to at most 10 Hz while maintaining the existing
  one-second heartbeat when idle.
- Full-ring `json.dump()` and atomic replace therefore cannot hold the ingest
  process GIL while new voice bursts are waiting in the MQTT subscriber pipe.
- The public bridge status now exposes `writer`, `snapshot_write_ms`, and
  `snapshot_write_max_ms` for diagnostics.

The runtime file schema remains schema 1 and the capability-gated DMR voice API
is unchanged.

## Test target

Pair with RX Monitor `0.4.0-alpha3` and test NETWORK audio using AUTO, then TS1
and TS2 manually, beginning at a 160 ms jitter buffer. Compare underruns and
capture timestamp gaps against Alpha22.4/alpha2.
