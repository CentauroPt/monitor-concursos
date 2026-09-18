"""
Módulo de análise, síntese, agregação e cache de concursos públicos
recolhidos a partir do Portal BASE e do TED Europa.
Suporta persistência de concursos descartados e exportação seletiva.
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Set

from scraper_base import BaseScraper
from scraper_ted import TedScraper

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data")
CACHE_FILE = os.path.join(CACHE_DIR, "cache.json")
DISMISSED_FILE = os.path.join(CACHE_DIR, "dismissed.json")
FAVORITES_FILE = os.path.join(CACHE_DIR, "favorites.json")


class ProcurementAnalyzer:
    def __init__(self):
        self.base_scraper = BaseScraper()
        self.ted_scraper = TedScraper()
        os.makedirs(CACHE_DIR, exist_ok=True)

    def get_favorite_ids(self) -> Set[str]:
        """Devolve o conjunto de IDs de concursos marcados como favoritos."""
        if os.path.exists(FAVORITES_FILE):
            try:
                with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(data)
                    elif isinstance(data, dict):
                        return set(data.keys())
            except Exception as e:
                logger.error(f"Erro ao ler favoritos: {e}")
        return set()

    def toggle_favorite(self, item_id: str) -> bool:
        """Alterna o estado de favorito de um concurso (Adicionar / Remover)."""
        favorites = self.get_favorite_ids()
        if item_id in favorites:
            favorites.remove(item_id)
            is_fav = False
        else:
            favorites.add(item_id)
            is_fav = True
        try:
            with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
                json.dump(list(favorites), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao gravar favoritos: {e}")
        return is_fav

    def get_dismissed_ids(self) -> Set[str]:
        """Devolve o conjunto de IDs de concursos descartados pelo utilizador."""
        if os.path.exists(DISMISSED_FILE):
            try:
                with open(DISMISSED_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(data)
                    elif isinstance(data, dict):
                        return set(data.keys())
            except Exception as e:
                logger.error(f"Erro ao ler descartados: {e}")
        return set()

    def dismiss_item(self, item_id: str) -> bool:
        """Marca permanentemente um concurso como descartado."""
        dismissed = self.get_dismissed_ids()
        dismissed.add(item_id)
        try:
            with open(DISMISSED_FILE, 'w', encoding='utf-8') as f:
                json.dump(list(dismissed), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Erro ao gravar descartado {item_id}: {e}")
            return False

    def restore_item(self, item_id: str) -> bool:
        """Restaura um concurso previamente descartado."""
        dismissed = self.get_dismissed_ids()
        if item_id in dismissed:
            dismissed.remove(item_id)
            try:
                with open(DISMISSED_FILE, 'w', encoding='utf-8') as f:
                    json.dump(list(dismissed), f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                logger.error(f"Erro ao restaurar {item_id}: {e}")
        return False

    def run_full_search(self, ted_country: str = "PRT", max_base_items: int = 30) -> Dict[str, Any]:
        """
        Executa pesquisa completa em ambas as fontes, processa os dados,
        gera resumos individuais e atualiza a cache local.
        """
        start_time = datetime.now()
        logger.info("A iniciar pesquisa agregada (BASE + TED)...")

        # 1. Obter dados do Portal BASE
        base_items = []
        try:
            base_items = self.base_scraper.search_all(max_per_term=max_base_items)
        except Exception as e:
            logger.error(f"Erro ao obter dados do Portal BASE: {e}")

        # 2. Obter dados do TED
        ted_items = []
        try:
            ted_items = self.ted_scraper.search(country=ted_country, limit=50)
        except Exception as e:
            logger.error(f"Erro ao obter dados do TED: {e}")

        # 3. Unificar e gerar resumos individuais
        all_items = base_items + ted_items

        for item in all_items:
            item['summary'] = self._generate_summary(item)

        # Ordenar por data de publicação (mais recentes primeiro)
        all_items.sort(key=lambda x: self._parse_date_sort(x.get('publication_date')), reverse=True)

        dismissed_ids = self.get_dismissed_ids()
        for item in all_items:
            item['is_dismissed'] = item.get('id') in dismissed_ids

        result = {
            'timestamp': datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            'total_raw_count': len(all_items),
            'ted_country': ted_country,
            'items': all_items,
            'duration_seconds': round((datetime.now() - start_time).total_seconds(), 2)
        }

        # Guardar na cache
        self.save_cache(result)
        return self._format_results_payload(result)

    def _format_results_payload(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Separa os itens em 3 listas distintas: Ativos (Geral), Favoritos e Descartados."""
        dismissed_ids = self.get_dismissed_ids()
        favorite_ids = self.get_favorite_ids()
        all_items = raw_data.get('items', [])

        active_items = []
        favorite_items = []
        dismissed_items = []

        base_active = 0
        ted_active = 0

        for it in all_items:
            it_id = it.get('id')
            it['is_favorite'] = it_id in favorite_ids
            if it_id in dismissed_ids:
                it['is_dismissed'] = True
                dismissed_items.append(it)
            elif it_id in favorite_ids:
                it['is_dismissed'] = False
                favorite_items.append(it)
            else:
                it['is_dismissed'] = False
                active_items.append(it)
                if it.get('source') == 'Portal BASE':
                    base_active += 1
                else:
                    ted_active += 1

        return {
            'timestamp': raw_data.get('timestamp'),
            'total_count': len(active_items),
            'base_count': base_active,
            'ted_count': ted_active,
            'favorite_count': len(favorite_items),
            'dismissed_count': len(dismissed_items),
            'ted_country': raw_data.get('ted_country', 'PRT'),
            'items': active_items,
            'favorite_items': favorite_items,
            'dismissed_items': dismissed_items,
            'duration_seconds': raw_data.get('duration_seconds', 0)
        }

    def _generate_summary(self, item: Dict[str, Any]) -> str:
        """Gera um resumo claro e estruturado dos 3 pilares requeridos."""
        title = item.get('title', 'Não especificado')
        deadline = item.get('deadline', 'Consulte o anúncio')
        value = item.get('value', 'Não especificado')
        entity = item.get('entity', 'Entidade Pública')

        return (
            f"• Objeto do Concurso: {title}\n"
            f"• Prazo de Entrega da Proposta: {deadline}\n"
            f"• Valor a Concurso: {value}\n"
            f"• Entidade Adjudicante: {entity}"
        )

    def _parse_date_sort(self, date_str: Optional[str]) -> str:
        """Normaliza DD-MM-YYYY para YYYY-MM-DD para ordenação correta."""
        if not date_str or date_str == "N/D":
            return "0000-00-00"
        parts = date_str.split(' ')[0].split('-')
        if len(parts) == 3:
            if len(parts[0]) == 4:
                return date_str
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return date_str

    def get_cached_results(self) -> Optional[Dict[str, Any]]:
        """Devolve os resultados em cache filtrando descartados."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    return self._format_results_payload(raw_data)
            except Exception as e:
                logger.error(f"Erro ao ler ficheiro de cache: {e}")
        return None

    def save_cache(self, data: Dict[str, Any]):
        """Grava os resultados brutos em cache JSON."""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao gravar cache: {e}")

    def export_csv(self, selected_ids: Optional[List[str]] = None) -> str:
        """
        Exporta resultados para CSV legível no Excel (UTF-8 com BOM).
        Se selected_ids for fornecido, exporta APENAS esses concursos.
        Caso contrário, exporta todos os concursos ativos (não descartados).
        """
        cached = self.get_cached_results()
        if not cached:
            return ""

        # Obter todos os itens (ativos, favoritos ou descartados)
        candidate_items = cached.get('items', []) + cached.get('favorite_items', []) + cached.get('dismissed_items', [])

        if selected_ids and len(selected_ids) > 0:
            ids_set = set(selected_ids)
            export_list = [it for it in candidate_items if it.get('id') in ids_set]
        else:
            # Por defeito: apenas os ativos
            export_list = cached.get('items', [])

        if not export_list:
            return ""

        headers = ["Fonte", "Categoria", "Tipo de Procedimento", "Objeto do Concurso", "Prazo de Entrega", "Valor a Concurso", "Entidade", "Data de Publicação", "Link Direto"]
        
        lines = [";".join([f'"{h}"' for h in headers])]
        for it in export_list:
            row = [
                it.get('source', ''),
                it.get('category', ''),
                it.get('procedure_type', ''),
                it.get('title', '').replace('"', '""'),
                it.get('deadline', ''),
                it.get('value', ''),
                it.get('entity', '').replace('"', '""'),
                it.get('publication_date', ''),
                it.get('direct_url', '')
            ]
            lines.append(";".join([f'"{c}"' for c in row]))

        return "\ufeff" + "\n".join(lines)


if __name__ == "__main__":
    analyzer = ProcurementAnalyzer()
    cached = analyzer.get_cached_results()
    if cached:
        print(f"Ativos: {cached['total_count']}, Descartados: {cached['dismissed_count']}")
