# E03 실패 사례 진단 — Upstage Standard vs 직접 파서 (X-DV-P04)

> E03 실패 사례 진단 예비 비교 (E04 본 실험 아님). 1개 문서·1회 호출 — 일반화하지 않는다. 정답: PubTables-1M 공식 주석 (VERIFIED_OFFICIAL). dev 묶음 문서(v2 개발에 사용) — v2 수치는 개발 참고값.

- 호출: SUCCESS, HTTP 200, 9.845s(네트워크 포함), 보낸 쪽 2, 과금 {'pages': 2, 'standard': [1, 2]}, 모델 `document-parse-260930`
- 비용: 추정 $0.02 (공개 단가, VAT 별도), 실제 청구 콘솔 확인 전 미확인
- 응답 보안 검사: {'api_key_in_response': False, 'home_path_in_response': False, 'email_like_in_response': False}

| 지표 | upstage_standard_html | upstage_standard_markdown | direct_v1_pdfplumber | direct_v2_pdfplumber |
|---|---|---|---|---|
| 표 재현율 | 1/1 | 1/1 | 0/1 | 1/1 |
| 표 정밀도 | 1/1 | 1/1 | 미측정 | 1/1 |
| 행·열 수 일치 | 1/1 | 1/1 | 0/1 | 1/1 |
| 셀 텍스트(격자, 공백무시) | 47/47 | 47/47 | 0/47 | 47/47 |
| 셀 텍스트(엄격) | 47/47 | 47/47 | 0/47 | 47/47 |
| 병합 셀 | 4/6 | 0/6 | 0/6 | 2/6 |
| 잘못된 병합 | 0 | 0 | 0 | 0 |
| 헤더 셀 텍스트 | 7/7 | 7/7 | 0/7 | 7/7 |
| 행 머리 | 미측정 | 미측정 | 미측정 | 미측정 |
| 표 bbox IoU 평균 | 0.888 | 0.888 | — | 0.932 |
| 셀 bbox IoU≥0.5 | 미제공 (측정 불가) | 미제공 (측정 불가) | 0/47 | 44/47 |

- Markdown 출력은 병합 정보를 표현하지 못하므로 병합 셀 지표는 HTML과 구분해 본다.
- 처리시간은 조건이 달라(API는 네트워크·서버 포함) 직접 파서와 비교하지 않는다.
