# RC4 Dashboard Startup Recovery Hardware Pass

Date: 2026-08-31

Hardware gate: mature YWD-Hotspot Raspberry Pi Zero appliance.

Accepted recovery baseline:

- `62d3a15c18b2cf6d8b8b696f18053cc3f296deeb`

Observed result:

- Dashboard loaded successfully again after removing the RC4 startup-readiness interception, preload experiment, and generated legacy UI bundle experiment.
- The proven dependency-ordered dashboard loader is the accepted startup baseline for continued RC4 work.
- DMR Audio Vocoder manager/background preflight foundation remains installed and is not itself responsible for the global dashboard startup regression.
- MMDVM/vocoder inventory remains lazy and must not add heavyweight verification work to initial Status-page startup.

Guardrail for continued work:

- Do not rewrite, preload, bundle, or intercept the proven base dashboard module loader as part of vocoder-manager work.
- Any splash-timing refinement must stay local to the existing splash lifecycle in `web/app.js` and must not alter module execution semantics.
