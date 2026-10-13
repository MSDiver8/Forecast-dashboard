# Fannie Mae, Economic Forecast (рост реального ВВП США)

- **Роль:** прогноз для «Реальный ВВП США». **PDF — исключение из правила ТЗ, согласовано заказчиком 13 октября 2026.**
- **Файл:** `https://www.fanniemae.com/media/document/pdf/economic-forecast-<MM><YYYY>` — переадресация 301 на `https://www.fanniemae.com/media/<id>/display` (PDF ≈75–170 КБ). Проверено 13 октября 2026: есть все месяцы с октября 2024 по сентябрь 2026, октябрь 2026 — 404 (ещё не вышел). Архив: https://www.fanniemae.com/data-and-insights/forecast/forecast-monthly-archive.
- **Таблица:** страница 1, текстовый слой. Признаки: «Quarterly SAAR», «Shaded areas denote forecasts». 12 квартальных столбцов `YY.Q` (например, `25.1` … `27.4`), строка «Gross Domestic Product» — первые 12 чисел (дальше — годовые). Прогнозные кварталы — столбцы с цветной заливкой (прямоугольники PDF под строкой ВВП).
- **Дата выпуска:** первая дата в тексте страницы («September 11, 2026»).
- **Граница факт/прогноз:** заливка; затенённый квартал раньше квартала выпуска (например, III кв. 2024 в выпуске 10.10.2024 — до первой оценки BEA) хранится как оценка.
- **Глубина:** около 2 лет (правило ТЗ): 25 выпусков с сентября 2024 года.
- **Оговорка источника:** «Opinions, analyses, estimates, forecasts… of Fannie Mae's Economic and Strategic Research (ESR) Group … should not be construed as indicating Fannie Mae's business prospects or expected results».
- **Лицензия:** публичная публикация; используем со ссылкой на источник.
- **Образцы:** `tests/fixtures/fannie_mae/economic-forecast-092026.pdf`, `economic-forecast-102024.pdf`.
