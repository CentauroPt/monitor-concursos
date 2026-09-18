"""
Módulo de pesquisa e extração de dados do Portal BASE (base.gov.pt).
Suporta pesquisa de Anúncios de Procedimento e Contratos (Ajustes Diretos, etc.)
por palavras-chave e códigos CPV (34140000 - 34149999).
"""

import json
import logging
import re
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://www.base.gov.pt"
RESULTADOS_URL = f"{BASE_URL}/Base4/pt/resultados/"

KEYWORDS = [
    "Unidade Móvel",
    "Unidades Móveis",
    "Viatura especial",
    "Viaturas Especiais",
    "Carrinha",
    "Biblioteca itinerante"
]

CPV_PREFIX = "3414"

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/plain, */*; q=0.01',
    'Accept-Language': 'pt-PT,pt;q=0.9,en;q=0.8',
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': BASE_URL,
    'Referer': f"{BASE_URL}/Base4/pt/pesquisa/"
}


class BaseScraper:
    def __init__(self, timeout: int = 15):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout
        self.version = "87.0"  # Versão de fallback testada com sucesso
        self._detect_version()

    def _detect_version(self):
        """Deteta dinamicamente a versão da API requerida pelo Portal BASE."""
        try:
            r = self.session.get(f"{BASE_URL}/Base4/pt/pesquisa/?type=anuncios", timeout=self.timeout)
            if r.status_code == 200:
                m = re.search(r'version:\s*["\']([^"\']+)["\']', r.text)
                if m and m.group(1) != "0.0":
                    self.version = m.group(1)
        except Exception as e:
            logger.warning(f"Não foi possível detetar versão dinâmica do BASE, a usar {self.version}: {e}")

    def _post_query(self, search_type: str, query: str, size: int = 30, sort: str = "-drPublicationDate") -> List[Dict[str, Any]]:
        """Executa um POST no endpoint /Base4/pt/resultados/."""
        payload = {
            'type': search_type,
            'version': self.version,
            'query': query,
            'sort': sort,
            'page': '0',
            'size': str(size)
        }
        try:
            resp = self.session.post(RESULTADOS_URL, data=payload, timeout=self.timeout)
            if resp.status_code == 200 and resp.text.strip():
                try:
                    data = json.loads(resp.text)
                    return data.get('items', []) or []
                except Exception as ex:
                    # Em alguns casos o JSON tem espaços ou quebras
                    cleaned = resp.text.strip()
                    data = json.loads(cleaned)
                    return data.get('items', []) or []
        except Exception as e:
            logger.error(f"Erro ao pesquisar no BASE ({search_type}, query={query}): {e}")
        return []

    def search_anuncios(self, max_per_term: int = 25) -> List[Dict[str, Any]]:
        """Pesquisa Anúncios de Procedimento (concursos públicos, concursos limitados, etc.)."""
        results_map = {}

        # 1. Pesquisa por CPV 3414 (34140000 - 34149999)
        items = self._post_query(
            search_type="search_anuncios",
            query=f"cpv={CPV_PREFIX}",
            size=max_per_term,
            sort="-drPublicationDate"
        )
        for it in items:
            item_id = it.get('id')
            if item_id:
                results_map[f"anuncio_{item_id}"] = self._normalize_anuncio(it, matched_by=f"CPV {CPV_PREFIX}xxxx")

        # 2. Pesquisa por cada palavra-chave
        for kw in KEYWORDS:
            kw_items = self._post_query(
                search_type="search_anuncios",
                query=f"texto={kw}",
                size=max_per_term,
                sort="-drPublicationDate"
            )
            for it in kw_items:
                item_id = it.get('id')
                key = f"anuncio_{item_id}"
                if key in results_map:
                    results_map[key]['matched_terms'].add(kw)
                else:
                    results_map[key] = self._normalize_anuncio(it, matched_by=kw)

        return list(results_map.values())

    def search_contratos(self, max_per_term: int = 25) -> List[Dict[str, Any]]:
        """Pesquisa Contratos e Ajustes Diretos já publicados."""
        results_map = {}

        # 1. Pesquisa por CPV 3414
        items = self._post_query(
            search_type="search_contratos",
            query=f"cpv={CPV_PREFIX}",
            size=max_per_term,
            sort=""
        )
        for it in items:
            item_id = it.get('id')
            if item_id:
                results_map[f"contrato_{item_id}"] = self._normalize_contrato(it, matched_by=f"CPV {CPV_PREFIX}xxxx")

        # 2. Pesquisa por palavras-chave em contratos
        for kw in KEYWORDS:
            kw_items = self._post_query(
                search_type="search_contratos",
                query=f"texto={kw}",
                size=max_per_term,
                sort=""
            )
            for it in kw_items:
                item_id = it.get('id')
                key = f"contrato_{item_id}"
                if key in results_map:
                    results_map[key]['matched_terms'].add(kw)
                else:
                    results_map[key] = self._normalize_contrato(it, matched_by=kw)

        return list(results_map.values())

    def search_all(self, max_per_term: int = 25) -> List[Dict[str, Any]]:
        """Agrega pesquisa de anúncios e contratos do Portal BASE."""
        anuncios = self.search_anuncios(max_per_term=max_per_term)
        contratos = self.search_contratos(max_per_term=max_per_term)
        all_results = anuncios + contratos
        
        # Converte o conjunto de termos correspondentes em lista para serialização JSON
        for r in all_results:
            if isinstance(r.get('matched_terms'), set):
                r['matched_terms'] = sorted(list(r['matched_terms']))
        return all_results

    def _normalize_anuncio(self, item: Dict[str, Any], matched_by: str) -> Dict[str, Any]:
        item_id = item.get('id')
        direct_url = f"{BASE_URL}/Base4/pt/detalhe/?type=anuncios&id={item_id}"
        
        return {
            'id': f"base_anuncio_{item_id}",
            'source': "Portal BASE",
            'category': "Anúncio de Concurso",
            'procedure_type': item.get('contractingProcedureType') or "Concurso Público",
            'title': (item.get('contractDesignation') or '').strip(),
            'entity': (item.get('contractingEntity') or '').strip(),
            'value': item.get('basePrice') or "Não especificado",
            'deadline': item.get('proposalDeadline') or "Consulte o anúncio",
            'publication_date': item.get('drPublicationDate') or "N/D",
            'direct_url': direct_url,
            'pieces_url': None,
            'matched_terms': {matched_by}
        }

    def _normalize_contrato(self, item: Dict[str, Any], matched_by: str) -> Dict[str, Any]:
        item_id = item.get('id')
        direct_url = f"{BASE_URL}/Base4/pt/detalhe/?type=contratos&id={item_id}"
        proc_type = item.get('contractingProcedureType') or "Ajuste Direto"
        
        return {
            'id': f"base_contrato_{item_id}",
            'source': "Portal BASE",
            'category': "Contrato / Ajuste Direto",
            'procedure_type': proc_type,
            'title': (item.get('objectBriefDescription') or '').strip(),
            'entity': (item.get('contracting') or '').strip(),
            'contracted': (item.get('contracted') or '').strip(),
            'value': item.get('initialContractualPrice') or "Não especificado",
            'deadline': f"Celebrado em {item.get('signingDate', 'N/D')}",
            'publication_date': item.get('publicationDate') or "N/D",
            'direct_url': direct_url,
            'pieces_url': None,
            'matched_terms': {matched_by}
        }


if __name__ == "__main__":
    scraper = BaseScraper()
    print("A pesquisar anúncios no BASE...")
    res = scraper.search_anuncios(max_per_term=5)
    print(f"Encontrados {len(res)} anúncios.")
    if res:
        print("Exemplo:", json.dumps(res[0], indent=2, ensure_ascii=False, default=list))
