'use strict';
(() => {
  const RF_PREFIX = 5_000_000;
  let installed = false;
  let passwordModal = null;

  const el = id => document.getElementById(id);
  const notify = (message, bad = false) => {
    if (typeof toast === 'function') toast(message, bad);
    else if (bad) console.error(message);
    else console.log(message);
  };

  async function apiPost(path, body) {
    const response = await fetch(path, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok || data.error || data.ok === false) {
      throw new Error(data.error || `Request failed (${response.status})`);
    }
    return data;
  }

  function currentConfig() {
    if (typeof state !== 'undefined' && state?.config?.tgif) return state.config.tgif;
    if (typeof configDoc !== 'undefined' && configDoc?.tgif) return configDoc.tgif;
    return null;
  }

  function authenticated() {
    return !!(typeof state !== 'undefined' && state?.controls?.authenticated);
  }

  function ensurePasswordModal() {
    if (passwordModal) return passwordModal;
    const overlay = document.createElement('div');
    overlay.className = 'modal';
    overlay.id = 'tgifPasswordModal';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.innerHTML = `
      <div class="dialog">
        <div class="card-title">TGIF SECURITY PASSWORD</div>
        <p class="hint">Use the secured hotspot/network password from TGIF User Security. It is stored on the Pi and is never returned to the browser.</p>
        <div class="field"><label>NEW TGIF PASSWORD</label><input id="tgifPasswordValue" type="password" autocomplete="new-password" maxlength="128"></div>
        <div class="field"><label>CONFIRM PASSWORD</label><input id="tgifPasswordConfirm" type="password" autocomplete="new-password" maxlength="128"></div>
        <div class="buttonrow"><button class="btn" id="tgifPasswordCancel" type="button">CANCEL</button><button class="btn primary" id="tgifPasswordSave" type="button">SAVE PASSWORD</button></div>
      </div>`;
    document.body.appendChild(overlay);
    el('tgifPasswordCancel').onclick = () => overlay.classList.remove('on');
    el('tgifPasswordSave').onclick = savePassword;
    passwordModal = overlay;
    return overlay;
  }

  function openPassword() {
    if (!authenticated()) return notify('Unlock WebUI controls first', true);
    const modal = ensurePasswordModal();
    el('tgifPasswordValue').value = '';
    el('tgifPasswordConfirm').value = '';
    modal.classList.add('on');
    setTimeout(() => el('tgifPasswordValue').focus(), 50);
  }

  async function savePassword() {
    const value = el('tgifPasswordValue').value;
    const confirm = el('tgifPasswordConfirm').value;
    if (!value) return notify('TGIF password cannot be empty', true);
    if (value !== confirm) return notify('TGIF passwords do not match', true);
    const button = el('tgifPasswordSave');
    button.disabled = true;
    try {
      await apiPost('/api/tgif/password', {password: value, apply: true});
      passwordModal.classList.remove('on');
      notify('TGIF security password saved');
      if (typeof getStatus === 'function') await getStatus();
      sync();
    } catch (err) {
      notify(err.message, true);
    } finally {
      button.disabled = false;
    }
  }

  async function saveSettings() {
    if (!authenticated()) return notify('Unlock WebUI controls first', true);
    const master = el('tgifMaster').value.trim();
    const port = Number(el('tgifPort').value);
    const enabled = el('tgifEnabled').checked;
    if (!master) return notify('TGIF master hostname is required', true);
    if (!Number.isInteger(port) || port < 1 || port > 65535) return notify('TGIF UDP port must be 1-65535', true);

    const button = el('tgifSaveApply');
    button.disabled = true;
    try {
      const result = await apiPost('/api/tgif/configure', {enabled, master, port, apply: true});
      const count = Array.isArray(result.changed) ? result.changed.length : 0;
      notify(count ? `TGIF settings applied (${count} change${count === 1 ? '' : 's'})` : 'No TGIF changes');
      if (typeof getStatus === 'function') await getStatus();
      if (typeof loadConfig === 'function') await loadConfig(true);
      sync();
    } catch (err) {
      notify(err.message, true);
      sync();
    } finally {
      button.disabled = false;
    }
  }

  function updateHelper() {
    const input = el('tgifTalkgroupHelper');
    const output = el('tgifRadioDestination');
    if (!input || !output) return;
    const tg = Number(input.value);
    if (!Number.isInteger(tg) || tg < 1 || tg > 999999) {
      output.textContent = 'Enter TGIF TG 1-999999';
      return;
    }
    output.textContent = `Radio group-call destination: ${RF_PREFIX + tg}`;
  }

  function sync() {
    const cfg = currentConfig();
    if (!cfg || !el('tgifSettingsCard')) return;
    const focused = document.activeElement;
    if (focused !== el('tgifMaster')) el('tgifMaster').value = cfg.master || 'tgif.network';
    if (focused !== el('tgifPort')) el('tgifPort').value = cfg.port || 62031;
    el('tgifEnabled').checked = !!cfg.enabled;
    el('tgifPasswordStatus').textContent = cfg.password_configured ? 'configured' : 'missing';
    el('tgifRuntimeIntent').textContent = cfg.enabled ? 'ENABLED — DMRGateway network 2' : 'DISABLED';
    const locked = !authenticated();
    ['tgifEnabled','tgifMaster','tgifPort','tgifSaveApply','tgifChangePassword'].forEach(id => {
      const node = el(id); if (node) node.disabled = locked;
    });
  }

  function install() {
    if (installed) return true;
    const settings = el('settings');
    if (!settings) return false;
    const firstGrid = settings.querySelector(':scope > .grid.two');
    if (!firstGrid) return false;

    const card = document.createElement('article');
    card.className = 'card';
    card.id = 'tgifSettingsCard';
    card.innerHTML = `
      <div class="card-title title-row"><span>TGIF NETWORK — EXPERIMENTAL</span><span id="tgifRuntimeIntent" class="badge">DISABLED</span></div>
      <p class="hint">Runs alongside BrandMeister through DMRGateway. TGIF group calls use the reserved 5xxxxxx RF namespace; normal talkgroup numbers continue to go to BrandMeister.</p>
      <div class="formgrid four">
        <div class="field span2"><label>MASTER HOSTNAME</label><input id="tgifMaster" value="tgif.network" maxlength="128"></div>
        <div class="field"><label>UDP PORT</label><input id="tgifPort" type="number" min="1" max="65535" value="62031"></div>
        <div class="field check"><label><input id="tgifEnabled" type="checkbox"> NETWORK ENABLED</label></div>
      </div>
      <div class="secretrow"><span>TGIF security password: <b id="tgifPasswordStatus">—</b></span><button class="btn ctl" id="tgifChangePassword" type="button">CHANGE</button></div>
      <div class="buttonrow wrap"><button class="btn primary ctl" id="tgifSaveApply" type="button">SAVE &amp; APPLY TGIF</button></div>
      <hr>
      <div class="field inline"><label>TGIF TG HELPER</label><input id="tgifTalkgroupHelper" inputmode="numeric" placeholder="31665" maxlength="6"><span id="tgifRadioDestination" class="hint">Example: TGIF 31665 → radio TG 5031665</span></div>
      <p class="hint">The prefix exists only on RF. DMRGateway removes the leading 5 before sending to TGIF and restores it on TGIF traffic sent back to the hotspot.</p>`;
    firstGrid.insertAdjacentElement('afterend', card);

    el('tgifChangePassword').onclick = openPassword;
    el('tgifSaveApply').onclick = saveSettings;
    el('tgifTalkgroupHelper').addEventListener('input', updateHelper);

    if (typeof render === 'function' && !render.__ywdTgifWrapped) {
      const baseRender = render;
      const wrapped = function(data) {
        const out = baseRender(data);
        sync();
        return out;
      };
      wrapped.__ywdTgifWrapped = true;
      render = wrapped;
    }

    installed = true;
    sync();
    return true;
  }

  const timer = setInterval(() => {
    if (install()) {
      sync();
      clearInterval(timer);
    }
  }, 100);
  setTimeout(() => clearInterval(timer), 15000);
})();
