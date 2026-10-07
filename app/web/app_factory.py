import os

from fastapi import FastAPI

from app.web.routes import build_web_router


def create_test_app(conn, data_dir: str = "."):
    os.makedirs(os.path.join(data_dir, "photos"), exist_ok=True)
    app = FastAPI()
    app.state.data_dir = data_dir
    app.include_router(
        build_web_router({"medicines": None}, conn, default_lang="en", data_dir=data_dir)
    )
    return app
