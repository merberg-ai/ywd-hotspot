'use strict';
(() => {
  const pluginId = document.body?.dataset?.pluginId || '';
  let port = null;
  let sequence = 0;
  const pending = new Map();
  let resolveReady;
  const ready = new Promise(resolve => { resolveReady = resolve; });

  function request(op, args = {}) {
    return ready.then(() => new Promise((resolve, reject) => {
      if (!port) return reject(new Error('YWD plugin bridge is unavailable'));
      const id = ++sequence;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`YWD plugin bridge timed out: ${op}`));
      }, 5000);
      pending.set(id, {resolve, reject, timer});
      port.postMessage({type:'request', id, op:String(op || ''), args:args && typeof args === 'object' ? args : {}});
    }));
  }

  window.ywdPlugin = Object.freeze({
    api: 1,
    id: pluginId,
    ready,
    request,
    getState: () => request('plugin.getState'),
    getConfig: () => request('plugin.getConfig'),
    ping: () => request('plugin.ping'),
    readDmrVoice: options => request('plugin.readDmrVoice', options || {}),
  });

  window.addEventListener('message', event => {
    const data = event.data || {};
    if (port || event.source !== parent || data.type !== 'ywd-plugin-ui-init' || data.api !== 1 || data.pluginId !== pluginId || !event.ports?.[0]) return;
    port = event.ports[0];
    port.onmessage = message => {
      const response = message.data || {};
      if (response.type !== 'response' || !Number.isInteger(response.id)) return;
      const waiter = pending.get(response.id);
      if (!waiter) return;
      pending.delete(response.id);
      clearTimeout(waiter.timer);
      if (response.ok) waiter.resolve(response.result);
      else waiter.reject(new Error(String(response.error || 'Plugin bridge request failed')));
    };
    port.start?.();
    resolveReady(Object.freeze({api:1, id:pluginId}));
  }, {once:false});
})();
