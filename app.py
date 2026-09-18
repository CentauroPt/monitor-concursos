"""
Servidor Web Local do Monitor de Concursos Públicos (Portal BASE & TED).
Executa na porta 8080 com interface moderna e API REST integrada.
Não requer instalação de frameworks externos (utiliza biblioteca padrão do Python).
"""

import os
import json
import logging
import mimetypes
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import webbrowser

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
        elif path == "/styles.css":
            return self._serve_file(os.path.join(STATIC_DIR, "styles.css"), "text/css; charset=utf-8")
        elif path == "/app.js":
            return self._serve_file(os.path.join(STATIC_DIR, "app.js"), "application/javascript; charset=utf-8")

        elif path == "/api/status":
            cached = analyzer.get_cached_results()
            if cached:
                resp = {
                    'has_data': True,
                    'timestamp': cached.get('timestamp'),
                    'total_count': cached.get('total_count', 0),
                    'base_count': cached.get('base_count', 0),
                    'ted_count': cached.get('ted_count', 0),
                    'favorite_count': cached.get('favorite_count', 0),
                    'dismissed_count': cached.get('dismissed_count', 0),
                    'ted_country': cached.get('ted_country', 'PRT')
                }
            else:
                resp = {'has_data': False}
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
                results = analyzer.run_full_search(ted_country=ted_country, max_base_items=25)
                return self._send_json(results)
            except Exception as e:
                logger.error(f"Erro ao executar pesquisa: {e}")
                return self._send_json({'error': str(e)}, status=500)

        elif path == "/api/dismiss":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                payload = json.loads(body.decode('utf-8'))
                item_id = payload.get('id')
                if item_id:
                    success = analyzer.dismiss_item(item_id)
                    return self._send_json({'success': success, 'id': item_id})
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
                    success = analyzer.restore_item(item_id)
            except Exception as e:
                logger.error(f"Erro ao restaurar item: {e}")
            return self._send_json({'success': False}, status=400)

        elif path == "/api/favorite":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                payload = json.loads(body.decode('utf-8'))
                item_id = payload.get('id')
                if item_id:
                    is_fav = analyzer.toggle_favorite(item_id)
                    return self._send_json({'success': True, 'id': item_id, 'is_favorite': is_fav})
            except Exception as e:
                logger.error(f"Erro ao alternar favorito: {e}")
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

        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
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
        self.end_headers()
        self.wfile.write(content)


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
    from datetime import datetime
    run_server()
