# Freelance Radar Bot

Telegram-бот «Ловец жирных заказов» — агрегатор фриланс-заказов с мгновенными уведомлениями, генерацией отклика через GigaChat, оплатой подписки через ЮKassa и мини-приложением в стиле 2025–2026.

## Что умеет MVP
- Выбор категорий (`Design`, `Python`) в Telegram.
- Мониторинг источников (HH API, Habr RSS, Telegram RSS + расширяемые адаптеры Kwork/FL).
- Мгновенные уведомления о новых заказах.
- Кнопка «Сгенерировать отклик» (GigaChat).
- 3 дня бесплатного триала.
- Подписка 690₽/мес через ЮKassa.
- Мини-приложение (`index.html`) для Telegram WebApp.
- Команды `/start`, `/menu`, `/status` + inline-кнопки в уведомлениях (отклик, открыть заказ).

## Локальный запуск
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

## Переменные окружения
См. `.env.example`.

Критично обязательно задать:
- `BOT_TOKEN`
- `PUBLIC_BASE_URL`
- `YOOKASSA_SHOP_ID`
- `YOOKASSA_SECRET_KEY`
- `YOOKASSA_RETURN_URL`
- `GIGACHAT_API_KEY`

## Деплой на Railway (пошагово)
1. Залей проект в GitHub (см. следующий раздел).
2. В Railway: **New Project → Deploy from GitHub repo**.
3. Railway увидит `Procfile` и запустит команду `python -m app.main`.
4. В `Variables` добавь все значения из `.env.example`.
5. `PUBLIC_BASE_URL` укажи как выданный Railway домен, например:
   - `https://freelance-radar-production.up.railway.app`
6. Для ЮKassa webhook укажи URL:
   - `https://<your-domain>/webhook/yookassa`
7. Проверь health endpoint:
   - `GET /` должен вернуть `{"ok": true, "service": "freelance-radar"}`.


## Что сделать в Telegram после деплоя
1. Открой бота и отправь `/start` — появятся кнопки категорий, PRO и мини-приложения.
2. Если кнопки пропали, отправь `/menu` — меню будет показано снова.
3. Проверка статуса подписки: `/status`.

## Как отправить проект в GitHub
Если репозиторий ещё не связан с GitHub:
```bash
git init
git add .
git commit -m "feat: freelance radar bot"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

Если remote уже есть:
```bash
git add .
git commit -m "chore: update deployment docs"
git push
```

## Важно
Некоторые биржи не дают открытый API. Поэтому `KworkSource` и `FLSource` в MVP — расширяемые заглушки, чтобы легально и безопасно расширять интеграции дальше.
