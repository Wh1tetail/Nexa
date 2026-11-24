"""Server-side texts in the user's language (ru — default, kk, en).

The Russian text is the message id (gettext style): code keeps writing
`BadRequest("Тест не найден")` or `BadRequest("Не более {n} файлов", n=5)`,
and `tr()` looks the template up in CATALOG for other languages. Unknown texts
fall back to Russian, so a missing translation never breaks a response.

- API responses: the language of the request (Accept-Language, set by the
  frontend from the interface language) — see `request_lang` and the
  exception handlers in app/main.py.
- Notifications and e-mails: the recipient's language (users.locale), since
  they are read later, outside the request that created them.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

LANGS = ("ru", "kk", "en")
DEFAULT_LANG = "ru"

request_lang: ContextVar[str] = ContextVar("request_lang", default=DEFAULT_LANG)


def norm_lang(value: str | None) -> str:
    return value if value in LANGS else DEFAULT_LANG


def lang_from_header(header: str | None) -> str:
    """First supported language from an Accept-Language header."""
    for part in (header or "").split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in LANGS:
            return code
        if code == "kz":
            return "kk"
    return DEFAULT_LANG


def tr(template: str, lang: str | None = None, **params: Any) -> str:
    lang = norm_lang(lang or request_lang.get())
    text = template
    if lang != "ru":
        text = CATALOG.get(template, {}).get(lang, template)
    if params:
        try:
            return text.format(**params)
        except (KeyError, IndexError, ValueError):
            return template.format(**params)
    return text


@dataclass(frozen=True)
class Msg:
    """A text rendered later, per recipient (notifications, e-mails)."""

    template: str
    params: dict[str, Any] = field(default_factory=dict)

    def render(self, lang: str | None) -> str:
        params = {k: (v.render(lang) if isinstance(v, Msg) else v) for k, v in self.params.items()}
        return tr(self.template, lang, **params)


def M(template: str, **params: Any) -> Msg:
    return Msg(template, params)


def render(text: str | Msg | None, lang: str | None) -> str | None:
    """Plain strings are user content (titles, names) and stay as they are."""
    return text.render(lang) if isinstance(text, Msg) else text


# ---------------------------------------------------------------------------
# Catalog: Russian template -> {"kk": ..., "en": ...}
# ---------------------------------------------------------------------------
CATALOG: dict[str, dict[str, str]] = {
    # --- generic / auth ---
    "Не найдено": {"kk": "Табылмады", "en": "Not found"},
    "Недостаточно прав": {"kk": "Құқық жеткіліксіз", "en": "You don't have permission"},
    "Требуется авторизация": {"kk": "Жүйеге кіру қажет", "en": "Please sign in"},
    "Некорректные данные": {"kk": "Деректер дұрыс емес", "en": "Invalid data"},
    "Срок действия токена истёк": {"kk": "Токеннің мерзімі өтті", "en": "The token has expired"},
    "Недействительный токен": {"kk": "Жарамсыз токен", "en": "Invalid token"},
    "Неверный тип токена": {"kk": "Токен түрі қате", "en": "Wrong token type"},
    "Сессия недействительна": {"kk": "Сессия жарамсыз", "en": "The session is no longer valid"},
    "Сессия истекла, войдите снова": {"kk": "Сессия аяқталды, қайта кіріңіз", "en": "Your session has expired, please sign in again"},
    "Неверный email или пароль": {"kk": "Email немесе құпиясөз қате", "en": "Wrong email or password"},
    "Аккаунт деактивирован. Обратитесь к администратору": {
        "kk": "Аккаунт өшірілген. Әкімшіге хабарласыңыз",
        "en": "This account is deactivated. Please contact the administrator",
    },
    "Вы вышли из аккаунта": {"kk": "Сіз аккаунттан шықтыңыз", "en": "You have signed out"},
    "Текущий пароль указан неверно": {"kk": "Ағымдағы құпиясөз қате", "en": "The current password is wrong"},
    "Если аккаунт с таким email существует, мы отправили инструкцию по восстановлению": {
        "kk": "Мұндай email-мен аккаунт болса, біз қалпына келтіру нұсқаулығын жібердік",
        "en": "If an account with this email exists, we have sent recovery instructions",
    },
    "Ссылка недействительна или устарела": {"kk": "Сілтеме жарамсыз немесе ескірген", "en": "The link is invalid or has expired"},
    "Пароль изменён. Войдите с новым паролем": {"kk": "Құпиясөз өзгертілді. Жаңа құпиясөзбен кіріңіз", "en": "Password changed. Sign in with the new password"},
    "Пароль изменён": {"kk": "Құпиясөз өзгертілді", "en": "Password changed"},
    "Слишком много попыток. Попробуйте через несколько минут": {
        "kk": "Әрекеттер тым көп. Бірнеше минуттан кейін қайталаңыз",
        "en": "Too many attempts. Please try again in a few minutes",
    },
    "Пароль должен содержать минимум 8 символов": {"kk": "Құпиясөзде кемінде 8 таңба болуы керек", "en": "The password must be at least 8 characters long"},
    "Пароль должен содержать буквы и цифры": {"kk": "Құпиясөзде әріптер мен сандар болуы керек", "en": "The password must contain letters and digits"},
    "Профиль преподавателя не найден": {"kk": "Оқытушы профилі табылмады", "en": "Teacher profile not found"},
    "Профиль ученика не найден": {"kk": "Оқушы профилі табылмады", "en": "Student profile not found"},
    "Выберите преподавателя": {"kk": "Оқытушыны таңдаңыз", "en": "Choose a teacher"},
    "Изменять время, название, ссылку и статус занятия может только администратор": {
        "kk": "Сабақтың уақытын, атауын, сілтемесін және мәртебесін тек әкімші өзгерте алады",
        "en": "Only an administrator can change a lesson's time, title, link and status",
    },
    "Убирать учеников из занятия может только администратор": {
        "kk": "Оқушыларды сабақтан тек әкімші алып тастай алады",
        "en": "Only an administrator can remove students from a lesson",
    },
    "Доступ к занятиям, заданиям и тестам откроется после продления абонемента": {
        "kk": "Сабақтарға, тапсырмаларға және тесттерге қолжетімділік абонемент ұзартылғаннан кейін ашылады",
        "en": "Lessons, homework and tests will open again once the subscription is renewed",
    },
    # --- people, groups, admin ---
    "Ученик не найден": {"kk": "Оқушы табылмады", "en": "Student not found"},
    "Можно назначать только своих учеников": {"kk": "Тек өз оқушыларыңызды тағайындай аласыз", "en": "You can only assign your own students"},
    "Группа не найдена": {"kk": "Топ табылмады", "en": "Group not found"},
    "Группа с таким названием уже существует": {"kk": "Мұндай атаумен топ бар", "en": "A group with this name already exists"},
    "Пользователь не найден": {"kk": "Пайдаланушы табылмады", "en": "User not found"},
    "Нельзя деактивировать собственный аккаунт": {"kk": "Өз аккаунтыңызды өшіре алмайсыз", "en": "You can't deactivate your own account"},
    "Нельзя удалить собственный аккаунт": {"kk": "Өз аккаунтыңызды жоюға болмайды", "en": "You cannot delete your own account"},
    "Администраторов удалять нельзя": {"kk": "Әкімшілерді жоюға болмайды", "en": "Administrators cannot be deleted"},
    "Выберите преподавателя, которому перейдут ученики": {"kk": "Оқушылар ауысатын мұғалімді таңдаңыз", "en": "Choose the teacher the students will move to"},
    "Нельзя передать учеников удаляемому преподавателю": {"kk": "Оқушыларды жойылатын мұғалімге беруге болмайды", "en": "Students cannot be handed over to the teacher being deleted"},
    "Уровень английского задаётся только ученикам": {"kk": "Ағылшын тілі деңгейі тек оқушыларға беріледі", "en": "Only students have an English level"},
    "Ссылка для смены пароля отправлена на {email}": {"kk": "Құпиясөзді өзгерту сілтемесі {email} мекенжайына жіберілді", "en": "A password reset link was sent to {email}"},
    "Приглашение отправлено на {email}": {"kk": "Шақыру {email} мекенжайына жіберілді", "en": "An invitation was sent to {email}"},
    "Пользователь с таким email уже существует": {"kk": "Мұндай email-мен пайдаланушы бар", "en": "A user with this email already exists"},
    "Преподаватель не найден": {"kk": "Оқытушы табылмады", "en": "Teacher not found"},
    "Укажите новый пароль или выберите отправку ссылки": {"kk": "Жаңа құпиясөзді көрсетіңіз немесе сілтеме жіберуді таңдаңыз", "en": "Enter a new password or choose to send a link"},
    "Укажите пароль или отправьте приглашение на email": {"kk": "Құпиясөзді көрсетіңіз немесе email-ге шақыру жіберіңіз", "en": "Enter a password or send an email invitation"},
    "Неизвестный тип уведомлений": {"kk": "Хабарландырудың белгісіз түрі", "en": "Unknown notification type"},
    "Неизвестный часовой пояс": {"kk": "Белгісіз уақыт белдеуі", "en": "Unknown time zone"},
    # --- homework ---
    "Задание не найдено": {"kk": "Тапсырма табылмады", "en": "Assignment not found"},
    "В выбранных группах нет учеников": {"kk": "Таңдалған топтарда оқушылар жоқ", "en": "The selected groups have no students"},
    "Не более {n} файлов на задание": {"kk": "Бір тапсырмаға {n} файлдан артық емес", "en": "No more than {n} files per assignment"},
    "Не более {n} файлов": {"kk": "{n} файлдан артық емес", "en": "No more than {n} files"},
    "Вопрос не найден": {"kk": "Сұрақ табылмады", "en": "Question not found"},
    "Вопрос уже в библиотеке": {"kk": "Сұрақ кітапханада тұр", "en": "The question is already in the library"},
    "Утверждённый вопрос нельзя перегенерировать: сначала верните его на проверку": {"kk": "Бекітілген сұрақты қайта жасауға болмайды: алдымен оны тексеруге қайтарыңыз", "en": "An approved question cannot be regenerated: send it back to review first"},
    "Книга ещё не обработана": {"kk": "Кітап әлі өңделмеген", "en": "The book has not been processed yet"},
    "Генерация вопросов не настроена: нет ключа AI": {"kk": "Сұрақ генерациясы бапталмаған: AI кілті жоқ", "en": "Question generation is not set up: there is no AI key"},
    "Укажите главу или страницы": {"kk": "Тарауды немесе беттерді көрсетіңіз", "en": "Choose a chapter or pages"},
    "Вопросы готовы: {n}": {"kk": "Сұрақтар дайын: {n}", "en": "Questions ready: {n}"},
    "Глава не найдена": {"kk": "Тарау табылмады", "en": "Chapter not found"},
    "Страницы главы — от 1 до {n}, начальная не больше конечной": {"kk": "Тарау беттері — 1-ден {n}-ге дейін, бастапқы бет соңғысынан аспайды", "en": "Chapter pages: 1 to {n}, the first page not after the last"},
    "Глава не может быть подразделом самой себя": {"kk": "Тарау өзінің бөлімі бола алмайды", "en": "A chapter cannot be its own section"},
    "Подраздел должен быть внутри страниц главы ({start}–{end})": {"kk": "Бөлім тараудың беттері ішінде болуы керек ({start}–{end})", "en": "A section must be within the chapter's pages ({start}–{end})"},
    "Не больше трёх уровней вложенности": {"kk": "Үш деңгейден артық емес", "en": "No more than three levels"},
    "Подразделы выходят за страницы главы": {"kk": "Бөлімдер тарау беттерінен шығып кетеді", "en": "Sections go beyond the chapter's pages"},
    "Эта книга уже обрабатывается": {"kk": "Бұл кітап өңделіп жатыр", "en": "This book is already being processed"},
    "Задание обработки не найдено": {"kk": "Өңдеу тапсырмасы табылмады", "en": "Processing job not found"},
    "Задание обработки уже завершено": {"kk": "Өңдеу тапсырмасы аяқталып қойған", "en": "The processing job has already finished"},
    "Книга обработана": {"kk": "Кітап өңделді", "en": "Book processed"},
    "Не удалось обработать книгу": {"kk": "Кітапты өңдеу мүмкін болмады", "en": "The book could not be processed"},
    "Книга не найдена": {"kk": "Кітап табылмады", "en": "Book not found"},
    "Загрузите файл PDF": {"kk": "PDF файлын жүктеңіз", "en": "Upload a PDF file"},
    "Файл повреждён или это не PDF": {"kk": "Файл бүлінген немесе PDF емес", "en": "The file is damaged or not a PDF"},
    "PDF защищён паролем — загрузите файл без защиты": {"kk": "PDF құпиясөзбен қорғалған — қорғалмаған файлды жүктеңіз", "en": "The PDF is password-protected: upload it without protection"},
    "В PDF нет страниц": {"kk": "PDF-те беттер жоқ", "en": "The PDF has no pages"},
    "В PDF больше {n} страниц": {"kk": "PDF-те {n} беттен көп", "en": "The PDF has more than {n} pages"},
    "Количество вопросов — от 1 до {n}": {"kk": "Сұрақтар саны — 1-ден {n}-ге дейін", "en": "Number of questions: 1 to {n}"},
    "Неверный диапазон страниц": {"kk": "Беттер ауқымы қате", "en": "Invalid page range"},
    "Не более {n} страниц за один раз": {"kk": "Бір жолы {n} беттен артық емес", "en": "No more than {n} pages at a time"},
    "Выберите типы вопросов": {"kk": "Сұрақ түрлерін таңдаңыз", "en": "Choose the question types"},
    "На выбранных страницах нет текста": {"kk": "Таңдалған беттерде мәтін жоқ", "en": "The selected pages have no text"},
    "Файл не найден": {"kk": "Файл табылмады", "en": "File not found"},
    "Нет доступа к файлу": {"kk": "Файлға қолжетімділік жоқ", "en": "You don't have access to this file"},
    "Работа не найдена": {"kk": "Жұмыс табылмады", "en": "Submission not found"},
    "Оценка не может быть больше {max}": {"kk": "Баға {max}-ден аспауы керек", "en": "The grade cannot be higher than {max}"},
    "Работа уже отправлена на проверку": {"kk": "Жұмыс тексеруге жіберіліп қойған", "en": "The work has already been submitted for review"},
    "Прикрепите файл или напишите ответ": {"kk": "Файл тіркеңіз немесе жауап жазыңыз", "en": "Attach a file or write an answer"},
    "Выберите хотя бы одного ученика или группу": {"kk": "Кемінде бір оқушыны немесе топты таңдаңыз", "en": "Select at least one student or group"},
    "Недопустимый статус": {"kk": "Рұқсат етілмеген мәртебе", "en": "Invalid status"},
    # --- lessons / subscriptions ---
    "Занятие не найдено": {"kk": "Сабақ табылмады", "en": "Lesson not found"},
    "Нельзя убрать ученика с уже отмеченной посещаемостью": {"kk": "Қатысуы белгіленген оқушыны алып тастауға болмайды", "en": "You can't remove a student whose attendance is already marked"},
    "Добавьте учеников или группу": {"kk": "Оқушыларды немесе топты қосыңыз", "en": "Add students or a group"},
    "Занятие отменено": {"kk": "Сабақ болдырылмады", "en": "Lesson cancelled"},
    "Ученик не участвует в этом занятии": {"kk": "Оқушы бұл сабаққа қатыспайды", "en": "The student is not in this lesson"},
    "Абонемент не найден": {"kk": "Абонемент табылмады", "en": "Subscription not found"},
    "Дата окончания не может быть раньше даты начала": {"kk": "Аяқталу күні басталу күнінен ерте болмауы керек", "en": "The end date cannot be earlier than the start date"},
    "Использованных занятий больше, чем оплачено": {"kk": "Пайдаланылған сабақтар төленгеннен көп", "en": "More lessons used than paid for"},
    "Новая дата окончания раньше даты начала": {"kk": "Жаңа аяқталу күні басталу күнінен ерте", "en": "The new end date is earlier than the start date"},
    "Укажите новую дату окончания, дни или занятия": {"kk": "Жаңа аяқталу күнін, күндерді немесе сабақтарды көрсетіңіз", "en": "Specify a new end date, days or lessons"},
    "Количество использованных занятий не может быть отрицательным": {"kk": "Пайдаланылған сабақтар саны теріс болмауы керек", "en": "The number of used lessons cannot be negative"},
    "Все оплаченные занятия уже использованы": {"kk": "Төленген сабақтардың бәрі пайдаланылды", "en": "All paid lessons have already been used"},
    # --- tests ---
    "Тест не найден": {"kk": "Тест табылмады", "en": "Test not found"},
    "Попытка не найдена": {"kk": "Әрекет табылмады", "en": "Attempt not found"},
    "Тест ещё не открыт": {"kk": "Тест әлі ашылмаған", "en": "The test is not open yet"},
    "Срок сдачи теста истёк": {"kk": "Тестті тапсыру мерзімі өтті", "en": "The test deadline has passed"},
    "Тест уже завершён": {"kk": "Тест аяқталып қойған", "en": "The test is already finished"},
    "Раздел не найден": {"kk": "Бөлім табылмады", "en": "Section not found"},
    # gamification
    "Новое достижение": {"kk": "Жаңа жетістік", "en": "New achievement"},
    "Первый урок": {"kk": "Алғашқы сабақ", "en": "First lesson"},
    "Первый тест": {"kk": "Алғашқы тест", "en": "First test"},
    "Идеальный результат": {"kk": "Мінсіз нәтиже", "en": "Perfect score"},
    "7 дней подряд": {"kk": "Қатарынан 7 күн", "en": "7-day streak"},
    "10 уроков": {"kk": "10 сабақ", "en": "10 lessons"},
    "Уровень пройден": {"kk": "Деңгей өтілді", "en": "Level completed"},
    # courses
    "Выберите уровень или модуль": {"kk": "Деңгейді немесе модульді таңдаңыз", "en": "Choose a level or a module"},
    "Выберите учеников или группы": {"kk": "Оқушыларды немесе топтарды таңдаңыз", "en": "Choose students or groups"},
    "Срок должен быть позже даты начала": {"kk": "Мерзім басталу күнінен кейін болуы керек", "en": "The deadline must be after the start"},
    "В выбранной части курса пока нет опубликованных уроков": {
        "kk": "Курстың таңдалған бөлігінде әзірге жарияланған сабақтар жоқ",
        "en": "The chosen part of the course has no published lessons yet",
    },
    "Сначала выполните все упражнения урока": {"kk": "Алдымен сабақтың барлық жаттығуларын орындаңыз", "en": "Do all the exercises of the lesson first"},
    "Назначение не найдено": {"kk": "Тағайындау табылмады", "en": "Assignment not found"},
    "Эта часть курса назначена ученикам — удалить её нельзя. Можно снять уроки с публикации": {
        "kk": "Курстың бұл бөлігі оқушыларға тағайындалған — оны жоюға болмайды. Сабақтарды жариялаудан алып тастауға болады",
        "en": "This part of the course is assigned to students and can't be deleted. You can unpublish its lessons",
    },
    "Новый курс: {course}": {"kk": "Жаңа курс: {course}", "en": "New course: {course}"},
    "Назначено: {part}": {"kk": "Тағайындалды: {part}", "en": "Assigned: {part}"},
    "Курс не найден": {"kk": "Курс табылмады", "en": "Course not found"},
    "Уровень не найден": {"kk": "Деңгей табылмады", "en": "Level not found"},
    "Модуль не найден": {"kk": "Модуль табылмады", "en": "Module not found"},
    "Урок не найден": {"kk": "Сабақ табылмады", "en": "Lesson not found"},
    "Введите название": {"kk": "Атауын енгізіңіз", "en": "Enter a title"},
    "Этот уровень уже есть в курсе": {"kk": "Бұл деңгей курста бар", "en": "This level is already in the course"},
    "Не более {n} файлов в уроке": {"kk": "Сабақта {n} файлдан артық болмауы керек", "en": "No more than {n} files per lesson"},
    "Файл не найден в материалах урока": {"kk": "Файл сабақ материалдарынан табылмады", "en": "The file is not among the lesson materials"},
    "Файл «{name}» не подходит для этого блока": {"kk": "«{name}» файлы бұл блокқа сәйкес келмейді", "en": "The file “{name}” does not fit this block"},
    "Добавьте в урок хотя бы один блок, прежде чем публиковать": {
        "kk": "Жарияламас бұрын сабаққа кемінде бір блок қосыңыз",
        "en": "Add at least one block to the lesson before publishing it",
    },
    "Текст блока слишком длинный": {"kk": "Блок мәтіні тым ұзын", "en": "The block text is too long"},
    "Добавьте текст": {"kk": "Мәтін қосыңыз", "en": "Add some text"},
    "Добавьте хотя бы одно слово": {"kk": "Кемінде бір сөз қосыңыз", "en": "Add at least one word"},
    "Не более {n} слов в словаре": {"kk": "Сөздікте {n} сөзден артық болмауы керек", "en": "No more than {n} words in a vocabulary block"},
    "Выберите изображение из материалов урока": {"kk": "Сабақ материалдарынан сурет таңдаңыз", "en": "Choose an image from the lesson materials"},
    "Выберите видеофайл из материалов урока": {"kk": "Сабақ материалдарынан бейнефайл таңдаңыз", "en": "Choose a video file from the lesson materials"},
    "Вставьте ссылку на видео YouTube или Vimeo": {"kk": "YouTube немесе Vimeo бейнесіне сілтеме қойыңыз", "en": "Paste a YouTube or Vimeo video link"},
    "Неверный тип задания для этого блока": {"kk": "Бұл блок үшін тапсырма түрі дұрыс емес", "en": "Wrong task type for this block"},
    "Добавьте хотя бы один вопрос": {"kk": "Кемінде бір сұрақ қосыңыз", "en": "Add at least one question"},
    "Не более {n} вопросов в блоке": {"kk": "Блокта {n} сұрақтан артық болмауы керек", "en": "No more than {n} questions per block"},
    "В этом блоке не бывает вопросов": {"kk": "Бұл блокта сұрақтар болмайды", "en": "This block has no questions"},
    "Раздел нельзя вложить в самого себя": {"kk": "Бөлімді өзіне салуға болмайды", "en": "A section can't be placed inside itself"},
    "Аудио не найдено": {"kk": "Аудио табылмады", "en": "Audio not found"},
    "Баллы за пропуск — от 1 до 20": {"kk": "Бір бос орын үшін ұпай — 1-ден 20-ға дейін", "en": "Points per gap: 1 to 20"},
    "Выберите аудиофайл": {"kk": "Аудиофайлды таңдаңыз", "en": "Choose an audio file"},
    "Выберите изображение из материалов теста": {"kk": "Тест материалдарынан суретті таңдаңыз", "en": "Choose an image from the test materials"},
    "Для аудиоблока нужен аудиофайл, для текста — изображение": {"kk": "Аудиоблокқа аудиофайл, мәтінге сурет қажет", "en": "An audio block needs an audio file, a reading text needs an image"},
    "Добавьте от 2 до 20 пар": {"kk": "2-ден 20-ға дейін жұп қосыңыз", "en": "Add 2 to 20 pairs"},
    "Добавьте текст для чтения": {"kk": "Оқуға арналған мәтінді қосыңыз", "en": "Add the reading text"},
    "Количество прослушиваний — от 1 до 10": {"kk": "Тыңдау саны — 1-ден 10-ға дейін", "en": "Number of listens: 1 to 10"},
    "Лимит прослушиваний исчерпан": {"kk": "Тыңдау шегі таусылды", "en": "No listens left"},
    "Не более 50 пропусков в задании": {"kk": "Тапсырмада 50-ден аспайтын бос орын", "en": "No more than 50 gaps per task"},
    "Неизвестный режим ответа": {"kk": "Жауап беру режимі белгісіз", "en": "Unknown answer mode"},
    "Отметьте пропуски: заключите правильный ответ в фигурные скобки": {"kk": "Бос орындарды белгілеңіз: дұрыс жауапты бұйра жақшаға алыңыз", "en": "Mark the gaps: put the correct answer in curly braces"},
    "Правые части пар должны различаться": {"kk": "Жұптардың оң жақтары әртүрлі болуы керек", "en": "The right-hand sides of the pairs must differ"},
    "Текст для чтения слишком длинный": {"kk": "Оқуға арналған мәтін тым ұзын", "en": "The reading text is too long"},
    "Текст задания слишком длинный": {"kk": "Тапсырма мәтіні тым ұзын", "en": "The task text is too long"},
    "У каждого пропуска должен быть правильный ответ": {"kk": "Әр бос орынның дұрыс жауабы болуы керек", "en": "Every gap needs a correct answer"},
    "Укажите баллы за вопрос": {"kk": "Сұрақ үшін ұпайды көрсетіңіз", "en": "Set the points for the question"},
    "Попытки закончились": {"kk": "Талпыныстар таусылды", "en": "No attempts left"},
    "Тест больше не назначен этому ученику": {"kk": "Бұл тест енді осы оқушыға тағайындалмаған", "en": "This test is no longer assigned to the student"},
    "Время на прохождение теста истекло": {"kk": "Тестке берілген уақыт бітті", "en": "Time for the test is up"},
    "Ученик ещё не завершил тест": {"kk": "Оқушы тестті әлі аяқтаған жоқ", "en": "The student has not finished the test yet"},
    "Ответ не относится к этой попытке": {"kk": "Жауап бұл әрекетке жатпайды", "en": "The answer does not belong to this attempt"},
    "Максимум за вопрос — {points} балл(ов)": {"kk": "Сұраққа ең көбі — {points} балл", "en": "Maximum for this question: {points} point(s)"},
    "Оцените все ответы, требующие проверки": {"kk": "Тексеруді қажет ететін барлық жауапты бағалаңыз", "en": "Grade all answers that need review"},
    "Вопросы нельзя изменить: тест уже начали проходить": {"kk": "Сұрақтарды өзгертуге болмайды: тестті тапсыру басталды", "en": "Questions can't be changed: students have already started the test"},
    "Материалы нельзя изменить: тест уже начали проходить": {"kk": "Материалдарды өзгертуге болмайды: тестті тапсыру басталды", "en": "Materials can't be changed: students have already started the test"},
    "Не более {n} файлов в тесте": {"kk": "Тестте {n} файлдан артық емес", "en": "No more than {n} files per test"},
    "Файл к вопросу не найден среди материалов теста": {"kk": "Сұраққа арналған файл тест материалдарынан табылмады", "en": "The question's file is not among the test materials"},
    "Для вопроса True/False укажите правильный ответ": {"kk": "Шын/Жалған сұрағы үшін дұрыс жауапты көрсетіңіз", "en": "Choose the correct answer for the true/false question"},
    "Добавьте минимум два варианта ответа": {"kk": "Кемінде екі жауап нұсқасын қосыңыз", "en": "Add at least two answer options"},
    "Идентификаторы вариантов должны быть уникальными": {"kk": "Нұсқа идентификаторлары бірегей болуы керек", "en": "Option ids must be unique"},
    "Отметьте правильный ответ": {"kk": "Дұрыс жауапты белгілеңіз", "en": "Mark the correct answer"},
    "В вопросе с одним ответом должен быть ровно один правильный вариант": {"kk": "Бір жауапты сұрақта дәл бір дұрыс нұсқа болуы керек", "en": "A single-answer question must have exactly one correct option"},
    "Дата открытия теста должна быть раньше срока сдачи": {"kk": "Тесттің ашылу күні тапсыру мерзімінен ерте болуы керек", "en": "The test must open before its due date"},
    # --- messages / notifications ---
    "Уведомление не найдено": {"kk": "Хабарландыру табылмады", "en": "Notification not found"},
    "Все уведомления прочитаны": {"kk": "Барлық хабарландырулар оқылды", "en": "All notifications marked as read"},
    "Сообщения доступны только преподавателям и ученикам": {"kk": "Хабарламалар тек оқытушылар мен оқушыларға қолжетімді", "en": "Messages are available to teachers and students only"},
    "Диалог не найден": {"kk": "Диалог табылмады", "en": "Conversation not found"},
    "Пользователь деактивирован — отправка сообщений недоступна": {"kk": "Пайдаланушы өшірілген — хабарлама жіберу мүмкін емес", "en": "The user is deactivated — messaging is unavailable"},
    "Сообщение не может быть пустым": {"kk": "Хабарлама бос болмауы керек", "en": "The message cannot be empty"},
    "Сообщение не может быть длиннее {n} символов": {"kk": "Хабарлама {n} таңбадан ұзын болмауы керек", "en": "The message cannot be longer than {n} characters"},
    "Выберите файл": {"kk": "Файлды таңдаңыз", "en": "Choose a file"},
    "Не более {n} файлов в одном сообщении": {"kk": "Бір хабарламада {n} файлдан артық емес", "en": "No more than {n} files per message"},
    "📎 {name}": {"kk": "📎 {name}", "en": "📎 {name}"},
    "📎 {name} и ещё {n}": {"kk": "📎 {name} және тағы {n}", "en": "📎 {name} and {n} more"},
    # --- file checks ---
    "Недопустимый формат файла «{name}». Разрешены: {allowed}": {"kk": "«{name}» файлының форматы рұқсат етілмеген. Рұқсат етілгендер: {allowed}", "en": "The file type of \"{name}\" is not allowed. Allowed: {allowed}"},
    "Файл «{name}» превышает {mb} МБ": {"kk": "«{name}» файлы {mb} МБ-тан үлкен", "en": "The file \"{name}\" is larger than {mb} MB"},
    "Файл «{name}» пустой": {"kk": "«{name}» файлы бос", "en": "The file \"{name}\" is empty"},
    "Содержимое файла «{name}» не соответствует расширению": {"kk": "«{name}» файлының мазмұны кеңейтімге сәйкес келмейді", "en": "The content of \"{name}\" doesn't match its extension"},
    "Файл «{name}» должен быть в кодировке UTF-8": {"kk": "«{name}» файлы UTF-8 кодтауында болуы керек", "en": "The file \"{name}\" must be UTF-8 encoded"},
    "Содержимое файла «{name}» не соответствует расширению .{ext}": {"kk": "«{name}» файлының мазмұны .{ext} кеңейтіміне сәйкес келмейді", "en": "The content of \"{name}\" doesn't match the .{ext} extension"},
    # --- notification texts ---
    "Новое домашнее задание": {"kk": "Жаңа үй тапсырмасы", "en": "New homework"},
    "Сдано домашнее задание": {"kk": "Үй тапсырмасы тапсырылды", "en": "Homework submitted"},
    "Домашнее задание проверено": {"kk": "Үй тапсырмасы тексерілді", "en": "Homework reviewed"},
    "Домашнее задание требует исправления": {"kk": "Үй тапсырмасы түзетуді қажет етеді", "en": "Homework needs corrections"},
    "{title} — оценка {grade}/{max}": {"kk": "{title} — баға {grade}/{max}", "en": "{title} — grade {grade}/{max}"},
    "Новый тест": {"kk": "Жаңа тест", "en": "New test"},
    "Тест пройден": {"kk": "Тест тапсырылды", "en": "Test completed"},
    "{name} завершил(а) тест «{title}»": {"kk": "{name} «{title}» тестін аяқтады", "en": "{name} completed the test \"{title}\""},
    "{name} завершил(а) тест «{title}» — требуется проверка": {"kk": "{name} «{title}» тестін аяқтады — тексеру қажет", "en": "{name} completed the test \"{title}\" — needs review"},
    "Результаты теста": {"kk": "Тест нәтижелері", "en": "Test results"},
    "Оценка за тест изменена": {"kk": "Тест бағасы өзгертілді", "en": "Test grade changed"},
    "Тест можно пройти ещё раз": {"kk": "Тестті қайта тапсыруға болады", "en": "You can take the test again"},
    "Занятие изменено": {"kk": "Сабақ өзгертілді", "en": "Lesson changed"},
    "Занятия отменены": {"kk": "Сабақтар болдырылмады", "en": "Lessons cancelled"},
    "Занятия изменены": {"kk": "Сабақтар өзгертілді", "en": "Lessons changed"},
    "«{title}»: занятий — {n}, начиная с {day}": {"kk": "«{title}»: {n} сабақ, {day} бастап", "en": "\"{title}\": {n} lessons starting {day}"},
    "Абонемент закончился": {"kk": "Абонемент аяқталды", "en": "Subscription ended"},
    "У ученика {name} закончился абонемент.": {"kk": "{name} оқушысының абонементі аяқталды.", "en": "{name}'s subscription has ended."},
    "Ваш абонемент закончился": {"kk": "Сіздің абонементіңіз аяқталды", "en": "Your subscription has ended"},
    "Обратитесь к преподавателю для продления.": {"kk": "Ұзарту үшін оқытушыға хабарласыңыз.", "en": "Contact your teacher to renew it."},
    "Абонемент скоро закончится": {"kk": "Абонемент жақында аяқталады", "en": "Subscription ends soon"},
    "У ученика {name} абонемент заканчивается через {n} дн.": {"kk": "{name} оқушысының абонементі {n} күннен кейін аяқталады.", "en": "{name}'s subscription ends in {n} day(s)."},
    "Осталось дней: {n}.": {"kk": "Қалған күндер: {n}.", "en": "Days left: {n}."},
    # --- attendance CSV ---
    "Дата ({tz})": {"kk": "Күні ({tz})", "en": "Date ({tz})"},
    "Время ({tz})": {"kk": "Уақыты ({tz})", "en": "Time ({tz})"},
    "Ученик": {"kk": "Оқушы", "en": "Student"},
    "Занятие": {"kk": "Сабақ", "en": "Lesson"},
    "Статус занятия": {"kk": "Сабақ мәртебесі", "en": "Lesson status"},
    "Посещаемость": {"kk": "Қатысу", "en": "Attendance"},
    "Комментарий": {"kk": "Пікір", "en": "Comment"},
    "Запланировано": {"kk": "Жоспарланған", "en": "Scheduled"},
    "Проведено": {"kk": "Өткізілді", "en": "Completed"},
    "Отменено": {"kk": "Болдырылмады", "en": "Cancelled"},
    "Присутствовал": {"kk": "Қатысты", "en": "Present"},
    "Отсутствовал": {"kk": "Қатыспады", "en": "Absent"},
    "Опоздал": {"kk": "Кешікті", "en": "Late"},
    "Уважительная причина": {"kk": "Дәлелді себеп", "en": "Excused"},
    "Не отмечено": {"kk": "Белгіленбеген", "en": "Not marked"},
}


# ---------------------------------------------------------------------------
# Built-in Pydantic messages (they come in English) by error type
# ---------------------------------------------------------------------------
PYDANTIC: dict[str, dict[str, str]] = {
    "missing": {"ru": "Обязательное поле", "kk": "Міндетті өріс", "en": "This field is required"},
    "string_too_short": {"ru": "Слишком короткое значение (минимум {min_length})", "kk": "Тым қысқа мән (кемінде {min_length})", "en": "Too short (at least {min_length})"},
    "string_too_long": {"ru": "Слишком длинное значение (максимум {max_length})", "kk": "Тым ұзын мән (ең көбі {max_length})", "en": "Too long (at most {max_length})"},
    "too_short": {"ru": "Слишком мало элементов (минимум {min_length})", "kk": "Элементтер тым аз (кемінде {min_length})", "en": "Too few items (at least {min_length})"},
    "too_long": {"ru": "Слишком много элементов (максимум {max_length})", "kk": "Элементтер тым көп (ең көбі {max_length})", "en": "Too many items (at most {max_length})"},
    "greater_than": {"ru": "Значение должно быть больше {gt}", "kk": "Мән {gt}-ден үлкен болуы керек", "en": "Must be greater than {gt}"},
    "greater_than_equal": {"ru": "Значение должно быть не меньше {ge}", "kk": "Мән {ge}-ден кем болмауы керек", "en": "Must be at least {ge}"},
    "less_than": {"ru": "Значение должно быть меньше {lt}", "kk": "Мән {lt}-ден кіші болуы керек", "en": "Must be less than {lt}"},
    "less_than_equal": {"ru": "Значение должно быть не больше {le}", "kk": "Мән {le}-ден аспауы керек", "en": "Must be at most {le}"},
    "string_pattern_mismatch": {"ru": "Недопустимое значение", "kk": "Рұқсат етілмеген мән", "en": "Invalid value"},
    "value_error.email": {"ru": "Введите корректный email", "kk": "Дұрыс email енгізіңіз", "en": "Enter a valid email"},
    "int_parsing": {"ru": "Введите целое число", "kk": "Бүтін сан енгізіңіз", "en": "Enter a whole number"},
    "int_from_float": {"ru": "Введите целое число", "kk": "Бүтін сан енгізіңіз", "en": "Enter a whole number"},
    "float_parsing": {"ru": "Введите число", "kk": "Сан енгізіңіз", "en": "Enter a number"},
    "bool_parsing": {"ru": "Некорректное значение", "kk": "Мән дұрыс емес", "en": "Invalid value"},
    "date_from_datetime_parsing": {"ru": "Некорректная дата", "kk": "Күні дұрыс емес", "en": "Invalid date"},
    "date_parsing": {"ru": "Некорректная дата", "kk": "Күні дұрыс емес", "en": "Invalid date"},
    "datetime_parsing": {"ru": "Некорректные дата и время", "kk": "Күні мен уақыты дұрыс емес", "en": "Invalid date and time"},
    "datetime_from_date_parsing": {"ru": "Некорректные дата и время", "kk": "Күні мен уақыты дұрыс емес", "en": "Invalid date and time"},
    "enum": {"ru": "Недопустимое значение", "kk": "Рұқсат етілмеген мән", "en": "Invalid value"},
    "literal_error": {"ru": "Недопустимое значение", "kk": "Рұқсат етілмеген мән", "en": "Invalid value"},
    "url_parsing": {"ru": "Некорректная ссылка", "kk": "Сілтеме дұрыс емес", "en": "Invalid link"},
    "json_invalid": {"ru": "Некорректные данные", "kk": "Деректер дұрыс емес", "en": "Invalid data"},
}


def validation_message(error: dict, lang: str) -> str:
    """Readable message for one Pydantic error in the given language."""
    lang = norm_lang(lang)
    kind = str(error.get("type", ""))
    msg = str(error.get("msg", "Некорректные данные"))
    if kind == "value_error":
        text = msg.removeprefix("Value error, ")
        if "email address" in text or "@-sign" in text:
            return PYDANTIC["value_error.email"][lang]
        return tr(text, lang)  # our own ValueError texts are Russian templates
    if kind in PYDANTIC:
        ctx = {k: v for k, v in (error.get("ctx") or {}).items()}
        try:
            return PYDANTIC[kind][lang].format(**ctx)
        except (KeyError, IndexError, ValueError):
            return PYDANTIC[kind][lang]
    return tr("Некорректные данные", lang)
