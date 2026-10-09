"""
Módulo de análise, síntese, agregação e cache de concursos públicos
recolhidos a partir do Portal BASE e do TED Europa.
Suporta persistência central no servidor de pastas e favoritos,
garantindo compatibilidade multi-computador e preservação absoluta de classificações.
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
ASSIGNMENTS_FILE = os.path.join(CACHE_DIR, "assignments.json")

# Ficheiros legados para retrocompatibilidade
DISMISSED_FILE = os.path.join(CACHE_DIR, "dismissed.json")
FAVORITES_FILE = os.path.join(CACHE_DIR, "favorites.json")
EVALUATION_FILE = os.path.join(CACHE_DIR, "evaluation.json")


class ProcurementAnalyzer:
    def __init__(self):
        self.base_scraper = BaseScraper()
        self.ted_scraper = TedScraper()
        os.makedirs(CACHE_DIR, exist_ok=True)
        self._ensure_assignments_initialized()

    def _ensure_assignments_initialized(self):
        """Inicializa e migra dados existentes para a estrutura central de assignments."""
        if not os.path.exists(ASSIGNMENTS_FILE):
            data = {
                "last_search": "",
                "assignments": {}
            }
            # Migrar data de pesquisa anterior do cache.json se existir
            if os.path.exists(CACHE_FILE):
                try:
                    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                        c = json.load(f)
                        data["last_search"] = c.get("timestamp", "")
                except Exception as e:
                    logger.error(f"Erro ao ler timestamp de cache.json: {e}")

            # Migrar descartados existentes
            if os.path.exists(DISMISSED_FILE):
                try:
                    with open(DISMISSED_FILE, 'r', encoding='utf-8') as f:
                        disms = json.load(f)
                        if isinstance(disms, list):
                            for did in disms:
                                data["assignments"][str(did)] = {"folder": "dismissed", "is_favorite": False}
                        elif isinstance(disms, dict):
                            for did in disms.keys():
                                data["assignments"][str(did)] = {"folder": "dismissed", "is_favorite": False}
                except Exception as e:
                    logger.error(f"Erro ao migrar descartados: {e}")

            # Migrar avaliações existentes
            if os.path.exists(EVALUATION_FILE):
                try:
                    with open(EVALUATION_FILE, 'r', encoding='utf-8') as f:
                        evals = json.load(f)
                        if isinstance(evals, list):
                            for eid in evals:
                                if str(eid) not in data["assignments"]:
                                    data["assignments"][str(eid)] = {"folder": "evaluation", "is_favorite": False}
                                else:
                                    data["assignments"][str(eid)]["folder"] = "evaluation"
                except Exception as e:
                    logger.error(f"Erro ao migrar avaliações: {e}")

            # Migrar favoritos existentes
            if os.path.exists(FAVORITES_FILE):
                try:
                    with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                        favs = json.load(f)
                        if isinstance(favs, list):
                            for fid in favs:
                                fid_str = str(fid)
                                if fid_str not in data["assignments"]:
                                    data["assignments"][fid_str] = {"folder": "favorites", "is_favorite": True}
                                else:
                                    data["assignments"][fid_str]["is_favorite"] = True
                except Exception as e:
                    logger.error(f"Erro ao migrar favoritos: {e}")

            self._save_assignments_file(data)
            logger.info(f"Assignments inicializados e migrados com {len(data['assignments'])} registos.")

    def get_assignments_data(self) -> Dict[str, Any]:
        """Devolve o dicionário completo de assignments do servidor."""
        if os.path.exists(ASSIGNMENTS_FILE):
            try:
                with open(ASSIGNMENTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erro ao ler assignments: {e}")
        return {"last_search": "", "assignments": {}}

    def _save_assignments_file(self, data: Dict[str, Any]):
        """Grava assignments e espelha em ficheiros legados para retrocompatibilidade."""
        try:
            with open(ASSIGNMENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Sincronizar ficheiros legados
            fav_list = []
            eval_list = []
            dism_list = []
            for item_id, asg in data.get("assignments", {}).items():
                if asg.get("is_favorite"):
                    fav_list.append(item_id)
                folder = asg.get("folder")
                if folder == "evaluation":
                    eval_list.append(item_id)
                elif folder == "dismissed":
                    dism_list.append(item_id)

            with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
                json.dump(sorted(fav_list), f, ensure_ascii=False, indent=2)
            with open(EVALUATION_FILE, 'w', encoding='utf-8') as f:
                json.dump(sorted(eval_list), f, ensure_ascii=False, indent=2)
            with open(DISMISSED_FILE, 'w', encoding='utf-8') as f:
                json.dump(sorted(dism_list), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao gravar assignments: {e}")

    def get_item_assignment(self, item_id: str) -> Dict[str, Any]:
        """Obtém a pasta e o estado de favorito de um concurso específico."""
        data = self.get_assignments_data()
        return data.get("assignments", {}).get(str(item_id), {"folder": "inbox", "is_favorite": False})

    def set_item_folder(self, item_id: str, target_folder: str) -> Dict[str, Any]:
        """
        Move o concurso para a pasta pretendida ('inbox', 'evaluation', 'dismissed', 'favorites').
        REGRA: Mudar de pasta NUNCA retira a marca de favorito (a menos que a pasta seja 'inbox' e não seja favorito).
        """
        data = self.get_assignments_data()
        assignments = data.setdefault("assignments", {})
        item_id_str = str(item_id)
        current = assignments.get(item_id_str, {"folder": "inbox", "is_favorite": False})

        is_fav = current.get("is_favorite", False)

        if target_folder == "favorites":
            # Ao mover expressamente para favoritos, ativa a estrela
            is_fav = True
            # Se já estava em avaliação, mantém a pasta evaluation mas com is_favorite = True
            if current.get("folder") == "evaluation":
                new_folder = "evaluation"
            else:
                new_folder = "favorites"
        elif target_folder in ("evaluation", "dismissed", "inbox"):
            new_folder = target_folder
            # O estado is_fav mantém-se exatamente como está!
        else:
            new_folder = current.get("folder", "inbox")

        assignments[item_id_str] = {
            "folder": new_folder,
            "is_favorite": is_fav
        }
        self._save_assignments_file(data)
        logger.info(f"Concurso {item_id} atualizado: pasta={new_folder}, favorito={is_fav}")
        return {"id": item_id, "folder": new_folder, "is_favorite": is_fav}

    def toggle_favorite(self, item_id: str) -> Dict[str, Any]:
        """
        Alterna a marca de favorito (☆ <-> ★) de um concurso.
        REGRAS:
        1. Se estava em 'inbox' (Todos) e ganha estrela -> Move-se para a pasta 'favorites' (sai de Todos).
        2. Se estava em 'evaluation' e ganha/perde estrela -> Mantém-se na pasta 'evaluation'! Apenas o símbolo muda.
        3. Se estava em 'dismissed' e ganha/perde estrela -> Mantém-se na pasta 'dismissed'! Apenas o símbolo muda.
        4. Se estava na pasta 'favorites' e perde a estrela -> Como já não é favorito e não estava em avaliação, volta para 'inbox' (Todos).
        """
        data = self.get_assignments_data()
        assignments = data.setdefault("assignments", {})
        item_id_str = str(item_id)
        current = assignments.get(item_id_str, {"folder": "inbox", "is_favorite": False})

        cur_fav = current.get("is_favorite", False)
        cur_folder = current.get("folder", "inbox")

        new_fav = not cur_fav

        if new_fav:
            # Ganhou a marca de favorito
            if cur_folder == "inbox":
                # Sai de Todos e vai para favoritos
                new_folder = "favorites"
            else:
                # Mantém a pasta onde estava (ex: evaluation ou dismissed)
                new_folder = cur_folder
        else:
            # Perdeu a marca de favorito por clique direto na estrela
            if cur_folder == "favorites":
                # Como a pasta era apenas 'favorites', retorna à caixa de entrada 'inbox'
                new_folder = "inbox"
            else:
                # Permanece na sua pasta (evaluation, dismissed, etc.)
                new_folder = cur_folder

        assignments[item_id_str] = {
            "folder": new_folder,
            "is_favorite": new_fav
        }
        self._save_assignments_file(data)
        logger.info(f"Concurso {item_id} alternou favorito: is_favorite={new_fav}, pasta={new_folder}")
        return {"id": item_id, "is_favorite": new_fav, "folder": new_folder}

    def toggle_evaluation(self, item_id: str) -> Dict[str, Any]:
        """
        Move o concurso para a pasta 'Para avaliação' ou retira-o de lá se já estiver.
        REGRA: A marca de favoritos NUNCA é removida!
        """
        current = self.get_item_assignment(item_id)
        cur_folder = current.get("folder", "inbox")
        is_fav = current.get("is_favorite", False)

        if cur_folder == "evaluation":
            # Já está em avaliação -> Retirar de avaliação
            # Se for favorito, passa para a pasta 'favorites'; senão, volta para 'inbox' (Todos)
            target = "favorites" if is_fav else "inbox"
        else:
            # Não está em avaliação -> Colocar na pasta 'evaluation'
            target = "evaluation"

        return self.set_item_folder(item_id, target)

    def dismiss_item(self, item_id: str) -> bool:
        """Marca um concurso como descartado."""
        self.set_item_folder(item_id, "dismissed")
        return True

    def restore_item(self, item_id: str) -> bool:
        """Restaura um concurso descartado para a sua pasta de trabalho (favorites se for favorito, senão inbox)."""
        current = self.get_item_assignment(item_id)
        is_fav = current.get("is_favorite", False)
        target = "favorites" if is_fav else "inbox"
        self.set_item_folder(item_id, target)
        return True

    def run_full_search(self, ted_country: str = "PRT", max_base_items: int = 30, client_timestamp: Optional[str] = None, client_classifications: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executa pesquisa completa em ambas as fontes, processa os dados,
        acumula concursos existentes, preserva rigorosamente as pastas e favoritos
        onde foram colocados pelo utilizador, e coloca APENAS concursos inéditos na pasta 'Todos'.
        A data e hora registada é a da última pesquisa feita.
        """
        start_time = datetime.now()
        # Data e hora exata da última pesquisa realizada agora no servidor
        search_timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        logger.info(f"A iniciar pesquisa agregada (BASE + TED) às {search_timestamp}...")

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
        # Recupera todos os concursos armazenados no histórico anterior
        existing_raw = self.get_raw_cache()
        existing_items = existing_raw.get('items', []) if existing_raw else []

        items_map: Dict[str, Dict[str, Any]] = {}
        for old_it in existing_items:
            old_id = old_it.get('id')
            if old_id:
                items_map[str(old_id)] = old_it

        # Obter assignments existentes no servidor
        asg_data = self.get_assignments_data()
        assignments = asg_data.setdefault("assignments", {})

        # Processar concursos recolhidos
        for fresh_it in fresh_items:
            fresh_id = fresh_it.get('id')
            if not fresh_id:
                continue
            fresh_id_str = str(fresh_id)

            if fresh_id_str in items_map:
                # O concurso JÁ EXISTE no sistema:
                # Atualiza campos informativos frescos sem nunca perturbar a pasta nem o favorito
                for k, v in fresh_it.items():
                    if v not in (None, '', 'N/D'):
                        items_map[fresh_id_str][k] = v
            else:
                # NOVO CONCURSO DESCOBERTO:
                # Entra como inédito na pasta 'inbox' (Todos) para triagem pelo utilizador
                items_map[fresh_id_str] = fresh_it
                if fresh_id_str not in assignments:
                    assignments[fresh_id_str] = {
                        "folder": "inbox",
                        "is_favorite": False
                    }

        all_items = list(items_map.values())

        # Ordenar por data de publicação (mais recentes primeiro)
        all_items.sort(key=lambda x: self._parse_date_sort(x.get('publication_date')), reverse=True)

        # Atualizar carimbo da última pesquisa no servidor
        asg_data["last_search"] = search_timestamp
        self._save_assignments_file(asg_data)

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
        Separa rigorosamente os itens segundo as suas pastas e marca de favoritos:
        - Ativos (separador 'Todos'): APENAS os concursos NÃO classificados ('inbox')
        - Favoritos (separador 'Favoritos'): TODOS os concursos com marca de favorito (★)
        - Para avaliação (separador 'Para avaliação'): concursos colocados na pasta 'evaluation'
        - Descartados (separador 'Descartados'): concursos colocados na pasta 'dismissed'
        """
        asg_data = self.get_assignments_data()
        assignments = asg_data.get("assignments", {})
        last_search = asg_data.get("last_search") or raw_data.get("timestamp") or datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        all_items = raw_data.get('items', [])

        active_items = []
        favorite_items = []
        evaluation_items = []
        dismissed_items = []

        base_active = 0
        ted_active = 0

        for it in all_items:
            it_id = str(it.get('id'))
            item_asg = assignments.get(it_id, {"folder": "inbox", "is_favorite": False})
            folder = item_asg.get("folder", "inbox")
            is_fav = bool(item_asg.get("is_favorite", False))

            it['folder'] = folder
            it['is_favorite'] = is_fav
            it['is_evaluation'] = (folder == "evaluation")
            it['is_dismissed'] = (folder == "dismissed")

            # 1. Separador 'Todos' -> Apenas e só os que aguardam triagem (inbox)
            if folder == "inbox":
                active_items.append(it)
                if it.get('source') == 'Portal BASE':
                    base_active += 1
                else:
                    ted_active += 1

            # 2. Separador 'Favoritos' -> Todos os que têm estrela de favorito ativa!
            if is_fav:
                favorite_items.append(it)

            # 3. Separador 'Para avaliação' -> Todos os que estão na pasta de avaliação
            if folder == "evaluation":
                evaluation_items.append(it)

            # 4. Separador 'Descartados' -> Todos os que estão na pasta de descartados
            if folder == "dismissed":
                dismissed_items.append(it)

        return {
            'timestamp': last_search,
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
        """Gera um resumo claro e estruturado dos pilares requeridos."""
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
        Caso contrário, exporta todos os concursos da lista ativa.
        """
        cached = self.get_cached_results()
        if not cached:
            return ""

        candidate_items = cached.get('items', []) + cached.get('favorite_items', []) + cached.get('evaluation_items', []) + cached.get('dismissed_items', [])
        seen_ids = set()
        unique_candidates = []
        for it in candidate_items:
            it_id = it.get('id')
            if it_id not in seen_ids:
                seen_ids.add(it_id)
                unique_candidates.append(it)

        if selected_ids and len(selected_ids) > 0:
            ids_set = set(selected_ids)
            export_list = [it for it in unique_candidates if it.get('id') in ids_set]
        else:
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
        print(f"Data última pesquisa: {cached['timestamp']}")
        print(f"Ativos (Todos): {cached['total_count']}, Favoritos: {cached['favorite_count']}, Avaliação: {cached['evaluation_count']}, Descartados: {cached['dismissed_count']}")
