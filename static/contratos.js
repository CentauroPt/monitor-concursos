// Lógica de Frontend para a Pesquisa de Contratos Públicos por Entidade
// Suporta filtragem por critérios e pesquisa de palavras no texto com painel lateral direito

let allContracts = [];
let currentFilteredContracts = [];
let activeSearchQuery = '';

// Elementos DOM
const searchForm = document.getElementById('contracts-search-form');
const inputNif = document.getElementById('input-nif');
const inputEntityName = document.getElementById('input-entity-name');
const selectSource = document.getElementById('select-source');
const selectLimit = document.getElementById('select-limit');
const inputDateStart = document.getElementById('input-date-start');
const inputDateEnd = document.getElementById('input-date-end');
const selectDateType = document.getElementById('select-date-type');
const btnSubmitSearch = document.getElementById('btn-submit-search');

// Secção de Filtros
const filterSection = document.getElementById('contracts-filter-section');
const filterObject = document.getElementById('filter-contract-object');
const filterSigningDate = document.getElementById('filter-contract-signing');
const filterPubDate = document.getElementById('filter-contract-publication');
const filterInsideWords = document.getElementById('filter-inside-words');
const btnClearWords = document.getElementById('btn-clear-words');
const btnClearAllFilters = document.getElementById('btn-clear-all-filters');
const btnExportExcel = document.getElementById('btn-export-excel');
const btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
const visibleCount = document.getElementById('visible-count');
const totalContractsCount = document.getElementById('total-contracts-count');

// Estados e Listas
const contractsContentColumn = document.getElementById('contracts-content-column');
const contractsList = document.getElementById('contracts-list');
const emptyState = document.getElementById('empty-state');
const loadingState = document.getElementById('loading-state');
const lastUpdateText = document.getElementById('last-update-text');

// Janela Vertical Lateral Direita
const wordsSidebarPanel = document.getElementById('words-sidebar-panel');
const btnCloseSidebar = document.getElementById('btn-close-sidebar');
const tabSidebarFicha = document.getElementById('tab-sidebar-ficha');
const tabSidebarWords = document.getElementById('tab-sidebar-words');
const sidebarTabFichaTitle = document.getElementById('sidebar-tab-ficha-title');
const sidebarWordsCountBadge = document.getElementById('sidebar-words-count-badge');
const sidebarViewFicha = document.getElementById('sidebar-view-ficha');
const sidebarViewWords = document.getElementById('sidebar-view-words');
const sidebarFichaEmpty = document.getElementById('sidebar-ficha-empty');
const sidebarFichaContent = document.getElementById('sidebar-ficha-content');
const sidebarQueryTitle = document.getElementById('sidebar-query-title');
const sidebarSubtitle = document.getElementById('sidebar-subtitle');
const sidebarEmptyState = document.getElementById('sidebar-empty-state');
const sidebarMatchesList = document.getElementById('sidebar-matches-list');

// Modal
const contractDetailModal = document.getElementById('contract-detail-modal');
const modalCloseBtn = document.getElementById('modal-close-btn');
const modalSourceBadge = document.getElementById('modal-source-badge');
const modalContractTitle = document.getElementById('modal-contract-title');
const modalContractBody = document.getElementById('modal-contract-body');
const modalExternalLink = document.getElementById('modal-external-link');

document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
});

function setupEventListeners() {
  // Submissão do formulário
  if (searchForm) {
    searchForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleContractSearch();
    });
  }

  // Atalhos Rápidos de Entidades
  document.querySelectorAll('.quick-entity-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const nif = btn.dataset.nif;
      const name = btn.dataset.name;
      if (inputNif) inputNif.value = nif;
      if (inputEntityName) inputEntityName.value = name;
      handleContractSearch();
    });
  });

  // Atalhos Rápidos de Datas
  document.querySelectorAll('.quick-date-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const today = new Date();
      if (btn.dataset.clear) {
        if (inputDateStart) inputDateStart.value = '';
        if (inputDateEnd) inputDateEnd.value = '';
      } else if (btn.dataset.days) {
        const days = parseInt(btn.dataset.days, 10);
        const past = new Date();
        past.setDate(past.getDate() - days);
        if (inputDateStart) inputDateStart.value = past.toISOString().substring(0, 10);
        if (inputDateEnd) inputDateEnd.value = today.toISOString().substring(0, 10);
      } else if (btn.dataset.year) {
        const yr = btn.dataset.year;
        if (inputDateStart) inputDateStart.value = `${yr}-01-01`;
        if (inputDateEnd) inputDateEnd.value = `${yr}-12-31`;
      }
      applyFilters();
    });
  });

  if (inputDateStart) inputDateStart.addEventListener('change', applyFilters);
  if (inputDateEnd) inputDateEnd.addEventListener('change', applyFilters);
  if (selectDateType) selectDateType.addEventListener('change', applyFilters);

  // Filtros em tempo real
  if (filterObject) filterObject.addEventListener('input', applyFilters);
  if (filterSigningDate) filterSigningDate.addEventListener('input', applyFilters);
  if (filterPubDate) filterPubDate.addEventListener('input', applyFilters);

  // Filtro especial de palavras no texto do contrato
  if (filterInsideWords) {
    filterInsideWords.addEventListener('input', () => {
      const val = filterInsideWords.value.trim();
      if (val) {
        btnClearWords.classList.remove('hidden');
        openSidebar();
      } else {
        btnClearWords.classList.add('hidden');
      }
      applyFilters();
    });
  }

  if (btnClearWords) {
    btnClearWords.addEventListener('click', () => {
      filterInsideWords.value = '';
      btnClearWords.classList.add('hidden');
      applyFilters();
    });
  }

  if (btnClearAllFilters) {
    btnClearAllFilters.addEventListener('click', clearAllFilters);
  }

  if (btnExportExcel) {
    btnExportExcel.addEventListener('click', exportFilteredContractsToExcel);
  }

  // Alternar painel lateral
  if (btnToggleSidebar) {
    btnToggleSidebar.addEventListener('click', () => {
      if (wordsSidebarPanel.classList.contains('hidden')) {
        openSidebar();
      } else {
        closeSidebar();
      }
    });
  }

  if (btnCloseSidebar) {
    btnCloseSidebar.addEventListener('click', closeSidebar);
  }

  // Alternar abas no painel lateral (Ficha vs Palavras)
  if (tabSidebarFicha) {
    tabSidebarFicha.addEventListener('click', () => {
      tabSidebarFicha.classList.add('active');
      if (tabSidebarWords) tabSidebarWords.classList.remove('active');
      if (sidebarViewFicha) sidebarViewFicha.classList.remove('hidden');
      if (sidebarViewWords) sidebarViewWords.classList.add('hidden');
    });
  }

  if (tabSidebarWords) {
    tabSidebarWords.addEventListener('click', () => {
      tabSidebarWords.classList.add('active');
      if (tabSidebarFicha) tabSidebarFicha.classList.remove('active');
      if (sidebarViewWords) sidebarViewWords.classList.remove('hidden');
      if (sidebarViewFicha) sidebarViewFicha.classList.add('hidden');
    });
  }

  // Modal
  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeModal);
  if (contractDetailModal) {
    contractDetailModal.addEventListener('click', (e) => {
      if (e.target === contractDetailModal) closeModal();
    });
  }
}

// Executar Pesquisa Principal no Servidor
async function handleContractSearch() {
  const nif = (inputNif ? inputNif.value.trim() : '');
  const entityName = (inputEntityName ? inputEntityName.value.trim() : '');
  const source = (selectSource ? selectSource.value : 'all');
  const limit = (selectLimit ? parseInt(selectLimit.value, 10) : 50);
  const dateStart = (inputDateStart ? inputDateStart.value.trim() : '');
  const dateEnd = (inputDateEnd ? inputDateEnd.value.trim() : '');
  const dateMode = (selectDateType ? selectDateType.value : 'any');

  if (!nif && !entityName) {
    alert("Por favor, introduza o NIF da entidade adjudicante ou o seu Nome para realizar a pesquisa.");
    if (inputNif) inputNif.focus();
    return;
  }

  setLoading(true);

  try {
    const response = await fetch('/api/contracts/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nif: nif,
        entity_name: entityName,
        source: source,
        limit: limit,
        date_start: dateStart,
        date_end: dateEnd,
        date_mode: dateMode
      })
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || `Erro HTTP ${response.status}`);
    }

    const data = await response.json();
    allContracts = data.contracts || [];

    if (totalContractsCount) totalContractsCount.textContent = allContracts.length;
    if (lastUpdateText) {
      lastUpdateText.textContent = `Pesquisa concluída (${allContracts.length} contratos encontrados em ${data.duration_seconds || 0}s)`;
    }

    if (filterSection) {
      filterSection.classList.remove('hidden');
    }

    applyFilters();

    // Se o utilizador já tiver palavras no filtro de texto, atualiza a barra lateral
    if (filterInsideWords && filterInsideWords.value.trim()) {
      openSidebar();
    }
  } catch (err) {
    console.error("Erro ao pesquisar contratos:", err);
    alert("Ocorreu um erro ao comunicar com os portais BASE e TED: " + (err.message || err));
  } finally {
    setLoading(false);
  }
}

function setLoading(isLoading) {
  if (isLoading) {
    if (btnSubmitSearch) {
      btnSubmitSearch.disabled = true;
      btnSubmitSearch.querySelector('.btn-icon').textContent = "⏳";
      btnSubmitSearch.querySelector('.btn-text').textContent = "A consultar portais...";
    }
    if (loadingState) loadingState.classList.remove('hidden');
    if (emptyState) emptyState.classList.add('hidden');
    if (contractsList) contractsList.innerHTML = '';
  } else {
    if (btnSubmitSearch) {
      btnSubmitSearch.disabled = false;
      btnSubmitSearch.querySelector('.btn-icon').textContent = "🔍";
      btnSubmitSearch.querySelector('.btn-text').textContent = "Pesquisar Contratos";
    }
    if (loadingState) loadingState.classList.add('hidden');
  }
}

function normalizeStr(str) {
  if (!str) return '';
  return String(str).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

function parseContractDate(dStr) {
  if (!dStr || dStr === 'N/D') return null;
  const s = String(dStr).trim().substring(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
    return new Date(s + 'T00:00:00');
  }
  const m = s.match(/^(\d{2})[-/](\d{2})[-/](\d{4})$/);
  if (m) {
    return new Date(`${m[3]}-${m[2]}-${m[1]}T00:00:00`);
  }
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

// Aplicação de Filtros da Lista Apresentada
function applyFilters() {
  const qObject = normalizeStr(filterObject ? filterObject.value.trim() : '');
  const qSigning = normalizeStr(filterSigningDate ? filterSigningDate.value.trim() : '');
  const qPub = normalizeStr(filterPubDate ? filterPubDate.value.trim() : '');
  const qInsideWord = normalizeStr(filterInsideWords ? filterInsideWords.value.trim() : '');

  const valStart = inputDateStart ? inputDateStart.value : '';
  const valEnd = inputDateEnd ? inputDateEnd.value : '';
  const dateType = selectDateType ? selectDateType.value : 'any';

  activeSearchQuery = qInsideWord;

  currentFilteredContracts = allContracts.filter(contract => {
    // 1. Filtro por Intervalo de Datas (Assinados e/ou Publicados)
    if (valStart || valEnd) {
      const dStart = valStart ? new Date(valStart + 'T00:00:00') : null;
      const dEnd = valEnd ? new Date(valEnd + 'T23:59:59') : null;

      const dSign = parseContractDate(contract.signing_date);
      const dPub = parseContractDate(contract.publication_date);

      const signInRange = dSign ? ((!dStart || dSign >= dStart) && (!dEnd || dSign <= dEnd)) : false;
      const pubInRange = dPub ? ((!dStart || dPub >= dStart) && (!dEnd || dPub <= dEnd)) : false;

      if (dateType === 'signing') {
        if (!signInRange) return false;
      } else if (dateType === 'publication') {
        if (!pubInRange) return false;
      } else {
        // 'any': assinados e/ou publicados entre essas datas
        if (!signInRange && !pubInRange) return false;
      }
    }

    // 2. Filtro por Objeto
    if (qObject) {
      const matchTitle = normalizeStr(contract.title).includes(qObject);
      const matchDesc = normalizeStr(contract.description).includes(qObject);
      if (!matchTitle && !matchDesc) return false;
    }

    // 3. Filtro por Data do Contrato (Celebração)
    if (qSigning) {
      const matchSigning = normalizeStr(contract.signing_date).includes(qSigning);
      if (!matchSigning) return false;
    }

    // 4. Filtro por Data de Publicação
    if (qPub) {
      const matchPub = normalizeStr(contract.publication_date).includes(qPub);
      if (!matchPub) return false;
    }

    // 5. Se tiver filtro de palavras, só mostra contratos onde a palavra ocorre
    if (qInsideWord) {
      const hasMatch = checkContractContainsWord(contract, qInsideWord);
      if (!hasMatch) return false;
    }

    return true;
  });

  if (visibleCount) visibleCount.textContent = currentFilteredContracts.length;

  renderContractsList();
  updateSidebarMatches(qInsideWord);
}

function checkContractContainsWord(contract, word) {
  if (!word) return true;
  const sections = contract.sections || {};
  for (const text of Object.values(sections)) {
    if (text && normalizeStr(text).includes(word)) {
      return true;
    }
  }
  return false;
}

function clearAllFilters() {
  if (filterObject) filterObject.value = '';
  if (filterSigningDate) filterSigningDate.value = '';
  if (filterPubDate) filterPubDate.value = '';
  if (filterInsideWords) filterInsideWords.value = '';
  if (btnClearWords) btnClearWords.classList.add('hidden');
  closeSidebar();
  applyFilters();
}

// Renderização dos Cartões de Contrato
function renderContractsList() {
  if (!contractsList) return;

  if (currentFilteredContracts.length === 0) {
    if (emptyState) {
      emptyState.classList.remove('hidden');
      emptyState.querySelector('h3').textContent = allContracts.length === 0 ?
        "Nenhum contrato encontrado" : "Nenhum contrato corresponde aos filtros aplicados";
      emptyState.querySelector('p').textContent = allContracts.length === 0 ?
        "Verifique se o NIF ou Nome da Entidade estão corretos e tente novamente." :
        "Altere ou limpe os termos de filtro acima para ver os restantes contratos.";
    }
    contractsList.innerHTML = '';
    return;
  }

  if (emptyState) emptyState.classList.add('hidden');

  contractsList.innerHTML = currentFilteredContracts.map(c => createContractCardHtml(c)).join('');
  attachCardEvents();
}

function createContractCardHtml(c) {
  const isBase = c.source === 'Portal BASE';
  const badgeClass = isBase ? 'badge-base' : 'badge-ted';
  const sourceIcon = isBase ? '🇵🇹' : '🇪🇺';

  const safeTitle = escapeHtml(c.title || 'Objeto do Contrato');
  const safeEntity = escapeHtml(c.entity || 'Entidade Adjudicante');
  const safeContracted = escapeHtml(c.contracted || 'Adjudicatário não especificado');

  return `
    <article class="contract-card" id="card-${escapeHtml(c.id)}" data-id="${escapeHtml(c.id)}">
      <div class="card-top">
        <div class="card-badges-left">
          <span class="source-badge ${badgeClass}">${sourceIcon} ${escapeHtml(c.source)}</span>
          <span class="procedure-type-badge">${escapeHtml(c.procedure_type || 'Contrato')}</span>
          <span class="id-tag">#${escapeHtml(c.raw_id || c.id)}</span>
        </div>
        <div class="card-top-right">
          <a href="${escapeHtml(c.direct_url)}" target="_blank" rel="noopener noreferrer" class="link-official-card" title="Abrir página oficial do contrato">
            Portal Oficial ↗
          </a>
        </div>
      </div>

      <h2 class="contract-title">${safeTitle}</h2>

      <div class="contract-parties-row">
        <div class="party-item">
          <span class="party-icon">🏛️</span>
          <span class="party-label">Adjudicante:</span>
          <strong class="party-name">${safeEntity}</strong>
          ${c.entity_nif ? `<span class="party-nif">NIF: ${escapeHtml(c.entity_nif)}</span>` : ''}
        </div>
        <div class="party-item">
          <span class="party-icon">🏢</span>
          <span class="party-label">Adjudicatário:</span>
          <strong class="party-name">${safeContracted}</strong>
          ${c.contracted_nif ? `<span class="party-nif">NIF: ${escapeHtml(c.contracted_nif)}</span>` : ''}
        </div>
      </div>

      <!-- Grid com os 4 Pilares do Contrato -->
      <div class="contract-pillars-grid">
        <div class="pillar-box">
          <span class="p-label">📅 Data do Contrato (Celebração)</span>
          <strong class="p-value highlight-date">${escapeHtml(c.signing_date || 'N/D')}</strong>
        </div>
        <div class="pillar-box">
          <span class="p-label">📢 Data de Publicação</span>
          <strong class="p-value">${escapeHtml(c.publication_date || 'N/D')}</strong>
        </div>
        <div class="pillar-box">
          <span class="p-label">💰 Preço Contratual</span>
          <strong class="p-value highlight-price">${escapeHtml(c.value || 'Não especificado')}</strong>
        </div>
        <div class="pillar-box">
          <span class="p-label">📍 Local de Execução</span>
          <strong class="p-value">${escapeHtml(c.execution_place || 'Portugal')}</strong>
        </div>
      </div>

      ${c.fundamentation ? `
        <div class="contract-fundamentation-box">
          <span class="f-label">⚖️ Fundamentação Legal:</span>
          <span class="f-text">${escapeHtml(c.fundamentation)}</span>
        </div>
      ` : ''}

      <div class="contract-card-footer">
        <button type="button" class="btn btn-secondary btn-detail" data-id="${escapeHtml(c.id)}">
          📋 Ver Ficha Completa
        </button>
        <a href="${escapeHtml(c.direct_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-direct-link">
          Abrir no Portal Oficial ↗
        </a>
      </div>
    </article>
  `;
}

function attachCardEvents() {
  document.querySelectorAll('.btn-detail').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const cid = btn.dataset.id;
      const found = allContracts.find(it => it.id === cid);
      if (found) showContractFichaInSidebar(found, true);
    });
  });

  document.querySelectorAll('.contract-card').forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('a') || e.target.closest('.btn-detail')) return;
      const cid = card.dataset.id;
      const found = allContracts.find(it => it.id === cid);
      if (found) showContractFichaInSidebar(found, true);
    });
  });
}

// JANELA VERTICAL LATERAL DIREITA: Ficha Detalhada do Contrato em Verificação
function showContractFichaInSidebar(c, switchToTab = true) {
  if (!wordsSidebarPanel) return;

  // 1. Destaque no cartão do contrato na lista ao lado
  document.querySelectorAll('.contract-card').forEach(card => {
    card.classList.remove('active-contract-card');
    const badge = card.querySelector('.active-verifying-badge');
    if (badge) badge.remove();
  });

  const cardElement = document.getElementById(`card-${c.id}`);
  if (cardElement) {
    cardElement.classList.add('active-contract-card');
    const badgeContainer = cardElement.querySelector('.card-badges-left');
    if (badgeContainer && !cardElement.querySelector('.active-verifying-badge')) {
      const badge = document.createElement('span');
      badge.className = 'active-verifying-badge';
      badge.innerHTML = '👁️ Em verificação';
      badgeContainer.appendChild(badge);
    }
  }

  // 2. Atualizar título da aba
  if (sidebarTabFichaTitle) {
    sidebarTabFichaTitle.textContent = `Ficha #${c.raw_id || c.id}`;
  }

  // 3. Alternar para a aba da Ficha
  if (switchToTab) {
    if (tabSidebarFicha) tabSidebarFicha.classList.add('active');
    if (tabSidebarWords) tabSidebarWords.classList.remove('active');
    if (sidebarViewFicha) sidebarViewFicha.classList.remove('hidden');
    if (sidebarViewWords) sidebarViewWords.classList.add('hidden');
  }

  // 4. Montar o conteúdo completo da Ficha Técnica na lateral
  const isBase = c.source === 'Portal BASE';
  const badgeClass = isBase ? 'badge-base' : 'badge-ted';
  const sourceIcon = isBase ? '🇵🇹' : '🇪🇺';

  const safeTitle = escapeHtml(c.title || 'Sem título');
  const safeEntity = escapeHtml(c.entity || 'Entidade Adjudicante');
  const safeContracted = escapeHtml(c.contracted || 'Não especificado');
  const safeDesc = escapeHtml(c.description || c.title || '');

  const sections = c.sections || {};
  let extraSectionsHtml = '';
  for (const [secTitle, secContent] of Object.entries(sections)) {
    if (!secContent || ['Objeto do Contrato', 'Descrição Detalhada', 'Entidade Adjudicante', 'Adjudicatário'].includes(secTitle)) continue;
    extraSectionsHtml += `
      <div class="ficha-section">
        <span class="ficha-section-title">📌 ${escapeHtml(secTitle)}</span>
        <div class="ficha-section-content">${escapeHtml(secContent)}</div>
      </div>
    `;
  }

  const fichaHtml = `
    <div class="ficha-header-block">
      <div class="ficha-badges-row">
        <span class="source-badge ${badgeClass}">${sourceIcon} ${escapeHtml(c.source)}</span>
        <span class="procedure-type-badge">${escapeHtml(c.procedure_type || 'Contrato')}</span>
        <span class="ficha-contract-id">#${escapeHtml(c.raw_id || c.id)}</span>
      </div>
      <h3 class="ficha-contract-title">${safeTitle}</h3>
    </div>

    <!-- 4 Pilares Técnicos -->
    <div class="ficha-pillars-mini">
      <div class="ficha-mini-pillar">
        <span class="mini-p-label">💰 Preço Contratual</span>
        <span class="mini-p-val highlight-price">${escapeHtml(c.value || 'N/D')}</span>
      </div>
      <div class="ficha-mini-pillar">
        <span class="mini-p-label">📅 Data do Contrato</span>
        <span class="mini-p-val highlight-date">${escapeHtml(c.signing_date || 'N/D')}</span>
      </div>
      <div class="ficha-mini-pillar">
        <span class="mini-p-label">📢 Publicação</span>
        <span class="mini-p-val">${escapeHtml(c.publication_date || 'N/D')}</span>
      </div>
      <div class="ficha-mini-pillar">
        <span class="mini-p-label">⏱️ Prazo Execução</span>
        <span class="mini-p-val">${escapeHtml(c.execution_deadline || 'Consulte caderno')}</span>
      </div>
    </div>

    <!-- Partes Envolvidas -->
    <div class="ficha-section">
      <span class="ficha-section-title">🏛️ Entidade Adjudicante</span>
      <div class="ficha-party-box">
        <span class="ficha-party-name">${safeEntity}</span>
        ${c.entity_nif ? `<span class="ficha-party-nif">NIF: ${escapeHtml(c.entity_nif)}</span>` : ''}
      </div>
    </div>

    <div class="ficha-section">
      <span class="ficha-section-title">🏢 Adjudicatário (Empresa)</span>
      <div class="ficha-party-box">
        <span class="ficha-party-name">${safeContracted}</span>
        ${c.contracted_nif ? `<span class="ficha-party-nif">NIF: ${escapeHtml(c.contracted_nif)}</span>` : ''}
      </div>
    </div>

    ${c.execution_place ? `
      <div class="ficha-section">
        <span class="ficha-section-title">📍 Local de Execução</span>
        <div class="ficha-section-content">${escapeHtml(c.execution_place)}</div>
      </div>
    ` : ''}

    ${c.fundamentation ? `
      <div class="ficha-section">
        <span class="ficha-section-title">⚖️ Fundamentação Legal</span>
        <div class="ficha-section-content">${escapeHtml(c.fundamentation)}</div>
      </div>
    ` : ''}

    ${c.cpvs_designation ? `
      <div class="ficha-section">
        <span class="ficha-section-title">🏷️ Designação CPV</span>
        <div class="ficha-section-content">${escapeHtml(c.cpvs_designation)}</div>
      </div>
    ` : ''}

    ${safeDesc && safeDesc !== safeTitle ? `
      <div class="ficha-section">
        <span class="ficha-section-title">📝 Descrição Detalhada</span>
        <div class="ficha-section-content">${safeDesc}</div>
      </div>
    ` : ''}

    ${extraSectionsHtml}

    <div class="ficha-footer-actions">
      <a href="${escapeHtml(c.direct_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary" style="flex: 1; text-align: center; justify-content: center;">
        Abrir no Portal Oficial ↗
      </a>
      <button type="button" id="btn-copy-ficha" class="btn btn-secondary" title="Copiar resumo do contrato">
        📋 Copiar Resumo
      </button>
    </div>
  `;

  if (sidebarFichaEmpty) sidebarFichaEmpty.classList.add('hidden');
  if (sidebarFichaContent) {
    sidebarFichaContent.innerHTML = fichaHtml;
    sidebarFichaContent.classList.remove('hidden');

    const btnCopy = document.getElementById('btn-copy-ficha');
    if (btnCopy) {
      btnCopy.addEventListener('click', () => {
        const textToCopy = `CONTRATO: ${c.title}\nENTIDADE: ${c.entity} (NIF: ${c.entity_nif || 'N/D'})\nADJUDICATÁRIO: ${c.contracted} (NIF: ${c.contracted_nif || 'N/D'})\nVALOR: ${c.value}\nDATA CONTRATO: ${c.signing_date}\nDATA PUBLICAÇÃO: ${c.publication_date}\nLINK: ${c.direct_url}`;
        navigator.clipboard.writeText(textToCopy).then(() => {
          btnCopy.textContent = '✓ Copiado!';
          setTimeout(() => { btnCopy.textContent = '📋 Copiar Resumo'; }, 2000);
        });
      });
    }
  }

  openSidebar();
}

// JANELA VERTICAL LATERAL DIREITA: Pesquisa de Palavras dentro dos Contratos
function openSidebar() {
  if (wordsSidebarPanel) {
    wordsSidebarPanel.classList.remove('hidden');
    if (contractsContentColumn) contractsContentColumn.classList.add('with-sidebar');
    if (btnToggleSidebar) {
      btnToggleSidebar.classList.add('active');
    }
  }
}

function closeSidebar() {
  if (wordsSidebarPanel) {
    wordsSidebarPanel.classList.add('hidden');
    if (contractsContentColumn) contractsContentColumn.classList.remove('with-sidebar');
    if (btnToggleSidebar) {
      btnToggleSidebar.classList.remove('active');
    }
  }
}

function updateSidebarMatches(searchWord) {
  if (!sidebarMatchesList) return;

  if (!searchWord || searchWord.length < 2) {
    if (sidebarEmptyState) sidebarEmptyState.classList.remove('hidden');
    if (sidebarQueryTitle) sidebarQueryTitle.textContent = "Ocorrências no Texto";
    if (sidebarSubtitle) sidebarSubtitle.textContent = "Introduza 2 ou mais letras no filtro";
    sidebarMatchesList.innerHTML = '';
    return;
  }

  if (sidebarEmptyState) sidebarEmptyState.classList.add('hidden');
  if (sidebarQueryTitle) sidebarQueryTitle.textContent = `Resultados para: "${searchWord}"`;

  const matches = [];

  // Varrer todos os contratos em allContracts
  for (const contract of allContracts) {
    const sections = contract.sections || {};
    for (const [sectionName, text] of Object.entries(sections)) {
      if (!text) continue;
      const normalizedText = normalizeStr(text);
      let startIndex = 0;

      while (startIndex < normalizedText.length) {
        const foundIndex = normalizedText.indexOf(searchWord, startIndex);
        if (foundIndex === -1) break;

        // Extrair excerto contextual (50 caracteres antes e depois)
        const snippetStart = Math.max(0, foundIndex - 45);
        const snippetEnd = Math.min(text.length, foundIndex + searchWord.length + 55);
        const rawSnippet = text.substring(snippetStart, snippetEnd);

        // Destacar o termo correspondente no snippet
        const regex = new RegExp(`(${escapeRegex(searchWord)})`, 'gi');
        const highlightedSnippet = escapeHtml(rawSnippet).replace(
          new RegExp(escapeRegex(searchWord), 'gi'),
          match => `<mark class="kw-highlight">${match}</mark>`
        );

        matches.push({
          contractId: contract.id,
          contractTitle: contract.title,
          contractDate: contract.signing_date || contract.publication_date,
          entity: contract.entity,
          value: contract.value,
          sectionName: sectionName,
          snippet: (snippetStart > 0 ? '...' : '') + highlightedSnippet + (snippetEnd < text.length ? '...' : '')
        });

        startIndex = foundIndex + searchWord.length;
      }
    }
  }

  const contractsWithMatchesCount = new Set(matches.map(m => m.contractId)).size;
  if (sidebarSubtitle) {
    sidebarSubtitle.textContent = `${matches.length} ocorrência${matches.length === 1 ? '' : 's'} em ${contractsWithMatchesCount} contrato${contractsWithMatchesCount === 1 ? '' : 's'}`;
  }

  if (matches.length === 0) {
    sidebarMatchesList.innerHTML = `
      <div class="sidebar-no-results">
        <span>🔍</span>
        <p>Nenhuma ocorrência encontrada para a palavra <strong>"${escapeHtml(searchWord)}"</strong> dentro do texto dos contratos recolhidos.</p>
      </div>
    `;
    return;
  }

  sidebarMatchesList.innerHTML = matches.map((m, idx) => `
    <div class="sidebar-match-card" data-contract-id="${escapeHtml(m.contractId)}">
      <div class="match-card-top">
        <span class="match-contract-badge">#${escapeHtml(m.contractId.replace('base_contrato_', '').replace('ted_', ''))}</span>
        <span class="match-section-badge">📍 ${escapeHtml(m.sectionName)}</span>
      </div>
      <div class="match-contract-title" title="${escapeHtml(m.contractTitle)}">
        ${escapeHtml(m.contractTitle)}
      </div>
      <div class="match-snippet">
        ${m.snippet}
      </div>
      <div class="match-card-bottom">
        <span class="match-date">📅 ${escapeHtml(m.contractDate)}</span>
        <button type="button" class="btn-locate-contract" data-contract-id="${escapeHtml(m.contractId)}">
          🎯 Localizar no Contrato ↘
        </button>
      </div>
    </div>
  `).join('');

  // Eventos de clique para localizar contrato
  document.querySelectorAll('.btn-locate-contract').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const cid = btn.dataset.contractId;
      scrollToAndHighlightContract(cid);
    });
  });

  document.querySelectorAll('.sidebar-match-card').forEach(card => {
    card.addEventListener('click', () => {
      const cid = card.dataset.contractId;
      scrollToAndHighlightContract(cid);
    });
  });
}

function scrollToAndHighlightContract(contractId) {
  const found = allContracts.find(it => it.id === contractId);
  if (found) {
    showContractFichaInSidebar(found, false);
  }
  const cardElement = document.getElementById(`card-${contractId}`);
  if (cardElement) {
    cardElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    cardElement.classList.add('card-glow-focus');
    setTimeout(() => {
      cardElement.classList.remove('card-glow-focus');
    }, 2800);
  } else {
    // Se o cartão estiver filtrado, limpa os filtros gerais exceto a palavra
    if (filterObject) filterObject.value = '';
    if (filterSigningDate) filterSigningDate.value = '';
    if (filterPubDate) filterPubDate.value = '';
    applyFilters();
    setTimeout(() => {
      const reElement = document.getElementById(`card-${contractId}`);
      if (reElement) {
        reElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        reElement.classList.add('card-glow-focus');
        setTimeout(() => reElement.classList.remove('card-glow-focus'), 2800);
      }
    }, 200);
  }
}

// Modal de Detalhes
function openDetailModal(contract) {
  if (!contractDetailModal) return;

  if (modalSourceBadge) {
    modalSourceBadge.textContent = contract.source;
    modalSourceBadge.className = `source-badge ${contract.source === 'Portal BASE' ? 'badge-base' : 'badge-ted'}`;
  }

  if (modalContractTitle) {
    modalContractTitle.textContent = contract.title;
  }

  if (modalExternalLink) {
    modalExternalLink.href = contract.direct_url;
  }

  const sections = contract.sections || {};
  let sectionsHtml = '';
  for (const [secTitle, secContent] of Object.entries(sections)) {
    if (!secContent) continue;
    sectionsHtml += `
      <div class="modal-section-block">
        <h4>${escapeHtml(secTitle)}</h4>
        <p>${escapeHtml(secContent)}</p>
      </div>
    `;
  }

  if (modalContractBody) {
    modalContractBody.innerHTML = `
      <div class="modal-info-grid">
        <div class="m-info-item">
          <span class="m-label">Entidade Adjudicante</span>
          <span class="m-val">${escapeHtml(contract.entity)} ${contract.entity_nif ? `(NIF: ${escapeHtml(contract.entity_nif)})` : ''}</span>
        </div>
        <div class="m-info-item">
          <span class="m-label">Adjudicatário</span>
          <span class="m-val">${escapeHtml(contract.contracted)} ${contract.contracted_nif ? `(NIF: ${escapeHtml(contract.contracted_nif)})` : ''}</span>
        </div>
        <div class="m-info-item">
          <span class="m-label">Preço Contratual</span>
          <span class="m-val highlight-price">${escapeHtml(contract.value)}</span>
        </div>
        <div class="m-info-item">
          <span class="m-label">Tipo de Procedimento</span>
          <span class="m-val">${escapeHtml(contract.procedure_type)}</span>
        </div>
        <div class="m-info-item">
          <span class="m-label">Data de Celebração</span>
          <span class="m-val">${escapeHtml(contract.signing_date)}</span>
        </div>
        <div class="m-info-item">
          <span class="m-label">Data de Publicação</span>
          <span class="m-val">${escapeHtml(contract.publication_date)}</span>
        </div>
      </div>
      <div class="modal-sections-list">
        ${sectionsHtml}
      </div>
    `;
  }

  contractDetailModal.classList.remove('hidden');
}

function closeModal() {
  if (contractDetailModal) contractDetailModal.classList.add('hidden');
}

// Exportação para Excel
async function exportFilteredContractsToExcel() {
  if (!currentFilteredContracts || currentFilteredContracts.length === 0) {
    alert("Não há contratos visíveis para exportar.");
    return;
  }

  try {
    const response = await fetch('/api/contracts/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contracts: currentFilteredContracts })
    });

    if (!response.ok) throw new Error("Erro na exportação.");

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    const now = new Date();
    const ts = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}`;
    a.download = `contratos_entidade_${ts}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(downloadUrl);
  } catch (err) {
    console.error("Erro ao exportar Excel:", err);
    alert("Ocorreu um erro ao descarregar os contratos para Excel.");
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeRegex(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
