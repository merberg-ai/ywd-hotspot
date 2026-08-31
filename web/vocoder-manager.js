'use strict';
(() => {
  const el = id => document.getElementById(id);
  let loading = false;
  let statusLoaded = false;
  let jobActive = false;
  let maintenanceActive = false;
  let launchPending = false;
  let launchedJobId = null;
  let pollTimer = null;
  let visibilityObserver = null;

  const stateTone = state => {
    const s = String(state || '').toUpperCase();
    if (s === 'READY') return 'good';
    if (['CHECKING','WAITING_FOR_APT','DOWNLOADING','BUILDING','STAGING','WAITING_FOR_RF_IDLE','ACTIVATING','VERIFYING','ROLLING_BACK'].includes(s)) return 'busy';
    if (['REPAIR_REQUIRED','FAILED_SAFE','ERROR'].includes(s)) return 'bad';
    return 'warn';
  };

  const text = (id, value) => {
    const node = el(id);
    if (node) node.textContent = value == null || value === '' ? '—' : String(value);
  };

  const shortSha = value => {
    const raw = String(value || '');
    return raw ? raw.slice(0, 12) : '—';
  };

  const stamp = value => {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return '—';
    try { return new Date(n * 1000).toLocaleString(); } catch (_) { return '—'; }
  };

  function systemVisible() {
    const page = el('system');
    return !!page && !document.hidden && page.classList.contains('on');
  }

  function policyText(policy) {
    if (!policy?.available) return 'UNAVAILABLE';
    const sched = String(policy.scheduling_policy || 'other').toUpperCase();
    return `Nice ${policy.nice ?? '—'} · CPUWeight ${policy.cpu_weight ?? '—'} · ${sched}${policy.ok ? ' · OK' : ' · CHECK'}`;
  }

  function runtimeText(runtime) {
    if (!runtime) return 'UNKNOWN';
    const variant = String(runtime.variant || 'unknown').toUpperCase();
    if (runtime.ready) return `${variant} · API ${runtime.extension_api ?? '—'} · READY`;
    if (runtime.upgrade_required) return `${variant} · UPDATE REQUIRED`;
    const missing = Array.isArray(runtime.missing_capabilities) ? runtime.missing_capabilities.length : 0;
    return `${variant} · ${missing ? `${missing} CAPABILITY GAP` : 'NOT READY'}`;
  }

  function socketText(backend) {
    if (!backend?.socket_exists) return 'NOT INSTALLED';
    return `${String(backend.socket_enabled || 'unknown').toUpperCase()} · ${String(backend.socket_state || 'unknown').toUpperCase()}`;
  }

  function selfTestText(doc) {
    const test = doc?.last_self_test;
    if (!test || typeof test !== 'object') return 'NOT RECORDED';
    const ok = test.ok === true ? 'PASS' : test.ok === false ? 'FAIL' : 'UNKNOWN';
    const when = stamp(test.completed_at || test.time || test.at);
    return `${ok} · ${when}`;
  }

  function maintenanceText(doc) {
    const m = doc?.maintenance || {};
    if (m.active) return `${String(m.job_type || 'maintenance').toUpperCase()} · ${String(m.phase || 'working').toUpperCase()}`;
    if (m.stale) return `STALE LEASE · ${String(m.stale_reason || 'CHECK REQUIRED').toUpperCase()}`;
    return 'IDLE';
  }

  function syncActionState() {
    const check = el('vocoderPreflight');
    if (!check) return;
    const unlocked = typeof state !== 'undefined' && !!state?.controls?.authenticated;
    const localBusy = check.dataset.ywdVocoderBusy === '1';
    const vocoderBusy = launchPending || jobActive;
    const blocked = maintenanceActive || vocoderBusy || localBusy;
    check.disabled = !unlocked || blocked;

    if (vocoderBusy && !localBusy) {
      check.classList.add('ywd-working');
      check.setAttribute('aria-busy', 'true');
      check.textContent = 'CHECKING…';
    } else if (!localBusy) {
      check.classList.remove('ywd-working');
      check.removeAttribute('aria-busy');
      check.textContent = 'CHECK INSTALL READINESS';
    }

    check.title = !unlocked
      ? 'Unlock the dashboard to run the install-readiness check.'
      : maintenanceActive || vocoderBusy
        ? 'Appliance maintenance is already in progress.'
        : 'Check install/build prerequisites without changing the live RF runtime.';
  }

  function renderConsole(job) {
    const pre = el('vocoderConsoleLog');
    if (!pre) return;
    const rows = Array.isArray(job?.log_tail) ? job.log_tail : [];
    if (rows.length) {
      pre.textContent = rows.join('\n');
      return;
    }
    if (job?.active) {
      pre.textContent = `${String(job.phase || 'working').toUpperCase()}${Number.isFinite(Number(job.progress)) ? ` · ${Number(job.progress)}%` : ''}\n${job.message || 'Managed vocoder job is running.'}`;
      return;
    }
    pre.textContent = 'No managed vocoder job transcript yet.\nUse CHECK INSTALL READINESS to exercise the guarded background job path without changing RF/runtime state.';
  }

  function renderLaunch(out) {
    launchedJobId = String(out?.job_id || '');
    launchPending = true;
    jobActive = true;
    maintenanceActive = true;
    const badge = el('vocoderState');
    if (badge) {
      badge.textContent = 'CHECKING';
      badge.className = 'vocoder-state busy';
    }
    text('vocoderSummary', 'Install-readiness job accepted. Exact runtime and appliance checks are running in the background.');
    text('vocoderMaintenance', 'VOCODER-PREFLIGHT · LAUNCHING');
    text('vocoderCollected', 'JOB ACCEPTED · waiting for worker status');
    const pre = el('vocoderConsoleLog');
    if (pre) {
      const id = launchedJobId || 'managed job';
      pre.textContent = `[JOB] ${id}\n[>>] Readiness check accepted by YWD-Hotspot\n[>>] Starting background worker…\n[>>] Exact runtime verification may take a little while on a Pi Zero.`;
    }
    el('vocoderConsoleDetails')?.setAttribute('open', '');
    syncActionState();
  }

  function render(doc) {
    statusLoaded = true;
    const stateDoc = doc?.state || {};
    const backend = doc?.backend || {};
    const recipe = doc?.recipe || {};
    const runtime = doc?.runtime || {};
    const job = doc?.job || {};
    const maintenance = doc?.maintenance || {};
    const serverJobActive = !!job.active;
    maintenanceActive = !!maintenance.active;

    const jobState = String(job.state || '').toUpperCase();
    const sameLaunchedJob = !!launchedJobId && String(job.job_id || '') === launchedJobId;
    const launchedTerminal = sameLaunchedJob && !maintenanceActive && ['COMPLETE','FAILED_SAFE'].includes(jobState);
    if (launchedTerminal) {
      launchPending = false;
      launchedJobId = null;
    }
    jobActive = launchPending ? true : serverJobActive;
    if (launchPending) maintenanceActive = true;

    const badge = el('vocoderState');
    const name = String(stateDoc.state || 'UNKNOWN').toUpperCase();
    if (badge) {
      badge.textContent = name.replaceAll('_', ' ');
      badge.className = `vocoder-state ${stateTone(name)}`;
    }
    text('vocoderSummary', stateDoc.reason || 'Vocoder manager status unavailable.');
    text('vocoderBackend', backend.binary_present ? (doc.managed ? 'MBELIB · MANAGED' : 'MBELIB · LEGACY/EXTERNAL') : 'NOT INSTALLED');
    text('vocoderProcess', stateDoc.process_mode || String(backend.service_state || 'not installed').toUpperCase());
    text('vocoderProtocol', `YWD PROTOCOL v${recipe.protocol ?? '—'}`);
    text('vocoderRecipe', `${recipe.id || '—'} · recipe ${recipe.version ?? '—'}`);
    text('vocoderMbelibPin', shortSha(recipe.mbelib_commit));
    text('vocoderSocket', socketText(backend));
    text('vocoderPolicy', policyText(backend.policy));
    text('vocoderExtended', runtimeText(runtime));
    text('vocoderSelfTest', selfTestText(doc));
    text('vocoderMaintenance', maintenanceText(doc));
    text('vocoderCollected', `STATUS ${stamp(doc?.collected_at)}`);
    const foundation = el('vocoderFoundationNote');
    if (foundation) {
      foundation.textContent = 'Background job foundation is active. CHECK INSTALL READINESS performs guarded preflight only; package install, source build, and live runtime activation remain disabled in this slice.';
    }
    renderConsole(job);
    if (jobActive || maintenanceActive) el('vocoderConsoleDetails')?.setAttribute('open', '');
    syncActionState();
  }

  async function loadStatus({showError = false, showButtonBusy = false} = {}) {
    if (loading || !el('vocoderManagerCard')) return null;
    loading = true;
    const button = el('vocoderRefresh');
    const old = button?.textContent;
    if (button && showButtonBusy) {
      button.disabled = true;
      button.classList.add('ywd-working');
      button.setAttribute('aria-busy', 'true');
      button.textContent = 'REFRESHING…';
    }
    try {
      const r = await fetch('/api/system/vocoder', {cache:'no-store', credentials:'same-origin'});
      let doc = {};
      try { doc = await r.json(); } catch (_) {}
      if (!r.ok || doc?.error) throw new Error(doc?.error || `HTTP ${r.status}`);
      render(doc);
      return doc;
    } catch (err) {
      const badge = el('vocoderState');
      if (badge) { badge.textContent = 'UNAVAILABLE'; badge.className = 'vocoder-state bad'; }
      text('vocoderSummary', err?.message || 'Could not read vocoder manager status.');
      if (showError && typeof toast === 'function') toast(`Vocoder status failed: ${err?.message || err}`, true);
      return null;
    } finally {
      loading = false;
      if (button && showButtonBusy) {
        button.classList.remove('ywd-working');
        button.removeAttribute('aria-busy');
        button.disabled = false;
        button.textContent = old || 'REFRESH STATUS';
      }
      syncActionState();
    }
  }

  function schedulePoll(delay = null) {
    clearTimeout(pollTimer);
    if (!el('vocoderManagerCard')) return;
    const next = delay == null ? (launchPending || jobActive || maintenanceActive ? 1500 : 30000) : delay;
    pollTimer = setTimeout(async () => {
      if (systemVisible()) await loadStatus();
      schedulePoll(launchPending || jobActive || maintenanceActive ? 1500 : 30000);
    }, next);
  }

  function activateWhenVisible() {
    if (!systemVisible() || !el('vocoderManagerCard')) return;
    if (!statusLoaded) loadStatus();
    schedulePoll(launchPending || jobActive || maintenanceActive ? 500 : 30000);
  }

  function installVisibilityHook(page) {
    if (!page || page.dataset.ywdVocoderVisibility === '1') return;
    page.dataset.ywdVocoderVisibility = '1';
    visibilityObserver?.disconnect();
    visibilityObserver = new MutationObserver(() => activateWhenVisible());
    visibilityObserver.observe(page, {attributes:true, attributeFilter:['class']});
    document.addEventListener('visibilitychange', activateWhenVisible);
  }

  async function startPreflight(button) {
    if (!button || button.dataset.ywdVocoderBusy === '1' || launchPending || jobActive || maintenanceActive) return;
    button.dataset.ywdVocoderBusy = '1';
    const old = button.textContent;
    button.disabled = true;
    button.classList.add('ywd-working');
    button.setAttribute('aria-busy', 'true');
    button.textContent = 'STARTING CHECK…';
    try {
      const out = await post('/api/system/vocoder/preflight', {});
      renderLaunch(out);
      if (typeof toast === 'function') toast(out?.message || 'Vocoder readiness check started');
      schedulePoll(250);
      setTimeout(() => loadStatus(), 200);
    } catch (err) {
      if (typeof toast === 'function') toast(`Vocoder readiness check failed to start: ${err?.message || err}`, true);
    } finally {
      delete button.dataset.ywdVocoderBusy;
      button.classList.remove('ywd-working');
      button.removeAttribute('aria-busy');
      button.textContent = old;
      syncActionState();
    }
  }

  function ensureCard() {
    const page = el('system');
    const host = el('hostPowerCard');
    const grid = host?.parentElement;
    if (!page || !host || !grid) return false;
    if (el('vocoderManagerCard')) {
      installVisibilityHook(page);
      activateWhenVisible();
      return true;
    }

    const card = document.createElement('article');
    card.className = 'card system-vocoder-card';
    card.id = 'vocoderManagerCard';
    card.innerHTML = `
      <div class="card-title title-row vocoder-title-row"><span>DMR AUDIO VOCODER</span><span id="vocoderState" class="vocoder-state">CHECKING</span></div>
      <p class="hint vocoder-summary" id="vocoderSummary">Status loads when the System page is opened so dashboard startup stays lightweight.</p>
      <div class="vocoder-grid">
        <div><span>BACKEND</span><b id="vocoderBackend">—</b></div>
        <div><span>PROCESS</span><b id="vocoderProcess">—</b></div>
        <div><span>PROTOCOL</span><b id="vocoderProtocol">—</b></div>
        <div><span>APPROVED RECIPE</span><b id="vocoderRecipe">—</b></div>
        <div><span>MBELIB PIN</span><b id="vocoderMbelibPin">—</b></div>
        <div><span>SOCKET ACTIVATION</span><b id="vocoderSocket">—</b></div>
        <div><span>SCHEDULING</span><b id="vocoderPolicy">—</b></div>
        <div><span>YWD EXTENDED</span><b id="vocoderExtended">—</b></div>
        <div><span>LAST SELF-TEST</span><b id="vocoderSelfTest">—</b></div>
        <div><span>MAINTENANCE</span><b id="vocoderMaintenance">—</b></div>
      </div>
      <div class="notice vocoder-foundation-note" id="vocoderFoundationNote">Status foundation is loading…</div>
      <div class="buttonrow wrap vocoder-actions">
        <button class="btn primary ctl" id="vocoderPreflight" type="button">CHECK INSTALL READINESS</button>
        <button class="btn vocoder-refresh" id="vocoderRefresh" type="button">REFRESH STATUS</button>
        <span class="hint" id="vocoderCollected">—</span>
      </div>
      <details class="vocoder-console" id="vocoderConsoleDetails"><summary>MANAGED JOB CONSOLE</summary><pre id="vocoderConsoleLog">No managed vocoder job transcript yet.</pre></details>
    `;
    grid.insertBefore(card, host);
    el('vocoderRefresh').onclick = () => loadStatus({showError:true, showButtonBusy:true});
    el('vocoderPreflight').onclick = event => startPreflight(event.currentTarget);
    if (typeof setCtl === 'function') setCtl();
    syncActionState();
    installVisibilityHook(page);
    activateWhenVisible();
    return true;
  }

  function init() {
    // system-ui.js is loaded late in the legacy serial module chain. Do not race
    // it with a fixed timeout: wait until its authoritative Host Power card
    // exists, then mount immediately before that card.
    const timer = setInterval(() => {
      if (ensureCard()) clearInterval(timer);
    }, 250);
    ensureCard();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
