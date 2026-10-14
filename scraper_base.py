"""
Módulo de pesquisa e extração de dados do Portal BASE (base.gov.pt).
Suporta pesquisa de Anúncios de Procedimento e Contratos (Ajustes Diretos, etc.)
por palavras-chave e códigos CPV (34140000 - 34149999).
"""

import json
import logging
import re
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

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
        self.session.verify = False
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout
        self.version = "87.0"  # Versão de fallback testada com sucesso
        self._detect_version()

    def _detect_version(self):
        """Deteta dinamicamente a versão da API requerida pelo Portal BASE com fallback rápido."""
        try:
            r = self.session.get(f"{BASE_URL}/Base4/pt/pesquisa/?type=anuncios", timeout=2)
            if r.status_code == 200:
                m = re.search(r'version:\s*["\']([^"\']+)["\']', r.text)
                if m and m.group(1) != "0.0":
                    self.version = m.group(1)
        except Exception:
            self.version = "87.0"

    def _post_query(self, search_type: str, query: str, size: int = 30, sort: Optional[str] = None) -> List[Dict[str, Any]]:
        """Executa um POST no endpoint /Base4/pt/resultados/."""
        if sort is None:
            sort = "-drPublicationDate" if search_type == "search_anuncios" else "-publicationDate"
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
                except Exception:
                    data = json.loads(resp.text.strip())
                if isinstance(data, dict):
                    return data.get('items', []) or []
                elif isinstance(data, list):
                    return data
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

        # Ler detalhes dos contratos (e anúncio original se associado) para obter o prazo de entrega de propostas ou prazo de execução
        contract_items = list(results_map.values())
        if contract_items:
            try:
                raw_ids = [str(it.get('id', '')).replace('base_contrato_', '') for it in contract_items]
                with ThreadPoolExecutor(max_workers=6) as pool:
                    deadlines = list(pool.map(self._fetch_contract_deadline, raw_ids))
                for it, dl in zip(contract_items, deadlines):
                    if dl:
                        it['deadline'] = dl
            except Exception as e:
                logger.warning(f"Erro ao obter prazos detalhados dos contratos: {e}")

        return list(results_map.values())

    def _fetch_contract_deadline(self, contract_id: Any) -> str:
        """
        Lê o detalhe do contrato (e anúncio original associado) para obter a data limite
        de entrega das propostas ou prazo de execução / duração estimada.
        Nunca utiliza a data de celebração do contrato como prazo de entrega.
        """
        try:
            resp = self.session.post(RESULTADOS_URL, data={
                'type': 'detail_contratos',
                'version': self.version,
                'id': str(contract_id)
            }, timeout=6)
            if resp.status_code == 200 and resp.text.strip():
                d = json.loads(resp.text.strip())
                aid = d.get('announcementId')
                if aid and int(aid) > 0:
                    try:
                        r2 = self.session.post(RESULTADOS_URL, data={
                            'type': 'detail_anuncios',
                            'version': self.version,
                            'id': str(aid)
                        }, timeout=6)
                        if r2.status_code == 200 and r2.text.strip():
                            d2 = json.loads(r2.text.strip())
                            p_dl = d2.get('proposalDeadline')
                            if p_dl:
                                return p_dl
                    except Exception:
                        pass
                exec_dl = d.get('executionDeadline')
                if exec_dl:
                    return f"{exec_dl} (Prazo de Execução)"
        except Exception:
            pass
        return "Consulte o anúncio"

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
            'deadline': "Consulte o anúncio",
            'publication_date': item.get('publicationDate') or "N/D",
            'direct_url': direct_url,
            'pieces_url': None,
            'matched_terms': {matched_by}
        }

    def search_contracts_by_entity(self, nif: Optional[str] = None, entity_name: Optional[str] = None, max_items: int = 50) -> List[Dict[str, Any]]:
        """
        Pesquisa contratos publicados no Portal BASE para uma entidade pública específica por NIF ou Nome.
        Obtém os detalhes completos de cada contrato para permitir pesquisa por palavras escritas no contrato.
        """
        results_map = {}
        queries = []

        if nif:
            clean_nif = str(nif).strip().replace(" ", "")
            if clean_nif:
                queries.append(f"texto={clean_nif}")

        if entity_name:
            clean_name = str(entity_name).strip()
            if clean_name:
                queries.append(f"adjudicante={clean_name}")
                queries.append(f"texto={clean_name}")

        if not queries:
            return []

        for q in queries:
            try:
                items = self._post_query(
                    search_type="search_contratos",
                    query=q,
                    size=max_items,
                    sort="-publicationDate"
                )
                for it in items:
                    cid = it.get('id')
                    if cid and f"base_contrato_{cid}" not in results_map:
                        results_map[f"base_contrato_{cid}"] = it
            except Exception as e:
                logger.error(f"Erro ao pesquisar contratos por entidade ({q}): {e}")

        contract_items = list(results_map.values())[:max_items]

        # Enriquecer concorrentemente com detail_contratos para texto completo
        enriched_list = []
        if contract_items:
            def fetch_full_detail(item):
                cid = item.get('id')
                detail = {}
                try:
                    resp = self.session.post(RESULTADOS_URL, data={
                        'type': 'detail_contratos',
                        'version': self.version,
                        'id': str(cid)
                    }, timeout=6)
                    if resp.status_code == 200 and resp.text.strip():
                        detail = json.loads(resp.text.strip())
                except Exception:
                    pass
                return self._normalize_entity_contract(item, detail)

            with ThreadPoolExecutor(max_workers=8) as pool:
                enriched_list = list(pool.map(fetch_full_detail, contract_items))

        return enriched_list

    def _normalize_entity_contract(self, item: Dict[str, Any], detail: Dict[str, Any]) -> Dict[str, Any]:
        item_id = item.get('id')
        direct_url = f"{BASE_URL}/Base4/pt/detalhe/?type=contratos&id={item_id}"

        contracting_list = detail.get('contracting') or []
        contracting_name = (item.get('contracting') or '').strip()
        contracting_nif = ''
        if contracting_list and isinstance(contracting_list, list):
            first_c = contracting_list[0]
            if isinstance(first_c, dict):
                contracting_name = (first_c.get('description') or contracting_name).strip()
                contracting_nif = str(first_c.get('nif') or '').strip()

        contracted_list = detail.get('contracted') or []
        contracted_name = (item.get('contracted') or '').strip()
        contracted_nif = ''
        if contracted_list and isinstance(contracted_list, list):
            first_ct = contracted_list[0]
            if isinstance(first_ct, dict):
                contracted_name = (first_ct.get('description') or contracted_name).strip()
                contracted_nif = str(first_ct.get('nif') or '').strip()

        title = (item.get('objectBriefDescription') or detail.get('objectBriefDescription') or '').strip()
        detail_desc = (detail.get('description') or '').strip()
        fundamentation = (detail.get('contractFundamentationType') or detail.get('nonWrittenContractJustificationTypes') or '').strip()
        execution_place = (detail.get('executionPlace') or '').strip()
        execution_deadline = (detail.get('executionDeadline') or '').strip()
        cpvs_designation = (detail.get('cpvsDesignation') or '').strip()
        observations = (detail.get('observations') or '').strip()
        procedure_type = item.get('contractingProcedureType') or detail.get('contractingProcedureType') or 'Ajuste Direto'
        value = item.get('initialContractualPrice') or detail.get('initialContractualPrice') or 'Não especificado'
        signing_date = item.get('signingDate') or detail.get('signingDate') or 'N/D'
        publication_date = item.get('publicationDate') or detail.get('publicationDate') or 'N/D'

        sections = {
            'Objeto do Contrato': title,
            'Descrição Detalhada': detail_desc,
            'Fundamentação Legal': fundamentation,
            'Local de Execução': execution_place,
            'Designação CPV': cpvs_designation,
            'Adjudicatário': contracted_name,
            'Entidade Adjudicante': contracting_name,
            'Observações': observations
        }

        return {
            'id': f"base_contrato_{item_id}",
            'raw_id': str(item_id),
            'source': "Portal BASE",
            'procedure_type': procedure_type,
            'title': title,
            'description': detail_desc or title,
            'fundamentation': fundamentation,
            'entity': contracting_name,
            'entity_nif': contracting_nif,
            'contracted': contracted_name,
            'contracted_nif': contracted_nif,
            'value': value,
            'signing_date': signing_date,
            'publication_date': publication_date,
            'execution_place': execution_place,
            'execution_deadline': execution_deadline,
            'cpvs_designation': cpvs_designation,
            'direct_url': direct_url,
            'sections': {k: v for k, v in sections.items() if v}
        }


if __name__ == "__main__":
    scraper = BaseScraper()
    print("A pesquisar anúncios no BASE...")
    res = scraper.search_anuncios(max_per_term=5)
    print(f"Encontrados {len(res)} anúncios.")
    if res:
        print("Exemplo:", json.dumps(res[0], indent=2, ensure_ascii=False, default=list))
