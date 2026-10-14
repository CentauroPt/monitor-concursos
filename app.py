"""
Servidor Web Local do Monitor de Concursos Públicos (Portal BASE & TED).
Executa na porta 8080 com interface moderna e API REST integrada.
Garante persistência central no servidor de pastas, favoritos e data/hora da última pesquisa.
"""

import os
import json
import logging
import mimetypes
from datetime import datetime
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

from analyzer import ProcurementAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MonitorConcursos")

PORT = int(os.environ.get("PORT", 8080))
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
analyzer = ProcurementAnalyzer()


class MonitorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            return self._serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
        elif path == "/contratos" or path == "/contratos.html":
            return self._serve_file(os.path.join(STATIC_DIR, "contratos.html"), "text/html; charset=utf-8")
        elif path == "/styles.css":
            return self._serve_file(os.path.join(STATIC_DIR, "styles.css"), "text/css; charset=utf-8")
        elif path == "/app.js":
            return self._serve_file(os.path.join(STATIC_DIR, "app.js"), "application/javascript; charset=utf-8")
        elif path == "/contratos.js":
            return self._serve_file(os.path.join(STATIC_DIR, "contratos.js"), "application/javascript; charset=utf-8")

        elif path == "/api/status":
            asg_data = analyzer.get_assignments_data()
            last_search = asg_data.get("last_search", "")
            cached = analyzer.get_cached_results()
            if cached:
                resp = {
                    'has_data': True,
                    'timestamp': cached.get('timestamp') or last_search,
                    'total_count': cached.get('total_count', 0),
                    'base_count': cached.get('base_count', 0),
                    'ted_count': cached.get('ted_count', 0),
                    'favorite_count': cached.get('favorite_count', 0),
                    'evaluation_count': cached.get('evaluation_count', 0),
                    'dismissed_count': cached.get('dismissed_count', 0),
                    'ted_country': cached.get('ted_country', 'PRT')
                }
            else:
                resp = {
                    'has_data': False,
                    'timestamp': last_search
                }
            return self._send_json(resp)

        elif path == "/api/results":
            cached = analyzer.get_cached_results()
            if not cached:
                return self._send_json({'items': [], 'total_count': 0})
            return self._send_json(cached)

        elif path == "/api/export":
            csv_content = analyzer.export_csv()
            if not csv_content:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Sem dados para exportar.")
                return

            filename = f"concursos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            data = csv_content.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        else:
            return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/search":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                params = json.loads(body.decode('utf-8'))
            except Exception:
                params = {}

            ted_country = params.get('ted_country', 'PRT')
            logger.info(f"A executar nova pesquisa a pedido do utilizador (País TED: {ted_country})...")
            
            try:
                results = analyzer.run_full_search(
                    ted_country=ted_country, 
                    max_base_items=25
                )
                return self._send_json(results)
            except Exception as e:
                logger.error(f"Erro ao executar pesquisa: {e}")
                return self._send_json({'error': str(e)}, status=500)

        elif path == "/api/set_folder":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                payload = json.loads(body.decode('utf-8'))
                item_id = payload.get('id')
                folder = payload.get('folder')
                if item_id and folder:
                    res = analyzer.set_item_folder(item_id, folder)
                    cached = analyzer.get_cached_results() or {}
                    return self._send_json({
                        'success': True,
                        'item': res,
                        'counts': self._extract_counts(cached)
                    })
            except Exception as e:
                logger.error(f"Erro ao alterar pasta: {e}")
            return self._send_json({'success': False}, status=400)

        elif path == "/api/favorite" or path == "/api/toggle_favorite":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                payload = json.loads(body.decode('utf-8'))
                item_id = payload.get('id')
                if item_id:
                    res = analyzer.toggle_favorite(item_id)
                    cached = analyzer.get_cached_results() or {}
                    return self._send_json({
                        'success': True,
                        'id': item_id,
                        'is_favorite': res.get('is_favorite'),
                        'folder': res.get('folder'),
                        'counts': self._extract_counts(cached)
                    })
            except Exception as e:
                logger.error(f"Erro ao alternar favorito: {e}")
            return self._send_json({'success': False}, status=400)

        elif path == "/api/evaluate":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                payload = json.loads(body.decode('utf-8'))
                item_id = payload.get('id')
                if item_id:
                    res = analyzer.toggle_evaluation(item_id)
                    cached = analyzer.get_cached_results() or {}
                    return self._send_json({
                        'success': True,
                        'id': item_id,
                        'is_evaluation': (res.get('folder') == 'evaluation'),
                        'folder': res.get('folder'),
                        'is_favorite': res.get('is_favorite'),
                        'counts': self._extract_counts(cached)
                    })
            except Exception as e:
                logger.error(f"Erro ao alternar avaliação: {e}")
            return self._send_json({'success': False}, status=400)

        elif path == "/api/dismiss":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                payload = json.loads(body.decode('utf-8'))
                item_id = payload.get('id')
                if item_id:
                    analyzer.dismiss_item(item_id)
                    cached = analyzer.get_cached_results() or {}
                    return self._send_json({
                        'success': True,
                        'id': item_id,
                        'folder': 'dismissed',
                        'counts': self._extract_counts(cached)
                    })
            except Exception as e:
                logger.error(f"Erro ao descartar item: {e}")
            return self._send_json({'success': False}, status=400)

        elif path == "/api/restore":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                payload = json.loads(body.decode('utf-8'))
                item_id = payload.get('id')
                if item_id:
                    analyzer.restore_item(item_id)
                    cached = analyzer.get_cached_results() or {}
                    asg = analyzer.get_item_assignment(item_id)
                    return self._send_json({
                        'success': True,
                        'id': item_id,
                        'folder': asg.get('folder', 'inbox'),
                        'is_favorite': asg.get('is_favorite', False),
                        'counts': self._extract_counts(cached)
                    })
            except Exception as e:
                logger.error(f"Erro ao restaurar item: {e}")
            return self._send_json({'success': False}, status=400)

        elif path == "/api/export":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                payload = json.loads(body.decode('utf-8'))
                selected_ids = payload.get('ids', [])
            except Exception:
                selected_ids = []

            csv_content = analyzer.export_csv(selected_ids=selected_ids)
            if not csv_content:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Sem dados para exportar.")
                return

            filename = f"concursos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            data = csv_content.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        elif path == "/api/contracts/search":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                params = json.loads(body.decode('utf-8'))
            except Exception:
                params = {}

            nif = params.get('nif')
            entity_name = params.get('entity_name')
            source = params.get('source', 'all')
            ted_country = params.get('ted_country', 'PRT')
            limit = int(params.get('limit', 50))
            date_start = params.get('date_start')
            date_end = params.get('date_end')
            date_mode = params.get('date_mode', 'any')

            logger.info(f"Pesquisa de contratos por entidade (NIF={nif}, Nome={entity_name}, Fonte={source}, Datas={date_start} a {date_end}, Modo={date_mode}, Limite={limit})...")
            try:
                results = analyzer.search_entity_contracts(
                    nif=nif,
                    entity_name=entity_name,
                    source=source,
                    ted_country=ted_country,
                    limit=limit,
                    date_start=date_start,
                    date_end=date_end,
                    date_mode=date_mode
                )
                return self._send_json(results)
            except Exception as e:
                logger.error(f"Erro na pesquisa de contratos: {e}")
                return self._send_json({'error': str(e)}, status=500)

        elif path == "/api/contracts/export":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                payload = json.loads(body.decode('utf-8'))
                contracts = payload.get('contracts', [])
            except Exception:
                contracts = []

            csv_content = analyzer.export_contracts_csv(contracts)
            if not csv_content:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Sem contratos para exportar.")
                return

            filename = f"contratos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            data = csv_content.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        else:
            self.send_response(404)
            self.end_headers()

    def _extract_counts(self, cached: Dict[str, Any]) -> Dict[str, int]:
        return _extract_counts_dict(cached)

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filepath: str, content_type: str):
        if not os.path.exists(filepath):
            self.send_response(404)
            self.end_headers()
            return
        with open(filepath, 'rb') as f:
            content = f.read()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        self.wfile.write(content)


def _extract_counts_dict(cached: Optional[Dict[str, Any]]) -> Dict[str, int]:
    if not cached:
        cached = {}
    return {
        'total_count': cached.get('total_count', 0),
        'base_count': cached.get('base_count', 0),
        'ted_count': cached.get('ted_count', 0),
        'favorite_count': cached.get('favorite_count', 0),
        'evaluation_count': cached.get('evaluation_count', 0),
        'dismissed_count': cached.get('dismissed_count', 0)
    }


def wsgi_application(environ, start_response):
    """
    Aplicação WSGI padrão para suporte universal (Vercel, Render, Gunicorn, uWSGI, etc.).
    Responde às chamadas serverless e compatibiliza todas as rotas com zero configuração.
    """
    method = environ.get('REQUEST_METHOD', 'GET').upper()
    path = environ.get('PATH_INFO', '/')

    def send_json_resp(data: Any, status_code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        status_text = f"{status_code} {'OK' if status_code == 200 else 'Error'}"
        headers = [
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Content-Length', str(len(body))),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
            ('Access-Control-Allow-Headers', 'Content-Type')
        ]
        start_response(status_text, headers)
        return [body]

    def send_file_resp(filepath: str, content_type: str):
        if not os.path.exists(filepath):
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b"Not Found"]
        with open(filepath, 'rb') as f:
            content = f.read()
        headers = [
            ('Content-Type', content_type),
            ('Content-Length', str(len(content))),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ('Access-Control-Allow-Origin', '*')
        ]
        start_response('200 OK', headers)
        return [content]

    # Tratamento de CORS preflight
    if method == 'OPTIONS':
        headers = [
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
            ('Access-Control-Allow-Headers', 'Content-Type'),
            ('Content-Length', '0')
        ]
        start_response('204 No Content', headers)
        return [b'']

    # Rotas GET
    if method == 'GET':
        if path == '/' or path == '/index.html':
            return send_file_resp(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
        elif path == '/contratos' or path == '/contratos.html':
            return send_file_resp(os.path.join(STATIC_DIR, "contratos.html"), "text/html; charset=utf-8")
        elif path == '/styles.css':
            return send_file_resp(os.path.join(STATIC_DIR, "styles.css"), "text/css; charset=utf-8")
        elif path == '/app.js':
            return send_file_resp(os.path.join(STATIC_DIR, "app.js"), "application/javascript; charset=utf-8")
        elif path == '/contratos.js':
            return send_file_resp(os.path.join(STATIC_DIR, "contratos.js"), "application/javascript; charset=utf-8")
        elif path == '/api/status':
            asg_data = analyzer.get_assignments_data()
            last_search = asg_data.get("last_search", "")
            cached = analyzer.get_cached_results()
            if cached:
                resp = {
                    'has_data': True,
                    'timestamp': cached.get('timestamp') or last_search,
                    'total_count': cached.get('total_count', 0),
                    'base_count': cached.get('base_count', 0),
                    'ted_count': cached.get('ted_count', 0),
                    'favorite_count': cached.get('favorite_count', 0),
                    'evaluation_count': cached.get('evaluation_count', 0),
                    'dismissed_count': cached.get('dismissed_count', 0),
                    'ted_country': cached.get('ted_country', 'PRT')
                }
            else:
                resp = {'has_data': False, 'timestamp': last_search}
            return send_json_resp(resp)
        elif path == '/api/results':
            cached = analyzer.get_cached_results()
            if not cached:
                return send_json_resp({'items': [], 'total_count': 0})
            return send_json_resp(cached)
        elif path == '/api/export':
            csv_content = analyzer.export_csv()
            if not csv_content:
                start_response('404 Not Found', [('Content-Type', 'text/plain')])
                return [b"Sem dados para exportar."]
            filename = f"concursos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            data = csv_content.encode('utf-8')
            headers = [
                ('Content-Type', 'text/csv; charset=utf-8'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(data)))
            ]
            start_response('200 OK', headers)
            return [data]
        else:
            rel_path = path.lstrip('/')
            static_file = os.path.join(STATIC_DIR, rel_path)
            if os.path.exists(static_file) and os.path.isfile(static_file):
                mime, _ = mimetypes.guess_type(static_file)
                return send_file_resp(static_file, mime or 'application/octet-stream')
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b"Not Found"]

    # Rotas POST
    elif method == 'POST':
        try:
            content_length = int(environ.get('CONTENT_LENGTH', 0))
        except (ValueError, TypeError):
            content_length = 0
        body_bytes = environ['wsgi.input'].read(content_length) if content_length > 0 else b'{}'
        try:
            payload = json.loads(body_bytes.decode('utf-8'))
        except Exception:
            payload = {}

        if path == '/api/search':
            ted_country = payload.get('ted_country', 'PRT')
            logger.info(f"Nova pesquisa solicitada via WSGI (País TED: {ted_country})...")
            try:
                results = analyzer.run_full_search(ted_country=ted_country, max_base_items=25)
                return send_json_resp(results)
            except Exception as e:
                logger.error(f"Erro ao executar pesquisa: {e}")
                return send_json_resp({'error': str(e)}, 500)

        elif path == '/api/set_folder':
            item_id = payload.get('id')
            folder = payload.get('folder')
            if item_id and folder:
                res = analyzer.set_item_folder(item_id, folder)
                cached = analyzer.get_cached_results() or {}
                return send_json_resp({
                    'success': True,
                    'item': res,
                    'counts': _extract_counts_dict(cached)
                })
            return send_json_resp({'success': False}, 400)

        elif path == '/api/favorite' or path == '/api/toggle_favorite':
            item_id = payload.get('id')
            if item_id:
                res = analyzer.toggle_favorite(item_id)
                cached = analyzer.get_cached_results() or {}
                return send_json_resp({
                    'success': True,
                    'id': item_id,
                    'is_favorite': res.get('is_favorite'),
                    'folder': res.get('folder'),
                    'counts': _extract_counts_dict(cached)
                })
            return send_json_resp({'success': False}, 400)

        elif path == '/api/evaluate':
            item_id = payload.get('id')
            if item_id:
                res = analyzer.toggle_evaluation(item_id)
                cached = analyzer.get_cached_results() or {}
                return send_json_resp({
                    'success': True,
                    'id': item_id,
                    'is_evaluation': (res.get('folder') == 'evaluation'),
                    'folder': res.get('folder'),
                    'is_favorite': res.get('is_favorite'),
                    'counts': _extract_counts_dict(cached)
                })
            return send_json_resp({'success': False}, 400)

        elif path == '/api/dismiss':
            item_id = payload.get('id')
            if item_id:
                analyzer.dismiss_item(item_id)
                cached = analyzer.get_cached_results() or {}
                return send_json_resp({
                    'success': True,
                    'id': item_id,
                    'folder': 'dismissed',
                    'counts': _extract_counts_dict(cached)
                })
            return send_json_resp({'success': False}, 400)

        elif path == '/api/restore':
            item_id = payload.get('id')
            if item_id:
                analyzer.restore_item(item_id)
                cached = analyzer.get_cached_results() or {}
                asg = analyzer.get_item_assignment(item_id)
                return send_json_resp({
                    'success': True,
                    'id': item_id,
                    'folder': asg.get('folder', 'inbox'),
                    'is_favorite': asg.get('is_favorite', False),
                    'counts': _extract_counts_dict(cached)
                })
            return send_json_resp({'success': False}, 400)

        elif path == '/api/export':
            selected_ids = payload.get('ids', [])
            csv_content = analyzer.export_csv(selected_ids=selected_ids)
            if not csv_content:
                start_response('404 Not Found', [('Content-Type', 'text/plain')])
                return [b"Sem dados para exportar."]
            filename = f"concursos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            data = csv_content.encode('utf-8')
            headers = [
                ('Content-Type', 'text/csv; charset=utf-8'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(data)))
            ]
            start_response('200 OK', headers)
            return [data]

        elif path == '/api/contracts/search':
            nif = payload.get('nif')
            entity_name = payload.get('entity_name')
            source = payload.get('source', 'all')
            ted_country = payload.get('ted_country', 'PRT')
            limit = int(payload.get('limit', 50))
            date_start = payload.get('date_start')
            date_end = payload.get('date_end')
            date_mode = payload.get('date_mode', 'any')

            logger.info(f"Pesquisa de contratos por entidade via WSGI (NIF={nif}, Nome={entity_name}, Fonte={source}, Datas={date_start} a {date_end}, Modo={date_mode}, Limite={limit})...")
            try:
                results = analyzer.search_entity_contracts(
                    nif=nif,
                    entity_name=entity_name,
                    source=source,
                    ted_country=ted_country,
                    limit=limit,
                    date_start=date_start,
                    date_end=date_end,
                    date_mode=date_mode
                )
                return send_json_resp(results)
            except Exception as e:
                logger.error(f"Erro na pesquisa de contratos via WSGI: {e}")
                return send_json_resp({'error': str(e)}, 500)

        elif path == '/api/contracts/export':
            contracts = payload.get('contracts', [])
            csv_content = analyzer.export_contracts_csv(contracts)
            if not csv_content:
                start_response('404 Not Found', [('Content-Type', 'text/plain')])
                return [b"Sem contratos para exportar."]
            filename = f"contratos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            data = csv_content.encode('utf-8')
            headers = [
                ('Content-Type', 'text/csv; charset=utf-8'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(data)))
            ]
            start_response('200 OK', headers)
            return [data]

        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b"Not Found"]

    start_response('405 Method Not Allowed', [('Content-Type', 'text/plain')])
    return [b"Method Not Allowed"]


# Variáveis universais de nível de topo para plataformas WSGI / Serverless (Vercel, Render, Gunicorn, uWSGI)
app = wsgi_application
application = wsgi_application
handler = wsgi_application


def run_server():
    server_address = ('', PORT)
    httpd = ThreadingHTTPServer(server_address, MonitorHandler)
    url = f"http://localhost:{PORT}"
    print("\n" + "=" * 60)
    print(f"  MONITOR DE CONCURSOS PUBLICOS (BASE & TED)")
    print(f"  Servidor ativo em: {url}")
    print(f"  Pressione Ctrl+C para encerrar o servidor.")
    print("=" * 60 + "\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nA encerrar servidor...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
