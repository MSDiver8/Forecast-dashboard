# Евростат: HICP еврозоны (факт)

- **Роль:** эталонный факт для «Инфляция в еврозоне, HICP, в среднем за год».
- **API:** `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_aind?geo=EA&coicop=CP00&unit=RCH_A_AVG&format=JSON&lang=en` — JSON-stat 2.0, без ключа. Проверено 8 октября 2026: ответ 200, поле `updated` = 2026-02-06, ряд 1997–2025.
- **Ряд:** `prc_hicp_aind` — HICP, годовые данные; `unit = RCH_A_AVG` (annual average rate of change), `coicop = CP00` (all-items), `geo = EA` — еврозона в меняющемся составе (EA11-1999 … EA21-2026), как `U2` у ЕЦБ.
- **Винтажи:** архива версий в API нет; выпуск — дата `updated` из ответа; новый выпуск появляется, когда Евростат обновляет набор.
- **Лицензия:** Eurostat, повторное использование с указанием источника (Commission Decision 2011/833/EU).
- **Образец:** `tests/fixtures/eurostat_hicp/prc_hicp_aind_EA.json`.
