'use strict';
(() => {
  const HOLD_CLASS = 'ywd-startup-held';
  const READY_FLAG = '__YWD_DASHBOARD_FULLY_READY';
  const START = Date.now();
  const SETTLE_MS = 500;
  const LEGACY_MODULES = [
    '/app-core.js',
    '/backup-restore.js?v=alpha18.2.1',
    '/talkgroups.js?v=alpha12.1',
    '/ui-polish.js?v=alpha12.2',
    '/update.js?v=alpha12.3',
    '/update-progress.js?v=alpha16.1',
    '/instrumentation.js?v=alpha12.1',
    '/instrumentation-bootstrap.js?v=alpha12.1',
    '/plugin-manager-render.js?v=alpha18.2',
    '/plugin-package-actions.js?v=alpha18.2',
    '/plugin-package-upload.js?v=alpha18.2',
    '/plugin-manager.js?v=alpha18.2',
    '/plugin-config-actions.js?v=alpha16',
    '/plugin-telemetry.js?v=alpha18',
    '/plugin-ui-host.js?v=alpha20.3',
    '/system-ui.js?v=dashboard1',
    '/ssh-key-export.js?v=rc1-system2',
  ];
  let overlay = null;
  let overlayObserver = null;
  let interval = null;
  let continueOffered = false;
  let structuralReadyAt = 0;

  window.__YWD_LEGACY_UI_PROGRESS = window.__YWD_LEGACY_UI_PROGRESS || {
    loaded: 0,
    total: LEGACY_MODULES.length,
    failed: 0,
    current: null,
    failedSources: [],
  };

  // The legacy app loader executes modules in dependency order. Preload them
  // all up front so a Pi Zero does not pay 17 separate network round trips
  // serially before System/UI polish can finish.
  LEGACY_MODULES.forEach(src => {
    const link = document.createElement('link');
    link.rel = 'preload';
    link.as = 'script';
    link.href = src;
    document.head.appendChild(link);
  });

  function dataReady() {
    try {
      return typeof state !== 'undefined' && !!state && typeof configDoc !== 'undefined' && !!configDoc;
    } catch (_) {
      return false;
    }
  }

  function heroElement() {
    return document.querySelector('.ywd-hero-banner');
  }

  function heroReady() {
    const hero = heroElement();
    return !!hero && hero.complete && hero.naturalWidth > 0;
  }

  function legacyProgress() {
    const p = window.__YWD_LEGACY_UI_PROGRESS;
    return p && typeof p === 'object' ? p : {};
  }

  function legacyReady() {
    const p = legacyProgress();
    const total = Number(p.total || LEGACY_MODULES.length);
    return Number(p.loaded || 0) >= total && Number(p.failed || 0) === 0;
  }

  function layoutReady() {
    return !!document.querySelector('.tabs [data-tab="system"]')
      && !!document.getElementById('system')
      && !!document.getElementById('hostPowerCard');
  }

  function systemExtensionsMounted() {
    return !!document.getElementById('mmdvmInfoCard')
      && !!document.getElementById('vocoderManagerCard');
  }

  function releaseUiProgress() {
    const p = window.__YWD_RELEASE_UI_PROGRESS;
    return p && typeof p === 'object' ? p : {};
  }

  function releaseUiReady() {
    const p = releaseUiProgress();
    return window.__YWD_RELEASE_UI_READY === true && Number(p.failed || 0) === 0;
  }

  function structuralReady() {
    return dataReady() && legacyReady() && layoutReady() && releaseUiReady() && systemExtensionsMounted();
  }

  function fullyReady() {
    if (!structuralReady()) {
      structuralReadyAt = 0;
      return false;
    }

    const hero = heroElement();
    if (hero && !heroReady()) return false;
    if (!structuralReadyAt) structuralReadyAt = Date.now();
    return Date.now() - structuralReadyAt >= SETTLE_MS;
  }

  function statusText() {
    if (!dataReady()) return 'Loading appliance status and configuration…';

    const lp = legacyProgress();
    const legacyLoaded = Number(lp.loaded || 0);
    const legacyTotal = Number(lp.total || LEGACY_MODULES.length);
    const legacyFailed = Number(lp.failed || 0);
    if (!legacyReady()) {
      if (legacyFailed > 0) {
        const failed = Array.isArray(lp.failedSources) && lp.failedSources.length
          ? lp.failedSources[lp.failedSources.length - 1]
          : 'unknown module';
        return `Dashboard module failed to load: ${failed}. Keeping the dashboard covered for safety…`;
      }
      const current = String(lp.current || '').replace(/^\//, '').split('?')[0];
      return current
        ? `Loading dashboard modules… ${legacyLoaded}/${legacyTotal} · ${current}`
        : `Loading dashboard modules… ${legacyLoaded}/${legacyTotal}`;
    }

    if (!layoutReady()) return 'Building dashboard interface…';
    if (!releaseUiReady()) {
      const p = releaseUiProgress();
      const loaded = Number(p.loaded || 0);
      const total = Number(p.total || 0);
      const failed = Number(p.failed || 0);
      if (failed > 0) return `RC4 interface module load failed (${failed}). Keeping the dashboard covered for safety…`;
      return total ? `Loading RC4 interface modules… ${loaded}/${total}` : 'Loading RC4 interface modules…';
    }
    if (!systemExtensionsMounted()) return 'Registering System tools…';
    if (heroElement() && !heroReady()) return 'Loading YWD dashboard artwork…';
    return 'Finalizing dashboard interface…';
  }

  function setStatus(message) {
    const node = document.getElementById('ywdStartupStatus');
    if (node && node.textContent !== message) node.textContent = message;
  }

  function attachOverlay(node) {
    if (!node || node.dataset.ywdReadinessHold === '1') return;
    overlay = node;
    overlay.dataset.ywdReadinessHold = '1';
    overlay.classList.add(HOLD_CLASS);
    overlay.setAttribute('aria-busy', 'true');

    const nativeRemove = Element.prototype.remove;
    overlay.remove = function() {
      if (!window[READY_FLAG] && this.dataset.ywdContinue !== '1') {
        this.classList.remove('ywd-startup-out');
        this.classList.add(HOLD_CLASS);
        this.setAttribute('aria-busy', 'true');
        return;
      }
      nativeRemove.call(this);
    };

    overlayObserver?.disconnect();
    overlayObserver = new MutationObserver(() => {
      if (!overlay || window[READY_FLAG] || overlay.dataset.ywdContinue === '1') return;
      if (overlay.classList.contains('ywd-startup-out')) overlay.classList.remove('ywd-startup-out');
      overlay.classList.add(HOLD_CLASS);
      overlay.setAttribute('aria-busy', 'true');
    });
    overlayObserver.observe(overlay, {attributes:true, attributeFilter:['class','aria-busy']});
    setStatus(statusText());
  }

  function offerContinue() {
    if (!overlay || continueOffered || window[READY_FLAG]) return;
    continueOffered = true;
    setStatus('Dashboard is taking longer than expected to assemble. You can keep waiting or continue to the partially loaded interface.');
    const card = overlay.querySelector('.ywd-startup-card');
    if (!card || card.querySelector('.ywd-startup-continue')) return;
    const button = document.createElement('button');
    button.className = 'btn ywd-startup-continue';
    button.type = 'button';
    button.textContent = 'CONTINUE';
    button.onclick = () => {
      overlay.dataset.ywdContinue = '1';
      overlay.classList.remove(HOLD_CLASS);
      overlay.setAttribute('aria-busy', 'false');
      overlay.classList.add('ywd-startup-out');
      setTimeout(() => Element.prototype.remove.call(overlay), 220);
    };
    card.appendChild(button);
  }

  function finish() {
    if (!overlay || window[READY_FLAG]) return;
    window[READY_FLAG] = true;
    clearInterval(interval);
    overlayObserver?.disconnect();
    setStatus('Dashboard ready');
    overlay.classList.remove(HOLD_CLASS);
    overlay.setAttribute('aria-busy', 'false');
    requestAnimationFrame(() => {
      overlay.classList.add('ywd-startup-out');
      setTimeout(() => Element.prototype.remove.call(overlay), 220);
    });
  }

  function tick() {
    const current = document.getElementById('ywdStartupOverlay');
    if (current && current !== overlay) attachOverlay(current);
    if (!overlay) return;
    if (fullyReady()) {
      finish();
      return;
    }
    setStatus(statusText());
    if (Date.now() - START > 45000) offerContinue();
  }

  const rootObserver = new MutationObserver(tick);
  rootObserver.observe(document.documentElement, {childList:true, subtree:true});
  window.addEventListener('ywd:release-ui-ready', tick);
  window.addEventListener('ywd:legacy-ui-progress', tick);
  interval = setInterval(tick, 80);
  tick();
})();
