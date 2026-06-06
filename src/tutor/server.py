"""Thin Python proxy: serves static frontend + proxies chat to DeepSeek API.

The browser never calls DeepSeek directly — the API key stays within this
process.  Textbook data is loaded once at startup.  Tool-use (show_toc /
get_page) is executed server-side from in-memory textbook data.
"""

from __future__ import annotations

import json
import logging
import queue
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

# Allow running as `python3 src/tutor/server.py` from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import requests

from src.tutor.compaction import compact_history
from src.tutor.system_prompt import get_system_prompt
from src.tutor.review import execute_review
from src.tutor.common import (
    DEEPSEEK_URL, ANTHROPIC_VERSION, MODEL, MAX_TOKENS, MAX_TOOL_ITERATIONS,
    make_tools, execute_tools,
)

logger = logging.getLogger(__name__)

STATIC_ROOT = Path(__file__).resolve().parent.parent / "frontend" / "legacy"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
DEFAULT_TEXTBOOK_PATH = PROJECT_ROOT / "data" / "textbook" / "textbook.json"

# ── Review SSE queues (thread-safe) ──────────────────────────────────────

_review_queues: dict[str, queue.Queue] = {}
_review_queues_lock = threading.Lock()


def _push_review_event(request_id: str, status: dict) -> None:
    """Push a status update to the SSE queue for *request_id*."""
    with _review_queues_lock:
        q = _review_queues.get(request_id)
        if q:
            q.put(status)


def _get_or_create_review_queue(request_id: str) -> queue.Queue:
    with _review_queues_lock:
        q = _review_queues.get(request_id)
        if q is None:
            q = queue.Queue()
            _review_queues[request_id] = q
        return q


def _remove_review_queue(request_id: str) -> None:
    with _review_queues_lock:
        _review_queues.pop(request_id, None)

# ── Textbook loading ────────────────────────────────────────────────────────


def load_textbook(path: str) -> dict:
    """Load textbook.json into memory, with a _page_index for fast lookups."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["_page_index"] = {(p["part"], p["pdf_page"]): p for p in data["pages"]}
    return data


# ── Anthropic tool definitions ──────────────────────────────────────────────


# ── Chat request building ───────────────────────────────────────────────────


def build_chat_request(
    api_key: str,
    messages: list[dict],
    progress_context: str = "",
    current_task: str = "",
) -> tuple[str, dict, dict]:
    """Return (url, headers, body) for a DeepSeek Messages API call."""
    url = DEEPSEEK_URL
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": ANTHROPIC_VERSION,
    }
    system = get_system_prompt(
        progress_context=progress_context,
        current_task=current_task,
    )
    body = {
        "model": MODEL,
        "system": system,
        "messages": messages,
        "tools": make_tools(),
        "stream": True,
        "max_tokens": MAX_TOKENS,
    }
    return url, headers, body


# ── Tool-use loop ───────────────────────────────────────────────────────────


def run_tool_use_loop(
    api_key: str,
    messages: list[dict],
    tools: list[dict],
    textbook: dict,
    max_iterations: int = MAX_TOOL_ITERATIONS,
    progress_context: str = "",
    current_task: str = "",
) -> tuple[dict, dict]:
    """Send messages to DeepSeek, handling tool-use callbacks up to *max_iterations*.

    Returns (final_message, total_usage) where total_usage aggregates input/output
    tokens across all iterations of the tool-use loop.
    """
    url = DEEPSEEK_URL
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": ANTHROPIC_VERSION,
    }

    system_prompt = get_system_prompt(
        progress_context=progress_context,
        current_task=current_task,
    )

    total_usage = {"input_tokens": 0, "output_tokens": 0}

    for _ in range(max_iterations):
        # Compact before each call
        compacted = compact_history(messages)

        body = {
            "model": MODEL,
            "system": system_prompt,
            "messages": compacted,
            "tools": tools,
            "stream": False,
            "max_tokens": MAX_TOKENS,
        }

        resp = requests.post(url, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        msg = resp.json()

        # Accumulate usage from this API call
        usage = msg.get("usage", {})
        total_usage["input_tokens"] += usage.get("input_tokens", 0)
        total_usage["output_tokens"] += usage.get("output_tokens", 0)

        if msg.get("stop_reason") != "tool_use":
            return msg, total_usage

        # Extract tool_use blocks
        tool_calls = [c for c in msg.get("content", []) if c.get("type") == "tool_use"]
        if not tool_calls:
            return msg, total_usage

        # Execute tools
        tool_results = execute_tools(tool_calls, textbook)

        # Append the assistant message and tool results to the conversation
        messages.append({"role": "assistant", "content": msg.get("content", [])})
        messages.append({"role": "user", "content": tool_results})

    # Ran out of iterations — return last response
    return msg, total_usage


# ── HTTP handler ────────────────────────────────────────────────────────────


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in its own thread."""
    daemon_threads = True


class TutorHandler(BaseHTTPRequestHandler):
    """Serves static files, /api/toc, /api/chat, and /api/review."""

    textbook_path = str(DEFAULT_TEXTBOOK_PATH)
    _textbook: dict | None = None  # class-level cache

    @classmethod
    def get_textbook(cls) -> dict:
        if cls._textbook is None:
            cls._textbook = load_textbook(cls.textbook_path)
        return cls._textbook

    def log_message(self, format, *args):
        logger.info("%s - %s", self.client_address[0], format % args)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/toc":
            self._serve_toc()
        elif path.startswith("/api/review/stream/"):
            self._serve_review_stream(path)
        else:
            self._serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/chat":
            self._handle_chat()
        elif parsed.path == "/api/review":
            self._handle_review()
        else:
            self.send_error(404)

    # ── API handlers ────────────────────────────────────────────────────

    def _serve_toc(self):
        tb = self.get_textbook()
        body = json.dumps(tb["toc"], ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_review_stream(self, path: str):
        """GET /api/review/stream/{request_id} — SSE stream of status transitions."""
        request_id = path.rsplit("/", 1)[-1]
        if len(request_id) != 12 or not all(c in '0123456789abcdef' for c in request_id):
            self.send_error(400, "Invalid request_id format")
            return
        q = _get_or_create_review_queue(request_id)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            while True:
                try:
                    status = q.get(timeout=300)  # 5 min timeout
                except queue.Empty:
                    break

                data = json.dumps(status, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()

                if status.get("step") in ("done", "error"):
                    break
            else:
                _remove_review_queue(request_id)
        except (BrokenPipeError, ConnectionResetError):
            pass  # keep queue alive for reconnection

    def _handle_chat(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        payload = json.loads(raw)

        api_key = payload.get("apiKey", "")
        messages = payload.get("messages", [])
        progress_context = payload.get("progressContext", "")
        current_task = payload.get("currentTask", "")

        if not api_key:
            self.send_error(400, "apiKey is required")
            return

        tools = make_tools()
        tb = self.get_textbook()

        try:
            final_msg, usage = run_tool_use_loop(
                api_key, messages, tools, tb,
                progress_context=progress_context,
                current_task=current_task,
            )
        except requests.HTTPError as e:
            self.send_error(e.response.status_code if e.response else 502,
                            f"Upstream error: {e}")
            return
        except requests.RequestException as e:
            self.send_error(502, f"Upstream error: {e}")
            return

        # For plain (non-streaming) response, return the full message
        content = final_msg.get("content", [])
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        response_body = json.dumps({
            "content": content,
            "stop_reason": final_msg.get("stop_reason"),
            "usage": usage,
        }, ensure_ascii=False)
        self.wfile.write(response_body.encode("utf-8"))

    def _handle_review(self):
        """POST /api/review — accept review request, process in background."""
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        payload = json.loads(raw)

        api_key = payload.get("apiKey", "")
        tasks = payload.get("tasks", [])
        variant_num = payload.get("variantNum", 0)
        if not isinstance(variant_num, int) or variant_num < 1 or variant_num > 15:
            variant_num = 0
        progress_context = payload.get("progressContext", "")

        if not api_key:
            self.send_error(400, "apiKey is required")
            return
        if not tasks:
            self.send_error(400, "tasks array is required")
            return

        request_id = uuid.uuid4().hex[:12]
        tb = self.get_textbook()
        _get_or_create_review_queue(request_id)

        body = json.dumps(
            {"request_id": request_id, "status": "accepted"},
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(202)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

        def on_status(s):
            _push_review_event(request_id, s)

        def run_review():
            on_status({"step": "starting", "message": "Начинаю проверку..."})
            try:
                result = execute_review(
                    api_key, tasks, variant_num, tb,
                    progress_context=progress_context,
                    on_status=on_status,
                )
                on_status({
                    "step": "done",
                    "reviews": result.get("reviews", []),
                    "usage": result.get("usage", {}),
                })
            except requests.HTTPError as e:
                status_code = e.response.status_code if e.response else 502
                on_status({
                    "step": "error",
                    "message": f"Ошибка API ({status_code}): {e}",
                })
            except requests.RequestException as e:
                on_status({
                    "step": "error",
                    "message": f"Сетевая ошибка: {e}",
                })
            except Exception as e:
                on_status({
                    "step": "error",
                    "message": f"Ошибка: {e}",
                })
        threading.Thread(target=run_review, daemon=True).start()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── Static file serving ──────────────────────────────────────────────

    def _serve_static(self, path: str):
        if path == "/" or path == "":
            path = "/index.html"

        # Data files are served from DATA_ROOT only
        if path.startswith("/data/"):
            file_path = DATA_ROOT / path[len("/data/"):]
        else:
            file_path = STATIC_ROOT / path.lstrip("/")

        if not file_path.is_file():
            self.send_error(404)
            return

        # Path traversal guard: ensure resolved path stays within its root
        resolved = file_path.resolve()
        if path.startswith("/data/"):
            if not str(resolved).startswith(str(DATA_ROOT.resolve())):
                self.send_error(403)
                return
        else:
            if not str(resolved).startswith(str(STATIC_ROOT.resolve())):
                self.send_error(403)
                return

        content_type = self._guess_mime(file_path.suffix)
        body = file_path.read_bytes()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _guess_mime(suffix: str) -> str:
        return {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }.get(suffix, "application/octet-stream")


# ── Entry point ─────────────────────────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Tutor proxy server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--textbook", type=str, default=str(DEFAULT_TEXTBOOK_PATH))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    TutorHandler.textbook_path = args.textbook

    server = ThreadingHTTPServer(("0.0.0.0", args.port), TutorHandler)
    logger.info("Tutor server listening on http://0.0.0.0:%d", args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
