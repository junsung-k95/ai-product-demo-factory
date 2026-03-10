"""FastAPI routes — HTTP + WebSocket endpoints for demo generation."""

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from demo_factory.agents.demo_factory_agent import DemoFactoryAgent
from demo_factory.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class GenerateRequest(BaseModel):
    rfp: str
    demo_id: str | None = None


# ── WebSocket endpoint (streaming) ──────────────────────────────────────────


@router.websocket("/ws/generate")
async def ws_generate(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time demo generation.

    Client sends: {"rfp": "Build a logistics dashboard..."}
    Server streams: {"type": "log"|"result"|"error"|"session", "content": "...", ...}
    """
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        payload = json.loads(data)
        rfp = payload.get("rfp", "").strip()

        if not rfp:
            await websocket.send_json({"type": "error", "content": "rfp is required"})
            return

        demo_id = payload.get("demo_id") or str(uuid.uuid4())[:8]
        agent = DemoFactoryAgent()

        await websocket.send_json(
            {
                "type": "log",
                "content": f"Starting generation for demo: {demo_id}",
                "demo_id": demo_id,
            }
        )

        async for progress in agent.generate(rfp=rfp, demo_id=demo_id):
            await websocket.send_json(
                {
                    "type": progress.type,
                    "content": progress.content,
                    "demo_id": progress.demo_id,
                    "session_id": progress.session_id,
                    "timestamp": progress.timestamp,
                }
            )

        await websocket.send_json({"type": "done", "demo_id": demo_id})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.exception("WebSocket error")
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass


# ── REST endpoint (non-streaming) ───────────────────────────────────────────


@router.post("/generate")
async def generate_demo(request: GenerateRequest) -> dict:
    """
    Generate a demo synchronously (collects all output, then returns).
    For large RFPs, prefer the WebSocket endpoint.
    """
    agent = DemoFactoryAgent()
    logs: list[str] = []
    result_content: str = ""
    session_id: str | None = None

    async for progress in agent.generate(rfp=request.rfp, demo_id=request.demo_id):
        logs.append(f"[{progress.type}] {progress.content}")
        if progress.type == "result":
            result_content = progress.content
        if progress.session_id:
            session_id = progress.session_id

    demo_id = request.demo_id or "unknown"
    demo_path = Path(settings.demos_output_dir) / demo_id

    return {
        "demo_id": demo_id,
        "status": "success",
        "demo_path": str(demo_path),
        "session_id": session_id,
        "result": result_content,
        "log": logs,
    }


# ── Demo file serving ────────────────────────────────────────────────────────


@router.get("/demos/{demo_id}/{file_path:path}")
async def serve_demo_file(demo_id: str, file_path: str) -> FileResponse:
    """Serve a file from a generated demo directory."""
    demo_dir = Path(settings.demos_output_dir) / demo_id
    full_path = (demo_dir / file_path).resolve()

    # Security: prevent path traversal
    if not str(full_path).startswith(str(demo_dir.resolve())):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Access denied")

    if not full_path.exists():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path)


@router.get("/demos/{demo_id}")
async def serve_demo(demo_id: str) -> FileResponse:
    """Serve index.html for a generated demo."""
    index = Path(settings.demos_output_dir) / demo_id / "index.html"
    if not index.exists():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Demo not found")
    return FileResponse(index)


@router.get("/demos")
async def list_demos() -> dict:
    """List all generated demos."""
    output_dir = Path(settings.demos_output_dir)
    if not output_dir.exists():
        return {"demos": []}

    demos = []
    for demo_dir in sorted(output_dir.iterdir()):
        if demo_dir.is_dir():
            files = [p.name for p in demo_dir.iterdir() if p.is_file()]
            demos.append(
                {
                    "demo_id": demo_dir.name,
                    "has_index": "index.html" in files,
                    "files": files,
                }
            )

    return {"demos": demos}


# ── Health check ─────────────────────────────────────────────────────────────


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ── Demo UI ───────────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Demo Factory</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-950 text-white min-h-screen flex flex-col items-center justify-center p-8">
  <div class="w-full max-w-3xl">
    <h1 class="text-4xl font-bold mb-2 text-center bg-gradient-to-r from-purple-400 to-cyan-400 bg-clip-text text-transparent">
      AI Demo Factory
    </h1>
    <p class="text-gray-400 text-center mb-8">RFP를 입력하면 Claude Code가 자동으로 데모를 빌드합니다</p>

    <textarea id="rfp" rows="8"
      class="w-full bg-gray-900 border border-gray-700 rounded-xl p-4 text-sm text-gray-100 resize-none focus:outline-none focus:border-purple-500 mb-4"
      placeholder="RFP를 입력하세요. 예) 실시간 배송 추적 대시보드, AI 경로 최적화 기능 포함. 지도, 차트, KPI 카드 포함..."></textarea>

    <button onclick="generate()"
      class="w-full py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-purple-600 to-cyan-600 hover:opacity-90 transition mb-6">
      데모 생성하기 ✨
    </button>

    <div id="log" class="hidden bg-gray-900 border border-gray-800 rounded-xl p-4 font-mono text-xs text-green-400 max-h-96 overflow-y-auto whitespace-pre-wrap"></div>
    <div id="result" class="hidden mt-4"></div>
  </div>

  <script>
    function generate() {
      const rfp = document.getElementById('rfp').value.trim();
      if (!rfp) return alert('RFP를 입력해주세요');

      const log = document.getElementById('log');
      const result = document.getElementById('result');
      log.classList.remove('hidden');
      log.textContent = '';
      result.classList.add('hidden');

      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${location.host}/ws/generate`);

      ws.onopen = () => ws.send(JSON.stringify({ rfp }));

      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        log.textContent += `[${msg.type}] ${msg.content}\\n`;
        log.scrollTop = log.scrollHeight;

        if (msg.type === 'done') {
          result.innerHTML = `<a href="/demos/${msg.demo_id}" target="_blank"
            class="block w-full py-3 rounded-xl text-center font-semibold bg-green-600 hover:bg-green-500 transition">
            데모 열기 →
          </a>`;
          result.classList.remove('hidden');
        }
      };

      ws.onerror = () => { log.textContent += '\\n[error] WebSocket 연결 오류\\n'; };
    }
  </script>
</body>
</html>"""
