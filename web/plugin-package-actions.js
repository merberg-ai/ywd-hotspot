'use strict';
(() => {
  function checkText(section, title, emptyText) {
    const items = Array.isArray(section?.items) ? section.items : [];
    if (!items.length) return `${title}: PASS — ${emptyText}`;
    return [`${title}: ${section.ok ? 'PASS' : 'MISSING'}`]
      .concat(items.map(item => `${item.ok ? 'PASS' : 'MISS'}  ${item.label} — ${item.detail || item.id}`))
      .join('\n');
  }

  async function handle(action, ctx) {
    const {button,id,pluginState,beginBusy,post,render,notify,confirmYwd,showResult} = ctx;
    let done = () => {};
    try {
      if (action === 'package-install') {
        done = beginBusy(button, 'INSTALLING…');
        const data = await post('/api/plugins/install', {id});
        render(data.plugins_state);
        notify(`${id} installed — remains disabled`);
        return true;
      }
      if (action === 'package-uninstall') {
        const plugin = (pluginState?.plugins || []).find(p => p.id === id);
        const ok = await confirmYwd({
          title:'UNINSTALL PLUGIN',
          message:`Uninstall ${plugin?.name || id}?\n\nAny service runtime and boot activation will be stopped/removed. The package will no longer be eligible to run. Configuration and plugin data are preserved until you explicitly choose REMOVE DATA.`,
          confirmText:'UNINSTALL', cancelText:'CANCEL', tone:'danger', kicker:'YWD // PLUGINS'
        });
        if (!ok) return true;
        done = beginBusy(button, 'UNINSTALLING…');
        const data = await post('/api/plugins/uninstall', {id});
        render(data.plugins_state);
        notify(`${id} uninstalled; data preserved`);
        return true;
      }
      if (action === 'package-data-remove') {
        const plugin = (pluginState?.plugins || []).find(p => p.id === id);
        const ok = await confirmYwd({
          title:'REMOVE PLUGIN DATA',
          message:`Permanently remove saved configuration and owned runtime data for ${plugin?.name || id}?\n\nThis is separate from uninstall and cannot be undone. The plugin must be disabled and its service stopped.`,
          confirmText:'REMOVE DATA', cancelText:'CANCEL', tone:'danger', kicker:'YWD // PLUGINS'
        });
        if (!ok) return true;
        done = beginBusy(button, 'REMOVING…');
        const data = await post('/api/plugins/data-remove', {id});
        render(data.plugins_state);
        notify(data.nothing_to_remove ? `${id} had no saved data` : `${id} data removed`);
        return true;
      }
      if (action === 'package-check-deps' || action === 'package-check-hardware') {
        const kind = action === 'package-check-deps' ? 'dependencies' : 'hardware';
        done = beginBusy(button, 'CHECKING…');
        const data = await post('/api/plugins/check', {id,kind});
        if (data.plugins_state) render(data.plugins_state);
        const title = kind === 'dependencies' ? 'Dependencies' : 'Hardware';
        const empty = kind === 'dependencies' ? 'no external dependencies declared' : 'no special hardware required';
        showResult(id, checkText(data[kind], title, empty), !data.ok);
        notify(`${id} ${kind} check ${data.ok ? 'passed' : 'found missing requirements'}`, !data.ok);
        return true;
      }
      return false;
    } finally {
      done();
    }
  }

  window.ywdPluginPackageUi = {handle};
})();
