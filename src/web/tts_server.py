"""
ExecVision AI — единый сервер: статика + Яндекс SpeechKit TTS прокси.

Отдаёт фронт (index.html, landing.html) и проксирует TTS — один процесс,
один порт. За ним Caddy делает reverse_proxy на hr.axioma-ai.ru.

Запуск локально:
    python src/web/tts_server.py

На сервере:
    uvicorn src.web.tts_server:app --host 0.0.0.0 --port 8081

Маршруты:
    GET  /               — index.html (демо-кокпит)
    GET  /landing        — landing.html
    GET  /health         — JSON статус
    GET  /tts/voices     — список голосов
    POST /tts            — синтез речи → MP3
    GET  /status         — статус-страница (диагностика)
"""

import os
import httpx
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, FileResponse
from pydantic import BaseModel

# Загружаем .env из корня проекта
ROOT    = Path(__file__).parent.parent.parent
DEMO    = Path(__file__).parent / "demo"
load_dotenv(ROOT / ".env")

YANDEX_SPEECH_KEY = os.getenv("YANDEX_SPEECH_KEY", "")
YANDEX_FOLDER_ID  = os.getenv("YANDEX_FOLDER_ID", "")
TTS_URL           = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

app = FastAPI(
    title="ExecVision AI",
    description="HR-кокпит для CHRO + Яндекс SpeechKit TTS",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class TTSRequest(BaseModel):
    text: str
    voice: str = "filipp"
    speed: float = 1.0
    format: str = "mp3"
    sample_rate: int = 48000


VOICES = [
    {"id": "filipp",  "name": "Филипп",  "type": "neural",   "gender": "male",   "desc": "Нейронный · Профессиональный · Деловой"},
    {"id": "alena",   "name": "Алёна",   "type": "neural",   "gender": "female", "desc": "Нейронная · Чёткая · Уверенная"},
    {"id": "jane",    "name": "Джейн",   "type": "standard", "gender": "female", "desc": "Стандартный · Спокойный"},
    {"id": "omazh",   "name": "Омаж",    "type": "standard", "gender": "female", "desc": "Стандартный · Нейтральный"},
    {"id": "zahar",   "name": "Захар",   "type": "standard", "gender": "male",   "desc": "Стандартный · Авторитетный"},
    {"id": "ermil",   "name": "Ермил",   "type": "standard", "gender": "male",   "desc": "Стандартный · Спокойный"},
]

MAX_CHUNK = 4500


def split_text(text: str, max_len: int = MAX_CHUNK) -> list[str]:
    """Разбивает длинный текст на части по границам предложений."""
    if len(text.encode("utf-8")) <= max_len:
        return [text]
    chunks, chunk = [], ""
    sentences = []
    current = ""
    for ch in text:
        current += ch
        if ch in ".!?":
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())
    for sent in sentences:
        test = (chunk + " " + sent).strip()
        if len(test.encode("utf-8")) <= max_len:
            chunk = test
        else:
            if chunk:
                chunks.append(chunk)
            chunk = sent
    if chunk:
        chunks.append(chunk)
    return chunks if chunks else [text[:max_len]]


async def synthesize_chunk(client: httpx.AsyncClient, text: str, req: TTSRequest) -> bytes:
    response = await client.post(
        TTS_URL,
        headers={"Authorization": f"Api-Key {YANDEX_SPEECH_KEY}"},
        data={
            "text":            text,
            "lang":            "ru-RU",
            "voice":           req.voice,
            "speed":           str(req.speed),
            "format":          req.format,
            "sampleRateHertz": str(req.sample_rate),
            "folderId":        YANDEX_FOLDER_ID,
        },
        timeout=30.0,
    )
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Яндекс SpeechKit вернул {response.status_code}: {response.text[:300]}",
        )
    return response.content


# ══════════════════════════════════════════════════
#  Фронтенд — статические страницы
# ══════════════════════════════════════════════════

@app.get("/")
async def index():
    """Главная — демо-кокпит ExecVision AI."""
    return FileResponse(DEMO / "index.html", media_type="text/html")


@app.get("/landing")
async def landing():
    """Лендинг ExecVision AI."""
    return FileResponse(DEMO / "landing.html", media_type="text/html")


# ══════════════════════════════════════════════════
#  API
# ══════════════════════════════════════════════════

@app.get("/health")
async def health():
    return JSONResponse({
        "status":      "ok",
        "service":     "ExecVision AI",
        "key_present": bool(YANDEX_SPEECH_KEY),
        "folder_set":  bool(YANDEX_FOLDER_ID),
    })


@app.get("/status")
async def status_page():
    """Диагностическая страница."""
    from fastapi.responses import HTMLResponse
    key_ok = bool(YANDEX_SPEECH_KEY)
    folder_ok = bool(YANDEX_FOLDER_ID)
    c = "#10b981" if (key_ok and folder_ok) else "#ef4444"
    t = "Готов к работе" if (key_ok and folder_ok) else "Ключи не заданы"
    html = f"""<!DOCTYPE html><html lang="ru">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ExecVision AI — Статус</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}html,body{{width:100%;height:100%;background:#0a0e1a;font-family:-apple-system,Inter,sans-serif;color:#e2e8f0}}
body{{display:flex;align-items:center;justify-content:center}}
.card{{background:#111827;border:1px solid rgba(200,164,92,0.25);border-radius:16px;padding:44px 52px;text-align:center;width:440px;box-shadow:0 0 40px rgba(200,164,92,0.08)}}
h1{{color:#c8a45c;font-size:20px;font-weight:700;margin-bottom:4px}}.sub{{color:#475569;font-size:13px;margin-bottom:20px}}
.badge{{display:inline-block;background:{c}22;color:{c};border:1px solid {c}55;border-radius:20px;padding:5px 18px;font-size:13px;margin-bottom:28px}}
.ep{{background:#0d1220;border:1px solid rgba(255,255,255,0.05);border-radius:8px;padding:10px 16px;font-family:monospace;font-size:13px;color:#94a3b8;margin:6px 0;text-align:left}}
.m{{color:#c8a45c;font-weight:700}}.ok{{color:#10b981}}.err{{color:#ef4444}}
.foot{{color:#334155;font-size:12px;margin-top:24px;line-height:1.8}}
a{{color:#c8a45c;text-decoration:none}}</style></head>
<body><div class="card">
<div style="font-size:36px;margin-bottom:12px">🎙</div>
<h1>ExecVision AI</h1>
<p class="sub">HR-кокпит для CHRO · Яндекс SpeechKit</p>
<div class="badge">● {t}</div>
<div class="ep"><span class="m">GET</span>  / — <a href="/">демо-кокпит</a></div>
<div class="ep"><span class="m">GET</span>  /landing — <a href="/landing">лендинг</a></div>
<div class="ep"><span class="m">GET</span>  /health — JSON статус</div>
<div class="ep"><span class="m">GET</span>  /tts/voices — список голосов</div>
<div class="ep"><span class="m">POST</span> /tts — синтез речи → MP3</div>
<p class="foot">
  Яндекс ключ: <span class="{'ok' if key_ok else 'err'}">{'✓ задан' if key_ok else '✗ не задан'}</span>
  &nbsp;·&nbsp;
  Folder ID: <span class="{'ok' if folder_ok else 'err'}">{'✓ задан' if folder_ok else '✗ не задан'}</span>
</p></div></body></html>"""
    return HTMLResponse(html)


@app.get("/tts/voices")
async def get_voices():
    return JSONResponse({"voices": VOICES})


@app.post("/tts")
async def text_to_speech(req: TTSRequest):
    if not YANDEX_SPEECH_KEY:
        raise HTTPException(status_code=503, detail="YANDEX_SPEECH_KEY не задан в .env")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Текст не может быть пустым")

    chunks = split_text(req.text.strip())

    async with httpx.AsyncClient() as client:
        if len(chunks) == 1:
            audio_bytes = await synthesize_chunk(client, chunks[0], req)
        else:
            parts = [await synthesize_chunk(client, c, req) for c in chunks]
            audio_bytes = b"".join(parts)

    media_type = "audio/ogg" if req.format == "ogg_opus" else "audio/mpeg"
    return Response(content=audio_bytes, media_type=media_type,
                    headers={"Cache-Control": "no-cache"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("TTS_SERVER_PORT", 8081))
    host = os.getenv("TTS_SERVER_HOST", "0.0.0.0")
    print(f"\n🚀 ExecVision AI → http://localhost:{port}")
    print(f"   Кокпит:    http://localhost:{port}/")
    print(f"   Лендинг:   http://localhost:{port}/landing")
    print(f"   Статус:    http://localhost:{port}/status")
    print(f"   Яндекс ключ: {'✓ задан' if YANDEX_SPEECH_KEY else '✗ НЕ ЗАДАН'}")
    print(f"   Folder ID:   {'✓ задан' if YANDEX_FOLDER_ID else '✗ НЕ ЗАДАН'}\n")
    uvicorn.run("src.web.tts_server:app", host=host, port=port, reload=True)
