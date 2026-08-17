'use strict';
(() => {
  const el = id => document.getElementById(id);
  function notify(message,bad=false){try{if(typeof toast==='function')return toast(message,bad);}catch(_){}console[bad?'error':'log'](message);}
  function unlocked(){return !!el('logoutBtn')&&!el('logoutBtn').hidden;}
  async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{}),credentials:'same-origin'});let d={};try{d=await r.json();}catch(_){}if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d;}
  function bytesToB64(bytes){let out='';for(let i=0;i<bytes.length;i+=0x8000)out+=String.fromCharCode(...bytes.subarray(i,i+0x8000));return btoa(out);}
  function refreshLocks(){const auth=unlocked();const upload=el('pluginUploadButton');if(upload&&!upload.dataset.pluginBusy)upload.disabled=!auth;document.querySelectorAll('#plugins [data-plugin-action="package-remove"]').forEach(button=>{button.disabled=!auth||button.dataset.pluginBusy==='1';});}

  function patchRenderer(){
    const base=window.ywdPluginCardRenderer;if(!base||base.__alpha182)return;
    const original=base.pluginCard.bind(base);
    base.pluginCard=(plugin,systemEnabled,utils={})=>{
      let html=original(plugin,systemEnabled,utils);
      const origin=plugin.package_origin||'builtin',sig=plugin.signature||{};
      const sigText=sig.status==='verified'?`VERIFIED · ${sig.key_id||'trusted key'}`:sig.status==='unsigned'?'UNSIGNED':sig.status==='builtin'?'YWD CORE':'UNKNOWN';
      const meta=`<div class="plugin-meta plugin-package-trust"><div><span>Source</span><b>${origin==='uploaded'?'UPLOADED':'BUILT-IN'}</b></div><div><span>Signature</span><b>${sigText}</b></div></div>`;
      html=html.replace('<div class="plugin-caps">',meta+'<div class="plugin-caps">');
      if(origin==='uploaded'&&!plugin.installed){
        const action=`<div class="buttonrow wrap plugin-remove-source"><button class="btn danger" data-plugin-action="package-remove" data-plugin-id="${String(plugin.id).replace(/[^a-z0-9-]/g,'')}"${unlocked()?'':' disabled'}>REMOVE PACKAGE</button></div>`;
        html=html.replace('<div id="pluginResult-',action+'<div id="pluginResult-');
      }
      queueMicrotask(refreshLocks);
      return html;
    };
    base.__alpha182=true;
  }

  function patchPackageActions(){
    const base=window.ywdPluginPackageUi;if(!base||base.__alpha182)return;
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
    base.__alpha182=true;
  }

  function ensureUploadUi(){
    const page=el('plugins');if(!page||el('pluginUploadButton'))return false;
    const managerCard=page.querySelector('.card:nth-of-type(2)')||page.querySelector('.card');
    const card=document.createElement('article');card.className='card plugin-upload-card';
    card.innerHTML=`<div class="card-title title-row"><span>UPLOAD PLUGIN PACKAGE</span><span class="hint">.ywdplugin v1</span></div><p class="plugin-api-note">Upload a local plugin archive into the persistent package catalog. Upload only makes a package AVAILABLE; INSTALL and ENABLE remain separate. Unsigned declarative packages are allowed with a warning. Uploaded service code requires a trusted Ed25519 signature.</p><div class="buttonrow wrap"><button class="btn primary" id="pluginUploadButton">UPLOAD .YWDPLUGIN</button><input id="pluginUploadFile" type="file" accept=".ywdplugin,application/zip" hidden></div><div id="pluginUploadStatus" class="hint">Maximum archive size: 1 MiB. ZIP paths, symlinks, unlisted files and invalid hashes are rejected.</div>`;
    if(managerCard?.parentElement)managerCard.parentElement.insertBefore(card,managerCard.nextSibling);else page.prepend(card);
    const file=el('pluginUploadFile'),button=el('pluginUploadButton');
    button.onclick=()=>{if(unlocked())file.click();};
    file.onchange=async()=>{const f=file.files?.[0];file.value='';if(!f)return;if(!unlocked())return notify('Unlock controls before uploading a plugin package.',true);if(f.size<=0||f.size>1024*1024)return notify('Plugin archive is empty or exceeds 1 MiB',true);button.dataset.pluginBusy='1';button.disabled=true;button.textContent='VALIDATING…';try{const bytes=new Uint8Array(await f.arrayBuffer());const d=await post('/api/plugins/upload',{filename:f.name,archive_b64:bytesToB64(bytes)});const sig=d.signature||{};notify(`${d.id} uploaded · ${sig.status||'unknown'} signature · remains uninstalled`);el('pluginUploadStatus').textContent=`${d.id} is now AVAILABLE. Signature: ${sig.status||'unknown'}${sig.key_id?' · '+sig.key_id:''}.`;setTimeout(()=>document.querySelector('[data-tab="plugins"]')?.click(),250);}catch(e){notify(e.message,true);el('pluginUploadStatus').textContent=e.message;}finally{delete button.dataset.pluginBusy;button.textContent='UPLOAD .YWDPLUGIN';refreshLocks();}};
    refreshLocks();return true;
  }

  function init(){patchRenderer();patchPackageActions();ensureUploadUi();const logout=el('logoutBtn');if(logout)new MutationObserver(refreshLocks).observe(logout,{attributes:true,attributeFilter:['hidden']});const mo=new MutationObserver(()=>{patchRenderer();patchPackageActions();ensureUploadUi();refreshLocks();});mo.observe(document.body,{childList:true,subtree:true});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
