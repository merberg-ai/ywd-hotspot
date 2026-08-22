'use strict';
(() => {
  function ensureLayoutStyle() {
    if (document.querySelector('link[data-ywd-instrument-layout="1"]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/instrumentation-layout.css?v=rc1.1';
    link.dataset.ywdInstrumentLayout = '1';
    link.onerror = () => console.error('YWD-Hotspot failed to load instrumentation layout CSS');
    document.head.appendChild(link);
  }

  function hasUsableRssi(d) {
    const rows = [];
    const cur = d?.activity?.current;
    if (cur && typeof cur === 'object') rows.push(cur);
    const heard = d?.activity?.lastheard;
    if (Array.isArray(heard)) rows.push(...heard);
    return rows.some(row => {
      const value = row?.rssi_dbm;
      return value != null && Number.isFinite(Number(value)) && Number(value) !== 0;
    });
  }

  function applyRssiAvailability(d) {
    // RSSI is optional at the modem-firmware layer. Some otherwise fully
    // compatible MMDVM_HS builds report BER/voice normally but return no RSSI.
    // In that case hide RSSI-only presentation instead of leaving a permanent
    // SAMPLING/blank meter. If a later call provides a real RSSI value, remove
    // the fallback layout and let the normal instrumentation renderer take over.
    const available = hasUsableRssi(d);
    const panel = document.getElementById('instrumentPanel');
    if (panel) panel.classList.toggle('rssi-unavailable', !available);
    if (available) return;

    const signal = document.querySelector('#instrumentPanel .signal-side');
    if (signal) signal.hidden = true;

    const rssiTrace = document.getElementById('rssiTraceRow');
    if (rssiTrace) rssiTrace.hidden = true;

    const history = document.getElementById('instrumentHistory');
    const berTrace = document.getElementById('berTraceRow');
    if (history && (!berTrace || berTrace.hidden)) history.hidden = true;
  }

  function renderInstrumentation(d) {
    try {
      window.YWDInstrumentation.render(d);
      applyRssiAvailability(d);
    } catch (e) {
      console.error('YWD instrumentation render failed', e);
    }
  }

  function wire() {
    ensureLayoutStyle();
    if (!window.YWDInstrumentation) return;
    if (typeof window.render === 'function' && !window.render.__ywdInstrumented) {
      const base = window.render;
      const wrapped = function(d) {
        base(d);
        renderInstrumentation(d);
      };
      wrapped.__ywdInstrumented = true;
      window.render = wrapped;
    }
    // The instrumentation/settings scripts load after app-core. Refresh the
    // already-present status/config once so the new controls do not wait for the
    // next normal dashboard cycle. This is initialization only, not a poll loop.
    fetch('/api/status', {cache:'no-store'}).then(r => r.ok ? r.json() : null).then(d => {
      if (d) renderInstrumentation(d);
    }).catch(() => {});
    fetch('/api/config', {cache:'no-store'}).then(r => r.ok ? r.json() : null).then(d => {
      if (d?.config && typeof window.fillForm === 'function') window.fillForm(d.config);
    }).catch(() => {});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire); else wire();
})();
