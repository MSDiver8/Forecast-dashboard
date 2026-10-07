# Forecast Dashboard

Локальное приложение: опубликованные прогнозы разных организаций с винтажами, факт и бенчмарк-модели на одном графике и в одной таблице. ТЗ — `docs/SPEC.md`, паспорта источников — `docs/sources/`.

## Запуск

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
- `uv run fdash rebuild` — пересобрать базу из `data/raw/` без сети;
- `uv run pytest`, `uv run ruff check . && uv run ruff format .` — тесты и проверка кода.

Во время `ingest` сервер нужно остановить: DuckDB допускает одного пишущего.

Разработка интерфейса: `uv run fdash serve` и в другом терминале `cd web && npm run dev` (http://localhost:5173, запросы `/api` проксируются на 8100).

## Папка проекта в iCloud

Если проект лежит в «Документах», которые синхронизирует iCloud, iCloud помечает файлы внутри `.venv` как скрытые, и Python 3.12 перестаёт видеть установленный пакет («No module named fdash»). Решение — держать окружение вне iCloud:

```bash
export UV_PROJECT_ENVIRONMENT="$HOME/.local/share/fdash/venv"
```

(добавить в `~/.zshrc` или задавать перед командами `uv`). `web/node_modules` — ссылка на `web/node_modules.nosync`: папки с суффиксом `.nosync` iCloud не синхронизирует.

## Ключи API

Ключи (если понадобятся, например EIA) — только в `.env` в корне проекта; файл не попадает в git.
