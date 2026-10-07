# МВФ, World Economic Outlook

- **API:** `https://api.imf.org/external/sdmx/2.1/` (SDMX 2.1 REST, без ключа). Также есть SDMX 3.0 (`/external/sdmx/3.0/`). Проверено 7 октября 2026.
- **Наборы:** `IMF.RES,WEO` — текущий выпуск (на 7 октября 2026 — апрель 2026, `PUBLICATION_DATE = 2026-04-14`); прошлые выпуски — отдельные наборы `WEO_<YYYY>_<MON>_VINTAGE` (на 7 октября 2026 есть только `WEO_2025_OCT_VINTAGE`, `PUBLICATION_DATE = 2025-10-14`). Список наборов: `…/sdmx/2.1/dataflow`.
- **Запрос:** `…/data/IMF.RES,<dataflow>/<COUNTRY>.<INDICATOR>.A?startPeriod=2015`, заголовок `Accept: application/vnd.sdmx.data+csv;version=1.0.0`. Измерения: `COUNTRY.INDICATOR.FREQUENCY`. Параметр `includeHistory=true` прошлых версий не отдаёт.
- **Показатели:** `NGDP_RPCH` — рост реального ВВП, % г/г; `PCPIPCH` — инфляция, средние цены, % к пред. году; `PCPIEPCH` — инфляция на конец периода (декабрь к декабрю); `LUR` — безработица, % рабочей силы.
- **Страны:** `RUS, USA, DEU, FRA, ITA, ESP, GBR, JPN, CHN`, агрегаты `G001` (мир), `G163` (еврозона).
- **Индекс цен:** атрибут `PRICES_SECTOR_HARMONIZED_PRICES` — `Yes` (HICP) у еврозоны, Германии, Франции, Италии, Испании, Великобритании; `No` (национальный ИПЦ) у США, Японии, Китая, России.
- **Факт и прогноз:** атрибут `LATEST_ACTUAL_ANNUAL_DATA` (последний фактический год по стране); годы до него включительно — `estimate`, позже — `forecast`. У агрегатов атрибут пустой — граница берётся как год публикации минус 1.
- **Архив до октября 2025.** Файлы базы WEO лежат на `https://www.imf.org/en/Publications/WEO/weo-database/<YYYY>/<Month>`, но 7 октября 2026 сайт отвечал 403 на все запросы (включая страницы апреля 2025, октября 2024 и октября 2021). Глубина 5 лет пока недоступна: 2 выпуска.
- **Лицензия:** IMF Copyright and Usage, бесплатное использование с указанием источника (https://www.imf.org/en/About/copyright-and-terms).
- **Образцы:** `tests/fixtures/imf_weo/`.
