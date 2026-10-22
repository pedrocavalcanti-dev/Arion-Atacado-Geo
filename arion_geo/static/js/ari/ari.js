(() => {
  const app = document.querySelector('[data-ari-app]');
  if (!app) return;

  const home = app.dataset.homeUrl;
  const endpoint = (template, id) => template.replace('00000000-0000-0000-0000-000000000000', id);
  const history = app.querySelector('[data-history]');
  const messages = app.querySelector('[data-messages]');
  const welcome = app.querySelector('[data-welcome]');
  const conversationView = app.querySelector('[data-conversation-view]');
  const suggestions = app.querySelector('[data-suggestions]');
  const composer = app.querySelector('[data-composer]');
  const input = app.querySelector('[data-prompt-input]');
  const sendButton = app.querySelector('[data-send]');
  const errorBox = app.querySelector('[data-error]');
  const titleNode = app.querySelector('[data-current-title]');
  const dialog = document.querySelector('[data-rename-dialog]');
  const renameForm = document.querySelector('[data-rename-form]');
  const renameInput = document.querySelector('#ari-rename-input');
  const renameError = document.querySelector('[data-rename-error]');
  const search = app.querySelector('[data-history-search]');
  const clearSearch = app.querySelector('[data-clear-search]');
  const backdrop = app.querySelector('[data-drawer-close]');
  const fileInput = app.querySelector('[data-file-input]');
  const fileQueue = app.querySelector('[data-attachment-queue]');
  const csrfToken = composer.querySelector('[name=csrfmiddlewaretoken]').value;
  let activeId = app.dataset.activeId || '';
  let renameTarget = null;
  let selectedFiles = [];

  const api = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: 'same-origin',
      ...options,
      headers: {
        'X-CSRFToken': csrfToken,
        ...(options.body && !(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Não foi possível concluir a solicitação.');
    return data;
  };

  const setError = (message = '') => {
    errorBox.textContent = message;
    errorBox.hidden = !message;
  };

  const sizeInput = () => {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 144)}px`;
  };

  const node = (tag, className, text) => {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = String(text);
    return item;
  };

  const byteLabel = (size) => {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} KB`;
    return `${(size / (1024 * 1024)).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`;
  };

  const renderFileList = (container, items, removable = false) => {
    if (!items || !items.length) return;
    const list = node('div', removable ? 'ari-attachment-list ari-attachment-list--queue' : 'ari-attachment-list');
    items.forEach((file, index) => {
      const item = node('div', 'ari-file-item');
      const icon = node('span', 'ari-file-icon');
      icon.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l5 5v13H7z"/><path d="M14 3v6h5M10 14h6M10 17h6"/></svg>';
      const copy = node('span', 'ari-file-copy');
      const name = node('span', 'ari-file-name', file.name || file.original_name || 'Arquivo');
      name.title = file.name || file.original_name || 'Arquivo';
      const size = node('small', '', byteLabel(Number(file.size) || 0));
      copy.append(name, size);
      item.append(icon, copy);
      if (removable) {
        const remove = node('button', 'ari-file-remove', '×');
        remove.type = 'button';
        remove.dataset.removeFile = String(index);
        remove.setAttribute('aria-label', `Remover ${file.name}`);
        item.append(remove);
      } else if (file.download_url) {
        const download = node('a', 'ari-file-download', 'Baixar');
        download.href = file.download_url;
        download.setAttribute('aria-label', `Baixar ${file.original_name}`);
        download.rel = 'noreferrer';
        item.append(download);
      }
      list.append(item);
    });
    container.append(list);
  };

  const renderTable = (container, metadata) => {
    if (!Array.isArray(metadata.columns) || !Array.isArray(metadata.rows)) return;
    const wrap = node('div', 'ari-rich-table-wrap');
    const table = node('table', 'ari-rich-table');
    const head = node('thead');
    const headRow = node('tr');
    metadata.columns.forEach((column) => headRow.append(node('th', '', column)));
    head.append(headRow);
    const body = node('tbody');
    metadata.rows.forEach((row) => {
      const tr = node('tr');
      row.forEach((cell) => tr.append(node('td', '', cell)));
      body.append(tr);
    });
    table.append(head, body);
    wrap.append(table);
    container.append(wrap);
  };

  const renderKpis = (container, kpis) => {
    if (!Array.isArray(kpis)) return;
    const grid = node('div', 'ari-rich-kpis');
    kpis.forEach((kpi) => {
      const item = node('div', 'ari-rich-kpi');
      item.append(node('span', '', kpi.label), node('strong', '', kpi.value));
      grid.append(item);
    });
    container.append(grid);
  };

  const renderList = (container, items, className = 'ari-rich-list') => {
    if (!Array.isArray(items) || !items.length) return;
    const list = node('ul', className);
    items.forEach((item) => list.append(node('li', '', item)));
    container.append(list);
  };

  const renderActions = (container, actions) => {
    if (!Array.isArray(actions) || !actions.length) return;
    const group = node('div', 'ari-response-actions');
    actions.slice(0, 4).forEach((action) => {
      const button = node('button', '', action.label);
      button.type = 'button';
      button.dataset.quickPrompt = action.prompt;
      group.append(button);
    });
    container.append(group);
  };

  const renderArtifact = (container, metadata, type) => {
    if (!metadata.artifact_url) return;
    const card = node('section', 'ari-artifact-card');
    const icon = node('span', 'ari-artifact-icon');
    icon.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h10l4 4v14H5z"/><path d="M15 3v5h4M8 13h8M8 17h5"/></svg>';
    const copy = node('div', 'ari-artifact-copy');
    copy.append(node('strong', '', metadata.artifact_title || (type === 'dashboard' ? 'Dashboard demonstrativo' : 'Relatório demonstrativo')),
      node('small', '', 'Artefato HTML · dados fictícios'));
    const links = node('div', 'ari-artifact-links');
    const open = node('a', '', type === 'dashboard' ? 'Abrir dashboard' : 'Abrir relatório');
    open.href = metadata.artifact_url;
    open.target = '_blank';
    open.rel = 'noopener noreferrer';
    links.append(open);
    if (metadata.download_url) {
      const download = node('a', '', 'Baixar HTML');
      download.href = metadata.download_url;
      download.rel = 'noreferrer';
      links.append(download);
    }
    card.append(icon, copy, links);
    container.append(card);
  };

  const renderStructured = (body, messageType, metadata) => {
    if (metadata.demo_label) body.append(node('span', 'ari-data-badge', metadata.demo_label));
    if (metadata.title) body.append(node('h3', 'ari-rich-title', metadata.title));
    switch (messageType) {
      case 'summary':
        renderKpis(body, metadata.kpis);
        renderList(body, metadata.insights, 'ari-rich-list');
        renderActions(body, metadata.next_actions);
        break;
      case 'comparison': {
        const columns = node('div', 'ari-comparison-head');
        columns.append(node('strong', '', metadata.left_label), node('strong', '', metadata.right_label));
        body.append(columns);
        (metadata.metrics || []).forEach((metric) => {
          const row = node('div', 'ari-comparison-row');
          row.append(node('span', 'ari-comparison-value', `${metric.left}${metric.suffix}`));
          const center = node('div', 'ari-comparison-center');
          center.append(node('span', '', metric.label));
          const bars = node('div', 'ari-comparison-bars');
          const max = Math.max(Number(metric.left) || 0, Number(metric.right) || 0, 1);
          const leftBar = node('i', 'ari-comparison-bar ari-comparison-bar--left');
          leftBar.style.width = `${Math.max(5, (Number(metric.left) / max) * 100)}%`;
          const rightBar = node('i', 'ari-comparison-bar ari-comparison-bar--right');
          rightBar.style.width = `${Math.max(5, (Number(metric.right) / max) * 100)}%`;
          bars.append(leftBar, rightBar);
          center.append(bars);
          row.append(center, node('span', 'ari-comparison-value', `${metric.right}${metric.suffix}`));
          body.append(row);
        });
        renderList(body, metadata.insights, 'ari-rich-list');
        renderActions(body, metadata.next_actions);
        break;
      }
      case 'table':
        renderTable(body, metadata);
        break;
      case 'action_plan':
        body.append(node('p', 'ari-structured-intro', `Objetivo: ${metadata.objective || ''}`));
        body.append(node('p', 'ari-plan-priority', `Prioridade ${metadata.priority || ''}`));
        renderList(body, metadata.actions, 'ari-rich-list ari-rich-list--numbered');
        body.append(node('p', 'ari-plan-owner', `Responsável sugerido: ${metadata.owner || 'Equipe NOC'} · Prazo sugerido: ${metadata.deadline || '30 dias'}`));
        break;
      case 'alert': {
        const alert = node('section', `ari-alert-box ari-alert-box--${metadata.level || 'info'}`);
        alert.append(node('span', 'ari-alert-label', `Alerta operacional · ${metadata.demo_label || 'Simulação'}`));
        alert.append(node('strong', 'ari-alert-title', metadata.title));
        const values = node('div', 'ari-alert-values');
        values.append(node('span', '', `Atual ${metadata.current}`), node('span', '', `Meta ${metadata.target}`));
        alert.append(values, node('p', '', `Impacto: ${metadata.impact || ''}`), node('p', '', `Sugestão: ${metadata.suggestion || ''}`));
        body.append(alert);
        break;
      }
      case 'goal': {
        const progress = node('div', 'ari-goal-progress');
        const track = node('div', 'ari-goal-track');
        const fill = node('span', 'ari-goal-fill');
        fill.style.width = `${Math.max(0, Math.min(100, Number(metadata.current) || 0))}%`;
        track.append(fill);
        progress.append(track, node('strong', '', `${metadata.current}%`));
        body.append(progress, node('p', 'ari-goal-summary', `Atual ${metadata.current}% · Meta ${metadata.target}% · Diferença ${metadata.difference}`),
          node('p', 'ari-goal-status', `Status: ${metadata.status}`));
        break;
      }
      case 'report':
        renderList(body, metadata.sections, 'ari-report-sections');
        renderArtifact(body, metadata, messageType);
        break;
      case 'dashboard':
        renderKpis(body, metadata.kpis);
        renderArtifact(body, metadata, messageType);
        break;
      default:
        break;
    }
    if (metadata.sources) {
      const source = node('div', 'ari-source-note');
      source.append(node('span', '', `Fontes futuras: ${metadata.sources}`), node('small', '', metadata.sources_status || 'Não conectadas à ARI'));
      body.append(source);
    }
  };

  const makeMessage = ({ role, content, message_type = 'text', metadata = {}, attachments = [] }) => {
    const article = document.createElement('article');
    article.className = `ari-message ari-message--${role === 'assistant' ? 'assistant' : 'user'}`;
    article.dataset.messageRole = role;
    const label = document.createElement('div');
    label.className = 'ari-message-label';
    if (role === 'assistant') {
      const mark = document.createElement('span');
      mark.className = 'ari-mini-mark';
      mark.textContent = '✦';
      label.append(mark, document.createTextNode(' ARI'));
    } else {
      label.textContent = 'Você';
    }
    const body = document.createElement('div');
    body.className = 'ari-message-content';
    body.append(node('p', 'ari-message-text', content));
    if (role === 'assistant') renderStructured(body, message_type, metadata || {});
    renderFileList(body, attachments);
    article.append(label, body);
    return article;
  };

  const renderMessages = (items) => {
    messages.replaceChildren(...items.map(makeMessage));
    messages.scrollTop = messages.scrollHeight;
  };

  const renderQueue = () => {
    fileQueue.replaceChildren();
    fileQueue.hidden = !selectedFiles.length;
    renderFileList(fileQueue, selectedFiles, true);
  };

  const openConversation = async (row, { updateHistory = true } = {}) => {
    try {
      const data = await api(row.dataset.detailUrl);
      activeId = data.conversation.id;
      app.dataset.activeId = activeId;
      titleNode.textContent = data.conversation.title;
      welcome.hidden = true;
      conversationView.hidden = false;
      suggestions.hidden = true;
      renderMessages(data.messages);
      history.querySelectorAll('[data-history-row]').forEach((item) => item.classList.toggle('is-active', item === row));
      if (updateHistory) window.history.pushState({}, '', row.dataset.pageUrl);
      closeDrawer();
      input.focus({ preventScroll: true });
    } catch (error) {
      setError(error.message);
    }
  };

  const closeDrawer = () => {
    app.classList.remove('is-drawer-open');
    backdrop.hidden = true;
  };

  const showHome = (push = true) => {
    activeId = '';
    app.dataset.activeId = '';
    titleNode.textContent = 'Nova conversa';
    welcome.hidden = false;
    conversationView.hidden = true;
    suggestions.hidden = false;
    history.querySelectorAll('[data-history-row]').forEach((row) => row.classList.remove('is-active'));
    messages.replaceChildren();
    setError();
    if (push && window.location.pathname !== home) window.history.pushState({}, '', home);
    closeDrawer();
    input.focus({ preventScroll: true });
  };

  const makeRow = (conversation, pageUrl) => {
    let group = history.querySelector('[data-history-group]');
    if (!group) {
      group = document.createElement('section');
      group.className = 'ari-history-group';
      group.dataset.historyGroup = '';
      const heading = document.createElement('h2');
      heading.textContent = 'Hoje';
      group.append(heading);
      history.replaceChildren(group);
    }
    let row = history.querySelector(`[data-conversation-id="${conversation.id}"]`);
    if (!row) {
      row = document.createElement('div');
      row.className = 'ari-history-row';
      row.dataset.historyRow = '';
      row.dataset.conversationId = conversation.id;
      const anchor = document.createElement('a');
      anchor.href = pageUrl;
      anchor.dataset.openConversation = '';
      const title = document.createElement('span');
      title.className = 'ari-history-title';
      anchor.append(title);
      const menu = document.createElement('button');
      menu.className = 'ari-row-menu';
      menu.type = 'button';
      menu.dataset.rowMenu = '';
      menu.setAttribute('aria-label', `Ações para ${conversation.title}`);
      menu.setAttribute('aria-expanded', 'false');
      menu.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg>';
      const actions = document.createElement('div');
      actions.className = 'ari-row-actions';
      actions.dataset.rowActions = '';
      actions.hidden = true;
      actions.innerHTML = '<button type="button" data-rename>Renomear</button><button type="button" data-delete>Excluir</button>';
      row.append(anchor, menu, actions);
      group.prepend(row);
    }
    row.dataset.title = conversation.title.toLocaleLowerCase();
    row.dataset.detailUrl = endpoint(app.dataset.detailTemplate, conversation.id);
    row.dataset.pageUrl = pageUrl;
    row.querySelector('.ari-history-title').textContent = conversation.title;
    const menuButton = row.querySelector('[data-row-menu]');
    menuButton.setAttribute('aria-label', `Ações para ${conversation.title}`);
    row.querySelector('[data-open-conversation]').href = pageUrl;
    row.classList.add('is-active');
    history.querySelectorAll('[data-history-row]').forEach((item) => { if (item !== row) item.classList.remove('is-active'); });
    updateSearch();
    return row;
  };

  const updateSearch = () => {
    const term = (search.value || '').trim().toLocaleLowerCase();
    const rows = [...history.querySelectorAll('[data-history-row]')];
    let visibleCount = 0;
    rows.forEach((row) => {
      const visible = (row.dataset.title || '').includes(term);
      row.hidden = !visible;
      if (visible) visibleCount += 1;
    });
    history.querySelectorAll('[data-history-group]').forEach((group) => {
      group.hidden = !group.querySelector('[data-history-row]:not([hidden])');
    });
    let empty = history.querySelector('[data-search-empty]');
    if (!empty) {
      empty = document.createElement('p');
      empty.className = 'ari-history-empty';
      empty.dataset.searchEmpty = '';
      empty.textContent = 'Nenhuma conversa encontrada.';
      history.append(empty);
    }
    empty.hidden = !term || visibleCount > 0;
    clearSearch.hidden = !search.value;
  };

  const send = async (content) => {
    const prompt = (content || '').trim();
    if ((!prompt && !selectedFiles.length) || sendButton.disabled) return;
    setError();
    sendButton.disabled = true;
    input.disabled = true;
    try {
      const url = activeId ? endpoint(app.dataset.sendTemplate, activeId) : app.dataset.createUrl;
      let body;
      if (selectedFiles.length) {
        body = new FormData();
        body.append('content', prompt);
        selectedFiles.forEach((file) => body.append('files', file, file.name));
      } else {
        body = JSON.stringify({ content: prompt });
      }
      const data = await api(url, { method: 'POST', body });
      activeId = data.conversation.id;
      app.dataset.activeId = activeId;
      titleNode.textContent = data.conversation.title;
      welcome.hidden = true;
      conversationView.hidden = false;
      suggestions.hidden = true;
      renderMessages(data.messages);
      makeRow(data.conversation, data.page_url);
      if (window.location.pathname !== data.page_url) window.history.pushState({}, '', data.page_url);
      input.value = '';
      selectedFiles = [];
      fileInput.value = '';
      renderQueue();
      sizeInput();
    } catch (error) {
      setError(error.message);
    } finally {
      sendButton.disabled = false;
      input.disabled = false;
      input.focus({ preventScroll: true });
    }
  };

  app.querySelector('[data-new-conversation]').addEventListener('click', () => showHome());
  app.querySelector('[data-sidebar-toggle]').addEventListener('click', (event) => {
    const collapsed = app.classList.toggle('is-collapsed');
    event.currentTarget.setAttribute('aria-expanded', String(!collapsed));
    localStorage.setItem('arion:ari-sidebar-collapsed', String(collapsed));
  });
  if (localStorage.getItem('arion:ari-sidebar-collapsed') === 'true' && window.matchMedia('(min-width: 801px)').matches) {
    app.classList.add('is-collapsed');
    app.querySelector('[data-sidebar-toggle]').setAttribute('aria-expanded', 'false');
  }
  app.querySelectorAll('[data-drawer-toggle]').forEach((button) => button.addEventListener('click', () => {
    const open = app.classList.toggle('is-drawer-open');
    backdrop.hidden = !open;
  }));
  backdrop.addEventListener('click', closeDrawer);

  history.addEventListener('click', (event) => {
    const row = event.target.closest('[data-history-row]');
    if (!row) return;
    const openLink = event.target.closest('[data-open-conversation]');
    if (openLink) {
      event.preventDefault();
      openConversation(row);
      return;
    }
    const menu = event.target.closest('[data-row-menu]');
    if (menu) {
      history.querySelectorAll('[data-row-actions]').forEach((actions) => { actions.hidden = true; });
      history.querySelectorAll('[data-row-menu]').forEach((button) => button.setAttribute('aria-expanded', 'false'));
      const actions = row.querySelector('[data-row-actions]');
      actions.hidden = false;
      menu.setAttribute('aria-expanded', 'true');
      return;
    }
    if (event.target.closest('[data-rename]')) {
      renameTarget = row;
      renameInput.value = row.querySelector('.ari-history-title').textContent;
      renameError.hidden = true;
      dialog.showModal();
      renameInput.focus();
      return;
    }
    if (event.target.closest('[data-delete]')) {
      if (!window.confirm('Excluir esta conversa? Esta ação não pode ser desfeita.')) return;
      api(endpoint(app.dataset.deleteTemplate, row.dataset.conversationId), { method: 'POST' }).then(() => {
        const wasActive = row.dataset.conversationId === activeId;
        row.remove();
        if (!history.querySelector('[data-history-row]')) {
          const empty = document.createElement('p');
          empty.className = 'ari-history-empty';
          empty.textContent = 'Suas conversas aparecerão aqui.';
          history.replaceChildren(empty);
        }
        if (wasActive) showHome();
        else updateSearch();
      }).catch((error) => setError(error.message));
    }
  });

  document.addEventListener('click', (event) => {
    if (!event.target.closest('[data-history-row]')) {
      history.querySelectorAll('[data-row-actions]').forEach((actions) => { actions.hidden = true; });
      history.querySelectorAll('[data-row-menu]').forEach((button) => button.setAttribute('aria-expanded', 'false'));
    }
  });
  composer.addEventListener('submit', (event) => {
    event.preventDefault();
    send(input.value);
  });
  input.addEventListener('input', sizeInput);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      composer.requestSubmit();
    }
  });
  app.querySelectorAll('[data-prompt]').forEach((button) => button.addEventListener('click', () => send(button.dataset.prompt)));
  messages.addEventListener('click', (event) => {
    const button = event.target.closest('[data-quick-prompt]');
    if (button) send(button.dataset.quickPrompt);
  });
  app.querySelector('[data-attach-trigger]').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    selectedFiles = [...selectedFiles, ...Array.from(fileInput.files || [])];
    fileInput.value = '';
    setError();
    renderQueue();
  });
  fileQueue.addEventListener('click', (event) => {
    const remove = event.target.closest('[data-remove-file]');
    if (!remove) return;
    selectedFiles.splice(Number(remove.dataset.removeFile), 1);
    renderQueue();
  });
  search.addEventListener('input', updateSearch);
  clearSearch.addEventListener('click', () => { search.value = ''; updateSearch(); search.focus(); });

  renameForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!renameTarget) return;
    try {
      const data = await api(endpoint(app.dataset.renameTemplate, renameTarget.dataset.conversationId), {
        method: 'POST', body: JSON.stringify({ title: renameInput.value }),
      });
      renameTarget.querySelector('.ari-history-title').textContent = data.conversation.title;
      renameTarget.dataset.title = data.conversation.title.toLocaleLowerCase();
      renameTarget.querySelector('[data-row-menu]').setAttribute('aria-label', `Ações para ${data.conversation.title}`);
      if (renameTarget.dataset.conversationId === activeId) titleNode.textContent = data.conversation.title;
      dialog.close();
      updateSearch();
    } catch (error) {
      renameError.textContent = error.message;
      renameError.hidden = false;
    }
  });
  document.querySelector('[data-cancel-rename]').addEventListener('click', () => dialog.close());
  search.closest('form').addEventListener('submit', (event) => event.preventDefault());
  window.addEventListener('popstate', () => {
    const row = history.querySelector(`[data-page-url="${CSS.escape(window.location.pathname)}"]`);
    if (row) openConversation(row, { updateHistory: false });
    else showHome(false);
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeDrawer(); });

  const initialMessagesNode = document.querySelector('#ari-initial-messages');
  if (initialMessagesNode) {
    try {
      const initialMessages = JSON.parse(initialMessagesNode.textContent || '[]');
      if (initialMessages.length) renderMessages(initialMessages);
    } catch (error) {
      setError('Não foi possível abrir as mensagens desta conversa.');
    }
  }
  updateSearch();
  sizeInput();
})();
