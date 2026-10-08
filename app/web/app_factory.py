import os
import pathlib

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.web.routes import build_web_router


def create_test_app(conn, data_dir: str = ".", settings=None):
    os.makedirs(os.path.join(data_dir, "photos"), exist_ok=True)
    app = FastAPI()
    app.state.data_dir = data_dir
    app.include_router(
        build_web_router({"medicines": None, "shopping": None}, conn, default_lang="en",
                         data_dir=data_dir, settings=settings)
    )
    app.mount("/static", StaticFiles(directory=str(pathlib.Path(__file__).parent / "static")), name="static")
    return app
