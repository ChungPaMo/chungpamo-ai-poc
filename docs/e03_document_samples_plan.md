# E03 1단계 — 문서 샘플 설계·정답 명세·패키지 조사

- 작성일: 2026-10-20 (E03 상태 `RUNNING`, 1단계 = 설계·정답 명세만. **문서 파일 미생성, 파서 미구현, 패키지 미설치, 외부 API 미호출**)
- 정답 명세: `data/canonical/e03_document_truth_v1.json` (생성: `scripts/e03_build_truth.py`, canonical v2를 읽기만 함, SHA-256 `982af3be7af0b4f512851a3a2cba2d68578b8e046540d94f0efe1170b0cf554a`)
- 관련: [intermediate_representation.md](intermediate_representation.md), [evaluation_protocol.md](evaluation_protocol.md) §10, [experiment_plan.md](experiment_plan.md) E03

## 1. 샘플 설계

### 1.1 내용 묶음 (형식과 무관한 정답 원천)

| 묶음 | 내용 | 검증 요소 | canonical 연결 |
|---|---|---|---|
| CS1 BOM 사양서 | FG001 BOM V1·V2 표 2개, 개정 설명 문단, 각주 | 한·영 혼합, **2행 병합 헤더**, g/kg 혼재(1.2 kg → 1,000 g), 날짜(유효기간), 본문↔표 연결(개정 문단이 두 표의 M001 행을 가리킴) | BOM, BOMLine |
| CS2 주문·재고 보고서 | 주문 20행 표, 재고 15행 표(단가·재고금액), 꼬리말 | **여러 페이지·슬라이드에 걸친 표**(12행마다 넘김, 헤더 반복), 천 단위 쉼표, 금액(KRW), 상태 한글 표기 | Order, Inventory, Material |
| CS3 생산계획안 비교 | 정규안 주차별 계획 표, 3개 계획안 비용 표, 본문, 발표자 노트 | 그룹 헤더(주차 4열 병합), 슬라이드 넘김 표, 노트, 금액 | ProductionPlanLine, expected.plan_evaluation (v2) |

- 모든 수치·날짜는 canonical v2 값을 그대로 쓴다. 새 값은 두 가지뿐이며 규칙을 명세에 적었다: ① 재고금액 = 보유 수량(기준 단위) × 자재 단가 ② 문서번호 `SPEC-FG001`(규칙 `SPEC-{product_id}`).
- 정답 규모: 표 6개, 셀 361개(앵커 기준), canonical 연결 값 142개, 텍스트 블록 **11개** (CS1 4, CS2 4, CS3 3). ※ 정정(2026-10-20): 처음 작성 시 '13개'로 잘못 적었다. 정답 명세 파일 자체는 처음부터 11개였고 변경하지 않았다.

### 1.2 형식별 샘플과 확보 가능 수

| 문서 ID | 형식 | 내용 | 확보 방법 | 확보 가능 수 |
|---|---|---|---|---|
| D-01, D-02 | DOCX | CS1, CS2 | 직접 생성 (python-docx) | 2 |
| P-01, P-02 | PDF 텍스트형 | CS1, CS2(3쪽, 표 넘김) | 직접 생성 (reportlab) | 2 |
| S-01, S-02 | PDF 스캔형 | CS1, CS2 | 직접 생성 (Pillow로 이미지에 그려 PDF 저장 — 텍스트 레이어 없음) | 2 |
| T-01, T-02 | PPTX | CS3(4장, 표 넘김·그룹 도형·노트), CS1 | 직접 생성 (python-pptx) | 2 |
| H-01 | HWPX | CS1 | 직접 생성 **시도** 가능 (python-hwpx 또는 zipfile+XML). 한글 프로그램에서 열림 확인 전 **검증 완료 처리 불가** | 1 (조건부) |
| W-01 | HWP | CS1 | **외부 확보 필요**: 한글 프로그램 보유자가 D-01/H-01을 HWP로 저장, 또는 라이선스가 확인된 공개 샘플 | 0 (직접) / 1 (외부) |

- 직접 생성 가능: 8건 (DOCX 2, PDF 텍스트 2, PDF 스캔 2, PPTX 2) + HWPX 1건(열림 미확인)
- 외부 확보 필요: HWP 1건, HWPX 열림 확인(한글 프로그램)
- 정답 위치: 생성 전에는 논리 위치(본문 순번·페이지 계획·슬라이드 계획·섹션)만 있다. 실제 좌표(PDF bbox, PPTX shape id, HWPX 문단 번호)는 **생성기가 렌더링하면서 기록**하고, 파서 출력으로 만들지 않는다.

## 2. 문서별 평가 가능 항목

| 형식 | 평가 항목 (evaluation_protocol.md §10) | 1차 샘플로 가능 여부 |
|---|---|---|
| DOCX | 블록 순서, 머리말·꼬리말·각주, 표 셀·2행 병합 헤더, 숫자·단위·날짜, 원본 위치(part·body_index·행열), 본문↔표 연결 | 가능 |
| PDF 텍스트형 | 블록 순서, 표 검출 재현율·정밀도, 셀·병합, **페이지 넘김 표·반복 헤더**, 숫자·단위·날짜, 위치(page·bbox IoU — 임계값 팀 합의 필요), 머리말 문서번호·개정 | 가능 |
| PDF 스캔형 | 스캔 판정, 직접 추출 빈 출력(EXT-EMPTY) 판정 — OCR·API 정확도는 E04 | 판정만 가능 |
| PPTX | 슬라이드·도형 순서, 표 도형 셀·병합, **슬라이드 넘김 표**, 그룹 도형 안 텍스트, 발표자 노트, 위치(slide·shape) | 가능 |
| HWPX | 열림 여부, 문단 순서, 표 셀·병합, 숫자·단위·날짜, 위치(section·paragraph) | 생성은 가능, **열림 확인 전 미측정** |
| HWP | 열림 여부, 문단·표, 병합, 위치 | 외부 확보 전 미측정 |

## 3. 패키지 조사 (설치하지 않음 — 승인 대기 D-014)

PyPI 공식 메타데이터를 2026-10-20에 조회한 값이다. Windows 호환성은 휠 태그 기준이며 실제 설치 시 다시 확인한다.

| 패키지 | 최신 버전 | 라이선스 | Python | 휠 / Windows | 용도 | 상태 |
|---|---|---|---|---|---|---|
| python-docx | 1.2.0 | MIT | ≥3.9 | py3-none-any | DOCX 생성 (D-01·02), E03 DOCX Baseline 파서 | 설치 필요 (가상환경에 없음) |
| reportlab | 5.0.1 | BSD | ≥3.9, <4 | 휠 태그 미확인 (메타데이터가 잘려 확인 못 함) | 텍스트형 PDF 생성 (P-01·02) | 설치 필요. 의존: pillow, charset-normalizer |
| python-pptx | 1.0.2 | MIT | ≥3.8 | py3-none-any | PPTX 생성 (T-01·02), E03 PPTX Baseline 파서 | 설치 필요. 의존: Pillow, XlsxWriter, lxml, typing-extensions |
| Pillow | 13.0.0 | MIT-CMU | ≥3.11 | (C 확장, Windows 휠 제공으로 알려짐 — 설치 시 확인) | 스캔형 PDF 생성 (S-01·02) | 설치 필요 |
| lxml | 6.1.3 | BSD-3-Clause | ≥3.8 | (C 확장, 설치 시 확인) | HWPX XML 처리, python-pptx·python-hwpx 의존 | 설치 필요 |
| python-hwpx | 6.8.0 | Apache-2.0 | ≥3.10 | py3-none-any | HWPX 생성·검증 시도 (H-01) | 후보. 서드파티(한컴 공식 아님). 검색 결과에 다른 버전(2.9.1) 표기가 있어 설치 시 버전 재확인 |
| pypdf | 6.21.1 | BSD-3-Clause | ≥3.9 | — | E03 PDF Baseline 파서 | 설치 필요 (전역에만 6.19.0 존재 — 사용 안 함) |
| pdfplumber | 0.11.10 | MIT | ≥3.8 | py3-none-any | E03 PDF 표 추출 비교 | 후보. 의존: pdfminer.six, Pillow≥12.2, pypdfium2 |
| PyMuPDF | 2.0 | **AGPL-3.0 또는 Artifex 상용 (이중)** | ≥3.11 | Windows 휠 제공으로 README 표기 (파일 미확인) | E03 PDF 비교 후보 | **라이선스 검토 필요** (MVP 배포 형태에 따라 AGPL 의무 발생) |
| olefile | 0.47 | BSD | ≥2.7 | — | HWP(OLE) 스트림 열기 | 후보 |
| pyhwp | 0.1b15 | **AGPL-3.0+** | 분류자상 3.5~3.8 | sdist만 | HWP5 파싱 후보 | **2020-05 이후 갱신 없음, Python 3.11 지원 미확인** → 후보 우선순위 낮음 |
| unhwp | 0.23.0 | MIT | ≥3.9 | py3-none-any (README는 Windows x64 지원 표기) | HWP/HWPX 추출 후보 | 후보 (검색으로 발견, 품질 미확인) |

- 샘플 생성만 먼저 한다면 최소 세트: **python-docx, reportlab, python-pptx, Pillow, lxml** (python-pptx가 lxml·Pillow·XlsxWriter·typing-extensions를 함께 설치). HWPX 생성 시도에 python-hwpx 추가.
- 파서 비교(E03 2단계) 세트는 샘플 확보 후 별도 승인: pypdf, pdfplumber, (PyMuPDF — 라이선스 결정 후), olefile, (pyhwp / unhwp — HWP 샘플 확보 후).
- 한글 폰트: PDF·스캔 이미지 생성에 Windows 시스템 한글 폰트를 쓸 경우 폰트 파일은 저장소에 넣지 않고, 생성 문서에 폰트가 임베드될 때의 재배포 조건을 확인해야 한다 (미확인).

## 4. HWP/HWPX 미해결 문제

1. **열림 확인 수단 없음**: 이 PC에 한글 프로그램이 없다. 생성한 HWPX가 실제 한글에서 열리는지 확인할 수 없으면 검증 완료로 처리하지 않는다 (사용자 지시). → 한글 보유자 확인 절차 또는 한컴 공식 뷰어 사용 가능 여부 확인 필요.
2. **HWP 생성 불가**: 오픈소스로 HWP(바이너리)를 쓰는 검증된 도구를 확인하지 못했다. 외부 제작·변환과 독립 검수(E01 예외 규칙)가 필요하다.
3. **파서 후보의 지원 범위 미확인**: pyhwp는 갱신 중단·Python 3.11 지원 미확인, unhwp·python-hwpx는 서드파티이며 품질 미검증.
4. **표준 문서 확인**: HWPX는 KS X 6101(OWPML) 기반 ZIP+XML로 알려져 있으나, 이번에는 표준 원문을 확인하지 못했다(검색 결과의 2차 정보). 위치 표현(문단 ID·XPath)을 확정하려면 원문 또는 한컴 공식 자료 확인이 필요하다.
5. **변환 경로 차이**: DOCX→HWP 변환본은 표 병합·글꼴이 바뀔 수 있어, 정답은 변환본을 사람이 검수한 JSON을 기준으로 해야 한다.

## 5. 공통 중간 JSON 수정 필요 여부 (제안만, 미적용 — E02 출력 변경 없음)

| 한계 | 영향 형식 | 제안 (schema 0.2) |
|---|---|---|
| 같은 내용을 여러 형식으로 렌더링할 때 공통 정답을 가리킬 키가 없음 | 전체 | `document.content_set` 추가, 블록·표에 `logical_id`(예: `CS1-T1`) 추가 |
| 계획 위치와 실제 위치 구분이 없음 | 정답 명세 | 정답의 위치를 `planned_location` / `actual_location`으로 분리 |
| 페이지·슬라이드를 넘는 표 조각이 같은 논리 표임을 표현하기 어려움 | PDF, PPTX | `tables[].logical_table_id` + `fragment_index` (기존 `continuation`은 유지) |
| 그룹 도형·중첩 구조 | PPTX, HWP | `location.parent_shape_id` / `location.container_path`(중첩 경로) |
| 셀 단위 canonical 연결 | 전체 | `cells[].canonical_ref` (정답 명세에는 이미 사용) |
| 스캔 문서의 인식 신뢰도·이미지 영역 | PDF 스캔(E04) | `blocks[].confidence`, `location.image_region` |
| HWP 표 안의 표 등 컨트롤 중첩 | HWP | `location.control_path` (도구 확정 후) |

## 6. 다음 구현 단계 권고

1. **D-014 승인 요청**: 샘플 생성 최소 세트(python-docx, reportlab, python-pptx, Pillow, lxml) 설치. HWPX 시도를 위해 python-hwpx 포함 여부 결정.
2. **E03 1단계-b (생성)**: 정답 명세를 원천으로 8개 문서 생성(DOCX·PDF 텍스트·PDF 스캔·PPTX), 생성 시 실제 위치를 `actual_location`으로 기록, 생성 결과를 사람이 뷰어로 표본 검수.
3. **HWP/HWPX**: 한글 프로그램 보유자 지정(열림 확인·HWP 변환·독립 검수). 지정 전까지 두 형식은 `BLOCKED` 후보로 표시.
4. **결정 필요**: PDF bbox IoU 임계값, 스캔 해상도(제안 200 dpi), PyMuPDF(AGPL) 사용 여부, 중간 JSON 0.2 변경안 채택 여부.
5. 그다음 E03 2단계(파서 비교)는 별도 승인 후 착수.

## 7. 1단계-b 진행 기록 (2026-10-20, 문서 생성·독립 검증)

- 생성 대상: D-01, D-02(DOCX), P-01, P-02(텍스트형 PDF), T-01, T-02(PPTX) 6개. 결과: `results/E03_document_parsers/summary.md`.
- **스캔형 PDF(S-01, S-02) 생성 보류**: 사용자 결정으로 OCR을 현재 우선순위에서 제외 (OCR 엔진 설치·이미지 텍스트 인식·인식률 측정·Upstage 호출 금지). 설계와 정답 명세는 그대로 보존한다. 스캔 문서는 E04(Upstage)에서 검증할 예정이며, Upstage의 지원 형식·제공 조건은 공식 문서·계약 확인 후 확정한다.
- **지시와 기존 설계의 차이 (기존 설계 유지)**: 작업 지시는 T-02를 "생산계획 비교 및 경영 의사결정 보고"로 설명했으나, 확정 명세는 T-01 = CS3(생산계획안 비교, 4장), **T-02 = CS1(BOM 사양서, 3장)** 이다. 지시에 따라 문서 ID와 내용 구성을 바꾸지 않았다.
- 텍스트 블록 수 정정: 13 → **11** (§1.1). 명세 파일은 변경하지 않았다.
- 실제 위치는 별도 버전 파일 `data/canonical/e03_document_locations_v1.json`에 기록 (정답 명세 v1은 불변).
- 설치 패키지(승인): python-docx 1.2.0, reportlab 5.0.1, python-pptx 1.0.2, lxml 6.1.3 + 필수 의존성 Pillow 13.0.0(python-pptx·reportlab 의존), XlsxWriter 3.2.9, charset-normalizer 3.5.2.
- PDF 한글 폰트: 로컬 Malgun Gothic(malgun.ttf, OS/2 fsType 8 = 편집 가능 임베딩 허용)을 서브셋 임베드. 폰트 파일은 저장소에 넣지 않음(`.gitignore`에 폰트 확장자 추가). Microsoft 폰트 EULA의 문서 재배포 세부 조건은 미확인.

### 7.2 결과 확정 준비 (2026-10-20)

- 독립 구조 검증 84항목(PASS 75 / FAIL 0 / NOT_MEASURED 3 / NEEDS_MANUAL_REVIEW 6)은 `results/E03_document_parsers/`의 실행 당시 기록을 유지. 이후 유지보수로 전체 pytest 통과 기록은 `results/E03_document_parsers/maintenance_note.md`에 연결.
- **P-01·P-02 공개 보류 (D-020)**: 임베드된 맑은 고딕 서브셋의 재배포 조건이 확인되지 않아 공개 저장소에 올리지 않는다. 로컬 보관·검증만 한다. DOCX·PPTX는 폰트를 임베드하지 않음(글꼴 이름만 지정)을 보안 점검으로 확인.
- 새 클론에 PDF가 없을 때 검증기는 해당 문서를 `NOT_MEASURED`(파일 없음)로 기록하고, PDF 전용 테스트는 사유와 함께 건너뛴다.

### 7.1 HWP/HWPX 추가 조사 (생성·변환·파싱은 하지 않음, 모두 미측정)

| 주제 | 확인 내용 | 확인 수준 |
|---|---|---|
| HWPX 표준 | KS X 6101(OWPML) 기반 ZIP+XML (mimetype, version.xml, settings.xml, Contents/section*.xml 등) | 2차 자료 (표준 원문 미확인) |
| HWP 형식 | HWP 5.0은 OLE2(복합 문서) 기반. 한컴이 2010년부터 형식 문서를 공개했다는 보도·오픈소스 구현(libhwp)의 언급 | 2차 자료 (한컴 공식 문서 다운로드 경로 미확인) |
| python-hwpx | 한글 프로그램 없이 HWPX를 열기·편집·생성·검증한다고 표방 (서드파티, Apache-2.0, 6.8.0) | PyPI 메타데이터 확인, 기능 미검증 |
| 열림 확인 방법 | ① 한글 프로그램 보유자 확인(권장) ② 한컴 무료 뷰어 제공 여부 — 확인 못 함 ③ 오픈소스 뷰어(오픈한글, HOP 등) — 한글 프로그램과 같은 판정으로 볼 수 없음 | 미확정 (D-017) |
| HWP 샘플 확보 | ① 한글 보유자가 D-01(DOCX) 또는 HWPX를 HWP로 저장 ② 공개 저장소 테스트 샘플(라이선스 확인 필요) | 계획만 |
| 변환본 차이 검수 | 변환본을 한글에서 열어 사람이 블록·표·병합을 기록한 검수 정답 JSON을 만들고, 정답 명세(CS1)와 차이를 표로 남김 → 차이가 있으면 검수 정답을 기준으로 함 (E01 HWP 예외 규칙) | 계획만 |

## 참고 출처 (2026-10-20 조회)

- PyPI JSON: python-docx, python-pptx, reportlab, PyMuPDF, pdfplumber, pyhwp, lxml, olefile, pypdf, python-hwpx, Pillow, unhwp (`https://pypi.org/pypi/<패키지>/json`)
- python-hwpx 저장소: https://github.com/airmang/python-hwpx
- HWPX(KS X 6101/OWPML) 2차 정보: https://news.hada.io/topic?id=19448 , https://byline.network/2021/04/15-117/
- HWP 형식·도구 2차 정보: https://pyhwp.readthedocs.io/ko/latest/intro.html , https://github.com/accforaus/libhwp , https://braindetox.kr/posts/hwp_open_source_editor.html
