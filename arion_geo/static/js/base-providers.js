(() => {
  const drawer=document.querySelector('[data-provider-drawer]');
  const backdrop=document.querySelector('[data-provider-backdrop]');
  const content=document.querySelector('[data-provider-content]');
  if(!drawer||!backdrop||!content)return;
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number=new Intl.NumberFormat('pt-BR');
  const section=(title,items,label,count)=>`<section class="provider-detail-section"><h3>${title} · REAL CMDB</h3>${items.length?items.map(item=>`<p><span>${esc(label(item))}</span><b>${number.format(item[count])} links</b></p>`).join(''):'<p>Sem registros classificados.</p>'}</section>`;
  async function open(row){
    drawer.hidden=false;backdrop.hidden=false;drawer.classList.add('is-open');content.innerHTML='<p>Carregando provedor…</p>';
    try{
      const response=await fetch(row.dataset.detailUrl,{headers:{'X-Requested-With':'XMLHttpRequest'}});
      if(!response.ok)throw new Error('Não foi possível carregar os dados do provedor.');
      const p=await response.json();
      content.innerHTML=`<header class="drawer-heading"><h2>${esc(p.name)}</h2><p>Base atual · CMDB real</p></header><section class="provider-detail-section"><h3>Resumo da base</h3><p><span>ConfigItem</span><b>${esc(p.cmdb_config_item_id||'Não informado')}</b></p><p><span>Links</span><b>${number.format(p.links)} · ${Number(p.share).toFixed(1).replace('.',',')}%</b></p><p><span>Classificados</span><b>${number.format(p.classified_links)}</b></p><p><span>Não classificados</span><b>${number.format(p.unclassified_links)}</b></p><p><span>Municípios</span><b>${number.format(p.cities.length)}</b></p></section>${section('Operadoras',p.operators,x=>x.name,'links')}${section('Projetos',p.projects,x=>x.name,'links')}${section('Principais UFs',p.states.slice(0,5),x=>x.uf,'links')}<a class="links-primary-button" href="/rankings/?provider=${p.id}">Ver no Ranking →</a>`;
    }catch(error){content.innerHTML=`<p>${esc(error.message)}</p>`;}
  }
  function close(){drawer.hidden=true;backdrop.hidden=true;drawer.classList.remove('is-open');}
  document.querySelectorAll('[data-provider-open]').forEach(row=>{row.addEventListener('click',()=>open(row));row.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open(row);}});});
  drawer.querySelector('[data-provider-close]')?.addEventListener('click',close);backdrop.addEventListener('click',close);document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
  const providerId=new URLSearchParams(location.search).get('provider');
  const row=providerId&&document.querySelector(`[data-provider-open="${CSS.escape(providerId)}"]`);if(row)open(row);
})();
