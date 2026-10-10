"""Web UI routes: medicine list, detail view + actions, add flow with
camera capture and AI extraction."""
import calendar
import dataclasses
import datetime
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile

from app.ai.client import extract_medicine, suggest_by_name
from app.i18n import LANGS, t
from app.services.medicine_service import MedicineService
from app.services.shopping_service import ShoppingService
from app.services.task_service import TaskService

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["LANGS"] = LANGS


def _shortdate(value):
    """2027-03 -> 03/2027, 2027-03-15 -> 15/03/2027, otherwise the raw value."""
    if not value:
        return value
    parts = str(value).split("-")
    if len(parts) == 2 and len(parts[0]) == 4:
        return f"{parts[1]}/{parts[0]}"
    if len(parts) == 3 and len(parts[0]) == 4:
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return value


templates.env.filters["shortdate"] = _shortdate

MAX_IMAGES = 2
MAX_IMAGE_BYTES = 8 * 1024 * 1024

# MedicineExtract fields that /extract echoes back to the browser.
_EXTRACT_FIELDS = (
    "name", "active_ingredient", "form",
    "dosage_pl", "dosage_ru", "dosage_uk", "dosage_en",
    "description_pl", "description_ru", "description_uk", "description_en",
    "expiry_date", "multiple",
)

# Form fields preserved when /add re-renders after a validation error.
_FORM_FIELDS = (
    "name", "active_ingredient", "form",
    "dosage_pl", "dosage_ru", "dosage_uk", "dosage_en",
    "description_pl", "description_ru", "description_uk", "description_en",
    "expiry_date", "quantity", "unit", "low_stock_threshold",
    "discard_after_days", "photo_saved", "ai_extracted", "ai_failed",
)

UNITS = ("pieces", "packages", "ml", "mg")
templates.env.globals["UNITS"] = UNITS


def _days_until(date_str) -> int | None:
    """Days from today until the given ISO date; None if unset/invalid."""
    if not date_str:
        return None
    try:
        d = datetime.date.fromisoformat(date_str)
    except ValueError:
        return None
    return (d - datetime.date.today()).days


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_expiry(raw: str) -> str | None:
    """Accept full dates (2027-02-28) or month-year short forms (02/2027,
    2/2027, 2027-02, 02.2027) — month-year means the LAST day of that month.
    Returns normalized YYYY-MM-DD or None if invalid."""
    raw = (raw or "").strip()
    if not raw:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        try:
            datetime.date(int(m[1]), int(m[2]), int(m[3]))
            return raw
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})[.,/](\d{4})", raw)  # MM/YYYY, MM.YYYY or MM,YYYY
    if m:
        month, year = int(m[1]), int(m[2])
    else:
        m = re.fullmatch(r"(\d{4})-(\d{1,2})", raw)  # YYYY-MM
        if not m:
            return None
        year, month = int(m[1]), int(m[2])
    if not 1 <= month <= 12:
        return None
    return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"


def build_web_router(services, conn, default_lang: str = "en", data_dir: str = ".",
                     settings=None) -> APIRouter:
    router = APIRouter()

    def _svc() -> MedicineService:
        """Real service when injected (Task 13), lazy fallback for tests."""
        return services.get("medicines") or MedicineService(conn)

    def _shop() -> ShoppingService:
        """Real service when injected, lazy fallback for tests."""
        return services.get("shopping") or ShoppingService(conn)

    def page_context(request: Request, **extra):
        lang = request.cookies.get("lang", default_lang)
        T = lambda key, **kw: t(lang, key, **kw)  # noqa: E731
        ctx = {"request": request, "T": T, "lang": lang}
        ctx.update(extra)
        return ctx

    @router.get("/")
    async def list_view(request: Request, q: str = ""):
        rows = [dict(r) for r in _svc().list_all()]
        if q:
            needle = q.lower()
            rows = [r for r in rows if needle in r["name"].lower()]
        expiring, others = [], []
        for r in rows:
            days = _days_until(r["expiry_date"])
            r["days_until"] = days
            if days is not None and 0 <= days <= 7:
                expiring.append(r)
            else:
                others.append(r)
        return templates.TemplateResponse(
            request, "list.html",
            page_context(request, q=q, expiring=expiring, others=others))

    @router.get("/medicine/{medicine_id}")
    async def detail_view(request: Request, medicine_id: int):
        row = _svc().get(medicine_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Medicine not found")
        m = dict(row)
        lang = request.cookies.get("lang", default_lang)
        dosage = m.get(f"dosage_{lang}") or m.get("dosage_en") or ""
        description = m.get(f"description_{lang}") or m.get("description_en") or ""
        discard_date = None
        if m["opened_at"] and m["discard_after_days"]:
            try:
                opened = datetime.date.fromisoformat(m["opened_at"])
                discard_date = (opened + datetime.timedelta(
                    days=m["discard_after_days"])).isoformat()
            except ValueError:
                pass
        return templates.TemplateResponse(
            request, "detail.html",
            page_context(request, m=m, dosage=dosage, description=description,
                         days_until=_days_until(m["expiry_date"]),
                         discard_date=discard_date))

    @router.api_route("/lang/{code}", methods=["GET", "POST"])
    async def set_lang(code: str, request: Request):
        if code not in LANGS:
            raise HTTPException(status_code=404, detail="Unknown language")
        # Return to the page the user came from (path + query), else home.
        referer = request.headers.get("referer")
        parsed = urlparse(referer or "")
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        response = RedirectResponse(target, status_code=303)
        response.set_cookie("lang", code)
        return response

    # ---- Add flow -------------------------------------------------

    @router.get("/add")
    async def add_form(request: Request):
        return templates.TemplateResponse(
            request, "add.html",
            page_context(request, values={}, error_expiry=False, units=UNITS))

    @router.post("/extract")
    async def extract(request: Request):
        form = await request.form()
        uploads = [u for u in form.getlist("images") if isinstance(u, UploadFile)]
        uploads = [u for u in uploads
                   if (u.content_type or "").startswith("image/")][:MAX_IMAGES]
        blobs = []
        for u in uploads:
            data = await u.read()
            if len(data) <= MAX_IMAGE_BYTES:
                blobs.append(data)
        if not blobs:
            return JSONResponse({"error": True})
        try:
            ext = await extract_medicine(settings, blobs)
        except Exception:
            # No settings configured (or extraction crashed) — treat as AI
            # failure; the photo is still saved below for the retry job.
            ext = None
        if ext is None:
            # AI failed, but keep the photo so the retry job can extract it
            # later: /add stores it as ai_status='needs_ai_data'.
            photo_dir = Path(data_dir) / "photos"
            photo_dir.mkdir(parents=True, exist_ok=True)
            rel = f"photos/{uuid.uuid4().hex}.jpg"
            (Path(data_dir) / rel).write_bytes(blobs[0])
            return JSONResponse({"error": True, "photo_saved": rel})
        if getattr(ext, "multiple", False):
            # Several packages in the shot: ask for a single box / barcode.
            return JSONResponse({"multiple": True})
        try:
            payload = dataclasses.asdict(ext)
        except TypeError:
            # Non-dataclass payloads (test doubles).
            payload = {f: getattr(ext, f, None) for f in _EXTRACT_FIELDS}
        photo_dir = Path(data_dir) / "photos"
        photo_dir.mkdir(parents=True, exist_ok=True)
        rel = f"photos/{uuid.uuid4().hex}.jpg"
        (Path(data_dir) / rel).write_bytes(blobs[0])
        payload["photo_saved"] = rel
        return JSONResponse(payload)

    @router.post("/suggest")
    async def suggest(request: Request):
        form = await request.form()
        name = (form.get("name") or "").strip()
        if settings is None or not name:
            return JSONResponse({"error": True})
        ext = await suggest_by_name(settings, name)
        if ext is None or getattr(ext, "multiple", False) or not getattr(ext, "name", ""):
            return JSONResponse({"error": True})
        try:
            payload = dataclasses.asdict(ext)
        except TypeError:
            # Non-dataclass payloads (test doubles).
            payload = {f: getattr(ext, f, None) for f in _EXTRACT_FIELDS}
        return JSONResponse(payload)

    @router.post("/add")
    async def add_save(request: Request):
        form = await request.form()
        no_expiry = form.get("no_expiry")
        expiry = None if no_expiry else _parse_expiry(
            form.get("expiry_date") or "")
        if not expiry and not no_expiry:
            values = {k: form.get(k, "") for k in _FORM_FIELDS}
            return templates.TemplateResponse(
                request, "add.html",
                page_context(request, values=values, error_expiry=True,
                             units=UNITS, no_expiry=no_expiry),
                status_code=400)
        photo_saved = (form.get("photo_saved") or "").strip()
        ai_failed = form.get("ai_failed") == "1"
        ai_status = "needs_ai_data" if (ai_failed and photo_saved) else "ok"
        discard_after_days = _to_int(form.get("discard_after_days"))
        mid = _svc().add({
            "name": (form.get("name") or "").strip(),
            "active_ingredient": (form.get("active_ingredient") or "").strip(),
            "form": (form.get("form") or "").strip(),
            "dosage_pl": (form.get("dosage_pl") or "").strip(),
            "dosage_ru": (form.get("dosage_ru") or "").strip(),
            "dosage_uk": (form.get("dosage_uk") or "").strip(),
            "dosage_en": (form.get("dosage_en") or "").strip(),
            "description_pl": (form.get("description_pl") or "").strip(),
            "description_ru": (form.get("description_ru") or "").strip(),
            "description_uk": (form.get("description_uk") or "").strip(),
            "description_en": (form.get("description_en") or "").strip(),
            "expiry_date": expiry,
            "quantity": _to_float(form.get("quantity"), 0.0),
            "unit": (form.get("unit") or "pieces").strip(),
            "low_stock_threshold": _to_int(form.get("low_stock_threshold"), 3) or 0,
            "discard_after_days": discard_after_days,
            "photo_path": photo_saved,
            "ai_status": ai_status,
        })
        return RedirectResponse(f"/medicine/{mid}", status_code=303)

    # ---- Shopping list ---------------------------------------------

    @router.get("/shopping")
    async def shopping_view(request: Request):
        svc = _shop()
        return templates.TemplateResponse(
            request, "shopping.html",
            page_context(request, unbought=svc.list_unbought(),
                         bought=svc.list_bought(20),
                         activity=svc.recent_activity(15)))

    @router.post("/shopping/add")
    async def shopping_add(request: Request):
        form = await request.form()
        names = (form.get("names") or "").split(",")
        _shop().add_items(names, "web")
        return RedirectResponse("/shopping", status_code=303)

    @router.post("/shopping/check/{item_id}")
    async def shopping_check(item_id: int):
        svc = _shop()
        row = conn.execute(
            "SELECT bought FROM shopping_items WHERE id=?", (item_id,)).fetchone()
        if row is not None:
            if row["bought"]:
                svc.uncheck(item_id)
            else:
                svc.check_off(str(item_id), "web")
        return RedirectResponse("/shopping", status_code=303)

    @router.post("/shopping/clear")
    async def shopping_clear():
        _shop().clear_bought()
        return RedirectResponse("/shopping", status_code=303)

    # ---- Family tasks ----------------------------------------------

    def _tasks() -> TaskService:
        """Real service when injected, lazy fallback for tests."""
        return services.get("tasks") or TaskService(conn)

    def _members():
        return conn.execute(
            "SELECT telegram_id, name FROM allowed_users WHERE role='member' "
            "ORDER BY name").fetchall()

    def _tasks_ctx(request: Request, **extra):
        ctx = {"open": _tasks().list_open(), "done": _tasks().list_done(20),
               "members": _members(), "values": {},
               "today": datetime.date.today().isoformat()}
        ctx.update(extra)
        return page_context(request, **ctx)

    @router.get("/tasks")
    async def tasks_view(request: Request):
        return templates.TemplateResponse(request, "tasks.html",
                                          _tasks_ctx(request))

    @router.post("/tasks/add")
    async def tasks_add(request: Request):
        form = await request.form()
        title = (form.get("title") or "").strip()
        due = _parse_expiry(form.get("due_date") or "")
        if not title or (not due and (form.get("due_date") or "").strip()):
            return templates.TemplateResponse(
                request, "tasks.html",
                _tasks_ctx(request, values={"title": title, "due_date": due},
                           error_task=True),
                status_code=400)
        assignee_id = assignee_name = None
        member_id = _to_int(form.get("assignee"))
        if member_id is not None:
            row = conn.execute(
                "SELECT name FROM allowed_users WHERE telegram_id=? "
                "AND role='member'", (member_id,)).fetchone()
            if row is not None:
                assignee_id, assignee_name = member_id, row["name"]
        _tasks().add_task(title, "web", due or None, assignee_id, assignee_name)
        return RedirectResponse("/tasks", status_code=303)

    @router.post("/tasks/complete/{task_id}")
    async def tasks_complete(task_id: int):
        _tasks().toggle(task_id, "web")
        return RedirectResponse("/tasks", status_code=303)

    # ---- Detail actions -------------------------------------------

    # ---- Edit ------------------------------------------------------

    @router.get("/medicine/{medicine_id}/edit")
    async def edit_form(request: Request, medicine_id: int):
        row = _svc().get(medicine_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Medicine not found")
        m = dict(row)
        return templates.TemplateResponse(
            request, "edit.html",
            page_context(request, values=m, units=UNITS, error_expiry=False))

    @router.post("/medicine/{medicine_id}/edit")
    async def edit_save(request: Request, medicine_id: int):
        if _svc().get(medicine_id) is None:
            raise HTTPException(status_code=404, detail="Medicine not found")
        form = await request.form()
        no_expiry = form.get("no_expiry")
        expiry = None if no_expiry else _parse_expiry(
            form.get("expiry_date") or "")
        name = (form.get("name") or "").strip()
        if not name or (not expiry and not no_expiry):
            values = {k: form.get(k, "") for k in _FORM_FIELDS if k not in
                      ("photo_saved", "ai_extracted", "ai_failed")}
            return templates.TemplateResponse(
                request, "edit.html",
                page_context(request, values=values, units=UNITS,
                             error_expiry=True, no_expiry=no_expiry),
                status_code=400)
        _svc().update(medicine_id, {
            "name": name,
            "expiry_date": expiry,
            "quantity": _to_float(form.get("quantity"), 0.0),
            "unit": (form.get("unit") or "pieces").strip(),
            "low_stock_threshold": _to_int(form.get("low_stock_threshold"), 3) or 0,
            "discard_after_days": _to_int(form.get("discard_after_days")),
        })
        return RedirectResponse(f"/medicine/{medicine_id}", status_code=303)

    @router.post("/medicine/{medicine_id}/take")
    async def take_dose(medicine_id: int, request: Request):
        if _svc().get(medicine_id) is None:
            raise HTTPException(status_code=404, detail="Medicine not found")
        form = await request.form()
        amount = max(0.0, _to_float(form.get("amount"), 0.0))
        _svc().take_dose(medicine_id, amount, "web")
        return RedirectResponse(f"/medicine/{medicine_id}", status_code=303)

    @router.post("/medicine/{medicine_id}/open")
    async def mark_opened(medicine_id: int):
        if _svc().get(medicine_id) is None:
            raise HTTPException(status_code=404, detail="Medicine not found")
        _svc().mark_opened(medicine_id, datetime.date.today().isoformat(), "web")
        return RedirectResponse(f"/medicine/{medicine_id}", status_code=303)

    @router.post("/medicine/{medicine_id}/discard")
    async def discard(medicine_id: int):
        if _svc().get(medicine_id) is None:
            raise HTTPException(status_code=404, detail="Medicine not found")
        _svc().discard(medicine_id, "web")
        return RedirectResponse("/", status_code=303)

    @router.post("/medicine/{medicine_id}/reread")
    async def reread(medicine_id: int):
        row = _svc().get(medicine_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Medicine not found")
        url = f"/medicine/{medicine_id}"
        if settings is None or not row["photo_path"]:
            return RedirectResponse(url, status_code=303)
        path = Path(data_dir) / row["photo_path"]
        if not path.is_file():
            return RedirectResponse(url, status_code=303)
        ext = await extract_medicine(settings, [path.read_bytes()])
        if ext and not ext.multiple and ext.name:
            updates = {
                "name": ext.name,
                "active_ingredient": ext.active_ingredient,
                "form": ext.form,
                "dosage_pl": ext.dosage_pl, "dosage_ru": ext.dosage_ru,
                "dosage_uk": ext.dosage_uk, "dosage_en": ext.dosage_en,
                "description_pl": ext.description_pl,
                "description_ru": ext.description_ru,
                "description_uk": ext.description_uk,
                "description_en": ext.description_en,
                "ai_status": "ok",
            }
            if ext.expiry_date:
                updates["expiry_date"] = ext.expiry_date
            _svc().update(medicine_id, updates)
        return RedirectResponse(url, status_code=303)

    return router
