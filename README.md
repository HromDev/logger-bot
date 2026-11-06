# HromAssistant Server Logger

Самостоятельный Discord-бот для журналирования событий сервера на `disnake`.
Проект не зависит от основного бота, MySQL или его конфигурации.

## Возможности

- Голосовые входы, выходы, переходы и перемещения с сопоставлением записей аудита.
- Различает самостоятельное выключение микрофона/звука и действия модератора.
- Отдельные события для mute/deaf, камеры, трансляций, сцен и запросов слова.
- Выдача и снятие ролей, действия журнала аудита Discord.
- Вход/выход участников, редактирование и удаление сообщений, реакции, опросы,
  AutoMod и подписки на события сервера.
- Отдельный канал назначения для каждого действия.
- Иконки действий из эмодзи приложения Discord.
- Components V2; содержимое и оформление собраны в одном cog.

Список действий, ключей маршрутизации и имён эмодзи находится в
[`docs/ACTIONS.md`](docs/ACTIONS.md).

## Требования

- Python 3.10 или новее.
- Discord application с созданным bot user.
- Права бота на целевом сервере:
  - View Channels
  - Send Messages
  - View Audit Log
- В Discord Developer Portal включите privileged intents:
  - **Server Members Intent**
  - **Message Content Intent**

Используются intents голосовых событий, реакций, опросов, запланированных
событий и AutoMod. Пригласите бота OAuth2 scope `bot`. Для эмодзи приложения
отдельное право `Use External Emojis` не требуется.

## Установка

Из папки `server_logger_bot`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Откройте `.env` и задайте:

- `DISCORD_TOKEN` — bot token из Developer Portal.
- `LOG_CHANNEL_DEFAULT` — ID канала, куда отправлять логи по умолчанию.
- `LOG_CHANNEL_OVERRIDES` — необязательный JSON-словарь отдельных каналов.

Включите Developer Mode в Discord, затем скопируйте ID нужного канала через
контекстное меню **Copy Channel ID**.

Пример настройки отдельных маршрутов:

```dotenv
LOG_CHANNEL_DEFAULT=123456789012345678
LOG_CHANNEL_OVERRIDES='{"voice_join":234567890123456789,"member_role_update":345678901234567890}'
```

Ключи можно посмотреть в [`docs/ACTIONS.md`](docs/ACTIONS.md). Все действия,
не указанные в `LOG_CHANNEL_OVERRIDES`, отправляются в канал по умолчанию.

Запуск:

```powershell
python main.py
```

На Linux/macOS активируйте окружение командой
`source .venv/bin/activate`; остальные команды те же.

## Иконки заголовков

Архив [`assets/server_log_icons.zip`](assets/server_log_icons.zip) содержит
PNG-файлы, манифесты, инструкцию и лицензию набора Lucide. Распакуйте его и
загрузите нужные PNG в Developer Portal → приложение → **Emojis**. Сохраняйте
имя файла без `.png`, например `log_voice_join`. Бот получает application
emojis через API и использует соответствующий значок в заголовке. Для
специфичных voice/role событий используйте все 92 PNG из архива.

## Заметки

- Бот не хранит сообщения или события в базе; логи отправляются в Discord.
- Для чтения аудита требуется `View Audit Log`. Без этого права Gateway-события
  продолжают работать, но исполнитель административного действия может быть
  неизвестен.
- Discord объединяет некоторые записи аудита. Для голосовых перемещений код
  сопоставляет Gateway-события с изменениями счётчика audit-log.
- Токен храните только в локальном `.env`. Не публикуйте его, логи с секретами
  или рабочий `.env` в GitHub.

## Разработка

Запуск встроенных тестов:

```powershell
python -m unittest discover -s tests
```

