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
        "list_added": "Added: {items}",
        "list_bought": "Bought: {name} ✓",
        "list_empty": "The shopping list is empty",
        "list_contents": "Shopping list:",
        "nav_shopping": "Shopping",
        "bought_section": "Bought",
        "clear_bought": "Clear bought",
        "activity": "Recent activity",
        "list_placeholder": "Add items, separated by commas",
        "feed_added": "added by {who}",
        "feed_bought": "bought by {who}",
        "list_title": "Medicine cabinet",
        "empty_cabinet": "Your cabinet is empty. Add your first medicine!",
        "no_expiry": "No expiry date set",
        "take_dose": "Took a dose",
        "mark_opened": "Mark opened",
        "reread_photo": "Re-read photo",
        "save": "Save",
        "edit": "Edit",
        "language": "Language",
        "search_placeholder": "Search...",
        "expiry_required": "Expiry date is required.",
        "discard": "Discard",
        "optional": "optional",
        "camera": "Camera",
        "multiple_warning": "The photo shows several packages — please photograph one box at a time, or the barcode.",
        "ai_error": "Could not read the photo — please fill in the fields manually.",
        "ai_ok": "Photo read — please check the fields below.",
        "reading_photo": "AI is reading the photo…",
        "camera_front": "Take a photo of the package",
        "camera_hint": "The AI reads the photo automatically — you can fix everything before saving.",
        "quantity": "Quantity",
        "unit": "Unit",
        "low_stock_threshold": "Low stock alert",
        "discard_after_days": "Discard after opening (days)",
        "form_name": "Name",
        "form_ingredient": "Active ingredient",
        "form_form": "Form",
        "form_dosage": "Dosage",
        "form_description": "Description",
        "form_expiry": "Expiry date",
        "form_quantity": "Quantity",
        "form_unit": "Unit",
        "form_threshold": "Low stock alert",
        "form_discard_after": "Discard after opening (days)",
        "detail_ingredient": "Active ingredient",
        "detail_opened": "Opened",
        "detail_discard_after": "Discard after opening",
        "section_info": "Info",
        "section_storage": "Storage & dates",
        "task_added": "Task added: {title}",
        "task_assigned_note": " → {who}",
        "task_unassigned_note": "(couldn't match member '{who}' — left unassigned)",
        "task_done": "Done: {title} ✓",
        "task_empty": "No open tasks",
        "task_list": "Open tasks:",
        "task_new_dm": "New task from {who}: {title}{due}",
        "task_due": " due {date}",
        "task_overdue": "OVERDUE",
        "task_digest": "Tasks due:",
        "nav_tasks": "Tasks",
        "help_text": (
            "Just write to me in plain words, for example:\n"
            "• took 1 paracetamol\n"
            "• opened aspirin\n"
            "• how much ibuprofen is left?\n"
            "• I have a headache — anything?\n"
            "• expiry soon?\n"
            "• add milk\n"
            "• bought milk\n"
            "• show shopping list\n"
            "• add task pay bills on friday\n"
            "• task pay bills is done\n"
            "• show tasks\n\n"
            "/lang pl — change language"
        ),
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
        "list_added": "Dodano: {items}",
        "list_bought": "Kupione: {name} ✓",
        "list_empty": "Lista zakupów jest pusta",
        "list_contents": "Lista zakupów:",
        "nav_shopping": "Zakupy",
        "bought_section": "Kupione",
        "clear_bought": "Wyczyść kupione",
        "activity": "Ostatnia aktywność",
        "list_placeholder": "Dodaj produkty, oddzielone przecinkami",
        "feed_added": "dodane przez {who}",
        "feed_bought": "kupione przez {who}",
        "list_title": "Domowa apteczka",
        "empty_cabinet": "Twoja apteczka jest pusta. Dodaj pierwszy lek!",
        "no_expiry": "Brak daty ważności",
        "take_dose": "Przyjęto dawkę",
        "mark_opened": "Oznacz jako otwarte",
        "reread_photo": "Ponów rozpoznawanie zdjęcia",
        "save": "Zapisz",
        "edit": "Edytuj",
        "language": "Język",
        "search_placeholder": "Szukaj...",
        "expiry_required": "Data ważności jest wymagana.",
        "discard": "Wyrzuć",
        "optional": "opcjonalnie",
        "camera": "Aparat",
        "multiple_warning": "Na zdjęciu jest kilka opakowań — sfotografuj jedno opakowanie naraz albo kod kreskowy.",
        "ai_error": "Nie udało się odczytać zdjęcia — wypełnij pola ręcznie.",
        "ai_ok": "Zdjęcie odczytane — sprawdź pola poniżej.",
        "reading_photo": "AI czyta zdjęcie…",
        "camera_front": "Zrób zdjęcie opakowania",
        "camera_hint": "AI odczyta zdjęcie automatycznie — przed zapisaniem możesz wszystko poprawić.",
        "quantity": "Ilość",
        "unit": "Jednostka",
        "low_stock_threshold": "Alarm niskiego stanu",
        "discard_after_days": "Wyrzuć po otwarciu (dni)",
        "form_name": "Nazwa",
        "form_ingredient": "Substancja czynna",
        "form_form": "Postać",
        "form_dosage": "Dawkowanie",
        "form_description": "Opis",
        "form_expiry": "Data ważności",
        "form_quantity": "Ilość",
        "form_unit": "Jednostka",
        "form_threshold": "Alarm niskiego stanu",
        "form_discard_after": "Wyrzuć po otwarciu (dni)",
        "detail_ingredient": "Substancja czynna",
        "detail_opened": "Otwarto",
        "detail_discard_after": "Wyrzuć po otwarciu",
        "section_info": "Informacje",
        "section_storage": "Przechowywanie i daty",
        "task_added": "Dodano zadanie: {title}",
        "task_assigned_note": " → {who}",
        "task_unassigned_note": "(nie dopasowano członka rodziny '{who}' — zadanie pozostało bez przypisania)",
        "task_done": "Zrobione: {title} ✓",
        "task_empty": "Brak otwartych zadań",
        "task_list": "Otwarte zadania:",
        "task_new_dm": "Nowe zadanie od {who}: {title}{due}",
        "task_due": " termin {date}",
        "task_overdue": "ZALEGŁE",
        "task_digest": "Zadania na dziś:",
        "nav_tasks": "Zadania",
        "help_text": (
            "Pisz do mnie zwykłymi słowami, na przykład:\n"
            "• wziąłem 1 paracetamol\n"
            "• otworzyłem aspirynę\n"
            "• ile zostało ibuprofenu?\n"
            "• boli mnie głowa — coś masz?\n"
            "• co wkrótce traci ważność?\n"
            "• dodaj mleko\n"
            "• kupiłem mleko\n"
            "• pokaż listę zakupów\n"
            "• dodaj zadanie zapłać rachunki w piątek\n"
            "• zadanie zapłać rachunki jest zrobione\n"
            "• pokaż zadania\n\n"
            "/lang pl — zmiana języka"
        ),
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
        "list_added": "Добавлено: {items}",
        "list_bought": "Куплено: {name} ✓",
        "list_empty": "Список покупок пуст",
        "list_contents": "Список покупок:",
        "nav_shopping": "Покупки",
        "bought_section": "Куплено",
        "clear_bought": "Очистить купленные",
        "activity": "Последние действия",
        "list_placeholder": "Добавьте пункты через запятую",
        "feed_added": "добавлено: {who}",
        "feed_bought": "куплено: {who}",
        "list_title": "Домашняя аптечка",
        "empty_cabinet": "Ваша аптечка пуста. Добавьте первое лекарство!",
        "no_expiry": "Срок годности не указан",
        "take_dose": "Доза принята",
        "mark_opened": "Отметить открытым",
        "reread_photo": "Повторно распознать фото",
        "save": "Сохранить",
        "edit": "Изменить",
        "language": "Язык",
        "search_placeholder": "Поиск...",
        "expiry_required": "Укажите срок годности.",
        "discard": "Выбросить",
        "optional": "необязательно",
        "camera": "Камера",
        "multiple_warning": "На фото несколько упаковок — сфотографируйте одну упаковку или штрихкод.",
        "ai_error": "Не удалось распознать фото — заполните поля вручную.",
        "ai_ok": "Фото распознано — проверьте поля ниже.",
        "reading_photo": "ИИ читает фото…",
        "camera_front": "Сфотографируйте упаковку",
        "camera_hint": "ИИ распознает фото автоматически — перед сохранением всё можно исправить.",
        "quantity": "Количество",
        "unit": "Единица",
        "low_stock_threshold": "Порог малого запаса",
        "discard_after_days": "Выбросить после вскрытия (дней)",
        "form_name": "Название",
        "form_ingredient": "Действующее вещество",
        "form_form": "Форма",
        "form_dosage": "Дозировка",
        "form_description": "Описание",
        "form_expiry": "Срок годности",
        "form_quantity": "Количество",
        "form_unit": "Единица",
        "form_threshold": "Порог малого запаса",
        "form_discard_after": "Выбросить после вскрытия (дней)",
        "detail_ingredient": "Действующее вещество",
        "detail_opened": "Открыто",
        "detail_discard_after": "Выбросить после вскрытия",
        "section_info": "Информация",
        "section_storage": "Хранение и даты",
        "task_added": "Задача добавлена: {title}",
        "task_assigned_note": " → {who}",
        "task_unassigned_note": "(не удалось сопоставить участника '{who}' — оставлено без исполнителя)",
        "task_done": "Готово: {title} ✓",
        "task_empty": "Нет открытых задач",
        "task_list": "Открытые задачи:",
        "task_new_dm": "Новая задача от {who}: {title}{due}",
        "task_due": " до {date}",
        "task_overdue": "ПРОСРОЧЕНО",
        "task_digest": "Задачи на сегодня:",
        "nav_tasks": "Задачи",
        "help_text": (
            "Просто напишите мне обычными словами, например:\n"
            "• принял 1 парацетамол\n"
            "• открыл аспирин\n"
            "• сколько осталось ибупрофена?\n"
            "• у меня болит голова — что есть?\n"
            "• что скоро истекает?\n"
            "• добавь молоко\n"
            "• купил молоко\n"
            "• покажи список покупок\n"
            "• добавь задачу заплатить за свет в пятницу\n"
            "• задача заплатить за свет сделана\n"
            "• покажи задачи\n\n"
            "/lang ru — сменить язык"
        ),
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
        "list_added": "Додано: {items}",
        "list_bought": "Куплено: {name} ✓",
        "list_empty": "Список покупок порожній",
        "list_contents": "Список покупок:",
        "nav_shopping": "Покупки",
        "bought_section": "Куплено",
        "clear_bought": "Очистити куплені",
        "activity": "Останні дії",
        "list_placeholder": "Додайте пункти через кому",
        "feed_added": "додано: {who}",
        "feed_bought": "куплено: {who}",
        "list_title": "Домашня аптечка",
        "empty_cabinet": "Ваша аптечка порожня. Додайте перші ліки!",
        "no_expiry": "Термін придатності не вказано",
        "take_dose": "Дозу прийнято",
        "mark_opened": "Позначити відкритим",
        "reread_photo": "Повторно розпізнати фото",
        "save": "Зберегти",
        "edit": "Редагувати",
        "language": "Мова",
        "search_placeholder": "Пошук...",
        "expiry_required": "Вкажіть термін придатності.",
        "discard": "Викинути",
        "optional": "необов'язково",
        "camera": "Камера",
        "multiple_warning": "На фото кілька упаковок — сфотографуйте одну упаковку або штрихкод.",
        "ai_error": "Не вдалося розпізнати фото — заповніть поля вручну.",
        "ai_ok": "Фото розпізнано — перевірте поля нижче.",
        "reading_photo": "ШІ читає фото…",
        "camera_front": "Сфотографуйте упаковку",
        "camera_hint": "ШІ розпізнає фото автоматично — перед збереженням все можна виправити.",
        "quantity": "Кількість",
        "unit": "Одиниця",
        "low_stock_threshold": "Поріг малого запасу",
        "discard_after_days": "Викинути після відкриття (днів)",
        "form_name": "Назва",
        "form_ingredient": "Діюча речовина",
        "form_form": "Форма",
        "form_dosage": "Дозування",
        "form_description": "Опис",
        "form_expiry": "Термін придатності",
        "form_quantity": "Кількість",
        "form_unit": "Одиниця",
        "form_threshold": "Поріг малого запасу",
        "form_discard_after": "Викинути після відкриття (днів)",
        "detail_ingredient": "Діюча речовина",
        "detail_opened": "Відкрито",
        "detail_discard_after": "Викинути після відкриття",
        "section_info": "Інформація",
        "section_storage": "Зберігання та дати",
        "task_added": "Завдання додано: {title}",
        "task_assigned_note": " → {who}",
        "task_unassigned_note": "(не вдалося зіставити учасника '{who}' — залишено без виконавця)",
        "task_done": "Готово: {title} ✓",
        "task_empty": "Немає відкритих завдань",
        "task_list": "Відкриті завдання:",
        "task_new_dm": "Нове завдання від {who}: {title}{due}",
        "task_due": " до {date}",
        "task_overdue": "ПРОСТРОЧЕНО",
        "task_digest": "Завдання на сьогодні:",
        "nav_tasks": "Завдання",
        "help_text": (
            "Пишіть мені звичайними словами, наприклад:\n"
            "• прийняв 1 парацетамол\n"
            "• відкрив аспірин\n"
            "• скільки залишилось ібупрофену?\n"
            "• у мене болить голова — щось є?\n"
            "• що скоро спливає?\n"
            "• додай молоко\n"
            "• купив молоко\n"
            "• покажи список покупок\n"
            "• додай завдання заплатити за світло у п'ятницю\n"
            "• завдання заплатити за світло виконано\n"
            "• покажи завдання\n\n"
            "/lang uk — змінити мову"
        ),
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
