'use strict';
(() => {
  const el = id => document.getElementById(id);
  let sshState = null;
  let busy = false;
  let busyAction = '';
  let policyDirty = false;

  function notify(message, bad = false) {
    try { if (typeof toast === 'function') return toast(message, bad); } catch (_) {}
    console[bad ? 'error' : 'log'](message);
  }
  function unlocked() { return !!el('logoutBtn') && !el('logoutBtn').hidden; }
  async function api(path, body) {
    const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body || {}), credentials:'same-origin', cache:'no-store'});
    let d = {}; try { d = await r.json(); } catch (_) {}
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    return d;
  }
  function download(filename, b64) {
    const raw = atob(String(b64 || '')); const bytes = new Uint8Array(raw.length);
    for (let i=0;i<raw.length;i++) bytes[i] = raw.charCodeAt(i);
    const url = URL.createObjectURL(new Blob([bytes], {type:'application/gzip'}));
    const a = document.createElement('a'); a.href=url; a.download=filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }
  function value(id, text) { const node = el(id); if (node) node.textContent = text; }
  function selectedUser() { return String(el('sshLoginUserSelect')?.value || '').trim(); }
  function selectedMode() { return el('sshAuthMode')?.value === 'password+key' ? 'password+key' : 'key-only'; }

  function syncSelectors(force = false) {
    const user = el('sshLoginUserSelect'); const mode = el('sshAuthMode');
    if (!user || !mode || !sshState) return;
    const users = Array.isArray(sshState.eligible_login_users) ? sshState.eligible_login_users : [];
    const desiredUser = sshState.login_user_exists ? sshState.login_user : sshState.suggested_login_user;
    const keepUser = !force && policyDirty ? user.value : desiredUser;
    user.replaceChildren(...users.map(name => { const o=document.createElement('option'); o.value=name; o.textContent=name; return o; }));
    if (users.includes(keepUser)) user.value = keepUser; else if (users.length) user.value = users[0];
    if (force || !policyDirty) mode.value = sshState.auth_mode === 'password+key' ? 'password+key' : 'key-only';
    const pw = el('sshPasswordBlock'); if (pw) pw.hidden = selectedMode() !== 'password+key';
  }

  function renderState() {
    const auth = unlocked(); const state = sshState || {}; const active=!!state.active; const enabled=!!state.enabled_at_boot;
    value('sshRuntimeState', sshState ? (active ? 'RUNNING' : 'STOPPED') : (auth ? 'CHECKING…' : 'LOCKED'));
    value('sshBootState', sshState ? (enabled ? 'ENABLED' : 'DISABLED') : '—');
    value('sshPort', sshState ? String(state.port || 22) : '22');
    value('sshPolicy', state.auth_mode === 'password+key' ? 'PASSWORD OR KEY' : 'KEY ONLY');
    value('sshLoginUser', state.login_user || '—');
    value('sshAuthorizedCount', sshState ? String(state.authorized_key_count ?? 0) : '—');
    value('sshPasswordState', sshState ? String(state.password_status || 'unknown').toUpperCase() : '—');
    syncSelectors(false);

    const badge=el('sshBadge'); if (badge) { badge.className='badge'; if(!auth) badge.textContent='LOCKED'; else if(!sshState) badge.textContent='CHECKING'; else if(active){badge.textContent='SSH ON';badge.classList.add('good');} else badge.textContent='SSH OFF'; }
    const users = Array.isArray(state.eligible_login_users) ? state.eligible_login_users : []; const haveUser = users.includes(selectedUser());
    const toggle=el('sshToggle'), apply=el('sshApplyPolicy'), create=el('sshClientCreate'), setPw=el('sshSetPassword'), user=el('sshLoginUserSelect'), mode=el('sshAuthMode');
    if (toggle) { toggle.disabled=!auth||busy||!sshState||(!active&&!haveUser); toggle.textContent=active?'DISABLE SSH ACCESS':'ENABLE SSH ACCESS'; toggle.className=active?'btn danger':'btn good'; }
    if (apply) { apply.disabled=!auth||busy||!active||!policyDirty||!haveUser; apply.textContent=active?'APPLY AUTHENTICATION':'USED WHEN SSH ENABLES'; }
    if (create) {
      const creating = busyAction === 'client-key';
      create.disabled=!auth||busy||!haveUser;
      create.classList.toggle('ywd-action-busy', creating);
      create.textContent=creating?'CREATING SSH CLIENT KEY…':'CREATE & EXPORT SSH CLIENT KEY';
      create.setAttribute('aria-busy', creating ? 'true' : 'false');
    }
    if (setPw) setPw.disabled=!auth||busy||!haveUser||selectedMode()!=='password+key';
    if (user) user.disabled=!auth||busy||users.length===0;
    if (mode) mode.disabled=!auth||busy||users.length===0;

    const note=el('sshAccessNote');
    if (note) {
      if (!auth) note.textContent='Unlock dashboard controls to view or change SSH access.';
      else if (!sshState) note.textContent='Reading SSH service state…';
      else if (!users.length) note.textContent='No eligible normal local login account was found. SSH cannot be enabled from the dashboard.';
      else if (!state.login_user_exists) note.textContent=`Configured SSH user ${state.login_user || 'ywd'} is missing. Choose an existing local user below; the missing-account issue is left untouched for later investigation.`;
      else if (active && state.auth_mode==='password+key') note.textContent=`SSH is listening for ${state.login_user}. Password or client-key login is accepted; root SSH remains disabled.`;
      else if (active) note.textContent=`SSH is listening for ${state.login_user} in key-only mode; password and root SSH login are disabled.`;
      else note.textContent='SSH is disabled. Choose the login user/authentication mode below; those selections are applied when SSH is enabled.';
    }
  }

  async function loadStatus() {
    if (!unlocked()) { sshState=null; renderState(); return; }
    try { sshState = await api('/api/ssh/status', {}); policyDirty=false; syncSelectors(true); }
    catch(e){ sshState=null; notify(e.message || 'Could not read SSH status.', true); }
    renderState();
  }

  async function configure(enabled, reapply = false) {
    if (!unlocked() || busy) return;
    const username=selectedUser(), mode=selectedMode();
    if (enabled && !username) return notify('No eligible SSH login user is available.', true);
    if (typeof window.ywdConfirm !== 'function') return notify('YWD confirmation UI is unavailable.', true);
    const authText = mode==='password+key' ? 'password OR a client key' : 'an authorized client key only';
    const ok = await window.ywdConfirm({
      title: reapply ? 'APPLY SSH AUTHENTICATION?' : (enabled ? 'ENABLE SSH ACCESS?' : 'DISABLE SSH ACCESS?'),
      kicker:'YWD // REMOTE ACCESS',
      message: reapply
        ? `Apply SSH login policy now?\n\nUser: ${username}\nAuthentication: ${authText}\n\nExisting SSH sessions may be affected while sshd reloads. Root SSH remains disabled.`
        : enabled
          ? `Enable SSH on TCP port 22?\n\nUser: ${username}\nAuthentication: ${authText}\n\nRoot SSH and keyboard-interactive authentication remain disabled.`
          : 'Disable SSH now and at boot?\n\nAuthorized client keys, the selected authentication policy, passwords, and server identity keys are preserved.',
      confirmText: reapply ? 'APPLY POLICY' : (enabled ? 'ENABLE SSH' : 'DISABLE SSH'), cancelText:'CANCEL', tone: enabled ? 'normal' : 'danger'
    });
    if (!ok) return;
    busy=true; renderState();
    try { sshState=await api('/api/ssh/configure', {enabled:!!enabled, auth_mode:mode, login_user:username}); policyDirty=false; syncSelectors(true); notify(sshState.message || 'SSH configuration updated'); }
    catch(e){ notify(e.message || 'Could not change SSH access.', true); await loadStatus(); }
    finally { busy=false; renderState(); }
  }

  async function setPassword() {
    if (!unlocked() || busy) return;
    const username=selectedUser(), p1=String(el('sshPassword')?.value || ''), p2=String(el('sshPasswordConfirm')?.value || '');
    if (!username) return notify('Choose an SSH login user first.', true);
    if (p1.length < 10) return notify('SSH password must be at least 10 characters.', true);
    if (p1 !== p2) return notify('SSH password confirmation does not match.', true);
    if (typeof window.ywdConfirm !== 'function') return notify('YWD confirmation UI is unavailable.', true);
    const ok=await window.ywdConfirm({title:'SET SSH LOGIN PASSWORD?',kicker:'YWD // REMOTE ACCESS',message:`Set/change the Linux login password for ${username}?\n\nThe password is sent only to the local privileged helper and is not returned, stored in YWD configuration, or written to diagnostics.`,confirmText:'SET PASSWORD',cancelText:'CANCEL',tone:'danger'});
    if (!ok) return;
    busy=true; renderState();
    try { const d=await api('/api/ssh/password',{username,password:p1}); el('sshPassword').value=''; el('sshPasswordConfirm').value=''; notify(d.message || `SSH password updated for ${username}`); await loadStatus(); }
    catch(e){ notify(e.message || 'Could not set SSH login password.', true); }
    finally { busy=false; renderState(); }
  }

  async function createClientKey() {
    if(!unlocked()||busy)return; const username=selectedUser(); if(!username)return notify('Choose an SSH login user first.',true);
    if(typeof window.ywdConfirm!=='function')return notify('YWD confirmation UI is unavailable.',true);
    const ok=await window.ywdConfirm({title:'CREATE & EXPORT SSH CLIENT KEY',kicker:'YWD // CLIENT ENROLLMENT',message:`Create a new Ed25519 SSH login key for ${username}?\n\nOnly the public key is retained on the hotspot. The private/public key archive is downloaded once; store it privately.`,confirmText:'CREATE & EXPORT KEY',cancelText:'CANCEL',tone:'danger'});
    if(!ok)return;busy=true;busyAction='client-key';renderState();
    try{const d=await api('/api/ssh-client-key/create',{username});if(!d.archive_b64)throw new Error('SSH client enrollment returned no key archive');download(d.filename||'ywd-hotspot-ssh-client-login.tar.gz',d.archive_b64);d.archive_b64='';notify(`SSH client login key created for ${username}${d.fingerprint?` · ${d.fingerprint}`:''}`);await loadStatus();}
    catch(e){notify(e.message||'Could not create SSH client login key.',true);}finally{busyAction='';busy=false;renderState();}
  }

  function canonicalSystemPage(){const pages=Array.from(document.querySelectorAll('section.page#system'));return pages.find(page=>page.querySelector('#rfToggle')||page.querySelector('#hostPowerCard')||page.querySelector('#dmridCard'))||null;}
  function cleanupDuplicateSystemShell(realPage){Array.from(document.querySelectorAll('.tabs [data-tab="system"]')).slice(1).forEach(tab=>tab.remove());Array.from(document.querySelectorAll('section.page#system')).forEach(page=>{if(page!==realPage)page.remove();});}
  function ensureUi(){
    const page=canonicalSystemPage();if(!page)return false;cleanupDuplicateSystemShell(page);if(el('sshAccessCard'))return true;
    const card=document.createElement('article');card.className='card';card.id='sshAccessCard';card.innerHTML=`
      <div class="card-title title-row"><span>SSH ACCESS</span><span id="sshBadge" class="badge">LOCKED</span></div>
      <p class="hint">Factory images still ship with SSH disabled. Key-only is recommended. Password-or-key login is an explicit LAN administration option; root SSH remains disabled.</p>
      <div class="backup-summary">
        <div><span>Server</span><b id="sshRuntimeState">LOCKED</b></div><div><span>At boot</span><b id="sshBootState">—</b></div>
        <div><span>Port</span><b id="sshPort">22</b></div><div><span>Policy</span><b id="sshPolicy">KEY ONLY</b></div>
        <div><span>Login user</span><b id="sshLoginUser">—</b></div><div><span>Authorized keys</span><b id="sshAuthorizedCount">—</b></div>
        <div><span>Password state</span><b id="sshPasswordState">—</b></div>
      </div>
      <div id="sshAccessNote" class="notice">Unlock dashboard controls to view or change SSH access.</div>
      <div class="formgrid">
        <div class="field"><label>SSH LOGIN USER</label><select id="sshLoginUserSelect"></select><small>Only normal local users (UID 1000+, interactive shell, /home directory) are offered.</small></div>
        <div class="field"><label>AUTHENTICATION</label><select id="sshAuthMode"><option value="key-only">Key only — recommended</option><option value="password+key">Password or key</option></select><small>Password mode keeps client-key login available as a recovery path.</small></div>
      </div>
      <div class="buttonrow wrap"><button class="btn" id="sshApplyPolicy" type="button">USED WHEN SSH ENABLES</button><button class="btn good" id="sshToggle" type="button">ENABLE SSH ACCESS</button></div>
      <div id="sshPasswordBlock" class="field" hidden><hr><label>SSH LOGIN PASSWORD</label><div class="formgrid"><div class="field"><input id="sshPassword" type="password" autocomplete="new-password" minlength="10" maxlength="128" placeholder="New password"></div><div class="field"><input id="sshPasswordConfirm" type="password" autocomplete="new-password" minlength="10" maxlength="128" placeholder="Confirm password"></div></div><div class="buttonrow wrap"><button class="btn" id="sshSetPassword" type="button">SET / CHANGE PASSWORD</button></div><div class="hint">The password changes the selected Linux account. It is not stored in YWD configuration or returned by the API.</div></div>
      <hr><div class="buttonrow ssh-client-key-row"><button class="btn" id="sshClientCreate" type="button" aria-busy="false">CREATE & EXPORT SSH CLIENT KEY</button></div>
      <div class="hint">Creates a new Ed25519 SSH login key for the selected user. The private/public key archive is downloaded once; only the public key is retained on the hotspot.</div>`;
    const runtime=page.querySelector('#rfToggle')?.closest('article.card');const grid=runtime?.parentElement;const hostPower=page.querySelector('#hostPowerCard');
    if(grid&&hostPower?.parentElement===grid)grid.insertBefore(card,hostPower);else if(grid)grid.appendChild(card);else page.appendChild(card);
    el('sshToggle').onclick=()=>configure(!sshState?.active,false);el('sshApplyPolicy').onclick=()=>configure(true,true);el('sshSetPassword').onclick=setPassword;el('sshClientCreate').onclick=createClientKey;
    [el('sshLoginUserSelect'),el('sshAuthMode')].forEach(node=>node?.addEventListener('change',()=>{policyDirty=true;const pw=el('sshPasswordBlock');if(pw)pw.hidden=selectedMode()!=='password+key';renderState();}));
    const logout=el('logoutBtn');if(logout)new MutationObserver(()=>{renderState();loadStatus();}).observe(logout,{attributes:true,attributeFilter:['hidden']});
    renderState();loadStatus();return true;
  }
  function init(){if(ensureUi())return;let tries=0;const timer=setInterval(()=>{tries+=1;if(ensureUi()||tries>=160)clearInterval(timer);},50);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();