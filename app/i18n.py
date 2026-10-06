"""i18n catalog: UI strings for en/pl/ru/uk.

`t(lang, key, **kwargs)` returns the translated, formatted string.
Falls back to English when a language (or key) is missing, and to the
key itself when even English lacks it.
"""

LANGS = ("en", "pl", "ru", "uk")
DEFAULT_LANG = "pl"

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "app_name": "Home Hub",
        "add_medicine": "Add medicine",
        "expires_in_days": "{name} expires in {days} days",
        "expired_days_ago": "{name} expired {days} days ago",
        "expires_today": "{name} expires TODAY",
        "discard_soon": "{name} must be discarded tomorrow (opened {opened})",
        "discard_today": "{name} must be discarded today (opened {opened})",
        "low_stock": "{name}: only {qty} left",
        "last_dose": "{name}: that was the last dose",
        "quantity_left": "{name}: {qty} {unit} left",
        "took": "OK — {name}: {qty} {unit} left",
        "opened_on": "{name} marked opened on {opened}",
        "no_match": "I couldn't find that medicine.",
        "which_one": "Which one?",
        "symptom_none": "Nothing in your cabinet matches.",
        "symptom_found": "For that you have:",
        "expiring_soon_list": "Expiring within 7 days:",
        "approved": "You're approved! ✅",
        "ask_admin": "Hi! I asked the admin to approve you.",
        "discarded": "Marked as discarded 🗑",
        "snoozed": "Snoozed ⏰",
        "added_to_list": "Added to the shopping list 🛒",
        "list_title": "Medicine cabinet",
        "no_expiry": "No expiry date set",
        "take_dose": "Took a dose",
        "mark_opened": "Mark opened",
        "reread_photo": "Re-read photo",
        "save": "Save",
        "edit": "Edit",
        "language": "Language",
        "search_placeholder": "Search...",
    },
    "pl": {
        "app_name": "Apteczka",
        "add_medicine": "Dodaj lek",
        "expires_in_days": "{name} traci ważność za {days} dni",
        "expired_days_ago": "{name} przeterminował się {days} dni temu",
        "expires_today": "{name} traci ważność DZIŚ",
        "discard_soon": "{name} trzeba wyrzucić jutro (otwarto {opened})",
        "discard_today": "{name} trzeba wyrzucić dziś (otwarto {opened})",
        "low_stock": "{name}: zostało tylko {qty}",
        "last_dose": "{name}: to była ostatnia dawka",
        "quantity_left": "{name}: zostało {qty} {unit}",
        "took": "OK — {name}: zostało {qty} {unit}",
        "opened_on": "{name} oznaczono jako otwarte {opened}",
        "no_match": "Nie znalazłem takiego leku.",
        "which_one": "Który?",
        "symptom_none": "Nic w twojej apteczce nie pasuje.",
        "symptom_found": "Na to masz:",
        "expiring_soon_list": "Tracą ważność w ciągu 7 dni:",
        "approved": "Jesteś zatwierdzony! ✅",
        "ask_admin": "Cześć! Poprosiłem administratora, żeby cię zatwierdził.",
        "discarded": "Oznaczono jako wyrzucone 🗑",
        "snoozed": "Odłożono ⏰",
        "added_to_list": "Dodano do listy zakupów 🛒",
        "list_title": "Domowa apteczka",
        "no_expiry": "Brak daty ważności",
        "take_dose": "Przyjęto dawkę",
        "mark_opened": "Oznacz jako otwarte",
        "reread_photo": "Ponów rozpoznawanie zdjęcia",
        "save": "Zapisz",
        "edit": "Edytuj",
        "language": "Język",
        "search_placeholder": "Szukaj...",
    },
    "ru": {
        "app_name": "Аптечка",
        "add_medicine": "Добавить лекарство",
        "expires_in_days": "{name} истекает через {days} дн.",
        "expired_days_ago": "{name} просрочено {days} дн. назад",
        "expires_today": "{name} истекает СЕГОДНЯ",
        "discard_soon": "{name} нужно выбросить завтра (открыто {opened})",
        "discard_today": "{name} нужно выбросить сегодня (открыто {opened})",
        "low_stock": "{name}: осталось всего {qty}",
        "last_dose": "{name}: это была последняя доза",
        "quantity_left": "{name}: осталось {qty} {unit}",
        "took": "ОК — {name}: осталось {qty} {unit}",
        "opened_on": "{name} отмечено открытым {opened}",
        "no_match": "Не нашёл такого лекарства.",
        "which_one": "Какое именно?",
        "symptom_none": "В вашей аптечке ничего не подходит.",
        "symptom_found": "От этого у вас есть:",
        "expiring_soon_list": "Истекает в течение 7 дней:",
        "approved": "Вам одобрен доступ! ✅",
        "ask_admin": "Привет! Я попросил администратора вас одобрить.",
        "discarded": "Помечено как выброшенное 🗑",
        "snoozed": "Отложено ⏰",
        "added_to_list": "Добавлено в список покупок 🛒",
        "list_title": "Домашняя аптечка",
        "no_expiry": "Срок годности не указан",
        "take_dose": "Доза принята",
        "mark_opened": "Отметить открытым",
        "reread_photo": "Повторно распознать фото",
        "save": "Сохранить",
        "edit": "Изменить",
        "language": "Язык",
        "search_placeholder": "Поиск...",
    },
    "uk": {
        "app_name": "Аптечка",
        "add_medicine": "Додати ліки",
        "expires_in_days": "{name} спливає за {days} днів",
        "expired_days_ago": "{name} прострочено {days} дн. тому",
        "expires_today": "{name} спливає СЬОГОДНІ",
        "discard_soon": "{name} треба викинути завтра (відкрито {opened})",
        "discard_today": "{name} треба викинути сьогодні (відкрито {opened})",
        "low_stock": "{name}: залишилося лише {qty}",
        "last_dose": "{name}: це була остання доза",
        "quantity_left": "{name}: залишилося {qty} {unit}",
        "took": "Гаразд — {name}: залишилося {qty} {unit}",
        "opened_on": "{name} позначено відкритим {opened}",
        "no_match": "Не знайшов такого препарату.",
        "which_one": "Яке саме?",
        "symptom_none": "У вашій аптечці нічого не підходить.",
        "symptom_found": "Від цього у вас є:",
        "expiring_soon_list": "Спливає протягом 7 днів:",
        "approved": "Вам схвалено доступ! ✅",
        "ask_admin": "Привіт! Я попросив адміністратора вас схвалити.",
        "discarded": "Позначено як викинуте 🗑",
        "snoozed": "Відкладено ⏰",
        "added_to_list": "Додано до списку покупок 🛒",
        "list_title": "Домашня аптечка",
        "no_expiry": "Термін придатності не вказано",
        "take_dose": "Дозу прийнято",
        "mark_opened": "Позначити відкритим",
        "reread_photo": "Повторно розпізнати фото",
        "save": "Зберегти",
        "edit": "Редагувати",
        "language": "Мова",
        "search_placeholder": "Пошук...",
    },
}

# The brief lists this key both as "re-read_photo" and "reread_photo";
# keep an alias so either spelling works.
for _msgs in MESSAGES.values():
    _msgs["re-read_photo"] = _msgs["reread_photo"]


def t(lang: str, key: str, **kwargs) -> str:
    msg = MESSAGES.get(lang, {}).get(key) or MESSAGES["en"].get(key) or key
    if kwargs:
        msg = msg.format(**kwargs)
    return msg


# Common Ukrainian words with no і/ї/є/ґ (e.g. "узяв", "взяв") would
# otherwise be misread as Russian by the letter heuristic alone.
_UK_WORDS = frozenset(
    {"узяв", "взяв", "що", "був", "була", "було", "його", "йому", "нею", "цей", "туди"}
)


def detect_lang(text: str) -> str:
    low = text.lower()
    if any(c in low for c in "іїєґ"):
        return "uk"
    if any(w in _UK_WORDS for w in low.split()):
        return "uk"
    if any("Ѐ" <= c <= "ӿ" for c in low):
        return "ru"
    if any(c in low for c in "ąćęłńóśźż"):
        return "pl"
    return "en"
