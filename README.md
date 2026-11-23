# Куди підемо?

Telegram-бот із Mini App для пари. Кожен відмічає, що йому подобається, а застосунок підбирає побачення за вподобаннями партнера, прогнозом погоди і спільним списком бажань. У четвер бот надсилає три ідеї на вихідні.

## Що вміє

- Пара з'єднується через посилання-запрошення.
- Вподобання: 26 категорій, у кожній «обожнюю», «можна» або «не моє».
- Квиток-ідея з фільтрами за бюджетом, місцем і часом. Категорії з «не моє» ніколи не випадають.
- Погода з Open-Meteo: якщо на обрану дату дощ від 60%, мороз від −5° або спека від +32°, ідеї надворі відсуваються.
- Спільний список бажань. Його пункти теж потрапляють у квитки.
- Історія побачень з оцінками 👍/👎. Категорії, які сподобались, випадають частіше.
- Нагадування щочетверга о 18:00 за Києвом (взимку; влітку о 19:00), вимикається командою /remind.

## Стек

Django 5, PostgreSQL (Neon), Telegram Bot API через webhook, Mini App на чистому JS, хостинг Render (free), розклад через GitHub Actions.

```
config/            налаштування Django
dates/
  models.py        Couple, Member, Preference, Wish, DateEvent
  ideas.py         категорії та 48 ідей
  picker.py        вибір ідеї з вагами
  weather.py       прогноз Open-Meteo
  telegram.py      перевірка initData, виклики Bot API
  bot.py           команди бота
  views.py         webhook, JSON API, нагадування
  templates/dates/app.html   Mini App
  tests.py         21 тест
.github/workflows/weekly.yml  нагадування в четвер
```

## Запуск у продакшн

Знадобляться акаунти на GitHub, Render і Neon. На Render і Neon можна увійти через GitHub. Картка не потрібна.

### 1. Створи бота

1. Напиши [@BotFather](https://t.me/BotFather) команду `/newbot`.
2. Придумай назву і username, що закінчується на `bot`.
3. Збережи токен виду `123456:ABC...` і username.

### 2. Створи базу в Neon

1. На [neon.com](https://neon.com) натисни **New Project**, регіон обери **Frankfurt** (найближчий до Києва).
2. На сторінці проєкту натисни **Connect** і скопіюй рядок підключення. Він починається з `postgresql://` і закінчується на `?sslmode=require`.

### 3. Залий код на GitHub

```bash
cd date-bot
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/GreedyClark/date-bot.git
git push -u origin main
```

Спершу створи порожній репозиторій `date-bot` на GitHub.

### 4. Згенеруй секрети

Запусти тричі, щоб отримати три різні рядки:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Це будуть `WEBHOOK_SECRET`, `CRON_SECRET` і `DJANGO_SECRET_KEY`.

### 5. Розгорни на Render

1. На [render.com](https://render.com) натисни **New → Web Service** і підключи репозиторій `date-bot`.
2. Заповни поля:
   - **Language:** Python 3
   - **Build Command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - **Start Command:** `python manage.py migrate --noinput && gunicorn config.wsgi --bind 0.0.0.0:$PORT`
   - **Instance Type:** Free
3. У розділі **Environment Variables** додай:

| Змінна | Значення |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен від BotFather |
| `TELEGRAM_BOT_USERNAME` | username бота без `@` |
| `DATABASE_URL` | рядок підключення з Neon |
| `WEBHOOK_SECRET` | перший секрет |
| `CRON_SECRET` | другий секрет |
| `DJANGO_SECRET_KEY` | третій секрет |
| `PUBLIC_URL` | поки залиш порожнім |

4. Натисни **Deploy**. Render покаже адресу виду `https://date-bot-xxxx.onrender.com`.
5. Впиши цю адресу в `PUBLIC_URL` (без `/` у кінці) і збережи. Render перезапустить сервіс.
6. Перевір: `https://date-bot-xxxx.onrender.com/health/` має показати `ok`.

### 6. Підключи webhook

Це робиться один раз зі свого комп'ютера:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Заповни `.env` тими самими значеннями, що й на Render, і запусти:

```bash
python manage.py set_webhook
```

Команда реєструє webhook, список команд і кнопку «Куди підемо?» біля поля вводу в чаті з ботом.

### 7. Увімкни нагадування

У репозиторії на GitHub відкрий **Settings → Secrets and variables → Actions → New repository secret** і додай:

- `PUBLIC_URL` — адреса з Render
- `CRON_SECRET` — другий секрет

Перевір вручну: **Actions → Нагадування в четвер → Run workflow**. Якщо ви вже в парі, бот надішле ідеї.

### 8. Перевір

1. Напиши боту `/start`. Він надішле посилання-запрошення.
2. Перешли посилання дівчині. Коли вона натисне **Start**, бот повідомить вам обом, що ви в парі.
3. Відкрийте застосунок кнопкою меню і відмітьте вподобання.

## Адмінка

Render free не дає консолі, тому адміна створюй локально, з `DATABASE_URL` від Neon у `.env`:

```bash
python manage.py createsuperuser
```

Адмінка відкривається за адресою `https://date-bot-xxxx.onrender.com/admin/`.

## Локальна розробка

```bash
python manage.py migrate
python manage.py test dates
python manage.py runserver
```

Без `DATABASE_URL` проєкт використовує SQLite. Telegram відкриває Mini App лише через HTTPS, тому для перевірки в самому Telegram потрібен тунель:

```bash
cloudflared tunnel --url http://localhost:8000
```

Встав видану адресу в `PUBLIC_URL` у `.env`, додай її хост у `PUBLIC_HOST` і знову запусти `python manage.py set_webhook`. Коли закінчиш, повтори `set_webhook` з адресою Render.

## Обмеження безкоштовного тарифу

- Render присипляє сервіс після 15 хвилин тиші. Перша відповідь після сну приходить приблизно за хвилину, далі все працює швидко.
- GitHub Actions іноді запускає розклад із запізненням на 10–30 хвилин.
- Neon Free дає 1 GB на проєкт. Для двох людей цього вистачить на роки.

## Як працює підбір

Кожна ідея отримує вагу: «обожнюю» — 6, «можна» — 2, без позначки — 0.7, «не моє» — ідея не потрапляє в пул. Бажання зі спільного списку мають вагу 5. Оцінка 👍 множить вагу категорії на 1.3, 👎 на 0.7. Ідеї з останніх п'яти побачень і ідеї надворі в погану погоду отримують маленький множник. Потім `random.choices` вибирає одну ідею з урахуванням ваг.
