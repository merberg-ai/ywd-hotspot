'use strict';
(() => {
  const byTitle = (root, text) => Array.from(root?.querySelectorAll('article.card') || []).find(card =>
    card.querySelector(':scope > .card-title')?.textContent?.trim() === text
  );

  function requireConfirm(options) {
    if (typeof window.ywdConfirm !== 'function') {
      toast('YWD confirmation UI is unavailable. Reload the dashboard and try again.', true);
      return Promise.resolve(false);
    }
    return window.ywdConfirm(options);
  }

  async function runButton(button, busyText, fn) {
    if (!button || button.dataset.ywdSystemBusy === '1') return;
    const oldText = button.textContent;
    const oldDisabled = button.disabled;
    button.dataset.ywdSystemBusy = '1';
    button.disabled = true;
    button.classList.add('ywd-working');
    button.setAttribute('aria-busy', 'true');
    button.textContent = busyText;
    try {
      await fn();
    } finally {
      delete button.dataset.ywdSystemBusy;
      button.classList.remove('ywd-working');
      button.removeAttribute('aria-busy');
      button.textContent = oldText;
      button.disabled = oldDisabled;
      if (typeof setCtl === 'function') setCtl();
      syncRfState(state);
    }
  }

  function installTalkgroupConfirmDedupe() {
    if (window.__ywdTgConfirmDedupe || typeof window.ywdConfirm !== 'function') return false;
    const baseConfirm = window.ywdConfirm;
    const duplicateLabels = new Set(['APPLY PLAN', 'DROP DYNAMIC', 'REPLACE SET', 'DELETE SET']);
    let recentlyAccepted = null;

    window.ywdConfirm = async function(options = {}) {
      const label = String(options?.confirmText || '').trim().toUpperCase();
      const now = performance.now();
      if (recentlyAccepted && recentlyAccepted.label === label && now - recentlyAccepted.at < 140) {
        recentlyAccepted = null;
        return true;
      }

      const ok = await baseConfirm(options);
      if (ok && duplicateLabels.has(label)) {
        const marker = {label, at: performance.now()};
        recentlyAccepted = marker;
        setTimeout(() => {
          if (recentlyAccepted === marker) recentlyAccepted = null;
        }, 180);
      } else {
        recentlyAccepted = null;
      }
      return ok;
    };
    window.__ywdTgConfirmDedupe = true;
    return true;
  }

  function installNavigation() {
    const tabs = document.querySelector('.tabs');
    const controlTab = tabs?.querySelector('[data-tab="control"]');
    const aboutTab = tabs?.querySelector('[data-tab="about"]');
    const page = document.getElementById('control');
    if (!tabs || !controlTab || !aboutTab || !page) return false;

    controlTab.textContent = 'SYSTEM';
    controlTab.dataset.tab = 'system';
    page.id = 'system';
    tabs.insertBefore(controlTab, aboutTab);
    return true;
  }

  function installStatusQuickActions() {
    const status = document.getElementById('status');
    const system = document.getElementById('system');
    const bmCard = document.getElementById('bmState')?.closest('article.card');
    const legacyBmCard = byTitle(system, 'BRANDMEISTER CONTROL');
    const dropQso = document.getElementById('dropQso');
    const dropDyn = document.getElementById('dropDyn');
    if (!status || !system || !bmCard || !legacyBmCard || !dropQso || !dropDyn) return false;

    if (!document.getElementById('bmQuickControls')) {
      const quick = document.createElement('div');
      quick.id = 'bmQuickControls';
      quick.className = 'bm-quick-controls';
      quick.innerHTML = '<span class="label">QUICK CONTROLS</span><div class="bm-quick-actions"></div>';
      const actions = quick.querySelector('.bm-quick-actions');
      dropQso.className = 'btn danger ctl ywd-quick-btn';
      dropDyn.className = 'btn danger ctl ywd-quick-btn';
      actions.append(dropQso, dropDyn);
      bmCard.appendChild(quick);
    }

    // Keep the legacy elements in the DOM because older render/gating code still
    // updates their IDs, but remove the duplicate control card from the visible UI.
    legacyBmCard.hidden = true;
    legacyBmCard.setAttribute('aria-hidden', 'true');
    return true;
  }

  function installRuntimeCard() {
    const page = document.getElementById('system');
    const runtime = byTitle(page, 'RUNTIME');
    const grid = runtime?.parentElement;
    const start = document.getElementById('startRf');
    const stop = document.getElementById('stopRf');
    const restart = document.getElementById('restartRf');
    const reboot = document.getElementById('rebootPi');
    if (!page || !runtime || !grid || !start || !stop || !restart || !reboot) return false;

    if (!document.getElementById('rfToggle')) {
      const statusRow = document.createElement('div');
      statusRow.className = 'system-state-row';
      statusRow.innerHTML = '<span>RF STACK</span><b id="rfRuntimeState">CHECKING…</b>';
      const title = runtime.querySelector(':scope > .card-title');
      title?.insertAdjacentElement('afterend', statusRow);

      const toggle = document.createElement('button');
      toggle.id = 'rfToggle';
      toggle.type = 'button';
      toggle.className = 'btn good ctl';
      toggle.textContent = 'START RF';
      restart.parentElement?.insertBefore(toggle, restart);
      start.remove();
      stop.remove();

      toggle.onclick = async () => {
        const running = state?.services?.mmdvmhost === 'active';
        const ok = await requireConfirm({
          title: running ? 'STOP RF STACK' : 'START RF STACK',
          message: running
            ? 'Stop MMDVM-Host and the BrandMeister network path now?\n\nThis runtime action does not change the configured RF autostart policy.'
            : 'Start MMDVM-Host and the BrandMeister network path now?\n\nVerify the antenna and configured frequencies before transmitting.',
          confirmText: running ? 'STOP RF' : 'START RF',
          cancelText: 'CANCEL',
          tone: 'warn',
          kicker: 'YWD // SYSTEM'
        });
        if (!ok) return;
        await runButton(toggle, running ? 'STOPPING…' : 'STARTING…', async () => {
          await post(running ? '/api/runtime/rf-stop' : '/api/runtime/rf-start', {});
          toast(running ? 'RF stack stopped' : 'RF stack started');
          setTimeout(getStatus, 550);
        });
      };
    }

    if (!document.getElementById('hostPowerCard')) {
      const host = document.createElement('article');
      host.className = 'card system-power-card';
      host.id = 'hostPowerCard';
      host.innerHTML = '<div class="card-title">HOST POWER</div><p class="hint">These actions interrupt the entire hotspot appliance. Shutdown leaves the Pi off until power is restored.</p><div class="buttonrow wrap system-power-actions"></div>';
      const actions = host.querySelector('.system-power-actions');
      reboot.className = 'btn danger ctl';
      actions.appendChild(reboot);
      runtime.querySelector('hr')?.remove();

      const shutdown = document.createElement('button');
      shutdown.id = 'shutdownPi';
      shutdown.type = 'button';
      shutdown.className = 'btn danger ctl';
      shutdown.textContent = 'SHUTDOWN PI';
      actions.appendChild(shutdown);
      grid.appendChild(host);

      shutdown.onclick = async () => {
        const ok = await requireConfirm({
          title: 'SHUTDOWN RASPBERRY PI',
          message: 'Power down the hotspot now?\n\nDMR services and the WebUI will remain offline until power is physically restored.',
          confirmText: 'SHUTDOWN PI',
          cancelText: 'CANCEL',
          tone: 'danger',
          kicker: 'YWD // SYSTEM'
        });
        if (!ok) return;
        await runButton(shutdown, 'SHUTTING DOWN…', async () => {
          await post('/api/runtime/shutdown', {});
          toast('Shutdown scheduled');
        });
      };
    }

    runtime.classList.add('system-runtime-card');
    syncRfState(state);
    return true;
  }

  function formatDate(epoch) {
    const n = Number(epoch);
    return Number.isFinite(n) && n > 0 ? new Date(n * 1000).toLocaleString() : '—';
  }

  function formatAge(seconds) {
    let s = Number(seconds);
    if (!Number.isFinite(s) || s < 0) return '—';
    if (s < 60) return `${Math.floor(s)} sec`;
    if (s < 3600) return `${Math.floor(s / 60)} min`;
    if (s < 86400) return `${Math.floor(s / 3600)} hr`;
    const days = Math.floor(s / 86400);
    const hours = Math.floor((s % 86400) / 3600);
    return hours ? `${days}d ${hours}h` : `${days}d`;
  }

  function renderDmrIdStatus(doc) {
    const card = document.getElementById('dmridCard');
    if (!card || !doc?.database) return;
    const db = doc.database;
    const timer = doc.timer || {};
    const service = doc.service || {};
    const status = document.getElementById('dmridState');
    const stateName = String(db.state || 'unknown').toLowerCase();
    const label = stateName === 'current' ? 'CURRENT' : stateName === 'due' ? 'DUE' : stateName === 'missing' ? 'MISSING' : 'CHECK';
    status.textContent = label;
    status.className = `dmrid-badge ${stateName === 'current' ? 'goodtext' : stateName === 'missing' ? 'badtext' : 'warntext'}`;
    document.getElementById('dmridSource').textContent = db.source || 'RadioID.net';
    document.getElementById('dmridRecords').textContent = Number.isFinite(Number(db.records)) ? Number(db.records).toLocaleString() : '—';
    document.getElementById('dmridUpdated').textContent = formatDate(db.last_updated);
    document.getElementById('dmridAge').textContent = formatAge(db.age_s);
    document.getElementById('dmridInterval').textContent = `${db.interval_days || 7} days`;
    document.getElementById('dmridNext').textContent = db.present ? formatDate(db.next_due) : 'update required';
    document.getElementById('dmridTimer').textContent = `${String(timer.active || 'unknown').toUpperCase()} · ${String(timer.enabled || 'unknown').toUpperCase()}`;
    document.getElementById('dmridResult').textContent = `${String(service.result || 'unknown').toUpperCase()} · EXIT ${service.exit_status ?? '—'}`;
  }

  async function loadDmrIdStatus(showError = false) {
    try {
      const r = await fetch('/api/system/dmrid', {cache: 'no-store'});
      const doc = await r.json();
      if (!r.ok || doc?.error) throw new Error(doc?.error || `HTTP ${r.status}`);
      renderDmrIdStatus(doc);
      return doc;
    } catch (err) {
      const stateLabel = document.getElementById('dmridState');
      if (stateLabel) {
        stateLabel.textContent = 'UNAVAILABLE';
        stateLabel.className = 'dmrid-badge badtext';
      }
      if (showError) toast(`DMR ID status failed: ${err.message || err}`, true);
      return null;
    }
  }

  function installDmrIdCard() {
    const page = document.getElementById('system');
    const runtime = byTitle(page, 'RUNTIME');
    const grid = runtime?.parentElement;
    if (!page || !runtime || !grid) return false;
    if (document.getElementById('dmridCard')) return true;

    const card = document.createElement('article');
    card.className = 'card system-dmrid-card';
    card.id = 'dmridCard';
    card.innerHTML = `
      <div class="card-title title-row"><span>DMR ID DATABASE</span><span id="dmridState" class="dmrid-badge">CHECKING…</span></div>
      <p class="hint">Local RadioID lookup data used for callsign display. The timer performs lightweight due-checks; downloads occur only when the configured interval is due.</p>
      <div class="dmrid-grid">
        <div><span>SOURCE</span><b id="dmridSource">—</b></div>
        <div><span>RECORDS</span><b id="dmridRecords">—</b></div>
        <div><span>LAST UPDATED</span><b id="dmridUpdated">—</b></div>
        <div><span>AGE</span><b id="dmridAge">—</b></div>
        <div><span>UPDATE INTERVAL</span><b id="dmridInterval">—</b></div>
        <div><span>NEXT DUE</span><b id="dmridNext">—</b></div>
        <div><span>TIMER</span><b id="dmridTimer">—</b></div>
        <div><span>LAST SERVICE RESULT</span><b id="dmridResult">—</b></div>
      </div>
      <div class="buttonrow wrap dmrid-actions"><button id="dmridCheck" class="btn ctl" type="button">CHECK NOW</button><button id="dmridUpdate" class="btn primary ctl" type="button">UPDATE NOW</button></div>
    `;
    const host = document.getElementById('hostPowerCard');
    grid.insertBefore(card, host || null);

    const check = document.getElementById('dmridCheck');
    const update = document.getElementById('dmridUpdate');
    check.onclick = async () => {
      await runButton(check, 'CHECKING…', async () => {
        const out = await post('/api/system/dmrid/check', {});
        renderDmrIdStatus(out);
        toast(out.message || 'DMR ID database check completed');
      });
    };
    update.onclick = async () => {
      const ok = await requireConfirm({
        title: 'UPDATE DMR ID DATABASE',
        message: 'Download a fresh RadioID database now, even if the normal update interval is not due yet?',
        confirmText: 'UPDATE NOW',
        cancelText: 'CANCEL',
        tone: 'warn',
        kicker: 'YWD // SYSTEM'
      });
      if (!ok) return;
      await runButton(update, 'UPDATING…', async () => {
        const out = await post('/api/system/dmrid/update', {});
        renderDmrIdStatus(out);
        toast(out.message || 'DMR ID database updated');
      });
    };

    loadDmrIdStatus(true);
    if (!window.__ywdDmrIdPoll) {
      window.__ywdDmrIdPoll = setInterval(() => loadDmrIdStatus(false), 60000);
    }
    return true;
  }

  function syncRfState(d) {
    const toggle = document.getElementById('rfToggle');
    const label = document.getElementById('rfRuntimeState');
    if (!toggle || !label || !d) return;
    const mmdvm = d.services?.mmdvmhost || 'unknown';
    const gateway = d.services?.dmrgateway || 'unknown';
    const running = mmdvm === 'active';
    label.textContent = running
      ? `RUNNING · GATEWAY ${String(gateway).toUpperCase()}`
      : `STOPPED · MMDVM ${String(mmdvm).toUpperCase()}`;
    label.className = running ? 'goodtext' : 'badtext';
    if (toggle.dataset.ywdSystemBusy !== '1') {
      toggle.textContent = running ? 'STOP RF' : 'START RF';
      toggle.className = `btn ${running ? 'danger' : 'good'} ctl`;
    }
  }

  function hookRender() {
    if (window.__ywdSystemRenderHook || typeof render !== 'function') return false;
    window.__ywdSystemRenderHook = true;
    const baseRender = render;
    render = function(d) {
      baseRender(d);
      syncRfState(d);
    };
    return true;
  }

  function install() {
    const dedupe = installTalkgroupConfirmDedupe();
    const nav = installNavigation();
    const quick = installStatusQuickActions();
    const runtime = installRuntimeCard();
    const dmrid = installDmrIdCard();
    const hooked = hookRender();
    if (typeof setCtl === 'function') setCtl();
    return dedupe && nav && quick && runtime && dmrid && hooked;
  }

  let tries = 0;
  const timer = setInterval(() => {
    tries += 1;
    if (install() || tries >= 80) clearInterval(timer);
  }, 100);
  if (install()) clearInterval(timer);
})();