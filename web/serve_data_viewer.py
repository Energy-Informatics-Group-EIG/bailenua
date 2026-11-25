#!/usr/bin/env python3
"""Local snapshot viewer for the hrsd-occupants Backblaze B2 bucket.

The browser never sees the application key. This process binds to 127.0.0.1,
authorizes with Backblaze, and proxies list and download calls.

Credentials, first match wins:
  .b2.local.json at the repo root: {"keyId": "...", "applicationKey": "..."}
  environment: B2_KEY_ID and B2_APPLICATION_KEY

Run from anywhere:
  python3 web/serve_data_viewer.py
Then open the localhost address it prints. The default port is 8787.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = Path(__file__).resolve().parent
CRED_PATH = ROOT / ".b2.local.json"
PORT = int(os.environ.get("PORT", "8787"))
HOST = "127.0.0.1"
LIST_TTL_S = 10
STATIC_EXT = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


def load_credentials() -> tuple[str, str]:
    if CRED_PATH.is_file():
        data = json.loads(CRED_PATH.read_text())
        key_id = str(data.get("keyId") or "").strip()
        app_key = str(data.get("applicationKey") or "").strip()
        if key_id and app_key:
            return key_id, app_key
    key_id = os.environ.get("B2_KEY_ID", "").strip()
    app_key = os.environ.get("B2_APPLICATION_KEY", "").strip()
    if key_id and app_key:
        return key_id, app_key
    raise RuntimeError(
        "Missing Backblaze credentials. Add .b2.local.json at the repo root "
        "or set B2_KEY_ID and B2_APPLICATION_KEY."
    )


class B2:
    def __init__(self, key_id: str, app_key: str) -> None:
        self.key_id = key_id
        self.app_key = app_key
        self.lock = threading.Lock()
        self.token: str | None = None
        self.api_url = ""
        self.download_url = ""
        self.bucket_id = ""
        self.bucket_name = ""
        self._files: list[dict] | None = None
        self._files_at = 0.0

    def authorize(self, force: bool = False) -> None:
        with self.lock:
            if self.token and not force:
                return
            basic = base64.b64encode(f"{self.key_id}:{self.app_key}".encode()).decode()
            req = urllib.request.Request(
                "https://api.backblazeb2.com/b2api/v3/b2_authorize_account",
                headers={"Authorization": f"Basic {basic}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            api = data["apiInfo"]["storageApi"]
            self.token = data["authorizationToken"]
            self.api_url = api["apiUrl"]
            self.download_url = api["downloadUrl"]
            self.bucket_id = api.get("bucketId") or ""
            self.bucket_name = api.get("bucketName") or ""
            if not self.bucket_id:
                buckets = self._post(
                    "/b2api/v2/b2_list_buckets",
                    {"accountId": data["accountId"]},
                    already_authorized=True,
                )
                match = next(
                    (b for b in buckets.get("buckets", []) if b.get("bucketName") == "hrsd-occupants"),
                    None,
                )
                if match is None and buckets.get("buckets"):
                    match = buckets["buckets"][0]
                if match is None:
                    raise RuntimeError("The key cannot see any buckets.")
                self.bucket_id = match["bucketId"]
                self.bucket_name = match["bucketName"]

    def _post(self, path: str, body: dict, already_authorized: bool = False) -> dict:
        if not already_authorized:
            self.authorize()
        payload = json.dumps(body).encode()

        def once() -> dict:
            req = urllib.request.Request(
                self.api_url + path,
                data=payload,
                method="POST",
                headers={
                    "Authorization": self.token or "",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)

        try:
            return once()
        except urllib.error.HTTPError as err:
            if err.code == 401 and not already_authorized:
                self.authorize(force=True)
                return once()
            detail = err.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"Backblaze {path} failed ({err.code}): {detail}") from err

    def list_files(self, refresh: bool = False) -> list[dict]:
        now = time.time()
        if self._files is not None and not refresh and now - self._files_at < LIST_TTL_S:
            return self._files
        self.authorize()
        files: list[dict] = []
        start = None
        while True:
            body: dict = {"bucketId": self.bucket_id, "maxFileCount": 10000}
            if start:
                body["startFileName"] = start
            page = self._post("/b2api/v2/b2_list_file_names", body)
            for item in page.get("files", []):
                name = item.get("fileName") or ""
                size = int(item.get("contentLength") or 0)
                if name.endswith("/") and size == 0:
                    continue
                files.append(
                    {
                        "name": name,
                        "size": size,
                        "contentType": item.get("contentType") or "",
                        "uploaded": item.get("uploadTimestamp"),
                    }
                )
            start = page.get("nextFileName")
            if not start:
                break
        self._files = files
        self._files_at = time.time()
        return files

    def open_download(self, name: str, range_header: str | None, method: str = "GET"):
        self.authorize()
        url = (
            f"{self.download_url}/file/{urllib.parse.quote(self.bucket_name)}"
            f"/{urllib.parse.quote(name, safe='/')}"
        )

        def once():
            headers = {"Authorization": self.token or ""}
            if range_header:
                headers["Range"] = range_header
            req = urllib.request.Request(url, headers=headers, method=method)
            return urllib.request.urlopen(req, timeout=120)

        try:
            return once()
        except urllib.error.HTTPError as err:
            if err.code == 401:
                self.authorize(force=True)
                return once()
            raise


def clean_name(raw: str) -> str:
    name = urllib.parse.unquote(raw or "")
    if not name or len(name) > 4096:
        raise ValueError("Missing file name.")
    if name.startswith("/") or "\\" in name or "\n" in name or "\r" in name or "\x00" in name:
        raise ValueError("File name is not allowed.")
    if any(part == ".." for part in name.split("/")):
        raise ValueError("File name is not allowed.")
    return name


def safe_static(url_path: str) -> Path | None:
    rel = urllib.parse.unquote(url_path).lstrip("/")
    if not rel or rel.endswith("/"):
        return None
    if any(part.startswith(".") or part == ".." for part in rel.split("/")):
        return None
    path = (WEB / rel).resolve()
    if WEB not in path.parents and path != WEB:
        return None
    if not path.is_file():
        return None
    if path.suffix.lower() not in STATIC_EXT:
        return None
    return path


class Handler(BaseHTTPRequestHandler):
    server_version = "BaileNuaDataViewer/1.0"

    def log_message(self, fmt: str, *args) -> None:
        message = fmt % args
        if "authorization" in message.lower() or "applicationKey" in message:
            return
        print(f"[{self.log_date_time_string()}] {message}")

    def _send(self, code: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json; charset=utf-8")

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                self.send_response(302)
                self.send_header("Location", "/data_viewer.html")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path == "/api/status":
                self._status()
                return
            if path == "/api/files":
                self._files(refresh=query.get("refresh", ["0"])[0] == "1")
                return
            if path == "/api/file":
                name = clean_name(query.get("name", [""])[0])
                download = query.get("download", ["0"])[0] == "1"
                max_bytes = query.get("maxBytes", [""])[0]
                cap = int(max_bytes) if max_bytes.isdigit() else None
                self._file(name, download, cap)
                return
            if path == "/docs/DATASETS.md":
                self._datasets_doc()
                return
            static = safe_static(path)
            if static is None:
                self._json(404, {"error": "Not found."})
                return
            data = static.read_bytes()
            content_type = STATIC_EXT.get(static.suffix.lower()) or mimetypes.guess_type(static.name)[0] or "application/octet-stream"
            self._send(200, data, content_type)
        except ValueError as err:
            self._json(400, {"error": str(err)})
        except Exception as err:  # noqa: BLE001 — surface a short message to the local UI
            self._json(502, {"error": str(err)})

    def _datasets_doc(self) -> None:
        path = (ROOT / "docs" / "DATASETS.md").resolve()
        docs = (ROOT / "docs").resolve()
        if path.parent != docs or not path.is_file():
            self._json(404, {"error": "docs/DATASETS.md is not on this machine."})
            return
        self._send(200, path.read_bytes(), "text/markdown; charset=utf-8")

    def _status(self) -> None:
        b2.authorize()
        self._json(
            200,
            {
                "ok": True,
                "bucket": b2.bucket_name,
                "bucketId": b2.bucket_id,
            },
        )

    def _files(self, refresh: bool) -> None:
        files = b2.list_files(refresh=refresh)
        self._json(
            200,
            {
                "bucket": b2.bucket_name,
                "count": len(files),
                "bytes": sum(f["size"] for f in files),
                "files": files,
            },
        )

    def _file(self, name: str, download: bool, cap: int | None) -> None:
        range_header = self.headers.get("Range")
        if cap is not None and cap > 0 and not range_header:
            known = next((f for f in (b2._files or []) if f["name"] == name), None)
            size = known["size"] if known else None
            if size is None or size > cap:
                range_header = f"bytes=0-{cap - 1}"
        remote = b2.open_download(name, range_header, method="HEAD" if self.command == "HEAD" else "GET")
        try:
            status = getattr(remote, "status", 200) or 200
            info = remote.headers
            self.send_response(status)
            self.send_header("Content-Type", info.get("Content-Type") or "application/octet-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("X-Content-Type-Options", "nosniff")
            if info.get("Content-Range"):
                self.send_header("Content-Range", info["Content-Range"])
            if info.get("Content-Length"):
                self.send_header("Content-Length", info["Content-Length"])
            if download:
                base = name.rsplit("/", 1)[-1].replace('"', "").replace("\r", "").replace("\n", "")
                self.send_header("Content-Disposition", f'attachment; filename="{base}"')
            self.end_headers()
            if self.command == "HEAD":
                return
            while True:
                chunk = remote.read(256 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
        finally:
            remote.close()


def main() -> None:
    global b2
    key_id, app_key = load_credentials()
    b2 = B2(key_id, app_key)
    b2.authorize()
    port = PORT
    httpd = None
    last_error: OSError | None = None
    for candidate in range(port, port + 20):
        try:
            httpd = ThreadingHTTPServer((HOST, candidate), Handler)
            port = candidate
            break
        except OSError as err:
            last_error = err
    if httpd is None:
        raise SystemExit(f"Could not bind {HOST}:{PORT} ({last_error})")
    print(f"Baile Nua data viewer  http://{HOST}:{port}/")
    print(f"Bucket                  {b2.bucket_name}")
    print("The application key stays in this process.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
