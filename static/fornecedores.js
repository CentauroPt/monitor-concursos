/**
 * Pesquisa de Fornecedores de Entidades Públicas - Portal BASE & Autarquias
 * Suporta identificação de fornecedores, agregação contratual,
 * enriquecimento cadastral (moradas, contactos, websites, redes sociais)
 * e gaveta lateral de raio-x empresarial.
 */

let allSuppliers = [];
let filteredSuppliers = [];
let activeDrawerSupplier = null;

document.addEventListener('DOMContentLoaded', () => {
  // Preencher datas padrão: último ano até hoje
  setDateRange('last_year');

  // Fechar gaveta com tecla ESC
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeSupplierDrawer();
    }
  });

  // Verificar se há parâmetros na URL (ex: ?nif=505170940)
  const urlParams = new URLSearchParams(window.location.search);
  const nifParam = urlParams.get('nif');
  const nameParam = urlParams.get('nome') || urlParams.get('entidade');
  if (nifParam || nameParam) {
    const input = document.getElementById('supplier-entity-input');
    if (input) {
      input.value = nifParam || nameParam;
      handleSupplierSearch();
    }
  }
});

function setEntityQuick(nif, name) {
  const input = document.getElementById('supplier-entity-input');
  if (input) {
    input.value = nif || name;
    handleSupplierSearch();
  }
}

function clearSupplierInput() {
  const input = document.getElementById('supplier-entity-input');
  if (input) {
    input.value = '';
    input.focus();
  }
}

function setDateRange(rangeType) {
  const startInput = document.getElementById('supplier-date-start');
  const endInput = document.getElementById('supplier-date-end');
  if (!startInput || !endInput) return;

  const now = new Date();
  const formatYMD = (d) => d.toISOString().split('T')[0];

  endInput.value = formatYMD(now);

  if (rangeType === 'last_month') {
    const past = new Date(now);
    past.setMonth(past.getMonth() - 1);
    startInput.value = formatYMD(past);
  } else if (rangeType === 'last_6m') {
    const past = new Date(now);
    past.setMonth(past.getMonth() - 6);
    startInput.value = formatYMD(past);
  } else if (rangeType === 'last_year') {
    const past = new Date(now);
    past.setFullYear(past.getFullYear() - 1);
    startInput.value = formatYMD(past);
  } else if (rangeType === 'all') {
    startInput.value = '';
    endInput.value = '';
  }
}

async function handleSupplierSearch() {
  const entityInput = document.getElementById('supplier-entity-input');
  const query = entityInput ? entityInput.value.trim() : '';

  if (!query) {
    alert('Por favor, introduza o NIF ou o Nome da Autarquia / Entidade Adjudicante.');
    if (entityInput) entityInput.focus();
    return;
  }

  let nif = null;
  let entity_name = null;

  const cleanDigits = query.replace(/\D/g, '');
  if (cleanDigits.length === 9) {
    nif = cleanDigits;
    entity_name = query;
  } else {
    entity_name = query;
  }

  const date_start = document.getElementById('supplier-date-start')?.value || null;
  const date_end = document.getElementById('supplier-date-end')?.value || null;
  const date_mode = document.getElementById('supplier-date-mode')?.value || 'any';
  const source = document.getElementById('supplier-source')?.value || 'all';

  // Mostrar indicador de carregamento
  showLoading(true, `A pesquisar fornecedores de "${query}"...`);

  try {
    const response = await fetch('/api/suppliers/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nif,
        entity_name,
        date_start,
        date_end,
        date_mode,
        source,
        limit: 100
      })
    });

    if (!response.ok) {
      throw new Error(`Erro no servidor (${response.status})`);
    }

    const data = await response.json();
    allSuppliers = data.suppliers || [];
    filteredSuppliers = [...allSuppliers];

    updateKPIs(data.stats || {});
    renderSuppliersTable();

    // Ativar botões de exportação se houver dados
    const hasData = allSuppliers.length > 0;
    const btnExcel = document.getElementById('btn-export-excel');
    const btnPdf = document.getElementById('btn-export-pdf');
    if (btnExcel) btnExcel.disabled = !hasData;
    if (btnPdf) btnPdf.disabled = !hasData;

    const lastUpdate = document.getElementById('last-update-text');
    if (lastUpdate) {
      lastUpdate.textContent = `${allSuppliers.length} fornecedores identificados em ${new Date().toLocaleTimeString('pt-PT')}`;
    }

  } catch (error) {
    console.error('Erro ao pesquisar fornecedores:', error);
    alert(`Ocorreu um erro ao obter os fornecedores: ${error.message}`);
  } finally {
    showLoading(false);
  }
}

function showLoading(show, title = null) {
  const loading = document.getElementById('suppliers-loading');
  const emptyState = document.getElementById('suppliers-empty-state');
  const tableContainer = document.getElementById('suppliers-table-container');
  const kpis = document.getElementById('suppliers-kpis');
  const filterBar = document.getElementById('suppliers-filter-bar');
  const btn = document.getElementById('btn-search-suppliers');

  if (show) {
    if (loading) loading.style.display = 'flex';
    if (title && document.getElementById('loading-title')) {
      document.getElementById('loading-title').textContent = title;
    }
    if (emptyState) emptyState.style.display = 'none';
    if (tableContainer) tableContainer.style.display = 'none';
    if (kpis) kpis.style.display = 'none';
    if (filterBar) filterBar.style.display = 'none';
    if (btn) btn.disabled = true;
  } else {
    if (loading) loading.style.display = 'none';
    if (btn) btn.disabled = false;
  }
}

function updateKPIs(stats) {
  const kpis = document.getElementById('suppliers-kpis');
  const filterBar = document.getElementById('suppliers-filter-bar');

  if (kpis) kpis.style.display = 'grid';
  if (filterBar) filterBar.style.display = 'flex';

  document.getElementById('kpi-total-suppliers').textContent = stats.total_suppliers || allSuppliers.length || '0';
  document.getElementById('kpi-total-amount').textContent = stats.total_amount || '0,00 €';
  document.getElementById('kpi-total-contracts').textContent = stats.total_contracts || '0';
  document.getElementById('kpi-avg-amount').textContent = stats.avg_amount || '0,00 €';
}

function renderSuppliersTable() {
  const tbody = document.getElementById('suppliers-table-body');
  const tableContainer = document.getElementById('suppliers-table-container');
  const emptyState = document.getElementById('suppliers-empty-state');

  if (!tbody || !tableContainer) return;

  if (filteredSuppliers.length === 0) {
    tableContainer.style.display = 'none';
    if (emptyState) {
      emptyState.style.display = 'block';
      emptyState.innerHTML = `
        <div class="empty-icon">🔍</div>
        <h3>Nenhum fornecedor encontrado</h3>
        <p>Não foram encontrados fornecedores para os critérios especificados. Tente alargar o período temporal ou verificar a designação da entidade.</p>
      `;
    }
    return;
  }

  if (emptyState) emptyState.style.display = 'none';
  tableContainer.style.display = 'block';

  let html = '';
  filteredSuppliers.forEach((s, idx) => {
    const enr = s.enrichment || {};
    const nif = s.nif || enr.nif || 'NIF N/D';
    const name = s.name || 'Fornecedor sem designação';
    const locality = enr.locality || enr.postal_code || 'Portugal';
    const address = enr.full_address || enr.street_address || '';
    
    // Contactos rápidos
    const phone = enr.phone || (enr.phones && enr.phones[0]) || '';
    const email = enr.email || (enr.emails && enr.emails[0]) || '';
    const website = enr.website || '';
    const social = enr.social_media || {};

    // Último contrato
    const lastDate = s.latest_date || 'N/D';
    const lastTitle = s.latest_title || 'Contrato Público';
    const lastProc = s.latest_procedure || 'Ajuste Direto';

    html += `
      <tr class="supplier-row">
        <!-- Coluna 1: Fornecedor -->
        <td class="col-supplier">
          <div class="supplier-name-box">
            <span class="supplier-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
            <div class="supplier-meta-tags">
              <span class="badge-nif">NIF ${nif}</span>
              ${locality ? `<span class="badge-locality">📍 ${escapeHtml(locality)}</span>` : ''}
            </div>
            ${address && address !== 'Morada disponível mediante consulta pública' ? `
              <div class="supplier-address-snippet" title="${escapeHtml(address)}">
                <span class="addr-icon">🏢</span> ${escapeHtml(address)}
              </div>
            ` : ''}
          </div>
        </td>

        <!-- Coluna 2: Volume Contratual com a Autarquia -->
        <td class="col-volume">
          <div class="volume-box">
            <span class="volume-amount">${s.total_value}</span>
            <span class="contracts-count-badge">${s.contracts_count} contrato${s.contracts_count > 1 ? 's' : ''} ganho${s.contracts_count > 1 ? 's' : ''}</span>
          </div>
        </td>

        <!-- Coluna 3: Contactos Rápidos & Presença Web -->
        <td class="col-contacts">
          <div class="contacts-list">
            ${phone ? `
              <a href="tel:${phone.replace(/\s+/g, '')}" class="contact-pill phone-pill" title="Ligar para ${phone}">
                <span class="pill-icon">📞</span> ${phone}
              </a>
            ` : ''}
            ${email ? `
              <a href="mailto:${email}" class="contact-pill email-pill" title="Enviar email para ${email}">
                <span class="pill-icon">✉️</span> ${escapeHtml(email)}
              </a>
            ` : ''}
            ${website ? `
              <a href="${website}" target="_blank" rel="noopener noreferrer" class="contact-pill web-pill" title="Visitar website oficial">
                <span class="pill-icon">🌐</span> Website Oficial
              </a>
            ` : ''}
            
            <div class="social-pills-row">
              ${social.linkedin ? `<a href="${social.linkedin}" target="_blank" rel="noopener noreferrer" class="social-mini-btn linkedin" title="Ver LinkedIn">in</a>` : ''}
              ${social.facebook ? `<a href="${social.facebook}" target="_blank" rel="noopener noreferrer" class="social-mini-btn facebook" title="Ver Facebook">fb</a>` : ''}
              <a href="${enr.google_search_url || `https://www.google.com/search?q=${encodeURIComponent(name)}`}" target="_blank" rel="noopener noreferrer" class="social-mini-btn google" title="Pesquisar no Google">G</a>
            </div>
          </div>
        </td>

        <!-- Coluna 4: Último Contrato -->
        <td class="col-latest-contract">
          <div class="latest-contract-box">
            <div class="latest-contract-header">
              <span class="latest-date">📅 ${lastDate}</span>
              <span class="latest-proc">${escapeHtml(lastProc)}</span>
            </div>
            <p class="latest-title" title="${escapeHtml(lastTitle)}">${escapeHtml(lastTitle)}</p>
          </div>
        </td>

        <!-- Coluna 5: Ações / Raio-X -->
        <td class="col-actions">
          <button type="button" class="btn-raiox" onclick="openSupplierDrawer(${idx})" title="Abrir raio-x completo do fornecedor e todos os contratos">
            <span class="btn-action-icon">👁️</span>
            <span>Raio-X</span>
          </button>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

function applyTableFilters() {
  const searchInput = document.getElementById('table-filter-input');
  const term = searchInput ? searchInput.value.toLowerCase().trim() : '';
  const amountFilter = document.getElementById('filter-amount')?.value || 'all';

  filteredSuppliers = allSuppliers.filter(s => {
    // Filtro por texto
    if (term) {
      const enr = s.enrichment || {};
      const haystack = [
        s.name,
        s.nif,
        enr.full_address,
        enr.locality,
        enr.activity_description,
        s.latest_title,
        ...(s.categories || [])
      ].join(' ').toLowerCase();

      if (!haystack.includes(term)) return false;
    }

    // Filtro por montante
    const val = s.total_value_raw || 0;
    if (amountFilter === 'over_100k' && val < 100000) return false;
    if (amountFilter === 'over_500k' && val < 500000) return false;
    if (amountFilter === 'over_1m' && val < 1000000) return false;

    return true;
  });

  applyTableSorting(false);
  renderSuppliersTable();
}

function applyTableSorting(reRender = true) {
  const sort = document.getElementById('sort-select')?.value || 'value_desc';

  filteredSuppliers.sort((a, b) => {
    if (sort === 'value_desc') {
      return (b.total_value_raw || 0) - (a.total_value_raw || 0);
    } else if (sort === 'contracts_desc') {
      return (b.contracts_count || 0) - (a.contracts_count || 0);
    } else if (sort === 'date_desc') {
      return String(b.latest_date || '').localeCompare(String(a.latest_date || ''));
    } else if (sort === 'name_asc') {
      return String(a.name || '').localeCompare(String(b.name || ''));
    }
    return 0;
  });

  if (reRender) {
    renderSuppliersTable();
  }
}

function openSupplierDrawer(index) {
  const supplier = filteredSuppliers[index];
  if (!supplier) return;

  activeDrawerSupplier = supplier;
  const enr = supplier.enrichment || {};
  const social = enr.social_media || {};

  // Atualizar cabeçalho
  document.getElementById('drawer-company-name').textContent = supplier.name;
  document.getElementById('drawer-company-nif').textContent = `NIF: ${supplier.nif || enr.nif || 'Não disponível'}`;

  // Morada e contactos
  const addressText = enr.full_address || enr.street_address || 'Morada disponível mediante consulta pública no Portal BASE e diretórios empresariais';
  document.getElementById('drawer-address').textContent = addressText;

  const mapsBtn = document.getElementById('drawer-maps-link');
  if (mapsBtn) {
    mapsBtn.href = enr.google_maps_url || `https://www.google.com/maps/search/${encodeURIComponent(addressText)}`;
  }

  // Telefones
  const phoneVal = enr.phone || (enr.phones && enr.phones.join(' / ')) || 'Disponível via consulta ao Portal BASE';
  const phoneEl = document.getElementById('drawer-phone');
  if (phoneEl) {
    if (enr.phone) {
      phoneEl.innerHTML = `<a href="tel:${enr.phone.replace(/\s+/g, '')}" class="link-direct-contact">📞 ${enr.phone}</a>`;
    } else {
      phoneEl.textContent = phoneVal;
    }
  }

  // Emails
  const emailVal = enr.email || (enr.emails && enr.emails.join(' / ')) || 'Disponível no processo do contrato';
  const emailEl = document.getElementById('drawer-email');
  if (emailEl) {
    if (enr.email) {
      emailEl.innerHTML = `<a href="mailto:${enr.email}" class="link-direct-contact">✉️ ${escapeHtml(enr.email)}</a>`;
    } else {
      emailEl.textContent = emailVal;
    }
  }

  // Website
  const webEl = document.getElementById('drawer-website');
  if (webEl) {
    if (enr.website) {
      webEl.innerHTML = `<a href="${enr.website}" target="_blank" rel="noopener noreferrer" class="link-direct-contact">🌐 ${escapeHtml(enr.website)}</a>`;
    } else {
      webEl.textContent = 'Não especificado';
    }
  }

  // Redes Sociais
  const socialsContainer = document.getElementById('drawer-socials');
  if (socialsContainer) {
    let sHtml = '';
    if (social.linkedin) {
      sHtml += `<a href="${social.linkedin}" target="_blank" class="social-pill linkedin">💼 LinkedIn</a>`;
    }
    if (social.facebook) {
      sHtml += `<a href="${social.facebook}" target="_blank" class="social-pill facebook">📘 Facebook</a>`;
    }
    if (social.instagram) {
      sHtml += `<a href="${social.instagram}" target="_blank" class="social-pill instagram">📸 Instagram</a>`;
    }
    sHtml += `<a href="${enr.google_search_url || '#'}" target="_blank" class="social-pill google">🔍 Google Web</a>`;
    socialsContainer.innerHTML = sHtml;
  }

  // Atividade
  const actEl = document.getElementById('drawer-activity');
  if (actEl) {
    actEl.textContent = enr.activity_description || 'Fornecimento de bens, serviços ou empreitadas em procedimentos de contratação pública.';
  }

  // Resumo financeiro
  document.getElementById('drawer-total-amount').textContent = supplier.total_value;
  document.getElementById('drawer-contracts-count').textContent = supplier.contracts_count;

  // Lista de Contratos
  const contractsListContainer = document.getElementById('drawer-contracts-list');
  if (contractsListContainer) {
    const contracts = supplier.contracts || [];
    if (contracts.length === 0) {
      contractsListContainer.innerHTML = '<p class="no-contracts-text">Nenhum detalhe adicional de contrato disponível.</p>';
    } else {
      let cHtml = '';
      contracts.forEach((c, cIdx) => {
        const val = c.value || 'Sob consulta';
        const sDate = c.signing_date || 'N/D';
        const pDate = c.publication_date || 'N/D';
        const obj = c.title || 'Sem título especificado';
        const proc = c.procedure_type || 'Ajuste Direto';
        const plat = c.platform_name || 'Portal BASE';
        const directUrl = c.direct_url || '#';

        cHtml += `
          <div class="drawer-contract-card">
            <div class="contract-card-top">
              <span class="card-contract-num">#${cIdx + 1}</span>
              <span class="card-contract-proc">${escapeHtml(proc)}</span>
              <span class="card-contract-value">${escapeHtml(val)}</span>
            </div>
            <h4 class="card-contract-title">${escapeHtml(obj)}</h4>
            <div class="card-contract-dates">
              <span>✍️ Celebração: <strong>${escapeHtml(sDate)}</strong></span>
              <span>📢 Publicação: <strong>${escapeHtml(pDate)}</strong></span>
              <span>🏢 Plataforma: <strong>${escapeHtml(plat)}</strong></span>
            </div>
            ${directUrl !== '#' ? `
              <div class="card-contract-link">
                <a href="${directUrl}" target="_blank" rel="noopener noreferrer" class="btn-contract-source">
                  <span>🇵🇹 Ver Contrato Oficial no Portal BASE</span> ↗
                </a>
              </div>
            ` : ''}
          </div>
        `;
      });
      contractsListContainer.innerHTML = cHtml;
    }
  }

  // Links externos de verificação
  const baseLink = document.getElementById('drawer-link-base');
  if (baseLink) baseLink.href = enr.base_gov_url || `https://www.base.gov.pt/Base4/pt/pesquisa/?type=contratos&adjudicataria=${encodeURIComponent(supplier.nif || supplier.name)}`;

  const raciusLink = document.getElementById('drawer-link-racius');
  if (raciusLink) raciusLink.href = enr.racius_url || `https://www.racius.com/pesquisa/?q=${encodeURIComponent(supplier.nif || supplier.name)}`;

  const nifLink = document.getElementById('drawer-link-nif');
  if (nifLink) nifLink.href = enr.nif_pt_url || `https://www.nif.pt/${supplier.nif}/`;

  const googleLink = document.getElementById('drawer-link-google');
  if (googleLink) googleLink.href = enr.google_search_url || `https://www.google.com/search?q=${encodeURIComponent(supplier.name)}`;

  // Abrir gaveta
  const drawer = document.getElementById('supplier-drawer');
  const backdrop = document.getElementById('supplier-drawer-backdrop');
  if (drawer) drawer.classList.add('open');
  if (backdrop) backdrop.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeSupplierDrawer() {
  const drawer = document.getElementById('supplier-drawer');
  const backdrop = document.getElementById('supplier-drawer-backdrop');
  if (drawer) drawer.classList.remove('open');
  if (backdrop) backdrop.classList.remove('open');
  document.body.style.overflow = '';
  activeDrawerSupplier = null;
}

async function exportSuppliersExcel() {
  if (filteredSuppliers.length === 0) {
    alert('Não existem fornecedores para exportar.');
    return;
  }

  try {
    const response = await fetch('/api/suppliers/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ suppliers: filteredSuppliers })
    });

    if (!response.ok) {
      throw new Error(`Erro ao exportar (${response.status})`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fornecedores_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Erro ao exportar para Excel:', error);
    alert(`Erro na exportação: ${error.message}`);
  }
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
