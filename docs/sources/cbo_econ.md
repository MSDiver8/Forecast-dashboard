# CBO, Economic Projections (рост реального ВВП США)

- **Роль:** прогноз для «Реальный ВВП США».
- **Источник файлов:** открытый репозиторий CBO на GitHub — https://github.com/US-CBO/cbo-data (organisation US-CBO). README: «Standardized, versioned data from public CBO releases… The canonical source of data remains Budget and Economic Data». Сайт cbo.gov 13 октября 2026 отвечал 403 автоматическим клиентам; обходить защиту не стали.
- **Список выпусков:** `https://raw.githubusercontent.com/US-CBO/cbo-data/main/catalog.json`, набор `economic_projections`, файлы `file_type: quarterly` с полем `vintage` (`2024-02`, `2024-06`, `2025-01`, `2025-09`, `2026-02`).
- **Файл:** `…/data/economic/economic_projections/quarterly_<YYYY-MM>.csv` (≈50–370 КБ): столбцы `date` (`2026q1`), `variable`, `value`, `estimate_type` (`actual` / `projected`). Берём `real_gdp_pct_change` — по `schema.json` «Real GDP, percentage change (annual rate)», т. е. рост к предыдущему кварталу в годовом выражении.
- **Граница факт/прогноз:** `estimate_type` из файла. Прогноз на кварталы раньше месяца выпуска (в выпуске 02.2026 — III–IV кв. 2025 из-за задержки данных BEA) хранится как оценка.
- **Даты:** в репозитории только месяц выпуска; винтаж — первое число месяца, в названии «≈».
- **Глубина:** около 2 лет (правило ТЗ): выпуски 01.2025, 09.2025, 02.2026; ещё два (02.2024, 06.2024) доступны.
- **Лицензия:** общественное достояние (LICENSE.md репозитория: «As a work of the United States Government, these materials are in the public domain… 17 U.S.C. § 105»).
- **Образцы:** `tests/fixtures/cbo_econ/quarterly_2026-02.csv` (строки `real_gdp_pct_change` и `real_gdp`), `catalog-excerpt.json`.
