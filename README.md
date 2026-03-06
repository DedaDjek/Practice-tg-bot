## ⚙️ Конфигурация (.env)

Файл `.env` создается в корневой директории проекта и содержит настройки для запуска приложения.

**Параметры базы данных:**
- `DB_HOST` - хост PostgreSQL (пример: localhost)
- `DB_PORT` - порт PostgreSQL (пример: 5432)  
- `DB_NAME` - название базы данных (пример: tgbot_db)
- `DB_USER` - пользователь базы данных (пример: postgres)
- `DB_PASSWORD` - пароль пользователя (пример: your_secure_password)

**Параметры Telegram бота:**
- `TELEGRAM_BOT_TOKEN` - токен бота от @BotFather (пример: 7166543533:AAF_pcGKWZ_iW4xYzAbCdEfGhIjKlMnOpQrStU)
- `TELEGRAM_ADMIN_IDS` - ID администраторов через запятую (пример: 12345678,87654321)

**Параметры файлов:**
- `DOWNLOAD_PATH` - папка для сохранения файлов (пример: downloads, по умолчанию downloads)
- `BASE_URL` - для скачивания файлов (пример: http://localhost:8000)

**Параметры Yandex GPT**
- `YANDEX_API_KEY` - API-ключ для доступа к Yandex GPT (пример: AQVN1HHJReSrfo9jU3aopsXrJyfq_UHs)
- `YANDEX_FOLDER_ID` - идентификатор каталога в Yandex Cloud (пример: b1gd129pp9ha)
- `YANDEX_MODEL` - модель Yandex GPT (пример: yandexgpt-lite, по умолчанию yandexgpt-lite)