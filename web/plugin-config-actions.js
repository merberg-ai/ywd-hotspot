'use strict';
(() => {
  async function post(url, body) {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {})
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  function collectConfig(id) {
    const config = {};
    document.querySelectorAll(`#plugins [data-plugin-config="${id}"]`).forEach(input => {
      const key = input.dataset.pluginField;
      const type = input.dataset.fieldType;
      if (type === 'boolean') config[key] = !!input.checked;
      else if (type === 'integer') config[key] = Number(input.value);
      else config[key] = input.value;
    });
    return config;
  }

  function showResult(id, message, bad = false) {
    const result = document.getElementById(`pluginResult-${id}`);
    if (!result) return;
    result.hidden = false;
    result.className = `plugin-result ${bad ? 'bad' : 'good'}`;
    result.textContent = message;
  }

  function notify(message, bad = false) {
    try {
      if (typeof window.toast === 'function') {
        window.toast(message, bad);
        return;
      }
    } catch (_) {}
    console[bad ? 'error' : 'log'](message);
  }

  function markConfigPresent(card) {
    if (!card) return;
    card.querySelectorAll('.plugin-package-meta > div').forEach(row => {
      const label = row.querySelector('span')?.textContent?.trim().toLowerCase();
      if (label !== 'config') return;
      const value = row.querySelector('b');
      if (value) value.textContent = 'PRESENT';
    });
  }

  function syncButtons() {
    document.querySelectorAll('#plugins .plugin-card[data-plugin-card]').forEach(card => {
      const id = card.dataset.pluginCard;
      const save = card.querySelector('[data-plugin-action="config-save"]');
      const restart = card.querySelector('[data-plugin-action="service-restart"]');
      if (!save || !restart) return;

      if (save.textContent !== 'SAVE') save.textContent = 'SAVE';

      let combined = card.querySelector('[data-plugin-action="config-save-restart"]');
      if (!combined) {
        combined = document.createElement('button');
        combined.className = 'btn good';
        combined.dataset.pluginAction = 'config-save-restart';
        combined.dataset.pluginId = id;
        combined.textContent = 'SAVE + RESTART PLUGIN';
        save.parentElement?.appendChild(combined);
      }
      const shouldDisable = !!save.disabled || !!restart.disabled || combined.dataset.pluginBusy === '1';
      if (combined.disabled !== shouldDisable) combined.disabled = shouldDisable;
    });
  }

  async function saveAndRestart(button) {
    const id = button.dataset.pluginId || '';
    const card = button.closest('.plugin-card');
    const name = card?.querySelector('.plugin-title h3')?.textContent?.trim() || id;

    if (typeof window.ywdConfirm !== 'function') {
      throw new Error('YWD confirmation UI is unavailable. Reload the dashboard and try again.');
    }
    const ok = await window.ywdConfirm({
      title: 'SAVE + RESTART PLUGIN',
      message: `Save configuration for ${name} and restart its sandboxed service now?\n\nThe plugin will briefly stop and start. Core DMR/BrandMeister operation will remain untouched.`,
      confirmText: 'SAVE + RESTART',
      cancelText: 'CANCEL',
      tone: 'warn',
      kicker: 'YWD // PLUGINS'
    });
    if (!ok) return;

    const previous = button.textContent;
    button.dataset.pluginBusy = '1';
    button.disabled = true;
    button.classList.add('ywd-working');
    button.setAttribute('aria-busy', 'true');
    button.textContent = 'SAVING + RESTARTING…';
    try {
      await post('/api/plugins/config', {id, config: collectConfig(id)});
      await post('/api/plugins/runtime', {id, action: 'restart'});
      markConfigPresent(card);
      showResult(id, 'Configuration saved and plugin service restarted.');
      notify(`${id} configuration saved and plugin restarted`);
    } catch (error) {
      showResult(id, error.message, true);
      notify(error.message, true);
    } finally {
      delete button.dataset.pluginBusy;
      button.classList.remove('ywd-working');
      button.removeAttribute('aria-busy');
      button.textContent = previous;
      syncButtons();
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-plugin-action="config-save-restart"]');
    if (!button || button.disabled) return;
    event.preventDefault();
    event.stopPropagation();
    saveAndRestart(button).catch(error => {
      showResult(button.dataset.pluginId || '', error.message, true);
      notify(error.message, true);
    });
  }, true);

  const observer = new MutationObserver(syncButtons);
  function init() {
    observer.observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['disabled']});
    syncButtons();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
