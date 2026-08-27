'use strict';
(() => {
  const plugins = new Map();
  const frames = new Map();
  let syncTimer = null;
  let streamSequence = 0;

  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pluginSelector = id => String(id || ''); // plugin IDs are already restricted to [a-z0-9-]

  async function jsonFetch(url) {
    const response = await fetch(url, {credentials:'same-origin', cache:'no-store'});
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  async function jsonPost(url, body = {}) {
    const response = await fetch(url, {
      method:'POST',
      credentials:'same-origin',
      cache:'no-store',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body && typeof body === 'object' ? body : {}),
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  function eligible(plugin) {
    return !!(plugin && plugin.valid && plugin.installed && plugin.effective_enabled && plugin.kind === 'ui' && plugin.ui?.api === 1 && plugin.ui?.label);
  }

  function pageId(id) { return `plugin-ui-${id}`; }

  function stopAudioStream(session, streamId = '') {
    const active = session?.audioStream;
    if (!active) return {ok:true, stopped:false};
    if (streamId && active.id !== String(streamId)) return {ok:true, stopped:false};
    session.audioStream = null;
    try { active.controller.abort(); } catch (_) {}
    return {ok:true, stopped:true, stream_id:active.id};
  }

  function destroyFrame(id) {
    const session = frames.get(id);
    if (!session) return;
    stopAudioStream(session);
    try { session.port?.close(); } catch (_) {}
    try { session.iframe?.remove(); } catch (_) {}
    frames.delete(id);
    const stage = document.querySelector(`[data-plugin-ui-stage="${pluginSelector(id)}"]`);
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
    const button = document.querySelector(`.tabs [data-plugin-ui-id="${pluginSelector(id)}"]`);
    const active = !!page?.classList.contains('on');
    destroyFrame(id);
    page?.remove();
    button?.remove();
    if (active) switchFallback();
  }

  function requireCapability(plugin, capability) {
    if (!Array.isArray(plugin.capabilities) || !plugin.capabilities.includes(capability)) {
      throw new Error(`Plugin does not have ${capability} capability`);
    }
  }

  async function pumpAudioStream(session, plugin, active, response) {
    let error = '';
    try {
      if (!response.body) throw new Error('RX audio stream body is unavailable');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let pending = '';
      while (frames.get(plugin.id) === session && session.audioStream === active) {
        const {value, done} = await reader.read();
        if (done) break;
        pending += decoder.decode(value, {stream:true});
        if (pending.length > 131072) throw new Error('RX audio stream framing buffer exceeded limit');
        while (true) {
          const newline = pending.indexOf('\n');
          if (newline < 0) break;
          const line = pending.slice(0, newline).trim();
          pending = pending.slice(newline + 1);
          if (!line) continue;
          let event;
          try { event = JSON.parse(line); }
          catch (_) { throw new Error('RX audio stream returned invalid NDJSON'); }
          if (session.port && session.audioStream === active) {
            session.port.postMessage({type:'stream-event', streamId:active.id, event});
          }
        }
      }
    } catch (exc) {
      if (!active.controller.signal.aborted) error = String(exc?.message || exc);
    } finally {
      if (session.audioStream === active) session.audioStream = null;
      try {
        session.port?.postMessage({type:'stream-end', streamId:active.id, error});
      } catch (_) {}
    }
  }

  async function startAudioStream(session, plugin, args = {}) {
    if (!eligible(plugin)) throw new Error('Plugin UI is no longer enabled');
    requireCapability(plugin, 'read:dmr-voice');
    requireCapability(plugin, 'use:vocoder');
    stopAudioStream(session);

    const sourceRaw = String(args?.source || 'network').toLowerCase();
    const source = ['network','rf','all'].includes(sourceRaw) ? sourceRaw : 'network';
    const slotRaw = String(args?.slot ?? 'auto').toLowerCase();
    const slot = ['auto','1','2'].includes(slotRaw) ? slotRaw : 'auto';
    const controller = new AbortController();
    const streamId = `${plugin.id}-${Date.now().toString(36)}-${(++streamSequence).toString(36)}`;
    const url = `/api/plugins/ui/${encodeURIComponent(plugin.id)}/audio-stream?source=${encodeURIComponent(source)}&slot=${encodeURIComponent(slot)}`;
    const response = await fetch(url, {
      credentials:'same-origin',
      cache:'no-store',
      signal:controller.signal,
      headers:{'Accept':'application/x-ndjson'},
    });
    if (!response.ok) {
      let data = {};
      try { data = await response.json(); } catch (_) {}
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    const active = {id:streamId, controller};
    session.audioStream = active;
    void pumpAudioStream(session, plugin, active, response);
    return {ok:true, stream_id:streamId, source, slot};
  }

  async function bridgeResult(plugin, op, args = {}) {
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
    if (op === 'plugin.readDmrActivity') {
      requireCapability(plugin, 'read:dmr-activity');
      const limitRaw = Number(args?.limit ?? 20);
      const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(60, Math.floor(limitRaw))) : 20;
      const data = await jsonFetch(`/api/plugins/ui/${encodeURIComponent(plugin.id)}/dmr-activity?limit=${encodeURIComponent(limit)}`);
      return data.activity || {schema:1, current:{active:false,direction:'idle'}, lastheard:[], counters:{}};
    }
    if (op === 'plugin.lookupDmrIds') {
      requireCapability(plugin, 'read:dmr-directory');
      const ids = Array.isArray(args?.ids) ? args.ids.slice(0, 64).map(x => String(x || '').trim()).filter(x => /^\d{1,8}$/.test(x)) : [];
      if (!ids.length) throw new Error('DMR ID lookup requires at least one ID');
      const data = await jsonFetch(`/api/plugins/ui/${encodeURIComponent(plugin.id)}/dmr-directory?ids=${encodeURIComponent(ids.join(','))}`);
      return data.directory || {ok:true, results:[]};
    }
    if (op === 'plugin.searchDmrDirectory') {
      requireCapability(plugin, 'read:dmr-directory');
      const query = String(args?.query || '').trim().slice(0, 32);
      const limitRaw = Number(args?.limit ?? 15);
      const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(25, Math.floor(limitRaw))) : 15;
      if (!query) throw new Error('Directory search requires a callsign or DMR ID');
      const data = await jsonFetch(`/api/plugins/ui/${encodeURIComponent(plugin.id)}/dmr-directory?q=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`);
      return data.directory || {ok:true, results:[]};
    }
    if (op === 'plugin.readDmrVoice') {
      requireCapability(plugin, 'read:dmr-voice');
      const afterRaw = Number(args?.after ?? 0);
      const limitRaw = Number(args?.limit ?? 32);
      const after = Number.isFinite(afterRaw) ? Math.max(0, Math.floor(afterRaw)) : 0;
      const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(64, Math.floor(limitRaw))) : 32;
      const data = await jsonFetch(`/api/plugins/ui/${encodeURIComponent(plugin.id)}/dmr-voice?after=${encodeURIComponent(after)}&limit=${encodeURIComponent(limit)}`);
      return data.voice || {schema:1, bridge:{status:'unavailable'}, cursor:after, frames:[]};
    }
    if (op === 'plugin.vocoderStatus') {
      requireCapability(plugin, 'use:vocoder');
      const data = await jsonFetch(`/api/plugins/ui/${encodeURIComponent(plugin.id)}/vocoder/status`);
      return data.vocoder || {available:false, protocol:1, error:'vocoder status unavailable'};
    }
    if (op === 'plugin.vocoderReset') {
      requireCapability(plugin, 'use:vocoder');
      const data = await jsonPost(`/api/plugins/ui/${encodeURIComponent(plugin.id)}/vocoder/reset`, {});
      return data.vocoder || {ok:false, protocol:1};
    }
    if (op === 'plugin.vocoderDecode') {
      requireCapability(plugin, 'use:vocoder');
      const voiceFrames = Array.isArray(args?.frames) ? args.frames.slice(0, 10).map(x => String(x || '')) : [];
      const data = await jsonPost(`/api/plugins/ui/${encodeURIComponent(plugin.id)}/vocoder/decode`, {frames:voiceFrames});
      return data.vocoder || {};
    }
    throw new Error(`Plugin UI operation is not permitted: ${op}`);
  }

  function startFrame(id) {
    if (frames.has(id)) return;
    const plugin = plugins.get(id);
    const stage = document.querySelector(`[data-plugin-ui-stage="${pluginSelector(id)}"]`);
    if (!eligible(plugin) || !stage) return;

    stage.innerHTML = '';
    const iframe = document.createElement('iframe');
    iframe.className = 'plugin-ui-frame';
    iframe.title = `${plugin.name} plugin`;
    const sandbox = ['allow-scripts'];
    // A read:dmr-voice UI may export a bounded capture that already exists in
    // its browser memory. allow-downloads permits only that user-requested
    // local download; the iframe remains opaque-origin with no network, forms,
    // popups, device access, or same-origin privilege.
    if (Array.isArray(plugin.capabilities) && plugin.capabilities.includes('read:dmr-voice')) sandbox.push('allow-downloads');
    iframe.setAttribute('sandbox', sandbox.join(' '));
    iframe.referrerPolicy = 'no-referrer';
    iframe.src = `/api/plugins/ui/${encodeURIComponent(id)}/frame?v=${encodeURIComponent(plugin.version || '')}`;
    stage.appendChild(iframe);

    const session = {iframe, port:null, audioStream:null, version:String(plugin.version || '')};
    frames.set(id, session);
    iframe.addEventListener('load', () => {
      if (!frames.has(id) || !eligible(plugins.get(id))) return;
      stopAudioStream(session);
      try { session.port?.close(); } catch (_) {}
      const channel = new MessageChannel();
      session.port = channel.port1;
      channel.port1.onmessage = async event => {
        const request = event.data || {};
        if (request.type !== 'request' || !Number.isInteger(request.id)) return;
        try {
          const current = plugins.get(id);
          const op = String(request.op || '');
          let result;
          if (op === 'plugin.startRxAudioStream') {
            result = await startAudioStream(session, current, request.args || {});
          } else if (op === 'plugin.stopRxAudioStream') {
            result = stopAudioStream(session, String(request.args?.stream_id || ''));
          } else {
            result = await bridgeResult(current, op, request.args || {});
          }
          channel.port1.postMessage({type:'response', id:request.id, ok:true, result});
        } catch (error) {
          try { channel.port1.postMessage({type:'response', id:request.id, ok:false, error:String(error?.message || error)}); } catch (_) {}
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
      let ok;
      if (typeof window.ywdConfirm === 'function') {
        ok = await window.ywdConfirm({
          title:'LEAVE SETTINGS?',
          message:'You have unsaved Settings edits. Leave Settings and discard those form edits?',
          confirmText:'DISCARD + LEAVE',
          tone:'warn',
        });
      } else {
        ok = window.confirm('You have unsaved Settings edits. Leave Settings and discard those form edits?');
      }
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
    const button = document.querySelector(`.tabs [data-plugin-ui-id="${pluginSelector(id)}"]`);
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

    let button = nav.querySelector(`[data-plugin-ui-id="${pluginSelector(plugin.id)}"]`);
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
      const hint = page.querySelector('.plugin-ui-host-title .hint');
      if (hint) hint.textContent = `Sandboxed Plugin UI v1 · ${plugin.id} · v${plugin.version}`;
    }
  }

  function render(data) {
    const incoming = new Map();
    for (const plugin of Array.isArray(data?.plugins) ? data.plugins : []) if (eligible(plugin)) incoming.set(plugin.id, plugin);
    const previous = new Map(plugins);

    for (const id of Array.from(plugins.keys())) if (!incoming.has(id)) removeUi(id);
    plugins.clear();
    for (const [id, plugin] of incoming) {
      const old = previous.get(id);
      if (old && String(old.version || '') !== String(plugin.version || '')) destroyFrame(id);
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
