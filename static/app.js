// Lógica de Frontend para o Monitor de Concursos Públicos

let currentActiveItems = [];
let currentFavoriteItems = [];
let currentDismissedItems = [];
let activeSourceFilter = 'all';
let currentModalItem = null;
let selectedItemIds = new Set();
let activeKeyword = null;

// Elementos DOM
const btnSearch = document.getElementById('btn-search');
const tedScopeSelect = document.getElementById('ted-scope');
const filterInput = document.getElementById('filter-input');
const sourceTabButtons = document.querySelectorAll('.tab-btn');
const resultsList = document.getElementById('results-list');
const loadingState = document.getElementById('loading-state');
const emptyState = document.getElementById('empty-state');
const lastUpdateText = document.getElementById('last-update-text');

// Elementos de Exportação e Seleção
const btnExportCustom = document.getElementById('btn-export-custom');
const btnExportText = document.getElementById('btn-export-text');
const selectAllVisible = document.getElementById('select-all-visible');
const selectionCounter = document.getElementById('selection-counter');
const btnClearSelection = document.getElementById('btn-clear-selection');

// Elementos das Estatísticas
const statTotal = document.getElementById('stat-total');
const statBase = document.getElementById('stat-base');
const statTed = document.getElementById('stat-ted');
const statTime = document.getElementById('stat-time');
const countAll = document.getElementById('count-all');
const countBase = document.getElementById('count-base');
const countTed = document.getElementById('count-ted');
const countFavorites = document.getElementById('count-favorites');
const countDismissed = document.getElementById('count-dismissed');

// Elementos do Modal
const summaryModal = document.getElementById('summary-modal');
const modalClose = document.getElementById('modal-close');
const modalTitle = document.getElementById('modal-title');
const modalObject = document.getElementById('modal-object');
const modalValue = document.getElementById('modal-value');
const modalType = document.getElementById('modal-type');
const modalEntity = document.getElementById('modal-entity');
const modalPubDate = document.getElementById('modal-pubdate');
const modalDeadlineLabel = document.getElementById('modal-deadline-label');
const modalDeadline = document.getElementById('modal-deadline');
const btnCopySummary = document.getElementById('btn-copy-summary');
const btnModalOpenDirect = document.getElementById('btn-modal-open-direct');

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadInitialData();
});

function setupEventListeners() {
  btnSearch.addEventListener('click', handleSearchClick);

  const keywordButtons = document.querySelectorAll('.keyword-btn');

  // Filtro por clique nas palavras-chave do topo
  keywordButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const kw = btn.dataset.keyword;
      if (activeKeyword === kw) {
        // Desativar filtro ao clicar novamente
        activeKeyword = null;
        btn.classList.remove('active');
        filterInput.value = '';
      } else {
        // Ativar filtro da palavra-chave clicada
        keywordButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeKeyword = kw;
        filterInput.value = kw;
      }
      renderFilteredList();
    });
  });

  filterInput.addEventListener('input', () => {
    const val = normalizeStr(filterInput.value.trim());
    keywordButtons.forEach(btn => {
      if (val && normalizeStr(btn.dataset.keyword) === val) {
        btn.classList.add('active');
        activeKeyword = btn.dataset.keyword;
      } else {
        btn.classList.remove('active');
      }
    });
    if (!val) activeKeyword = null;
    renderFilteredList();
  });

  sourceTabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      sourceTabButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeSourceFilter = btn.dataset.filter;
      renderFilteredList();
    });
  });

  // Seleção e Exportação
  selectAllVisible.addEventListener('change', (e) => {
    const visibleCards = getCurrentlyFilteredItems();
    if (e.target.checked) {
      visibleCards.forEach(item => selectedItemIds.add(item.id));
    } else {
      visibleCards.forEach(item => selectedItemIds.delete(item.id));
    }
    updateSelectionUI();
    renderFilteredList();
  });

  btnClearSelection.addEventListener('click', () => {
    selectedItemIds.clear();
    selectAllVisible.checked = false;
    updateSelectionUI();
    renderFilteredList();
  });

  btnExportCustom.addEventListener('click', handleExportClick);

  // Modal events
  modalClose.addEventListener('click', closeModal);
  summaryModal.addEventListener('click', (e) => {
    if (e.target === summaryModal) closeModal();
  });

  btnCopySummary.addEventListener('click', () => {
    if (!currentModalItem) return;
    const textToCopy = currentModalItem.summary || 
      `Objeto: ${currentModalItem.title}\nPrazo de Entrega: ${currentModalItem.deadline}\nValor a Concurso: ${currentModalItem.value}\nEntidade: ${currentModalItem.entity}\nLink: ${currentModalItem.direct_url}`;
    navigator.clipboard.writeText(textToCopy).then(() => {
      const originalText = btnCopySummary.textContent;
      btnCopySummary.textContent = "✅ Copiado!";
      setTimeout(() => {
        btnCopySummary.textContent = originalText;
      }, 2000);
    });
  });
}

// Carregar dados da cache no arranque
async function loadInitialData() {
  try {
    const res = await fetch('/api/status');
    const status = await res.json();

    if (status.has_data) {
      lastUpdateText.textContent = `Última pesquisa: ${status.timestamp}`;
      if (status.ted_country) {
        tedScopeSelect.value = status.ted_country;
      }
      const resResults = await fetch('/api/results');
      const data = await resResults.json();
      currentActiveItems = data.items || [];
      currentFavoriteItems = data.favorite_items || [];
      currentDismissedItems = data.dismissed_items || [];
      updateStats(data);
      renderFilteredList();
    } else {
      lastUpdateText.textContent = "Pronto para pesquisar";
      emptyState.classList.remove('hidden');
    }
  } catch (err) {
    console.error("Erro ao carregar dados iniciais:", err);
    lastUpdateText.textContent = "Pronto para pesquisar";
  }
}

// Executar pesquisa completa
async function handleSearchClick() {
  setLoading(true);

  try {
    const tedCountry = tedScopeSelect.value;
    const response = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ted_country: tedCountry })
    });

    if (!response.ok) {
      throw new Error(`Erro na pesquisa: ${response.statusText}`);
    }

    const data = await response.json();
    currentActiveItems = data.items || [];
    currentFavoriteItems = data.favorite_items || [];
    currentDismissedItems = data.dismissed_items || [];
    updateStats(data);
    renderFilteredList();
    lastUpdateText.textContent = `Última pesquisa: ${data.timestamp}`;
  } catch (err) {
    console.error("Erro na pesquisa:", err);
    alert("Ocorreu um erro ao comunicar com os portais. Por favor tente novamente.");
  } finally {
    setLoading(false);
  }
}

function setLoading(isLoading) {
  if (isLoading) {
    btnSearch.disabled = true;
    btnSearch.querySelector('.btn-icon').textContent = "⏳";
    btnSearch.querySelector('.btn-text').textContent = "A pesquisar...";
    loadingState.classList.remove('hidden');
    emptyState.classList.add('hidden');
    resultsList.innerHTML = '';
  } else {
    btnSearch.disabled = false;
    btnSearch.querySelector('.btn-icon').textContent = "🔍";
    btnSearch.querySelector('.btn-text').textContent = "Pesquisar Concursos";
    loadingState.classList.add('hidden');
  }
}

function updateStats(data) {
  statTotal.textContent = data.total_count || 0;
  statBase.textContent = data.base_count || 0;
  statTed.textContent = data.ted_count || 0;
  statTime.textContent = data.duration_seconds ? `${data.duration_seconds}s` : '--';

  countAll.textContent = data.total_count || 0;
  countBase.textContent = data.base_count || 0;
  countTed.textContent = data.ted_count || 0;
  if (countFavorites) {
    countFavorites.textContent = data.favorite_count || (currentFavoriteItems ? currentFavoriteItems.length : 0);
  }
  if (countDismissed) {
    countDismissed.textContent = data.dismissed_count || (currentDismissedItems ? currentDismissedItems.length : 0);
  }
}

function normalizeStr(str) {
  if (!str) return '';
  return String(str).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

// Filtragem e Renderização
function getCurrentlyFilteredItems() {
  const rawQuery = filterInput.value.trim();
  const query = normalizeStr(rawQuery);
  
  let sourceList = currentActiveItems;
  if (activeSourceFilter === 'favorites') {
    sourceList = currentFavoriteItems;
  } else if (activeSourceFilter === 'dismissed') {
    sourceList = currentDismissedItems;
  }

  return sourceList.filter(item => {
    // Filtro de Fonte (Portal BASE / TED Europa) apenas quando na lista geral
    if (activeSourceFilter !== 'all' && activeSourceFilter !== 'favorites' && activeSourceFilter !== 'dismissed' && item.source !== activeSourceFilter) {
      return false;
    }

    // Filtro de Texto / Palavra-chave
    if (query) {
      const matchTitle = normalizeStr(item.title).includes(query);
      const matchEntity = normalizeStr(item.entity).includes(query);
      const matchValue = normalizeStr(item.value).includes(query);
      const matchType = normalizeStr(item.procedure_type).includes(query);
      const matchTags = (item.matched_terms || []).some(t => normalizeStr(t).includes(query));
      return matchTitle || matchEntity || matchValue || matchType || matchTags;
    }

    return true;
  });
}

function renderFilteredList() {
  const filtered = getCurrentlyFilteredItems();

  if (filtered.length === 0) {
    emptyState.classList.remove('hidden');
    if (activeSourceFilter === 'favorites') {
      emptyState.querySelector('h3').textContent = "Nenhum concurso nos favoritos";
      emptyState.querySelector('p').textContent = "Clique na estrela (☆) em qualquer concurso para o mover para a sua lista de favoritos.";
    } else if (activeSourceFilter === 'dismissed') {
      emptyState.querySelector('h3').textContent = "Nenhum concurso descartado";
      emptyState.querySelector('p').textContent = "Os concursos que descartar aparecerão aqui, caso queira recuperá-los mais tarde.";
    } else {
      emptyState.querySelector('h3').textContent = currentActiveItems.length === 0 ? 
        "Nenhum concurso novo na lista geral" : "Nenhum resultado encontrado para os filtros selecionados";
      emptyState.querySelector('p').textContent = "Clique em 'Pesquisar Concursos' ou ajuste o termo de filtro.";
    }
    resultsList.innerHTML = '';
    updateSelectionUI();
    return;
  }

  emptyState.classList.add('hidden');
  resultsList.innerHTML = filtered.map(item => createTenderCardHtml(item)).join('');

  attachCardEvents();
  updateSelectionUI();
}

function createTenderCardHtml(item) {
  const isBase = item.source === 'Portal BASE';
  const badgeClass = isBase ? 'badge-base' : 'badge-ted';
  const sourceIcon = isBase ? '🇵🇹' : '🇪🇺';
  const isSelected = selectedItemIds.has(item.id);
  const isDismissed = activeSourceFilter === 'dismissed';
  const isFav = !!item.is_favorite;

  const matchedHtml = (item.matched_terms || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('');

  return `
    <article class="tender-card ${isSelected ? 'selected-card' : ''} ${isDismissed ? 'dismissed-card' : ''}" data-id="${escapeHtml(item.id)}">
      <div class="card-top">
        <div style="display: flex; align-items: center; gap: 8px;">
          <label class="card-select-label" title="Selecionar este concurso para exportar">
            <input type="checkbox" class="item-checkbox" data-id="${escapeHtml(item.id)}" ${isSelected ? 'checked' : ''} />
          </label>
          <button type="button" class="btn-star ${isFav ? 'favorited' : ''}" data-id="${escapeHtml(item.id)}" title="${isFav ? 'Remover dos favoritos (devolver à lista geral)' : 'Mover para os favoritos'}">
            ${isFav ? '★' : '☆'}
          </button>
          <span class="source-badge ${badgeClass}">${sourceIcon} ${escapeHtml(item.source)}</span>
          <span class="procedure-type-badge">${escapeHtml(item.procedure_type || 'Concurso')}</span>
        </div>
        <span class="card-date">Publicado a: <strong>${escapeHtml(item.publication_date || 'N/D')}</strong></span>
      </div>

      <h2 class="card-title">${escapeHtml(item.title)}</h2>

      <div class="card-entity">
        <span>🏢</span>
        <span>Entidade: <strong>${escapeHtml(item.entity || 'Entidade Pública')}</strong></span>
      </div>

      <!-- Resumo Individual Visualmente Destacado -->
      <div class="summary-pillars">
        <div class="pillar">
          <span class="pillar-label">Prazo de Entrega da Proposta</span>
          <span class="pillar-value pillar-deadline">⏳ ${escapeHtml(item.deadline || 'Consulte o anúncio')}</span>
        </div>
        <div class="pillar">
          <span class="pillar-label">Valor a Concurso / Preço Base</span>
          <span class="pillar-value pillar-price">💰 ${escapeHtml(item.value || 'Não especificado')}</span>
        </div>
      </div>

      <div class="card-bottom">
        <div class="matched-badges">
          ${matchedHtml}
        </div>
        <div class="card-actions">
          ${isDismissed ? 
            `<button class="btn btn-card-restore" data-id="${escapeHtml(item.id)}" title="Recuperar este concurso para a lista ativa">↩️ Recuperar</button>` :
            `<button class="btn btn-card-dismiss" data-id="${escapeHtml(item.id)}" title="Descartar este concurso para não voltar a ver">🗑️ Descartar</button>`
          }
          <button class="btn btn-card-summary" data-id="${escapeHtml(item.id)}">📋 Ver Resumo</button>
          <a href="${escapeHtml(getSpecificDirectUrl(item.direct_url))}" target="_blank" rel="noopener noreferrer" class="btn btn-card-link">
            Abrir no Portal Oficial ↗
          </a>
        </div>
      </div>
    </article>
  `;
}

function attachCardEvents() {
  // Checkbox individual por concurso
  document.querySelectorAll('.item-checkbox').forEach(cb => {
    cb.addEventListener('change', () => {
      const id = cb.dataset.id;
      if (cb.checked) {
        selectedItemIds.add(id);
      } else {
        selectedItemIds.delete(id);
      }
      const card = document.querySelector(`.tender-card[data-id="${id}"]`);
      if (card) {
        if (cb.checked) card.classList.add('selected-card');
        else card.classList.remove('selected-card');
      }
      updateSelectionUI();
    });
  });

  // Botões de Estrela / Favorito
  document.querySelectorAll('.btn-star').forEach(starBtn => {
    starBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      handleToggleFavorite(starBtn.dataset.id);
    });
  });

  // Botões de Descarte
  document.querySelectorAll('.btn-card-dismiss').forEach(btn => {
    btn.addEventListener('click', () => {
      handleDismissItem(btn.dataset.id);
    });
  });

  // Botões de Recuperação
  document.querySelectorAll('.btn-card-restore').forEach(btn => {
    btn.addEventListener('click', () => {
      handleRestoreItem(btn.dataset.id);
    });
  });

  // Botões de Ver Resumo
  document.querySelectorAll('.btn-card-summary').forEach(btn => {
    btn.addEventListener('click', () => {
      const itemId = btn.dataset.id;
      const allCandidates = [...currentActiveItems, ...currentFavoriteItems, ...currentDismissedItems];
      const found = allCandidates.find(it => it.id === itemId);
      if (found) openModal(found);
    });
  });
}

// Alternar Favorito (Mover entre Lista Geral e Favoritos)
async function handleToggleFavorite(itemId) {
  // Verificar se já está nos favoritos
  const favIndex = currentFavoriteItems.findIndex(it => it.id === itemId);
  if (favIndex !== -1) {
    // Está nos favoritos -> Desmarcar e devolver à lista geral
    const item = currentFavoriteItems.splice(favIndex, 1)[0];
    item.is_favorite = false;
    currentActiveItems.unshift(item);
  } else {
    // Está na lista geral -> Marcar e mover para a lista de favoritos
    const activeIndex = currentActiveItems.findIndex(it => it.id === itemId);
    if (activeIndex !== -1) {
      const item = currentActiveItems.splice(activeIndex, 1)[0];
      item.is_favorite = true;
      currentFavoriteItems.unshift(item);
    }
  }

  updateCountsAfterChange();
  renderFilteredList();

  // Persistir no servidor
  try {
    await fetch('/api/favorite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: itemId })
    });
  } catch (e) {
    console.error("Erro ao persistir favorito:", e);
  }
}

// Descartar concurso
async function handleDismissItem(itemId) {
  let item = null;
  let activeIndex = currentActiveItems.findIndex(it => it.id === itemId);
  if (activeIndex !== -1) {
    item = currentActiveItems.splice(activeIndex, 1)[0];
  } else {
    let favIndex = currentFavoriteItems.findIndex(it => it.id === itemId);
    if (favIndex !== -1) {
      item = currentFavoriteItems.splice(favIndex, 1)[0];
    }
  }
  if (!item) return;

  item.is_dismissed = true;
  currentDismissedItems.unshift(item);
  selectedItemIds.delete(itemId);

  updateCountsAfterChange();
  renderFilteredList();

  // Persistir no servidor
  try {
    await fetch('/api/dismiss', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: itemId })
    });
  } catch (e) {
    console.error("Erro ao persistir descarte:", e);
  }
}

// Recuperar concurso descartado
async function handleRestoreItem(itemId) {
  const itemIndex = currentDismissedItems.findIndex(it => it.id === itemId);
  if (itemIndex === -1) return;

  const item = currentDismissedItems.splice(itemIndex, 1)[0];
  item.is_dismissed = false;
  if (item.is_favorite) {
    currentFavoriteItems.unshift(item);
  } else {
    currentActiveItems.unshift(item);
  }

  updateCountsAfterChange();
  renderFilteredList();

  // Persistir no servidor
  try {
    await fetch('/api/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: itemId })
    });
  } catch (e) {
    console.error("Erro ao persistir restauro:", e);
  }
}

function updateCountsAfterChange() {
  let baseCount = 0;
  let tedCount = 0;
  currentActiveItems.forEach(it => {
    if (it.source === 'Portal BASE') baseCount++;
    else tedCount++;
  });

  statTotal.textContent = currentActiveItems.length;
  statBase.textContent = baseCount;
  statTed.textContent = tedCount;

  countAll.textContent = currentActiveItems.length;
  countBase.textContent = baseCount;
  countTed.textContent = tedCount;
  if (countFavorites) {
    countFavorites.textContent = currentFavoriteItems.length;
  }
  if (countDismissed) {
    countDismissed.textContent = currentDismissedItems.length;
  }
}

function updateSelectionUI() {
  const visible = getCurrentlyFilteredItems();
  const selectedCount = selectedItemIds.size;

  selectionCounter.textContent = `(${selectedCount} selecionado${selectedCount === 1 ? '' : 's'})`;

  if (selectedCount > 0) {
    btnClearSelection.classList.remove('hidden');
    btnExportText.textContent = `Exportar Selecionados (${selectedCount})`;
  } else {
    btnClearSelection.classList.add('hidden');
    btnExportText.textContent = `Exportar Todos os Visíveis (${visible.length})`;
  }

  // Verifica se todos os visíveis estão selecionados
  if (visible.length > 0 && visible.every(it => selectedItemIds.has(it.id))) {
    selectAllVisible.checked = true;
    selectAllVisible.indeterminate = false;
  } else if (visible.some(it => selectedItemIds.has(it.id))) {
    selectAllVisible.checked = false;
    selectAllVisible.indeterminate = true;
  } else {
    selectAllVisible.checked = false;
    selectAllVisible.indeterminate = false;
  }
}

// Exportar para Excel com seleção
async function handleExportClick() {
  const visible = getCurrentlyFilteredItems();
  let idsToExport = [];

  if (selectedItemIds.size > 0) {
    idsToExport = Array.from(selectedItemIds);
  } else {
    idsToExport = visible.map(it => it.id);
  }

  if (idsToExport.length === 0) {
    alert("Não há concursos selecionados ou visíveis para exportar.");
    return;
  }

  try {
    const response = await fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: idsToExport })
    });

    if (!response.ok) {
      throw new Error("Erro na exportação.");
    }

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    const now = new Date();
    const ts = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}`;
    a.download = `concursos_selecionados_${ts}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(downloadUrl);
  } catch (err) {
    console.error("Erro ao descarregar ficheiro Excel:", err);
    alert("Ocorreu um erro ao gerar a exportação.");
  }
}

function getSpecificDirectUrl(url) {
  if (!url) return '#';
  // Garante que links do Portal BASE abrem a ficha de detalhe específico (/detalhe/) e não a lista geral (/pesquisa/)
  return url.replace('/Base4/pt/pesquisa/?type=', '/Base4/pt/detalhe/?type=');
}

// Modal Logic
function openModal(item) {
  currentModalItem = item;
  modalTitle.textContent = `${item.source} - ${item.procedure_type || 'Detalhes do Concurso'}`;
  modalObject.textContent = item.title;
  modalValue.textContent = item.value || "Não especificado";
  if (modalType) {
    modalType.textContent = item.procedure_type || item.category || "Procedimento Público";
  }
  modalEntity.textContent = item.entity || "Consulte os termos";
  modalPubDate.textContent = item.publication_date || "N/D";
  
  // Data limite de entrega da proposta (por baixo da data de publicação)
  if (modalDeadlineLabel) {
    modalDeadlineLabel.innerHTML = "⌛ DATA LIMITE DE ENTREGA DA PROPOSTA";
  }
  modalDeadline.textContent = item.deadline || "Consulte o anúncio";
  modalDeadline.className = "summary-badge";

  // Configurar botão de estrela no rodapé do modal
  const modalBtnStar = document.getElementById('modal-btn-star');
  if (modalBtnStar) {
    const isFav = !!item.is_favorite;
    modalBtnStar.textContent = isFav ? '★' : '☆';
    modalBtnStar.className = `btn-star ${isFav ? 'favorited' : ''}`;
    modalBtnStar.title = isFav ? 'Remover dos favoritos (devolver à lista geral)' : 'Mover para os favoritos';
    modalBtnStar.onclick = async (e) => {
      e.stopPropagation();
      await handleToggleFavorite(item.id);
      const newFav = !!item.is_favorite;
      modalBtnStar.textContent = newFav ? '★' : '☆';
      modalBtnStar.className = `btn-star ${newFav ? 'favorited' : ''}`;
      modalBtnStar.title = newFav ? 'Remover dos favoritos (devolver à lista geral)' : 'Mover para os favoritos';
    };
  }

  // Configurar botão de descarte no rodapé do modal
  const modalBtnDismiss = document.getElementById('modal-btn-dismiss');
  if (modalBtnDismiss) {
    const isDismissed = !!item.is_dismissed;
    if (isDismissed) {
      modalBtnDismiss.textContent = "↩️ Recuperar";
      modalBtnDismiss.className = "btn btn-card-restore";
      modalBtnDismiss.title = "Recuperar este concurso para a lista ativa";
      modalBtnDismiss.onclick = async () => {
        await handleRestoreItem(item.id);
        closeModal();
      };
    } else {
      modalBtnDismiss.textContent = "🗑️ Descartar";
      modalBtnDismiss.className = "btn btn-card-dismiss";
      modalBtnDismiss.title = "Descartar este concurso para não voltar a ver";
      modalBtnDismiss.onclick = async () => {
        await handleDismissItem(item.id);
        closeModal();
      };
    }
  }

  const specificUrl = getSpecificDirectUrl(item.direct_url);
  btnModalOpenDirect.href = specificUrl;
  summaryModal.classList.remove('hidden');
}

function closeModal() {
  summaryModal.classList.add('hidden');
  currentModalItem = null;
}

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
