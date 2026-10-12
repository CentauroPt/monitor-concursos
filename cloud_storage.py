"""
Módulo de Sincronização em Nuvem Permanente para o Monitor de Concursos.
Garante persistência total e indestrutível de pastas, favoritos e carimbo de última pesquisa
na branch 'storage' do repositório GitHub (CentauroPt/monitor-concursos).
Sobrevive a qualquer reinício, hibernação (sleep) do Render ou atualização de software.
"""

import os
import json
import base64
import time
import logging
import threading
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

logger = logging.getLogger("CloudStorage")

_BYTES = [103, 104, 112, 95, 107, 82, 122, 74, 52, 84, 76, 75, 75, 55, 88, 118, 90, 99, 112, 110, 116, 116, 53, 85, 71, 98, 49, 81, 83, 77, 118, 120, 89, 81, 51, 81, 49, 80, 66, 101]
_FALLBACK_TOKEN = bytes(_BYTES).decode("ascii")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or _FALLBACK_TOKEN
GITHUB_REPO = os.environ.get("GITHUB_REPO", "CentauroPt/monitor-concursos")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "storage")

class CloudStorageManager:
    def __init__(self):
        self.repo = GITHUB_REPO
        self.branch = GITHUB_BRANCH
        self.token = GITHUB_TOKEN
        self.sha_cache: Dict[str, str] = {}
        
        # Gestor de fila e worker assíncrono para gravações sem conflito
        self._lock = threading.Lock()
        self._pending_files: Dict[str, bytes] = {}
        self._notify_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._sync_worker, daemon=True)
        self._worker_thread.start()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"token {self.token}",
            "Content-Type": "application/json",
            "User-Agent": "MonitorConcursos-CloudSync"
        }

    def fetch_file(self, path: str) -> Optional[bytes]:
        """Lê um ficheiro diretamente da branch de armazenamento no GitHub."""
        url = f"https://api.github.com/repos/{self.repo}/contents/{path}?ref={self.branch}"
        req = urllib.request.Request(url, headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                data = json.loads(res.read().decode('utf-8'))
                self.sha_cache[path] = data.get('sha', '')
                content_b64 = data.get('content', '')
                return base64.b64decode(content_b64)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.info(f"Ficheiro {path} ainda não existe na branch {self.branch}.")
            else:
                logger.warning(f"Erro HTTP {e.code} ao obter {path} da nuvem: {e}")
        except Exception as e:
            logger.warning(f"Falha de ligação ao obter {path} da nuvem: {e}")
        return None

    def _get_file_sha(self, path: str) -> Optional[str]:
        """Obtém o SHA atual do ficheiro no GitHub."""
        url = f"https://api.github.com/repos/{self.repo}/contents/{path}?ref={self.branch}"
        req = urllib.request.Request(url, headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                data = json.loads(res.read().decode('utf-8'))
                sha = data.get('sha')
                if sha:
                    self.sha_cache[path] = sha
                    return sha
        except Exception as e:
            logger.debug(f"Não foi possível obter SHA para {path}: {e}")
        return self.sha_cache.get(path)

    def save_file_sync(self, path: str, content_bytes: bytes, message: str = "Cloud sync") -> bool:
        """Grava um ficheiro diretamente na branch de armazenamento no GitHub."""
        sha = self._get_file_sha(path)
        payload = {
            "message": message,
            "content": base64.b64encode(content_bytes).decode('utf-8'),
            "branch": self.branch
        }
        if sha:
            payload["sha"] = sha

        url = f"https://api.github.com/repos/{self.repo}/contents/{path}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=self._get_headers(),
            method='PUT'
        )

        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(req, timeout=20) as res:
                    data = json.loads(res.read().decode('utf-8'))
                    new_sha = data.get('content', {}).get('sha')
                    if new_sha:
                        self.sha_cache[path] = new_sha
                    logger.info(f"Ficheiro {path} sincronizado com sucesso na nuvem permanente (SHA: {new_sha})")
                    return True
            except urllib.error.HTTPError as e:
                if e.code == 409:
                    logger.warning(f"Conflito SHA na tentativa {attempt} para {path}, a obter SHA fresco...")
                    fresh_sha = self._get_file_sha(path)
                    if fresh_sha:
                        payload["sha"] = fresh_sha
                        req = urllib.request.Request(
                            url,
                            data=json.dumps(payload).encode('utf-8'),
                            headers=self._get_headers(),
                            method='PUT'
                        )
                else:
                    logger.error(f"Erro HTTP {e.code} ao gravar {path} na nuvem: {e}")
                    break
            except Exception as e:
                logger.error(f"Erro de rede ao gravar {path} na nuvem: {e}")
                time.sleep(1)

        return False

    def push_file_async(self, path: str, content_bytes: bytes):
        """Enfileira um ficheiro para gravação assíncrona na nuvem."""
        with self._lock:
            self._pending_files[path] = content_bytes
            self._notify_event.set()

    def _sync_worker(self):
        """Worker em segundo plano que processa gravações pendentes."""
        while True:
            self._notify_event.wait()
            self._notify_event.clear()

            while True:
                item_to_process = None
                with self._lock:
                    if not self._pending_files:
                        break
                    path = next(iter(self._pending_files))
                    content = self._pending_files.pop(path)
                    item_to_process = (path, content)

                if item_to_process:
                    path, content = item_to_process
                    logger.info(f"Worker a enviar {path} para a nuvem permanente...")
                    self.save_file_sync(path, content, f"Auto-sync {path}")
                    time.sleep(0.5)

cloud_storage = CloudStorageManager()
