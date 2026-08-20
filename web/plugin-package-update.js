'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
  const notify = (message, bad = false) => {
    try { if (typeof toast === 'function') return toast(message, bad); } catch (_) {}
    console[bad ? 'error' : 'log'](message);
  };
  const unlocked = () => !!$('logoutBtn') && !$('logoutBtn').hidden;

  function bytesToB64(bytes) {
    let out = '';
    for (let i = 0; i < bytes.length; i += 0x8000) out += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(out);
  }

  function setProgress(percent, active = true) {
    const wrap = $('pluginUploadProgress'), bar = $('pluginUploadProgressBar'), label = $('pluginUploadProgressText');
    if (!wrap || !bar || !label) return;
    wrap.hidden = !active;
    bar.style.width = `${percent}%`;
    label.textContent = `${percent}%`;
  }

  function request(path, body, onProgress, onUploaded) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', path, true);
      xhr.withCredentials = true;
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.upload.onprogress = event => {
        if (!event.lengthComputable || !onProgress) return;
        onProgress(Math.max(0, Math.min(100, Math.round((event.loaded / event.total) * 100))));
      };
      xhr.upload.onload = () => { if (onProgress) onProgress(100); if (onUploaded) onUploaded(); };
      xhr.onerror = () => reject(new Error('Plugin package request failed before the hotspot responded.'));
      xhr.onload = () => {
        let data = {};
        try { data = JSON.parse(xhr.responseText || '{}'); } catch (_) {}
        if (xhr.status < 200 || xhr.status >= 300) return reject(new Error(data.error || `HTTP ${xhr.status}`));
        resolve(data);
      };
      xhr.send(JSON.stringify(body));
    });
  }

  function ensureModal() {
    if ($('pluginUpdateReviewModal')) return $('pluginUpdateReviewModal');
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'pluginUpdateReviewModal';
    modal.innerHTML = `<div class="dialog plugin-install-dialog plugin-update-dialog" role="dialog" aria-modal="true" aria-labelledby="pluginUpdateReviewTitle">
      <div class="card-title title-row"><span id="pluginUpdateReviewTitle">PLUGIN PACKAGE REVIEW</span><span class="badge" id="pluginUpdateReviewBadge">WORKING</span></div>
      <div class="plugin-install-steps">
        <div data-update-stage="upload"><span>PACKAGE UPLOAD</span><b>COMPLETE</b></div>
        <div data-update-stage="verify"><span>VERIFY + CLASSIFY</span><b>WORKING…</b></div>
        <div data-update-stage="apply"><span>INSTALL / UPDATE</span><b>WAITING</b></div>
      </div>
      <div id="pluginUpdateReviewMessage" class="notice">Validating the package…</div>
      <div id="pluginUpdateReviewDetails" class="plugin-install-details" hidden></div>
      <div id="pluginUpdateReviewCaps" class="plugin-update-caps" hidden></div>
      <div id="pluginUpdateReviewWarnings" class="plugin-update-warnings" hidden></div>
      <div class="buttonrow plugin-install-review-actions"><button class="btn" id="pluginUpdateCancel" disabled>CANCEL</button><button class="btn primary" id="pluginUpdateConfirm" hidden>INSTALL PLUGIN</button></div>
    </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', event => { if (event.target === modal && !$('pluginUpdateCancel')?.disabled) modal.classList.remove('on'); });
    $('pluginUpdateCancel').onclick = () => modal.classList.remove('on');
    return modal;
  }

  function setStage(name, text, state = '') {
    const row = document.querySelector(`[data-update-stage="${name}"]`);
    if (!row) return;
    row.className = state;
    const value = row.querySelector('b');
    if (value) value.textContent = text;
  }

  function showVerifying() {
    const modal = ensureModal();
    setStage('upload', 'COMPLETE', 'good'); setStage('verify', 'WORKING…', 'working'); setStage('apply', 'WAITING', '');
    $('pluginUpdateReviewTitle').textContent = 'PLUGIN PACKAGE REVIEW';
    $('pluginUpdateReviewBadge').textContent = 'VERIFYING';
    $('pluginUpdateReviewBadge').className = 'badge warn';
    $('pluginUpdateReviewMessage').className = 'notice';
    $('pluginUpdateReviewMessage').textContent = 'Checking package identity, hashes, signature trust, requirements, version, capabilities, and configuration compatibility.';
    $('pluginUpdateReviewDetails').hidden = true; $('pluginUpdateReviewCaps').hidden = true; $('pluginUpdateReviewWarnings').hidden = true;
    $('pluginUpdateConfirm').hidden = true; $('pluginUpdateCancel').disabled = true;
    modal.classList.add('on');
  }

  function actionLabel(review) {
    const installed = review.current?.installed !== false;
    if (review.operation === 'install') return 'INSTALL PLUGIN';
    if (!installed) return 'UPDATE PACKAGE';
    if (review.operation === 'update') return 'UPDATE PLUGIN';
    if (review.operation === 'reinstall') return 'REINSTALL PLUGIN';
    if (review.operation === 'downgrade') return 'DOWNGRADE PLUGIN';
    return 'REPLACE PLUGIN';
  }

  function titleFor(review) {
    if (review.operation === 'install') return 'NEW PLUGIN';
    if (review.operation === 'update') return 'PLUGIN UPDATE';
    if (review.operation === 'reinstall') return 'PLUGIN REINSTALL';
    if (review.operation === 'downgrade') return 'PLUGIN DOWNGRADE';
    return 'PLUGIN VERSION REPLACEMENT';
  }

  function kindText(kind) {
    if (kind === 'ui') return 'Browser UI plugin';
    if (kind === 'service') return 'Sandboxed service plugin';
    if (kind === 'declarative') return 'Declarative plugin';
    return kind || 'Unknown';
  }

  function renderCapabilityChanges(review) {
    const box = $('pluginUpdateReviewCaps');
    const current = review.current?.capabilities || [], candidate = review.candidate?.capabilities || [];
    const added = review.capability_changes?.added || [], removed = review.capability_changes?.removed || [];
    box.hidden = false;
    box.innerHTML = `<div class="plugin-update-section-title">CAPABILITIES</div><div class="plugin-update-cap-columns">
      <div><span>Current</span><div class="plugin-caps">${current.length ? current.map(x => `<span class="plugin-cap">${esc(x)}</span>`).join('') : '<span class="plugin-cap">none</span>'}</div></div>
      <div><span>Candidate</span><div class="plugin-caps">${candidate.length ? candidate.map(x => `<span class="plugin-cap">${esc(x)}</span>`).join('') : '<span class="plugin-cap">none</span>'}</div></div>
    </div>${(added.length || removed.length) ? `<div class="plugin-update-delta">${added.map(x => `<span class="plugin-cap plugin-cap-added">+ ${esc(x)}</span>`).join('')}${removed.map(x => `<span class="plugin-cap plugin-cap-removed">− ${esc(x)}</span>`).join('')}</div>` : ''}`;
  }

  function renderWarnings(review) {
    const warnings = [], addedCaps = review.capability_changes?.added || [], cfg = review.configuration || {};
    if (addedCaps.length) warnings.push(`New capabilities requested: ${addedCaps.join(', ')}`);
    if (review.operation === 'downgrade') warnings.push('This candidate is older than the currently installed package.');
    if (review.operation === 'replace') warnings.push('Version ordering could not be determined; review the versions carefully.');
    if (!review.requirements_ok) warnings.push(review.requirements_error || 'Plugin requirements are not satisfied.');
    if (cfg.migration_required) {
      const bits = [];
      if (cfg.added_keys?.length) bits.push(`defaults added: ${cfg.added_keys.join(', ')}`);
      if (cfg.dropped_keys?.length) bits.push(`obsolete keys removed: ${cfg.dropped_keys.join(', ')}`);
      if (cfg.reset_keys?.length) bits.push(`incompatible values reset: ${cfg.reset_keys.join(', ')}`);
      warnings.push(`Configuration will be normalized (${bits.join('; ') || 'schema changed'}).`);
    }
    const box = $('pluginUpdateReviewWarnings');
    box.hidden = warnings.length === 0;
    box.innerHTML = warnings.map(text => `<div class="notice plugin-warning">${esc(text)}</div>`).join('');
  }

  function showReview(review, applyBody) {
    const modal = ensureModal(), candidate = review.candidate || {}, current = review.current;
    const signature = review.signature || {}, cfg = review.configuration || {}, label = actionLabel(review);
    $('pluginUpdateReviewTitle').textContent = titleFor(review);
    $('pluginUpdateReviewBadge').textContent = review.requirements_ok ? 'READY' : 'BLOCKED';
    $('pluginUpdateReviewBadge').className = `badge ${review.requirements_ok ? 'applied' : 'pending'}`;
    setStage('verify', 'PASS', 'good'); setStage('apply', 'READY', 'good');
    $('pluginUpdateReviewMessage').className = `notice ${review.requirements_ok ? 'plugin-good' : 'plugin-warning'}`;
    $('pluginUpdateReviewMessage').textContent = current ? `Verified ${current.version} → ${candidate.version}. Review the update before applying it.` : `Verified ${candidate.name || review.id} ${candidate.version}. Review the plugin before installing it.`;

    const details = $('pluginUpdateReviewDetails'); details.hidden = false;
    details.innerHTML = `<div class="plugin-install-name"><strong>${esc(candidate.name || review.id)}</strong><span>${esc(review.id)}</span></div>
      <div class="plugin-version-flow">${current ? `<span>${esc(current.version)}</span><b>→</b>` : ''}<span class="candidate">${esc(candidate.version || 'unknown')}</span></div>
      <p>${esc(candidate.description || 'No plugin description was provided.')}</p>
      <div class="plugin-meta">
        <div><span>Action</span><b>${esc(label)}</b></div><div><span>Type</span><b>${esc(kindText(candidate.kind))}</b></div>
        <div><span>Signature</span><b>${signature.status === 'verified' ? `VERIFIED · ${esc(signature.key_id || 'trusted key')}` : esc(String(signature.status || 'unknown').toUpperCase())}</b></div>
        <div><span>Requirements</span><b>${review.requirements_ok ? 'PASS' : 'BLOCKED'}</b></div>
        <div><span>Configuration</span><b>${cfg.present ? (cfg.migration_required ? 'PRESERVE + NORMALIZE' : 'PRESERVED') : 'NONE'}</b></div>
        <div><span>Plugin data</span><b>${current?.data_present ? 'PRESERVED' : 'NONE'}</b></div>
        <div><span>Installed state</span><b>${current ? (current.installed ? 'PRESERVED · INSTALLED' : 'PRESERVED · NOT INSTALLED') : 'INSTALL'}</b></div>
        <div><span>Enabled state</span><b>${current ? (current.enabled ? 'PRESERVED · ENABLED' : 'PRESERVED · DISABLED') : 'DISABLED AFTER INSTALL'}</b></div>
      </div>`;
    renderCapabilityChanges(review); renderWarnings(review);

    const confirm = $('pluginUpdateConfirm'), cancel = $('pluginUpdateCancel');
    cancel.disabled = false; cancel.textContent = 'CANCEL';
    confirm.hidden = false; confirm.disabled = !review.requirements_ok; confirm.textContent = label;
    confirm.onclick = async () => {
      confirm.disabled = true; cancel.disabled = true; confirm.classList.add('ywd-working'); confirm.setAttribute('aria-busy', 'true');
      confirm.textContent = review.operation === 'install' ? 'INSTALLING…' : 'UPDATING…'; setStage('apply', 'APPLYING…', 'working');
      try {
        const result = await request('/api/plugins/package-apply', applyBody, null, null);
        setStage('apply', 'COMPLETE', 'good'); $('pluginUpdateReviewBadge').textContent = 'COMPLETE'; $('pluginUpdateReviewBadge').className = 'badge applied';
        $('pluginUpdateReviewMessage').className = 'notice plugin-good';
        $('pluginUpdateReviewMessage').textContent = result.operation === 'install' ? 'Plugin installed successfully. It remains disabled until you explicitly enable it.' : `Plugin ${result.operation} completed successfully. Installed/enabled state and plugin data were preserved.`;
        notify(result.operation === 'install' ? `${result.id} installed` : `${result.id} ${result.operation} complete`);
        setTimeout(() => { modal.classList.remove('on'); document.querySelector('[data-tab="plugins"]')?.click(); }, 850);
      } catch (error) {
        setStage('apply', 'ROLLED BACK / FAILED', 'bad'); $('pluginUpdateReviewBadge').textContent = 'FAILED'; $('pluginUpdateReviewBadge').className = 'badge pending';
        $('pluginUpdateReviewMessage').className = 'notice plugin-warning'; $('pluginUpdateReviewMessage').textContent = `${error.message} The previous plugin package/state was retained or restored.`;
        notify(error.message, true); cancel.disabled = false; confirm.disabled = false; confirm.textContent = `TRY ${label} AGAIN`;
      } finally { confirm.classList.remove('ywd-working'); confirm.removeAttribute('aria-busy'); }
    };
    modal.classList.add('on');
  }

  function showError(message) {
    const modal = ensureModal(); setStage('verify', 'FAILED', 'bad'); setStage('apply', 'BLOCKED', 'bad');
    $('pluginUpdateReviewBadge').textContent = 'REJECTED'; $('pluginUpdateReviewBadge').className = 'badge pending';
    $('pluginUpdateReviewMessage').className = 'notice plugin-warning'; $('pluginUpdateReviewMessage').textContent = message;
    $('pluginUpdateReviewDetails').hidden = true; $('pluginUpdateReviewCaps').hidden = true; $('pluginUpdateReviewWarnings').hidden = true; $('pluginUpdateConfirm').hidden = true;
    $('pluginUpdateCancel').disabled = false; $('pluginUpdateCancel').textContent = 'CLOSE'; modal.classList.add('on');
  }

  function patchUploadInput() {
    const input = $('pluginUploadFile'), button = $('pluginUploadButton');
    if (!input || !button) return false;
    if (input.dataset.transactionalUpdater === '1') return true;
    input.dataset.transactionalUpdater = '1';
    const note = button.closest('.plugin-upload-card')?.querySelector('.plugin-api-note');
    if (note) note.textContent = 'Upload a signed .ywdplugin package to verify it. New plugin IDs are offered for install; existing uploaded IDs are classified as update, reinstall, downgrade, or replacement before anything changes.';

    input.onchange = async () => {
      const file = input.files?.[0]; input.value = '';
      if (!file) return;
      if (!unlocked()) return notify('Unlock controls before reviewing a plugin package.', true);
      if (file.size <= 0 || file.size > 1024 * 1024) return notify('Plugin archive is empty or exceeds 1 MiB.', true);
      const previous = button.textContent; button.dataset.pluginBusy = '1'; button.disabled = true; button.classList.add('ywd-working'); button.setAttribute('aria-busy', 'true'); button.textContent = 'PREPARING…'; setProgress(0, true);
      try {
        const bytes = new Uint8Array(await file.arrayBuffer());
        const body = {filename: file.name, archive_b64: bytesToB64(bytes)};
        button.textContent = 'UPLOADING…';
        const review = await request('/api/plugins/package-review', body, pct => { setProgress(pct, true); button.textContent = `UPLOADING… ${pct}%`; }, () => { button.textContent = 'VERIFYING…'; showVerifying(); });
        const action = actionLabel(review);
        $('pluginUploadStatus').textContent = `${review.id} verified · ${review.current ? `${review.current.version} → ` : ''}${review.candidate?.version || 'unknown'} · ${action}.`;
        notify(`${review.id} verified — ${action.toLowerCase()} ready`);
        showReview(review, body);
      } catch (error) {
        $('pluginUploadStatus').textContent = error.message; notify(error.message, true); showError(error.message);
      } finally {
        delete button.dataset.pluginBusy; button.classList.remove('ywd-working'); button.removeAttribute('aria-busy'); button.textContent = previous; setTimeout(() => setProgress(0, false), 500);
      }
    };
    return true;
  }

  function init() {
    const timer = setInterval(() => { if (patchUploadInput()) clearInterval(timer); }, 100);
    const observer = new MutationObserver(() => patchUploadInput());
    observer.observe(document.documentElement, {childList: true, subtree: true});
    patchUploadInput();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true}); else init();
})();
