'use strict';
(() => {
  const HOLD_CLASS = 'ywd-startup-held';
  const READY_FLAG = '__YWD_DASHBOARD_FULLY_READY';
  const START = Date.now();
  const SETTLE_MS = 500;
  let overlay = null;
  let overlayObserver = null;
  let interval = null;
  let continueOffered = false;
  let structuralReadyAt = 0;

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
    return dataReady() && layoutReady() && releaseUiReady() && systemExtensionsMounted();
  }

  function fullyReady() {
    if (!structuralReady()) {
      structuralReadyAt = 0;
      return false;
    }

    // The hero banner is a late cosmetic transform in app.js, not a functional
    // dashboard dependency. If it exists, wait for the image to finish. If it
    // has not been inserted yet, give the final DOM transforms a short settling
    // window but never let a missing decorative image deadlock startup.
    const hero = heroElement();
    if (hero && !heroReady()) return false;
    if (!structuralReadyAt) structuralReadyAt = Date.now();
    return Date.now() - structuralReadyAt >= SETTLE_MS;
  }

  function statusText() {
    if (!dataReady()) return 'Loading appliance status and configuration…';
    if (!layoutReady()) return 'Loading dashboard modules and building interface…';
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
  interval = setInterval(tick, 80);
  tick();
})();
