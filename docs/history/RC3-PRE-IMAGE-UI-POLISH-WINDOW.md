# RC3 Pre-Image UI Polish Window

RC3 is not yet finally accepted or published.

The previously frozen candidate `release/0.2.0-rc3` at `cba7648d1428c07ee7592be8f423d88ae5568c99` passed the appliance/runtime regression. A small UI-only polish window was then intentionally reopened on `dev` before the final image test.

The UI batch was physically accepted on the running hotspot and is now eligible for inclusion in the final RC3 candidate. Final image/updater artifact acceptance is still outstanding.

The accepted UI changes remain narrowly scoped and do not intentionally alter RF/runtime behavior, MMDVM/DMRGateway pins, plugin lifecycle semantics, vocoder behavior, updater policy, or factory-image safety.

## UI polish batch — PHYSICALLY ACCEPTED

All items below were implemented for both mobile and desktop. Touch targets, keyboard focus, narrow-screen layout, and `prefers-reduced-motion` behavior are part of the design.

1. **Branded dashboard startup/loading overlay — PASS**
   - appears while the dashboard populates in the background;
   - dark YWD/cyber styling;
   - animated RF-style orbiting rings and center pulse rather than a generic spinner;
   - `LOADING YWD HOTSPOT` with synchronization/status text;
   - dismisses after initial status data, initial config data, and required UI-polish hooks are ready rather than after a fixed cosmetic delay;
   - smooth fade into the populated dashboard;
   - 12-second fail-safe so an optional UI failure cannot trap the browser behind the loader;
   - respects `prefers-reduced-motion`.

2. **Blocking Save / Save & Apply transaction modal — PASS**
   - blocks background interaction while settings are being written/applied;
   - prevents duplicate Save / Save & Apply submissions through the blocking transaction state;
   - uses the matching RF/data ring treatment;
   - stage-aware text covers saving, applying, affected-service restarts, and dashboard restart/reconnect;
   - no fake percentage/progress values;
   - short success confirmation before returning control;
   - persistent readable error state with an explicit Close control;
   - active writes cannot be dismissed by clicking outside the modal;
   - same-port dashboard restart uses status polling/reload; changed WebUI port redirects to the returned port;
   - respects `prefers-reduced-motion`.

3. **Responsive cyber-style checkbox replacement — PASS**
   - keeps the real checkbox inputs and existing data binding/semantics;
   - replaces native checkbox chrome with a dark pill/slider switch;
   - cyan energized ON state, subdued OFF state, clear disabled state and keyboard focus halo;
   - full label row remains clickable;
   - mobile sizing provides an approximately 44px+ touch target;
   - shared `.field.check` treatment covers core Settings, OLED/instrumentation booleans, and plugin boolean configuration fields.

Physically accepted UI functional commit:

```text
6593687a5ec477609483ec8cd6eaa3386bcbec7b
```

## Required acceptance after UI polish

The next step is the final RC3 image/updater acceptance. Before public promotion, the exact final candidate must still pass:

1. candidate validation and quick appliance/source sanity for the final ref;
2. published `0.2.0-rc2` -> exact final RC3 updater test, including proof that the ordinary application updater does not silently recompile MMDVM-Host or DMRGateway and that legacy RC2 YWD Extended is recognized correctly;
3. explicit YWD Extended refresh to the current demand-gated RC3 patch where required;
4. exact RC3 factory-image build;
5. fresh flash / first boot / setup / duplex RF / BrandMeister / plugin + external vocoder / reboot / zero-failed-units acceptance on the image;
6. only after exact-artifact acceptance: immutable RC3 proven checkpoint, `main` promotion, and public `v0.2.0-rc3` tag.

Until those tests pass, `main`, the public RC3 tag, and the immutable proven RC3 checkpoint must remain untouched.
