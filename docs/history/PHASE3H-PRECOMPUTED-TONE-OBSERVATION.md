# Phase 3H precomputed fake-tone observation

Physical observation on the Pi Zero test hotspot with RX Monitor Alpha15 and core commit `8908b103d2732842916edf20f98f6e721e6d17a2`:

- Persistent YWD Vocoder Protocol v1 transport active.
- `client_transport`: 2 connects, 83 requests, 81 reused requests in the captured run.
- Fake backend reports `tone_generation: precomputed-period`.
- Fake PCM generation cost observed at about 0.071 ms last / 1.749 ms max.
- Browser RX audio reached LIVE with 240 ms buffer.
- Decode RTT observed around 60 ms current / 302 ms max in the captured frame.
- Underrun counter was 47 in the captured run; therefore the transport/backend itself is no longer the dominant steady-state cost, but intermittent delivery/scheduling stalls remain.

Interpretation: persistent AF_UNIX reuse and precomputed fake-tone generation are working. Remaining sustained-RX instability should be investigated in the voice-ring / dashboard delivery path or replaced with a persistent live stream rather than hidden with larger jitter buffers.
