# E10 평가 프로토콜 — 모의 ERP 매핑 안전성

> 작성 2026-10-21 (초안, **평가 미실행**). 계획: [e10_erp_mapping_plan.md](e10_erp_mapping_plan.md), 계약: [e10_data_contract.md](e10_data_contract.md).
> 모든 시나리오 데이터는 합성이다. 기준(정답) 데이터는 E01 정답셋 v2(`ground_truth_v2.json`, sha256 `262dbe75…`)이며 변경하지 않는다. 시나리오 입력은 별도 파일로 만든다(아직 만들지 않음).

## 1. 원칙

- 정답은 매핑 방식의 출력과 독립적으로, E01 정답셋과 시나리오 정의만으로 정한다 (E05 평가셋과 같은 원칙).
- 방식(규칙·검색·임베딩·Tri-CHEF·LLM)은 같은 입력·같은 정답·같은 검증·같은 승인 시뮬레이션으로 비교한다.
- 승인 시뮬레이션: 사람 승인자를 흉내 내는 규칙을 고정한다 — "검토 필요 후보는 정답과 같을 때만 승인" (리뷰어가 완벽하다고 가정한 상한)과 "검토 필요 후보를 모두 승인" (리뷰어가 확인 없이 승인하는 최악)을 **둘 다** 보고한다. 실제 승인자 행동은 측정하지 않는다.
- 측정하지 않은 값은 `미측정`, 목표값은 `팀 합의 필요`.

## 2. 기대 판정(expected_decision) 값

| 값 | 의미 |
|---|---|
| AUTO_ACCEPT_ELIGIBLE | 자동 승인 조건(계약 §5)을 모두 만족해야 함 |
| REVIEW_REQUIRED | 후보는 나와야 하지만 자동 확정하면 안 됨 |
| REJECT | 반영되면 안 됨 (매핑 불가·잘못된 코드) |
| BLOCKED_BY_VALIDATION | 후보가 나와도 검증 오류(ERROR)로 승인 불가여야 함 |
| NO_NEW_RECORD | 반영 결과 신규 레코드 0 (재반입·중복) |
| NO_COMMIT | 본 테이블 변경 0 (승인 없는 반영 시도) |

## 3. 시나리오와 독립 정답

| ID | 시나리오 | 입력 예 (합성) | 독립 정답 | expected_decision | 관련 검증 규칙 |
|---|---|---|---|---|---|
| M01 | 정확한 제품코드 | 업체 A 주문의 제품코드 `0001001` | ProductMaster `FG001` (E02 코드표) | AUTO_ACCEPT_ELIGIBLE | — |
| M02 | 유사 제품명 | 품명 `가정용히터A` (띄어쓰기 없음) | `FG001` (`가정용 히터 A`) | REVIEW_REQUIRED | — |
| M03 | 동일 명칭의 서로 다른 제품 | 품명 `가정용 히터` (A/B 구분 없음) | 후보 `FG001`·`FG002` 모두 가능 → 정답 없음(모호) | REVIEW_REQUIRED (자동 확정 시 오답) | — |
| M04 | 잘못된 제품코드 | 제품코드 `0009999` (코드표에 없음) | 대응 제품 없음 | REJECT | R01 |
| M05 | 단위 불일치 | BOM 라인 `M004`(ABS 수지, 기준 kg)에 단위 `EA` (E01-ERR-004와 같은 유형) | 값은 매핑되나 반영 불가 | BLOCKED_BY_VALIDATION | B08 (ERR-UNIT) |
| M06 | 수량 오류 | 주문 수량 `-5`, `1O50` | 반영 불가 | BLOCKED_BY_VALIDATION | S06, S02 |
| M07 | 중복 주문 | 같은 주문 `O012`가 한 파일에 두 번 | 중복 1건 탐지, 레코드 1개만 반영 후보 | 1건 REVIEW_REQUIRED(중복) | S08 (ERR-DUPID) |
| M08 | 구버전 BOM | `BOM-FG001-V1`(2026-11-30 종료)을 현재 버전처럼 담은 구버전 문서 | 본 테이블의 V2(2026-12-01~)를 덮어쓰지 않음 | REVIEW_REQUIRED + SUPERSEDED_INPUT | B02, B06 |
| M09 | 유효기간 충돌 | FG002에 V1과 기간·수량이 겹치는 활성 V2 (E01-ERR-011 유형) | 반영 불가 | BLOCKED_BY_VALIDATION | B02 (ERR-BOMVER) |
| M10 | 참조 대상 누락 | BOM 라인이 없는 자재 `M099` 참조 | 반영 불가 | BLOCKED_BY_VALIDATION | R02 (ERR-BADREF) |
| M11 | 재반입 시 중복 | M01 파일을 같은 sha256으로 다시 반입 | 신규 레코드 0, 이전 batch 연결 | NO_NEW_RECORD | dedup_key |
| M12 | 승인되지 않은 데이터 반영 시도 | PENDING 상태 staging을 본 테이블에 쓰려는 요청 | 본 테이블 변경 0 | NO_COMMIT | DDL 트리거 |

시나리오별 정답 파일 형식(예정): `{scenario_id, inputs[], expected: [{input_id, entity, field, value | null, expected_decision}], notes}`. 정답은 위 표와 E01 값으로만 만든다.

## 4. 지표 정의

| 지표 | 정의 | 비고 |
|---|---|---|
| Field Mapping Accuracy | 정답 (엔터티, 필드)가 있는 입력 중 1순위 후보의 (엔터티, 필드)가 정답과 같은 비율 | 값은 따지지 않음 |
| Wrong-field Mapping Rate | 1순위 후보가 정답과 다른 (엔터티, 필드)인 입력의 비율 | 정답 없음(M03·M04)에서 후보를 낸 경우 별도 집계 |
| **Wrong-value Commit Rate** | 승인 시뮬레이션 후 본 테이블에 반영된 값 중 정답과 다른 값의 비율 (분모: 반영된 값 수). 건수도 함께 보고 | **가장 중요한 안전성 지표.** 리뷰어 상한·최악 두 경우 모두 |
| Duplicate Detection Rate | 정답 중복(M07·M11) 중 탐지된 비율 | — |
| Auto-accept Coverage | 전체 후보 중 자동 승인 조건을 만족한 비율 | 높을수록 수작업 감소, 단 Wrong-value Commit과 함께 본다 |
| Manual Review Rate | 전체 후보 중 review_required = true 비율 | — |
| Rejection Accuracy | REJECT·BLOCKED_BY_VALIDATION·NO_COMMIT 정답 중 실제로 반영되지 않은 비율, 그리고 반영돼야 할 값을 잘못 반려한 수 | — |
| 처리시간 | 입력 1건당 후보 생성·검증 시간 (3회 중앙값) | — |
| API 비용 | 외부 API를 쓴 방식만, 실제 청구·사용량 기록 기준 | 추정 금지, 없으면 `미측정` |
| 원본 추적 가능률 | 반영된 값 중 `ApprovalLog → MappingCandidate → source_reference`로 원본 파일·위치까지 역추적되는 비율 | — |

## 5. 결과 형식 (예정)

`results/E10_erp_mapping/`: `metrics.csv`(방식 × 지표, 리뷰어 상한/최악), `candidates.jsonl`, `commits.json`, `failures.md`, `summary.md`, `run_meta.json`.

## 6. 미확정

- 목표값(특히 Wrong-value Commit Rate 허용 상한) — 팀 합의 필요. 제안: 상한은 0건 목표로 두고 0이 아니면 해당 방식의 자동 승인 금지.
- 시나리오 수·입력 문서 형식(CSV/XLSX/DOCX/PDF) 비율 — 팀 합의 필요.
