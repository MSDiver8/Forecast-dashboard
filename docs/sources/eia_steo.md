# EIA Short-Term Energy Outlook

- **Организация:** U.S. Energy Information Administration.
- **Страница выпусков:** https://www.eia.gov/outlooks/steo/outlook.php — таблица архива: месяц выпуска, дата публикации (MM/DD/YYYY), PDF и XLSX. Текущий выпуск — строка «Release Date:» в шапке страницы.
- **Файл выпуска:** `https://www.eia.gov/outlooks/steo/archives/<mon><yy>_base.xlsx` (например, `oct26_base.xlsx`), ≈1 МБ. Проверено 7 октября 2026: ответ 200, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Каталог `archives/` без имени файла отдаёт 403.
- **Структура:** лист `Dates`: D1 — месяц выпуска, D2 — дата завершения расчётов, D7 — последний фактический месяц (`YYYYMM`). Лист `2tab`: строка с кодом `BREPUUS` в столбце A (Brent Spot Average, долл./барр.), строка 3 — годы, строка 4 — месяцы, данные с столбца C; горизонт ≈ 6 лет помесячно. Структура совпадает в выпусках октября 2024 и октября 2026.
- **Частота:** только месячные значения. Годовые и квартальные средние в XLSX не публикуются; ядро считает их как среднее 12 (3) месяцев одного выпуска.
- **Винтажи:** ежемесячно, каждый выпуск — отдельный файл; архив с 2014 года. Загружаем выпуски за последние 2 года.
- **Факт внутри выпуска:** месяцы до D7 включительно — `kind = actual` (факт, как он был известен на дату выпуска), позже — `forecast`.
- **Лимиты:** не указаны; запросов немного (один файл на выпуск).
- **Лицензия:** данные EIA — общественное достояние США (public domain), https://www.eia.gov/about/copyrights_reuse.php.
- **Образцы:** `tests/fixtures/eia_steo/outlook.html`, `tests/fixtures/eia_steo/oct26_base.xlsx`.
