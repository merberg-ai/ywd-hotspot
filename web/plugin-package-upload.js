'use strict';
(() => {
  const el = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function notify(message,bad=false){try{if(typeof toast==='function')return toast(message,bad);}catch(_){}console[bad?'error':'log'](message);}
  function unlocked(){return !!el('logoutBtn')&&!el('logoutBtn').hidden;}
  async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{}),credentials:'same-origin'});let d={};try{d=await r.json();}catch(_){}if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d;}
  function bytesToB64(bytes){let out='';for(let i=0;i<bytes.length;i+=0x8000)out+=String.fromCharCode(...bytes.subarray(i,i+0x8000));return btoa(out);}
  function refreshLocks(){const auth=unlocked();const upload=el('pluginUploadButton');if(upload&&!upload.dataset.pluginBusy)upload.disabled=!auth;document.querySelectorAll('#plugins [data-plugin-action="package-remove"]').forEach(button=>{button.disabled=!auth||button.dataset.pluginBusy==='1';});}

  function patchRenderer(){
    const base=window.ywdPluginCardRenderer;if(!base||base.__alpha226)return;
    const original=base.pluginCard.bind(base);
    base.pluginCard=(plugin,systemEnabled,utils={})=>{
      let html=original(plugin,systemEnabled,utils);
      const origin=plugin.package_origin||'builtin',sig=plugin.signature||{};
      const sigText=sig.status==='verified'?`VERIFIED · ${sig.key_id||'trusted key'}`:sig.status==='unsigned'?'UNSIGNED':sig.status==='builtin'?'YWD CORE':'UNKNOWN';
      const meta=`<div class="plugin-meta plugin-package-trust"><div><span>Source</span><b>${origin==='uploaded'?'UPLOADED':'BUILT-IN'}</b></div><div><span>Signature</span><b>${esc(sigText)}</b></div></div>`;
      html=html.replace('<div class="plugin-caps">',meta+'<div class="plugin-caps">');
      if(origin==='uploaded'&&!plugin.installed){
        const action=`<div class="buttonrow wrap plugin-remove-source"><button class="btn danger" data-plugin-action="package-remove" data-plugin-id="${String(plugin.id).replace(/[^a-z0-9-]/g,'')}"${unlocked()?'':' disabled'}>REMOVE PACKAGE</button></div>`;
        html=html.replace('<div id="pluginResult-',action+'<div id="pluginResult-');
      }
      queueMicrotask(refreshLocks);
      return html;
    };
    base.__alpha226=true;
  }

  function patchPackageActions(){
    const base=window.ywdPluginPackageUi;if(!base||base.__alpha226)return;
    const original=base.handle.bind(base);
    base.handle=async(action,ctx)=>{
      if(action!=='package-remove')return original(action,ctx);
      if(!unlocked())throw new Error('Unlock controls before removing a plugin package.');
      const plugin=(ctx.pluginState?.plugins||[]).find(p=>p.id===ctx.id);
      const ok=await ctx.confirmYwd({title:'REMOVE UPLOADED PACKAGE',message:`Permanently remove the uploaded package source for ${plugin?.name||ctx.id}?\n\nThe plugin must already be uninstalled. Saved configuration/data are not removed by this action. Use REMOVE DATA separately if you want those erased too.`,confirmText:'REMOVE PACKAGE',cancelText:'CANCEL',tone:'danger',kicker:'YWD // PLUGINS'});
      if(!ok)return true;
      const done=ctx.beginBusy(ctx.button,'REMOVING…');ctx.button.dataset.pluginBusy='1';
      try{await post('/api/plugins/package-remove',{id:ctx.id});ctx.notify(`${ctx.id} package removed`);setTimeout(()=>document.querySelector('[data-tab="plugins"]')?.click(),250);}finally{delete ctx.button.dataset.pluginBusy;done();refreshLocks();}
      return true;
    };
    base.__alpha226=true;
  }

  function kindText(plugin){
    const kind=String(plugin?.kind||'').toLowerCase();
    if(kind==='ui')return 'Browser UI plugin';
    if(kind==='service')return 'Sandboxed service plugin';
    if(kind==='declarative')return 'Declarative plugin';
    return kind||'Unknown plugin type';
  }

  function ensureReviewModal(){
    if(el('pluginInstallReviewModal'))return el('pluginInstallReviewModal');
    const modal=document.createElement('div');
    modal.className='modal';modal.id='pluginInstallReviewModal';
    modal.innerHTML=`<div class="dialog plugin-install-dialog" role="dialog" aria-modal="true" aria-labelledby="pluginInstallReviewTitle">
      <div class="card-title title-row"><span id="pluginInstallReviewTitle">PLUGIN PACKAGE REVIEW</span><span class="badge" id="pluginInstallReviewBadge">WORKING</span></div>
      <div class="plugin-install-steps">
        <div data-plugin-stage="upload"><span>PACKAGE UPLOAD</span><b>COMPLETE</b></div>
        <div data-plugin-stage="verify"><span>ARCHIVE + SIGNATURE VERIFICATION</span><b>WORKING…</b></div>
        <div data-plugin-stage="ready"><span>INSTALL REVIEW</span><b>WAITING</b></div>
      </div>
      <div id="pluginInstallReviewMessage" class="notice">Validating the uploaded package…</div>
      <div id="pluginInstallReviewDetails" class="plugin-install-details" hidden></div>
      <div id="pluginInstallReviewCaps" class="plugin-caps" hidden></div>
      <div class="buttonrow plugin-install-review-actions">
        <button class="btn" id="pluginInstallCancel" disabled>CANCEL</button>
        <button class="btn primary" id="pluginInstallConfirm" hidden>INSTALL PLUGIN</button>
      </div>
    </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click',e=>{if(e.target===modal&&!el('pluginInstallCancel')?.disabled)modal.classList.remove('on');});
    el('pluginInstallCancel').onclick=()=>modal.classList.remove('on');
    return modal;
  }

  function stage(name,text,state=''){
    const row=document.querySelector(`[data-plugin-stage="${name}"]`);if(!row)return;
    row.className=state;const value=row.querySelector('b');if(value)value.textContent=text;
  }

  function showVerifying(){
    const modal=ensureReviewModal();
    stage('upload','COMPLETE','good');stage('verify','WORKING…','working');stage('ready','WAITING','');
    el('pluginInstallReviewBadge').textContent='VERIFYING';
    el('pluginInstallReviewBadge').className='badge warn';
    el('pluginInstallReviewMessage').className='notice';
    el('pluginInstallReviewMessage').textContent='The hotspot is validating the archive manifest, hashes, package policy, and signature trust.';
    el('pluginInstallReviewDetails').hidden=true;el('pluginInstallReviewCaps').hidden=true;
    el('pluginInstallConfirm').hidden=true;el('pluginInstallCancel').disabled=true;el('pluginInstallCancel').textContent='CANCEL';
    modal.classList.add('on');
  }

  function showReview(data){
    const modal=ensureReviewModal();
    const plugin=(data?.plugins_state?.plugins||[]).find(p=>p.id===data.id)||{};
    const sig=plugin.signature||data.signature||{};
    const signature=sig.status==='verified'?`Verified${sig.key_id?` · ${sig.key_id}`:''}`:String(sig.status||'unknown').toUpperCase();
    stage('verify',sig.status==='verified'||plugin.kind==='declarative'?'PASS':'CHECKED','good');stage('ready','READY','good');
    el('pluginInstallReviewBadge').textContent='READY';el('pluginInstallReviewBadge').className='badge applied';
    el('pluginInstallReviewMessage').className='notice plugin-good';
    el('pluginInstallReviewMessage').textContent='Package verification passed. Review the plugin details before installing it.';
    const details=el('pluginInstallReviewDetails');details.hidden=false;
    details.innerHTML=`
      <div class="plugin-install-name"><strong>${esc(plugin.name||data.id)}</strong><span>${esc(data.id)} · v${esc(plugin.version||'unknown')}</span></div>
      <p>${esc(plugin.description||'No plugin description was provided.')}</p>
      <div class="plugin-meta">
        <div><span>Type</span><b>${esc(kindText(plugin))}</b></div>
        <div><span>Trust</span><b>${esc(plugin.trust||'experimental')}</b></div>
        <div><span>Signature</span><b>${esc(signature)}</b></div>
        <div><span>RF ownership</span><b>${plugin.rf_mode?'YES':'NO'}</b></div>
        <div><span>Provider</span><b>${esc(plugin.provider||'—')}</b></div>
        <div><span>Service</span><b>${esc(plugin.service||'none')}</b></div>
      </div>`;
    const caps=el('pluginInstallReviewCaps'),items=Array.isArray(plugin.capabilities)?plugin.capabilities:[];
    caps.hidden=false;caps.innerHTML=items.length?items.map(x=>`<span class="plugin-cap">${esc(x)}</span>`).join(''):'<span class="plugin-cap">no capabilities</span>';
    const install=el('pluginInstallConfirm'),cancel=el('pluginInstallCancel');
    cancel.disabled=false;cancel.textContent='CANCEL';install.hidden=false;install.disabled=false;install.textContent='INSTALL PLUGIN';
    install.onclick=async()=>{
      install.disabled=true;cancel.disabled=true;install.classList.add('ywd-working');install.setAttribute('aria-busy','true');install.textContent='INSTALLING…';
      stage('ready','INSTALLING…','working');
      try{
        await post('/api/plugins/install',{id:data.id});
        stage('ready','INSTALLED','good');el('pluginInstallReviewBadge').textContent='INSTALLED';el('pluginInstallReviewBadge').className='badge applied';
        el('pluginInstallReviewMessage').textContent='Plugin installed successfully. It remains disabled until you explicitly enable it.';
        notify(`${data.id} installed — remains disabled`);
        setTimeout(()=>{modal.classList.remove('on');document.querySelector('[data-tab="plugins"]')?.click();},700);
      }catch(e){stage('ready','FAILED','bad');el('pluginInstallReviewBadge').textContent='FAILED';el('pluginInstallReviewBadge').className='badge pending';el('pluginInstallReviewMessage').className='notice plugin-warning';el('pluginInstallReviewMessage').textContent=e.message;notify(e.message,true);cancel.disabled=false;install.disabled=false;install.textContent='TRY INSTALL AGAIN';}
      finally{install.classList.remove('ywd-working');install.removeAttribute('aria-busy');}
    };
    modal.classList.add('on');
  }

  function showReviewError(message){
    const modal=ensureReviewModal();stage('verify','FAILED','bad');stage('ready','BLOCKED','bad');
    el('pluginInstallReviewBadge').textContent='REJECTED';el('pluginInstallReviewBadge').className='badge pending';
    el('pluginInstallReviewMessage').className='notice plugin-warning';el('pluginInstallReviewMessage').textContent=message;
    el('pluginInstallReviewDetails').hidden=true;el('pluginInstallReviewCaps').hidden=true;el('pluginInstallConfirm').hidden=true;
    el('pluginInstallCancel').disabled=false;el('pluginInstallCancel').textContent='CLOSE';modal.classList.add('on');
  }

  function uploadWithProgress(body,onProgress,onUploaded){
    return new Promise((resolve,reject)=>{
      const xhr=new XMLHttpRequest();xhr.open('POST','/api/plugins/upload',true);xhr.withCredentials=true;xhr.setRequestHeader('Content-Type','application/json');
      xhr.upload.onprogress=e=>{if(e.lengthComputable)onProgress(Math.max(0,Math.min(100,Math.round((e.loaded/e.total)*100))));};
      xhr.upload.onload=()=>{onProgress(100);onUploaded();};
      xhr.onerror=()=>reject(new Error('Plugin upload failed before the hotspot responded.'));
      xhr.onload=()=>{let d={};try{d=JSON.parse(xhr.responseText||'{}');}catch(_){}if(xhr.status<200||xhr.status>=300)return reject(new Error(d.error||`HTTP ${xhr.status}`));resolve(d);};
      xhr.send(JSON.stringify(body));
    });
  }

  function setUploadProgress(percent,active=true){
    const wrap=el('pluginUploadProgress'),bar=el('pluginUploadProgressBar'),label=el('pluginUploadProgressText');if(!wrap||!bar||!label)return;
    wrap.hidden=!active;bar.style.width=`${percent}%`;label.textContent=`${percent}%`;
  }

  function ensureUploadUi(){
    const page=el('plugins');if(!page||el('pluginUploadButton'))return false;
    const managerCard=page.querySelector('.card:nth-of-type(2)')||page.querySelector('.card');
    const card=document.createElement('article');card.className='card plugin-upload-card';
    card.innerHTML=`<div class="card-title title-row"><span>UPLOAD PLUGIN PACKAGE</span><span class="hint">.ywdplugin v1</span></div><p class="plugin-api-note">Choose a package to upload and verify. Installation requires a separate confirmation after the hotspot shows the package identity, type, capabilities, and signature status.</p><div class="buttonrow wrap"><button class="btn primary" id="pluginUploadButton">UPLOAD .YWDPLUGIN</button><input id="pluginUploadFile" type="file" accept=".ywdplugin,application/zip" hidden></div><div class="plugin-upload-progress" id="pluginUploadProgress" hidden><div class="plugin-upload-track"><span id="pluginUploadProgressBar"></span></div><span id="pluginUploadProgressText">0%</span></div><div id="pluginUploadStatus" class="hint">Maximum archive size: 1 MiB. Uploaded packages are verified before they become installable.</div>`;
    if(managerCard?.parentElement)managerCard.parentElement.insertBefore(card,managerCard.nextSibling);else page.prepend(card);
    const file=el('pluginUploadFile'),button=el('pluginUploadButton');
    button.onclick=()=>{if(unlocked())file.click();};
    file.onchange=async()=>{
      const f=file.files?.[0];file.value='';if(!f)return;if(!unlocked())return notify('Unlock controls before uploading a plugin package.',true);if(f.size<=0||f.size>1024*1024)return notify('Plugin archive is empty or exceeds 1 MiB',true);
      const previous=button.textContent;button.dataset.pluginBusy='1';button.disabled=true;button.classList.add('ywd-working');button.setAttribute('aria-busy','true');button.textContent='PREPARING…';setUploadProgress(0,true);
      try{
        const bytes=new Uint8Array(await f.arrayBuffer());button.textContent='UPLOADING…';
        const d=await uploadWithProgress({filename:f.name,archive_b64:bytesToB64(bytes)},pct=>{setUploadProgress(pct,true);button.textContent=`UPLOADING… ${pct}%`;},()=>{button.textContent='VERIFYING…';showVerifying();});
        const sig=d.signature||{};el('pluginUploadStatus').textContent=`${d.id} verified and ready for install${sig.key_id?` · ${sig.key_id}`:''}.`;notify(`${d.id} uploaded and verified`);showReview(d);
      }catch(e){notify(e.message,true);el('pluginUploadStatus').textContent=e.message;if(el('pluginInstallReviewModal')?.classList.contains('on'))showReviewError(e.message);}
      finally{delete button.dataset.pluginBusy;button.classList.remove('ywd-working');button.removeAttribute('aria-busy');button.textContent=previous;setTimeout(()=>setUploadProgress(0,false),450);refreshLocks();}
    };
    refreshLocks();return true;
  }

  // The duplex talkgroup controller owns DROP QSO, and historically its native
  // confirm() ran after the general polish layer. Handle the action directly in
  // capture phase so every in-app confirmation uses the YWD modal.
  function installDropQsoModal(){
    if(document.documentElement.dataset.ywdDropQsoModal==='1')return;document.documentElement.dataset.ywdDropQsoModal='1';
    document.addEventListener('click',async e=>{
      const button=e.target.closest?.('#dropQso');if(!button||button.disabled||!document.body.contains(button))return;
      e.preventDefault();e.stopImmediatePropagation();
      if(typeof window.ywdConfirm!=='function'){notify('YWD confirmation UI is unavailable. Reload the dashboard.',true);return;}
      const duplex=typeof tgIsDuplex==='function'?tgIsDuplex():String((typeof state!=='undefined'&&state?.config?.radio?.mode)||'simplex').toLowerCase()==='duplex';
      const slots=typeof tgAllowedSlots==='function'?tgAllowedSlots():(duplex?[1,2]:[0]);
      const ok=await window.ywdConfirm({title:'DROP ACTIVE QSO',message:`Drop the active BrandMeister QSO on ${duplex?'TS1 and TS2':'this simplex hotspot'}?`,confirmText:'DROP QSO',cancelText:'CANCEL',tone:'warn',kicker:'YWD // BRANDMEISTER'});if(!ok)return;
      const old=button.textContent;button.disabled=true;button.classList.add('ywd-working');button.setAttribute('aria-busy','true');button.textContent='DROPPING…';
      try{for(const slot of slots)await post('/api/bm/drop-qso',{slot});notify(`Drop QSO sent${duplex?' to TS1 + TS2':''}`);setTimeout(()=>{try{getStatus();}catch(_){}},700);}catch(err){notify(err.message,true);}finally{button.classList.remove('ywd-working');button.removeAttribute('aria-busy');button.textContent=old;button.disabled=false;}
    },true);
  }

  function init(){patchRenderer();patchPackageActions();ensureUploadUi();ensureReviewModal();installDropQsoModal();const logout=el('logoutBtn');if(logout)new MutationObserver(refreshLocks).observe(logout,{attributes:true,attributeFilter:['hidden']});const mo=new MutationObserver(()=>{patchRenderer();patchPackageActions();ensureUploadUi();refreshLocks();});mo.observe(document.body,{childList:true,subtree:true});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
