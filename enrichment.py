"""
Módulo de Enriquecimento de Dados Cadastrais e de Contacto de Fornecedores.
Recolhe morada completa, contactos (telefone, email, website), redes sociais,
objeto social/CAE e links de verificação a partir de fontes públicas (Portal BASE, Racius, NIF.pt).
Inclui cache persistente para máxima velocidade e fiabilidade.
"""

import os
import json
import re
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = "/tmp/data" if os.environ.get("VERCEL") else os.path.join(os.path.dirname(__file__), "data")
SUPPLIERS_CACHE_FILE = os.path.join(CACHE_DIR, "suppliers_cache.json")

# Cache em memória
_MEMORY_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_cache():
    global _MEMORY_CACHE
    if _MEMORY_CACHE:
        return
    try:
        if os.path.exists(SUPPLIERS_CACHE_FILE):
            with open(SUPPLIERS_CACHE_FILE, 'r', encoding='utf-8') as f:
                _MEMORY_CACHE = json.load(f)
    except Exception as e:
        logger.warning(f"Aviso ao carregar cache de fornecedores: {e}")
        _MEMORY_CACHE = {}


def _save_cache():
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(SUPPLIERS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_MEMORY_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Aviso ao guardar cache de fornecedores: {e}")


def enrich_supplier(nif: Optional[str], name: Optional[str]) -> Dict[str, Any]:
    """
    Enriquece um fornecedor com morada completa, telefones, email, website,
    redes sociais e links de consulta com base no seu NIF ou Denominação Social.
    """
    _load_cache()

    clean_nif = str(nif or '').strip().replace(" ", "")
    clean_name = str(name or '').strip()
    cache_key = clean_nif or clean_name.lower()

    if not cache_key:
        return _default_supplier_info(clean_nif, clean_name)

    if cache_key in _MEMORY_CACHE:
        cached = _MEMORY_CACHE[cache_key]
        if cached.get("address") or cached.get("website") or cached.get("phone"):
            return cached

    info = _default_supplier_info(clean_nif, clean_name)

    # 1. Tentar consulta por NIF no NIF.pt e Racius (Schema.org JSON-LD)
    if clean_nif and len(clean_nif) == 9 and clean_nif.isdigit():
        try:
            _enrich_via_nif_and_racius(clean_nif, info)
        except Exception as e:
            logger.debug(f"Aviso ao consultar Racius/NIF.pt para NIF {clean_nif}: {e}")

    # 2. Se ainda faltar website ou telefone, tentar deteção inteligente por nome
    if not info.get("website") or not info.get("phone"):
        try:
            _enrich_contacts_heuristic(clean_name, clean_nif, info)
        except Exception as e:
            logger.debug(f"Aviso ao enriquecer contactos de {clean_name}: {e}")

    # Guardar na cache
    _MEMORY_CACHE[cache_key] = info
    _save_cache()
    return info


def _default_supplier_info(nif: str, name: str) -> Dict[str, Any]:
    encoded_name = urllib.parse.quote(name or nif or "")
    encoded_search = urllib.parse.quote(f"{name or ''} {nif or ''}".strip())

    return {
        "nif": nif,
        "name": name,
        "legal_name": name,
        "street_address": "",
        "postal_code": "",
        "locality": "",
        "country": "Portugal",
        "full_address": "Morada disponível mediante consulta pública",
        "phone": "",
        "phones": [],
        "email": "",
        "emails": [],
        "website": "",
        "social_media": {
            "linkedin": f"https://www.google.com/search?q={urllib.parse.quote(f'site:linkedin.com {name}')}",
            "facebook": f"https://www.google.com/search?q={urllib.parse.quote(f'site:facebook.com {name}')}",
            "instagram": "",
            "twitter": ""
        },
        "activity_description": "",
        "racius_url": f"https://www.racius.com/pesquisa/?q={nif or encoded_name}",
        "nif_pt_url": f"https://www.nif.pt/{nif}/" if nif else f"https://www.nif.pt/?q={encoded_name}",
        "base_gov_url": f"https://www.base.gov.pt/Base4/pt/pesquisa/?type=contratos&adjudicataria={nif or encoded_name}",
        "google_search_url": f"https://www.google.com/search?q={encoded_search}",
        "google_maps_url": f"https://www.google.com/maps/search/{encoded_search}",
        "is_enriched": False
    }


def _enrich_via_nif_and_racius(nif: str, info: Dict[str, Any]):
    url_nif = f"https://www.nif.pt/{nif}/"
    req = urllib.request.Request(
        url_nif,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    )
    
    html = ""
    try:
        with urllib.request.urlopen(req, timeout=6) as res:
            html = res.read().decode('utf-8', errors='ignore')
    except Exception:
        return

    # Extrair título ou link para Racius
    m_racius = re.search(r'href=[\x27\x22](https://www\.racius\.com/[^\x27\x22]+)[\x27\x22]', html)
    racius_url = m_racius.group(1) if m_racius else None

    # Tentar extrair morada direta do NIF.pt se houver
    m_addr_nif = re.search(r'(\d{4}-\d{3})\s+([A-Za-zÀ-ÖØ-öø-ÿ\s]+)', html)
    if m_addr_nif:
        info["postal_code"] = m_addr_nif.group(1).strip()
        info["locality"] = m_addr_nif.group(2).strip()

    if racius_url:
        info["racius_url"] = racius_url
        req_racius = urllib.request.Request(
            racius_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        try:
            with urllib.request.urlopen(req_racius, timeout=6) as r_res:
                r_html = r_res.read().decode('utf-8', errors='ignore')

            # Extrair application/ld+json Schema.org
            m_ld = re.search(r'<script\s+type=[\x22\x27]application/ld\+json[\x22\x27]>(.*?)</script>', r_html, re.DOTALL)
            if m_ld:
                try:
                    data = json.loads(m_ld.group(1))
                    if isinstance(data, dict):
                        if data.get("name"):
                            info["name"] = data.get("name")
                        if data.get("legalName"):
                            info["legal_name"] = data.get("legalName")
                        if data.get("description"):
                            info["activity_description"] = data.get("description").strip()

                        addr = data.get("address")
                        if isinstance(addr, dict):
                            street = str(addr.get("streetAddress") or "").strip()
                            postal = str(addr.get("postalCode") or "").strip()
                            loc = str(addr.get("addressLocality") or "").strip()
                            country = str(addr.get("addressCountry") or "Portugal").strip()

                            info["street_address"] = street
                            if postal:
                                info["postal_code"] = postal
                            if loc:
                                info["locality"] = loc
                            info["country"] = country

                            full_parts = [p for p in [street, f"{postal} {loc}".strip(), country] if p]
                            if full_parts:
                                info["full_address"] = ", ".join(full_parts)
                                info["google_maps_url"] = f"https://www.google.com/maps/search/{urllib.parse.quote(info['full_address'])}"

                        info["is_enriched"] = True
                except Exception as je:
                    logger.debug(f"Erro ao descodificar JSON-LD Racius: {je}")

            # Procurar websites e contactos no HTML do Racius
            phones = re.findall(r'\b(?:2\d{1,2}[\s.-]?\d{3}[\s.-]?\d{3,4}|9[1236]\d{1}[\s.-]?\d{3}[\s.-]?\d{3}|80[08][\s.-]?\d{3}[\s.-]?\d{3})\b', r_html)
            valid_phones = []
            for p in phones:
                digits = re.sub(r'\D', '', p)
                if len(digits) == 9 and digits not in [nif, '500239037']:
                    # Formatar legível: ex: 227 867 000
                    formatted = f"{digits[:3]} {digits[3:6]} {digits[6:]}" if not digits.startswith("21") and not digits.startswith("22") else f"{digits[:2]} {digits[2:5]} {digits[5:]}"
                    valid_phones.append(formatted)
            if valid_phones:
                info["phones"] = list(dict.fromkeys(valid_phones[:3]))
                info["phone"] = valid_phones[0]

            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', r_html)
            valid_emails = [e for e in emails if not any(x in e.lower() for x in ['racius', 'vendus', 'sentry', 'google', 'w3.org'])]
            if valid_emails:
                info["emails"] = list(dict.fromkeys(valid_emails[:2]))
                info["email"] = valid_emails[0]

        except Exception as re_err:
            logger.debug(f"Aviso ao ler página do Racius: {re_err}")


def _enrich_contacts_heuristic(name: str, nif: str, info: Dict[str, Any]):
    """
    Gera ligações canónicas e dados de pesquisa para redes sociais e websites oficiais.
    """
    clean = re.sub(r'\b(unipessoal|lda|sa|s\.a|s\.a\.|limitada|sociedade|portugal|pt)\b', '', name, flags=re.I).strip()
    slug = re.sub(r'[^a-zA-Z0-9]', '', clean).lower()

    if slug and not info.get("website"):
        # Se for uma empresa conhecida ou domínio dedutível
        candidate_site = f"https://www.{slug}.pt"
        info["website"] = candidate_site

    # Links diretos para redes sociais
    search_q = urllib.parse.quote(name or nif)
    info["social_media"]["linkedin"] = f"https://www.linkedin.com/search/results/all/?keywords={search_q}"
    info["social_media"]["facebook"] = f"https://www.facebook.com/search/top?q={search_q}"
    info["social_media"]["instagram"] = f"https://www.google.com/search?q={urllib.parse.quote(f'site:instagram.com {name}')}"
    info["social_media"]["twitter"] = f"https://x.com/search?q={search_q}"
