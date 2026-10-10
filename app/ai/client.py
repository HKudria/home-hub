import base64, json, re
from dataclasses import dataclass
import httpx

PROMPT = (
    "You are reading a photo of ONE medicine package. First: if the photo shows more than one "
    "package/box, reply ONLY with {\"multiple\": true} — never guess which one is meant.\n"
    "Otherwise reply with RAW JSON (no markdown, no commentary) with exactly these keys: "
    "name, active_ingredient, form, dosage_pl, dosage_ru, dosage_uk, dosage_en, "
    "description_pl, description_ru, description_uk, description_en, expiry_date.\n"
    "dosage_*: how to take it (e.g. '1 tablet 2x daily') in the given language. "
    "description_*: one short sentence 'what it is for' in the given language. "
    "expiry_date: 'YYYY-MM-DD' if visible, else 'YYYY-MM', else null. "
    "If a value is unknown use '' (or null for expiry_date)."
)

@dataclass
class MedicineExtract:
    name: str
    active_ingredient: str
    form: str
    dosage_pl: str
    dosage_ru: str
    dosage_uk: str
    dosage_en: str
    description_pl: str
    description_ru: str
    description_uk: str
    description_en: str
    expiry_date: str | None
    multiple: bool = False

def parse_extraction(text: str) -> MedicineExtract | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if data.get("multiple"):
        return MedicineExtract(name="", active_ingredient="", form="",
                               dosage_pl="", dosage_ru="", dosage_uk="", dosage_en="",
                               description_pl="", description_ru="", description_uk="",
                               description_en="", expiry_date=None, multiple=True)
    if not data.get("name"):
        return None
    exp = data.get("expiry_date") or None
    return MedicineExtract(
        name=str(data["name"]), active_ingredient=data.get("active_ingredient", "") or "",
        form=data.get("form", "") or "",
        dosage_pl=data.get("dosage_pl", "") or "", dosage_ru=data.get("dosage_ru", "") or "",
        dosage_uk=data.get("dosage_uk", "") or "", dosage_en=data.get("dosage_en", "") or "",
        description_pl=data.get("description_pl", "") or "", description_ru=data.get("description_ru", "") or "",
        description_uk=data.get("description_uk", "") or "", description_en=data.get("description_en", "") or "",
        expiry_date=exp)

SUGGEST_PROMPT = (
    "You are a pharmacy assistant. For the given medicine name, return RAW JSON "
    "(no markdown) with exactly these keys: name (the standard product name), "
    "active_ingredient, form, dosage_pl, dosage_ru, dosage_uk, dosage_en, "
    "description_pl, description_ru, description_uk, description_en, expiry_date: null. "
    "dosage_*: typical usage in the given language. description_*: one short sentence "
    "'what it is for' in the given language. If you don't know the medicine, reply "
    "with {\"name\": \"\"} and empty strings."
)

async def suggest_by_name(settings, name: str) -> MedicineExtract | None:
    """Pre-fill medicine details from a manually typed name via the
    z.ai text model. Expiry is never suggested (expiry_date: null)."""
    payload = {"model": settings.zai_text_model,
               "max_tokens": 1024,
               "system": SUGGEST_PROMPT,
               "messages": [{"role": "user", "content": name}]}
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{settings.zai_base_url.rstrip('/')}/v1/messages",
                             json=payload,
                             headers={"x-api-key": settings.zai_api_key,
                                      "anthropic-version": "2023-06-01"})
            r.raise_for_status()
            data = r.json()
            text = "".join(b.get("text", "") for b in data.get("content", [])
                           if isinstance(b, dict))
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        return None
    return parse_extraction(text)

async def extract_medicine(settings, images: list[bytes]) -> MedicineExtract | None:
    """Extract medicine data from package photos via z.ai's Anthropic-compatible
    API (POST {base_url}/v1/messages with x-api-key auth)."""
    content = []
    for img in images:
        b64 = base64.b64encode(img).decode()
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}})
    content.append({"type": "text", "text": PROMPT})
    payload = {"model": settings.zai_vision_model,
               "max_tokens": 2048,
               "system": PROMPT,
               "messages": [{"role": "user", "content": content}]}
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{settings.zai_base_url.rstrip('/')}/v1/messages",
                             json=payload,
                             headers={"x-api-key": settings.zai_api_key,
                                      "anthropic-version": "2023-06-01"})
            r.raise_for_status()
            data = r.json()
            text = "".join(block.get("text", "") for block in data.get("content", [])
                           if isinstance(block, dict))
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        return None
    return parse_extraction(text)
