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
EVALUATION_FILE = os.path.join(CACHE_DIR, "evaluation.json")


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

    def _save_favorite_ids(self, favorites: Set[str]):
        """Grava os IDs favoritos em JSON."""
        try:
            with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
                json.dump(sorted(list(favorites)), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao gravar favoritos: {e}")

    def get_evaluation_ids(self) -> Set[str]:
        """Devolve o conjunto de IDs de concursos marcados para avaliação."""
        if os.path.exists(EVALUATION_FILE):
            try:
                with open(EVALUATION_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(data)
                    elif isinstance(data, dict):
                        return set(data.keys())
            except Exception as e:
                logger.error(f"Erro ao ler itens em avaliação: {e}")
        return set()

    def _save_evaluation_ids(self, evaluations: Set[str]):
        """Grava os IDs em avaliação em JSON."""
        try:
            with open(EVALUATION_FILE, 'w', encoding='utf-8') as f:
                json.dump(sorted(list(evaluations)), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao gravar avaliação: {e}")

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

    def _save_dismissed_ids(self, dismissed: Set[str]):
        """Grava os IDs descartados em JSON."""
        try:
            with open(DISMISSED_FILE, 'w', encoding='utf-8') as f:
                json.dump(sorted(list(dismissed)), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao gravar descartados: {e}")

    def sync_classifications(self, favorites: Optional[List[str]] = None, evaluations: Optional[List[str]] = None, dismissed: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Sincroniza e funde classificações existentes no servidor com eventuais classificações
        enviadas pelo cliente (garantindo persistência absoluta mesmo após reinício de contentor).
        Assegura exclusividade mútua entre categorias.
        """
        current_favs = self.get_favorite_ids()
        current_evals = self.get_evaluation_ids()
        current_disms = self.get_dismissed_ids()

        if favorites:
            current_favs.update(favorites)
        if evaluations:
            current_evals.update(evaluations)
        if dismissed:
            current_disms.update(dismissed)

        # Regras de precedência e exclusividade:
        # Se um ID foi explicitamente descartado, não deve ser favorito nem avaliação
        if dismissed:
            current_favs.difference_update(dismissed)
            current_evals.difference_update(dismissed)
        # Se um ID é favorito, não deve ser avaliação nem descartado
        if favorites:
            current_evals.difference_update(favorites)
            current_disms.difference_update(favorites)
        # Se um ID é avaliação, não deve ser favorito nem descartado
        if evaluations:
            current_favs.difference_update(evaluations)
            current_disms.difference_update(evaluations)

        self._save_favorite_ids(current_favs)
        self._save_evaluation_ids(current_evals)
        self._save_dismissed_ids(current_disms)

        logger.info(f"Classificações sincronizadas no servidor: {len(current_favs)} favoritos, {len(current_evals)} avaliação, {len(current_disms)} descartados.")
        return {
            'favorites': len(current_favs),
            'evaluations': len(current_evals),
            'dismissed': len(current_disms)
        }

    def toggle_favorite(self, item_id: str) -> bool:
        """Alterna o estado de favorito de um concurso (Adicionar / Remover)."""
        favorites = self.get_favorite_ids()
        evaluations = self.get_evaluation_ids()
        dismissed = self.get_dismissed_ids()

        if item_id in favorites:
            favorites.remove(item_id)
            is_fav = False
        else:
            favorites.add(item_id)
            is_fav = True
            # Exclusividade: remove de avaliação e de descartados
            evaluations.discard(item_id)
            dismissed.discard(item_id)
            self._save_evaluation_ids(evaluations)
            self._save_dismissed_ids(dismissed)

        self._save_favorite_ids(favorites)
        return is_fav

    def toggle_evaluation(self, item_id: str) -> bool:
        """Alterna o estado de 'Para avaliação' de um concurso."""
        evaluations = self.get_evaluation_ids()
        favorites = self.get_favorite_ids()
        dismissed = self.get_dismissed_ids()

        if item_id in evaluations:
            evaluations.remove(item_id)
            is_eval = False
        else:
            evaluations.add(item_id)
            is_eval = True
            # Exclusividade: remove de favoritos e de descartados
            favorites.discard(item_id)
            dismissed.discard(item_id)
            self._save_favorite_ids(favorites)
            self._save_dismissed_ids(dismissed)

        self._save_evaluation_ids(evaluations)
        return is_eval

    def dismiss_item(self, item_id: str) -> bool:
        """Marca permanentemente um concurso como descartado."""
        dismissed = self.get_dismissed_ids()
        favorites = self.get_favorite_ids()
        evaluations = self.get_evaluation_ids()

        dismissed.add(item_id)
        # Exclusividade: remove de favoritos e de avaliação
        favorites.discard(item_id)
        evaluations.discard(item_id)

        self._save_dismissed_ids(dismissed)
        self._save_favorite_ids(favorites)
        self._save_evaluation_ids(evaluations)
        return True

    def restore_item(self, item_id: str) -> bool:
        """Restaura um concurso previamente descartado."""
        dismissed = self.get_dismissed_ids()
        if item_id in dismissed:
            dismissed.remove(item_id)
            self._save_dismissed_ids(dismissed)
            return True
        return False

    def run_full_search(self, ted_country: str = "PRT", max_base_items: int = 30, client_timestamp: Optional[str] = None, client_classifications: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
        """
        Executa pesquisa completa em ambas as fontes, processa os dados,
        acumula concursos existentes, reconhece e preserva classificações
        e atualiza a cache do servidor.
        """
        start_time = datetime.now()
        logger.info("A iniciar pesquisa agregada (BASE + TED)...")

        # Se o cliente enviou classificações locais, consolida imediatamente no servidor
        if client_classifications and isinstance(client_classifications, dict):
            self.sync_classifications(
                favorites=client_classifications.get('favorites'),
                evaluations=client_classifications.get('evaluations'),
                dismissed=client_classifications.get('dismissed')
            )

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

        # 3. Unificar dados novos e gerar resumos
        fresh_items = base_items + ted_items
        for item in fresh_items:
            item['summary'] = self._generate_summary(item)

        # 4. ACUMULAÇÃO E RECONHECIMENTO DE CONCURSOS EXISTENTES:
        # Recupera todos os concursos armazenados na cache anterior para NUNCA perder nada
        existing_raw = self.get_raw_cache()
        existing_items = existing_raw.get('items', []) if existing_raw else []

        # Dicionário de todos os itens indexados por ID
        items_map: Dict[str, Dict[str, Any]] = {}
        for old_it in existing_items:
            old_id = old_it.get('id')
            if old_id:
                items_map[old_id] = old_it

        # Incorporar novos resultados raspados:
        # Se o concurso já existir no sistema, atualiza campos frescos mantendo a sua identidade
        for fresh_it in fresh_items:
            fresh_id = fresh_it.get('id')
            if not fresh_id:
                continue
            if fresh_id in items_map:
                # Concurso já existe: atualiza campos não vazios sem perturbar
                for k, v in fresh_it.items():
                    if v not in (None, '', 'N/D'):
                        items_map[fresh_id][k] = v
            else:
                # Novo concurso descoberto
                items_map[fresh_id] = fresh_it

        all_items = list(items_map.values())

        # Ordenar por data de publicação (mais recentes primeiro)
        all_items.sort(key=lambda x: self._parse_date_sort(x.get('publication_date')), reverse=True)

        search_timestamp = client_timestamp if client_timestamp else datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        result = {
            'timestamp': search_timestamp,
            'total_raw_count': len(all_items),
            'ted_country': ted_country,
            'items': all_items,
            'duration_seconds': round((datetime.now() - start_time).total_seconds(), 2)
        }

        # Guardar permanentemente na cache do servidor
        self.save_cache(result)
        return self._format_results_payload(result)

    def _format_results_payload(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Separa rigorosamente os itens segundo as suas classificações:
        - Ativos (separador 'Todos'): APENAS os concursos NÃO classificados, prontos para triagem
        - Favoritos: concursos marcados como favoritos
        - Para avaliação: concursos em avaliação
        - Descartados: concursos descartados
        """
        dismissed_ids = self.get_dismissed_ids()
        favorite_ids = self.get_favorite_ids()
        evaluation_ids = self.get_evaluation_ids()
        all_items = raw_data.get('items', [])

        active_items = []
        favorite_items = []
        evaluation_items = []
        dismissed_items = []

        base_active = 0
        ted_active = 0

        for it in all_items:
            it_id = it.get('id')
            if it_id in dismissed_ids:
                it['is_dismissed'] = True
                it['is_favorite'] = False
                it['is_evaluation'] = False
                dismissed_items.append(it)
            elif it_id in favorite_ids:
                it['is_dismissed'] = False
                it['is_favorite'] = True
                it['is_evaluation'] = False
                favorite_items.append(it)
            elif it_id in evaluation_ids:
                it['is_dismissed'] = False
                it['is_favorite'] = False
                it['is_evaluation'] = True
                evaluation_items.append(it)
            else:
                # Concurso não classificado -> Aparece no separador "Todos" para ser classificado
                it['is_dismissed'] = False
                it['is_favorite'] = False
                it['is_evaluation'] = False
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
            'evaluation_count': len(evaluation_items),
            'dismissed_count': len(dismissed_items),
            'ted_country': raw_data.get('ted_country', 'PRT'),
            'items': active_items,
            'favorite_items': favorite_items,
            'evaluation_items': evaluation_items,
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

    def get_raw_cache(self) -> Optional[Dict[str, Any]]:
        """Devolve os dados brutos armazenados na cache."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erro ao ler cache bruta: {e}")
        return None

    def get_cached_results(self) -> Optional[Dict[str, Any]]:
        """Devolve os resultados em cache estruturados por categorias."""
        raw_data = self.get_raw_cache()
        if raw_data:
            return self._format_results_payload(raw_data)
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

        # Obter todos os itens (ativos, favoritos, avaliação ou descartados)
        candidate_items = cached.get('items', []) + cached.get('favorite_items', []) + cached.get('evaluation_items', []) + cached.get('dismissed_items', [])

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
