import os
import sys
import base64
import json
import urllib.request

TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
REPO = "CentauroPt/monitor-concursos"
BASE_DIR = os.path.dirname(__file__)

FILES_TO_UPLOAD = [
    "app.py",
    "analyzer.py",
    "scraper_base.py",
    "scraper_ted.py",
    "requirements.txt",
    "render.yaml",
    "Procfile",
    "README.md",
    "sync_github.py",
    "static/index.html",
    "static/contratos.html",
    "static/contratos.js",
    "static/styles.css",
    "static/app.js",
    "data/cache.json",
    "data/evaluation.json",
    "data/favorites.json",
    "data/dismissed.json"
]

def upload_file(rel_path, token):
    full_path = os.path.join(BASE_DIR, rel_path.replace('/', os.sep))
    if not os.path.exists(full_path):
        print(f"Ignorado (nao existe): {rel_path}")
        return

    with open(full_path, 'rb') as f:
        content_b64 = base64.b64encode(f.read()).decode('utf-8')

    url = f"https://api.github.com/repos/{REPO}/contents/{rel_path}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'MonitorConcursosDeployer'
    }

    # Check if file exists to get sha
    sha = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            sha = data.get('sha')
    except Exception:
        pass

    payload = {
        'message': f"Inclui Diário da República Eletrónico (DRE), Acingov, Vortal, AnoGov e ComprasPT na pesquisa ({rel_path})",
        'content': content_b64
    }
    if sha:
        payload['sha'] = sha

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='PUT')
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"[OK] Enviado com sucesso: {rel_path}")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar {rel_path}: {e}")

if __name__ == "__main__":
    if not TOKEN:
        print("Uso: python sync_github.py <GITHUB_TOKEN>")
        sys.exit(1)
    for f in FILES_TO_UPLOAD:
        upload_file(f, TOKEN)
    print("\nSincronizacao concluida!")
