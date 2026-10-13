# ONS, временные ряды D7G7 и IHYR (факт по Великобритании)

- **Роль:** эталонный факт для «Инфляция в Великобритании» (`ons_cpi`) и «Реальный ВВП Великобритании» (`ons_gdp`).
- **Адреса (JSON, без ключа):**
  - CPI: `https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/data` — «CPI ANNUAL RATE 00: ALL ITEMS 2015=100».
  - ВВП: `https://www.ons.gov.uk/economy/grossdomesticproductgdp/timeseries/ihyr/qna/data` и `…/ihyr/pn2/data` — «Gross Domestic Product: q-on-q4 growth rate CVM SA %». PN2 — первая оценка квартала, QNA — квартальные национальные счета; берём набор с более поздней датой выпуска.
  - Проверено 13 октября 2026: ответы 200; D7G7 — 150 кварталов (1989–2026 Q2), IHYR — 282 квартала (1956–2026 Q2).
- **Структура:** `description.cdid`, `description.releaseDate` (полночь по Лондону в UTC: `2026-09-15T23:00:00.000Z` = 16 сентября), массив `quarters` с `date` вида `2026 Q2` и `value` строкой.
- **Определения и сопоставимость:** квартальные значения D7G7 — годовой темп CPI по средним за квартал индексам. Банк Англии в Projections Databank указывает: «Four-quarter percentage change in CPI index. Based on ONS series D7G7»; OBR в таблице 1.7 ссылается на D7G7. IHYR — рост ABMI к тому же кварталу прошлого года; Банк Англии: «Percentage change on quarter a year earlier… Based on ONS series ABMI». Темпы взяты готовыми, не пересчитываются из уровней (в прототипе их считали из D7BT и ABMI; из округлённого индекса D7BT расхождения до 0,1 п. п.).
- **Винтажи:** архив версий в этом API не отдаётся. Винтаж — `releaseDate`; новый выпуск сохраняется, только когда файл изменился.
- **Лицензия:** Open Government Licence v3.0 (https://www.ons.gov.uk/help/termsandconditions).
- **Образцы:** `tests/fixtures/ons/d7g7_mm23.json`, `tests/fixtures/ons/ihyr_qna.json`.
