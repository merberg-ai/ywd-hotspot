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

  function formatBytes(value) {
    const n = Number(value);
    if (!Number.isFinite(n) || n < 0) return 'unknown size';
    if (n < 1024) return `${Math.round(n)} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MiB`;
  }

  async function supportJson(url, options = {}) {
    const r = await fetch(url, {credentials:'same-origin', cache:'no-store', ...options});
    let d = {};
    try { d = await r.json(); } catch (_) {}
    if (!r.ok || d?.error) throw new Error(d?.error || `HTTP ${r.status}`);
    return d;
  }

  function fulfilled(result, fallback = {}) {
    return result?.status === 'fulfilled' ? result.value : fallback;
  }

  function tgList(items) {
    if (!Array.isArray(items) || !items.length) return 'none';
    return items.slice(0, 16).map(item => {
      if (item && typeof item === 'object') {
        const tg = item.talkgroup ?? item.id ?? item.tg ?? '?';
        const slot = item.slot ?? item.timeslot;
        const name = item.name ? ` ${item.name}` : '';
        return `${tg}${slot !== undefined && slot !== null ? `/TS${slot}` : ''}${name}`;
      }
      return String(item);
    }).join(', ');
  }

  function pluginSummary(doc) {
    const system = doc?.system || {};
    const rows = Array.isArray(doc?.plugins) ? doc.plugins : [];
    const visible = rows.filter(p => p?.installed || p?.enabled || p?.health === 'error').slice(0, 16);
    const detail = visible.length
      ? visible.map(p => `${p.id || p.name || '?'}@${p.version || '?'}:${p.health || (p.enabled ? 'enabled' : 'installed')}`).join(', ')
      : 'none installed';
    return `health=${system.health || 'unknown'} | installed=${system.installed ?? 'unknown'} | enabled=${system.enabled_plugins ?? 'unknown'} | active=${system.active_plugins ?? 'unknown'} | ${detail}`;
  }

  function trafficSummary(activity) {
    const rows = Array.isArray(activity?.lastheard) ? activity.lastheard.slice(0, 3) : [];
    if (!rows.length) return ['Recent traffic: none recorded'];
    return rows.map((row, index) => {
      const src = row?.source?.display || row?.source?.callsign || row?.source || '?';
      const dst = row?.destination?.display || row?.destination?.name || row?.destination || '?';
      const path = row?.path || row?.direction || '?';
      const duration = Number.isFinite(Number(row?.duration_s)) ? `${Number(row.duration_s).toFixed(1)}s` : '—';
      const metrics = [
        row?.ber_pct !== undefined && row?.ber_pct !== null ? `BER ${row.ber_pct}%` : null,
        row?.rssi_dbm !== undefined && row?.rssi_dbm !== null ? `RSSI ${row.rssi_dbm} dBm` : null,
        row?.packet_loss_pct !== undefined && row?.packet_loss_pct !== null ? `loss ${row.packet_loss_pct}%` : null,
      ].filter(Boolean).join(' | ') || 'no quality metrics';
      return `Recent traffic ${index + 1}: ${path} | ${src} -> ${dst} | ${duration} | ${metrics}`;
    });
  }

  function modernSupportSummary(status, health, plugins, dmrid, ssh, update) {
    const s = status || {};
    const h = health || {};
    const c = s.config || {};
    const r = c.radio || {};
    const bmCfg = c.brandmeister || {};
    const display = c.display || {};
    const web = c.web || {};
    const maintenance = c.maintenance || {};
    const build = s.build || {};
    const wifi = h.wifi || s.system?.wifi || {};
    const throttled = h.throttled || s.system?.throttled || {};
    const mem = h.memory || s.system?.memory || {};
    const disk = h.disk || s.system?.disk || {};
    const db = dmrid?.database || {};
    const cal = s.calibration || {};
    const baseline = cal.baseline || {};
    const best = cal.best || null;
    const u = update?.update || update || {};
    const channel = u.channel || build.update_channel || build.branch || 'unknown';
    const mode = String(r.mode || 'simplex').toLowerCase();
    const mhz = value => Number.isFinite(Number(value)) && Number(value) > 0 ? `${(Number(value) / 1e6).toFixed(6)} MHz` : 'unknown';
    const rfLine = mode === 'duplex'
      ? `duplex | hotspot RX ${mhz(r.rx_frequency_hz || r.frequency_hz)} | hotspot TX ${mhz(r.tx_frequency_hz || r.frequency_hz)} | DMR slots 1+2`
      : `simplex | ${mhz(r.frequency_hz)} | DMR slot 2`;
    const serviceHealth = h.services || {};
    const extendedServices = Object.entries(serviceHealth)
      .filter(([name]) => name.startsWith('ywd-') || name === 'ssh.service')
      .map(([name, value]) => `${name}=${value?.active || value || 'unknown'}${value?.restarts !== undefined && value?.restarts !== null ? `(restarts:${value.restarts})` : ''}`)
      .join(' | ');
    const baselineText = baseline?.saved_at || baseline?.time
      ? `saved ${new Date(Number(baseline.saved_at || baseline.time) * 1000).toLocaleString()}`
      : 'none';
    const bestText = best ? `${best.rx_offset ?? '?'} Hz / BER ${best.ber_pct ?? '?'}%` : 'none';
    const previous = h.previous_boot || {};
    const warnings = Array.isArray(h.kernel_warnings) ? h.kernel_warnings.length : 0;
    const sourceCommit = build.commit || u.current_commit || 'unknown';

    return [
      `YWD-Hotspot support summary · ${new Date().toISOString()}`,
      `Version/build: ${s.version || build.version || 'unknown'} | ${build.branch || 'unknown'} @ ${sourceCommit} | channel ${channel}`,
      `Source: ${build.source || 'unknown'} / ${build.source_state || 'unknown'} | commit date ${build.commit_date || 'unknown'}`,
      `Host: ${h.hostname || s.system?.hostname || 'unknown'} | uptime ${Math.floor(Number(h.uptime_s ?? s.system?.uptime_s ?? 0))}s | boot ${h.boot_id || 'unknown'}`,
      `Core services: MMDVM=${s.services?.mmdvmhost || 'unknown'} | Gateway=${s.services?.dmrgateway || 'unknown'} | Dashboard=${s.services?.dashboard || 'unknown'} | OLED=${s.services?.oled || 'unknown'} (${s.services?.oled_unit || 'unknown'}) | Activity=${s.services?.activity || 'unknown'}`,
      extendedServices ? `Discovered service health: ${extendedServices}` : 'Discovered service health: unavailable',
      `RF: ${rfLine} | CC${r.color_code ?? '?'} | RX/TX offset ${r.rx_offset ?? '?'} / ${r.tx_offset ?? '?'} Hz | RX/TX/RF levels ${r.rx_level ?? '?'} / ${r.tx_level ?? '?'} / ${r.rf_level ?? '?'}%`,
      `Modem: ${r.port || 'unknown'} @ ${r.baud || 'unknown'} | TX/RX invert ${r.tx_invert ?? '?'} / ${r.rx_invert ?? '?'} | jitter ${r.jitter_ms ?? '?'} ms | hang ${r.call_hang_s ?? '?'}/${r.tx_hang_s ?? '?'} s`,
      `BrandMeister config: enabled=${bmCfg.enabled ?? false} | ${bmCfg.master || 'unknown'}:${bmCfg.port || 'unknown'} | hotspot password configured=${bmCfg.password_configured ?? false} | API key configured=${s.brandmeister?.api_key_configured ?? false}`,
      `BrandMeister runtime: ${s.brandmeister?.state || 'unknown'} | ${s.brandmeister?.detail || s.brandmeister?.profile_error || 'no detail'} | static=${tgList(s.brandmeister?.static)} | dynamic=${tgList(s.brandmeister?.dynamic)}`,
      `Config: pending=${s.pending?.pending ?? 'unknown'} | hash=${s.pending?.current_hash || 'unknown'} | RF autostart=${maintenance.rf_autostart ?? 'unknown'} | persistent journal=${maintenance.persistent_journal ?? 'unknown'} (${maintenance.journal_max_mb ?? '?'} MB)`,
      `Display/WebUI: OLED enabled=${display.enabled ?? false} | address=${display.address || 'unknown'} | brightness=${display.brightness ?? 'unknown'} | idle=${display.idle_timeout_s ?? 'unknown'}s | Web ${web.bind || 'unknown'}:${web.port || 'unknown'}`,
      `System: temp ${h.temperature_c ?? s.system?.temp_c ?? '—'} C | load ${(h.load || s.system?.load || []).join(' / ') || '—'} | memory ${mem.used_mb ?? '—'}/${mem.total_mb ?? '—'} MB | disk ${disk.used_gb ?? '—'}/${disk.total_gb ?? '—'} GB (${disk.used_pct ?? '—'}%)`,
      `Power/throttle: ${throttled.raw || throttled.value || 'unavailable'} | history=${Array.isArray(throttled.history) && throttled.history.length ? throttled.history.join(', ') : 'none'}`,
      `Wi-Fi: ${wifi.interface || 'wlan0'} | SSID=${wifi.ssid || 'unknown'} | IP=${wifi.ip || 'none'} | signal=${wifi.signal_dbm ?? '—'} dBm | gateway=${wifi.gateway || 'unknown'} | RX errors/dropped=${wifi.rx_errors ?? '—'}/${wifi.rx_dropped ?? '—'} | TX=${wifi.tx_errors ?? '—'}/${wifi.tx_dropped ?? '—'}`,
      `DMR ID DB: ${db.state || 'unknown'} | records=${db.records ?? 'unknown'} | size=${db.size_bytes ?? 'unknown'} | age=${formatAge(db.age_s)} | interval=${db.interval_days ?? 'unknown'}d | due=${db.due ?? 'unknown'} | timer=${dmrid?.timer?.active || 'unknown'}/${dmrid?.timer?.enabled || 'unknown'}`,
      `Plugins: ${pluginSummary(plugins)}`,
      `SSH: active=${ssh?.active ?? 'unknown'} | boot=${ssh?.enabled_at_boot ?? 'unknown'} | policy=${ssh?.authentication || 'unknown'} | managed=${ssh?.policy_managed ?? 'unknown'} | user=${ssh?.login_user || 'ywd'} | authorized keys=${ssh?.authorized_key_count ?? 'unknown'} | host keys=${ssh?.host_key_count ?? 'unknown'}`,
      `Updater: state=${u.state || 'idle'} | phase=${u.phase || '—'} | channel=${channel} | current=${u.current_commit || sourceCommit} | target=${u.target_commit || '—'} | available=${u.available ?? false}`,
      `Calibration: baseline ${baselineText} | best ${bestText} | runs=${Array.isArray(cal.tests) ? cal.tests.length : 0}`,
      `Boot/crash: previous=${previous.shutdown || 'unknown'} | kernel/hardware warning matches=${warnings} | journal=${h.journal_disk || 'unknown'}`,
      ...trafficSummary(s.activity),
      'Secrets intentionally omitted: BrandMeister password/API key, WebUI credentials, Wi-Fi PSK, and SSH key material are not included in this summary.',
      'For deeper troubleshooting use CREATE DIAGNOSTIC BUNDLE; review third-party/plugin logs before posting an archive publicly.'
    ].join('\n');
  }

  function installDiagnosticsPolish() {
    if (window.__ywdDiagnosticsPolish) return true;
    const copy = document.getElementById('copySupport');
    const make = document.getElementById('makeDiag');
    const preview = document.getElementById('supportPreview');
    const link = document.getElementById('diagLink');
    if (!copy || !make || !preview || !link) return false;
    window.__ywdDiagnosticsPolish = true;

    copy.onclick = async () => {
      if (copy.dataset.ywdSystemBusy === '1') return;
      const old = copy.textContent;
      copy.dataset.ywdSystemBusy = '1';
      copy.disabled = true;
      copy.classList.add('ywd-working');
      copy.textContent = 'COLLECTING…';
      preview.textContent = 'Collecting fresh sanitized support state…';
      try {
        const results = await Promise.allSettled([
          supportJson('/api/status'),
          supportJson('/api/health'),
          supportJson('/api/plugins'),
          supportJson('/api/system/dmrid'),
          supportJson('/api/ssh/status', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'}),
          supportJson('/api/update/status'),
        ]);
        const status = fulfilled(results[0], (typeof state !== 'undefined' ? state : {}));
        const health = fulfilled(results[1], (typeof healthDoc !== 'undefined' ? healthDoc : {}));
        const plugins = fulfilled(results[2], {});
        const dmrid = fulfilled(results[3], {});
        const ssh = fulfilled(results[4], {});
        const update = fulfilled(results[5], {});
        const text = modernSupportSummary(status, health, plugins, dmrid, ssh, update);
        preview.textContent = text;
        try {
          await navigator.clipboard.writeText(text);
          toast('Expanded support summary copied');
        } catch (_) {
          toast('Support summary generated; clipboard permission was denied', true);
        }
      } catch (err) {
        preview.textContent = `Support summary failed: ${err.message || err}`;
        toast(err.message || 'Could not create support summary', true);
      } finally {
        delete copy.dataset.ywdSystemBusy;
        copy.classList.remove('ywd-working');
        copy.textContent = old;
        copy.disabled = false;
        if (typeof setCtl === 'function') setCtl();
      }
    };

    make.onclick = async () => {
      if (make.dataset.ywdSystemBusy === '1') return;
      const old = make.textContent;
      make.dataset.ywdSystemBusy = '1';
      make.disabled = true;
      make.classList.add('ywd-working');
      make.textContent = 'COLLECTING…';
      link.textContent = '';
      try {
        const d = await post('/api/diagnostics/create', {});
        const a = document.createElement('a');
        a.href = `/api/diagnostics/${encodeURIComponent(d.filename)}`;
        a.textContent = `DOWNLOAD ${d.filename} · ${formatBytes(d.size)}`;
        link.replaceChildren(a);
        toast(`Diagnostic bundle v${d.schema || 1} ready · ${formatBytes(d.size)}`);
        a.click();
      } catch (err) {
        toast(err.message || 'Could not create diagnostic bundle', true);
      } finally {
        delete make.dataset.ywdSystemBusy;
        make.classList.remove('ywd-working');
        make.textContent = old;
        make.disabled = false;
        if (typeof setCtl === 'function') setCtl();
      }
    };
    return true;
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
    const nav = installNavigation();
    const quick = installStatusQuickActions();
    const runtime = installRuntimeCard();
    const dmrid = installDmrIdCard();
    const diagnostics = installDiagnosticsPolish();
    const hooked = hookRender();
    if (typeof setCtl === 'function') setCtl();
    return nav && quick && runtime && dmrid && diagnostics && hooked;
  }

  let tries = 0;
  const timer = setInterval(() => {
    tries += 1;
    if (install() || tries >= 80) clearInterval(timer);
  }, 100);
  if (install()) clearInterval(timer);
})();