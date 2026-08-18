'use strict';
(() => {
  const plugins = new Map();
  const frames = new Map();
  let syncTimer = null;

  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  async function jsonFetch(url) {
    const response = await fetch(url, {credentials:'same-origin', cache:'no-store'});
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  function eligible(plugin) {
    return !!(plugin && plugin.valid && plugin.installed && plugin.effective_enabled && plugin.kind === 'ui' && plugin.ui?.api === 1 && plugin.ui?.label);
  }

  function pageId(id) { return `plugin-ui-${id}`; }

  function destroyFrame(id) {
    const session = frames.get(id);
    if (!session) return;
    try { session.port?.close(); } catch (_) {}
    try { session.iframe?.remove(); } catch (_) {}
    frames.delete(id);
    const stage = document.querySelector(`[data-plugin-ui-stage="${CSS.escape(id)}"]`);
    if (stage) stage.innerHTML = '<div class="plugin-ui-placeholder">Open this section to start its sandboxed browser UI.</div>';
  }

  function destroyOtherFrames(keepId = null) {
    for (const id of Array.from(frames.keys())) if (id !== keepId) destroyFrame(id);
  }

  function switchFallback() {
    const button = document.querySelector('.tabs [data-tab="plugins"]') || document.querySelector('.tabs [data-tab="status"]');
    const target = button?.dataset.tab;
    if (!button || !target) return;
    document.querySelectorAll('.tabs button').forEach(x => x.classList.remove('on'));
    document.querySelectorAll('.page').forEach(x => x.classList.remove('on'));
    button.classList.add('on');
    document.getElementById(target)?.classList.add('on');
    if (target === 'plugins' && typeof window.ywdPluginManagerReload === 'function') window.ywdPluginManagerReload();
  }

  function removeUi(id) {
    const page = document.getElementById(pageId(id));
    const button = document.querySelector(`.tabs [data-plugin-ui-id="${CSS.escape(id)}"]`);
    const active = !!page?.classList.contains('on');
    destroyFrame(id);
    page?.remove();
    button?.remove();
    if (active) switchFallback();
  }

  function bridgeResult(plugin, op) {
    if (!eligible(plugin)) throw new Error('Plugin UI is no longer enabled');
    if (op === 'plugin.ping') return {ok:true, api:1, id:plugin.id};
    if (op === 'plugin.getConfig') return plugin.config && typeof plugin.config === 'object' ? plugin.config : {};
    if (op === 'plugin.getState') {
      return {
        id: plugin.id,
        name: plugin.name,
        version: plugin.version,
        health: plugin.health,
        enabled: !!plugin.enabled,
        effective_enabled: !!plugin.effective_enabled,
        capabilities: Array.isArray(plugin.capabilities) ? [...plugin.capabilities] : [],
        ui: plugin.ui || null,
      };
    }
    throw new Error(`Plugin UI operation is not permitted: ${op}`);
  }

  function startFrame(id) {
    if (frames.has(id)) return;
    const plugin = plugins.get(id);
    const stage = document.querySelector(`[data-plugin-ui-stage="${CSS.escape(id)}"]`);
    if (!eligible(plugin) || !stage) return;

    stage.innerHTML = '';
    const iframe = document.createElement('iframe');
    iframe.className = 'plugin-ui-frame';
    iframe.title = `${plugin.name} plugin`;
    iframe.sandbox = 'allow-scripts';
    iframe.referrerPolicy = 'no-referrer';
    iframe.src = `/api/plugins/ui/${encodeURIComponent(id)}/frame?v=${encodeURIComponent(plugin.version || '')}`;
    stage.appendChild(iframe);

    const session = {iframe, port:null};
    frames.set(id, session);
    iframe.addEventListener('load', () => {
      if (!frames.has(id) || !eligible(plugins.get(id))) return;
      try { session.port?.close(); } catch (_) {}
      const channel = new MessageChannel();
      session.port = channel.port1;
      channel.port1.onmessage = event => {
        const request = event.data || {};
        if (request.type !== 'request' || !Number.isInteger(request.id)) return;
        try {
          const result = bridgeResult(plugins.get(id), String(request.op || ''));
          channel.port1.postMessage({type:'response', id:request.id, ok:true, result});
        } catch (error) {
          channel.port1.postMessage({type:'response', id:request.id, ok:false, error:String(error?.message || error)});
        }
      };
      channel.port1.start?.();
      iframe.contentWindow?.postMessage({type:'ywd-plugin-ui-init', api:1, pluginId:id}, '*', [channel.port2]);
    });
  }

  async function leaveSettingsIfNeeded() {
    try {
      if (!document.getElementById('settings')?.classList.contains('on')) return true;
      if (typeof dirty === 'undefined' || !dirty) return true;
      if (typeof window.ywdConfirm !== 'function') return false;
      const ok = await window.ywdConfirm({
        title:'LEAVE SETTINGS?',
        message:'You have unsaved Settings edits. Leave Settings and discard those form edits?',
        confirmText:'DISCARD + LEAVE',
        tone:'warn',
      });
      if (!ok) return false;
      if (typeof configDoc !== 'undefined' && configDoc && typeof fillForm === 'function') fillForm(configDoc);
      if (typeof setDirty === 'function') setDirty(false);
      return true;
    } catch (_) { return false; }
  }

  async function activate(id) {
    if (!eligible(plugins.get(id))) return;
    if (!(await leaveSettingsIfNeeded())) return;
    const page = document.getElementById(pageId(id));
    const button = document.querySelector(`.tabs [data-plugin-ui-id="${CSS.escape(id)}"]`);
    if (!page || !button) return;
    document.querySelectorAll('.tabs button').forEach(x => x.classList.remove('on'));
    document.querySelectorAll('.page').forEach(x => x.classList.remove('on'));
    button.classList.add('on');
    page.classList.add('on');
    destroyOtherFrames(id);
    startFrame(id);
  }

  function ensureUi(plugin) {
    const nav = document.querySelector('.tabs');
    const aboutButton = nav?.querySelector('[data-tab="about"]');
    const aboutPage = document.getElementById('about');
    if (!nav || !aboutButton || !aboutPage?.parentElement) return;

    let button = nav.querySelector(`[data-plugin-ui-id="${CSS.escape(plugin.id)}"]`);
    if (!button) {
      button = document.createElement('button');
      button.dataset.tab = pageId(plugin.id);
      button.dataset.pluginUiId = plugin.id;
      button.addEventListener('click', () => activate(plugin.id));
      nav.insertBefore(button, aboutButton);
    }
    button.textContent = String(plugin.ui.label).toUpperCase();
    button.title = plugin.name;

    let page = document.getElementById(pageId(plugin.id));
    if (!page) {
      page = document.createElement('section');
      page.className = 'page plugin-ui-page';
      page.id = pageId(plugin.id);
      page.dataset.pluginUiPage = plugin.id;
      page.innerHTML = `<article class="card plugin-ui-host-card"><div class="plugin-ui-host-title"><div><div class="card-title">${esc(plugin.name)}</div><div class="hint">Sandboxed Plugin UI v1 · ${esc(plugin.id)} · v${esc(plugin.version)}</div></div><span class="badge applied">ACTIVE</span></div><div class="plugin-ui-stage" data-plugin-ui-stage="${esc(plugin.id)}"><div class="plugin-ui-placeholder">Open this section to start its sandboxed browser UI.</div></div></article>`;
      aboutPage.parentElement.insertBefore(page, aboutPage);
    } else {
      const title = page.querySelector('.card-title');
      if (title) title.textContent = plugin.name;
    }
  }

  function render(data) {
    const incoming = new Map();
    for (const plugin of Array.isArray(data?.plugins) ? data.plugins : []) if (eligible(plugin)) incoming.set(plugin.id, plugin);

    for (const id of Array.from(plugins.keys())) if (!incoming.has(id)) removeUi(id);
    plugins.clear();
    for (const [id, plugin] of incoming) {
      plugins.set(id, plugin);
      ensureUi(plugin);
    }

    for (const [id] of frames) if (!incoming.has(id)) destroyFrame(id);
  }

  async function sync() {
    clearTimeout(syncTimer); syncTimer = null;
    try { render(await jsonFetch('/api/plugins')); }
    catch (error) { console.error('YWD Plugin UI sync failed:', error); }
  }

  function scheduleSync(delay = 80) {
    clearTimeout(syncTimer);
    syncTimer = setTimeout(sync, delay);
  }

  function init() {
    sync();
    document.addEventListener('click', event => {
      const tab = event.target.closest('.tabs button');
      if (tab && !tab.dataset.pluginUiId) destroyOtherFrames(null);
      if (event.target.closest('#plugins [data-plugin-action]')) scheduleSync(500);
    }, {capture:true});
    const cards = document.getElementById('pluginCards');
    if (cards) new MutationObserver(() => scheduleSync()).observe(cards, {childList:true, subtree:false});
    document.addEventListener('visibilitychange', () => { if (!document.hidden) scheduleSync(); });
  }

  window.ywdPluginUiHost = Object.freeze({sync: scheduleSync});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
