(() => {
  const root = document.querySelector('[data-ranking-root]');
  if (!root) return;
  const dataNode = document.getElementById('ranking-providers');
  const rows = root.querySelector('[data-ranking-rows]');
  const podium = root.querySelector('[data-podium]');
  const drawer = root.querySelector('[data-provider-drawer]');
  const backdrop = root.querySelector('[data-drawer-backdrop]');
  if (!dataNode || !rows || !podium || !drawer || !backdrop) return;
  const source = JSON.parse(dataNode.textContent);
  const fmt = new Intl.NumberFormat('pt-BR');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct = value => `${Number(value).toFixed(1).replace('.', ',')}%`;
  let sort = new URLSearchParams(location.search).get('sort') || 'score';
  const sorters = {
    score: (a,b) => b.score-a.score, links: (a,b) => b.links-a.links,
    sla: (a,b) => b.dentro_pct-a.dentro_pct, 'sla-worst': (a,b) => a.dentro_pct-b.dentro_pct,
    chamados: (a,b) => b.chamados-a.chamados, reincidencias: (a,b) => b.reincidencias-a.reincidencias,
    estourados: (a,b) => b.estourados-a.estourados, avaliacao: (a,b) => b.avaliacao-a.avaliacao,
  };
  const labels = {score:'Score · Demonstração',links:'Links · CMDB real',sla:'SLA · Demonstração','sla-worst':'SLA · Demonstração',chamados:'Chamados · Demonstração',reincidencias:'Reincidência · Demonstração',estourados:'Estourados · Demonstração',avaliacao:'Avaliação · Demonstração'};
  const cards = item => `<article class="podium-card"><header class="podium-header"><div class="provider-brand"><span class="provider-logo">${esc(item.logo)}</span><div class="provider-identity"><h3>${esc(item.name)}</h3><span class="provider-meta">${fmt.format(item.links)} links · CMDB real</span></div></div><span class="demo-badge">DEMO</span></header><div class="podium-hero"><div><span class="hero-label">SCORE DEMO</span><strong class="podium-score">${item.score.toFixed(1).replace('.', ',')}</strong></div><div><span class="hero-label">PARTICIPAÇÃO REAL</span><strong class="podium-links">${pct(item.share)}</strong></div></div><div class="podium-quick"><span>SLA demo <b>${pct(item.dentro_pct)}</b></span><span>Chamados demo <b>${item.chamados}</b></span></div><button class="detail-link" data-open="${item.id}">Ver análise <span aria-hidden="true">→</span></button></article>`;
  const row = (item, index) => `<tr tabindex="0" data-open="${item.id}"><td class="col-rank"><span class="rank-number">${String(index+1).padStart(2,'0')}</span></td><td class="col-provider"><div class="table-provider"><span class="provider-logo">${esc(item.logo)}</span><div class="table-provider-info"><b>${esc(item.name)}</b><small>${fmt.format(item.links)} links reais · ${pct(item.share)} da CMDB</small></div></div></td><td class="col-num"><div class="links-cell"><strong>${fmt.format(item.links)}</strong><small>${pct(item.share)} real</small></div></td><td class="col-num">${item.chamados}<small class="row-sub">DEMO</small></td><td class="col-sla"><div class="sla-cell"><i class="sla-bar"><b style="width:${item.dentro_pct}%"></b></i><strong>${pct(item.dentro_pct)}</strong><small>DEMO</small></div></td><td class="col-num">${item.reincidencias}<small class="row-sub">DEMO</small></td><td class="col-score"><b class="score-cell">${item.score.toFixed(1).replace('.', ',')}</b><small>DEMO</small></td><td class="col-trend">${item.tendencia==='up'?'↑':item.tendencia==='down'?'↓':'→'}</td><td><button class="row-action" data-open="${item.id}" aria-label="Ver ${esc(item.name)}">→</button></td></tr>`;
  function show(item) {
    root.querySelector('#drawer-title').textContent = item.name;
    root.querySelector('[data-drawer-meta]').textContent = `${fmt.format(item.links)} links · ${pct(item.share)} da base · CMDB real`;
    const line = (label, value) => `<p><span>${esc(label)}</span><b>${esc(value)}</b></p>`;
    const list = (heading, values, label) => `<section class="drawer-section"><h3>${heading} <small>REAL CMDB</small></h3>${values.length ? values.map(value => line(label(value), fmt.format(value.links))).join('') : '<p>Sem classificação na base.</p>'}</section>`;
    const months=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out'];
    root.querySelector('[data-drawer-content]').innerHTML = `<section class="drawer-section"><h3>Dados da base <small>REAL CMDB</small></h3>${line('ConfigItem do provedor', item.cmdb_config_item_id || 'Não informado')}${line('Links presentes', fmt.format(item.links))}${line('Participação', pct(item.share))}${line('Links classificados', fmt.format(item.classified_links))}${line('Links não classificados', fmt.format(item.unclassified_links))}${line('Municípios', fmt.format(item.cities.length))}</section>${list('Projetos atendidos',item.projects,x=>x.name)}${list('Operadoras',item.operators,x=>x.name)}${list('Top UFs',item.states.slice(0,5),x=>x.uf)}<section class="drawer-section"><h3>Performance <small>DEMONSTRAÇÃO</small></h3>${line('Chamados',item.chamados)}${line('SLA',pct(item.dentro_pct))}${line('Reincidências',item.reincidencias)}${line('Estourados',item.estourados)}${line('Uptime',pct(item.uptime))}${line('Avaliação',`${item.avaliacao.toFixed(2)} / 5`)}${line('Score',item.score.toFixed(1))}<h4>Histórico mensal demo</h4><div class="history-bars">${item.history.map((n,i)=>`<div><b>${n}</b><i style="height:${Math.max(8,n/Math.max(...item.history)*100)}%"></i><small>${months[i]}</small></div>`).join('')}</div></section><a class="detail-link" href="/base/?view=links&provedor=${item.id}">Ver links deste provedor →</a>`;
    drawer.hidden=false; backdrop.hidden=false; document.body.classList.add('drawer-open');
  }
  function close() { drawer.hidden=true; backdrop.hidden=true; document.body.classList.remove('drawer-open'); }
  function render() {
    const filters = [...root.querySelectorAll('[data-filter]')];
    const data = source.filter(item => filters.every(filter => !filter.value || (filter.dataset.filter==='operadora' ? item.operadoras : item.projetos_nomes).includes(filter.value))).sort(sorters[sort] || sorters.score);
    root.querySelector('[data-source-note]').textContent = labels[sort] || labels.score;
    podium.innerHTML = data.slice(0,3).map(cards).join(''); rows.innerHTML=data.map(row).join('');
    root.querySelector('[data-result-count]').textContent=data.length;
    root.querySelector('[data-empty]').hidden=!!data.length;
    root.querySelector('.table-scroll').hidden=!data.length;
    root.querySelector('.podium-section').hidden=!data.length;
  }
  root.querySelector('.criteria-chips').addEventListener('click', event => {
    const button=event.target.closest('[data-sort]'); if(!button)return;
    sort=button.dataset.sort; root.querySelectorAll('[data-sort]').forEach(item=>item.classList.toggle('is-selected',item===button)); render();
  });
  root.querySelectorAll('[data-filter]').forEach(filter=>filter.addEventListener('change',render));
  root.addEventListener('click',event=>{const button=event.target.closest('[data-open]');if(button){const item=source.find(row=>String(row.id)===button.dataset.open);if(item)show(item);}});
  rows.addEventListener('keydown',event=>{if((event.key==='Enter'||event.key===' ')&&event.target.matches('tr[data-open]')){event.preventDefault();const item=source.find(row=>String(row.id)===event.target.dataset.open);if(item)show(item);}});
  drawer.querySelector('[data-drawer-close]').addEventListener('click',close);backdrop.addEventListener('click',close);document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!drawer.hidden)close();});
  render();
  const requestedProvider = new URLSearchParams(location.search).get('provider');
  const selectedProvider = source.find(item => String(item.id) === requestedProvider);
  if (selectedProvider) show(selectedProvider);
})();
