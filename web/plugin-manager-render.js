'use strict';
(() => {
  let escp = value => String(value ?? '');
  let formatUptime = value => String(value ?? '');

  function schemaField(plugin, field) {
    const id = escp(plugin.id), key = escp(field.key), value = plugin.config?.[field.key] ?? field.default ?? '';
    const common = `data-plugin-config="${id}" data-plugin-field="${key}" data-field-type="${escp(field.type)}"`;
    let control = '';
    if (field.type === 'boolean') control = `<div class="field check"><label><input type="checkbox" ${common}${value ? ' checked' : ''}> ${escp(field.label)}</label></div>`;
    else if (field.type === 'select') {
      const options = (field.options || []).map(option => `<option value="${escp(option)}"${String(value) === String(option) ? ' selected' : ''}>${escp(option)}</option>`).join('');
      control = `<div class="field"><label>${escp(field.label)}</label><select ${common}>${options}</select></div>`;
    } else {
      const type = field.type === 'integer' ? 'number' : 'text';
      const min = field.min != null ? ` min="${escp(field.min)}"` : '';
      const max = field.max != null ? ` max="${escp(field.max)}"` : '';
      const maxlength = field.max_length != null ? ` maxlength="${escp(field.max_length)}"` : '';
      control = `<div class="field"><label>${escp(field.label)}</label><input type="${type}" value="${escp(value)}" ${common}${min}${max}${maxlength}></div>`;
    }
    if (field.help) control += `<div class="plugin-help">${escp(field.help)}</div>`;
    return control;
  }

  function serviceRows(plugin) {
    if (!plugin.service) return '';
    const runtime = plugin.runtime || {};
    return `<div class="plugin-meta"><div><span>Runtime</span><b>${escp(runtime.state || 'unknown')}</b></div><div><span>Boot</span><b>${escp(runtime.boot || 'disabled')}</b></div></div>`;
  }

  function requirementState(plugin, section) {
    const data = plugin.requirements?.[section];
    const items = Array.isArray(data?.items) ? data.items : [];
    if (!items.length) return {text:'N/A', cls:'na'};
    return data?.ok ? {text:'PASS', cls:'pass'} : {text:'MISSING', cls:'missing'};
  }

  function packageRows(plugin) {
    const deps = requirementState(plugin, 'dependencies'); const hardware = requirementState(plugin, 'hardware');
    return `<div class="plugin-meta plugin-package-meta"><div><span>Package</span><b>${plugin.installed ? 'INSTALLED' : 'AVAILABLE'}</b></div><div><span>Config</span><b>${plugin.config_present ? 'PRESENT' : 'NONE'}</b></div><div><span>Data</span><b>${plugin.data_present ? 'PRESENT' : 'NONE'}</b></div><div><span>Dependencies</span><b class="plugin-check-${deps.cls}">${deps.text}</b></div><div><span>Hardware</span><b class="plugin-check-${hardware.cls}">${hardware.text}</b></div></div>`;
  }

  function packageActions(plugin) {
    const id = escp(plugin.id);
    const lifecycle = plugin.installed ? `<button class="btn danger" data-plugin-action="package-uninstall" data-plugin-id="${id}">UNINSTALL</button>` : `<button class="btn good" data-plugin-action="package-install" data-plugin-id="${id}">INSTALL</button>`;
    const removeData = plugin.config_present || plugin.data_present ? `<button class="btn danger" data-plugin-action="package-data-remove" data-plugin-id="${id}">REMOVE DATA</button>` : '';
    return `<div class="buttonrow wrap plugin-package-actions">${lifecycle}<button class="btn" data-plugin-action="package-check-deps" data-plugin-id="${id}">CHECK DEPENDENCIES</button><button class="btn" data-plugin-action="package-check-hardware" data-plugin-id="${id}">CHECK HARDWARE</button>${removeData}</div>`;
  }

  function pluginCard(plugin, systemEnabled) {
    const installed = !!plugin.installed; const good = plugin.health === 'active'; const bad = plugin.health === 'error'; const stopped = plugin.health === 'stopped';
    const status = bad ? 'ERROR' : !installed ? 'AVAILABLE' : good ? 'ACTIVE' : stopped ? 'STOPPED' : 'DISABLED';
    const caps = (plugin.capabilities || []).map(cap => `<span class="plugin-cap">${escp(cap)}</span>`).join('') || '<span class="plugin-cap">no capabilities</span>';
    const fields = installed && plugin.valid ? (plugin.schema?.fields || []).map(field => schemaField(plugin, field)).join('') : '';
    const data = plugin.data || {};
    const liveRows = plugin.effective_enabled && !plugin.service ? [data.label ? `<div><span>Label</span><b>${escp(data.label)}</b></div>` : '',data.hostname ? `<div><span>Hostname</span><b>${escp(data.hostname)}</b></div>` : '',data.uptime_s != null ? `<div><span>Uptime</span><b>${escp(formatUptime(data.uptime_s))}</b></div>` : '',data.temperature_c != null ? `<div><span>Temperature</span><b>${escp(data.temperature_c)} °C</b></div>` : '',Array.isArray(data.load) ? `<div><span>Load</span><b>${escp(data.load.map(x => Number(x).toFixed(2)).join(' / '))}</b></div>` : ''].filter(Boolean).join('') : '';
    const errorText = plugin.error || plugin.config_error || '';
    const serviceButtons = installed && plugin.service ? `<div class="buttonrow wrap plugin-runtime-actions"><button class="btn good" data-plugin-action="service-start" data-plugin-id="${escp(plugin.id)}">START</button><button class="btn danger" data-plugin-action="service-stop" data-plugin-id="${escp(plugin.id)}">STOP RUNTIME</button><button class="btn" data-plugin-action="service-restart" data-plugin-id="${escp(plugin.id)}">RESTART</button><button class="btn" data-plugin-action="service-logs" data-plugin-id="${escp(plugin.id)}">LOGS</button></div>` : '';
    const enableButtons = installed ? `<div class="buttonrow wrap"><button class="btn ${plugin.enabled ? 'danger' : 'good'}" data-plugin-action="plugin-toggle" data-plugin-id="${escp(plugin.id)}" data-enabled="${plugin.enabled ? '0' : '1'}"${!plugin.valid || !systemEnabled ? ' disabled' : ''}>${plugin.enabled ? 'DISABLE' : 'ENABLE'}</button><button class="btn" data-plugin-action="plugin-test" data-plugin-id="${escp(plugin.id)}"${!plugin.effective_enabled || (plugin.service && plugin.health !== 'active') ? ' disabled' : ''}>TEST</button></div>` : '';
    return `<article class="card plugin-card${good ? ' active' : ''}${bad ? ' error' : ''}${!installed ? ' available' : ''}" data-plugin-card="${escp(plugin.id)}"><div class="plugin-title"><div><h3>${escp(plugin.name)}</h3><small>${escp(plugin.id)} · v${escp(plugin.version)}</small></div><span class="badge ${good ? 'applied' : bad ? 'pending' : ''}">${status}</span></div><p class="plugin-description">${escp(plugin.description || errorText || 'Plugin package could not be loaded.')}</p><div class="plugin-meta"><div><span>Trust</span><b>${escp(plugin.trust || 'unknown')}</b></div><div><span>Model</span><b>${escp(plugin.kind || 'invalid')}</b></div><div><span>RF mode</span><b>${plugin.rf_mode ? 'YES' : 'NO'}</b></div><div><span>Service</span><b>${escp(plugin.service || 'none')}</b></div></div>${packageRows(plugin)}${serviceRows(plugin)}<div class="plugin-caps">${caps}</div>${errorText ? `<div class="notice plugin-warning">${escp(errorText)}</div>` : ''}${liveRows ? `<div class="plugin-meta">${liveRows}</div>` : ''}${packageActions(plugin)}${enableButtons}${serviceButtons}<div id="pluginResult-${escp(plugin.id)}" class="plugin-result" hidden></div>${installed && plugin.valid ? `<details class="plugin-config"><summary>CONFIGURE</summary><div class="plugin-config-grid">${fields}</div><div class="buttonrow"><button class="btn primary" data-plugin-action="config-save" data-plugin-id="${escp(plugin.id)}">SAVE PLUGIN CONFIG</button></div></details>` : ''}</article>`;
  }

  window.ywdPluginCardRenderer = { pluginCard(plugin, systemEnabled, utils = {}) { if (typeof utils.escp === 'function') escp = utils.escp; if (typeof utils.formatUptime === 'function') formatUptime = utils.formatUptime; return pluginCard(plugin, systemEnabled); } };
})();
