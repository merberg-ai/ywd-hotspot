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

  function installHeroHeader() {
    const topbar = document.querySelector('.topbar');
    const brand = topbar?.querySelector('.header-brand');
    if (!topbar || !brand) return false;

    if (topbar.dataset.ywdHero !== '1') {
      topbar.dataset.ywdHero = '1';
      topbar.classList.add('ywd-hero-topbar');
      brand.classList.add('ywd-hero-overlay');

      const oldLogo = brand.querySelector('.header-logo');
      if (oldLogo) oldLogo.hidden = true;

      const img = document.createElement('img');
      img.className = 'ywd-hero-banner';
      img.src = '/ywd-hotspot-banner.webp?v=alpha18.2.10';
      img.alt = '';
      img.setAttribute('aria-hidden', 'true');
      topbar.prepend(img);
    }

    let metaRow = topbar.parentElement?.querySelector(':scope > .ywd-hero-meta-row');
    if (!metaRow) {
      metaRow = document.createElement('div');
      metaRow.className = 'ywd-hero-meta-row';
      metaRow.setAttribute('aria-label', 'Build metadata');
      topbar.insertAdjacentElement('afterend', metaRow);
    }

    const buildMeta = brand.querySelector('.build-meta') || document.getElementById('buildMeta');
    if (buildMeta && buildMeta.parentElement !== metaRow) metaRow.appendChild(buildMeta);
    return true;
  }

  let duplexHooksInstalled = false;
  function installDuplexSettings() {
    const settings = document.getElementById('settings');
    if (!settings || typeof fillForm !== 'function' || typeof formConfig !== 'function' || typeof render !== 'function') return false;

    const identityCard = Array.from(settings.querySelectorAll('article.card')).find(card => {
      const title = card.querySelector(':scope > .card-title');
      return title?.textContent?.trim() === 'IDENTITY + RF';
    });
    const grid = identityCard?.querySelector('.formgrid');
    const simplexInput = document.getElementById('frequencyMhz');
    const simplexField = simplexInput?.closest('.field');
    if (!grid || !simplexInput || !simplexField) return false;

    simplexField.id = 'simplexFrequencyField';

    if (!document.getElementById('hatMode')) {
      const modeField = document.createElement('div');
      modeField.className = 'field';
      modeField.innerHTML = `<label>HAT MODE</label><select id="hatMode" data-cfg="radio.mode"><option value="simplex">Simplex</option><option value="duplex">Duplex</option></select>`;
      grid.insertBefore(modeField, simplexField);

      const rxField = document.createElement('div');
      rxField.className = 'field duplex-frequency-field';
      rxField.id = 'duplexRxFrequencyField';
      rxField.innerHTML = `<label>HOTSPOT RX FREQUENCY MHz</label><input id="duplexRxMhz" inputmode="decimal"><small>Frequency the hotspot receives from radios.</small>`;

      const txField = document.createElement('div');
      txField.className = 'field duplex-frequency-field';
      txField.id = 'duplexTxFrequencyField';
      txField.innerHTML = `<label>HOTSPOT TX FREQUENCY MHz</label><input id="duplexTxMhz" inputmode="decimal"><small>Frequency the hotspot transmits to radios.</small>`;

      simplexField.insertAdjacentElement('afterend', rxField);
      rxField.insertAdjacentElement('afterend', txField);

      const hint = document.createElement('p');
      hint.id = 'duplexModeHint';
      hint.className = 'hint duplex-mode-hint';
      hint.textContent = 'Simplex uses one RF frequency and DMR slot 2. Duplex uses separate hotspot RX/TX frequencies and enables DMR slots 1 + 2.';
      identityCard.appendChild(hint);
    }

    const mode = document.getElementById('hatMode');
    const rxInput = document.getElementById('duplexRxMhz');
    const txInput = document.getElementById('duplexTxMhz');
    const rxField = document.getElementById('duplexRxFrequencyField');
    const txField = document.getElementById('duplexTxFrequencyField');
    if (!mode || !rxInput || !txInput || !rxField || !txField) return false;

    const mhzText = value => (Number(value || 0) / 1e6).toFixed(6).replace(/0+$/, '').replace(/\.$/, '');
    const syncMode = () => {
      const duplex = mode.value === 'duplex';
      simplexField.hidden = duplex;
      simplexInput.disabled = duplex;
      rxField.hidden = !duplex;
      txField.hidden = !duplex;
      rxInput.disabled = !duplex;
      txInput.disabled = !duplex;
      identityCard.classList.toggle('duplex-selected', duplex);
    };

    if (!duplexHooksInstalled) {
      duplexHooksInstalled = true;
      const baseFillForm = fillForm;
      fillForm = function(c) {
        baseFillForm(c);
        const r = c?.radio || {};
        if (document.getElementById('duplexRxMhz')) document.getElementById('duplexRxMhz').value = mhzText(r.rx_frequency_hz ?? r.frequency_hz);
        if (document.getElementById('duplexTxMhz')) document.getElementById('duplexTxMhz').value = mhzText(r.tx_frequency_hz ?? r.frequency_hz);
        syncMode();
      };

      const baseFormConfig = formConfig;
      formConfig = function() {
        const c = baseFormConfig();
        const selectedMode = document.getElementById('hatMode')?.value === 'duplex' ? 'duplex' : 'simplex';
        c.radio.mode = selectedMode;
        const rxMhz = Number(document.getElementById('duplexRxMhz')?.value);
        const txMhz = Number(document.getElementById('duplexTxMhz')?.value);
        if (selectedMode === 'duplex') {
          if (!Number.isFinite(rxMhz) || rxMhz <= 0) throw Error('Duplex hotspot RX frequency must be a valid MHz value');
          if (!Number.isFinite(txMhz) || txMhz <= 0) throw Error('Duplex hotspot TX frequency must be a valid MHz value');
          c.radio.rx_frequency_hz = Math.round(rxMhz * 1e6);
          c.radio.tx_frequency_hz = Math.round(txMhz * 1e6);
        } else {
          if (Number.isFinite(rxMhz) && rxMhz > 0) c.radio.rx_frequency_hz = Math.round(rxMhz * 1e6);
          if (Number.isFinite(txMhz) && txMhz > 0) c.radio.tx_frequency_hz = Math.round(txMhz * 1e6);
        }
        return c;
      };

      const baseRender = render;
      render = function(d) {
        baseRender(d);
        const r = d?.config?.radio || {};
        const duplex = r.mode === 'duplex';
        const summary = document.getElementById('radioSummary');
        if (summary) {
          summary.innerHTML = duplex
            ? kv('HAT mode', 'Duplex') +
              kv('RX frequency', `${(Number(r.rx_frequency_hz || 0) / 1e6).toFixed(6)} MHz`) +
              kv('TX frequency', `${(Number(r.tx_frequency_hz || 0) / 1e6).toFixed(6)} MHz`) +
              kv('DMR slots', '1 + 2') +
              kv('Color code', r.color_code) +
              kv('RX / TX offset', `${r.rx_offset} / ${r.tx_offset} Hz`)
            : kv('HAT mode', 'Simplex') +
              kv('Frequency', `${(Number(r.frequency_hz || 0) / 1e6).toFixed(6)} MHz`) +
              kv('DMR slot', '2') +
              kv('Color code', r.color_code) +
              kv('RX / TX offset', `${r.rx_offset} / ${r.tx_offset} Hz`);
        }
      };
    }

    if (mode.dataset.ywdDuplexBound !== '1') {
      mode.dataset.ywdDuplexBound = '1';
      const mark = () => { syncMode(); setDirty(true); };
      mode.addEventListener('change', mark);
      [rxInput, txInput].forEach(el => {
        el.addEventListener('input', () => setDirty(true));
        el.addEventListener('change', () => setDirty(true));
      });
    }

    if (typeof configDoc !== 'undefined' && configDoc?.radio) {
      mode.value = configDoc.radio.mode || 'simplex';
      rxInput.value = mhzText(configDoc.radio.rx_frequency_hz ?? configDoc.radio.frequency_hz);
      txInput.value = mhzText(configDoc.radio.tx_frequency_hz ?? configDoc.radio.frequency_hz);
    }
    syncMode();
    if (typeof state !== 'undefined' && state) render(state);
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

    new MutationObserver(sync).observe(badge, {childList:true, characterData:true,subtree:true});
    button.addEventListener('click', () => {
      button.classList.add('ywd-checking');
      button.setAttribute('aria-busy', 'true');
      setTimeout(sync, 0);
    }, {capture:true});
    sync();
    return true;
  }

  function installConfirmFirstSaveApply() {
    const button = document.getElementById('applyConfig');
    if (!button) return false;
    if (button.dataset.ywdConfirmFirst === '1') return true;
    button.dataset.ywdConfirmFirst = '1';

    button.onclick = async () => {
      try {
        const c = formConfig();
        const pending = typeof state !== 'undefined' && !!state?.pending?.pending;
        const changed = !configDoc || JSON.stringify(c) !== JSON.stringify(configDoc);
        if (!changed && !pending) {
          toast('No settings changes to apply');
          return;
        }
        if (typeof window.ywdConfirm !== 'function') {
          throw new Error('YWD confirmation UI is unavailable. Reload the dashboard and try again.');
        }
        const ok = await window.ywdConfirm({
          title: 'SAVE + APPLY CONFIGURATION',
          message: 'Save and apply these settings now?\n\nAffected services may restart.',
          confirmText: 'SAVE + APPLY',
          cancelText: 'CANCEL',
          tone: 'warn',
          kicker: 'YWD // HOTSPOT'
        });
        if (!ok) {
          toast('Save & Apply canceled — nothing changed');
          return;
        }

        await post('/api/config/save', {config: c});
        configDoc = c;
        setDirty(false);
        const a = await post('/api/config/apply', {});
        toast(a.changed?.length ? 'Configuration applied' : 'Configuration already applied');
        if (a.dashboard_restart_pending) {
          const port = a.new_port;
          toast(`Dashboard restarting${port ? ' on port ' + port : ''}…`);
          if (port && Number(port) !== Number(location.port || 80)) {
            setTimeout(() => { location.href = `${location.protocol}//${location.hostname}:${port}/`; }, 4500);
          }
        }
        setTimeout(() => { getStatus(); loadConfig(true); }, 800);
      } catch (e) {
        toast(e.message, true);
      }
    };
    return true;
  }

  function applyAlpha21Polish() {
    let settingsDone = false;
    let updaterDone = false;
    let heroDone = false;
    let duplexDone = false;
    let saveApplyDone = false;
    let tries = 0;
    const tick = () => {
      tries += 1;
      settingsDone = moveOledSettings() || settingsDone;
      updaterDone = installUpdateCheckingPolish() || updaterDone;
      heroDone = installHeroHeader() || heroDone;
      duplexDone = installDuplexSettings() || duplexDone;
      saveApplyDone = installConfirmFirstSaveApply() || saveApplyDone;
      if ((settingsDone && updaterDone && heroDone && duplexDone && saveApplyDone) || tries >= 100) clearInterval(timer);
    };
    const timer = setInterval(tick, 100);
    tick();
  }

  loadStyle('/ui-polish.css?v=alpha18.2.7');
  loadStyle('/hero-layout.css?v=alpha21.1');
  loadStyle('/update.css?v=alpha18.2.6');
  loadStyle('/instrumentation.css?v=alpha12.1');
  loadStyle('/plugin-manager.css?v=alpha17');
  loadStyle('/plugin-ui.css?v=alpha19');
  loadStyle('/backup-restore.css?v=alpha18.2.1');
  loadStyle('/system-ui.css?v=dashboard1');
  load('/app-core.js', () => load('/backup-restore.js?v=alpha18.2.1', () => load('/talkgroups.js?v=alpha12.1', () => load('/ui-polish.js?v=alpha12.2', () => load('/update.js?v=alpha12.3', () => load('/update-progress.js?v=alpha16.1', () => load('/instrumentation.js?v=alpha12.1', () => load('/instrumentation-bootstrap.js?v=alpha12.1', () => load('/plugin-manager-render.js?v=alpha18.2', () => load('/plugin-package-actions.js?v=alpha18.2', () => load('/plugin-package-upload.js?v=alpha18.2', () => load('/plugin-manager.js?v=alpha18.2', () => load('/plugin-config-actions.js?v=alpha16', () => load('/plugin-telemetry.js?v=alpha18', () => load('/plugin-ui-host.js?v=alpha20.3', () => load('/system-ui.js?v=dashboard1', applyAlpha21Polish))))))))))))))));
})();
