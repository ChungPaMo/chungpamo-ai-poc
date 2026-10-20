# E03 외부 제작 문서 후보 — 검사 결과 요약 (2026-10-20)

> 문서 확보·검사만 수행. **파서 실행·정확도 채점 없음** (블라인드 유지). 평가 설계: [docs/e03_external_testset_plan.md](../../../docs/e03_external_testset_plan.md)
> 검사 도구: zipfile + lxml (OOXML), pypdfium2 (PDF) — 평가 대상 파서(python-docx·python-pptx·pypdf·pdfplumber)와 `src/parsers` 미사용.
> 원본은 `data/raw/external_documents/` (Git 제외). 이 폴더에는 출처·해시·구조 수치만 둔다.

> 후속(2026-10-20): `manifest.csv`·`inspection.json`은 dev·holdout 17건을 더해 다시 생성됨(30건). 아래 표는 확보 단계의 13건. 추가 문서 중 PDF 3건의 첨부(/EmbeddedFile)는 Acrobat Distiller 설정 파일(joboptions)로 확인, 실행하지 않음.

## 1. 파일 목록

| ID | 역할 | 파일 | SHA-256 (앞 16자) | 바이트 | 단위 | 표 | 병합 표기 | 만든 프로그램 (메타데이터) |
|---|---|---|---|---|---|---|---|---|
| X-D01 | 최종 | kitchen-sink.docx | 14e39475fb2f85ad | 9,497 | 구역 1 | 2 | gridSpan 2, vMerge 3 | app.xml 없음 (저장소: XML 직접 조립) |
| X-D02 | 최종 | google-docs-export.docx | e975d3f44427dcd8 | 17,433 | 구역 1 | 2 | gridSpan 1, vMerge 4 | app.xml 없음 (저장소: Google Docs 저장) |
| X-T01 | 최종 | mixed.pptx | db80910224b01b46 | 105,638 | 슬라이드 11 | 1 (+차트 1, SmartArt 1) | 없음 | Microsoft Macintosh PowerPoint 16.0 |
| X-T02 | 최종 | table-merge-encoding.pptx | c2756f8f042c92c8 | 39,880 | 슬라이드 5 | 5 | gridSpan 8, rowSpan 8, hMerge 11, vMerge 11 | Microsoft Office PowerPoint 16.0 |
| X-P01 | 최종 | PMC2008195.1.pdf | 98c6255a845dce75 | 348,002 | 8쪽 | 2 (공식 주석) | 병합 셀 3 | FrameMaker 7.0 / Distiller 5.0.5 |
| X-P02 | 최종 | PMC2671505.1.pdf | b41e4a0f793fee14 | 1,344,218 | 14쪽 | 4 (공식 주석) | 병합 셀 13 | FrameMaker 7.1 / Distiller 7.0 |
| X-P03 | 최종 | PMC3296738.1.pdf | 144ad3a42b3fe759 | 358,917 | 8쪽 | 2 (공식 주석) | 병합 셀 10 | 3B2 7.51n / Distiller 9.0 |
| X-P04 | 최종 | PMC4729796.1.pdf | ec906d0d0d2e5618 | 884,550 | 9쪽 | 1 (공식 주석) | 병합 셀 3 | 3B2 8.07e / Distiller 9.0 |
| X-D03 | 예비 | content-controls.docx | c7a36fe8b5e807a8 | 6,735 | 구역 2 | 5 (콘텐츠 컨트롤 안 1) | 없음 | XML 직접 조립 |
| X-D04 | 예비 | preserved-markup.docx | 8bfbf9f4a01c3936 | 6,204 | 구역 1 | 2 | 없음 | XML 직접 조립 |
| X-T03 | 예비 | group-transform.pptx | 492fa2a2b69ee5f9 | 45,469 | 슬라이드 2 | 0 (그룹 8, 회전 22, 반전 17) | — | Microsoft Office PowerPoint 16.0 |
| X-T04 | 예비 | table-placeholder.pptx | f18ae67b1df1cc1c | 37,405 | 슬라이드 1 | 1 (자리표시자 안) | 없음 | Microsoft Office PowerPoint 16.0 |
| X-P05 | 예비 | nics-background-checks-2015-11.pdf | 4f0ae6e017b0e97d | 90,468 | 1쪽 | 미확인 (주석 없음) | 미확인 | Mac OS X Quartz PDFContext |

- 전체 SHA-256·출처 URL·라이선스: `manifest.csv`, 상세 구조: `inspection.json`
- 무결성: PPTX 4건 = 저장소 README 공개 SHA-256과 일치 / PDF 4건 = PMC 메타데이터 MD5와 일치 / DOCX는 공개 해시 없음 (커밋 고정 URL로 확보)
- 형식 검증: 13건 모두 시그니처 정상(OOXML `PK`, PDF `%PDF-`), OOXML 압축 무결성 검사 통과, 주 콘텐츠 형식이 매크로 사용 형식 아님

## 2. 안전성

| 항목 | 결과 |
|---|---|
| 매크로·ActiveX (OOXML) | 0건 |
| OLE·임베딩 | X-T01 차트 데이터 통합문서 1건 (xlsx, VBA 없음, 외부 링크 없음) |
| 외부 관계 (OOXML) | 하이퍼링크 2건 (example.com) |
| PDF JavaScript·Launch·첨부·XFA·암호화 | 0건 (객체 사전·객체 스트림 검사, 스트림 본문 제외) |
| PDF OpenAction | 3건 — 모두 쪽 이동(GoTo·목적지 배열) |
| 임베드 글꼴 (OOXML) | 0건 |

## 3. PDF 공식 주석 대응 (PubTables-1M)

| ID | 표 (쪽 번호 0부터) | 행×열 | 병합 셀 | 헤더 셀 | 행 머리 | 빈 셀 | 쪽 크기 | 셀 텍스트 대응 | 선 형태 |
|---|---|---|---|---|---|---|---|---|---|
| X-P01 | t0 (p2) | 30×3 | 1 | 3 | 1 | 26 | 일치 | 62/62 | 가로선만 |
| X-P01 | t1 (p4) | 17×3 | 2 | 3 | 2 | 0 | 일치 | 47/47 | 가로선만 |
| X-P02 | t0 (p2) | 8×17 | 13 | 18 | 0 | 0 | 일치 | 118/120 | 가로선만 |
| X-P02 | t1 (p3) | 4×7 | 0 | 7 | 0 | 1 | 일치 | 27/27 | 가로선만 |
| X-P02 | t2 (p4) | 3×6 | 0 | 6 | 0 | 1 | 일치 | 17/17 | 가로선만 |
| X-P02 | t3 (p6) | 12×8 | 0 | 8 | 0 | 0 | 일치 | 96/96 | 가로선만 |
| X-P03 | t0 (p3) | 36×5 | 7 | 5 | 7 | 21 | 일치 | 131/131 | 가로선만 (기타 경로 360) |
| X-P03 | t1 (p5) | 18×7 | 3 | 9 | 0 | 0 | 일치 | 121/121 | 가로선만 (기타 경로 244) |
| X-P04 | t0 (p3) | 14×4 | 3 | 5 | 0 | 0 | 일치 | 53/53 | 가로선만 |

- 셀 텍스트 대응: 주석 셀 bbox 영역의 PDF 텍스트(PDFium)와 주석 텍스트를 공백 제거 후 비교 — 455/457. 불일치 2건은 영역 경계 글자 잘림·하이픈 제어문자(주석 오류 아님)
- 주석된 표 수 = 논문 JATS XML의 표 수 (2·4·2·1) → 문서 안 모든 표가 주석됨
- X-P05(선 있는 격자, 세로선 364개)는 공식 주석이 없어 정량 평가 대상으로 확정하지 않음

## 4. 하지 않은 것

- 평가 대상 파서 실행, 정답 파일 작성, 정확도 채점, 파서 수정, Upstage 호출, OCR
