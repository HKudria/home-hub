"""Web UI routes: medicine list, detail view, language switcher."""
import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.i18n import LANGS, t
from app.services.medicine_service import MedicineService

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["LANGS"] = LANGS


def _days_until(date_str) -> int | None:
    """Days from today until the given ISO date; None if unset/invalid."""
    if not date_str:
        return None
    try:
        d = datetime.date.fromisoformat(date_str)
    except ValueError:
        return None
    return (d - datetime.date.today()).days


def build_web_router(services, conn, default_lang: str = "en", data_dir: str = ".") -> APIRouter:
    router = APIRouter()
    medicines = services.get("medicines") or MedicineService(conn)

    def page_context(request: Request, **extra):
        lang = request.cookies.get("lang", default_lang)
        T = lambda key, **kw: t(lang, key, **kw)  # noqa: E731
        ctx = {"request": request, "T": T, "lang": lang}
        ctx.update(extra)
        return ctx

    @router.get("/")
    async def list_view(request: Request, q: str = ""):
        rows = [dict(r) for r in medicines.list_all()]
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
        row = medicines.get(medicine_id)
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

    @router.post("/lang/{code}")
    async def set_lang(code: str):
        if code not in LANGS:
            raise HTTPException(status_code=404, detail="Unknown language")
        response = RedirectResponse("/", status_code=303)
        response.set_cookie("lang", code)
        return response

    return router
