# E05 실패·오탐·미탐 기록 (자동 생성, scripts/e05_run.py)

판정 기준: scripts/e05_score.py. 수동 조정 없음. 정답셋 정의 한계로 보이는 항목도 판정대로 남긴다.

## python_full

- ERROR TP/FP/FN: 99/0/0, WARNING TP/FP/FN: 5/1/0
- 보고 분류: {'tp_reports': 104, 'derived': 65, 'acceptable': 25, 'fp': 1}
- 한 번도 검출하지 못한 기대 규칙: 없음

### 오탐

| 데이터셋 | 규칙 | 엔터티 | 필드 | 건수 |
|---|---|---|---|---|
| I-S08c | B10 | BOMLine | * | 1 |

## python_pydantic_only

- ERROR TP/FP/FN: 31/0/68, WARNING TP/FP/FN: 1/0/4
- 보고 분류: {'tp_reports': 32}
- 한 번도 검출하지 못한 기대 규칙: B01, B02, B04, B06, B08, B09, B10, B11, B12, R01, R02, R03, R04, R05, R06, R07, S08, V03, V04, V06, V08, V09, V11, V12

### 미탐지

| 데이터셋 | 규칙 | 필드 | record_uid |
|---|---|---|---|
| I-S08a | S08 | * | rec_878631a4408e8636 |
| I-S08b | S08 | * | rec_21dee955185a170d |
| I-S08c | S08 | * | rec_cff5a7adc755e66c |
| I-R01 | R01 | product_id | rec_dc024ee206f72b29 |
| I-R02a | R02 | component_material_id | rec_63312641cc902ec9 |
| I-R02b | R02 | component_material_id | rec_87ac4c1b12a1badc |
| I-R02c | R02 | component_material_id | rec_352cbb3264509242 |
| I-R02c | R02 | material_id | rec_fb694a77ac062b4c |
| I-R02c | R02 | item_id | rec_367d8e714ac1b695 |
| I-R03 | R03 | supplier_id | rec_77999e04447f956f |
| I-R04 | R04 | bom_id | rec_d2cca52a274869d1 |
| I-R05a | R05 | resource_id | rec_399d5a02c199abe7 |
| I-R05b | R05 | resource_id | rec_233a6ff89a36c0a1 |
| I-R06 | R06 | plan_id | rec_1607d4a2a6c2de41 |
| I-R07 | R07 | unit | rec_86fc41700e5b9227 |
| I-B01a | B01 | component_product_id | rec_0bdf55f468360e43 |
| I-B01b | B01 | component_product_id | rec_5db7c125a15f98df |
| I-B02a | B02 | * | rec_67ca1c17bd0470af |
| I-B02b | B02 | * | rec_426ffe9aea1abdd3 |
| I-B02c | B02 | * | rec_f8df671e73b78d87 |
| I-B04 | B04 | * | rec_c7752d8dbab4f109 |
| I-B06 | B06 | product_id | rec_879776be691e6d69 |
| I-B06 | B06 | product_id | rec_6d1729ee9e2cc07d |
| I-B06 | B06 | product_id | rec_7bc777cf179e236c |
| I-B06 | B06 | product_id | rec_1108df78610f37c0 |
| I-B06 | B06 | product_id | rec_6296bf848588fbb2 |
| I-B06 | B06 | product_id | rec_e9a93b809ab8820f |
| I-B06 | B06 | product_id | rec_613143b4dbd01957 |
| I-B06 | B06 | product_id | rec_573143a632ce6cca |
| I-B06 | B06 | product_id | rec_aa3127bb3163604b |
| I-B08a | B08 | unit | rec_4e29fcc3c9b08c42 |
| I-B08b | B08 | unit | rec_f8699be15b52ae9d |
| I-B09 | B09 | * | rec_133c1310b14b6c9d |
| I-B10 | B10 | * | rec_82419ef304cbe3f2 |
| I-B11a | B11 | is_preferred | rec_0f8418a171df4bdb |
| I-B11b | B11 | is_preferred | rec_9674d1988b25c5b2 |
| I-B11b | B11 | is_preferred | rec_be8ff9405fc00ef0 |
| I-B12 | B12 | allocation_share | rec_c182faba659b8610 |
| I-V03 | V03 | on_hand_qty | rec_c2b4c918d638b848 |
| I-V04 | V04 | * | rec_9abfd3b315011b76 |
| I-V06 | V06 | as_of_date | rec_9ec12f93b3c09d6d |
| I-V08 | V08 | product_id | rec_f47deba67c2464fb |
| I-V08 | V08 | product_id | rec_01be0d60c0db0469 |
| I-V08 | V08 | product_id | rec_acb02a9d1f81ac6f |
| I-V08 | V08 | product_id | rec_341d5b819ed04880 |
| I-V08 | V08 | product_id | rec_7a020872c9aedc5c |
| I-V08 | V08 | product_id | rec_1607d4a2a6c2de41 |
| I-V08 | V08 | product_id | rec_879776be691e6d69 |
| I-V08 | V08 | product_id | rec_6d1729ee9e2cc07d |
| I-V08 | V08 | product_id | rec_7bc777cf179e236c |
| I-V08 | V08 | product_id | rec_233a6ff89a36c0a1 |
| I-V08 | V08 | product_id | rec_1108df78610f37c0 |
| I-V08 | V08 | product_id | rec_6296bf848588fbb2 |
| I-V08 | V08 | product_id | rec_e9a93b809ab8820f |
| I-V08 | V08 | product_id | rec_972fda2be6d7eae4 |
| I-V08 | V08 | product_id | rec_613143b4dbd01957 |
| I-V08 | V08 | product_id | rec_573143a632ce6cca |
| I-V08 | V08 | product_id | rec_aa3127bb3163604b |
| I-V09 | V09 | resource_id | rec_42835a48ce9fb52a |
| I-V11 | V11 | production_mode | rec_f5d557f8c11d5d1f |
| I-V12 | V12 | period_start | rec_47539f6525643972 |
| C-1 | R02 | component_material_id | rec_63312641cc902ec9 |
| C-1 | B02 | * | rec_f8df671e73b78d87 |
| C-2 | R02 | component_material_id | rec_352cbb3264509242 |
| C-2 | R02 | material_id | rec_fb694a77ac062b4c |
| C-2 | R02 | item_id | rec_367d8e714ac1b695 |
| C-2 | S08 | * | rec_06b9b2ac81e02ac5 |
| C-2 | B01 | component_product_id | rec_6771109c49c7f75f |
| C-3 | R01 | product_id | rec_7a020872c9aedc5c |
| C-3 | R07 | unit | rec_8e1d740335bee22c |
| C-3 | V06 | as_of_date | rec_8e1d740335bee22c |
| C-3 | B05 | valid_to | rec_8c75fd594fab5063 |

## sql_queries

- ERROR TP/FP/FN: 99/0/0, WARNING TP/FP/FN: 5/1/0
- 보고 분류: {'tp_reports': 104, 'derived': 65, 'acceptable': 25, 'fp': 1}
- 한 번도 검출하지 못한 기대 규칙: 없음

### 오탐

| 데이터셋 | 규칙 | 엔터티 | 필드 | 건수 |
|---|---|---|---|---|
| I-S08c | B10 | BOMLine | * | 1 |

## sql_constraints

- ERROR TP/FP/FN: 50/114/49, WARNING TP/FP/FN: 0/0/5
- 보고 분류: {'tp_reports': 50, 'partial': 1, 'fp': 114}
- 한 번도 검출하지 못한 기대 규칙: B01, B02, B04, B06, B08, B09, B10, B11, B12, S07, V08, V09, V11, V12
- 오탐 중 연쇄 거부(부모 행이 먼저 거부되어 자식 FK 실패): 114/114
- 적재 거부 행 수(데이터셋별, 0 제외): {'I-S01a': {'rejected_rows': 1, 'unclassified': 0}, 'I-S01b': {'rejected_rows': 4, 'unclassified': 0}, 'I-S02a': {'rejected_rows': 3, 'unclassified': 0}, 'I-S02b': {'rejected_rows': 1, 'unclassified': 0}, 'I-S03a': {'rejected_rows': 1, 'unclassified': 0}, 'I-S03b': {'rejected_rows': 1, 'unclassified': 0}, 'I-S04a': {'rejected_rows': 1, 'unclassified': 0}, 'I-S04b': {'rejected_rows': 4, 'unclassified': 0}, 'I-S05': {'rejected_rows': 4, 'unclassified': 0}, 'I-S06a': {'rejected_rows': 1, 'unclassified': 0}, 'I-S06b': {'rejected_rows': 1, 'unclassified': 0}, 'I-S06c': {'rejected_rows': 1, 'unclassified': 0}, 'I-S06d': {'rejected_rows': 1, 'unclassified': 0}, 'I-S08a': {'rejected_rows': 1, 'unclassified': 0}, 'I-S08b': {'rejected_rows': 1, 'unclassified': 0}, 'I-S08c': {'rejected_rows': 1, 'unclassified': 0}, 'I-R01': {'rejected_rows': 1, 'unclassified': 0}, 'I-R02a': {'rejected_rows': 1, 'unclassified': 0}, 'I-R02b': {'rejected_rows': 1, 'unclassified': 0}, 'I-R02c': {'rejected_rows': 2, 'unclassified': 0}, 'I-R03': {'rejected_rows': 1, 'unclassified': 0}, 'I-R04': {'rejected_rows': 1, 'unclassified': 0}, 'I-R05a': {'rejected_rows': 1, 'unclassified': 0}, 'I-R05b': {'rejected_rows': 1, 'unclassified': 0}, 'I-R06': {'rejected_rows': 1, 'unclassified': 0}, 'I-R07': {'rejected_rows': 1, 'unclassified': 0}, 'I-B03': {'rejected_rows': 4, 'unclassified': 0}, 'I-B05a': {'rejected_rows': 4, 'unclassified': 0}, 'I-B05b': {'rejected_rows': 4, 'unclassified': 0}, 'I-B07': {'rejected_rows': 1, 'unclassified': 0}, 'I-B13': {'rejected_rows': 1, 'unclassified': 0}, 'I-B14': {'rejected_rows': 92, 'unclassified': 0}, 'I-V01': {'rejected_rows': 1, 'unclassified': 0}, 'I-V02': {'rejected_rows': 1, 'unclassified': 0}, 'I-V03': {'rejected_rows': 1, 'unclassified': 0}, 'I-V04': {'rejected_rows': 1, 'unclassified': 0}, 'I-V05': {'rejected_rows': 1, 'unclassified': 0}, 'I-V06': {'rejected_rows': 1, 'unclassified': 0}, 'I-V07': {'rejected_rows': 1, 'unclassified': 0}, 'I-V10': {'rejected_rows': 1, 'unclassified': 0}, 'C-1': {'rejected_rows': 4, 'unclassified': 0}, 'C-2': {'rejected_rows': 3, 'unclassified': 0}, 'C-3': {'rejected_rows': 6, 'unclassified': 0}}

### 오탐

| 데이터셋 | 규칙 | 엔터티 | 필드 | 건수 |
|---|---|---|---|---|
| C-3 | R04 | BOMLine | bom_id | 3 |
| I-B03 | R04 | BOMLine | bom_id | 3 |
| I-B05a | R04 | BOMLine | bom_id | 3 |
| I-B05b | R04 | BOMLine | bom_id | 3 |
| I-B14 | R01 | BOM | product_id | 2 |
| I-B14 | R01 | Operation | product_id | 2 |
| I-B14 | R01 | Order | product_id | 7 |
| I-B14 | R01 | ProductionPlanLine | product_id | 12 |
| I-B14 | R01 | SalesHistory | product_id | 60 |
| I-B14 | R04 | BOMLine | bom_id | 8 |
| I-S01b | R04 | BOMLine | bom_id | 3 |
| I-S02a | R02 | BOMLine | component_material_id | 1 |
| I-S02a | R02 | SupplierMaterial | material_id | 1 |
| I-S04b | R04 | BOMLine | bom_id | 3 |
| I-S05 | R03 | SupplierMaterial | supplier_id | 3 |

### 미탐지

| 데이터셋 | 규칙 | 필드 | record_uid |
|---|---|---|---|
| I-S01b | S01 | valid_from | rec_133c1310b14b6c9d |
| I-S07 | S07 | site_id | rec_56af60086ee67acf |
| I-R02c | R02 | item_id | rec_367d8e714ac1b695 |
| I-B01a | B01 | component_product_id | rec_0bdf55f468360e43 |
| I-B01b | B01 | component_product_id | rec_5db7c125a15f98df |
| I-B02a | B02 | * | rec_67ca1c17bd0470af |
| I-B02b | B02 | * | rec_426ffe9aea1abdd3 |
| I-B02c | B02 | * | rec_f8df671e73b78d87 |
| I-B04 | B04 | * | rec_c7752d8dbab4f109 |
| I-B06 | B06 | product_id | rec_879776be691e6d69 |
| I-B06 | B06 | product_id | rec_6d1729ee9e2cc07d |
| I-B06 | B06 | product_id | rec_7bc777cf179e236c |
| I-B06 | B06 | product_id | rec_1108df78610f37c0 |
| I-B06 | B06 | product_id | rec_6296bf848588fbb2 |
| I-B06 | B06 | product_id | rec_e9a93b809ab8820f |
| I-B06 | B06 | product_id | rec_613143b4dbd01957 |
| I-B06 | B06 | product_id | rec_573143a632ce6cca |
| I-B06 | B06 | product_id | rec_aa3127bb3163604b |
| I-B08a | B08 | unit | rec_4e29fcc3c9b08c42 |
| I-B08b | B08 | unit | rec_f8699be15b52ae9d |
| I-B09 | B09 | * | rec_133c1310b14b6c9d |
| I-B10 | B10 | * | rec_82419ef304cbe3f2 |
| I-B11a | B11 | is_preferred | rec_0f8418a171df4bdb |
| I-B11b | B11 | is_preferred | rec_9674d1988b25c5b2 |
| I-B11b | B11 | is_preferred | rec_be8ff9405fc00ef0 |
| I-B12 | B12 | allocation_share | rec_c182faba659b8610 |
| I-V08 | V08 | product_id | rec_f47deba67c2464fb |
| I-V08 | V08 | product_id | rec_01be0d60c0db0469 |
| I-V08 | V08 | product_id | rec_acb02a9d1f81ac6f |
| I-V08 | V08 | product_id | rec_341d5b819ed04880 |
| I-V08 | V08 | product_id | rec_7a020872c9aedc5c |
| I-V08 | V08 | product_id | rec_1607d4a2a6c2de41 |
| I-V08 | V08 | product_id | rec_879776be691e6d69 |
| I-V08 | V08 | product_id | rec_6d1729ee9e2cc07d |
| I-V08 | V08 | product_id | rec_7bc777cf179e236c |
| I-V08 | V08 | product_id | rec_233a6ff89a36c0a1 |
| I-V08 | V08 | product_id | rec_1108df78610f37c0 |
| I-V08 | V08 | product_id | rec_6296bf848588fbb2 |
| I-V08 | V08 | product_id | rec_e9a93b809ab8820f |
| I-V08 | V08 | product_id | rec_972fda2be6d7eae4 |
| I-V08 | V08 | product_id | rec_613143b4dbd01957 |
| I-V08 | V08 | product_id | rec_573143a632ce6cca |
| I-V08 | V08 | product_id | rec_aa3127bb3163604b |
| I-V09 | V09 | resource_id | rec_42835a48ce9fb52a |
| I-V11 | V11 | production_mode | rec_f5d557f8c11d5d1f |
| I-V12 | V12 | period_start | rec_47539f6525643972 |
| C-1 | B02 | * | rec_f8df671e73b78d87 |
| C-2 | R02 | item_id | rec_367d8e714ac1b695 |
| C-2 | B01 | component_product_id | rec_6771109c49c7f75f |
| C-3 | S04 | status | rec_7a020872c9aedc5c |
| C-3 | R01 | product_id | rec_7a020872c9aedc5c |
| C-3 | R07 | unit | rec_8e1d740335bee22c |
| C-3 | V06 | as_of_date | rec_8e1d740335bee22c |
| C-3 | B05 | valid_to | rec_8c75fd594fab5063 |

### 부분 탐지 (기대 레코드에 다른 규칙·필드로 보고)

- I-S01b: S03 BOM.valid_from
