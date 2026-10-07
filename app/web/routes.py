"""Web UI routes: medicine list, detail view + actions, add flow with
camera capture and AI extraction."""
import dataclasses
import datetime
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.ai.client import extract_medicine
from app.i18n import LANGS, t
from app.services.medicine_service import MedicineService

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["LANGS"] = LANGS

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


def build_web_router(services, conn, default_lang: str = "en", data_dir: str = ".",
                     settings=None) -> APIRouter:
    router = APIRouter()

    def _svc() -> MedicineService:
        """Real service when injected (Task 13), lazy fallback for tests."""
        return services.get("medicines") or MedicineService(conn)

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
    async def set_lang(code: str):
        if code not in LANGS:
            raise HTTPException(status_code=404, detail="Unknown language")
        response = RedirectResponse("/", status_code=303)
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
        lens = []
        for u in uploads:
            data = await u.read()
            lens.append(len(data))
            if len(data) <= MAX_IMAGE_BYTES:
                blobs.append(data)
        if not blobs:
            raw = form.getlist("images")
            return JSONResponse({"error": True, "dbg": {
                "raw_count": len(raw),
                "types": sorted({type(u).__name__ for u in raw}),
                "cts": [getattr(u, "content_type", None) for u in raw],
                "lens": lens,
                "size": len(blobs),
            }})
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

    @router.post("/add")
    async def add_save(request: Request):
        form = await request.form()
        expiry = (form.get("expiry_date") or "").strip()
        if not expiry:
            values = {k: form.get(k, "") for k in _FORM_FIELDS}
            return templates.TemplateResponse(
                request, "add.html",
                page_context(request, values=values, error_expiry=True, units=UNITS),
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
        expiry = (form.get("expiry_date") or "").strip()
        name = (form.get("name") or "").strip()
        if not name or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", expiry):
            values = {k: form.get(k, "") for k in _FORM_FIELDS if k not in
                      ("photo_saved", "ai_extracted", "ai_failed")}
            return templates.TemplateResponse(
                request, "edit.html",
                page_context(request, values=values, units=UNITS,
                             error_expiry=True),
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
        return RedirectResponse(f"/medicine/{medicine_id}", status_code=303)

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
