'use strict';
(() => {
  const pluginId = document.body?.dataset?.pluginId || '';
  let port = null;
  let sequence = 0;
  const pending = new Map();
  const streamHandlers = new Map();
  const streamBacklog = new Map();
  let resolveReady;
  const ready = new Promise(resolve => { resolveReady = resolve; });

  function timeoutFor(op) {
    if (op === 'plugin.vocoderStatus' || op === 'plugin.vocoderReset' || op === 'plugin.startRxAudioStream') return 20000;
    if (op === 'plugin.lookupDmrIds' || op === 'plugin.searchDmrDirectory') return 15000;
    if (op === 'plugin.vocoderDecode') return 1500;
    return 5000;
  }

  function request(op, args = {}) {
    return ready.then(() => new Promise((resolve, reject) => {
      if (!port) return reject(new Error('YWD plugin bridge is unavailable'));
      const id = ++sequence;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`YWD plugin bridge timed out: ${op}`));
      }, timeoutFor(op));
      pending.set(id, {resolve, reject, timer});
      port.postMessage({type:'request', id, op:String(op || ''), args:args && typeof args === 'object' ? args : {}});
    }));
  }

  function queueStreamEvent(streamId, event) {
    const handler = streamHandlers.get(streamId);
    if (handler) {
      try { handler(event); } catch (error) { console.error('YWD RX audio stream handler failed:', error); }
      return true;
    }
    const queued = streamBacklog.get(streamId) || [];
    queued.push(event);
    while (queued.length > 32) queued.shift();
    streamBacklog.set(streamId, queued);
    return false;
  }

  async function startRxAudioStream(options = {}, onEvent) {
    if (typeof onEvent !== 'function') throw new Error('RX audio stream requires an event handler');
    const info = await request('plugin.startRxAudioStream', options && typeof options === 'object' ? options : {});
    const streamId = String(info?.stream_id || '');
    if (!streamId) throw new Error('RX audio stream did not return a stream id');
    streamHandlers.set(streamId, onEvent);
    const queued = streamBacklog.get(streamId) || [];
    streamBacklog.delete(streamId);
    for (const event of queued) queueStreamEvent(streamId, event);
    return Object.freeze({
      id: streamId,
      stop: async () => {
        try { return await request('plugin.stopRxAudioStream', {stream_id:streamId}); }
        finally {
          streamHandlers.delete(streamId);
          streamBacklog.delete(streamId);
        }
      },
    });
  }

  window.ywdPlugin = Object.freeze({
    api: 1,
    id: pluginId,
    ready,
    request,
    getState: () => request('plugin.getState'),
    getConfig: () => request('plugin.getConfig'),
    ping: () => request('plugin.ping'),
    readDmrActivity: options => request('plugin.readDmrActivity', options || {}),
    lookupDmrIds: ids => request('plugin.lookupDmrIds', {ids:Array.isArray(ids) ? ids : []}),
    searchDmrDirectory: (query, options = {}) => request('plugin.searchDmrDirectory', {
      query:String(query || ''),
      limit:options && typeof options === 'object' ? options.limit : undefined,
    }),
    readDmrVoice: options => request('plugin.readDmrVoice', options || {}),
    vocoderStatus: () => request('plugin.vocoderStatus'),
    vocoderReset: () => request('plugin.vocoderReset'),
    vocoderDecode: frames => request('plugin.vocoderDecode', {frames:Array.isArray(frames) ? frames : []}),
    startRxAudioStream,
  });

  window.addEventListener('message', event => {
    const data = event.data || {};
    if (port || event.source !== parent || data.type !== 'ywd-plugin-ui-init' || data.api !== 1 || data.pluginId !== pluginId || !event.ports?.[0]) return;
    port = event.ports[0];
    port.onmessage = message => {
      const response = message.data || {};
      if (response.type === 'stream-event' && response.streamId) {
        queueStreamEvent(String(response.streamId), response.event || {});
        return;
      }
      if (response.type === 'stream-end' && response.streamId) {
        const streamId = String(response.streamId);
        const delivered = queueStreamEvent(streamId, {type:'stream-end', error:String(response.error || '')});
        if (delivered) {
          streamHandlers.delete(streamId);
          streamBacklog.delete(streamId);
        }
        return;
      }
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
