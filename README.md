# 메모리 반도체 브리프

삼성전자·SK하이닉스·마이크론(MU)·구글(GOOGL)·SOXL 투자에 참고할 업황·실적·AI 수요·정책 이슈와 주요 지표, 일정을 모은 개인용 정적 페이지입니다. 투자 권유가 아닙니다.

- `index.html` — 페이지 (Cloudflare로 게시)
- `data/issues.json` — 이슈 목록 (한 줄에 한 건, 최신순)
- `data/indicators.json` — 지표 띠
- `data/calendar.json` — 다가오는 일정
- `data/meta.json` — 최근 갱신 시각

평일 07:00·12:00·16:00·23:00, 주말 10:00(KST)에 Claude 예약 작업이 AUTOMATION.md 규칙에 따라 데이터 파일을 갱신하고 커밋합니다.

## 이슈 항목 형식
| 필드 | 설명 |
|---|---|
| id | `YYYYMMDD-영문-슬러그` |
| date | 기사·발표일 `YYYY-MM-DD` (KST) |
| category | `market`(업황·시장) · `earnings`(실적·가이던스) · `ai`(AI 수요) · `policy`(정책·거시) · `report`(증권가 리포트) |
| tickers | 관련 종목 배열: `삼성전자` `SK하이닉스` `MU` `GOOGL` `SOXL` (없으면 `[]`) |
| type | `domestic` · `foreign` · `report` · `policy` |
| region | `KR` `US` `EU` `GL` `CN` `JP` `TW` |
| importance | 3 핵심 · 2 주요 · 1 참고 |
| title / originalTitle | 한국어 제목 / 외신 원제 |
| summary | 2~4개 문장 배열 |
| impact | 체크 포인트 (종목에 주는 의미, 매매 추천 금지) |
| detail | (핵심만) 상세 요약 4~6개 문장 |
| verified | 원문을 직접 읽었으면 true |
| source / url / extraLinks | 출처, 원문 https 링크, 추가 링크 `[{label,url}]` |
| addedAt | 추가 시각 ISO8601 |

## 지표 (`data/indicators.json`)
`{"asOf", "items": [{group, label, value, unit, change, dir(up|down|flat), asOf, source}]}` — 못 찾은 값은 직전 값과 기준일을 유지.

## 일정 (`data/calendar.json`)
`[{date: "YYYY-MM-DD"(한국시간), time: "HH:MM"(한국시간, 없으면 ""), kind: macro|earn|kr, title, note}]` — 지난 일정은 화면에서 자동으로 숨겨짐.
