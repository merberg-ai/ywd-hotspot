# Alpha22.6 — WebUI and plugin polish

Alpha22.6 is a presentation/package-management polish build on top of the physically proven Alpha22.5 RF and DMR voice runtime. It does not change MMDVM-Host, DMRGateway, the MMDVM voice tap, the Alpha22.5 voice bridge/writer, duplex configuration, or BrandMeister routing behavior.

## Alpha22.6.1 updater hotfix

The first Alpha22.6 candidate correctly removed the retired `mmdvm-live-telemetry` package, but `UPDATE.sh`, `INSTALL.sh`, and `MANIFEST.txt` still treated that package as required source. WebUI update validation therefore stopped safely before touching the live application with `Update source missing .../mmdvm-live-telemetry/plugin.json`.

Alpha22.6.1 removes those stale package requirements, explicitly validates that the retired package is absent from the service-plugin catalog, and leaves the core `ywd-mmdvm-telemetry.service` infrastructure unchanged. The failure happened before plugin quiesce/application replacement, so the prior live RF/runtime was not modified by the failed attempt.

## Confirmation UI

- `DROP QSO` now uses the YWD in-app confirmation dialog instead of a browser-native `confirm()` dialog.
- The existing confirmation audit was rechecked. Internal navigation away from dirty Settings already uses the YWD modal, as do update, backup/restore, plugin lifecycle, RF runtime, calibration, and destructive talkgroup actions.
- Browser/tab close or reload with dirty Settings intentionally remains the browser-provided `beforeunload` prompt; browsers do not allow that prompt to be replaced safely with custom markup.

## Plugin upload/install review

The `.ywdplugin` upload flow is split into explicit stages:

1. client-side package preparation;
2. upload with a real request progress bar;
3. archive + signature verification on the hotspot;
4. a YWD review modal showing plugin identity, version, description, type, trust/signature state, RF ownership, provider/service information, and requested capabilities;
5. explicit `INSTALL PLUGIN` or `CANCEL`.

Upload no longer implicitly feels like installation. A successful upload leaves the package available until the operator explicitly confirms installation. Installation still does not enable the plugin.

## MMDVM Live Telemetry plugin retirement

The old `mmdvm-live-telemetry` service-plugin package has been retired. It was only a sandboxed journal adapter reading the already-existing core telemetry snapshot; it did not provide telemetry to the dashboard.

The core `ywd-mmdvm-telemetry.service`, trusted telemetry bridge, runtime snapshot, dashboard telemetry consumers, and RX Monitor/voice path remain intact.

During an update, the existing plugin update-safety helper quiesces plugin services before application replacement. Because the retired package is absent from the target catalog, restore leaves it disabled rather than restarting it.

## Paired RX Monitor candidate

RX Monitor `0.4.0-alpha6` is the UI-polish companion candidate. Its proven alpha5 decoder, AUTO selection, reservoir controller, 100 ms chunk scheduler, FEC path, and browser audio behavior are unchanged. Alpha6 adds only a presentation controller:

- one animated `START AUDIO` / `STOP AUDIO` toggle;
- cleaner RX audio heading/copy;
- technical audio counters collapsed under Advanced Audio Stats;
- capture/FEC and raw frame diagnostics collapsed by default;
- obsolete experimental/debug-facing notes removed from the normal view.

The Alpha22.5 + RX alpha5 proof checkpoint remains immutable at `checkpoint-alpha22.5-rx3e-alpha5-live-audio-proven`.
