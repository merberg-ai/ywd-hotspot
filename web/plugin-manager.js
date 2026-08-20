'use strict';
(() => {
  let pluginState = null;

  const el = id => document.getElementById(id);
  const escp = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const unlocked = () => !!el('logoutBtn') && !el('logoutBtn').hidden;
  const notify = (message, bad = false) => {
    try { if (typeof toast === 'function') return toast(message, bad); } catch (_) {}
    console[bad ? 'error' : 'log'](message);
  };

  async function jsonFetch(url, options = {}) {
    const response = await fetch(url, {credentials:'same-origin', cache:'no-store', ...options});
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  async function post(url, body) {
    return jsonFetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body || {})});
  }

  async function confirmYwd(options) {
    if (typeof window.ywdConfirm !== 'function') throw new Error('YWD confirmation UI is unavailable. Reload the dashboard and try again.');
    return window.ywdConfirm(options);
  }

  function beginBusy(button, label) {
    if (!button) return () => {};
    const previous = button.textContent;
    button.dataset.pluginBusy = '1';
    button.disabled = true;
    button.classList.add('ywd-working');
    button.setAttribute('aria-busy', 'true');
    if (label) button.textContent = label;
    return () => {
      if (!button.isConnected) return;
      delete button.dataset.pluginBusy;
      button.classList.remove('ywd-working');
      button.removeAttribute('aria-busy');
      if (!label || button.textContent === label) button.textContent = previous;
    };
  }

  function formatUptime(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const days = Math.floor(total / 86400);
    const hours = Math.floor((total % 86400) / 3600);
    const mins = Math.floor((total % 3600) / 60);
    return days ? `${days}d ${hours}h ${mins}m` : hours ? `${hours}h ${mins}m` : `${mins}m`;
  }

  function ensureUi() {
    if (el('plugins')) return;
    const nav = document.querySelector('.tabs');
    const aboutButton = nav?.querySelector('[data-tab="about"]');
    if (!nav || !aboutButton) return;

    const button = document.createElement('button');
    button.dataset.tab = 'plugins';
    button.textContent = 'PLUGINS';
    nav.insertBefore(button, aboutButton);

    const page = document.createElement('section');
    page.className = 'page';
    page.id = 'plugins';
    page.innerHTML = `
      <article class="card plugin-hero">
        <div>
          <div class="card-title">PLUGIN SUBSYSTEM</div>
          <div id="pluginSystemState" class="plugin-system-state disabled">DISABLED</div>
          <div id="pluginSystemMessage" class="hint">Plugin support is loading…</div>
          <div id="pluginSummary" class="plugin-summary"></div>
        </div>
        <div class="buttonrow wrap">
          <button class="btn primary" id="pluginSystemToggle" data-plugin-action="system-toggle">ENABLE PLUGIN SUPPORT</button>
        </div>
      </article>
      <div id="pluginMasterNotice" class="notice plugin-warning">Available packages are separate from installed/active plugins.</div>
      <article class="card">
        <div class="card-title title-row"><span>PLUGIN MANAGER</span><span class="hint">API v1 · Alpha16 package lifecycle</span></div>
        <p class="plugin-api-note">Repository-bundled packages are only available source until installed. Installation never enables or starts a plugin. Declarative plugins remain data-only; service plugins run only through the shared hardened YWD systemd template. RF ownership, plugin-supplied units, arbitrary sudo, device access, and normal network sockets remain blocked.</p>
      </article>
      <div id="pluginCards" class="plugin-grid"><article class="card plugin-empty">Loading plugin packages…</article></div>`;
    const about = el('about');
    if (about?.parentElement) about.parentElement.insertBefore(page, about); else document.querySelector('main')?.append(page);

    button.onclick = async () => {
      const current = document.querySelector('.tabs button.on')?.dataset.tab;
      try {
        if (current === 'settings' && typeof dirty !== 'undefined' && dirty) {
          const ok = await confirmYwd({title:'LEAVE SETTINGS?',message:'You have unsaved Settings edits. Leave Settings and discard those form edits?',confirmText:'DISCARD + LEAVE',tone:'warn'});
          if (!ok) return;
          if (typeof configDoc !== 'undefined' && configDoc && typeof fillForm === 'function') fillForm(configDoc);
          if (typeof setDirty === 'function') setDirty(false);
        }
      } catch (_) { return; }
      document.querySelectorAll('.tabs button').forEach(x => x.classList.remove('on'));
      document.querySelectorAll('.page').forEach(x => x.classList.remove('on'));
      button.classList.add('on'); page.classList.add('on');
      loadPlugins();
    };
    page.addEventListener('click', handleClick);
  }

  function pluginCard(plugin, systemEnabled) {
    const renderer = window.ywdPluginCardRenderer;
    if (!renderer || typeof renderer.pluginCard !== 'function') throw new Error('Plugin card renderer is unavailable. Reload the dashboard.');
    return renderer.pluginCard(plugin, systemEnabled, {escp, formatUptime});
  }

  function render(data) {
    pluginState = data; ensureUi();
    const system = data?.system || {enabled:false, available:0, installed:0, active_plugins:0, enabled_plugins:0, health:'disabled'};
    const stateEl = el('pluginSystemState');
    stateEl.textContent = system.enabled ? 'ENABLED' : 'DISABLED';
    stateEl.className = `plugin-system-state ${system.enabled ? 'good' : 'disabled'}`;
    el('pluginSystemMessage').textContent = system.package_state_error || (system.enabled ? 'Plugin support is enabled. Only explicitly installed, enabled, validated plugins may become active.' : 'Plugin runtime is off. Package installation state and plugin configuration are preserved independently.');
    el('pluginSummary').innerHTML = `<span class="badge">API ${escp(data?.api ?? 1)}</span><span class="badge">${escp(system.available || 0)} AVAILABLE</span><span class="badge">${escp(system.installed || 0)} INSTALLED</span><span class="badge">${escp(system.enabled_plugins || 0)} ENABLED</span><span class="badge">${escp(system.active_plugins || 0)} ACTIVE</span>`;
    const toggle = el('pluginSystemToggle');
    toggle.textContent = system.enabled ? 'DISABLE ALL PLUGINS' : 'ENABLE PLUGIN SUPPORT'; toggle.className = `btn ${system.enabled ? 'danger' : 'primary'}`; toggle.dataset.enabled = system.enabled ? '0' : '1'; toggle.disabled = !unlocked();
    const notice = el('pluginMasterNotice');
    notice.className = `notice ${system.package_state_error ? 'plugin-warning' : system.enabled ? 'plugin-good' : 'plugin-warning'}`;
    notice.textContent = system.package_state_error || (system.enabled ? 'Plugin subsystem active. INSTALL never enables a package; UNINSTALL stops/disables service runtime and preserves config/data unless REMOVE DATA is explicitly confirmed.' : 'Plugin subsystem disabled. You may still install/uninstall packages. Every plugin activation state remains OFF until explicitly enabled.');
    const plugins = Array.isArray(data?.plugins) ? data.plugins : [];
    el('pluginCards').innerHTML = plugins.length ? plugins.map(p => pluginCard(p, !!system.enabled)).join('') : '<article class="card plugin-empty">No plugin packages are available.</article>';
    refreshControls();
  }

  function refreshControls() {
    const auth = unlocked(), systemEnabled = !!pluginState?.system?.enabled;
    const plugins = pluginState?.plugins || [];
    const find = id => plugins.find(x => x.id === id);
    const master = el('pluginSystemToggle'); if (master) master.disabled = !auth || master.dataset.pluginBusy === '1';
    document.querySelectorAll('#plugins [data-plugin-action="plugin-toggle"]').forEach(button => { const p=find(button.dataset.pluginId); button.disabled=button.dataset.pluginBusy==='1'||!auth||!systemEnabled||!p?.valid||!p?.installed; });
    document.querySelectorAll('#plugins [data-plugin-action="plugin-test"]').forEach(button => { const p=find(button.dataset.pluginId); button.disabled=button.dataset.pluginBusy==='1'||!auth||!systemEnabled||!p?.installed||!p?.effective_enabled||(!!p?.service&&p?.health!=='active'); });
    document.querySelectorAll('#plugins [data-plugin-action^="service-"]').forEach(button => { const p=find(button.dataset.pluginId), runtime=p?.runtime?.state, action=button.dataset.pluginAction; let blocked=!auth||!systemEnabled||!p?.installed||!p?.enabled||!p?.valid; if(action==='service-start'&&runtime==='active')blocked=true; if((action==='service-stop'||action==='service-restart')&&runtime!=='active')blocked=true; button.disabled=button.dataset.pluginBusy==='1'||blocked; });
    document.querySelectorAll('#plugins [data-plugin-action="config-save"]').forEach(button => { const p=find(button.dataset.pluginId); button.disabled=button.dataset.pluginBusy==='1'||!auth||!p?.installed||!p?.valid; });
    document.querySelectorAll('#plugins [data-plugin-action="package-install"]').forEach(button => { const p=find(button.dataset.pluginId); button.disabled=button.dataset.pluginBusy==='1'||!auth||!p?.valid||!!p?.installed; });
    document.querySelectorAll('#plugins [data-plugin-action="package-uninstall"]').forEach(button => { const p=find(button.dataset.pluginId); button.disabled=button.dataset.pluginBusy==='1'||!auth||!p?.valid||!p?.installed; });
    document.querySelectorAll('#plugins [data-plugin-action="package-check-deps"],#plugins [data-plugin-action="package-check-hardware"]').forEach(button => { const p=find(button.dataset.pluginId); button.disabled=button.dataset.pluginBusy==='1'||!auth||!p?.valid; });
    document.querySelectorAll('#plugins [data-plugin-action="package-data-remove"]').forEach(button => { const p=find(button.dataset.pluginId), runtime=p?.runtime||{}; const unsafe=p?.enabled||runtime.state==='active'||runtime.boot==='enabled'; button.disabled=button.dataset.pluginBusy==='1'||!auth||!p?.valid||unsafe||!(p?.config_present||p?.data_present); });
  }

  async function loadPlugins() { try { render(await jsonFetch('/api/plugins')); } catch (error) { ensureUi(); if (el('pluginCards')) el('pluginCards').innerHTML=`<article class="card plugin-empty badtext">${escp(error.message)}</article>`; } }
  function collectConfig(id) { const config={}; document.querySelectorAll(`#plugins [data-plugin-config="${id}"]`).forEach(input=>{const key=input.dataset.pluginField,type=input.dataset.fieldType; if(type==='boolean')config[key]=!!input.checked; else if(type==='integer')config[key]=Number(input.value); else config[key]=input.value;}); return config; }
  function showResult(id,message,bad=false){const result=el(`pluginResult-${id}`);if(!result)return;result.hidden=false;result.className=`plugin-result ${bad?'bad':'good'}`;result.textContent=message;}


  async function runtimeAction(button,id,action){const labels={start:'STARTING…',stop:'STOPPING…',restart:'RESTARTING…'};if(action==='stop'){const ok=await confirmYwd({title:'STOP PLUGIN RUNTIME',message:'Stop this plugin service for the current runtime?\n\nThe plugin remains enabled and will start again at boot unless you DISABLE it.',confirmText:'STOP RUNTIME',tone:'warn',kicker:'YWD // PLUGINS'});if(!ok)return;}if(action==='restart'){const ok=await confirmYwd({title:'RESTART PLUGIN SERVICE',message:'Restart this sandboxed plugin service now? A brief interruption is expected.',confirmText:'RESTART',tone:'warn',kicker:'YWD // PLUGINS'});if(!ok)return;}const done=beginBusy(button,labels[action]||'WORKING…');try{const data=await post('/api/plugins/runtime',{id,action});render(data.plugins_state);notify(`${id} ${action} complete`);}finally{done();}}

  async function handleClick(event){const button=event.target.closest('[data-plugin-action]');if(!button||button.disabled)return;const action=button.dataset.pluginAction,id=button.dataset.pluginId;let done=()=>{};try{
    if(action==='system-toggle'){const enabled=button.dataset.enabled==='1';if(!enabled){const ok=await confirmYwd({title:'DISABLE PLUGIN SUBSYSTEM',message:'Disable the entire plugin subsystem?\n\nAll active service plugins will be stopped/unloaded and every plugin will be individually disabled. Package installation and plugin configuration are preserved. Core DMR operation will remain untouched.',confirmText:'DISABLE ALL',cancelText:'CANCEL',tone:'danger',kicker:'YWD // PLUGINS'});if(!ok)return;}done=beginBusy(button,enabled?'ENABLING…':'DISABLING…');const data=await post('/api/plugins/system',{enabled});render(data.plugins_state);notify(enabled?'Plugin support enabled':'All plugins safely disabled');}
    else if(action.startsWith('package-')){
      const packageUi = window.ywdPluginPackageUi;
      if (!packageUi || typeof packageUi.handle !== 'function') throw new Error('Plugin package controls are unavailable. Reload the dashboard.');
      const handled = await packageUi.handle(action, {button,id,pluginState,beginBusy,post,render,notify,confirmYwd,showResult});
      if (handled) return;
    }
    else if(action==='plugin-toggle'){const enabled=button.dataset.enabled==='1',plugin=(pluginState?.plugins||[]).find(p=>p.id===id);if(!enabled){const ok=await confirmYwd({title:'DISABLE PLUGIN',message:`Disable ${plugin?.name||id}?\n\nAny service runtime will be stopped and boot activation removed. Configuration will be preserved.`,confirmText:'DISABLE PLUGIN',cancelText:'CANCEL',tone:'danger',kicker:'YWD // PLUGINS'});if(!ok)return;}done=beginBusy(button,enabled?'ENABLING…':'DISABLING…');const data=await post('/api/plugins/enable',{id,enabled});render(data.plugins_state);notify(`${id} ${enabled?'enabled':'disabled'}`);}
    else if(action==='config-save'){done=beginBusy(button,'SAVING…');const data=await post('/api/plugins/config',{id,config:collectConfig(id)});render(data.plugins_state);notify(data.restart_required?`${id} config saved — restart service to apply`:`${id} configuration saved`);}
    else if(action==='plugin-test'){done=beginBusy(button,'TESTING…');const data=await post('/api/plugins/test',{id});if(data.plugins_state)render(data.plugins_state);const lines=[data.message||'Plugin test passed'];if(data.data?.hostname)lines.push(`Hostname: ${data.data.hostname}`);if(data.data?.uptime_s!=null)lines.push(`Uptime: ${formatUptime(data.data.uptime_s)}`);if(data.data?.temperature_c!=null)lines.push(`Temperature: ${data.data.temperature_c} °C`);if(Array.isArray(data.data?.load))lines.push(`Load: ${data.data.load.map(x=>Number(x).toFixed(2)).join(' / ')}`);if(data.data?.service)lines.push(`Service: ${data.data.service}`);if(data.data?.state)lines.push(`Runtime: ${data.data.state}`);if(data.data?.boot)lines.push(`Boot: ${data.data.boot}`);showResult(id,lines.join('\n'));notify(`${id} test passed`);}
    else if(action==='service-start'){await runtimeAction(button,id,'start');return;}
    else if(action==='service-stop'){await runtimeAction(button,id,'stop');return;}
    else if(action==='service-restart'){await runtimeAction(button,id,'restart');return;}
    else if(action==='service-logs'){done=beginBusy(button,'LOADING…');const data=await jsonFetch(`/api/plugins/logs?id=${encodeURIComponent(id)}`);showResult(id,(data.lines||[]).join('\n')||'No journal entries yet.');}
  }catch(error){if(id)showResult(id,error.message,true);notify(error.message,true);}finally{done();refreshControls();}}

  function init(){ensureUi();loadPlugins();const logout=el('logoutBtn');if(logout)new MutationObserver(refreshControls).observe(logout,{attributes:true,attributeFilter:['hidden']});document.addEventListener('visibilitychange',()=>{if(!document.hidden&&el('plugins')?.classList.contains('on'))loadPlugins();});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
