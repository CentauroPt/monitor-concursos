"""
Módulo de pesquisa e extração de dados do TED (Tenders Electronic Daily - ted.europa.eu).
Utiliza a API oficial v3 aberta para pesquisar anúncios de concursos europeus
por palavras-chave e códigos CPV 3414*.
"""

import json
import logging
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

TED_API_URL = "https://api.ted.europa.eu/v3/notices/search"
TED_BASE_WEB = "https://ted.europa.eu"

KEYWORDS = [
    "unidade móvel",
    "unidades móveis",
    "viatura especial",
    "viaturas especiais",
    "carrinha",
    "biblioteca itinerante"
]

CPV_PREFIX = "3414"

DEFAULT_HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) MonitorConcursos/1.0'
}


class TedScraper:
    def __init__(self, timeout: int = 20):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout

    def search(self, country: str = "PRT", limit: int = 50, page: int = 1) -> List[Dict[str, Any]]:
        """
        Pesquisa concursos no TED Europa.
        :param country: Código ISO de 3 letras (ex: 'PRT' para Portugal, ou None/'' para toda a UE)
        :param limit: Número de resultados a devolver (máx 100)
        :param page: Página de resultados
        """
        # Constrói a query pericial (Expert Search)
        kw_quoted = [f'"{kw}"' for kw in KEYWORDS]
        kw_expression = " OR ".join(kw_quoted)
        
        filter_parts = [
            f"(classification-cpv = {CPV_PREFIX}* OR FT ~ ({kw_expression}))"
        ]
        
        if country and country.upper() != "ALL":
            filter_parts.append(f"buyer-country = {country.upper()}")

        query_str = " AND ".join(filter_parts) + " SORT BY publication-date DESC"

        payload = {
            'query': query_str,
            'fields': [
                'publication-number',
                'notice-title',
                'buyer-name',
                'deadline-receipt-request',
                'deadline-receipt-tender-date-lot',
                'estimated-value-proc',
                'estimated-value-lot',
                'publication-date'
            ],
            'page': page,
            'limit': limit
        }

        try:
            resp = self.session.post(TED_API_URL, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                raw_notices = data.get('notices', []) or []
                return [self._normalize_notice(n) for n in raw_notices]
            else:
                logger.error(f"Erro na API do TED (Status {resp.status_code}): {resp.text[:300]}")
        except Exception as e:
            logger.error(f"Exceção ao comunicar com a API do TED: {e}")

        return []

    def _format_price(self, val_proc: Any, val_lots: Any) -> str:
        """Formata valor numérico em moeda Euro legível."""
        val = val_proc
        if not val and val_lots:
            if isinstance(val_lots, list) and len(val_lots) > 0:
                try:
                    val = sum(float(str(v).replace(',', '.')) for v in val_lots if v)
                except Exception:
                    val = val_lots[0]

        if not val:
            return "Consulte o caderno de encargos"

        try:
            num = float(str(val).replace(',', '.'))
            # Formatação portuguesa: 1.234.567,89 €
            formatted = f"{num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            return f"{formatted} €"
        except Exception:
            return f"{val} €"

    def _format_date(self, raw_date: Optional[str]) -> str:
        """Converte ISO timestamp (ex: 2026-10-15T17:00:59Z) em formato legível DD-MM-YYYY HH:MM."""
        if not raw_date:
            return "Consulte o anúncio"
        try:
            cleaned = raw_date.replace('Z', '+00:00')
            dt = datetime.fromisoformat(cleaned)
            return dt.strftime("%d-%m-%Y %H:%M")
        except Exception:
            # Tentar apenas os primeiros 10 caracteres YYYY-MM-DD
            if len(raw_date) >= 10:
                parts = raw_date[:10].split('-')
                if len(parts) == 3:
                    return f"{parts[2]}-{parts[1]}-{parts[0]}"
            return raw_date

    def _normalize_notice(self, item: Dict[str, Any]) -> Dict[str, Any]:
        pub_number = item.get('publication-number', '')
        
        # Objeto / Título: prioridade a português 'por', depois 'eng', depois qualquer
        title_dict = item.get('notice-title') or {}
        title = title_dict.get('por') or title_dict.get('eng')
        if not title and title_dict:
            title = next(iter(title_dict.values()))
        if not title:
            title = f"Concurso TED nº {pub_number}"

        # Entidade Adjudicante
        buyer_dict = item.get('buyer-name') or {}
        buyer = ""
        if isinstance(buyer_dict, dict):
            buyer_list = buyer_dict.get('por') or buyer_dict.get('eng')
            if not buyer_list and buyer_dict:
                buyer_list = next(iter(buyer_dict.values()))
            if isinstance(buyer_list, list) and len(buyer_list) > 0:
                buyer = buyer_list[0]
            elif isinstance(buyer_list, str):
                buyer = buyer_list
        elif isinstance(buyer_dict, list) and len(buyer_dict) > 0:
            buyer = buyer_dict[0]

        # Prazo de entrega
        deadline_raw = None
        deadlines = item.get('deadline-receipt-request') or item.get('deadline-receipt-tender-date-lot')
        if isinstance(deadlines, list) and len(deadlines) > 0:
            deadline_raw = deadlines[0]
        elif isinstance(deadlines, str):
            deadline_raw = deadlines

        formatted_deadline = self._format_date(deadline_raw)

        # Valor estimado
        val_proc = item.get('estimated-value-proc')
        val_lot = item.get('estimated-value-lot')
        formatted_value = self._format_price(val_proc, val_lot)

        # Data de publicação
        pub_date_raw = item.get('publication-date')
        if isinstance(pub_date_raw, str) and len(pub_date_raw) >= 10:
            p_parts = pub_date_raw[:10].split('-')
            if len(p_parts) == 3:
                pub_date = f"{p_parts[2]}-{p_parts[1]}-{p_parts[0]}"
            else:
                pub_date = pub_date_raw[:10]
        else:
            pub_date = "N/D"

        direct_url = f"{TED_BASE_WEB}/pt/notice/-/detail/{pub_number}"

        return {
            'id': f"ted_{pub_number}",
            'source': "TED Europa",
            'category': "Concurso Europeu (TED)",
            'procedure_type': "Concurso Público Internacional",
            'title': title.strip(),
            'entity': buyer.strip() if buyer else "Entidade Pública (Consulte o anúncio)",
            'value': formatted_value,
            'deadline': formatted_deadline,
            'publication_date': pub_date,
            'direct_url': direct_url,
            'pieces_url': None,
            'matched_terms': [f"CPV {CPV_PREFIX}xxxx / Palavras-chave"]
        }


if __name__ == "__main__":
    ted = TedScraper()
    print("A pesquisar no TED para Portugal...")
    notices = ted.search(country="PRT", limit=5)
    print(f"Encontrados {len(notices)} concursos no TED.")
    if notices:
        print("Exemplo:", json.dumps(notices[0], indent=2, ensure_ascii=False))
