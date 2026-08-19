# Alpha22.3 RX Voice Bridge Pacing Fix

Phase 3E live browser audio proved that AMBE recovery and browser decode work, but a busy network test produced heavily choppy audio.

The attached test capture recovered every AMBE frame with zero sequence gaps and zero unrecoverable frames, while 500 recovered AMBE frames (10.00 seconds nominal audio) were assigned bridge receive timestamps spanning roughly 29.8 seconds.

Root cause: `mmdvm_voice_bridge.py` combined `selectors` with a buffered text `readline()`. A text wrapper may prefetch several MQTT lines into userspace while the selector only reports kernel-level readability. Extra complete lines could therefore remain buffered until more kernel data arrived, creating artificial 100-400 ms delivery gaps.

Alpha22.3 changes only the first-party passive voice bridge subscriber path:

- `mosquitto_sub` stdout is binary and unbuffered.
- the pipe fd is non-blocking.
- selector wakeups drain all currently available bytes with `os.read()`.
- every complete newline-delimited MQTT record already available is parsed in the same wakeup.
- the trusted runtime ring, capability checks, RF ownership model, MMDVM voice tap, DMRGateway, BrandMeister TG controls, and Plugin UI sandbox remain unchanged.

The existing RX Monitor v0.4.0-alpha1 can be re-tested after this core update. A successful test should show substantially smoother live NETWORK audio and bridge receive cadence much closer to the DMR stream rate.
