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

    const paths = ['display.enabled','display.brightness','display.idle_timeout_s','display.address'];
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
    if (button.dataset.ywdCheckingPolish === '3') return true;
    button.dataset.ywdCheckingPolish = '3';

    if (!button.querySelector('.ywd-check-spinner')) {
      const spin = document.createElement('span');
      spin.className = 'ywd-check-spinner';
      spin.setAttribute('aria-hidden', 'true');
      button.prepend(spin);
    }

    const sync = () => {
      const checking = badge.textContent.trim().toUpperCase() === 'CHECKING';
      button.classList.toggle('ywd-checking', checking);
      badge.classList.toggle('ywd-checking', checking);
      if (checking) button.setAttribute('aria-busy', 'true');
      else button.removeAttribute('aria-busy');
    };

    new MutationObserver(sync).observe(badge, {childList:true, characterData:true, subtree:true});
    button.addEventListener('click', () => {
      button.classList.add('ywd-checking');
      button.setAttribute('aria-busy', 'true');
      setTimeout(sync, 0);
    }, {capture:true});
    sync();
    return true;
  }

  function applyAlpha1826Polish() {
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
  loadStyle('/update.css?v=alpha18.2.6');
  loadStyle('/instrumentation.css?v=alpha12.1');
  loadStyle('/plugin-manager.css?v=alpha17');
  loadStyle('/backup-restore.css?v=alpha18.2.1');
  load('/app-core.js', () => load('/backup-restore.js?v=alpha18.2.1', () => load('/talkgroups.js?v=alpha12.1', () => load('/ui-polish.js?v=alpha12.2', () => load('/update.js?v=alpha12.3', () => load('/update-progress.js?v=alpha16.1', () => load('/instrumentation.js?v=alpha12.1', () => load('/instrumentation-bootstrap.js?v=alpha12.1', () => load('/plugin-manager-render.js?v=alpha18.2', () => load('/plugin-package-actions.js?v=alpha18.2', () => load('/plugin-package-upload.js?v=alpha18.2', () => load('/plugin-manager.js?v=alpha18.2', () => load('/plugin-config-actions.js?v=alpha16', () => load('/plugin-telemetry.js?v=alpha18', applyAlpha1826Polish))))))))))))));
})();
