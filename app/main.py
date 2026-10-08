import asyncio
import contextlib
import hashlib
import logging
import os
import pathlib

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.db import init_db
from app.services.medicine_service import MedicineService
from app.services.shopping_service import ShoppingService
from app.services.task_service import TaskService
from app.web.routes import build_web_router

logger = logging.getLogger("home-hub.main")


def _login_page(error: str = "") -> str:
    msg = f'<p class="error">{error}</p>' if error else ""
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Home Hub — login</title>"
        "<style>body{font-family:sans-serif;background:#f4f5f7;"
        "display:flex;align-items:center;justify-content:center;height:100vh}"
        "form{background:#fff;padding:2rem;border-radius:8px;"
        "box-shadow:0 1px 4px rgba(0,0,0,.15)}input{margin:.5rem 0;padding:.5rem}"
        ".error{color:#b00}</style></head><body>"
        "<form method='post' action='/login'>"
        "<h1>Home Hub</h1>" + msg +
        "<input type='password' name='password' placeholder='Password' autofocus> "
        "<button type='submit'>Sign in</button></form></body></html>"
    )


def create_app(settings) -> FastAPI:
    """Assemble the FastAPI app: DB, services, web router, auth, lifespan."""
    os.makedirs(settings.data_dir, exist_ok=True)
    os.makedirs(os.path.join(settings.data_dir, "photos"), exist_ok=True)

    db_path = os.path.join(settings.data_dir, "hub.db")
    conn = init_db(db_path)

    services = {"medicines": MedicineService(conn),
               "shopping": ShoppingService(conn),
               "tasks": TaskService(conn)}

    # Seed the admin as an allowed bot user (idempotent). Done synchronously
    # so create_app() alone (tests, web-only mode) leaves a usable DB.
    if settings.admin_telegram_id:
        conn.execute(
            "INSERT OR IGNORE INTO allowed_users (telegram_id, name, role, lang) "
            "VALUES (?, '', 'member', 'pl')",
            (settings.admin_telegram_id,),
        )
        conn.commit()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        polling_task = None
        scheduler = None
        if settings.telegram_bot_token:
            # Lazy imports keep module import light and import-safe.
            from aiogram import Bot, Dispatcher
            from apscheduler.schedulers.asyncio import AsyncIOScheduler

            from app.ai.client import extract_medicine
            from app.bot.router import build_router
            from app.services.scheduler import schedule_jobs

            bot = Bot(settings.telegram_bot_token)
            dp = Dispatcher()
            dp.include_router(build_router(conn, settings, services))
            # Telegram client-side command menu ("/" button).
            from aiogram.types import BotCommand
            await bot.set_my_commands([
                BotCommand(command="start", description="Start / register"),
                BotCommand(command="help", description="What can I ask?"),
                BotCommand(command="lang", description="Switch language (pl/ru/uk/en)"),
            ])
            polling_task = asyncio.create_task(dp.start_polling(bot))
            app.state.bot = bot
            app.state.polling_task = polling_task

            scheduler = AsyncIOScheduler()
            schedule_jobs(conn, settings, bot, scheduler, extract_fn=extract_medicine)
            scheduler.start()
            app.state.scheduler = scheduler
        else:
            logger.warning(
                "TELEGRAM_BOT_TOKEN empty — starting in web-only mode "
                "(bot polling and scheduler disabled)"
            )
        try:
            yield
        finally:
            if polling_task is not None:
                polling_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await polling_task
            if scheduler is not None:
                scheduler.shutdown(wait=False)
            conn.close()

    app = FastAPI(lifespan=lifespan)
    app.state.conn = conn
    app.state.services = services
    app.state.data_dir = settings.data_dir

    app.include_router(
        build_web_router(services, conn, default_lang="pl",
                         data_dir=settings.data_dir, settings=settings)
    )
    app.mount(
        "/static",
        StaticFiles(directory=str(pathlib.Path(__file__).parent / "web" / "static")),
        name="static",
    )

    if settings.web_password:
        expected_cookie = hashlib.sha256(settings.web_password.encode("utf-8")).hexdigest()

        @app.get("/login", response_class=HTMLResponse)
        async def login_form(request: Request):
            if request.cookies.get("auth") == expected_cookie:
                return RedirectResponse("/", status_code=303)
            return HTMLResponse(_login_page())

        @app.post("/login")
        async def login_submit(password: str = Form("")):
            if password == settings.web_password:
                resp = RedirectResponse("/", status_code=303)
                resp.set_cookie("auth", expected_cookie, httponly=True,
                                samesite="lax", max_age=30 * 86400)
                return resp
            return HTMLResponse(_login_page("Wrong password."), status_code=401)

        @app.middleware("http")
        async def password_guard(request: Request, call_next):
            path = request.url.path
            if (path == "/login" or path.startswith("/static/")
                    or request.cookies.get("auth") == expected_cookie):
                return await call_next(request)
            return RedirectResponse("/login", status_code=303)

    return app


app = create_app(load_settings())
