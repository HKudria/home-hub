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

async def extract_medicine(settings, images: list[bytes]) -> MedicineExtract | None:
    content = [{"type": "text", "text": PROMPT}]
    for img in images:
        b64 = base64.b64encode(img).decode()
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    payload = {"model": settings.zai_vision_model,
               "messages": [{"role": "user", "content": content}]}
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{settings.zai_base_url}/chat/completions",
                             json=payload, headers={"Authorization": f"Bearer {settings.zai_api_key}"})
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None
    return parse_extraction(text)
