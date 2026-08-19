'use strict';
(() => {
  let pollTimer = null;
  let armedAt = 0;
  let lastProgress = 0;
  let armedBuild = null;
  let reloadScheduled = false;
  let locked = false;
  let lockedOverflow = '';
  let lockObserver = null;

  const el = id => document.getElementById(id);
  const safeText = v => String(v ?? '');

  async function statusFetch() {
    const r = await fetch('/api/update/status', {cache:'no-store', credentials:'same-origin'});
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  function pageBuild() {
    try {
      const current = (typeof state !== 'undefined' && state) ? state : {};
      const build = current?.build || {};
      return {
        version: safeText(build.version || current.version || '').trim(),
        commit: safeText(build.commit || '').trim(),
      };
    } catch (_) {
      return {version:'', commit:''};
    }
  }

  function completedBuild(u) {
    return {
      version: safeText(u.installed_version || u.target_version || '').trim(),
      commit: safeText(u.current_commit || u.target_commit || '').trim(),
    };
  }

  function buildChanged(u) {
    const before = armedBuild || {};
    const after = completedBuild(u);
    if (before.commit && after.commit && after.commit !== 'unknown') return before.commit !== after.commit;
    if (before.version && after.version && after.version !== 'unknown') return before.version !== after.version;
    return false;
  }

  function scheduleFreshDashboard(u) {
    if (reloadScheduled || u.phase === 'up-to-date' || !buildChanged(u)) return false;
    reloadScheduled = true;
    if (el('updateProgressMessage')) el('updateProgressMessage').textContent = 'Update complete. Loading the new dashboard assets…';
    setTimeout(() => location.reload(), 900);
    return true;
  }

  function ensureModal() {
    if (el('updateProgressModal')) return;
    const modal = document.createElement('div');
    modal.className = 'modal update-progress-modal';
    modal.id = 'updateProgressModal';
    modal.tabIndex = -1;
    modal.innerHTML = `
      <div class="dialog update-progress-dialog" role="dialog" aria-modal="true" aria-labelledby="updateProgressTitle">
        <div class="card-title title-row">
          <span id="updateProgressTitle">SOFTWARE UPDATE</span>
          <span id="updateProgressState" class="badge warn">STARTING</span>
        </div>
        <div class="update-progress-stage">
          <span id="updateProgressSpinner" class="update-spinner" aria-hidden="true"></span>
          <div>
            <div id="updateProgressPhase" class="update-progress-phase">Starting update…</div>
            <div id="updateProgressMessage" class="hint">The detached update service is starting.</div>
          </div>
        </div>
        <div class="update-progress-meter-row">
          <div class="update-progress-track" role="progressbar" aria-label="Software update progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
            <div id="updateProgressFill" class="update-progress-fill" data-progress="0"></div>
          </div>
          <b id="updateProgressPercent">0%</b>
        </div>
        <div id="updateProgressTarget" class="update-progress-target"></div>
        <div class="buttonrow update-progress-actions">
          <button class="btn" id="closeUpdateProgress" hidden>CLOSE</button>
          <button class="btn primary" id="reloadUpdateProgress" hidden>RELOAD DASHBOARD</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    el('closeUpdateProgress').addEventListener('click', () => {
      modal.classList.remove('on');
      unlockDashboard();
    });
    el('reloadUpdateProgress').addEventListener('click', () => location.reload());
  }

  function inertBackgroundNode(node) {
    const modal = el('updateProgressModal');
    if (!node || node === modal || node.nodeType !== 1 || node.dataset?.ywdUpdateInert === '1') return;
    if (!node.inert) {
      node.inert = true;
      node.dataset.ywdUpdateInert = '1';
    }
  }

  function lockDashboard() {
    ensureModal();
    const modal = el('updateProgressModal');
    if (!locked) {
      locked = true;
      lockedOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      Array.from(document.body.children).forEach(inertBackgroundNode);
      lockObserver = new MutationObserver(records => {
        records.forEach(record => Array.from(record.addedNodes || []).forEach(inertBackgroundNode));
      });
      lockObserver.observe(document.body, {childList:true});
    }
    modal.inert = false;
    modal.removeAttribute('aria-hidden');
    modal.setAttribute('aria-busy', 'true');
    setTimeout(() => {
      try { modal.focus({preventScroll:true}); } catch (_) { modal.focus(); }
    }, 0);
  }

  function unlockDashboard() {
    if (!locked) return;
    locked = false;
    lockObserver?.disconnect();
    lockObserver = null;
    Array.from(document.body.children).forEach(node => {
      if (node?.dataset?.ywdUpdateInert === '1') {
        node.inert = false;
        delete node.dataset.ywdUpdateInert;
      }
    });
    document.body.style.overflow = lockedOverflow;
    lockedOverflow = '';
    el('updateProgressModal')?.removeAttribute('aria-busy');
  }

  function statusTime(u) {
    const value = u.started_at || u.completed_at || u.updated_at;
    const ms = value ? Date.parse(value) : NaN;
    return Number.isFinite(ms) ? ms : 0;
  }

  function relevant(u) {
    if (!u || !u.state || u.state === 'idle' || u.state === 'checked') return false;
    if (!armedAt) {
      if (u.state !== 'running') return false;
      const t = statusTime(u);
      if (t) armedAt = t;
      return true;
    }
    const t = statusTime(u);
    return !t || t >= armedAt - 1500;
  }

  function setProgress(value) {
    const pct = Math.max(0, Math.min(100, Number(value) || 0));
    lastProgress = Math.max(lastProgress, pct);
    const track = document.querySelector('#updateProgressModal .update-progress-track');
    const fill = el('updateProgressFill');
    if (fill) fill.dataset.progress = String(Math.round(lastProgress / 5) * 5);
    if (track) track.setAttribute('aria-valuenow', String(Math.round(lastProgress)));
    if (el('updateProgressPercent')) el('updateProgressPercent').textContent = `${Math.round(lastProgress)}%`;
  }

  function targetText(u) {
    const version = u.target_version && u.target_version !== 'unknown' ? u.target_version : '';
    const commit = u.target_commit && u.target_commit !== 'unknown' ? String(u.target_commit).slice(0,10) : '';
    const channel = u.channel || '';
    return [version, commit && `@ ${commit}`, channel && `· ${channel}`].filter(Boolean).join(' ');
  }

  function render(u) {
    ensureModal();
    const modal = el('updateProgressModal');
    modal.classList.add('on');
    modal.classList.remove('failed','complete','reconnecting');
    lockDashboard();

    const stateName = safeText(u.state || 'running');
    const phase = safeText(u.phase || 'working');
    const message = safeText(u.message || 'Software update is running…');
    const badge = el('updateProgressState');
    const spinner = el('updateProgressSpinner');
    const close = el('closeUpdateProgress');
    const reload = el('reloadUpdateProgress');

    setProgress(u.progress ?? (stateName === 'complete' ? 100 : lastProgress));
    el('updateProgressPhase').textContent = phase.replace(/[-_]/g,' ').toUpperCase();
    el('updateProgressMessage').textContent = message;
    el('updateProgressTarget').textContent = targetText(u);
    close.hidden = true;
    reload.hidden = true;
    spinner.hidden = false;

    if (stateName === 'complete') {
      modal.classList.add('complete');
      modal.removeAttribute('aria-busy');
      badge.textContent = u.phase === 'up-to-date' ? 'UP TO DATE' : 'COMPLETE';
      badge.className = 'badge good';
      spinner.hidden = true;
      setProgress(100);
      el('updateProgressPhase').textContent = u.phase === 'up-to-date' ? 'ALREADY CURRENT' : 'UPDATE COMPLETE';
      const autoReload = scheduleFreshDashboard(u);
      reload.hidden = autoReload || u.phase === 'up-to-date';
      close.hidden = autoReload;
      stopPolling();
      return;
    }
    if (stateName === 'failed') {
      modal.classList.add('failed');
      modal.removeAttribute('aria-busy');
      badge.textContent = 'FAILED';
      badge.className = 'badge bad';
      spinner.hidden = true;
      el('updateProgressPhase').textContent = 'UPDATE FAILED';
      el('updateProgressMessage').textContent = safeText(u.error || u.message || 'The update failed. Check the update service journal for details.');
      close.hidden = false;
      stopPolling();
      return;
    }

    modal.setAttribute('aria-busy', 'true');
    badge.textContent = `${Math.round(lastProgress)}%`;
    badge.className = 'badge warn';
  }

  function showReconnect() {
    ensureModal();
    const modal = el('updateProgressModal');
    if (!modal.classList.contains('on')) return;
    lockDashboard();
    modal.classList.add('reconnecting');
    el('updateProgressState').textContent = 'RECONNECTING';
    el('updateProgressState').className = 'badge warn';
    el('updateProgressPhase').textContent = 'DASHBOARD RESTARTING';
    el('updateProgressMessage').textContent = 'The updater is still running outside the dashboard. Reconnecting to live update status…';
  }

  function showImmediateStart() {
    render({
      state:'running',
      phase:'starting',
      progress:0,
      message:'Starting the detached updater. Dashboard controls are locked until the update reaches a terminal state.'
    });
  }

  function reflectUpdateCardTerminal() {
    const modal = el('updateProgressModal');
    const cardBadge = el('updateBadge');
    if (!modal?.classList.contains('on') || modal.classList.contains('complete') || modal.classList.contains('failed') || !cardBadge) return;
    const text = safeText(cardBadge.textContent).trim().toUpperCase();
    if (text === 'FAILED') {
      render({state:'failed', error:safeText(el('updateMessage')?.textContent || 'Update failed before live progress became available.')});
    } else if (text === 'UP TO DATE' || text === 'COMPLETE') {
      render({state:'complete', phase:text === 'UP TO DATE' ? 'up-to-date' : 'complete', message:safeText(el('updateMessage')?.textContent || 'Update complete.')});
    }
  }

  async function poll() {
    try {
      const d = await statusFetch();
      const u = d.update || {};
      if (relevant(u)) render(u);
    } catch (_) {
      showReconnect();
    }
  }

  function startPolling() {
    if (pollTimer) return;
    poll();
    pollTimer = setInterval(poll, 1000);
  }

  function stopPolling() {
    if (!pollTimer) return;
    clearInterval(pollTimer);
    pollTimer = null;
  }

  function armForNewUpdate() {
    armedBuild = pageBuild();
    reloadScheduled = false;
    armedAt = Date.now();
    lastProgress = 0;
    showImmediateStart();
    startPolling();
  }

  function init() {
    ensureModal();
    document.addEventListener('click', e => {
      if (e.target && e.target.id === 'confirmUpdate') armForNewUpdate();
    }, true);
    const cardBadge = el('updateBadge');
    if (cardBadge) new MutationObserver(reflectUpdateCardTerminal).observe(cardBadge, {childList:true, characterData:true, subtree:true});
    startPolling();
    setTimeout(() => {
      const modal = el('updateProgressModal');
      if (!modal?.classList.contains('on')) stopPolling();
    }, 5000);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && (el('updateProgressModal')?.classList.contains('on') || armedAt)) startPolling();
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
