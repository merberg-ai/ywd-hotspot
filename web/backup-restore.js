'use strict';
(() => {
  const el = id => document.getElementById(id);
  let importFile = null;
  let importB64 = null;

  function notify(message, bad = false) {
    try { if (typeof toast === 'function') return toast(message, bad); } catch (_) {}
    console[bad ? 'error' : 'log'](message);
  }
  function unlocked() { return !!el('logoutBtn') && !el('logoutBtn').hidden; }
  async function api(path, body) {
    const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body || {}), credentials:'same-origin'});
    let d = {}; try { d = await r.json(); } catch (_) {}
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    return d;
  }
  function bytesToB64(bytes) {
    let out = ''; const step = 0x8000;
    for (let i = 0; i < bytes.length; i += step) out += String.fromCharCode(...bytes.subarray(i, i + step));
    return btoa(out);
  }
  function b64ToBytes(text) {
    const raw = atob(text); const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  function download(filename, b64) {
    const blob = new Blob([b64ToBytes(b64)], {type:'application/octet-stream'});
    const url = URL.createObjectURL(blob); const a = document.createElement('a');
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }
  function previewText(p) {
    if (!p) return 'Backup preview unavailable.';
    const source = p.source || {};
    return [
      `Created: ${p.created_at || 'unknown'}`,
      `Source:  ${source.version || 'unknown'} · ${source.branch || 'unknown'} @ ${String(source.commit || 'unknown').slice(0,12)}`,
      `Station: ${p.callsign || '?'} · DMR ${p.dmr_id || '?'}`,
      `Radio:   ${p.frequency_mhz ?? '?'} MHz · CC${p.color_code ?? '?'}`,
      `BM:      ${p.brandmeister_master || 'unknown'}`,
      `Secrets: Hotspot ${p.hotspot_password_configured ? 'yes' : 'no'} · API ${p.bm_api_key_configured ? 'yes' : 'no'} · Web ${p.web_password_configured ? 'yes' : 'no'}`,
      `Plugins: ${p.plugins_installed || 0} installed · ${p.plugins_enabled || 0} enabled · ${p.plugin_configs || 0} configs · ${p.trust_keys || 0} trust keys`,
      `Wi-Fi:   ${p.wifi_included ? `included (${p.wifi_ssid || 'unknown'})` : 'not included'}`,
      `RF intent from backup: ${p.rf_autostart ? 'enabled at boot' : 'disabled at boot'}`,
    ].join('\n');
  }
  function closeModal() { el('backupModal')?.classList.remove('on'); }
  function setButtons() {
    const auth = unlocked();
    ['backupExport','backupImport'].forEach(id => { const x = el(id); if (x) x.disabled = !auth; });
  }
  function ensureUi() {
    const page = el('settings');
    if (!page || el('backupExport')) return;
    const history = el('historyRows')?.closest('article.card');
    const card = document.createElement('article');
    card.className = 'card backup-card';
    card.innerHTML = `
      <div class="card-title">BACKUP / RESTORE</div>
      <p class="hint">Create an encrypted portable appliance backup for a fresh YWD-Hotspot OS install, or restore one here. The file can contain RF, BrandMeister, WebUI credentials, calibration, plugin configuration/state and optional Wi-Fi credentials.</p>
      <div class="backup-summary"><div><span>Format</span><b>.ywdsettings v1</b></div><div><span>Protection</span><b>scrypt + AES-256 + HMAC</b></div><div><span>Restore</span><b>validated + transactional</b></div></div>
      <div class="backup-actions"><button class="btn primary" id="backupExport">EXPORT SETTINGS</button><button class="btn" id="backupImport">IMPORT SETTINGS</button></div>
      <input class="backup-file" id="backupFile" type="file" accept=".ywdsettings,application/octet-stream">
      <div class="notice backup-warning">Encrypted backups contain reusable secrets. Keep the file and its passphrase private. This dashboard uses trusted-LAN HTTP, so perform export/import only on a network you trust.</div>`;
    if (history) page.insertBefore(card, history); else page.appendChild(card);

    const modal = document.createElement('div');
    modal.className = 'modal'; modal.id = 'backupModal';
    modal.innerHTML = `<div class="dialog"><div class="dialog-head"><div><div class="kicker">YWD // MIGRATION</div><h3 id="backupModalTitle">SETTINGS BACKUP</h3></div><button class="btn ghost" id="backupClose" type="button">CLOSE</button></div><div class="backup-modal-grid"><div id="backupModalHint" class="hint"></div><div class="field"><label>BACKUP PASSPHRASE</label><input id="backupPass" type="password" autocomplete="new-password" minlength="10"></div><div class="field" id="backupPass2Row"><label>CONFIRM PASSPHRASE</label><input id="backupPass2" type="password" autocomplete="new-password" minlength="10"></div><label class="backup-check" id="backupWifiExportRow"><input id="backupWifiExport" type="checkbox"> Include current Wi-Fi profile when available</label><label class="backup-check" id="backupRfRow" hidden><input id="backupStartRf" type="checkbox"> Start RF after successful restore and enable RF at boot</label><label class="backup-check" id="backupWifiRestoreRow" hidden><input id="backupWifiRestore" type="checkbox"> Restore included Wi-Fi as a saved profile (do not switch live connection)</label><pre class="backup-preview" id="backupPreview" hidden></pre><div class="backup-actions"><button class="btn primary" id="backupGo" type="button">CONTINUE</button><button class="btn" id="backupCancel" type="button">CANCEL</button></div></div></div>`;
    document.body.appendChild(modal);

    el('backupClose').onclick = closeModal; el('backupCancel').onclick = closeModal;
    el('backupExport').onclick = openExport;
    el('backupImport').onclick = () => el('backupFile').click();
    el('backupFile').onchange = chooseImport;
    const logout = el('logoutBtn'); if (logout) new MutationObserver(setButtons).observe(logout,{attributes:true,attributeFilter:['hidden']});
    setButtons();
  }
  function resetModal() {
    el('backupPass').value = ''; el('backupPass2').value = ''; el('backupPreview').hidden = true; el('backupPreview').textContent = '';
    el('backupStartRf').checked = false; el('backupWifiRestore').checked = false;
  }
  function openExport() {
    resetModal();
    el('backupModalTitle').textContent = 'EXPORT ENCRYPTED SETTINGS';
    el('backupModalHint').textContent = 'Choose a passphrase you will still know after flashing the new SD card. The backup will not be recoverable without it.';
    el('backupPass2Row').hidden = false; el('backupWifiExportRow').hidden = false; el('backupRfRow').hidden = true; el('backupWifiRestoreRow').hidden = true;
    el('backupGo').textContent = 'CREATE BACKUP'; el('backupGo').onclick = doExport;
    el('backupModal').classList.add('on'); setTimeout(() => el('backupPass').focus(),50);
  }
  async function chooseImport() {
    const file = el('backupFile').files?.[0]; el('backupFile').value = '';
    if (!file) return;
    if (file.size <= 0 || file.size > 1536 * 1024) return notify('Settings backup is empty or exceeds the 1.5 MiB limit', true);
    importFile = file;
    const bytes = new Uint8Array(await file.arrayBuffer()); importB64 = bytesToB64(bytes);
    resetModal();
    el('backupModalTitle').textContent = 'IMPORT ENCRYPTED SETTINGS';
    el('backupModalHint').textContent = `${file.name} · ${(file.size/1024).toFixed(1)} KiB. Enter the backup passphrase to decrypt and verify it before anything is changed.`;
    el('backupPass2Row').hidden = true; el('backupWifiExportRow').hidden = true; el('backupRfRow').hidden = false; el('backupWifiRestoreRow').hidden = false;
    el('backupGo').textContent = 'DECRYPT & VERIFY'; el('backupGo').onclick = previewImport;
    el('backupModal').classList.add('on'); setTimeout(() => el('backupPass').focus(),50);
  }
  async function doExport() {
    const pass = el('backupPass').value, confirm = el('backupPass2').value;
    if (pass.length < 10) return notify('Use a backup passphrase of at least 10 characters', true);
    if (pass !== confirm) return notify('Backup passphrases do not match', true);
    const button = el('backupGo'); button.disabled = true; button.textContent = 'ENCRYPTING…';
    try {
      const d = await api('/api/settings/export',{passphrase:pass,include_wifi:!!el('backupWifiExport').checked});
      download(d.filename || 'ywd-hotspot-settings.ywdsettings', d.backup_b64);
      notify('Encrypted settings backup created'); closeModal();
    } catch (e) { notify(e.message,true); }
    finally { button.disabled=false; button.textContent='CREATE BACKUP'; }
  }
  async function previewImport() {
    const pass = el('backupPass').value;
    if (!importB64 || !importFile) return notify('Choose a .ywdsettings file first', true);
    if (pass.length < 10) return notify('Enter the backup passphrase', true);
    const button = el('backupGo'); button.disabled=true; button.textContent='VERIFYING…';
    try {
      const d = await api('/api/settings/preview',{backup_b64:importB64,passphrase:pass});
      el('backupPreview').textContent = previewText(d.preview); el('backupPreview').hidden=false;
      // The backup shows the prior RF intent, but every new restore starts with
      // a fresh explicit operator choice before RF can be enabled or started.
      el('backupStartRf').checked = false;
      el('backupWifiRestore').checked = !!d.preview?.wifi_included;
      button.textContent='RESTORE SETTINGS'; button.onclick=doImport;
      notify('Backup decrypted and authenticated');
    } catch (e) { notify(e.message,true); button.textContent='DECRYPT & VERIFY'; }
    finally { button.disabled=false; }
  }
  async function doImport() {
    const p = el('backupPreview').textContent || 'Verified backup';
    if (typeof window.ywdConfirm !== 'function') return notify('YWD confirmation UI is unavailable',true);
    const ok = await window.ywdConfirm({title:'RESTORE HOTSPOT SETTINGS',message:`Restore this verified backup?\n\n${p}\n\nCurrent protected settings will be snapshotted first. RF is forced off during restore and only started if the restore checkbox is selected.`,confirmText:'RESTORE SETTINGS',cancelText:'CANCEL',tone:'danger',kicker:'YWD // MIGRATION'});
    if (!ok) return;
    const button=el('backupGo'); button.disabled=true; button.textContent='RESTORING…';
    try {
      const d=await api('/api/settings/import',{backup_b64:importB64,passphrase:el('backupPass').value,start_rf:!!el('backupStartRf').checked,restore_wifi:!!el('backupWifiRestore').checked,first_boot:false});
      const warns=(d.warnings||[]).length; const missing=(d.missing_plugins||[]).length;
      notify(`Settings restored${warns?` · ${warns} warning(s)`:''}${missing?` · ${missing} missing plugin package(s)`:''}`);
      closeModal(); importB64=null; importFile=null;
      setTimeout(()=>location.reload(),1800);
    } catch(e){notify(e.message,true);button.disabled=false;button.textContent='RESTORE SETTINGS';}
  }
  function init(){ ensureUi(); }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
