'use strict';
(() => {
  const ACTIONS = {
    tgifCcSave: {path:'/api/tgif/control/save', label:'SAVING…'},
    tgifCcStart: {path:'/api/tgif/control/start', label:'STARTING…'},
    tgifCcHoldBtn: {path:'/api/tgif/control/hold', label:'HOLDING…'},
    tgifCcResume: {path:'/api/tgif/control/resume', label:'RESUMING…'},
    tgifCcNext: {path:'/api/tgif/control/next', label:'NEXT…'},
    tgifCcStop: {path:'/api/tgif/control/stop', label:'STOPPING…'},
    tgifCcDisconnect: {path:'/api/tgif/control/disconnect', label:'DISCONNECTING…'},
  };
  const BY_PATH = Object.fromEntries(Object.entries(ACTIONS).map(([id,row]) => [row.path,id]));
  const busyTimers = new Map();
  let pollBusy = false;

  const el = id => document.getElementById(id);

  function setBusy(id) {
    const button = el(id), spec = ACTIONS[id];
    if (!button || !spec || button.dataset.ywdBusy === '1') return;
    button.dataset.ywdBusy = '1';
    button.dataset.ywdBusyLabel = button.textContent;
    button.setAttribute('aria-busy','true');
    button.setAttribute('aria-disabled','true');
    button.innerHTML = `<span class="tgif-action-spinner" aria-hidden="true"></span><span>${spec.label}</span>`;
    clearTimeout(busyTimers.get(id));
    busyTimers.set(id, setTimeout(() => clearBusy(id), 20000));
  }

  function clearBusy(id) {
    const button = el(id);
    if (!button || button.dataset.ywdBusy !== '1') return;
    const label = button.dataset.ywdBusyLabel || button.textContent;
    clearTimeout(busyTimers.get(id));
    busyTimers.delete(id);
    button.textContent = label;
    button.removeAttribute('aria-busy');
    button.removeAttribute('aria-disabled');
    delete button.dataset.ywdBusy;
    delete button.dataset.ywdBusyLabel;
  }

  function pathOf(input) {
    try {
      const raw = typeof input === 'string' ? input : input?.url;
      return new URL(raw, location.origin).pathname;
    } catch (_) { return ''; }
  }

  function installFetchFeedback() {
    if (window.fetch.__ywdTgifPolishWrapped) return;
    const baseFetch = window.fetch.bind(window);
    const wrapped = async function(input, init) {
      const path = pathOf(input);
      const buttonId = BY_PATH[path];
      try {
        return await baseFetch(input, init);
      } finally {
        if (buttonId) clearBusy(buttonId);
      }
    };
    wrapped.__ywdTgifPolishWrapped = true;
    window.fetch = wrapped;
  }

  function installClickFeedback() {
    document.addEventListener('click', event => {
      const button = event.target.closest('button');
      if (!button || !ACTIONS[button.id] || button.disabled) return;
      if (button.dataset.ywdBusy === '1') {
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
      // Do not set the native disabled property here. This listener runs during
      // capture, and disabling the target before its own click handler executes
      // can suppress the real control action in some browsers. aria-busy plus
      // pointer-events/duplicate-click suppression gives immediate feedback
      // without stealing the first click from the proven Control Center code.
      setBusy(button.id);
    }, true);
  }

  function renameBmTab() {
    const tab = document.querySelector('.tabs [data-tab="talkgroups"]');
    if (!tab) return false;
    if (tab.textContent !== 'BM TALKGROUPS') tab.textContent = 'BM TALKGROUPS';
    tab.title = 'BrandMeister Talkgroups';
    return true;
  }

  function installBmTabRename() {
    const attach = () => {
      const tabs = document.querySelector('.tabs');
      if (!tabs) return false;
      renameBmTab();
      if (!tabs.__ywdBmTalkgroupObserver) {
        const observer = new MutationObserver(() => renameBmTab());
        observer.observe(tabs, {childList:true, subtree:true});
        tabs.__ywdBmTalkgroupObserver = observer;
      }
      return true;
    };
    if (attach()) return;
    const retry = setInterval(() => {
      if (attach()) clearInterval(retry);
    }, 120);
    setTimeout(() => clearInterval(retry), 60000);
  }

  function ensureStatusCard() {
    const page = el('status');
    if (!page) return null;
    let card = el('tgifScannerStatusCard');
    if (card) return card;
    card = document.createElement('article');
    card.id = 'tgifScannerStatusCard';
    card.className = 'card tgif-status-scanner';
    card.hidden = true;
    card.innerHTML = `
      <div class="card-title title-row"><span>TGIF SCANNER</span><span id="tgifStatusScannerBadge" class="tgif-status-badge">SCANNING</span></div>
      <div class="tgif-status-layout">
        <div class="tgif-status-scope" aria-hidden="true">
          <div class="tgif-status-grid"></div>
          <div class="tgif-status-sweep"></div>
          <div class="tgif-status-lock"><i></i><i></i><i></i></div>
          <div class="tgif-status-centerline"></div>
        </div>
        <div class="tgif-status-copy">
          <div id="tgifStatusScannerTg" class="tgif-status-tg">TG —</div>
          <div id="tgifStatusScannerName" class="tgif-status-name">Waiting for scanner state</div>
          <div id="tgifStatusScannerRf" class="tgif-status-rf">RF —</div>
          <div id="tgifStatusScannerDetail" class="tgif-status-detail">—</div>
        </div>
      </div>`;
    const firstGrid = page.querySelector(':scope > .grid.two');
    if (firstGrid) firstGrid.insertAdjacentElement('afterend', card);
    else page.prepend(card);
    return card;
  }

  function scannerDetail(runtime) {
    const stateName = String(runtime?.state || '').toLowerCase();
    const reason = String(runtime?.hold_reason || '').toLowerCase();
    if (stateName.includes('hold')) {
      if (reason === 'traffic') return 'Traffic detected · holding this talkgroup';
      if (reason === 'post-call') return 'Post-call hold before scanning resumes';
      if (reason === 'manual') return 'Manual hold · press RESUME to continue';
      return 'Scanner hold active';
    }
    const remaining = Number(runtime?.dwell_remaining_s);
    return Number.isFinite(remaining) ? `${Math.max(0, Math.ceil(remaining))}s dwell remaining` : 'Scanning watchlist';
  }

  function renderStatusScanner(data) {
    const card = ensureStatusCard();
    if (!card) return;
    const runtime = data?.runtime || {};
    const active = !!data?.service_active;
    const stateName = String(runtime.state || '').toLowerCase();
    if (!active || !['scanning','holding','starting'].includes(stateName)) {
      card.hidden = true;
      card.classList.remove('is-holding','is-scanning','is-starting');
      return;
    }
    const holding = stateName === 'holding';
    card.hidden = false;
    card.classList.toggle('is-holding', holding);
    card.classList.toggle('is-scanning', stateName === 'scanning');
    card.classList.toggle('is-starting', stateName === 'starting');
    const badge = el('tgifStatusScannerBadge');
    if (badge) badge.textContent = holding ? 'HOLDING' : stateName === 'starting' ? 'STARTING' : 'SCANNING';
    const tg = runtime.current_tg;
    const name = runtime.current_name || '';
    const rf = runtime.current_rf_tg;
    const slot = runtime.slot || data?.preferences?.slot || 2;
    if (el('tgifStatusScannerTg')) el('tgifStatusScannerTg').textContent = tg ? `TG ${tg}` : 'TG —';
    if (el('tgifStatusScannerName')) el('tgifStatusScannerName').textContent = name || (tg ? 'TGIF talkgroup' : 'Selecting talkgroup…');
    if (el('tgifStatusScannerRf')) el('tgifStatusScannerRf').textContent = rf ? `RF ${rf} · TS${slot}` : `TS${slot}`;
    if (el('tgifStatusScannerDetail')) el('tgifStatusScannerDetail').textContent = scannerDetail(runtime);
  }

  function statusVisible() {
    return !document.hidden && !!el('status')?.classList.contains('on');
  }

  async function pollStatus() {
    if (pollBusy || !statusVisible()) return;
    pollBusy = true;
    try {
      const response = await fetch('/api/tgif/control/status', {cache:'no-store', credentials:'same-origin'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      renderStatusScanner(data);
    } catch (_) {
      const card = el('tgifScannerStatusCard');
      if (card) card.hidden = true;
    } finally {
      pollBusy = false;
    }
  }

  function installStatusPolling() {
    ensureStatusCard();
    pollStatus();
    setInterval(pollStatus, 1200);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) pollStatus(); });
    document.querySelector('.tabs [data-tab="status"]')?.addEventListener('click', () => setTimeout(pollStatus, 0));
  }

  function install() {
    installFetchFeedback();
    installClickFeedback();
    installBmTabRename();
    ensureStatusCard();
    installStatusPolling();
  }

  install();
})();
