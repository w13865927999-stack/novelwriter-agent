"""Run the NovelWriter Agent FastAPI web app."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.getenv("NOVELWRITER_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("NOVELWRITER_WEB_PORT", "8000"))
    reload = os.getenv("NOVELWRITER_WEB_RELOAD", "true").lower() in {"1", "true", "yes", "on"}
    uvicorn.run("novelwriter.web:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()

