'use strict';
(() => {
  const el = id => document.getElementById(id);
  let sshState = null;
  let busy = false;

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

  function value(id, text) {
    const node = el(id);
    if (node) node.textContent = text;
  }

  function renderState() {
    const auth = unlocked();
    const state = sshState || {};
    const active = !!state.active;
    const enabled = !!state.enabled_at_boot;

    value('sshRuntimeState', sshState ? (active ? 'RUNNING' : 'STOPPED') : (auth ? 'CHECKING…' : 'LOCKED'));
    value('sshBootState', sshState ? (enabled ? 'ENABLED' : 'DISABLED') : '—');
    value('sshPort', sshState ? String(state.port || 22) : '22');
    value('sshPolicy', 'PUBLIC KEY ONLY');
    value('sshLoginUser', state.login_user || 'ywd');
    value('sshAuthorizedCount', sshState ? String(state.authorized_key_count ?? 0) : '—');

    const badge = el('sshBadge');
    if (badge) {
      badge.className = 'badge';
      if (!auth) {
        badge.textContent = 'LOCKED';
      } else if (!sshState) {
        badge.textContent = 'CHECKING';
      } else if (active) {
        badge.textContent = 'SSH ON';
        badge.classList.add('good');
      } else {
        badge.textContent = 'SSH OFF';
      }
    }

    const enable = el('sshEnable');
    const disable = el('sshDisable');
    const create = el('sshClientCreate');
    const exportBtn = el('sshKeysExport');
    if (enable) enable.disabled = !auth || busy || active;
    if (disable) disable.disabled = !auth || busy || !active;
    if (create) create.disabled = !auth || busy;
    if (exportBtn) exportBtn.disabled = !auth || busy;

    const note = el('sshAccessNote');
    if (note) {
      if (!auth) note.textContent = 'Unlock dashboard controls to view or change SSH access.';
      else if (!sshState) note.textContent = 'Reading SSH service state…';
      else if (active) note.textContent = 'SSH is listening on the LAN. Password authentication and root SSH login are disabled.';
      else note.textContent = 'SSH is disabled. Existing client keys are preserved and can be used again after SSH is enabled.';
    }
  }

  async function loadStatus() {
    if (!unlocked()) {
      sshState = null;
      renderState();
      return;
    }
    try {
      sshState = await api('/api/ssh/status', {});
    } catch (e) {
      sshState = null;
      notify(e.message || 'Could not read SSH status.', true);
    }
    renderState();
  }

  async function configure(enabled) {
    if (!unlocked() || busy) return;
    if (typeof window.ywdConfirm !== 'function') return notify('YWD confirmation UI is unavailable.', true);
    const ok = await window.ywdConfirm({
      title: enabled ? 'ENABLE SSH ACCESS?' : 'DISABLE SSH ACCESS?',
      kicker: 'YWD // REMOTE ACCESS',
      message: enabled
        ? 'Enable the SSH server on TCP port 22?\n\nYWD will enforce public-key-only authentication. SSH passwords and root SSH login remain disabled. Only users with an authorized client key can log in.'
        : 'Disable the SSH server now and at boot?\n\nExisting authorized client keys and server identity keys will be preserved so SSH can be safely re-enabled later.',
      confirmText: enabled ? 'ENABLE SSH' : 'DISABLE SSH',
      cancelText: 'CANCEL',
      tone: enabled ? 'normal' : 'danger',
    });
    if (!ok) return;

    busy = true;
    renderState();
    try {
      sshState = await api('/api/ssh/configure', {enabled: !!enabled});
      notify(sshState.message || (enabled ? 'SSH enabled' : 'SSH disabled'));
    } catch (e) {
      notify(e.message || 'Could not change SSH access.', true);
      await loadStatus();
    } finally {
      busy = false;
      renderState();
    }
  }

  async function exportServerIdentity() {
    if (!unlocked()) return notify('Unlock dashboard controls before exporting SSH server identity keys.', true);
    if (typeof window.ywdConfirm !== 'function') return notify('YWD confirmation UI is unavailable.', true);

    const ok = await window.ywdConfirm({
      title: 'EXPORT SSH SERVER IDENTITY KEYS',
      kicker: 'YWD // RECOVERY BACKUP',
      message: 'Export this hotspot’s SSH SERVER identity keys?\n\nRecovery only: these preserve the server fingerprint after a rebuild and CANNOT be used by PuTTY or another SSH client to log in.\n\nThe archive contains private server identity keys and is not encrypted. Export only over a trusted LAN and store it securely.',
      confirmText: 'EXPORT SERVER IDENTITY',
      cancelText: 'CANCEL',
      tone: 'danger',
    });
    if (!ok) return;

    busy = true;
    const button = el('sshKeysExport');
    if (button) { button.classList.add('ywd-working'); button.textContent = 'EXPORTING…'; }
    renderState();
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
      busy = false;
      if (button) { button.classList.remove('ywd-working'); button.textContent = 'EXPORT SERVER IDENTITY'; }
      renderState();
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
      message: `Create a new Ed25519 login key for local user ${username}?\n\nThe public key will be added to that user’s authorized_keys. The private key will be downloaded once and NOT retained by YWD-Hotspot.\n\nCreating a key does not itself enable SSH; use ENABLE SSH ACCESS when you are ready to open port 22.`,
      confirmText: 'CREATE & DOWNLOAD KEY',
      cancelText: 'CANCEL',
      tone: 'danger',
    });
    if (!ok) return;

    busy = true;
    const button = el('sshClientCreate');
    if (button) { button.classList.add('ywd-working'); button.textContent = 'CREATING…'; }
    renderState();
    try {
      const d = await api('/api/ssh-client-key/create', {username});
      if (!d.archive_b64) throw new Error('SSH client enrollment returned no key archive');
      download(d.filename || 'ywd-hotspot-ssh-client-login.tar.gz', d.archive_b64);
      d.archive_b64 = '';
      notify(`SSH client login key created for ${username}${d.fingerprint ? ` · ${d.fingerprint}` : ''}`);
      if (d.ssh) sshState = d.ssh;
      else await loadStatus();
    } catch (e) {
      notify(e.message || 'Could not create SSH client login key.', true);
    } finally {
      busy = false;
      if (button) { button.classList.remove('ywd-working'); button.textContent = 'CREATE & EXPORT CLIENT KEY'; }
      renderState();
    }
  }

  function ensureUi() {
    const page = el('settings');
    if (!page) return false;
    if (el('sshAccessCard')) return true;

    const backup = page.querySelector('.backup-card');
    if (!backup) return false;

    const card = document.createElement('article');
    card.className = 'card';
    card.id = 'sshAccessCard';
    card.innerHTML = `
      <div class="card-title title-row"><span>SSH ACCESS</span><span id="sshBadge" class="badge">LOCKED</span></div>
      <p class="hint">Factory images ship with SSH disabled. Enable it here only when remote shell/SFTP access is needed. YWD always enforces public-key-only authentication; password SSH and root SSH login are disabled.</p>
      <div class="backup-summary">
        <div><span>Server</span><b id="sshRuntimeState">LOCKED</b></div>
        <div><span>At boot</span><b id="sshBootState">—</b></div>
        <div><span>Port</span><b id="sshPort">22</b></div>
        <div><span>Policy</span><b id="sshPolicy">PUBLIC KEY ONLY</b></div>
        <div><span>Login user</span><b id="sshLoginUser">ywd</b></div>
        <div><span>Authorized keys</span><b id="sshAuthorizedCount">—</b></div>
      </div>
      <div id="sshAccessNote" class="notice">Unlock dashboard controls to view or change SSH access.</div>
      <div class="buttonrow wrap">
        <button class="btn good" id="sshEnable" type="button">ENABLE SSH ACCESS</button>
        <button class="btn danger" id="sshDisable" type="button">DISABLE SSH ACCESS</button>
      </div>
      <hr>
      <div class="field">
        <label>SSH / SFTP CLIENT LOGIN KEY</label>
        <div class="lookup-row">
          <input id="sshClientUser" autocomplete="username" autocapitalize="none" spellcheck="false" maxlength="32" value="ywd" placeholder="Linux username">
          <button class="btn" id="sshClientCreate" type="button">CREATE & EXPORT CLIENT KEY</button>
        </div>
        <div class="hint">Creates a fresh Ed25519 client key, installs only its public half in authorized_keys, downloads the private/public pair once, then discards the private key from the hotspot.</div>
      </div>
      <div class="buttonrow wrap"><button class="btn" id="sshKeysExport" type="button">EXPORT SERVER IDENTITY</button></div>
      <div class="hint">Server identity export is recovery-only and cannot be used as a client login key.</div>`;
    backup.insertAdjacentElement('afterend', card);

    el('sshEnable').onclick = () => configure(true);
    el('sshDisable').onclick = () => configure(false);
    el('sshClientCreate').onclick = createClientKey;
    el('sshKeysExport').onclick = exportServerIdentity;

    const logout = el('logoutBtn');
    if (logout) new MutationObserver(() => { renderState(); loadStatus(); }).observe(logout, {attributes: true, attributeFilter: ['hidden']});
    renderState();
    loadStatus();
    return true;
  }

  function init() {
    if (ensureUi()) return;
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (ensureUi() || tries >= 80) clearInterval(timer);
    }, 50);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
