"""
Ollama ExApp - Nextcloud External Application wrapper for Ollama LLM server.

This module provides the lifecycle endpoints required by Nextcloud's AppAPI
to manage the Ollama container as an external application.
"""

import os
import json
import time
import subprocess
import threading
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse


# Configuration from environment
APP_ID = os.environ.get("APP_ID", "ollama")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_SECRET = os.environ.get("APP_SECRET", "")
APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "9000"))
NEXTCLOUD_URL = os.environ.get("NEXTCLOUD_URL", "http://nextcloud")

# Ollama configuration
OLLAMA_PORT = 11434
OLLAMA_PROCESS = None
INIT_PROGRESS = 0

# Default model to pull on startup
DEFAULT_MODEL = os.environ.get("OLLAMA_DEFAULT_MODEL", "llama3.2:3b")


def get_nc_headers() -> dict:
    """Get headers for Nextcloud API calls."""
    import base64
    auth = base64.b64encode(f":{APP_SECRET}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": auth,
    }


async def report_status(progress: int):
    """Report initialization progress to Nextcloud."""
    global INIT_PROGRESS
    INIT_PROGRESS = progress
    try:
        async with httpx.AsyncClient() as client:
            await client.put(
                f"{NEXTCLOUD_URL}/ocs/v1.php/apps/app_api/apps/status",
                headers=get_nc_headers(),
                json={"progress": progress},
                timeout=10,
            )
    except Exception as e:
        print(f"Failed to report status: {e}")


def start_ollama():
    """Start the Ollama server process."""
    global OLLAMA_PROCESS

    env = os.environ.copy()

    # Configure Ollama
    env["OLLAMA_HOST"] = f"0.0.0.0:{OLLAMA_PORT}"

    # Use persistent storage for models
    storage_path = env.get("APP_PERSISTENT_STORAGE", "/data")
    env["OLLAMA_MODELS"] = f"{storage_path}/models"
    os.makedirs(env["OLLAMA_MODELS"], exist_ok=True)

    # Performance settings
    env.setdefault("OLLAMA_NUM_PARALLEL", "2")
    env.setdefault("OLLAMA_KEEP_ALIVE", "15m")
    env.setdefault("OLLAMA_MAX_LOADED_MODELS", "1")

    # Start Ollama serve
    OLLAMA_PROCESS = subprocess.Popen(
        ["ollama", "serve"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Log output in background
    def log_output():
        for line in OLLAMA_PROCESS.stdout:
            print(f"[ollama] {line.decode().strip()}")

    threading.Thread(target=log_output, daemon=True).start()


async def wait_for_ollama(timeout: int = 60) -> bool:
    """Wait for Ollama to become healthy."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"http://localhost:{OLLAMA_PORT}/api/tags", timeout=5)
                if resp.status_code == 200:
                    return True
        except Exception:
            pass
        await report_status(int((time.time() - start) / timeout * 50))
        time.sleep(2)
    return False


async def pull_default_model():
    """Pull the default model if not already present."""
    try:
        async with httpx.AsyncClient() as client:
            # Check if model exists
            resp = await client.get(f"http://localhost:{OLLAMA_PORT}/api/tags", timeout=10)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                if any(DEFAULT_MODEL in name for name in model_names):
                    print(f"Model {DEFAULT_MODEL} already present")
                    return True

            # Pull the model
            print(f"Pulling default model: {DEFAULT_MODEL}")
            resp = await client.post(
                f"http://localhost:{OLLAMA_PORT}/api/pull",
                json={"name": DEFAULT_MODEL, "stream": False},
                timeout=600,  # 10 minutes for model download
            )
            return resp.status_code == 200
    except Exception as e:
        print(f"Failed to pull model: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print(f"Starting Ollama ExApp v{APP_VERSION}")
    yield
    # Cleanup
    if OLLAMA_PROCESS:
        OLLAMA_PROCESS.terminate()
        OLLAMA_PROCESS.wait(timeout=10)


app = FastAPI(lifespan=lifespan)


@app.get("/heartbeat")
async def heartbeat():
    """Health check endpoint required by AppAPI."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://localhost:{OLLAMA_PORT}/api/tags", timeout=5)
            if resp.status_code == 200:
                return JSONResponse({"status": "ok"})
    except Exception:
        pass
    return JSONResponse({"status": "error"}, status_code=503)


@app.post("/init")
async def init(background_tasks: BackgroundTasks):
    """Initialization endpoint required by AppAPI."""

    async def do_init():
        await report_status(0)

        # Start Ollama
        start_ollama()
        await report_status(10)

        # Wait for Ollama to be ready
        if not await wait_for_ollama():
            print("Ollama failed to start within timeout")
            return

        await report_status(50)

        # Pull default model
        if DEFAULT_MODEL:
            await pull_default_model()

        await report_status(100)
        print("Ollama initialization complete")

    background_tasks.add_task(do_init)
    return JSONResponse({"status": "init_started"})


@app.put("/enabled")
async def enabled(request: Request):
    """Enable/disable endpoint required by AppAPI."""
    data = await request.json()
    is_enabled = data.get("enabled", False)

    if is_enabled:
        if not OLLAMA_PROCESS or OLLAMA_PROCESS.poll() is not None:
            start_ollama()
    else:
        if OLLAMA_PROCESS and OLLAMA_PROCESS.poll() is None:
            OLLAMA_PROCESS.terminate()

    return JSONResponse({"status": "ok"})


# Proxy all other requests to Ollama
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy(request: Request, path: str):
    """Proxy requests to Ollama."""
    try:
        url = f"http://localhost:{OLLAMA_PORT}/{path}"
        body = await request.body()

        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "connection", "transfer-encoding")
        }

        # Check if this is a streaming request
        is_streaming = False
        if body:
            try:
                data = json.loads(body)
                is_streaming = data.get("stream", False)
            except json.JSONDecodeError:
                pass

        async with httpx.AsyncClient() as client:
            if is_streaming:
                # Handle streaming responses
                async def stream_response():
                    async with client.stream(
                        method=request.method,
                        url=url,
                        content=body,
                        headers=headers,
                        params=request.query_params,
                        timeout=600,
                    ) as resp:
                        async for chunk in resp.aiter_bytes():
                            yield chunk

                return StreamingResponse(
                    stream_response(),
                    media_type="application/x-ndjson",
                )
            else:
                # Regular request
                resp = await client.request(
                    method=request.method,
                    url=url,
                    content=body,
                    headers=headers,
                    params=request.query_params,
                    timeout=600,
                )

                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    headers=dict(resp.headers),
                )
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=502,
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)
