# Phase 3H next step: persistent RX/audio stream

The precomputed-tone observation eliminated fake backend PCM generation and AF_UNIX connect churn as the dominant bottlenecks. The next architecture should remove the high-frequency browser poll/decode request loop.

Target path:

MMDVM voice tap -> trusted core RX stream worker -> external YWD Vocoder Protocol v1 backend -> bounded PCM chunks -> one persistent browser-side stream -> Web Audio.

Constraints:

- MMDVM-Host remains sole RF/modem owner.
- No AMBE software vocoder is distributed inside RX Monitor.
- RX Monitor absent/disabled: no RX stream worker or vocoder runtime.
- RX audio stopped: vocoder backend must be allowed to idle-exit.
- RF wins: bounded queues; stale audio is dropped rather than backpressuring RF.
- Preserve Alpha15 browser call selection, route filtering, bounded playout and diagnostics where applicable.
- Keep trusted host bridge; sandboxed plugin gets no direct network access.

The first streaming implementation should use the fake backend and prove continuous tone over a long busy DMR call before any real decoder backend is introduced.
