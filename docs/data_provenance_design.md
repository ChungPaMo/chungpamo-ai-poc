# 데이터 출처 추적 설계 (PROV-O 참고) — E01

- 작성일: 2026-10-20 (설계안, **미구현**)
- 정책(분류·라이선스·표기 규칙)은 [data_provenance_policy.md](data_provenance_policy.md), 데이터 모델은 [manufacturing_data_schema.md](manufacturing_data_schema.md) 참고.
- 참고 표준: W3C PROV-O, W3C Recommendation 2013-04-30 — https://www.w3.org/TR/prov-o/ [확인]

## 1. 추적 대상

| 추적 정보 | 기록 위치 |
|---|---|
| 원본 파일 (경로, SHA-256) | 원본 파일 Entity |
| 원본 시트·행·컬럼 | 원본 위치(SourceLocator) |
| 데이터 출처 URL | 데이터셋 Entity |
| 실제/합성 구분 | `origin_class` ([정책 §1](data_provenance_policy.md)) |
| 변환 과정 | 변환 Activity (스크립트, 버전, 파라미터) |
| 변환 실행 시각 | Activity 시작·종료 시각 |
| 데이터셋 버전 | 데이터셋 Entity의 버전·해시 |
| 원본 ID ↔ 공통 ID 매핑 | 매핑 레코드 (원본 ID 값, 공통 ID, 매핑 규칙) |

## 2. PROV-O 표준 용어와 프로젝트 확장 구분

PROV-O는 **필수(mandatory) 속성을 정의하지 않는다** [확인: 문서에 필수 표시 없음, 한정(qualified) 형식과 비한정 형식 모두 선택적]. 따라서 아래 "필수"는 **이 프로젝트가 정한 필수**다.

### 2.1 사용할 PROV-O 표준 용어 (Starting Point 중심)

| PROV-O 용어 | 구분 | 프로젝트에서의 의미 | 프로젝트 필수 |
|---|---|---|---|
| `prov:Entity` | Starting Point 클래스 | 데이터셋, 원본 파일, 원본 레코드, 변환된 레코드 | Y |
| `prov:Activity` | Starting Point 클래스 | 파싱·정규화·매핑·오류 주입·합성 생성 실행 1회 | Y |
| `prov:Agent` | Starting Point 클래스 | 스크립트(SoftwareAgent), 담당자 역할(사람 이름 대신 역할) | N |
| `prov:wasGeneratedBy` | Starting Point 속성 | 변환 레코드 → 생성한 Activity | Y |
| `prov:used` | Starting Point 속성 | Activity → 입력 파일·레코드 | Y |
| `prov:wasDerivedFrom` | Starting Point 속성 | 변환 레코드 → 원본 레코드 | Y |
| `prov:startedAtTime`, `prov:endedAtTime` | Starting Point 속성 | 변환 실행 시각 | Y |
| `prov:wasAssociatedWith` | Starting Point 속성 | Activity → 실행 스크립트 | Y |
| `prov:wasAttributedTo` | Starting Point 속성 | 데이터셋 → 제공 주체(UCI, Kaggle, 프로젝트) | N |
| `prov:hadPrimarySource` | Expanded (wasDerivedFrom 하위) | 공개 데이터셋 → 최초 출처 | N |
| `prov:wasRevisionOf` | Expanded (wasDerivedFrom 하위) | 데이터셋 v2 → v1 | N |
| `prov:Collection`, `prov:hadMember` | Expanded | 데이터셋과 소속 레코드 | N |
| `prov:Plan` | Expanded | 변환 규칙·매핑 사전 | N |

### 2.2 프로젝트 확장 속성 (네임스페이스 예: `cpm:` — 이름은 미정)

PROV-O에 대응 용어가 없거나, 위치를 기계적으로 비교해야 하는 항목이다. 표준 용어로 오해하지 않도록 별도 네임스페이스를 쓴다.

| 확장 속성 | 대상 | 의미 |
|---|---|---|
| `cpm:originClass` | Entity | `PUBLIC_REAL` / `SYNTHETIC` 등 (정책 §1) |
| `cpm:generationMethod`, `cpm:allocationShare` | 합성 레코드 | `GENERATED` / `ALLOCATED` / `MAPPED` / `TRANSFORMED`와 배분 비율. 원본 공개 레코드와의 연결은 표준 `prov:wasDerivedFrom` 사용 (정책 §4.2) |
| `cpm:sourceFile` | 원본 레코드 | 원본 파일 Entity |
| `cpm:sheetName`, `cpm:rowNumber`, `cpm:columnName` | 원본 레코드·필드 값 | 원본 위치. 문서(PDF 등)는 `cpm:page`, `cpm:tableId`, `cpm:cell` 추가 |
| `cpm:sha256` | 파일·데이터셋 | 무결성 확인 |
| `cpm:datasetVersion` | 데이터셋 | 버전 문자열 |
| `cpm:sourceUrl` | 데이터셋 | 출처 URL (`prov:atLocation`은 범위가 넓어 그대로 쓰지 않고 별도 속성으로 둠) |
| `cpm:recordUid` | 원본 레코드 | 원본 레코드 고유 ID (§3) |
| `cpm:businessId` | 원본 레코드 | 원본에 적힌 업무 ID 값 그대로 (중복 가능) |
| `cpm:mappedTo` | 원본 레코드 | 매핑된 공통 업무 개체 |
| `cpm:mappingRule` | 매핑 | 적용한 매핑 규칙 ID (컬럼명 사전 등) |
| `cpm:scriptVersion`, `cpm:parameters`, `cpm:randomSeed` | Activity | 재현 정보 |

## 3. 원본 레코드 ID와 업무 개체 ID 분리 (중복 ID 병합 방지)

### 3.1 문제

RDF에서 `product_id = P001`을 URI `ex:product/P001`로 바로 바꾸면, 원본에 `P001`이 두 행 있을 때 두 행의 속성이 **한 노드로 합쳐진다**. 그러면 중복 ID 오류가 그래프에서 보이지 않고, 상충하는 값(예: 단위 kg과 g)이 한 노드에 같이 붙어 원인 추적이 어려워진다.

### 3.2 설계

| 계층 | ID | 만드는 방법 | 유일성 |
|---|---|---|---|
| ① 원본 레코드 | `record_uid` | `<dataset_version>:<source_file_sha256 앞 12자>:<sheet>:<row>`를 해시한 값 (결정적: 같은 입력 → 같은 ID) | 항상 유일 |
| ② 업무 ID 값 | `business_id` | 원본 셀 값 그대로 (정규화 전 값도 보존) | 중복 가능 |
| ③ 공통 업무 개체 | 정규 URI (예: `ex:product/P001`) | 검증 통과 후 매핑 규칙으로 생성 | 정상 데이터에서 유일 |

- 변환 순서: **원본 → ① 레코드 노드 생성 → 검증(SHACL·SQL) → ③ 개체 매핑**. 검증은 ① 계층에서 수행하므로 중복 ID는 "같은 `business_id`를 가진 서로 다른 `record_uid`"로 탐지된다(schema QR-01).
- 중복 ID 레코드는 ③으로 매핑하지 않거나(`cpm:mappedTo` 없음), 사람이 해결 규칙을 정한 뒤 매핑한다. 어느 쪽으로 할지는 E06 설계 시 결정.
- 여러 업체(Vendor A의 `product_id`, Vendor B의 `품목번호`)가 같은 개체를 가리키는 경우: 각 원본 레코드는 자신의 ①을 유지하고 같은 ③으로 `cpm:mappedTo` 한다. 매핑 근거는 `cpm:mappingRule`로 남긴다. → "서로 다른 기업의 컬럼·ID 매핑 가능 여부" 평가 항목의 근거가 된다.
- SQL 방식도 같은 원칙: 원본 적재 테이블(`stg_*`)은 `record_uid`를 PK로 두고, 업무 PK 제약은 정제 테이블에만 건다.

## 4. 레코드별 추적 열 (SQL/JSON 공통)

| 열 | 내용 |
|---|---|
| `record_uid` | §3.2 ① |
| `source_ref` | JSON 객체: `{file, sheet, row, columns: {field: column_name}}` (문서이면 page, table_id, cell 추가) |
| `origin_class` | 정책 §1 |
| `dataset_version` | 데이터셋 버전 |
| `transform_run_id` | 이 레코드를 만든 변환 Activity ID |

변환 Activity 기록(`transform_runs` 표 또는 JSON): `run_id`, 스크립트 경로·Git 커밋, 시작·종료 시각, 입력 파일 해시, 출력 파일 해시, 파라미터, 시드.

## 5. 원본 위치 역추적 판정

[evaluation_protocol.md](evaluation_protocol.md) §5.4의 "원본 위치 역추적 성공률" 측정 기준이다.

- 질의 결과 또는 오류 보고의 값 하나에서 시작해 `record_uid` → `source_ref`로 원본 파일·시트·행·열에 도달하고, 그 위치의 원본 값이 정답 원천의 위치 정보와 일치하면 성공.
- 레코드는 찾았지만 열(필드) 정보가 없으면 `부분 성공`으로 따로 센다.

## 6. 구현 부담 메모 (E06 판단용)

- 레코드 노드 계층을 두면 RDF 트리플 수가 업무 개체만 표현할 때보다 늘어난다. 늘어난 양은 E06에서 측정한다(추정치를 미리 적지 않음).
- PROV-O 한정(qualified) 패턴(`prov:qualifiedUsage` 등)은 사용 역할·시각을 세밀히 기록할 필요가 확인될 때만 쓴다. 기본은 비한정 Starting Point 속성으로 충분하다.
