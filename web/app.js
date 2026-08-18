'use strict';
(() => {
  function loadStyle(href) {
    const l = document.createElement('link');
    l.rel = 'stylesheet';
    l.href = href;
    l.onerror = () => console.error(`YWD-Hotspot failed to load ${href}`);
    document.head.appendChild(l);
  }

  function load(src, next) {
    const s = document.createElement('script');
    s.src = src;
    s.async = false;
    s.onload = () => next && next();
    s.onerror = () => console.error(`YWD-Hotspot failed to load ${src}`);
    document.head.appendChild(s);
  }

  function installAlpha1824Styles() {
    if (document.getElementById('alpha1824UiPolish')) return;
    const style = document.createElement('style');
    style.id = 'alpha1824UiPolish';
    style.textContent = `
      #checkUpdate.ywd-checking{display:inline-flex;align-items:center;gap:9px;cursor:wait}
      #checkUpdate.ywd-checking::before{content:"";width:14px;height:14px;flex:0 0 14px;border:2px solid rgba(98,233,255,.18);border-top-color:var(--cyan,#62e9ff);border-right-color:rgba(98,233,255,.72);border-radius:50%;animation:ywd-check-spin .72s linear infinite;box-shadow:0 0 10px rgba(98,233,255,.22)}
      #updateBadge.ywd-checking{position:relative;overflow:hidden;border-color:rgba(98,233,255,.72)!important;color:var(--cyan,#62e9ff)!important;box-shadow:0 0 0 1px rgba(98,233,255,.08),0 0 18px rgba(98,233,255,.18);animation:ywd-check-pulse 1.15s ease-in-out infinite}
      #updateBadge.ywd-checking::after{content:"";position:absolute;inset:-60% auto -60% -45%;width:42%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.34),transparent);transform:skewX(-18deg);animation:ywd-check-scan 1.05s ease-in-out infinite;pointer-events:none}
      #settings .webui-hint{margin:0 0 12px}
      @keyframes ywd-check-spin{to{transform:rotate(360deg)}}
      @keyframes ywd-check-pulse{0%,100%{filter:brightness(.92);box-shadow:0 0 0 1px rgba(98,233,255,.08),0 0 10px rgba(98,233,255,.10)}50%{filter:brightness(1.18);box-shadow:0 0 0 1px rgba(98,233,255,.18),0 0 24px rgba(98,233,255,.30)}}
      @keyframes ywd-check-scan{0%{left:-45%;opacity:0}20%{opacity:1}80%{opacity:1}100%{left:115%;opacity:0}}
      @media(prefers-reduced-motion:reduce){#checkUpdate.ywd-checking::before,#updateBadge.ywd-checking,#updateBadge.ywd-checking::after{animation:none}}
    `;
    document.head.appendChild(style);
  }

  function moveOledSettings() {
    const settings = document.getElementById('settings');
    const runtimeCard = document.getElementById('oledRuntimeSettingsCard');
    if (!settings || !runtimeCard) return false;

    const webCard = Array.from(settings.querySelectorAll('article.card')).find(card => {
      const title = card.querySelector(':scope > .card-title');
      const text = title?.textContent?.trim();
      return text === 'OLED + WEB' || text === 'WEBUI';
    });
    if (!webCard) return false;

    const title = webCard.querySelector(':scope > .card-title');
    if (title) title.textContent = 'WEBUI';

    const runtimeGrid = runtimeCard.querySelector('.formgrid');
    if (!runtimeGrid) return false;

    const paths = [
      'display.enabled',
      'display.brightness',
      'display.idle_timeout_s',
      'display.address'
    ];
    const moved = document.createDocumentFragment();
    paths.forEach(path => {
      const input = webCard.querySelector(`[data-cfg="${path}"]`);
      const field = input?.closest('.field');
      if (field) moved.appendChild(field);
    });
    if (moved.childNodes.length) runtimeGrid.insertBefore(moved, runtimeGrid.firstChild);

    if (!webCard.querySelector('.webui-hint')) {
      const hint = document.createElement('p');
      hint.className = 'hint webui-hint';
      hint.textContent = 'Dashboard listener settings. Changing these may move the WebUI to a different address or port after SAVE & APPLY.';
      title?.insertAdjacentElement('afterend', hint);
    }
    return true;
  }

  function installUpdateCheckingPolish() {
    const button = document.getElementById('checkUpdate');
    const badge = document.getElementById('updateBadge');
    if (!button || !badge) return false;
    if (button.dataset.ywdCheckingPolish === '1') return true;
    button.dataset.ywdCheckingPolish = '1';

    const sync = () => {
      const checking = badge.textContent.trim().toUpperCase() === 'CHECKING';
      button.classList.toggle('ywd-checking', checking);
      badge.classList.toggle('ywd-checking', checking);
      if (checking) button.setAttribute('aria-busy', 'true');
      else button.removeAttribute('aria-busy');
    };

    new MutationObserver(sync).observe(badge, {childList:true, characterData:true, subtree:true});
    button.addEventListener('click', () => setTimeout(sync, 0));
    sync();
    return true;
  }

  function applyAlpha1824Polish() {
    installAlpha1824Styles();
    let settingsDone = false;
    let updaterDone = false;
    let tries = 0;
    const tick = () => {
      tries += 1;
      settingsDone = moveOledSettings() || settingsDone;
      updaterDone = installUpdateCheckingPolish() || updaterDone;
      if ((settingsDone && updaterDone) || tries >= 100) clearInterval(timer);
    };
    const timer = setInterval(tick, 100);
    tick();
  }

  loadStyle('/ui-polish.css?v=alpha12.2');
  loadStyle('/update.css?v=alpha12.1');
  loadStyle('/instrumentation.css?v=alpha12.1');
  loadStyle('/plugin-manager.css?v=alpha17');
  loadStyle('/backup-restore.css?v=alpha18.2.1');
  load('/app-core.js', () => load('/backup-restore.js?v=alpha18.2.1', () => load('/talkgroups.js?v=alpha12.1', () => load('/ui-polish.js?v=alpha12.2', () => load('/update.js?v=alpha12.3', () => load('/update-progress.js?v=alpha16.1', () => load('/instrumentation.js?v=alpha12.1', () => load('/instrumentation-bootstrap.js?v=alpha12.1', () => load('/plugin-manager-render.js?v=alpha18.2', () => load('/plugin-package-actions.js?v=alpha18.2', () => load('/plugin-package-upload.js?v=alpha18.2', () => load('/plugin-manager.js?v=alpha18.2', () => load('/plugin-config-actions.js?v=alpha16', () => load('/plugin-telemetry.js?v=alpha18', applyAlpha1824Polish))))))))))))));
})();
