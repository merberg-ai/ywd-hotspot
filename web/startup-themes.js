'use strict';
(() => {
  const STORAGE_KEY = 'ywd.loadingAnimation';
  const DEFAULT_THEME = 'rf_sweep';
  const THEMES = [
    ['rf_sweep','RF Sweep','Oscilloscope-style RF trace and scan.'],
    ['radar_scan','Radar Scan','Circular RF scan with transient signal blips.'],
    ['packet_burst','Packet Burst','Digital packets move RADIO → MMDVM → GATEWAY → NET.'],
    ['digital_waterfall','Digital Waterfall','Compact scrolling spectrum/waterfall display.'],
    ['rf_orbit','RF Orbit','RF, DMR, NET and UI nodes orbit the YWD core.'],
    ['boot_telemetry','Boot Telemetry','Retro subsystem status terminal.'],
    ['signal_lock','Signal Lock','Noisy signal bars converge toward system lock.'],
    ['vfo_tuning','VFO Tuning','Simulated boot VFO settles on the configured RF frequency.'],
    ['dmr_frame','DMR Frame Pulse','Alternating TS1/TS2 digital frame bursts.'],
  ];
  const allowed = new Set(THEMES.map(row => row[0]));
  const reduceMotion = !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  let lastStatus = null;
  let lastConfig = null;
  let pollTimer = null;
  let previewTimer = null;
  let hooksInstalled = false;
  let earlyObserver = null;
  let earlyObserverTimer = null;

  const safeTheme = value => allowed.has(String(value || '')) ? String(value) : DEFAULT_THEME;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function storedTheme() {
    try { return safeTheme(localStorage.getItem(STORAGE_KEY)); } catch (_) { return DEFAULT_THEME; }
  }
  function initialTheme() {
    return safeTheme(window.__YWD_LOADING_ANIMATION || storedTheme());
  }
  function rememberTheme(theme) {
    try { localStorage.setItem(STORAGE_KEY, safeTheme(theme)); } catch (_) {}
  }

  function themeMarkup(theme) {
    switch (safeTheme(theme)) {
      case 'radar_scan': return `<div class="ywd-radar"><div class="ywd-radar-sweep"></div><i class="ywd-radar-blip b1"></i><i class="ywd-radar-blip b2"></i><i class="ywd-radar-blip b3"></i></div><div class="theme-caption">RADAR // SPECTRUM SCAN</div>`;
      case 'packet_burst': return `<div class="ywd-packet-chain"><span class="ywd-packet"></span><span class="ywd-packet p2"></span><b class="ywd-packet-node">RADIO</b><b class="ywd-packet-node">MMDVM</b><b class="ywd-packet-node">GATE</b><b class="ywd-packet-node">NET</b></div><div class="theme-caption">DIGITAL TRANSPORT // SYNCHRONIZING</div>`;
      case 'digital_waterfall': return `<div class="ywd-waterfall"></div><div class="theme-caption">DIGITAL WATERFALL // RF ACTIVITY MAP</div>`;
      case 'rf_orbit': return `<div class="ywd-orbit"><div class="ywd-orbit-ring"><span class="ywd-orbit-node">RF</span></div><div class="ywd-orbit-ring r2"><span class="ywd-orbit-node">NET</span></div><div class="ywd-orbit-core">YWD</div></div><div class="theme-caption" id="ywdOrbitCaption">RF · DMR · NET · UI</div>`;
      case 'boot_telemetry': return `<div class="ywd-boot-lines"><div class="ywd-boot-line" data-boot="ui"><span>UI CORE</span><b>WAIT</b></div><div class="ywd-boot-line" data-boot="config"><span>CONFIG</span><b>WAIT</b></div><div class="ywd-boot-line" data-boot="rf"><span>RF STACK</span><b>WAIT</b></div><div class="ywd-boot-line" data-boot="gateway"><span>DMRGATEWAY</span><b>WAIT</b></div></div><div class="theme-caption">BOOT TELEMETRY // READINESS GATE</div>`;
      case 'signal_lock': return `<div class="ywd-lock-bars">${Array.from({length:18},()=>'<i></i>').join('')}</div><div class="theme-caption" id="ywdLockCaption">SIGNAL SEARCH // ACQUIRING LOCK</div>`;
      case 'vfo_tuning': return `<div class="ywd-vfo"><div class="ywd-vfo-display"><span id="ywdVfoDigits">446.525000</span><span class="ywd-vfo-unit">MHz</span></div><div class="ywd-s-meter">${Array.from({length:12},()=>'<i></i>').join('')}</div></div><div class="theme-caption">SIMULATED BOOT VFO // CONFIGURED TARGET</div>`;
      case 'dmr_frame': return `<div class="ywd-dmr-lanes"><div class="ywd-dmr-lane lane1"><label>TS1</label><i class="ywd-dmr-burst"></i></div><div class="ywd-dmr-lane lane2"><label>TS2</label><i class="ywd-dmr-burst"></i></div></div><div class="theme-caption">MMDVM // DMR FRAME PULSE</div>`;
      default: return `<div class="ywd-scope"><svg viewBox="0 0 300 80" preserveAspectRatio="none" aria-hidden="true"><polyline points="0,42 18,42 30,38 42,46 54,42 74,42 84,12 94,70 104,42 126,42 136,34 146,49 156,42 182,42 190,24 198,60 206,42 230,42 240,37 250,47 260,42 300,42"></polyline></svg><div class="ywd-scope-scan"></div></div><div class="theme-caption">RF SCOPE // ACQUIRING DASHBOARD</div>`;
    }
  }

  function ensureVisual(card, theme) {
    if (!card) return null;
    let host = card.querySelector('.ywd-loader-scene');
    const old = card.querySelector('.ywd-rf-loader');
    if (!host) {
      host = document.createElement('div');
      host.className = 'ywd-loader-scene';
      host.setAttribute('aria-hidden','true');
      if (old) old.replaceWith(host);
      else card.querySelector('.ywd-load-title')?.insertAdjacentElement('beforebegin', host);
    } else if (old) old.remove();
    const chosen = safeTheme(theme);
    if (host.dataset.theme !== chosen) {
      host.dataset.theme = chosen;
      host.className = `ywd-loader-scene theme-${chosen}`;
      host.innerHTML = themeMarkup(chosen);
    }
    updateDynamic(host);
    return host;
  }

  function readiness() {
    const services = lastStatus?.services || {};
    return {
      ui: document.readyState !== 'loading',
      config: !!lastConfig,
      rf: services.mmdvmhost === 'active',
      gateway: services.dmrgateway === 'active',
    };
  }

  function configuredFrequency() {
    const r = lastConfig?.radio || {};
    const hz = r.mode === 'duplex' ? (r.tx_frequency_hz || r.frequency_hz) : r.frequency_hz;
    return Number.isFinite(Number(hz)) && Number(hz) > 0 ? Number(hz) / 1e6 : null;
  }

  function updateDynamic(host) {
    if (!host) return;
    const ready = readiness();
    host.querySelectorAll('[data-boot]').forEach(line => {
      const yes = !!ready[line.dataset.boot];
      line.classList.toggle('ready', yes);
      const b = line.querySelector('b');
      if (b) b.textContent = yes ? 'READY' : 'WAIT';
    });
    const orbit = host.querySelector('#ywdOrbitCaption');
    if (orbit) orbit.textContent = `RF ${ready.rf?'✓':'·'}  DMR ${ready.gateway?'✓':'·'}  NET ${lastStatus?.brandmeister?.state === 'connected'?'✓':'·'}  UI ${ready.ui?'✓':'·'}`;
    const lock = host.querySelector('#ywdLockCaption');
    if (lock) lock.textContent = ready.config ? 'SIGNAL LOCK // DASHBOARD SYNCHRONIZED' : 'SIGNAL SEARCH // ACQUIRING LOCK';
    const digits = host.querySelector('#ywdVfoDigits');
    if (digits) {
      const fixed = configuredFrequency();
      if (fixed != null) digits.textContent = fixed.toFixed(6);
      else if (!reduceMotion) {
        const fake = [144.390000,438.800000,440.000000,446.525000];
        digits.textContent = fake[Math.floor(Date.now()/180)%fake.length].toFixed(6);
      }
    }
  }

  function applyStartupTheme(theme) {
    const overlay = document.getElementById('ywdStartupOverlay');
    const card = overlay?.querySelector('.ywd-startup-card');
    if (!card) return false;
    ensureVisual(card, safeTheme(theme));
    return true;
  }

  function applyConfig(config) {
    lastConfig = config || lastConfig;
    const chosen = safeTheme(config?.web?.loading_animation || DEFAULT_THEME);
    window.__YWD_LOADING_ANIMATION = chosen;
    rememberTheme(chosen);
    const select = document.getElementById('loadingAnimationSelect');
    if (select) select.value = chosen;
    applyStartupTheme(chosen);
  }

  function installSetting() {
    if (document.getElementById('loadingAnimationField')) return true;
    const settings = document.getElementById('settings');
    if (!settings) return false;
    const webCard = Array.from(settings.querySelectorAll('article.card')).find(card => {
      const text = card.querySelector(':scope > .card-title')?.textContent?.trim();
      return text === 'WEBUI' || text === 'OLED + WEB';
    });
    const grid = webCard?.querySelector('.formgrid');
    if (!grid) return false;
    const field = document.createElement('div');
    field.className = 'field span2';
    field.id = 'loadingAnimationField';
    field.innerHTML = `<label>LOADING ANIMATION</label><div class="loading-theme-control"><select id="loadingAnimationSelect">${THEMES.map(([id,label])=>`<option value="${esc(id)}">${esc(label)}</option>`).join('')}</select><button class="btn" id="loadingAnimationPreview" type="button">PREVIEW</button></div><div class="loading-theme-help" id="loadingAnimationHelp"></div>`;
    grid.appendChild(field);
    const select = document.getElementById('loadingAnimationSelect');
    const help = document.getElementById('loadingAnimationHelp');
    const syncHelp = () => {
      const row = THEMES.find(item => item[0] === select.value) || THEMES[0];
      help.textContent = row[2] + (row[0] === DEFAULT_THEME ? ' · Default' : '');
    };
    select.value = safeTheme(lastConfig?.web?.loading_animation || initialTheme());
    syncHelp();
    select.addEventListener('change', () => { syncHelp(); if (typeof window.setDirty === 'function') window.setDirty(true); else if (typeof setDirty === 'function') setDirty(true); });
    document.getElementById('loadingAnimationPreview').addEventListener('click', () => preview(select.value));
    return true;
  }

  function installHooks() {
    if (hooksInstalled) return true;
    // The first-paint theme engine now runs before app-core. Do not mark these
    // form hooks installed until the core functions actually exist; a later
    // initialization pass will attach them once app-core has loaded.
    if (typeof window.fillForm !== 'function' || typeof window.formConfig !== 'function') return false;
    hooksInstalled = true;
    const baseFill = window.fillForm;
    window.fillForm = function(c) { const out = baseFill(c); applyConfig(c); installSetting(); return out; };
    const baseForm = window.formConfig;
    window.formConfig = function() {
      const c = baseForm();
      c.web = c.web || {};
      c.web.loading_animation = safeTheme(document.getElementById('loadingAnimationSelect')?.value || lastConfig?.web?.loading_animation || DEFAULT_THEME);
      return c;
    };
    return true;
  }

  function preview(theme) {
    clearTimeout(previewTimer);
    document.getElementById('ywdLoadingPreview')?.remove();
    const overlay = document.createElement('div');
    overlay.id = 'ywdLoadingPreview';
    overlay.className = 'modal on ywd-loading-preview';
    overlay.innerHTML = `<div class="dialog ywd-startup-card"><div class="card-title">YWD // STARTUP PREVIEW</div><div class="who ywd-load-title">${esc((THEMES.find(x=>x[0]===safeTheme(theme))||THEMES[0])[1].toUpperCase())}</div><div class="hint ywd-load-status">Preview only · click anywhere to close</div></div>`;
    document.body.appendChild(overlay);
    const card = overlay.querySelector('.ywd-startup-card');
    const title = card.querySelector('.ywd-load-title');
    const host = document.createElement('div'); host.className = 'ywd-loader-scene'; title.insertAdjacentElement('beforebegin',host); ensureVisual(card,safeTheme(theme));
    const close = () => { clearTimeout(previewTimer); overlay.remove(); };
    overlay.addEventListener('click', close);
    previewTimer = setTimeout(close, 3600);
  }

  function refreshRuntimeData() {
    if (!document.getElementById('ywdStartupOverlay')) { clearInterval(pollTimer); pollTimer = null; return; }
    fetch('/api/status',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>{ if(d){lastStatus=d;updateDynamic(document.querySelector('#ywdStartupOverlay .ywd-loader-scene'));} }).catch(()=>{});
  }

  function init() {
    applyStartupTheme(initialTheme());
    installHooks();
    installSetting();
    fetch('/api/config',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>{ if(d?.config){ applyConfig(d.config); if(typeof window.fillForm==='function') window.fillForm(d.config); } }).catch(()=>{});
    refreshRuntimeData();
    if (!pollTimer && document.getElementById('ywdStartupOverlay')) pollTimer = setInterval(refreshRuntimeData, 450);
  }

  function installEarlyOverlayWatcher() {
    const apply = () => applyStartupTheme(initialTheme());
    if (apply()) return;
    if (!document.documentElement || typeof MutationObserver !== 'function') return;
    earlyObserver = new MutationObserver(() => {
      if (!apply()) return;
      earlyObserver?.disconnect();
      earlyObserver = null;
      clearTimeout(earlyObserverTimer);
      earlyObserverTimer = null;
    });
    earlyObserver.observe(document.documentElement, {childList:true, subtree:true});
    earlyObserverTimer = setTimeout(() => {
      earlyObserver?.disconnect();
      earlyObserver = null;
      earlyObserverTimer = null;
    }, 2000);
  }

  window.YWDStartupThemes = {
    init,
    applyStartupTheme,
    themes: THEMES.map(([id,label,description])=>({id,label,description})),
    defaultTheme: DEFAULT_THEME,
    preview,
  };

  // When this engine is bundled ahead of app.js, the observer sees the startup
  // overlay mutation and replaces the historical spinner in the same microtask
  // checkpoint, before the browser paints. The server-provided theme hint wins;
  // browser storage remains a fallback for older dashboard builds.
  installEarlyOverlayWatcher();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true}); else init();
})();
