# TD Economics, Quarterly Economic Forecast (рост реального ВВП США)

- **Роль:** прогноз для «Реальный ВВП США». **PDF — исключение из правила ТЗ, согласовано заказчиком 13 октября 2026.**
- **Страница:** https://economics.td.com/us-quarterly-economic-forecast — ссылка только на последний выпуск (сентябрь 2026: `…/documents/reports/qef/2026-sep/QEF_September2026_US.pdf`). Архива и sitemap нет (404).
- **Прошлые выпуски** находятся по папкам и именам, которые использовал TD (сервер не различает регистр): папка `<YYYY>-<mon>` или `<YYYY>-<month>`, файл `QEF_<Month><YYYY>_US.pdf`, `QEF<Month><YYYY>_US.pdf`, `qef<mon><YYYY>_us.pdf` или `QEF_<mon><YYYY>_US.pdf`. Проверено 13 октября 2026: 2024-dec/qefdec2024_us.pdf, 2025-mar/qefmar2025_us.pdf, 2025-jun/qefjun2025_us.pdf, 2025-sep/QEF_sep2025_US.pdf, 2025-dec/QEF_dec2025_US.pdf, 2026-mar/QEF_March2026_US.pdf, 2026-june/QEF_June2026_US.pdf, 2026-sep/QEF_September2026_US.pdf; сентябрь 2024 не найден.
- **Ограничение:** в выпусках до сентября 2025 года включительно таблица по США — изображение без текстового слоя. Распознавание изображений не используем, эти выпуски не загружаются; загружаются с декабря 2025 года (4 выпуска).
- **Таблица:** страница «U.S. Economic Outlook», подзаголовок «Period-Over-Period Annualized Per Cent Change Unless Otherwise Indicated». Строка лет (`2026 2027 2028 …`), строка кварталов `Q1 Q2 Q3F Q4F …` (F — прогноз), строка `Real GDP` — первые 12 чисел (дальше — годовые средние и Q4/Q4).
- **Граница факт/прогноз:** все кварталы после первого с пометкой F — прогноз (в выпуске сентября 2026 у I кв. 2027 F пропущена). Прогноз на квартал раньше квартала выпуска хранится как оценка.
- **Дата выпуска:** первая дата в тексте первых страниц («September 17, 2026»).
- **Оговорка источника:** «This report is provided by TD Economics. It is for informational and educational purposes only…».
- **Лицензия:** публичная публикация; используем со ссылкой на источник.
- **Образцы:** `tests/fixtures/td_economics/QEF_September2026_US-pages-1-5.pdf` (страницы 1 и 5 выпуска), `us-quarterly-economic-forecast-excerpt.html`.
