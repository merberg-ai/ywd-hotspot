'use strict';
(() => {
  let lastCheck = null;
  let installed = {};
  let pollTimer = null;

  const el = id => document.getElementById(id);
  const escu = v => String(v ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const short = v => (!v || v === 'unknown') ? 'unknown' : String(v).slice(0, 10);

  async function jsonFetch(url, options = {}) {
    const r = await fetch(url, {credentials: 'same-origin', cache: 'no-store', ...options});
    let d = {};
    try { d = await r.json(); } catch (_) {}
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    return d;
  }

  function controlsUnlocked() {
    const b = el('logoutBtn');
    return !!b && !b.hidden;
  }

  function unsavedForm() {
    const b = el('unsavedBadge');
    return !!b && !b.hidden;
  }

  function ensureUi() {
    const about = el('about');
    if (!about || el('softwareUpdateCard')) return;
    const commandCard = Array.from(about.querySelectorAll('article.card')).find(x => x.textContent.includes('UPDATE COMMANDS'));
    if (commandCard) {
      const title = commandCard.querySelector('.card-title');
      if (title) title.textContent = 'CLI UPDATE COMMANDS';
    }
    const card = document.createElement('article');
    card.className = 'card update-card';
    card.id = 'softwareUpdateCard';
    card.innerHTML = `
      <div class="card-title title-row"><span>SOFTWARE UPDATE</span><span id="updateBadge" class="badge">READY</span></div>
      <p class="hint">Updates follow the saved first-party <b>main</b>, <b>dev</b>, or <b>dev-plugins</b> channel. Candidates are fetched and validated before the live hotspot is touched.</p>
      <div id="updateRows" class="update-rows"></div>
      <div id="updateMessage" class="notice update-message">Unlock controls, then check GitHub for an update.</div>
      <div class="buttonrow wrap">
        <button class="btn ctl" id="checkUpdate">CHECK FOR UPDATE</button>
        <button class="btn primary ctl" id="installUpdate" hidden>INSTALL UPDATE</button>
        <button class="btn" id="reloadAfterUpdate" hidden>RELOAD DASHBOARD</button>
      </div>`;
    if (commandCard) about.insertBefore(card, commandCard); else about.appendChild(card);

    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'updateModal';
    modal.innerHTML = `<div class="dialog update-dialog">
      <div class="card-title">INSTALL YWD-HOTSPOT UPDATE?</div>
      <div id="updateConfirmRows" class="update-confirm"></div>
      <p class="hint">The updater creates a protected rollback backup, preserves configuration/credentials and RF policy, and does not recompile MMDVM-Host or DMRGateway. The dashboard and DMR traffic may be interrupted briefly.</p>
      <div class="buttonrow"><button class="btn" id="cancelUpdate">CANCEL</button><button class="btn primary" id="confirmUpdate">INSTALL UPDATE</button></div>
    </div>`;
    document.body.appendChild(modal);

    el('checkUpdate').addEventListener('click', checkForUpdate);
    el('installUpdate').addEventListener('click', openConfirm);
    el('cancelUpdate').addEventListener('click', () => el('updateModal').classList.remove('on'));
    el('confirmUpdate').addEventListener('click', startUpdate);
    el('reloadAfterUpdate').addEventListener('click', () => location.reload());
    modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('on'); });
  }

  function rows(info = {}) {
    const currentVersion = info.installed_version || installed.version || 'unknown';
    const currentCommit = info.current_commit || installed.commit || 'unknown';
    const targetVersion = info.target_version || '—';
    const targetCommit = info.target_commit || '—';
    const channel = info.channel || installed.update_channel || installed.branch || 'unknown';
    return `
      <div class="row"><span>Installed</span><span>${escu(currentVersion)}</span></div>
      <div class="row"><span>Channel</span><span>${escu(channel)}</span></div>
      <div class="row"><span>Current commit</span><span>${escu(short(currentCommit))}</span></div>
      <div class="row"><span>Available</span><span>${escu(targetVersion)}</span></div>
      <div class="row"><span>Target commit</span><span>${escu(short(targetCommit))}</span></div>`;
  }

  function render(info = {}) {
    ensureUi();
    if (!el('softwareUpdateCard')) return;
    el('updateRows').innerHTML = rows(info);
    const badge = el('updateBadge');
    const msg = el('updateMessage');
    const installBtn = el('installUpdate');
    const reloadBtn = el('reloadAfterUpdate');
    const state = info.state || 'idle';
    badge.className = 'badge';
    installBtn.hidden = true;
    reloadBtn.hidden = true;

    if (state === 'running') {
      badge.textContent = 'UPDATING'; badge.classList.add('warn');
      msg.textContent = 'Update is running. The dashboard may disappear briefly; this page will keep reconnecting.';
      el('checkUpdate').disabled = true;
      return;
    }
    if (state === 'failed') {
      badge.textContent = 'FAILED'; badge.classList.add('bad');
      msg.textContent = info.error || 'Update failed. The existing updater should have restored the previous application if live changes had begun.';
      el('checkUpdate').disabled = !controlsUnlocked();
      return;
    }
    if (state === 'complete') {
      badge.textContent = info.phase === 'up-to-date' ? 'UP TO DATE' : 'COMPLETE'; badge.classList.add('good');
      msg.textContent = info.phase === 'up-to-date' ? 'This hotspot is already current.' : 'Update complete. Reload to use the newly installed dashboard assets.';
      reloadBtn.hidden = info.phase === 'up-to-date';
      el('checkUpdate').disabled = !controlsUnlocked();
      return;
    }
    if (info.available) {
      badge.textContent = 'UPDATE AVAILABLE'; badge.classList.add('warn');
      if (info.pending_config) {
        msg.textContent = info.blocked_reason || 'Apply or revert pending configuration changes before updating.';
      } else if (unsavedForm()) {
        msg.textContent = 'Save or discard the unsaved Settings form before updating.';
      } else {
        msg.textContent = `Validated update available: ${info.target_version || 'new build'} @ ${short(info.target_commit)}.`;
        installBtn.hidden = false;
      }
      el('checkUpdate').disabled = !controlsUnlocked();
      return;
    }
    if (info.up_to_date || state === 'checked') {
      badge.textContent = 'UP TO DATE'; badge.classList.add('good');
      msg.textContent = 'No newer build is available on the saved update channel.';
      el('checkUpdate').disabled = !controlsUnlocked();
      return;
    }
    badge.textContent = controlsUnlocked() ? 'READY' : 'LOCKED';
    msg.textContent = controlsUnlocked() ? 'Check the saved GitHub channel for a validated update.' : 'Unlock controls to manage software updates.';
    el('checkUpdate').disabled = !controlsUnlocked();
  }

  async function loadInstalled() {
    try {
      const d = await jsonFetch('/api/status');
      installed = d.build || {};
    } catch (_) {}
  }

  async function loadStatus() {
    try {
      const d = await jsonFetch('/api/update/status');
      const u = d.update || {};
      if (u.state && u.state !== 'idle') {
        if (u.state === 'checked') lastCheck = {...lastCheck, ...u};
        render({...lastCheck, ...u});
        if (u.state === 'running') beginPolling();
        return u;
      }
    } catch (_) {}
    render(lastCheck || {});
    return null;
  }

  async function checkForUpdate() {
    if (unsavedForm()) {
      el('updateMessage').textContent = 'Save or discard unsaved Settings changes before checking/installing an update.';
      return;
    }
    el('checkUpdate').disabled = true;
    el('updateBadge').textContent = 'CHECKING';
    el('updateMessage').textContent = 'Fetching and validating the candidate while the live hotspot keeps running…';
    try {
      const d = await jsonFetch('/api/update/check', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
      lastCheck = {...d, state:'checked'};
      render(lastCheck);
    } catch (e) {
      render({state:'failed', error:e.message});
    }
  }

  function openConfirm() {
    if (!lastCheck?.available || lastCheck?.pending_config || unsavedForm()) return;
    el('updateConfirmRows').innerHTML = `
      <div class="row"><span>Channel</span><span>${escu(lastCheck.channel)}</span></div>
      <div class="row"><span>Current</span><span>${escu(short(lastCheck.current_commit))}</span></div>
      <div class="row"><span>Target</span><span>${escu(short(lastCheck.target_commit))}</span></div>
      <div class="row"><span>Version</span><span>${escu(lastCheck.target_version)}</span></div>`;
    el('updateModal').classList.add('on');
  }

  async function startUpdate() {
    el('confirmUpdate').disabled = true;
    try {
      const d = await jsonFetch('/api/update/start', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
      el('updateModal').classList.remove('on');
      if (!d.started) {
        lastCheck = {...d, state:'complete', phase:'up-to-date'};
        render(lastCheck);
        return;
      }
      lastCheck = {...d, state:'running', phase:'starting'};
      render(lastCheck);
      beginPolling();
    } catch (e) {
      el('updateModal').classList.remove('on');
      render({state:'failed', error:e.message});
    } finally {
      el('confirmUpdate').disabled = false;
    }
  }

  function beginPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(async () => {
      try {
        const d = await jsonFetch('/api/update/status');
        const u = d.update || {};
        render({...lastCheck, ...u});
        if (u.state === 'complete' || u.state === 'failed') {
          clearInterval(pollTimer); pollTimer = null;
          if (u.state === 'complete') await loadInstalled();
        }
      } catch (_) {
        ensureUi();
        if (el('updateBadge')) el('updateBadge').textContent = 'RECONNECTING';
        if (el('updateMessage')) el('updateMessage').textContent = 'Dashboard is restarting. Reconnecting to update status…';
      }
    }, 2000);
  }

  async function init() {
    ensureUi();
    await loadInstalled();
    await loadStatus();
    const logout = el('logoutBtn');
    if (logout) new MutationObserver(() => render(lastCheck || {})).observe(logout, {attributes:true, attributeFilter:['hidden']});
    document.addEventListener('visibilitychange', () => { if (!document.hidden) loadStatus(); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
