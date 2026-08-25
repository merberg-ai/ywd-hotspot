'use strict';
(() => {
  const el = id => document.getElementById(id);
  const esc = value => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const short = value => (!value || value === 'unknown') ? 'unknown' : String(value).slice(0, 10);
  const LABELS = {
    main: ['STABLE', 'Primary supported release channel.'],
    dev: ['DEVELOPMENT', 'Active YWD-Hotspot development channel.'],
    'dev-plugins': ['PLUGIN DEVELOPMENT', 'Plugin/runtime integration development channel.'],
  };

  let inventory = null;
  let selected = null;
  let loading = false;

  function unlocked() {
    const logout = el('logoutBtn');
    return !!logout && !logout.hidden;
  }

  function unsaved() {
    const badge = el('unsavedBadge');
    return !!badge && !badge.hidden;
  }

  async function postJson(url, body = {}) {
    const r = await fetch(url, {
      method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: {'Content-Type':'application/json'}, body: JSON.stringify(body),
    });
    let d = {};
    try { d = await r.json(); } catch (_) {}
    if (!r.ok || d?.error) throw new Error(d?.error || `HTTP ${r.status}`);
    return d;
  }

  function injectStyle() {
    if (el('ywdBranchStyle')) return;
    const style = document.createElement('style');
    style.id = 'ywdBranchStyle';
    style.textContent = `
      .branch-dialog{max-width:760px;max-height:min(88vh,820px);overflow:auto}
      .branch-current{margin:12px 0;padding:12px;border:1px solid rgba(98,233,255,.18);border-radius:10px;background:rgba(3,12,17,.62)}
      .branch-current-grid,.branch-detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 18px}
      .branch-current-grid>div,.branch-detail-grid>div{display:flex;justify-content:space-between;gap:14px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.06)}
      .branch-current-grid span,.branch-detail-grid span{color:var(--muted);font-size:10px;letter-spacing:.05em}
      .branch-current-grid b,.branch-detail-grid b{text-align:right;overflow-wrap:anywhere;font-size:10px}
      .branch-options{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:13px 0}
      .branch-option{appearance:none;text-align:left;padding:12px;border:1px solid var(--line);border-radius:10px;background:#061017;color:var(--text);cursor:pointer;min-height:82px}
      .branch-option:hover,.branch-option:focus-visible{border-color:var(--cyan);outline:none;box-shadow:0 0 0 1px rgba(98,233,255,.12),0 0 18px rgba(98,233,255,.08)}
      .branch-option.on{border-color:var(--cyan);background:linear-gradient(180deg,rgba(12,49,58,.92),rgba(4,18,24,.94));box-shadow:0 0 18px rgba(98,233,255,.12)}
      .branch-option strong{display:block;color:var(--cyan);font-size:11px;letter-spacing:.08em;margin-bottom:5px}
      .branch-option small{display:block;color:var(--muted);line-height:1.35}
      .branch-option .branch-version{margin-top:7px;color:var(--text);font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:10px}
      .branch-relation{display:inline-block;padding:3px 7px;border:1px solid var(--line);border-radius:999px;font-size:9px;letter-spacing:.07em}
      .branch-relation.good{color:var(--good);border-color:rgba(107,244,165,.45)}
      .branch-relation.warn{color:#ffd36f;border-color:rgba(255,197,74,.5)}
      .branch-relation.bad{color:var(--bad);border-color:rgba(255,108,125,.55)}
      .branch-warning{margin:12px 0;padding:11px 12px;border:1px solid rgba(255,197,74,.32);border-radius:9px;background:rgba(45,31,7,.34);color:#e8d6a4;line-height:1.45;font-size:11px;white-space:pre-line}
      .branch-warning.danger{border-color:rgba(255,108,125,.45);background:rgba(52,14,21,.38);color:#ffc0c9}
      .branch-actions{justify-content:flex-end;margin-top:15px}
      #branchSwitchStatus{margin:10px 0}
      @media(max-width:640px){
        .branch-dialog{max-height:92vh;padding:14px}
        .branch-options,.branch-current-grid,.branch-detail-grid{grid-template-columns:1fr}
        .branch-current-grid>div,.branch-detail-grid>div{align-items:flex-start;flex-direction:column;gap:3px}
        .branch-current-grid b,.branch-detail-grid b{text-align:left}
        .branch-option{min-height:0}
        .branch-actions .btn{width:100%}
      }
    `;
    document.head.appendChild(style);
  }

  function relationInfo(row) {
    const rel = row?.relation || 'unknown';
    if (rel === 'current') return ['CURRENT BUILD', 'good'];
    if (rel === 'forward') return ['FORWARD', 'good'];
    if (rel === 'backward') return ['DOWNGRADE', 'bad'];
    if (rel === 'diverged') return ['DIFFERENT LINE', 'warn'];
    return ['UNKNOWN', 'warn'];
  }

  function warningFor(row) {
    if (!row) return '';
    const lines = [];
    if (row.same_installed_commit) {
      if (inventory?.saved_channel === row.branch && inventory?.checkout_branch === row.branch) {
        lines.push('This branch already owns the installed build and is the saved update channel. No switch is needed.');
      } else {
        lines.push('This branch points at the exact installed commit. Switching will only adopt the managed checkout/update channel; application files do not need to be reinstalled.');
      }
    } else if (row.relation === 'backward') {
      lines.push('WARNING: This target is behind the installed commit. The switch is a software downgrade. A protected rollback backup is created first, but older code may not understand every newer feature/state file.');
    } else if (row.relation === 'diverged') {
      lines.push('WARNING: This target is on a diverged development line rather than a simple forward/backward ancestry path. Treat the transition as experimental.');
    } else if (row.relation === 'forward') {
      lines.push('This target is a descendant of the installed build. The normal protected update/rollback workflow will be used.');
    } else {
      lines.push('The ancestry relationship could not be proven. The candidate will still be fully validated before the live hotspot is touched.');
    }

    if (row.branch === 'dev') {
      lines.push('DEV may contain unfinished or rapidly changing work. It is intended for development/testing rather than normal stable installations.');
    } else if (row.branch === 'dev-plugins') {
      lines.push('DEV-PLUGINS may change plugin/runtime compatibility. Moving into or out of it can quiesce or remove branch-specific plugin runtime services while preserving supported appliance state/backups.');
    } else {
      lines.push('MAIN is the stable channel, but when the currently installed development build is newer than MAIN, selecting MAIN is still a downgrade.');
    }
    lines.push('A branch switch never flashes the physical MMDVM HAT and normal app switching does not intentionally rebuild MMDVM-Host/DMRGateway. Dashboard and RF/network services may restart briefly.');
    return lines.join('\n\n');
  }

  function ensureModal() {
    injectStyle();
    if (el('branchChannelModal')) return;
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'branchChannelModal';
    modal.innerHTML = `
      <div class="dialog branch-dialog" role="dialog" aria-modal="true" aria-labelledby="branchChannelTitle">
        <div class="card-title title-row"><span id="branchChannelTitle">SOFTWARE CHANNEL</span><span id="branchModalBadge" class="badge">LOCKED</span></div>
        <p class="hint">Choose which approved first-party GitHub branch this hotspot follows. Release/checkpoint branches remain CLI-only engineering targets.</p>
        <div id="branchCurrent" class="branch-current">Loading current checkout…</div>
        <div class="label">APPROVED CHANNELS</div>
        <div id="branchOptions" class="branch-options"></div>
        <div id="branchSelected"></div>
        <div id="branchSwitchStatus" class="notice" hidden></div>
        <div class="buttonrow branch-actions"><button class="btn" id="branchCancel">CANCEL</button><button class="btn primary ctl" id="branchSwitch" disabled>SWITCH CHANNEL</button></div>
      </div>`;
    document.body.appendChild(modal);
    el('branchCancel').addEventListener('click', closeModal);
    el('branchSwitch').addEventListener('click', switchSelected);
    modal.addEventListener('click', event => { if (event.target === modal) closeModal(); });
  }

  function closeModal() {
    el('branchChannelModal')?.classList.remove('on');
  }

  function renderCurrent() {
    if (!inventory) return;
    el('branchCurrent').innerHTML = `
      <div class="label">CURRENT INSTALLATION</div>
      <div class="branch-current-grid">
        <div><span>INSTALLED</span><b>${esc(inventory.installed_version)} @ ${esc(inventory.installed_commit_short)}</b></div>
        <div><span>SAVED CHANNEL</span><b>${esc(inventory.saved_channel)}</b></div>
        <div><span>CHECKOUT</span><b>${esc(inventory.checkout_branch)}</b></div>
        <div><span>SOURCE</span><b>${esc(inventory.source)} / ${esc(inventory.source_state)}</b></div>
      </div>`;
  }

  function renderOptions() {
    if (!inventory) return;
    el('branchOptions').innerHTML = inventory.branches.map(row => {
      const [role] = LABELS[row.branch] || [row.label || row.branch];
      const selectedClass = selected?.branch === row.branch ? ' on' : '';
      return `<button type="button" class="branch-option${selectedClass}" data-ywd-branch="${esc(row.branch)}">
        <strong>${esc(row.branch)} · ${esc(role)}</strong>
        <small>${esc(row.description || '')}</small>
        <span class="branch-version">${esc(row.version)} @ ${esc(row.commit_short)}</span>
      </button>`;
    }).join('');
    document.querySelectorAll('[data-ywd-branch]').forEach(button => {
      button.addEventListener('click', () => selectBranch(button.dataset.ywdBranch));
    });
  }

  function renderSelected() {
    const host = el('branchSelected');
    const button = el('branchSwitch');
    if (!selected) {
      host.innerHTML = '<p class="hint">Select a channel to inspect its current GitHub head.</p>';
      button.disabled = true;
      return;
    }
    const [relText, relTone] = relationInfo(selected);
    const role = LABELS[selected.branch]?.[0] || selected.label || selected.branch;
    const already = selected.same_installed_commit && inventory.saved_channel === selected.branch && inventory.checkout_branch === selected.branch;
    const warning = warningFor(selected);
    host.innerHTML = `
      <div class="label">SELECTED TARGET</div>
      <div class="branch-detail-grid">
        <div><span>BRANCH</span><b>${esc(selected.branch)} · ${esc(role)}</b></div>
        <div><span>TRANSITION</span><b><span class="branch-relation ${esc(relTone)}">${esc(relText)}</span></b></div>
        <div><span>VERSION</span><b>${esc(selected.version)}</b></div>
        <div><span>HEAD COMMIT</span><b title="${esc(selected.commit)}">${esc(selected.commit_short)}</b></div>
        <div><span>COMMIT DATE</span><b>${esc(selected.date)}</b></div>
        <div><span>CONFIG SCHEMA</span><b>${esc(selected.config_schema ?? 'unknown')}</b></div>
        <div><span>PLUGIN RUNTIME</span><b>${selected.plugin_runtime ? 'present' : 'not present'}</b></div>
        <div><span>LATEST COMMIT</span><b>${esc(selected.subject)}</b></div>
      </div>
      <div class="branch-warning ${selected.relation === 'backward' ? 'danger' : ''}">${esc(warning).replace(/\n/g,'<br>')}</div>`;
    button.disabled = !unlocked() || already || loading;
    button.textContent = already
      ? 'ALREADY SELECTED'
      : selected.same_installed_commit
        ? `ADOPT ${selected.branch.toUpperCase()} CHANNEL`
        : `SWITCH TO ${selected.branch.toUpperCase()}`;
  }

  function selectBranch(name) {
    selected = inventory?.branches?.find(row => row.branch === name) || null;
    renderOptions();
    renderSelected();
  }

  async function loadInventory() {
    loading = true;
    el('branchModalBadge').textContent = 'FETCHING';
    el('branchModalBadge').className = 'badge warn';
    el('branchOptions').innerHTML = '<div class="hint">Fetching approved branch heads from GitHub…</div>';
    el('branchSelected').innerHTML = '';
    try {
      inventory = await postJson('/api/update/branches', {});
      const preferred = inventory.branches?.find(row => row.branch === inventory.saved_channel)
        || inventory.branches?.find(row => row.branch === inventory.checkout_branch)
        || inventory.branches?.[0]
        || null;
      selected = preferred;
      renderCurrent();
      renderOptions();
      renderSelected();
      el('branchModalBadge').textContent = 'READY';
      el('branchModalBadge').className = 'badge good';
    } catch (error) {
      inventory = null;
      selected = null;
      el('branchCurrent').textContent = 'Branch inventory unavailable.';
      el('branchOptions').innerHTML = '';
      el('branchSelected').innerHTML = `<div class="notice">${esc(error.message)}</div>`;
      el('branchModalBadge').textContent = 'FAILED';
      el('branchModalBadge').className = 'badge bad';
    } finally {
      loading = false;
      renderSelected();
    }
  }

  async function openModal() {
    if (!unlocked()) {
      toast('Unlock dashboard controls before changing the software channel', true);
      return;
    }
    if (unsaved()) {
      toast('Save or discard unsaved Settings changes before changing channels', true);
      return;
    }
    ensureModal();
    el('branchSwitchStatus').hidden = true;
    el('branchChannelModal').classList.add('on');
    await loadInventory();
  }

  async function switchSelected() {
    if (!selected || loading || !unlocked()) return;
    if (unsaved()) {
      toast('Save or discard unsaved Settings changes before changing channels', true);
      return;
    }
    const branch = selected.branch;
    const relation = selected.relation;
    const currentText = `${inventory.installed_version} @ ${inventory.installed_commit_short}`;
    const targetText = `${selected.version} @ ${selected.commit_short}`;
    const relationText = relation === 'backward' ? 'DOWNGRADE' : relation === 'diverged' ? 'DIVERGED BRANCH CHANGE' : relation === 'forward' ? 'FORWARD UPDATE' : selected.same_installed_commit ? 'CHANNEL ADOPTION' : 'BRANCH CHANGE';
    const message = [
      `Current: ${currentText} · ${inventory.saved_channel}`,
      `Target: ${targetText} · ${branch}`,
      `Transition: ${relationText}`,
      '',
      relation === 'backward'
        ? 'This installs older application code. A protected rollback backup is created first, but downgrade compatibility cannot be guaranteed for every future feature.'
        : selected.same_installed_commit
          ? 'The selected branch already points at the installed commit, so only the managed checkout/update channel needs to change.'
          : 'The selected branch will be fetched and fully validated before live application files are changed.',
      '',
      'Configuration and normal appliance state are preserved by the updater. RF/dashboard services may restart briefly. Physical MMDVM HAT firmware is not flashed.',
    ].join('\n');

    const confirmFn = typeof window.ywdConfirm === 'function' ? window.ywdConfirm : null;
    if (!confirmFn) {
      toast('YWD confirmation UI is unavailable. Reload the dashboard and try again.', true);
      return;
    }
    const ok = await confirmFn({
      title: `SWITCH TO ${branch.toUpperCase()}?`,
      message,
      confirmText: selected.same_installed_commit ? `ADOPT ${branch.toUpperCase()}` : `SWITCH TO ${branch.toUpperCase()}`,
      cancelText: 'CANCEL',
      tone: relation === 'backward' ? 'danger' : 'warn',
      kicker: 'YWD // SOFTWARE CHANNEL',
    });
    if (!ok) return;

    const button = el('branchSwitch');
    const status = el('branchSwitchStatus');
    loading = true;
    button.disabled = true;
    button.textContent = selected.same_installed_commit ? 'ADOPTING…' : 'VALIDATING…';
    status.hidden = false;
    status.textContent = selected.same_installed_commit
      ? `Adopting ${branch} as the managed checkout/update channel…`
      : `Validating ${branch} and preparing the protected branch switch. The live RF stack remains untouched during validation…`;
    try {
      const result = await postJson('/api/update/branch/switch', {branch});
      closeModal();
      if (result.adopted) {
        toast(`Software channel changed to ${branch}; installed files already matched`);
        setTimeout(() => location.reload(), 350);
        return;
      }
      if (result.started) {
        toast(`Protected switch to ${branch} started`);
        // Reload once so the existing update-progress bootstrap sees the shared
        // detached update-status document and takes over reconnect/progress UI.
        setTimeout(() => location.reload(), 350);
        return;
      }
      toast(`No branch change was required for ${branch}`);
    } catch (error) {
      status.textContent = `Branch switch failed: ${error.message}`;
      status.className = 'notice badtext';
      toast(error.message || 'Could not switch software channel', true);
    } finally {
      loading = false;
      renderSelected();
    }
  }

  function installButton() {
    const card = el('softwareUpdateCard');
    if (!card || el('changeUpdateChannel')) return !!card;
    const row = card.querySelector('.buttonrow');
    if (!row) return false;
    const button = document.createElement('button');
    button.id = 'changeUpdateChannel';
    button.type = 'button';
    button.className = 'btn ctl';
    button.textContent = 'CHANGE CHANNEL';
    button.disabled = !unlocked();
    button.addEventListener('click', openModal);
    const install = el('installUpdate');
    row.insertBefore(button, install || row.firstChild || null);
    return true;
  }

  function syncLock() {
    const button = el('changeUpdateChannel');
    if (button) button.disabled = !unlocked();
    if (!unlocked()) closeModal();
  }

  function init() {
    ensureModal();
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (installButton() || tries > 100) clearInterval(timer);
    }, 100);
    installButton();
    const logout = el('logoutBtn');
    if (logout) new MutationObserver(syncLock).observe(logout, {attributes:true, attributeFilter:['hidden']});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
