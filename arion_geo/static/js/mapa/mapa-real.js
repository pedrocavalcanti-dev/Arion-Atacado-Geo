(() => {
  const root = document.querySelector("[data-map-config]");
  const page = document.querySelector(".geo-page");
  if (!root || !page) return;
  const $ = selector => (page || root).querySelector(selector);
  const number = new Intl.NumberFormat("pt-BR");
  const stateNames = { AC:"Acre",AL:"Alagoas",AM:"Amazonas",AP:"Amapá",BA:"Bahia",CE:"Ceará",DF:"Distrito Federal",ES:"Espírito Santo",GO:"Goiás",MA:"Maranhão",MG:"Minas Gerais",MS:"Mato Grosso do Sul",MT:"Mato Grosso",PA:"Pará",PB:"Paraíba",PE:"Pernambuco",PI:"Piauí",PR:"Paraná",RJ:"Rio de Janeiro",RN:"Rio Grande do Norte",RO:"Rondônia",RR:"Roraima",RS:"Rio Grande do Sul",SC:"Santa Catarina",SE:"Sergipe",SP:"São Paulo",TO:"Tocantins" };
  const modeLabels = { base:"Links CMDB",projects:"Links do projeto",calls:"Tickets criados no período",repeat:"Links reincidentes",motives:"Tickets encerrados" };
  const brand = { claro:"#9f4b46",vivo:"#675086",algar:"#4b7155",other:"#687b86" };
  const brandLight = { claro:"#c88984",vivo:"#a28cbd",algar:"#8aa892",other:"#aebec5" };
  const quantitative = {
    calls: { dark:["#202220","#805f50","#d18a69"], light:["#ece8e2","#d5a083","#a95335"] },
    repeat: { dark:["#202220","#665469","#bc86a9"], light:["#ece8ed","#b69ab5","#815a80"] },
    motives: { dark:["#202220","#665469","#b68bb1"], light:["#ece8ed","#b69ab5","#765b82"] },
  };
  const required = [
    "#brazil-map", "#geo-title", "#state-flags-data", "[data-source-badge]", "[data-breadcrumb]", "[data-selected-name]",
    "[data-map-message]", "[data-map-error]", "[data-map-error-title]", "[data-map-error-detail]", "[data-map-retry]",
    "[data-national-panel]", "[data-national-view]", "[data-national-content]", "[data-national-collapse]", "[data-national-expand]",
    "[data-national-tab='summary']", "[data-national-tab='ranking']", "[data-national-tab='distribution']", "[data-brazil-link]",
    "[data-state-panel]", "[data-panel-backdrop]", "[data-panel-close]", "[data-panel-code]", "[data-panel-name]", "[data-panel-flag]",
    "[data-panel-total]", "[data-panel-scope]", "[data-panel-context]", "[data-panel-clients]", "[data-panel-coverage]", "[data-panel-status]",
    "[data-panel-projects]", "[data-panel-providers]", "[data-panel-cities]", "[data-panel-reasons]", "[data-panel-links]", "[data-panel-tickets]",
    "[data-ticket-modal]", "[data-ticket-title]", "[data-ticket-content]", "[data-ticket-close]", "[data-ticket-filters]", "[data-status-filter]", "[data-priority-filter]",
    "[data-open-base]", "[data-open-cockpit]", "[data-map-announcement]", "[data-state-search]", "[data-state-search-results]",
    "[data-mode]", "[data-client]", "[data-project-filter]", "[data-period-control]", "[data-period-filter]",
    "[data-provider-filter]", "[data-motives-select]", "[data-motive-filter]", "[data-custom-period]",
    "[data-date-from]", "[data-date-to]", "[data-apply-period]", "[data-legend]",
  ];
  const missingRequired = required.filter(selector => !$(selector));
  if (missingRequired.length) {
    console.error("Mapa: elementos obrigatorios ausentes no template.", missingRequired);
    return;
  }
  const mapElement = $("#brazil-map"), message = $("[data-map-message]"), errorBox = $("[data-map-error]");
  const panel = $("[data-state-panel]"), national = $("[data-national-panel]"), panelBackdrop = $("[data-panel-backdrop]");
  const flagsNode = $("#state-flags-data");
  const flags = flagsNode ? JSON.parse(flagsNode.textContent || "{}") : {};
  const ui = {
    source: $("[data-source-badge]"), breadcrumb: $("[data-breadcrumb]"), selectedName: $("[data-selected-name]"),
    project: $("[data-project-filter]"), period: $("[data-period-filter]"), periodControl: $("[data-period-control]"), provider: $("[data-provider-filter]"),
    reason: $("[data-motive-filter]"), reasonWrap: $("[data-motives-select]"), dates: $("[data-custom-period]"),
    dateFrom: $("[data-date-from]"), dateTo: $("[data-date-to]"), search: $("[data-state-search]"), results: $("[data-state-search-results]"),
    nationalView: $("[data-national-view]"), panelName: $("[data-panel-name]"), panelCode: $("[data-panel-code]"), panelFlag: $("[data-panel-flag]"),
    panelTotal: $("[data-panel-total]"), panelScope: $("[data-panel-scope]"), panelContext: $("[data-panel-context]"),
    clients: $("[data-panel-clients]"), statuses: $("[data-panel-status]"), projects: $("[data-panel-projects]"), providers: $("[data-panel-providers]"), cities: $("[data-panel-cities]"),
    reasons: $("[data-panel-reasons]"), links: $("[data-panel-links]"), tickets: $("[data-panel-tickets]"),
    ticketFilters: $("[data-ticket-filters]"), status: $("[data-status-filter]"), priority: $("[data-priority-filter]"), ticketModal: $("[data-ticket-modal]"), ticketTitle: $("[data-ticket-title]"), ticketContent: $("[data-ticket-content]"), ticketClose: $("[data-ticket-close]"),
    openBase: $("[data-open-base]"), openCockpit: $("[data-open-cockpit]"), announce: $("[data-map-announcement]"), legend: $("[data-legend]"),
  };
  const state = { mode:"base", client:"all", project:"", provider:"", period:"this_month", reason:"", status:"", priority:"", dateFrom:"", dateTo:"", selectedUF:"", panelTab:"summary", distributionDimension:"status", collapsed:false };
  const initialParams=new URLSearchParams(location.search);
  ["mode","client","project","provider","period","reason","status","priority"].forEach(key=>{if(initialParams.has(key))state[key]=initialParams.get(key);});
  state.selectedUF=(initialParams.get("uf")||"").toUpperCase();
  if(/^\d{4}-(0[1-9]|1[0-2])$/.test(state.period)){const [year,month]=state.period.split("-").map(Number);state.dateFrom=`${state.period}-01`;state.dateTo=new Date(Date.UTC(year,month,0)).toISOString().slice(0,10);}
  state.dateFrom=initialParams.get("date_from")||state.dateFrom;state.dateTo=initialParams.get("date_to")||state.dateTo;
  if(!["base","projects","calls","repeat","motives"].includes(state.mode))state.mode="base";
  if(!["all","Claro","Vivo","Algar","other"].includes(state.client))state.client="all";
  ui.period.disabled = true;
  ui.reasonWrap.hidden = true;
  let map = null, geojson = null, data = null, mapLoaded = false, requestSequence = 0, searchIndex = -1, periodHideTimer = 0, ticketRows = [], ticketReturnFocus = null;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const norm = value => String(value || "").trim().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
  const theme = () => document.documentElement.dataset.theme === "light" ? "light" : "dark";
  const showError = (detail, title = "Mapa indisponível") => { message.hidden = true; errorBox.hidden = false; $("[data-map-error-title]").textContent = title; $("[data-map-error-detail]").textContent = detail; };
  const metricValue = row => {
    if (!row) return 0;
    if (state.mode === "calls") return row.ticket_count || 0;
    if (state.mode === "repeat") return row.recurrence_links || 0;
    if (state.mode === "motives") return state.reason ? (row.reason_counts?.[state.reason] || 0) : Object.values(row.reason_counts || {}).reduce((a,b)=>a+b,0);
    return row.total_links || 0;
  };
  const selectedTotal = () => {
    if (!data) return 0;
    if (state.mode === "calls") return data.ticket_count || 0;
    if (state.mode === "repeat") return data.recurrence_link_count || 0;
    if (state.mode === "motives") return data.terminal_ticket_count || 0;
    return data.filtered_source_total || 0;
  };
  function urlFor(path, overrides = {}) {
    const url = new URL(path, window.location.origin);
    const params = { mode:state.mode, client:state.client, project:state.project, provider:state.provider, reason:state.reason, period:state.period, date_from:state.dateFrom, date_to:state.dateTo, status:state.status, priority:state.priority, ...overrides };
    Object.entries(params).forEach(([key,value]) => { if (value) url.searchParams.set(key,value); });
    return url;
  }
  function syncUrl(){
    const url=new URL(location.href);
    ["mode","client","project","period","uf","reason","provider","date_from","date_to","status","priority"].forEach(key=>url.searchParams.delete(key));
    url.searchParams.set("mode",state.mode);
    if(state.client!=="all")url.searchParams.set("client",state.client);
    if(state.project)url.searchParams.set("project",state.project);
    if(state.provider)url.searchParams.set("provider",state.provider);
    if(["calls","repeat","motives"].includes(state.mode)){
      url.searchParams.set("period",state.period);
      if(state.dateFrom)url.searchParams.set("date_from",state.dateFrom);
      if(state.dateTo)url.searchParams.set("date_to",state.dateTo);
    }
    if(state.reason)url.searchParams.set("reason",state.reason);
    if(state.mode==="calls"&&state.status)url.searchParams.set("status",state.status);
    if(state.mode==="calls"&&state.priority)url.searchParams.set("priority",state.priority);
    if(state.selectedUF)url.searchParams.set("uf",state.selectedUF);
    history.replaceState(null,"",url.pathname+url.search+url.hash);
  }
  function updateModeControls(){
    const temporal=["calls","repeat","motives"].includes(state.mode);
    if(ui.periodControl){
      if(temporal){
        clearTimeout(periodHideTimer);ui.periodControl.hidden=false;
        requestAnimationFrame(()=>ui.periodControl.classList.add("is-visible"));
      }else{
        ui.periodControl.classList.remove("is-visible");
        clearTimeout(periodHideTimer);periodHideTimer=setTimeout(()=>{if(!["calls","repeat","motives"].includes(state.mode))ui.periodControl.hidden=true;},180);
      }
    }
    ui.period.disabled=!temporal;
    ui.dates.hidden=!(temporal&&(state.period==="custom"||/^\d{4}-(0[1-9]|1[0-2])$/.test(state.period)));
    ui.reasonWrap.hidden=state.mode!=="motives";
    ui.ticketFilters.hidden=state.mode!=="calls";
    ui.status.value=state.mode==="calls"?state.status:"";
    ui.priority.value=state.mode==="calls"?state.priority:"";
    page.querySelectorAll("[data-mode]").forEach(item=>{const selected=item.dataset.mode===state.mode;item.classList.toggle("is-selected",selected);item.setAttribute("aria-pressed",String(selected));});
    if(["this_month","last_month","last_30","last_90","custom"].includes(state.period))ui.period.value=state.period;
    else ui.period.value="custom";
    ui.dateFrom.value=state.dateFrom;ui.dateTo.value=state.dateTo;
    const titlePeriod=state.period.match(/^\d{4}-(0[1-9]|1[0-2])$/)?periodLabel({date_from:`${state.period}-01`}):periodLabel({date_from:state.dateFrom||data?.period?.date_from});
    const heading=state.mode==="base"?"Base de links":state.mode==="projects"?(state.project?`Projeto \u00b7 ${displayProject(state.project)}`:"Projetos"): ["calls","repeat","motives"].includes(state.mode)?`${state.mode==="calls"?"Chamados":state.mode==="repeat"?"Reincid\u00eancia":"Motivos"} \u00b7 ${titlePeriod}`:"Vis\u00e3o geogr\u00e1fica";
    $("#geo-title").textContent=heading;
  }
  async function fetchData() {
    const seq = ++requestSequence;
    message.hidden = false; errorBox.hidden = true;
    syncUrl();
    const response = await fetch(urlFor(root.dataset.apiUrl), { headers:{"X-Requested-With":"XMLHttpRequest"}, signal:AbortSignal.timeout(20000) });
    if (!response.ok) throw new Error(`A consulta do Mapa respondeu HTTP ${response.status}.`);
    const payload = await response.json();
    if (!payload.states || !Array.isArray(payload.projects) || !Array.isArray(payload.providers)) throw new Error("A API retornou um formato inesperado.");
    if (seq !== requestSequence) return false;
    data = payload;
    fillFilters();
    updateModeControls();syncUrl();
    renderMap(); renderLegend(); renderNational();
    message.hidden = true;
    if (state.selectedUF) await loadState(state.selectedUF);
    return true;
  }
  function displayProject(value){
    const known={"BANCO DO BRASIL":"Banco do Brasil","CAIXA ECONOMICA FEDERAL":"Caixa Econ\u00f4mica Federal","CORREIOS":"Correios","BRADESCO":"Bradesco","ARCOS DOURADOS":"Arcos Dourados","DIVERSOS":"Diversos"};
    return known[norm(value).toLocaleUpperCase("pt-BR")]||String(value||"").toLocaleLowerCase("pt-BR").replace(/(^|\s)\S/g,letter=>letter.toLocaleUpperCase("pt-BR"));
  }
  function periodLabel(period){
    const value=period?.date_from||"";
    if(!value)return "per\u00edodo";
    return new Intl.DateTimeFormat("pt-BR",{month:"long",year:"numeric",timeZone:"UTC"}).format(new Date(`${value}T12:00:00Z`));
  }
  function fillFilters() {
    const oldProject = state.project;
    ui.project.innerHTML = '<option value="">Todos os projetos</option>' + data.projects.map(value=>`<option value="${esc(value)}">${esc(displayProject(value))}</option>`).join("");
    if (data.projects.includes(oldProject)) ui.project.value = oldProject; else { state.project=""; ui.project.value=""; }
    ui.provider.innerHTML = '<option value="">Todos os provedores</option>' + data.providers.map(row=>`<option value="${esc(row.id)}">${esc(row.name)}</option>`).join("");
    ui.priority.innerHTML='<option value="">Todas</option>'+(data.priority_options||[]).map(value=>`<option value="${esc(value)}">${esc(value)}</option>`).join("");
    ui.provider.value = data.providers.some(row=>String(row.id)===state.provider) ? state.provider : "";
    const oldReason = state.reason;
    ui.reason.innerHTML = '<option value="">Todos os motivos</option>' + data.reasons.map(value=>`<option value="${esc(value)}">${esc(value)}</option>`).join("");
    if (data.reasons.includes(oldReason)) ui.reason.value=oldReason; else { state.reason=""; ui.reason.value=""; }
  }
  function dominantClient(row) {
    const counts=row?.client_counts || {};
    const unidentified=counts["Cliente não identificado"]||0;
    const identified={claro:0,vivo:0,algar:0,other:0};
    Object.entries(counts).forEach(([name,value])=>{
      const key=norm(name);
      if(key==="cliente nao identificado") return;
      if(key==="claro"||key==="vivo"||key==="algar") identified[key]+=value;
      else identified.other+=value;
    });
    const winner=Object.entries(identified).sort((a,b)=>b[1]-a[1])[0];
    return !winner||unidentified>=winner[1]?"unclassified":winner[0];
  }
  function dominantClientLabel(row) {
    const dominant=dominantClient(row);
    return dominant==="unclassified"?"Cliente n\u00e3o identificado":dominant==="other"?"Outras":dominant.charAt(0).toUpperCase()+dominant.slice(1);
  }
  function maxMetric() { return Math.max(1,...Object.values(data?.states || {}).map(metricValue)); }
  function featureCollection() {
    const maximum=maxMetric();
    return { type:"FeatureCollection", features:geojson.features.map(feature=>{
      const code=feature.properties.sigla,row=data.states[code] || {};
      return { ...feature, id:code, properties:{...feature.properties,value:metricValue(row),dominant:dominantClient(row),intensity:Math.sqrt(metricValue(row)/maximum),selected:code===state.selectedUF,has_data:metricValue(row)>0} };
    })};
  }
  function baseColorExpression() {
    const p=theme()==="light"?brandLight:brand;
    if (state.mode === "projects") {
      const colors=quantitative.projects?.[theme()] || (theme()==="light"?["#edf0f1","#93a7b1","#58717d"]:["#191d1f","#526873","#91aab4"]);
      return ["interpolate",["linear"],["get","intensity"],0,colors[0],.45,colors[1],1,colors[2]];
    }
    if (state.client !== "all") {
      const key=state.client==="other"?"other":norm(state.client);
      const colors=quantitative.base?.[theme()] || ["#d3d7d3",p[key] || p.other,p[key] || p.other];
      return ["interpolate",["linear"],["get","intensity"],0,theme()==="light"?"#eef0ed":"#171a18",.35,colors[1],1,p[key] || p.other];
    }
    return ["match",["get","dominant"],"claro",p.claro,"vivo",p.vivo,"algar",p.algar,"other",theme()==="light"?"#89979d":"#596970",theme()==="light"?"#d8dcda":"#343a3b"];
  }
  function fillExpression() {
    if (["base","projects"].includes(state.mode)) return baseColorExpression();
    const colors=quantitative[state.mode]?.[theme()] || quantitative.calls[theme()];
    return ["interpolate",["linear"],["get","intensity"],0,colors[0],.45,colors[1],1,colors[2]];
  }
  function renderMap() {
    if (!map || !geojson) return;
    const features=featureCollection();
    if (map.getSource("arion-states")) map.getSource("arion-states").setData(features);
    const maximum=maxMetric();
    if (map.getLayer("arion-state-fill")) map.setPaintProperty("arion-state-fill","fill-color",fillExpression());
    if (map.getLayer("arion-state-fill")) map.setPaintProperty("arion-state-fill","fill-opacity",["case",["boolean",["get","selected"],false],.97,["boolean",["get","has_data"],false],.9,.42]);
    if (map.getLayer("arion-state-outline")) {
      map.setPaintProperty("arion-state-outline","line-color",["case",["boolean",["get","selected"],false],theme()==="light"?"#26372b":"#eff3ef",theme()==="light"?"rgba(35,48,39,.34)":"rgba(225,235,228,.28)"]);
      map.setPaintProperty("arion-state-outline","line-width",["case",["boolean",["get","selected"],false],2.4,1]);
    }
    $("[data-map-context]")?.replaceChildren();
    renderNational();
  }
  function renderLegend() {
    if (state.mode === "base") {
      ui.legend.classList.remove("geo-legend--scale");
      ui.legend.innerHTML='<span class="legend-item"><i class="legend-dot legend-dot--claro"></i>Claro</span><span class="legend-item"><i class="legend-dot legend-dot--vivo"></i>Vivo</span><span class="legend-item"><i class="legend-dot legend-dot--algar"></i>Algar</span><span class="legend-item"><i class="legend-dot legend-dot--other"></i>Outras</span><span class="legend-item"><i class="legend-dot legend-dot--unidentified"></i>N\u00e3o identificado</span>';
    } else {
      ui.legend.classList.add("geo-legend--scale");
      const label=state.mode==="motives" && state.reason?state.reason:modeLabels[state.mode];
      ui.legend.innerHTML=`<span class="legend-scale-label">Menor ${esc(label)}</span><span class="legend-scale legend-scale--${state.mode}"></span><span class="legend-scale-label">Maior</span>`;
    }
    const source={base:"CMDB real \u00b7 base atual",projects:"CMDB real \u00b7 projetos atuais",calls:"OTRS + CMDB \u00b7 chamados",repeat:"OTRS + CMDB \u00b7 reincid\u00eancia",motives:"OTRS \u00b7 motivos de encerramento"};
    ui.source.innerHTML=`<i></i>${source[state.mode]}`;
  }
  function renderNational() {
    if (!data || !ui.nationalView) return;
    const rows=Object.entries(data.states).map(([code,row])=>({code,name:stateNames[code]||code,row,value:metricValue(row)})).sort((a,b)=>b.value-a.value);
    const active=rows.filter(row=>row.value>0).length;
    const total=selectedTotal();
    const baseCoverage=Number(data.client_coverage||0).toLocaleString("pt-BR",{maximumFractionDigits:1});
    const max=Math.max(1,...rows.map(row=>row.value));
    if (state.panelTab==="summary") {
      const top=rows[0];
      const projects=new Set(),clients=new Set(),providers=new Set();
      const reasonCounts={};
      Object.values(data.states).forEach(row=>{
        Object.keys(row.project_counts||{}).filter(value=>value!=="Projeto n\u00e3o identificado").forEach(value=>projects.add(value));
        Object.keys(row.client_counts||{}).filter(value=>value!=="Cliente n\u00e3o identificado").forEach(value=>clients.add(value));
        Object.keys(row.provider_counts||{}).filter(value=>value!=="Provedor n\u00e3o identificado").forEach(value=>providers.add(value));
        Object.entries(row.reason_counts||{}).forEach(([reason,count])=>reasonCounts[reason]=(reasonCounts[reason]||0)+count);
      });
      const topReason=Object.entries(reasonCounts).sort((a,b)=>b[1]-a[1])[0];
      let kpis;
      if(state.mode==="base") kpis=[["Links CMDB",total],["UFs com links",active],["Cobertura Cliente",`${baseCoverage}%`],["Clientes",clients.size],["Projetos",projects.size],["Provedores",providers.size]];
      else if(state.mode==="projects") kpis=[["Links CMDB",total],["UFs com links",active],["Clientes",clients.size],["Projetos",projects.size],["Provedores",providers.size]];
      else if(state.mode==="calls") kpis=[["Tickets criados",data.ticket_count||0],["Links afetados",data.affected_link_count||0],["UFs com chamados",active],["Links reincidentes",data.recurrence_link_count||0]];
      else if(state.mode==="repeat") kpis=[["Links reincidentes",data.recurrence_link_count||0],["Tickets nesses links",data.recurrence_ticket_count||0],["UFs com reincidencia",active],["Projetos",projects.size]];
      else kpis=[["Tickets encerrados",data.terminal_ticket_count||0],["Motivo dominante",topReason?.[0]||"Sem dados"],["UFs com encerramentos",active],["Links afetados",data.terminal_link_count||0]];
      const source=["base","projects"].includes(state.mode)?"CMDB atual":state.mode==="repeat"?"OTRS + CMDB":"OTRS local";
      const period=["base","projects"].includes(state.mode)?"Snapshot atual":`${data.period?.date_from||""} \u2013 ${data.period?.date_to||""}`;
      ui.nationalView.innerHTML=`<div class="national-kpis">${kpis.map(([label,value])=>`<div><strong>${typeof value==="number"?number.format(value):esc(value)}</strong><span>${esc(label)}</span></div>`).join("")}</div><div class="national-leaders"><div><span>Maior valor por UF</span><strong>${esc(top?.name||"Sem dados")}</strong><small>${number.format(top?.value||0)} ${esc(modeLabels[state.mode])}</small></div><div><span>Fonte / recorte</span><strong>${esc(source)}</strong><small>${esc(period)}</small></div></div>`;
    } else if (state.panelTab==="ranking") {
      ui.nationalView.innerHTML=`<div class="national-view-heading"><span>Top 5 por ${esc(modeLabels[state.mode])}</span><span class="demo-inline">Dados reais</span></div><ol class="national-ranking">${rows.filter(row=>row.value>0).slice(0,5).map((row,i)=>`<li><span class="national-rank-number">${String(i+1).padStart(2,"0")}</span><img src="${esc(flags[row.code]||"")}" alt="" width="22" height="15" loading="lazy"><span class="national-rank-name">${esc(row.name)}</span><strong>${number.format(row.value)}</strong></li>`).join("")||"<li>Nenhum dado para este recorte.</li>"}</ol>`;
    } else {
      let distribution={},distributionLabel="",dimensionSelector="";
      if(state.mode==="base") { distributionLabel="Distribui\u00e7\u00e3o por cliente";Object.values(data.states).forEach(row=>Object.entries(row.client_counts||{}).forEach(([key,value])=>{const normKey=norm(key);const bucket=normKey==="claro"?"Claro":normKey==="vivo"?"Vivo":normKey==="algar"?"Algar":normKey==="cliente nao identificado"?"Cliente n\u00e3o identificado":"Outras";distribution[bucket]=(distribution[bucket]||0)+value;})); }
      else if(state.mode==="projects") { distributionLabel="Distribui\u00e7\u00e3o por provedor";Object.values(data.states).forEach(row=>Object.entries(row.provider_counts||{}).forEach(([key,value])=>distribution[key]=(distribution[key]||0)+value)); }
      else if(state.mode==="calls") {
        const dimensions={status:["Status",data.ticket_status_counts||{}],client:["Cliente",data.ticket_client_counts||{}],project:["Projeto",data.ticket_project_counts||{}],provider:["Provedor",data.ticket_provider_counts||{}],reason:["Motivo",data.ticket_reason_counts||{}]};
        const selected=dimensions[state.distributionDimension]||dimensions.status;distributionLabel=`Tickets por ${selected[0].toLocaleLowerCase("pt-BR")}`;distribution=selected[1];
        dimensionSelector=`<label class="distribution-dimension"><span>Distribuir por</span><select data-distribution-filter>${Object.entries(dimensions).map(([key,value])=>`<option value="${key}" ${key===state.distributionDimension?"selected":""}>${value[0]}</option>`).join("")}</select></label>`;
      }
      else if(state.mode==="repeat") { distributionLabel="Links reincidentes por cliente";distribution=data.recurrence_client_counts||{}; }
      else { distributionLabel="Tickets por motivo";Object.values(data.states).forEach(row=>Object.entries(row.reason_counts||{}).forEach(([key,value])=>distribution[key]=(distribution[key]||0)+value)); }
      const allItems=Object.entries(distribution).sort((a,b)=>b[1]-a[1]),sum=allItems.reduce((a,item)=>a+item[1],0),items=allItems.slice(0,8);
      ui.nationalView.innerHTML=`<div class="national-view-heading"><span>${esc(distributionLabel)}</span>${dimensionSelector}<span class="demo-inline">${number.format(sum)} registros</span></div><div class="national-distribution">${items.map(([label,value])=>{const key=norm(label);const tone=key==="claro"?"claro":key==="vivo"?"vivo":key==="algar"?"algar":key==="cliente nao identificado"?"unidentified":"other";return `<div class="national-distribution-row"><span><i class="operator-swatch operator-swatch--${tone}"></i>${esc(label)}</span><strong>${sum?(value/sum*100).toLocaleString("pt-BR",{maximumFractionDigits:1}):0}%</strong><small>${number.format(value)}</small><i class="national-distribution-track"><b class="operator-fill--${tone}" style="width:${Math.max(0,value/sum*100)}%"></b></i></div>`;}).join("")||"<p>Nenhum dado para este recorte.</p>"}</div>`;
    }
  }
  ui.nationalView.addEventListener("change",event=>{if(event.target.matches("[data-distribution-filter]")){state.distributionDimension=event.target.value;renderNational();}});
  function setPanelTab(tab) {
    state.panelTab=tab;
    $("[data-national-tab='summary']").setAttribute("aria-selected",String(tab==="summary"));
    $("[data-national-tab='ranking']").setAttribute("aria-selected",String(tab==="ranking"));
    $("[data-national-tab='distribution']").setAttribute("aria-selected",String(tab==="distribution"));
    renderNational();
  }
  function listRows(target, values, suffix="links") {
    const rows=Object.entries(values||{}).filter(([,count])=>count).sort((a,b)=>b[1]-a[1]).slice(0,6);
    target.innerHTML=rows.map(([label,count])=>`<div class="panel-reason-row"><span>${esc(label)}</span><b>${number.format(count)} ${suffix}</b></div>`).join("")||'<p class="panel-empty">Sem registros neste recorte.</p>';
  }
  const statusLabels={OPEN:"Aberto",PENDING:"Pendente",SCHEDULED:"Agendado",RESOLVED:"Resolvido",CLOSED:"Fechado"};
  function openTicket(ticket, trigger){
    ticketReturnFocus=trigger;ui.ticketTitle.textContent=ticket.ticket_number||"Chamado";
    const identity=ticket.identity||{},cmdb=ticket.cmdb||{};
    const rows=[["T?tulo",ticket.title||"N?o informado"],["Cliente do ticket",identity.client||"N?o identificado"],["Cliente informado no t?tulo",identity.client_raw||"N?o identificado"],["Projeto",identity.project||"N?o identificado"],["Tipo",identity.occurrence||"N?o identificado"],["Servi?o",identity.service||"N?o identificado"],["Business ID",identity.business_id||"N?o identificado"],["Status",statusLabels[ticket.status]||"Status n?o mapeado"],["Prioridade",ticket.priority||"N?o informada"],["Criado em",ticket.created_at||"N?o informado"],["Alterado em",ticket.changed_at||"N?o informado"],["Encerrado em",ticket.terminal_at||"N?o informado"],["Motivo",ticket.closing_reason||"N?o informado"],["Item CMDB",cmdb.number||cmdb.name||"N?o relacionado"],["Designa??o",cmdb.designation||"N?o informada"],["Circuito",cmdb.circuit||"N?o informado"],["Cidade / UF",[cmdb.city,cmdb.uf].filter(Boolean).join(" / ")||"N?o informada"],["Provedor",cmdb.provider||"N?o identificado"]];
    ui.ticketContent.innerHTML=rows.map(([label,value])=>`<div class="ticket-detail-row"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("")+`<p class="ticket-detail-note">Contexto associado ao recorte geogr?fico; ${esc(identity.source||"UNKNOWN")} ? a identidade do t?tulo n?o altera a classifica??o do link CMDB.</p>`;
    ui.ticketModal.hidden=false;document.body.classList.add("ticket-dialog-open");ui.ticketClose.focus();
  }
  function closeTicket(){if(ui.ticketModal.hidden)return;ui.ticketModal.hidden=true;document.body.classList.remove("ticket-dialog-open");ticketReturnFocus?.focus();}
  async function loadState(code) {
    if (!data) return;
    const row=data.states[code]||{};
    const url=urlFor(root.dataset.detailUrl,{uf:code});
    const response=await fetch(url,{headers:{"X-Requested-With":"XMLHttpRequest"},signal:AbortSignal.timeout(20000)});
    if(!response.ok) throw new Error(`Não foi possível abrir os detalhes da UF (${response.status}).`);
    const detail=await response.json();
    ui.panelCode.textContent=code; ui.panelName.textContent=stateNames[code]||code;
    const title=state.mode==="base"?"Base de links":state.mode==="projects"?(state.project?`Projeto \u00b7 ${displayProject(state.project)}`:"Projetos"):`${state.mode==="calls"?"Chamados":state.mode==="repeat"?"Reincid\u00eancia":"Motivos"} \u00b7 ${periodLabel(data.period)}`;
    $("#geo-title").textContent=title;
    ui.panelFlag.src=flags[code]||""; ui.panelFlag.alt=`Bandeira de ${stateNames[code]||code}`;
    const count=metricValue(row); ui.panelTotal.textContent=number.format(count);
    ui.panelScope.textContent=`${modeLabels[state.mode]} · ${["base","projects"].includes(state.mode)?"Atual":`${data.period?.date_from||""} – ${data.period?.date_to||""}`}`;
    ui.panelContext.textContent=`${number.format(row.total_links||0)} links CMDB · ${number.format(row.ticket_count||0)} tickets no período · ${number.format(row.recurrence_links||0)} links reincidentes.`;
    listRows(ui.clients,state.mode==="repeat"?row.recurrence_client_counts:["calls","motives"].includes(state.mode)?row.ticket_client_counts:row.client_counts); listRows(ui.projects,Object.entries(["calls","repeat","motives"].includes(state.mode)?(row.ticket_project_counts||{}):(row.project_counts||{})).reduce((items,[key,value])=>{const label=displayProject(key);items[label]=(items[label]||0)+value;return items;},{})); listRows(ui.providers,["calls","repeat","motives"].includes(state.mode)?row.ticket_provider_counts:row.provider_counts); listRows(ui.cities,["calls","repeat","motives"].includes(state.mode)?row.ticket_city_counts:row.city_counts);
    listRows(ui.statuses,Object.fromEntries(Object.entries(row.ticket_status_counts||{}).map(([key,value])=>[statusLabels[key]||"Status n?o mapeado",value])),"tickets");
    listRows(ui.reasons,state.mode==="calls"?row.ticket_reason_counts:row.reason_counts,"tickets");
    const sectionData={clients:["base","projects","repeat","calls","motives"].includes(state.mode)&&(state.mode==="repeat"?Object.keys(row.recurrence_client_counts||{}).length>0:["calls","motives"].includes(state.mode)?Object.keys(row.ticket_client_counts||{}).length>0:Object.keys(row.client_counts||{}).length>0),coverage:state.mode==="base"&&(row.total_links||0)>0,status:state.mode==="calls"&&Object.keys(row.ticket_status_counts||{}).length>0,projects:["base","projects","calls","repeat","motives"].includes(state.mode)&&Object.keys(["calls","repeat","motives"].includes(state.mode)?(row.ticket_project_counts||{}):(row.project_counts||{})).length>0,providers:["base","projects","calls","repeat","motives"].includes(state.mode)&&Object.keys(["calls","repeat","motives"].includes(state.mode)?(row.ticket_provider_counts||{}):(row.provider_counts||{})).length>0,cities:["base","projects","calls","repeat","motives"].includes(state.mode)&&Object.keys(["calls","repeat","motives"].includes(state.mode)?(row.ticket_city_counts||{}):(row.city_counts||{})).length>0,reasons:["calls","repeat","motives"].includes(state.mode)&&Object.keys(state.mode==="calls"?(row.ticket_reason_counts||{}):(row.reason_counts||{})).length>0,links:["base","projects","calls","repeat","motives"].includes(state.mode)&&(detail.link_total||0)>0,tickets:["calls","repeat","motives"].includes(state.mode)&&(detail.ticket_total||0)>0};
    page.querySelectorAll("[data-panel-section]").forEach(section=>{section.hidden=!sectionData[section.dataset.panelSection];});
    const links=detail.links||[];
    ui.links.innerHTML=links.slice(0,8).map(link=>`<div class="panel-reason-row"><span>${esc(link.number||link.name||"Link sem designa??o")}<small>${esc(link.city||"Cidade n?o informada")} ? ${esc(link.provider||"Provedor n?o identificado")}${link.ticket_count?` ? ${number.format(link.ticket_count)} tickets`:""}</small></span><b>${esc(`Projeto: ${link.project?displayProject(link.project):"Projeto n?o identificado"}`)}</b></div>`).join("")||'<p class="panel-empty">Nenhum link para este recorte.</p>';
    if(detail.link_total>8) ui.links.insertAdjacentHTML("beforeend",`<p class="panel-empty">Exibindo 8 de ${number.format(detail.link_total)} links. Use “Ver links na Base” para a lista completa.</p>`);
    const tickets=detail.tickets||[];ticketRows=tickets;
    ui.tickets.innerHTML=tickets.slice(0,8).map((ticket,index)=>`<button type="button" class="panel-ticket-button" data-ticket-index="${index}"><span>${esc(ticket.ticket_number||"Ticket")}<small>${esc(statusLabels[ticket.status]||"Status n?o mapeado")} ? ${esc(ticket.link||"Link n?o informado")}</small></span><b>${esc(ticket.closing_reason||"Detalhes")}</b></button>`).join("")||'<p class="panel-empty">Nenhum ticket associado neste recorte.</p>';
    if(detail.ticket_total>8) ui.tickets.insertAdjacentHTML("beforeend",`<p class="panel-empty">Exibindo 8 de ${number.format(detail.ticket_total)} tickets.</p>`);
    const base=new URL(root.dataset.baseUrl,location.origin);base.searchParams.set("uf",code);if(state.client!=="all")base.searchParams.set("cliente",state.client);if(state.project)base.searchParams.set("projeto",state.project);if(state.provider)base.searchParams.set("provider_id",state.provider);ui.openBase.href=base.pathname+base.search;
    const cockpit=new URL(root.dataset.cockpitUrl,location.origin);cockpit.searchParams.set("group_by","uf");cockpit.searchParams.set("uf",code);
    cockpit.searchParams.set("metric",state.mode==="motives"?"resolved_closed_tickets":state.mode==="repeat"?"recurrences":"tickets");
    if(data.period?.date_from)cockpit.searchParams.set("start",data.period.date_from);if(data.period?.date_to)cockpit.searchParams.set("end",data.period.date_to);
    if(state.mode==="motives"&&state.reason)cockpit.searchParams.set("termination_reason",state.reason);ui.openCockpit.href=cockpit.pathname+cockpit.search;
    ui.openCockpit.textContent=["base","projects"].includes(state.mode)?"Abrir UF no Cockpit":"Analisar no Cockpit";
    openPanel(); ui.announce.textContent=`${stateNames[code]}, ${number.format(count)} ${modeLabels[state.mode]}.`;
  }
  function openPanel(){panel.hidden=false;panel.inert=false;panel.setAttribute("aria-hidden","false");panelBackdrop.classList.add("is-visible");requestAnimationFrame(()=>panel.classList.add("is-open"));root.classList.add("has-selection");}
  function closePanel(){panel.classList.remove("is-open");panel.inert=true;panel.setAttribute("aria-hidden","true");panelBackdrop.classList.remove("is-visible");root.classList.remove("has-selection");setTimeout(()=>{if(!state.selectedUF)panel.hidden=true;},220);}
  function selectState(code,zoom=true){if(!stateNames[code])return;state.selectedUF=code;syncUrl();ui.breadcrumb.hidden=false;ui.selectedName.textContent=stateNames[code];renderMap();loadState(code).catch(error=>showError(error.message,"Detalhes indisponíveis"));if(zoom){const feature=geojson.features.find(item=>item.properties.sigla===code);if(feature)fitState(feature);}}
  function clearSelection(){state.selectedUF="";syncUrl();ui.breadcrumb.hidden=true;closePanel();renderMap();fitBrazil();}
  function fitState(feature){const points=[];const walk=value=>Array.isArray(value)&& (typeof value[0]==="number"?points.push(value):value.forEach(walk));walk(feature.geometry.coordinates);if(!points.length)return;const bounds=points.reduce((box,p)=>box.extend(p),new mapboxgl.LngLatBounds(points[0],points[0]));const mobile=window.matchMedia("(max-width: 900px)").matches;const padding={top:30,right:mobile?30:(panel.offsetWidth||390)+30,bottom:mobile?(panel.offsetHeight||410)+30:30,left:national.classList.contains("is-collapsed")?35:290};map.fitBounds(bounds,{padding,maxZoom:5.5,duration:650});}
  function fitBrazil(){map.fitBounds([[-76,-37],[-32,8]],{padding:{top:34,right:35,bottom:34,left:national.classList.contains("is-collapsed")?40:300},maxZoom:4.4,duration:550});}
  function searchResults(){const query=norm(ui.search.value);if(!query){ui.results.hidden=true;return;}const found=geojson.features.filter(feature=>norm(feature.properties.nome).includes(query)||norm(feature.properties.sigla).startsWith(query)).slice(0,8);ui.results.innerHTML=found.map(feature=>`<button type="button" class="state-search-option" role="option" data-search-code="${feature.properties.sigla}"><span>${esc(feature.properties.nome)}</span><small>${feature.properties.sigla}</small></button>`).join("");ui.results.hidden=!found.length;searchIndex=-1;}
  ui.ticketClose.addEventListener("click",closeTicket);
  ui.ticketModal.addEventListener("click",event=>{if(event.target===ui.ticketModal)closeTicket();});
  ui.tickets.addEventListener("click",event=>{const button=event.target.closest("[data-ticket-index]");if(button)openTicket(ticketRows[Number(button.dataset.ticketIndex)]||{},button);});
  document.addEventListener("keydown",event=>{if(ui.ticketModal.hidden)return;if(event.key==="Escape"){event.preventDefault();closeTicket();return;}if(event.key==="Tab"){const focusables=[ui.ticketClose,...ui.ticketModal.querySelectorAll("a[href],button:not([disabled]),[tabindex]:not([tabindex='-1'])")];const first=focusables[0],last=focusables[focusables.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}});
  function bind(){
    page.querySelectorAll("[data-mode]").forEach(button=>button.addEventListener("click",()=>{state.mode=button.dataset.mode;if(state.mode!=="calls"){state.status="";state.priority="";}updateModeControls();fetchData().catch(error=>showError("Não foi possível carregar o recorte selecionado. Tente novamente."));}));
    page.querySelectorAll("[data-client]").forEach(button=>button.addEventListener("click",()=>{state.client=button.dataset.client;page.querySelectorAll("[data-client]").forEach(item=>{const selected=item===button;item.classList.toggle("is-selected",selected);item.setAttribute("aria-pressed",String(selected));});state.project="";ui.project.value="";fetchData().catch(()=>showError("Não foi possível filtrar os dados. Tente novamente."));}));
    ui.project.addEventListener("change",()=>{state.project=ui.project.value;fetchData().catch(()=>showError("Não foi possível filtrar os dados. Tente novamente."));});
    ui.provider.addEventListener("change",()=>{state.provider=ui.provider.value;fetchData().catch(()=>showError("Não foi possível filtrar os dados. Tente novamente."));});
    ui.period.addEventListener("change",()=>{state.period=ui.period.value;state.dateFrom="";state.dateTo="";ui.dates.hidden=state.period!=="custom";if(state.period!=="custom")fetchData().catch(()=>showError("Não foi possível carregar o período selecionado."));});
    $("[data-apply-period]").addEventListener("click",()=>{state.dateFrom=ui.dateFrom.value;state.dateTo=ui.dateTo.value;if(state.dateFrom&&state.dateTo&&state.dateFrom>state.dateTo){ui.dateTo.setCustomValidity("A data final deve ser igual ou posterior à inicial.");ui.dateTo.reportValidity();return;}ui.dateTo.setCustomValidity("");fetchData().catch(()=>showError("Não foi possível carregar o período selecionado."));});
    ui.reason.addEventListener("change",()=>{state.reason=ui.reason.value;fetchData().catch(()=>showError("Não foi possível filtrar os motivos."));});
    ui.status.addEventListener("change",()=>{state.status=ui.status.value;fetchData().catch(()=>showError("N\u00e3o foi poss\u00edvel filtrar o status."));});
    ui.priority.addEventListener("change",()=>{state.priority=ui.priority.value;fetchData().catch(()=>showError("N\u00e3o foi poss\u00edvel filtrar a prioridade."));});
    ui.search.addEventListener("input",searchResults);ui.search.addEventListener("keydown",event=>{if(event.key==="Escape"){ui.results.hidden=true;ui.search.blur();}else if(event.key==="Enter"){const first=ui.results.querySelector("[data-search-code]");if(first){event.preventDefault();selectState(first.dataset.searchCode);ui.results.hidden=true;}}});
    ui.results.addEventListener("click",event=>{const button=event.target.closest("[data-search-code]");if(button){selectState(button.dataset.searchCode);ui.results.hidden=true;ui.search.value="";}});
    $("[data-national-collapse]").addEventListener("click",()=>{state.collapsed=true;national.classList.add("is-collapsed");national.querySelector("[data-national-content]").inert=true;$("[data-national-expand]").hidden=false;$("[data-national-collapse]").setAttribute("aria-expanded","false");setTimeout(()=>map?.resize(),240);});
    $("[data-national-expand]").addEventListener("click",()=>{state.collapsed=false;national.classList.remove("is-collapsed");national.querySelector("[data-national-content]").inert=false;$("[data-national-expand]").hidden=true;$("[data-national-collapse]").setAttribute("aria-expanded","true");setTimeout(()=>map?.resize(),240);});
    page.querySelectorAll("[data-national-tab]").forEach(button=>button.addEventListener("click",()=>setPanelTab(button.dataset.nationalTab)));
    $("[data-brazil-link]").addEventListener("click",clearSelection);$("[data-panel-close]").addEventListener("click",clearSelection);panelBackdrop.addEventListener("click",clearSelection);
    $("[data-map-retry]").addEventListener("click",initialize);
    window.addEventListener("arion:themechange",event=>{const next=event.detail?.theme||theme();if(map?.getLayer("arion-background"))map.setPaintProperty("arion-background","background-color",next==="light"?"#e9ece8":"#080909");renderMap();});
  }
  async function initialize(){
    if(!root.dataset.token){showError("Token público do Mapbox não configurado.");return;}
    if(!window.mapboxgl){showError("Não foi possível carregar o componente do mapa. Verifique a conexão.");return;}
    message.hidden=false;errorBox.hidden=true;
    try{
      const response=await fetch(root.dataset.geojsonUrl,{signal:AbortSignal.timeout(20000)});if(!response.ok)throw new Error("Não foi possível carregar as geometrias locais.");geojson=await response.json();
      if(geojson.type!=="FeatureCollection"||geojson.features.length!==27)throw new Error("A base geográfica precisa conter as 27 UFs.");
      await fetchData();window.mapboxgl.accessToken=root.dataset.token;
      map=new window.mapboxgl.Map({container:mapElement,style:{version:8,sources:{},layers:[{id:"arion-background",type:"background",paint:{"background-color":theme()==="light"?"#e9ece8":"#080909"}}]},bounds:[[-76,-37],[-32,8]],fitBoundsOptions:{padding:35},minZoom:2.5,maxZoom:8,renderWorldCopies:false,attributionControl:true,cooperativeGestures:false});
      map.addControl(new window.mapboxgl.NavigationControl({showCompass:false}),"top-right");map.dragRotate.disable();map.touchZoomRotate.disableRotation();
      map.on("load",()=>{try{map.addSource("arion-states",{type:"geojson",data:featureCollection(),promoteId:"sigla"});map.addLayer({id:"arion-state-fill",type:"fill",source:"arion-states",paint:{"fill-color":fillExpression(),"fill-opacity":.9}});map.addLayer({id:"arion-state-outline",type:"line",source:"arion-states",paint:{"line-color":theme()==="light"?"rgba(35,48,39,.34)":"rgba(225,235,228,.28)","line-width":1}});map.on("click","arion-state-fill",event=>{const code=event.features?.[0]?.properties?.sigla;if(code)selectState(code);});map.on("mouseenter","arion-state-fill",()=>map.getCanvas().style.cursor="pointer");map.on("mouseleave","arion-state-fill",()=>{map.getCanvas().style.cursor="";popup?.remove();});map.on("mousemove","arion-state-fill",event=>showTooltip(event));mapLoaded=true;message.hidden=true;renderMap();if(state.selectedUF)selectState(state.selectedUF,false);else fitBrazil();}catch(_error){showError("Não foi possível preparar as unidades do mapa.");}});
      map.on("error",()=>{if(!mapLoaded)showError("Confira a configuração pública e a conexão do Mapbox.");});
    }catch(_error){showError("Não foi possível carregar os dados locais do Mapa. Tente novamente.");}
  }
  let popup=null;
  function showTooltip(event){
    const code=event.features?.[0]?.properties?.sigla;if(!code)return;
    const row=data?.states?.[code]||{},title=stateNames[code]||code,amount=metricValue(row);
    const dominant=dominantClientLabel(row);
    const wrapper=document.createElement("div");wrapper.className="state-tooltip";
    const heading=document.createElement("strong");heading.textContent=title;
    const value=document.createElement("p");const metricLabel=state.mode==="motives"&&state.reason?state.reason:modeLabels[state.mode];value.textContent=`${number.format(amount)} ${metricLabel}`;
    const detail=document.createElement("small");
    detail.textContent=["base","projects"].includes(state.mode)?`Cliente predominante: ${dominant} \u00b7 Cobertura de Cliente: ${(row.client_coverage||0).toLocaleString("pt-BR",{maximumFractionDigits:1})}%`:state.mode==="calls"?`${number.format(row.affected_links||0)} links afetados`:state.mode==="repeat"?`${number.format(row.recurrence_tickets||0)} tickets nos links reincidentes`:`${number.format(row.terminal_link_count||row.terminal_links||0)} links com encerramento`;
    wrapper.append(heading,value,detail);
    if(!popup)popup=new window.mapboxgl.Popup({closeButton:false,closeOnClick:false,offset:8,className:"geo-popup"});
    popup.setDOMContent(wrapper).setLngLat(event.lngLat).addTo(map);
  }

  updateModeControls();
  page.querySelectorAll("[data-client]").forEach(item=>{const selected=item.dataset.client===state.client;item.classList.toggle("is-selected",selected);item.setAttribute("aria-pressed",String(selected));});
  bind();initialize();
})();
