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
    const auth = unlocked();
    ['sshKeysExport','sshClientCreate'].forEach(id => {
      const button = el(id);
      if (button) button.disabled = !auth;
    });
  }

  async function exportServerIdentity() {
    if (!unlocked()) return notify('Unlock dashboard controls before exporting SSH server identity keys.', true);
    if (typeof window.ywdConfirm !== 'function') return notify('YWD confirmation UI is unavailable.', true);

    const ok = await window.ywdConfirm({
      title: 'EXPORT SSH SERVER IDENTITY KEYS',
      kicker: 'YWD // RECOVERY BACKUP',
      message: 'Export this hotspot’s SSH SERVER identity keys?\n\nRecovery only: these preserve the server fingerprint after a rebuild and CANNOT be used by andFTP or another SSH client to log in.\n\nThe archive contains private server identity keys and is not encrypted. Export only over a trusted LAN and store it securely.',
      confirmText: 'EXPORT SERVER IDENTITY',
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
      if (!d.archive_b64) throw new Error('SSH server identity export returned no archive');
      download(d.filename || 'ywd-hotspot-ssh-server-identity.tar.gz', d.archive_b64);
      const count = Array.isArray(d.files) ? d.files.length : 0;
      d.archive_b64 = '';
      notify(`SSH server identity archive created${count ? ` · ${count} key file(s)` : ''}`);
    } catch (e) {
      notify(e.message || 'Could not export SSH server identity keys.', true);
    } finally {
      if (button) {
        button.classList.remove('ywd-working');
        button.textContent = 'EXPORT SSH SERVER IDENTITY KEYS';
      }
      setButtonState();
    }
  }

  async function createClientKey() {
    if (!unlocked()) return notify('Unlock dashboard controls before creating an SSH client login key.', true);
    const username = String(el('sshClientUser')?.value || '').trim();
    if (!/^[a-z_][a-z0-9_-]{0,31}$/.test(username)) {
      el('sshClientUser')?.focus();
      return notify('Enter the normal Linux username you want the client key to log in as.', true);
    }
    if (typeof window.ywdConfirm !== 'function') return notify('YWD confirmation UI is unavailable.', true);

    const ok = await window.ywdConfirm({
      title: 'CREATE SSH CLIENT LOGIN KEY',
      kicker: 'YWD // CLIENT ENROLLMENT',
      message: `Create a new Ed25519 login key for local user ${username}?\n\nThe public key will be added to that user’s authorized_keys. The private key will be downloaded once and NOT retained by YWD-Hotspot.\n\nThe downloaded private key is unencrypted. Anyone who obtains it can log in as ${username} until you revoke its authorized_keys entry.`,
      confirmText: 'CREATE & DOWNLOAD KEY',
      cancelText: 'CANCEL',
      tone: 'danger',
    });
    if (!ok) return;

    const button = el('sshClientCreate');
    if (button) {
      button.disabled = true;
      button.classList.add('ywd-working');
      button.textContent = 'CREATING…';
    }
    try {
      const d = await api('/api/ssh-client-key/create', {username});
      if (!d.archive_b64) throw new Error('SSH client enrollment returned no key archive');
      download(d.filename || 'ywd-hotspot-ssh-client-login.tar.gz', d.archive_b64);
      d.archive_b64 = '';
      notify(`SSH client login key created for ${username}${d.fingerprint ? ` · ${d.fingerprint}` : ''}`);
    } catch (e) {
      notify(e.message || 'Could not create SSH client login key.', true);
    } finally {
      if (button) {
        button.classList.remove('ywd-working');
        button.textContent = 'CREATE & EXPORT CLIENT LOGIN KEY';
      }
      setButtonState();
    }
  }

  function ensureUi() {
    if (el('sshKeysExport') && el('sshClientCreate')) {
      setButtonState();
      return true;
    }
    const settingsExport = el('backupExport');
    const actions = settingsExport?.closest('.backup-actions');
    if (!actions) return false;

    if (!el('sshKeysExport')) {
      const server = document.createElement('button');
      server.className = 'btn';
      server.id = 'sshKeysExport';
      server.type = 'button';
      server.textContent = 'EXPORT SSH SERVER IDENTITY KEYS';
      server.title = 'Recovery backup only. These preserve the SSH server fingerprint and cannot be used to log in.';
      server.onclick = exportServerIdentity;
      actions.appendChild(server);
    }

    if (!el('sshKeyHelp')) {
      const help = document.createElement('div');
      help.id = 'sshKeyHelp';
      help.className = 'hint';
      help.innerHTML = '<b>SSH keys:</b> Server identity keys are recovery-only. To configure andFTP/SFTP without a password, create a separate client login key below.';
      actions.insertAdjacentElement('afterend', help);
    }

    if (!el('sshClientEnroll')) {
      const block = document.createElement('div');
      block.id = 'sshClientEnroll';
      block.className = 'field';
      block.innerHTML = `
        <label>SSH / SFTP CLIENT LOGIN</label>
        <div class="lookup-row">
          <input id="sshClientUser" autocomplete="username" autocapitalize="none" spellcheck="false" maxlength="32" placeholder="Linux username">
          <button class="btn" id="sshClientCreate" type="button">CREATE & EXPORT CLIENT LOGIN KEY</button>
        </div>
        <div class="hint">Creates a fresh Ed25519 client key, adds only its public key to the selected normal user’s authorized_keys, downloads the private/public pair once, then discards the private key from the hotspot.</div>`;
      el('sshKeyHelp').insertAdjacentElement('afterend', block);
      el('sshClientCreate').onclick = createClientKey;
    }

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
