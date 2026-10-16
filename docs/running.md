# Запуск и обновление данных

Нужны Python 3.12 (uv скачает сам), [uv](https://docs.astral.sh/uv/) и Node.js 20+.

```bash
uv sync                      # зависимости Python
uv run fdash ingest --all    # скачать выпуски всех источников и загрузить в базу
cd web && npm install && npm run build && cd ..   # собрать интерфейс
uv run fdash serve           # http://127.0.0.1:8100
```

Другие команды:

- `uv run fdash status` — сколько выпусков у каждого источника и итог последней загрузки;
- `uv run fdash ingest eia_steo cbr_survey` — обновить отдельные источники;
- `uv run fdash rebuild` — пересобрать базу из `data/raw/` без обращения к источникам;
- `uv run pytest`, `uv run ruff check . && uv run ruff format .` — тесты и проверка кода.

Во время `ingest` сервер нужно остановить: DuckDB допускает один пишущий процесс.

Разработка интерфейса: `uv run fdash serve` и в другом терминале `cd web && npm run dev` (http://localhost:5173, запросы `/api` проксируются на порт 8100).

Ключи API, если понадобятся, хранятся только в файле `.env` в корне проекта; в git он не попадает.

Сайт Росстата открывается по TLS с сертификатом Минцифры; сертификаты лежат в `src/fdash/ingest/certs/` и подключаются только для запросов к Росстату.
