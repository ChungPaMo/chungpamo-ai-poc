# E03 결과 후속 기록 (유지보수 연결)

이 폴더의 `summary.md`, `run_meta.json`, `pytest_output.txt`는 **2026-10-20 E03 1단계-b 실행 당시의 측정값**이며 수정하지 않는다.

| 시점 | 전체 pytest | 비고 |
|---|---|---|
| E03 1단계-b 실행 (`run_meta.json`) | 75/76 (실패 1) | `test_e01_dataset.py::test_regeneration_is_byte_identical` — lxml 설치로 openpyxl xlsx 기록 바이트 변경 (E01 데이터 자체는 불변). 진단은 `run_meta.json`의 `regression_diagnosis` |
| 유지보수 (2026-10-20, `results/maintenance/2026-10-20_env_lxml_fix/`) | **82/82** | E01 생성 코드와 `tests/conftest.py`에 `OPENPYXL_LXML=False` 지정. 새 프로세스 E01 재생성 31개 파일 바이트 일치. `.env` 로컬 테스트 6개 추가 |
| 결과 확정 준비 (2026-10-20) | 최신값은 `docs/e03_document_samples_plan.md` §7.2 | PDF 2건 공개 보류(D-020) 반영 |

## 문서 샘플 상태 요약 (변경 없음)

- 6개 문서 SHA-256은 `sample_manifest.csv` 기준. 독립 구조 검증 84항목: PASS 75 / FAIL 0 / NOT_MEASURED 3 / NEEDS_MANUAL_REVIEW 6.
- 뷰어 미검수 6건(13_visual_layout) — 렌더링 품질은 PASS로 처리하지 않는다.
- 미측정 3건: D-01·D-02 페이지 나눔(뷰어 의존), T-02 노트·그룹(해당 요소 없음).
- 텍스트 블록 수 11개 (1단계 보고의 13개는 오기, 정답 명세 파일은 불변).
- 정답 명세 `e03_document_truth_v1.json`, 위치 `e03_document_locations_v1.json` 보존.
- **P-01·P-02(PDF)는 공개 저장소에서 보류**: 임베드된 맑은 고딕 서브셋의 재배포 조건(Microsoft EULA) 미확인. 로컬에만 보관하며, 새 클론에서는 검증기가 `NOT_MEASURED`(파일 없음)로 기록한다.
