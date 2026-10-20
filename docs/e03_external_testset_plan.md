# E03 외부 제작 문서 테스트셋 — 확보 결과와 평가 설계 (측정 전)

- 작성일: 2026-10-20. E03 상태 `RUNNING`. 이번 단계는 **문서 확보·분석·평가 설계까지** — 파서 실행·수정·채점 없음.
- 목적: 직접 파서 Baseline(`results/E03_document_parsers/parser_baseline/`)은 생성 라이브러리와 같은 계열로 읽은 왕복 결과다(D-022). 다른 도구·사람이 만든 문서로 같은 지표를 다시 재기 위한 테스트셋을 준비한다.
- 출처 목록: [`configs/e03_external_sources.json`](../configs/e03_external_sources.json) · 내려받기 `scripts/e03_external_fetch.py` · 검사 `scripts/e03_external_inspect.py`
- 검사 결과(공개용): `results/E03_document_parsers/external_candidates/` (`manifest.csv`, `inspection.json`, `summary.md`)
- 원본: `data/raw/external_documents/` (Git 제외, `.gitignore` `data/raw/*`)

> **후속 (2026-10-20)**: 이 설계대로 정답 v1 작성·블라인드 평가·v2 개선·holdout 평가를 수행했다 → [e03_external_generalization_report.md](e03_external_generalization_report.md). 평가 묶음은 `configs/e03_external_splits.json`(dev·holdout 문서 추가).

## 1. 확보 결과 (목표 DOCX 2·PPTX 2·PDF 4 → 최종 후보 8건 확보, 예비 5건)

| ID | 역할 | 형식 | 파일 | 출처 (커밋 고정) | 만든 방식 | 라이선스 |
|---|---|---|---|---|---|---|
| X-D01 | 최종 | DOCX | kitchen-sink.docx | portone-io/docx-editor `18628ae` `__fixtures__/` | XML 부품 직접 조립 (워드프로세서 저장 아님, 저장소 README) | Apache-2.0 |
| X-D02 | 최종 | DOCX | google-docs-export.docx | 같은 저장소 `__fixtures__/producers/` | **Google Docs(웹)에서 저장** 후 작성자 정보 정리·본문 치환 | Apache-2.0 |
| X-T01 | 최종 | PPTX | mixed.pptx | shbernal/ts-pptx `11611de` `test/read/fixtures/` | **Mac PowerPoint 16** — 실제 사용 덱에서 승격 | MIT |
| X-T02 | 최종 | PPTX | table-merge-encoding.pptx | 같은 저장소 | **Windows PowerPoint COM** 작성 | MIT |
| X-P01 | 최종 | PDF | PMC2008195.1.pdf (Virol J 2007) | PMC Cloud Service `pmc-oa-opendata` + PubTables-1M 주석 | FrameMaker 7.0 → Acrobat Distiller | CC BY |
| X-P02 | 최종 | PDF | PMC2671505.1.pdf (BMC Plant Biol 2009) | 같음 | FrameMaker 7.1 → Distiller | CC BY |
| X-P03 | 최종 | PDF | PMC3296738.1.pdf (PLoS One 2012) | 같음 | 3B2 → Distiller | CC BY |
| X-P04 | 최종 | PDF | PMC4729796.1.pdf (Environ Monit Assess 2016) | 같음 | 3B2 → Distiller | CC BY |
| X-D03 | 예비 | DOCX | content-controls.docx | docx-editor | XML 직접 조립 | Apache-2.0 |
| X-D04 | 예비 | DOCX | preserved-markup.docx | docx-editor | XML 직접 조립 | Apache-2.0 |
| X-T03 | 예비 | PPTX | group-transform.pptx | ts-pptx | Windows PowerPoint | MIT |
| X-T04 | 예비 | PPTX | table-placeholder.pptx | ts-pptx | Windows PowerPoint COM | MIT |
| X-P05 | 예비 | PDF | nics-background-checks-2015-11.pdf | jsvine/pdfplumber `4c64b92` `tests/pdfs/` | Mac Quartz PDFContext | 저장소 코드 MIT, **문서 자체 출처·저작권 미확인** |

- SHA-256·크기·구조 수치: `manifest.csv`. PPTX 4건은 저장소 README가 공개한 SHA-256과 일치, PDF 4건은 PMC 메타데이터 MD5와 일치.
- 조사했지만 쓰지 않은 소스: **microsoft/table-transformer 저장소에는 예시 PDF·주석이 없음**(2024년 보관 처리). 주석은 Hugging Face `bsmock/pubtables-1m`의 `PubTables-1M-PDF_Annotations.tar.gz`(3.7GB)에 있고 원본 PDF는 포함되지 않음 → 아카이브 앞부분만 스트리밍해 JSON 40개(압축 약 0.34MB)를 받고, 원본 PDF는 PMC 공개 버킷에서 받음. PMC OA 웹 서비스(`oa.fcgi`)는 조회 시 404 — 원인 미확인 (PMC Cloud Service 페이지에 2026-08 레거시 데이터셋 파일 제거 공지가 있음). 라이선스는 각 논문 메타데이터 JSON의 `license_code`로 확인.
- 쪽 넘김·선 형태: PDF 최종 4건은 모두 **가로선만 있는 표(세로선 없음)**. 선 있는 격자 표는 X-P05뿐이며 공식 셀 주석이 없다 → **선 있는 표의 공식 정답 PDF는 0건 확보**.

## 2. 안전성 검사 (실행·렌더링 없이 구조만 확인)

- DOCX·PPTX: 매크로(vbaProject)·ActiveX 0건. 외부 관계는 하이퍼링크 2건(`example.com`). 임베딩은 X-T01의 차트 데이터 통합문서 1건(xlsx, VBA 없음, 외부 링크 없음). 임베드 글꼴 0건.
- PDF: JavaScript·Launch·첨부(EmbeddedFile)·XFA·암호화 0건. OpenAction 3건은 모두 쪽 이동(GoTo·목적지 배열). /URI는 논문 하이퍼링크.
- 처음 검사에서 X-P04에 `/JS`·`/AA` 토큰이 잡혔으나 이미지·XMP 이진 데이터 안의 우연한 바이트였다 → 스트림 본문을 제외하도록 검사기를 고쳐 다시 확인(오탐 0).
- 개인 메타데이터: 작성자 필드가 있는 파일이 있으나 값은 기록하지 않음(존재 여부만).

## 3. 독립 정답 확보 가능 범위

정답 원천 등급: **A 공식 주석**(사람·도구가 만든 정답 데이터, 원본 대응 확인) / **B 저장소 문서·테스트 기대값**(README 계약, 테스트 단언) / **C 제3자 판독**(다른 라이브러리의 읽기 결과 — 교차 확인용, 단독 정답 불가) / **M 수동 검수 필요** / **N 미측정**. 평가 대상 파서의 출력은 어떤 등급에도 쓰지 않는다.

| 항목 | X-P01~P04 (PubTables) | X-D01 kitchen-sink | X-D02 google-docs | X-T01 mixed | X-T02 table-merge |
|---|---|---|---|---|---|
| 본문 텍스트 | M (JATS XML 본문은 있으나 PDF 쪽·하이픈·머리말과 대응 규칙 필요) | M | **B** (`source.md` 본문 원문) | C (ts-pptx 스냅숏) + M | C |
| 표 영역 | **A** (`pdf_table_bbox`) | B (표 2개·순서) | B (표 2개) | C | B (슬라이드당 1개) |
| 행·열 구조 | **A** | B (첫 표 가로·세로 병합, 둘째 표 gridCol 없음) + M | B (3열 표) + M | C + M | **B** (3×3·4×4 등) |
| 셀 텍스트 | **A** (`pdf_text_content`) | M | B/M | C + M | B (1번 표 일부) + M |
| 셀 병합 | **A** (`row_nums`·`column_nums`) | B + M | **B** (세로 병합 2·gridSpan 1) | 해당 없음 (병합 0) | **B** (슬라이드별 span 전체) |
| 헤더 셀 | **A** (`is_column_header`, 행 머리 `is_projected_row_header`) | M | M | M | N |
| 문단·읽기 순서 | N | M | B (`source.md` 순서) | M (논리 순서 정의 없음) | 해당 없음 |
| 페이지·슬라이드 번호 | **A** (`pdf_page_index`) | N (DOCX 쪽 정보 없음) | N | B (11장) | B (5장) |
| 도형 계층 | 해당 없음 | 해당 없음 | 해당 없음 | C (z-order·부모) + M | 해당 없음 |
| 원본 위치 | **A** (셀 bbox, PDF 좌표) | M (본문 순번) | M | C (상자 좌표) | B (슬라이드) |
| 각주·머리말 | N | B (머리말·꼬리말 부품 있음, **각주·미주는 구분자만 — 실제 0건**) | B (각주 2·메모 1·꼬리말 필드) | B (노트 10장) | 해당 없음 |

- PubTables 대응 확인: 4개 PDF 9개 표 모두 쪽 크기 일치, 셀 텍스트(공백 무시) 457개 중 455개가 PDF 해당 영역 텍스트와 일치. 불일치 2개는 주석 오류가 아니라 영역 경계에서 글자가 잘리거나 하이픈이 제어문자로 나온 경우 → 채점 시 하이픈·줄바꿈 정규화 규칙 필요.
- PubTables 표 수 = 각 논문 JATS XML의 `table-wrap` 수 (2·4·2·1) → 문서 안 모든 표가 주석됨 → **표 검출 정밀도 측정 가능**.
- PubTables 주석 규칙 주의: 헤더 셀 정규화(canonicalization), 빈 셀도 셀로 주석, 행 머리(projected row header)는 행 전체를 덮는 셀 — 직접 파서 출력과 규칙이 달라 생기는 차이를 오류와 구분해 기록해야 한다.

## 4. 난이도·결함 발견 가능성 (측정 전 가설 — 근거는 구조 특성과 파서 설계)

| 순위 | ID | 근거 | 예상 결함 (검증 전) |
|---|---|---|---|
| 1 | X-P02 | 17열 표, 병합 13·헤더 18셀, 세로선 없음 | pdfplumber 선 기반 검출 실패 또는 열 붕괴 |
| 2 | X-P03 | 36×5 표, 행 머리 7·빈 셀 21, 경로 객체 360개(음영 추정) | 표 경계 오검출, 행 머리 처리 |
| 3 | X-T01 | 차트·SmartArt·연결선·그룹, 노트 10장 | SmartArt·차트 텍스트 누락 (python-pptx 미지원 영역), 그룹 안 읽기 순서 |
| 4 | X-D02 | 실제 워드프로세서 마크업(rsid·paraId), 변경 추적 삽입, 각주 2, 메모 | 변경 추적 안 텍스트·각주 누락 (python-docx 각주 API 없음) |
| 5 | X-P01 | 표 2개(쪽 2·4), 빈 셀 26, 행 머리 | 세로선 없는 표 검출 실패 |
| 6 | X-D01 | 둘째 표의 `w:tblGrid`에 gridCol 0개, 셀 안 목록, 콘텐츠 컨트롤 | 열 수 계산 오류 |
| 7 | X-P04 | 14×4, 병합 3, 세로선 없음 | 검출 실패 |
| 8 | X-T02 | 병합 덮인 셀의 hMerge·vMerge 반복 표기, 행·열 삽입·삭제 후 span | 비교적 낮음 (python-pptx 병합 API) |
| 예비 | X-D03 | 블록 수준 콘텐츠 컨트롤 안의 표 1개 (`w:sdt` 안) | **E03 DOCX 파서는 본문 직속 요소만 읽으므로 표 누락 가능성 높음** |

## 5. 블라인드 평가 프로토콜 (다음 단계 승인 시 적용)

1. **동결**: 평가할 파서 = 커밋 `34293ad`의 `src/parsers/doc_*.py`와 공통 후처리 규칙(header_repeat_rule). 실행 전 파일 SHA-256을 결과에 기록.
2. **정답 먼저**: 외부 문서 정답(`data/canonical/e03_external_truth_v1.json`, 공개 가능 부분만)과 수동 검수 기록을 만들고 해시를 고정한 뒤에만 파서를 실행한다. 정답 작성에는 평가 대상 파서를 쓰지 않는다 (지금까지의 검사도 zipfile+lxml·pypdfium2만 사용).
3. **최초 실행 1회 보존**: 동결 파서로 1회 실행한 IR·점수를 `external_blind_run1/`에 저장하고 해시를 기록, 이후 덮어쓰지 않는다 (재실행은 비결정성 확인용으로만, 결과는 별도 파일).
4. **조정은 새 버전으로**: 결함을 고칠 때는 파서 v2로 분리하고 변경 이력을 남긴다. v2 결과는 최종 8건이 아닌 **예비 문서(X-D03·X-D04·X-T03·X-T04, 받아 둔 PubTables 주석 중 미사용 문서)** 로 따로 보고해 과적합을 드러낸다.
5. **하드코딩 금지 검사**: 파서 소스에 외부 문서 파일명·헤더 문구·표 위치가 들어가지 않았는지 테스트로 확인 (기존 정답 문자열 검사와 같은 방식).
6. **채점기**: 외부 정답 구조에 맞춘 채점 어댑터가 필요하다 (파서는 바꾸지 않음). PDF 표 매칭은 기존과 같은 IoU ≥ 0.5 임시 기준, 셀 텍스트는 하이픈·공백 정규화 후 비교 (규칙은 실행 전 확정).

## 6. 수동 검수가 필요한 항목

- X-D01·X-D02: 셀 텍스트·병합 영역·본문 순서 정답 초안(XML 판독)을 사람이 Word·LibreOffice에서 열어 확인 (매크로 없음 확인됨, 편집 모드 저장 금지).
- X-T01: 논리 읽기 순서(그룹·연결선이 있는 슬라이드 5·6·7), 표 9×3 셀 텍스트, SmartArt 노드 텍스트(저장소 `diagram.test.ts` 기대값과 대조), 차트 텍스트를 평가에 넣을지 결정.
- X-T02: 1번 표 외 셀 텍스트(병합으로 옮겨진 문단 포함).
- PDF: 공식 주석과 직접 파서 규칙 차이(빈 셀·행 머리·헤더 정규화)를 어떻게 셀지 규칙 확정. 본문 텍스트·읽기 순서는 미측정으로 둘지 결정.
- X-P05: 공식 주석이 없어 정량 평가 대상에서 제외. 선 있는 표 정성 확인용으로만 쓸지, 정답을 사람이 만들지 결정 (만들 경우 이 문서의 원 출처·저작권 확인 선행).

## 7. 예상 한계

- 샘플 수가 형식별 2~4건이라 정확도 수치는 결함 사례 발견용이며 일반화하지 않는다.
- DOCX 2건 중 X-D01은 사람이 아닌 XML 조립 문서이고, X-D02는 Google Docs 산출물이다. **Microsoft Word·한글에서 저장한 DOCX는 확보하지 못했다** (해당 저장소 README도 Word 산출물이 아직 없다고 명시).
- PDF는 학술지 조판(FrameMaker·3B2) 4건으로, 기업 문서(보고서·견적서)와 레이아웃이 다르다. 선 있는 격자 표·스캔 문서는 공식 정답 없음.
- PubTables 주석은 원 PDF가 아니라 PMC가 현재 제공하는 PDF(버전 .1)와 대조했다 — 대응은 텍스트·쪽 크기로 확인했지만 바이트 동일성은 확인 불가.
- 제3자 판독(ts-pptx 스냅숏)은 그 도구의 해석이므로 단독 정답으로 쓰지 않는다.
- 실제 기업 문서 정확도는 여전히 미측정이다.

## 8. 공개 범위 (결정 대기 D-023)

- 공개 저장소에 올리는 것: 출처 목록(`configs/e03_external_sources.json`), 검사 스크립트, `external_candidates/`의 비식별 매니페스트·검사 결과, 이 문서.
- 올리지 않는 것: 외부 문서 원본·PubTables 주석 원본·PMC XML·저장소 README 사본 (`data/raw/external_documents/`). 라이선스상 재배포가 허용되더라도(Apache-2.0·MIT·CC BY, 고지 의무 있음) 사용자 결정 전에는 올리지 않는다. X-P05는 문서 자체 저작권 미확인.
