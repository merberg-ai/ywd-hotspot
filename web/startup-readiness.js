'use strict';
(() => {
  const HOLD_CLASS = 'ywd-startup-held';
  const READY_FLAG = '__YWD_DASHBOARD_FULLY_READY';
  const START = Date.now();
  let overlay = null;
  let overlayObserver = null;
  let interval = null;
  let continueOffered = false;

  const style = document.createElement('style');
  style.textContent = `
    #ywdStartupOverlay.${HOLD_CLASS}{opacity:1!important;visibility:visible!important;pointer-events:auto!important}
    #ywdStartupOverlay.${HOLD_CLASS}.ywd-startup-out{opacity:1!important;visibility:visible!important;pointer-events:auto!important}
    #ywdStartupOverlay .ywd-startup-continue{margin-top:12px}
  `;
  document.head.appendChild(style);

  function dataReady() {
    try {
      return typeof state !== 'undefined' && !!state && typeof configDoc !== 'undefined' && !!configDoc;
    } catch (_) {
      return false;
    }
  }

  function heroReady() {
    const hero = document.querySelector('.ywd-hero-banner');
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

  function releaseUiReady() {
    return window.__YWD_RELEASE_UI_READY === true;
  }

  function fullyReady() {
    return dataReady() && heroReady() && layoutReady() && releaseUiReady() && systemExtensionsMounted();
  }

  function statusText() {
    if (!dataReady()) return 'Loading appliance status and configuration…';
    if (!document.querySelector('.ywd-hero-banner')) return 'Assembling dashboard interface…';
    if (!heroReady()) return 'Loading YWD dashboard artwork…';
    if (!layoutReady()) return 'Building System controls…';
    if (!releaseUiReady()) {
      const p = window.__YWD_RELEASE_UI_PROGRESS || {};
      const loaded = Number(p.loaded || 0);
      const total = Number(p.total || 0);
      return total ? `Loading RC4 interface modules… ${loaded}/${total}` : 'Loading RC4 interface modules…';
    }
    if (!systemExtensionsMounted()) return 'Registering System tools…';
    return 'Dashboard ready';
  }

  function setStatus(message) {
    const node = document.getElementById('ywdStartupStatus');
    if (node) node.textContent = message;
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
