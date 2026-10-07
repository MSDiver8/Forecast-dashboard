# ЕЦБ, Macroeconomic Projection Database (MPD): предпосылка по нефти

- **API:** ECB Data Portal, SDMX 2.1 REST, без ключа. Набор `MPD`, структура `ECB_MPD1`, измерения: `FREQ.REF_AREA.PD_ITEM.SERIES_DENOM.PD_SEAS_EX.PD_ORIGIN`.
- **Ряд:** `PD_ITEM = POU` («Price and cost developments — oil price assumption»), `REF_AREA = A1` (мир), `SERIES_DENOM = U` (доллар США), `PD_ORIGIN = 0000`. Частоты `A` и `Q`.
- **Выпуск (раунд):** `PD_SEAS_EX`: `W26` — Winter/March 2026, `G26` — Spring/June, `S26` — Summer/September, `A25` — Autumn/December 2025. Запрос раунда: `https://data-api.ecb.europa.eu/service/data/MPD/A+Q.A1.POU.U.S26.0000?format=csvdata`. Список раундов: `…/MPD/..POU...?format=csvdata&detail=serieskeysonly`.
- **Определение.** В атрибутах ряда марка не указана. Подтверждение — в тексте прогноза ЕЦБ за сентябрь 2026 (https://www.ecb.europa.eu/press/projections/html/ecb.projections202609_ecbstaff~8e340fc69d.en.html): «Oil prices refer to Brent crude oil spot and futures prices», «Oil price assumption (USD/barrel)». Годовые значения — средние за год, квартальные — за квартал. Это рыночная предпосылка (фьючерсы), а не собственный прогноз ЕЦБ.
- **Исторические значения в раунде** чуть отличаются от EIA RBRTE (2022: 102.3 против 100.9; 2025: 69.1 против 69.1) — другой источник спот-цены; в базе они помечены `estimate`.
- **Дата выпуска:** страница https://www.ecb.europa.eu/press/projections/html/index.en.html показывает 5 последних раундов с датами публикации (дата идёт после ссылки: 202606 → 11 June 2026). Более ранние список подгружает скриптом; для них дата приблизительная — 15-е число месяца раунда, в названии выпуска пометка «≈».
- **Лимиты и сбои:** 7 октября 2026 широкие запросы (`detail=serieskeysonly` по всему набору) и отдельные запросы ряда временами возвращали 504 «We are experiencing some problems»; повтор через 20 с проходил.
- **Лицензия:** статистика ЕЦБ, повторное использование с указанием источника (https://www.ecb.europa.eu/home/disclaimer/html/index.en.html).
- **Образцы:** `tests/fixtures/ecb_mpd/`.

## Прогноз по еврозоне (`ecb_mpd_macro`)

- **Ряды** того же набора MPD и тех же раундов: `A.U2.YER.A` — рост реального ВВП, % г/г (`UNIT = PCCH`); `A.U2.HIC.A` — HICP, % к пред. году; `A.U2.URX.F` — безработица, % рабочей силы. `U2` — еврозона в меняющемся составе. Отдельных стран в MPD по этим показателям нет (проверено на раунде S26: есть только `U2` и `U4`).
- **Отличия от МВФ:** рост ВВП ЕЦБ считает по данным с поправкой на число рабочих дней, МВФ — по годовым данным без поправки; состав еврозоны — «меняющийся» у ЕЦБ, у МВФ — текущий. Расхождения обычно в десятых долях процента; вынесено заказчику.
- **Образец:** `tests/fixtures/ecb_mpd/macro-U2-S26.csv`.
