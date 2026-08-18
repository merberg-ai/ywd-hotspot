'use strict';
(() => {
  const el = id => document.getElementById(id);

  function notify(message, bad = false) {
    try { if (typeof toast === 'function') return toast(message, bad); } catch (_) {}
    console[bad ? 'error' : 'log'](message);
  }

  function unlocked() {
    return !!el('logoutBtn') && !el('logoutBtn').hidden;
  }

  async function api(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {}),
      credentials: 'same-origin',
      cache: 'no-store',
    });
    let d = {};
    try { d = await r.json(); } catch (_) {}
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    return d;
  }

  function download(filename, b64) {
    const raw = atob(String(b64 || ''));
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const blob = new Blob([bytes], {type: 'application/gzip'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  function setButtonState() {
    const button = el('sshKeysExport');
    if (button) button.disabled = !unlocked();
  }

  async function exportKeys() {
    if (!unlocked()) return notify('Unlock dashboard controls before exporting SSH host keys.', true);
    if (typeof window.ywdConfirm !== 'function') return notify('YWD confirmation UI is unavailable.', true);

    const ok = await window.ywdConfirm({
      title: 'EXPORT SSH HOST KEYS',
      kicker: 'YWD // SENSITIVE BACKUP',
      message: 'Export this hotspot’s SSH host identity keys?\n\nThe archive contains PRIVATE host keys and is NOT encrypted or included in the normal .ywdsettings backup. Anyone who obtains these private keys may be able to impersonate this SSH server. Export only over a trusted LAN and store the archive securely.',
      confirmText: 'EXPORT SSH KEYS',
      cancelText: 'CANCEL',
      tone: 'danger',
    });
    if (!ok) return;

    const button = el('sshKeysExport');
    if (button) {
      button.disabled = true;
      button.classList.add('ywd-working');
      button.textContent = 'EXPORTING…';
    }
    try {
      const d = await api('/api/ssh-keys/export', {});
      if (!d.archive_b64) throw new Error('SSH key export returned no archive');
      download(d.filename || 'ywd-hotspot-ssh-host-keys.tar.gz', d.archive_b64);
      const count = Array.isArray(d.files) ? d.files.length : 0;
      d.archive_b64 = '';
      notify(`SSH host key archive created${count ? ` · ${count} key file(s)` : ''}`);
    } catch (e) {
      notify(e.message || 'Could not export SSH host keys.', true);
    } finally {
      if (button) {
        button.classList.remove('ywd-working');
        button.textContent = 'EXPORT SSH HOST KEYS';
      }
      setButtonState();
    }
  }

  function ensureUi() {
    if (el('sshKeysExport')) {
      setButtonState();
      return true;
    }
    const settingsExport = el('backupExport');
    const actions = settingsExport?.closest('.backup-actions');
    if (!actions) return false;

    const button = document.createElement('button');
    button.className = 'btn';
    button.id = 'sshKeysExport';
    button.type = 'button';
    button.textContent = 'EXPORT SSH HOST KEYS';
    button.title = 'Exports private/public OpenSSH host identity keys. Requires unlocked dashboard controls.';
    button.onclick = exportKeys;
    actions.appendChild(button);

    const logout = el('logoutBtn');
    if (logout) new MutationObserver(setButtonState).observe(logout, {attributes: true, attributeFilter: ['hidden']});
    setButtonState();
    return true;
  }

  function init() {
    if (ensureUi()) return;
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (ensureUi() || tries >= 40) clearInterval(timer);
    }, 50);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
