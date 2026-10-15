/**
 * Frontend para a Pesquisa de Fornecedores de Entidades Públicas.
 * Segue a mesma linha estética e arquitetura da Pesquisa de Contratos Públicos:
 * Formulário com grelha moderna, atalhos rápidos de datas e municípios,
 * barra de filtros interativos, cartões com 4 pilares e painel lateral vertical de Raio-X.
 */

let allSuppliers = [];
let currentFilteredSuppliers = [];
let activeSupplierIndex = null;

// Elementos DOM do Formulário
const searchForm = document.getElementById('suppliers-search-form');
const inputNif = document.getElementById('input-nif');
const inputEntityName = document.getElementById('input-entity-name');
const selectSource = document.getElementById('select-source');
const selectLimit = document.getElementById('select-limit');
const inputDateStart = document.getElementById('input-date-start');
const inputDateEnd = document.getElementById('input-date-end');
const selectDateType = document.getElementById('select-date-type');
const btnSubmitSearch = document.getElementById('btn-submit-search');

// Secção de Filtros
const filterSection = document.getElementById('suppliers-filter-section');
const filterName = document.getElementById('filter-supplier-name');
const filterLocality = document.getElementById('filter-supplier-locality');
const filterAmount = document.getElementById('filter-supplier-amount');
const filterWords = document.getElementById('filter-supplier-words');
const btnClearWords = document.getElementById('btn-clear-words');
const btnClearAllFilters = document.getElementById('btn-clear-all-filters');
const btnExportExcel = document.getElementById('btn-export-excel');
const btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
const visibleCount = document.getElementById('visible-count');
const totalSuppliersCount = document.getElementById('total-suppliers-count');
const totalAmountBadge = document.getElementById('total-amount-badge');

// Estados e Conteúdo
const suppliersContentColumn = document.getElementById('suppliers-content-column');
const suppliersList = document.getElementById('suppliers-list');
const emptyState = document.getElementById('empty-state');
const loadingState = document.getElementById('loading-state');
const lastUpdateText = document.getElementById('last-update-text');

// Janela Vertical Lateral Direita (Raio-X & Contratos)
const sidebarPanel = document.getElementById('supplier-sidebar-panel');
const btnCloseSidebar = document.getElementById('btn-close-sidebar');
const tabSidebarRaiox = document.getElementById('tab-sidebar-raiox');
const tabSidebarContracts = document.getElementById('tab-sidebar-contracts');
const sidebarContractsCountBadge = document.getElementById('sidebar-contracts-count-badge');
const sidebarViewRaiox = document.getElementById('sidebar-view-raiox');
const sidebarViewContracts = document.getElementById('sidebar-view-contracts');
const sidebarRaioxEmpty = document.getElementById('sidebar-raiox-empty');
const sidebarRaioxContent = document.getElementById('sidebar-raiox-content');

document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  checkUrlParams();
});

function setupEventListeners() {
  // Submissão do formulário
  if (searchForm) {
    searchForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleSupplierSearch();
    });
  }

  // Atalhos Rápidos de Municípios / Entidades
  document.querySelectorAll('.quick-entity-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const nif = btn.dataset.nif;
      const name = btn.dataset.name;
      if (inputNif) inputNif.value = nif || '';
      if (inputEntityName) inputEntityName.value = name || '';
      handleSupplierSearch();
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
        const year = btn.dataset.year;
        if (inputDateStart) inputDateStart.value = `${year}-01-01`;
        if (inputDateEnd) inputDateEnd.value = `${year}-12-31`;
      }
    });
  });

  // Filtros em Tempo Real
  if (filterName) filterName.addEventListener('input', applyFilters);
  if (filterLocality) filterLocality.addEventListener('input', applyFilters);
  if (filterAmount) filterAmount.addEventListener('change', applyFilters);
  if (filterWords) {
    filterWords.addEventListener('input', () => {
      if (btnClearWords) {
        btnClearWords.classList.toggle('hidden', !filterWords.value.trim());
      }
      applyFilters();
    });
  }

  if (btnClearWords) {
    btnClearWords.addEventListener('click', () => {
      if (filterWords) filterWords.value = '';
      btnClearWords.classList.add('hidden');
      applyFilters();
    });
  }

  if (btnClearAllFilters) {
    btnClearAllFilters.addEventListener('click', clearAllFilters);
  }

  if (btnExportExcel) {
    btnExportExcel.addEventListener('click', exportToExcel);
  }

  if (btnToggleSidebar) {
    btnToggleSidebar.addEventListener('click', toggleSidebar);
  }

  if (btnCloseSidebar) {
    btnCloseSidebar.addEventListener('click', closeSidebar);
  }

  // Tabs do Painel Lateral
  if (tabSidebarRaiox) {
    tabSidebarRaiox.addEventListener('click', () => switchSidebarTab('raiox'));
  }
  if (tabSidebarContracts) {
    tabSidebarContracts.addEventListener('click', () => switchSidebarTab('contracts'));
  }
}

function checkUrlParams() {
  const urlParams = new URLSearchParams(window.location.search);
  const nifParam = urlParams.get('nif');
  const nameParam = urlParams.get('nome') || urlParams.get('entidade');
  if (nifParam || nameParam) {
    if (inputNif && nifParam) inputNif.value = nifParam;
    if (inputEntityName && nameParam) inputEntityName.value = nameParam;
    handleSupplierSearch();
  }
}

async function handleSupplierSearch() {
  const nif = inputNif ? inputNif.value.trim() : '';
  const entityName = inputEntityName ? inputEntityName.value.trim() : '';

  if (!nif && !entityName) {
    alert('Por favor, indique o NIF ou o Nome da Entidade Adjudicante / Município.');
    if (inputNif) inputNif.focus();
    return;
  }

  const source = selectSource ? selectSource.value : 'all';
  const limit = selectLimit ? parseInt(selectLimit.value, 10) : 50;
  const date_start = inputDateStart ? inputDateStart.value : null;
  const date_end = inputDateEnd ? inputDateEnd.value : null;
  const date_mode = selectDateType ? selectDateType.value : 'any';

  // Mostrar estado de carregamento
  showLoading(true, `A pesquisar fornecedores de "${entityName || nif}"...`);

  try {
    const response = await fetch('/api/suppliers/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nif,
        entity_name: entityName,
        source,
        limit,
        date_start,
        date_end,
        date_mode
      })
    });

    if (!response.ok) {
      throw new Error(`Erro na pesquisa (${response.status})`);
    }

    const data = await response.json();
    allSuppliers = data.suppliers || [];
    currentFilteredSuppliers = [...allSuppliers];

    // Atualizar estatísticas e indicadores
    const stats = data.stats || {};
    if (totalSuppliersCount) totalSuppliersCount.textContent = stats.total_suppliers || allSuppliers.length;
    if (totalAmountBadge) totalAmountBadge.textContent = stats.total_amount || '0,00 €';
    if (visibleCount) visibleCount.textContent = currentFilteredSuppliers.length;

    if (lastUpdateText) {
      lastUpdateText.textContent = `${allSuppliers.length} fornecedores recolhidos às ${new Date().toLocaleTimeString('pt-PT')}`;
    }

    // Exibir barra de filtros
    if (filterSection) {
      filterSection.classList.remove('hidden');
    }

    renderSuppliersList();

  } catch (error) {
    console.error('Erro na pesquisa de fornecedores:', error);
    alert(`Ocorreu um erro ao obter fornecedores: ${error.message}`);
  } finally {
    showLoading(false);
  }
}

function showLoading(show, title = null) {
  if (loadingState) loadingState.classList.toggle('hidden', !show);
  if (emptyState && show) emptyState.classList.add('hidden');
  if (btnSubmitSearch) btnSubmitSearch.disabled = show;
  if (title && document.getElementById('loading-title')) {
    document.getElementById('loading-title').textContent = title;
  }
}

function renderSuppliersList() {
  if (!suppliersList) return;

  if (currentFilteredSuppliers.length === 0) {
    suppliersList.innerHTML = `
      <div class="state-card">
        <div class="state-icon">🔍</div>
        <h3>Nenhum fornecedor encontrado</h3>
        <p>Não foram encontrados fornecedores correspondentes aos filtros selecionados. Tente ajustar os termos ou o período temporal.</p>
      </div>
    `;
    return;
  }

  suppliersList.innerHTML = currentFilteredSuppliers.map((s, idx) => createSupplierCardHtml(s, idx)).join('');
}

function createSupplierCardHtml(s, idx) {
  const enr = s.enrichment || {};
  const nif = s.nif || enr.nif || 'NIF N/D';
  const name = s.name || 'Fornecedor';
  const locality = enr.locality || 'Portugal';
  const address = enr.full_address || enr.street_address || '';
  const phone = enr.phone || (enr.phones && enr.phones[0]) || '';
  const email = enr.email || (enr.emails && enr.emails[0]) || '';
  const website = enr.website || '';
  const social = enr.social_media || {};
  const contractsCount = s.contracts_count || 1;
  const totalVal = s.total_value || 'Sob consulta';
  const latestDate = s.latest_date || 'N/D';
  const latestTitle = s.latest_title || 'Fornecimento / Prestação de Serviços';
  const latestProc = s.latest_procedure || 'Ajuste Direto';

  const isCurrentActive = activeSupplierIndex === idx;

  return `
    <article class="contract-card supplier-card ${isCurrentActive ? 'card-selected' : ''}" id="card-supplier-${idx}" data-idx="${idx}">
      <div class="card-top">
        <div class="card-badges-left">
          <span class="status-badge badge-signed">🏢 Fornecedor Oficial</span>
          <span class="party-nif">NIF: ${escapeHtml(nif)}</span>
          <span class="source-badge badge-base">📍 ${escapeHtml(locality)}</span>
          <span class="framework-tag">🏆 ${contractsCount} Contrato${contractsCount > 1 ? 's' : ''}</span>
          <span class="procedure-type-badge">${escapeHtml(latestProc)}</span>
        </div>
        <div class="card-top-right">
          ${enr.base_gov_url ? `
            <a href="${escapeHtml(enr.base_gov_url)}" target="_blank" rel="noopener noreferrer" class="link-official-card" title="Abrir ficha oficial no Portal BASE">
              Portal BASE ↗
            </a>
          ` : ''}
          ${enr.racius_url ? `
            <a href="${escapeHtml(enr.racius_url)}" target="_blank" rel="noopener noreferrer" class="link-official-card" title="Ver ficha no Racius">
              Racius ↗
            </a>
          ` : ''}
        </div>
      </div>

      <h2 class="contract-title">${escapeHtml(name)}</h2>

      <!-- Sede & Contactos Principais -->
      <div class="contract-parties-row">
        <div class="party-item">
          <span class="party-icon">📍</span>
          <span class="party-label">Sede / Morada:</span>
          <strong class="party-name">${escapeHtml(address || 'Morada oficial disponível mediante consulta no Portal BASE')}</strong>
          ${enr.google_maps_url ? `<a href="${escapeHtml(enr.google_maps_url)}" target="_blank" class="party-nif" style="text-decoration: underline;">Ver no Mapa ↗</a>` : ''}
        </div>
        <div class="party-item">
          <span class="party-icon">📞</span>
          <span class="party-label">Contactos Principais:</span>
          <strong class="party-name">
            ${phone ? `<a href="tel:${phone.replace(/\s+/g, '')}" style="color: #2563eb; text-decoration: none;">📞 ${phone}</a>` : 'Telefone disponível na ficha'}
            ${email ? ` &bull; <a href="mailto:${escapeHtml(email)}" style="color: #db2777; text-decoration: none;">✉️ ${escapeHtml(email)}</a>` : ''}
          </strong>
          ${website ? `<a href="${escapeHtml(website)}" target="_blank" rel="noopener noreferrer" class="party-nif" style="color: #166534; font-weight: 700;">🌐 ${escapeHtml(website.replace(/^https?:\/\//, ''))}</a>` : ''}
        </div>
      </div>

      <!-- Grid com os 4 Pilares do Fornecedor -->
      <div class="contract-pillars-grid">
        <div class="pillar-box">
          <span class="p-label">💰 Volume Total Adjudicado</span>
          <strong class="p-value highlight-price">${escapeHtml(totalVal)}</strong>
        </div>
        <div class="pillar-box">
          <span class="p-label">📑 Contratos Celebrados</span>
          <strong class="p-value">${contractsCount} contrato${contractsCount > 1 ? 's' : ''}</strong>
        </div>
        <div class="pillar-box">
          <span class="p-label">📅 Último Contrato Celebrado</span>
          <strong class="p-value highlight-date">${escapeHtml(latestDate)}</strong>
        </div>
        <div class="pillar-box">
          <span class="p-label">🏢 Atividade / Setor</span>
          <strong class="p-value" style="font-size: 0.85rem; font-weight: 600;" title="${escapeHtml(enr.activity_description || latestTitle)}">
            ${escapeHtml((enr.activity_description || latestTitle).substring(0, 45))}...
          </strong>
        </div>
      </div>

      <!-- Resumo do Último Contrato -->
      <div class="contract-desc-box">
        <span class="desc-label">Último Procedimento:</span>
        <span class="desc-content">${escapeHtml(latestTitle)}</span>
      </div>

      <!-- Rodapé do Cartão com Ações e Redes Sociais -->
      <div class="card-bottom">
        <div class="matched-badges">
          ${social.linkedin ? `<a href="${escapeHtml(social.linkedin)}" target="_blank" class="platform-badge badge-vortal">in LinkedIn</a>` : ''}
          ${social.facebook ? `<a href="${escapeHtml(social.facebook)}" target="_blank" class="platform-badge badge-acingov">fb Facebook</a>` : ''}
          <a href="${escapeHtml(enr.google_search_url || `https://www.google.com/search?q=${encodeURIComponent(name)}`)}" target="_blank" class="platform-badge">🔍 Google Web</a>
        </div>
        <div class="card-actions">
          <button type="button" class="btn btn-primary btn-sm" onclick="openSupplierSidebar(${idx})">
            <span>📋</span> <span>Ver Raio-X & Todos os Contratos (${contractsCount})</span>
          </button>
        </div>
      </div>
    </article>
  `;
}

function openSupplierSidebar(idx) {
  const supplier = currentFilteredSuppliers[idx];
  if (!supplier) return;

  activeSupplierIndex = idx;
  const enr = supplier.enrichment || {};
  const social = enr.social_media || {};

  // Destacar cartão selecionado
  document.querySelectorAll('.supplier-card').forEach(c => c.classList.remove('card-selected'));
  const card = document.getElementById(`card-supplier-${idx}`);
  if (card) card.classList.add('card-selected');

  // Atualizar cabeçalho da barra lateral
  document.getElementById('sb-supplier-name').textContent = supplier.name;
  document.getElementById('sb-supplier-nif').textContent = `NIF: ${supplier.nif || enr.nif || 'N/D'}`;
  document.getElementById('sb-supplier-legal').textContent = enr.legal_name || supplier.name;

  // Atualizar resumo financeiro
  document.getElementById('sb-total-amount').textContent = supplier.total_value;
  document.getElementById('sb-contracts-count').textContent = `${supplier.contracts_count} contrato(s)`;
  if (sidebarContractsCountBadge) {
    sidebarContractsCountBadge.textContent = supplier.contracts_count;
  }

  // Atualizar morada
  const addr = enr.full_address || enr.street_address || 'Morada oficial disponível para consulta pública nos portais governamentais';
  document.getElementById('sb-address').textContent = addr;
  document.getElementById('sb-locality').textContent = `${enr.postal_code || ''} ${enr.locality || ''}`.trim() || 'Portugal';
  const mapsLink = document.getElementById('sb-maps-link');
  if (mapsLink) {
    mapsLink.href = enr.google_maps_url || `https://www.google.com/maps/search/${encodeURIComponent(addr)}`;
  }

  // Atualizar contactos
  const phoneEl = document.getElementById('sb-phone');
  if (phoneEl) {
    const phone = enr.phone || (enr.phones && enr.phones.join(', '));
    if (phone) {
      phoneEl.innerHTML = `<a href="tel:${phone.replace(/\s+/g, '')}" style="color: #2563eb; font-weight: 700; text-decoration: none;">📞 ${phone}</a>`;
    } else {
      phoneEl.textContent = 'Não especificado no registo prévio';
    }
  }

  const emailEl = document.getElementById('sb-email');
  if (emailEl) {
    const email = enr.email || (enr.emails && enr.emails.join(', '));
    if (email) {
      emailEl.innerHTML = `<a href="mailto:${escapeHtml(email)}" style="color: #db2777; font-weight: 700; text-decoration: none;">✉️ ${escapeHtml(email)}</a>`;
    } else {
      emailEl.textContent = 'Disponível no caderno de encargos do contrato';
    }
  }

  const webEl = document.getElementById('sb-website');
  if (webEl) {
    if (enr.website) {
      webEl.innerHTML = `<a href="${escapeHtml(enr.website)}" target="_blank" rel="noopener noreferrer" style="color: #166534; font-weight: 700; text-decoration: underline;">🌐 ${escapeHtml(enr.website)}</a>`;
    } else {
      webEl.textContent = 'Não especificado';
    }
  }

  // Redes Sociais
  const socialsBox = document.getElementById('sb-socials');
  if (socialsBox) {
    let sHtml = '';
    if (social.linkedin) {
      sHtml += `<a href="${escapeHtml(social.linkedin)}" target="_blank" class="platform-badge badge-vortal">in LinkedIn</a>`;
    }
    if (social.facebook) {
      sHtml += `<a href="${escapeHtml(social.facebook)}" target="_blank" class="platform-badge badge-acingov">fb Facebook</a>`;
    }
    sHtml += `<a href="${escapeHtml(enr.google_search_url || '#')}" target="_blank" class="platform-badge">🔍 Google Web</a>`;
    socialsBox.innerHTML = sHtml;
  }

  // Atividade
  const actEl = document.getElementById('sb-activity');
  if (actEl) {
    actEl.textContent = enr.activity_description || 'Fornecimentos de bens, prestação de serviços ou empreitadas de obras públicas.';
  }

  // Links Oficiais
  const linkBase = document.getElementById('sb-link-base');
  if (linkBase) linkBase.href = enr.base_gov_url || `https://www.base.gov.pt/Base4/pt/pesquisa/?type=contratos&adjudicataria=${encodeURIComponent(supplier.nif || supplier.name)}`;

  const linkRacius = document.getElementById('sb-link-racius');
  if (linkRacius) linkRacius.href = enr.racius_url || `https://www.racius.com/pesquisa/?q=${encodeURIComponent(supplier.nif || supplier.name)}`;

  const linkNif = document.getElementById('sb-link-nif');
  if (linkNif) linkNif.href = enr.nif_pt_url || `https://www.nif.pt/${supplier.nif}/`;

  const linkGoogle = document.getElementById('sb-link-google');
  if (linkGoogle) linkGoogle.href = enr.google_search_url || `https://www.google.com/search?q=${encodeURIComponent(supplier.name)}`;

  // Preencher Lista de Contratos na Aba 2
  const contractsItemsBox = document.getElementById('sb-contracts-list-items');
  if (contractsItemsBox) {
    const contracts = supplier.contracts || [];
    if (contracts.length === 0) {
      contractsItemsBox.innerHTML = '<p class="sidebar-no-results">Nenhum contrato individual encontrado.</p>';
    } else {
      contractsItemsBox.innerHTML = contracts.map((c, cIdx) => {
        const val = c.value || 'Sob consulta';
        const sDate = c.signing_date || 'N/D';
        const pDate = c.publication_date || 'N/D';
        const obj = c.title || 'Contrato Público';
        const proc = c.procedure_type || 'Ajuste Direto';
        const directUrl = c.direct_url || '#';

        return `
          <div class="sidebar-match-card">
            <div class="sidebar-match-header">
              <span class="match-source-tag">#${cIdx + 1} &bull; ${escapeHtml(proc)}</span>
              <strong style="color: #059669; font-size: 0.95rem;">${escapeHtml(val)}</strong>
            </div>
            <p class="sidebar-match-title">${escapeHtml(obj)}</p>
            <div class="sidebar-match-footer" style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
              <span class="sidebar-match-meta">📅 Assinatura: ${escapeHtml(sDate)} | Publicação: ${escapeHtml(pDate)}</span>
              ${directUrl !== '#' ? `
                <a href="${escapeHtml(directUrl)}" target="_blank" rel="noopener noreferrer" class="link-official-card" style="font-size: 0.76rem; padding: 2px 8px;">
                  BASE ↗
                </a>
              ` : ''}
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // Exibir conteúdo
  if (sidebarRaioxEmpty) sidebarRaioxEmpty.classList.add('hidden');
  if (sidebarRaioxContent) sidebarRaioxContent.classList.remove('hidden');

  // Abrir painel lateral
  if (sidebarPanel) sidebarPanel.classList.remove('hidden');
  if (suppliersContentColumn) suppliersContentColumn.classList.add('expanded-with-sidebar');
  if (btnToggleSidebar) btnToggleSidebar.classList.add('active');
}

function closeSidebar() {
  if (sidebarPanel) sidebarPanel.classList.add('hidden');
  if (suppliersContentColumn) suppliersContentColumn.classList.remove('expanded-with-sidebar');
  if (btnToggleSidebar) btnToggleSidebar.classList.remove('active');
  document.querySelectorAll('.supplier-card').forEach(c => c.classList.remove('card-selected'));
  activeSupplierIndex = null;
}

function toggleSidebar() {
  if (!sidebarPanel) return;
  const isHidden = sidebarPanel.classList.contains('hidden');
  if (isHidden) {
    if (activeSupplierIndex !== null) {
      openSupplierSidebar(activeSupplierIndex);
    } else if (currentFilteredSuppliers.length > 0) {
      openSupplierSidebar(0);
    }
  } else {
    closeSidebar();
  }
}

function switchSidebarTab(tabName) {
  if (tabName === 'raiox') {
    if (tabSidebarRaiox) tabSidebarRaiox.classList.add('active');
    if (tabSidebarContracts) tabSidebarContracts.classList.remove('active');
    if (sidebarViewRaiox) sidebarViewRaiox.classList.remove('hidden');
    if (sidebarViewContracts) sidebarViewContracts.classList.add('hidden');
  } else if (tabName === 'contracts') {
    if (tabSidebarContracts) tabSidebarContracts.classList.add('active');
    if (tabSidebarRaiox) tabSidebarRaiox.classList.remove('active');
    if (sidebarViewContracts) sidebarViewContracts.classList.remove('hidden');
    if (sidebarViewRaiox) sidebarViewRaiox.classList.add('hidden');
  }
}

function applyFilters() {
  const qName = normalizeStr(filterName ? filterName.value.trim() : '');
  const qLoc = normalizeStr(filterLocality ? filterLocality.value.trim() : '');
  const amountVal = filterAmount ? filterAmount.value : 'all';
  const qWords = normalizeStr(filterWords ? filterWords.value.trim() : '');

  currentFilteredSuppliers = allSuppliers.filter(s => {
    const enr = s.enrichment || {};

    // 1. Filtro por Nome ou NIF
    if (qName) {
      const matchName = normalizeStr(s.name).includes(qName);
      const matchNif = normalizeStr(s.nif).includes(qName);
      if (!matchName && !matchNif) return false;
    }

    // 2. Filtro por Localidade / Sede
    if (qLoc) {
      const matchLoc = normalizeStr(enr.locality).includes(qLoc);
      const matchAddr = normalizeStr(enr.full_address).includes(qLoc);
      if (!matchLoc && !matchAddr) return false;
    }

    // 3. Filtro por Escalão de Valor
    if (amountVal !== 'all') {
      const val = s.total_value_raw || 0;
      if (amountVal === 'over_50k' && val < 50000) return false;
      if (amountVal === 'over_100k' && val < 100000) return false;
      if (amountVal === 'over_500k' && val < 500000) return false;
      if (amountVal === 'over_1m' && val < 1000000) return false;
    }

    // 4. Filtro por Palavras / Setor / Contratos
    if (qWords) {
      const haystack = [
        enr.activity_description,
        s.latest_title,
        ...(s.categories || []),
        ...(s.contracts || []).map(c => c.title)
      ].join(' ');
      if (!normalizeStr(haystack).includes(qWords)) return false;
    }

    return true;
  });

  if (visibleCount) visibleCount.textContent = currentFilteredSuppliers.length;
  renderSuppliersList();
}

function clearAllFilters() {
  if (filterName) filterName.value = '';
  if (filterLocality) filterLocality.value = '';
  if (filterAmount) filterAmount.value = 'all';
  if (filterWords) filterWords.value = '';
  if (btnClearWords) btnClearWords.classList.add('hidden');
  applyFilters();
}

async function exportToExcel() {
  if (currentFilteredSuppliers.length === 0) {
    alert('Não existem fornecedores para exportar.');
    return;
  }

  try {
    const response = await fetch('/api/suppliers/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ suppliers: currentFilteredSuppliers })
    });

    if (!response.ok) {
      throw new Error(`Erro na exportação (${response.status})`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fornecedores_${new Date().toISOString().substring(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error('Erro ao exportar:', err);
    alert(`Ocorreu um erro ao exportar: ${err.message}`);
  }
}

function normalizeStr(str) {
  if (!str) return '';
  return str.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
