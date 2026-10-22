# E06 실패·오탐·미탐 기록 (자동 생성)

판정: scripts/e05_score.py (E05와 동일). 수동 조정 없음.

## shacl_pyshacl

- ERROR TP/FP/FN 99/0/0, WARNING 5/1/0
- 보고 분류: {'tp_reports': 104, 'partial': 4, 'acceptable': 25, 'derived': 54, 'fp': 1}
- 검출하지 못한 기대 규칙: 없음

### 오탐

| 데이터셋 | 규칙 | 엔터티 | 필드 |
|---|---|---|---|
| I-S08c | B10 | BOMLine | * |

### 부분 탐지

- I-S01b: S03 BOM.valid_from
- I-S02a: S06 Material.unit_cost
- I-S02b: S06 Operation.run_time_per_unit_h
- I-S03b: V06 Inventory.as_of_date

## shacl_hybrid

- ERROR TP/FP/FN 99/0/0, WARNING 5/1/0
- 보고 분류: {'tp_reports': 104, 'partial': 4, 'acceptable': 25, 'derived': 54, 'fp': 1}
- 검출하지 못한 기대 규칙: 없음

### 오탐

| 데이터셋 | 규칙 | 엔터티 | 필드 |
|---|---|---|---|
| I-S08c | B10 | BOMLine | * |

### 부분 탐지

- I-S01b: S03 BOM.valid_from
- I-S02a: S06 Material.unit_cost
- I-S02b: S06 Operation.run_time_per_unit_h
- I-S03b: V06 Inventory.as_of_date

## shacl_core_compare

- ERROR TP/FP/FN 90/0/9, WARNING 5/1/0
- 보고 분류: {'tp_reports': 95, 'partial': 4, 'acceptable': 23, 'derived': 42, 'fp': 1}
- 검출하지 못한 기대 규칙: 없음

### 오탐

| 데이터셋 | 규칙 | 엔터티 | 필드 |
|---|---|---|---|
| I-S08c | B10 | BOMLine | * |

### 미탐지

| 데이터셋 | 규칙 | 필드 | record_uid |
|---|---|---|---|
| I-S03a | S03 | due_date | rec_5ee648ee9a69daf6 |
| C-3 | S03 | due_date | rec_7a020872c9aedc5c |
| C-3 | S04 | status | rec_7a020872c9aedc5c |
| C-3 | R01 | product_id | rec_7a020872c9aedc5c |
| C-3 | V01 | on_hand_qty | rec_8e1d740335bee22c |
| C-3 | R07 | unit | rec_8e1d740335bee22c |
| C-3 | V06 | as_of_date | rec_8e1d740335bee22c |
| C-3 | S04 | status | rec_8c75fd594fab5063 |
| C-3 | B05 | valid_to | rec_8c75fd594fab5063 |

### 부분 탐지

- I-S01b: S03 BOM.valid_from
- I-S02a: S06 Material.unit_cost
- I-S02b: S06 Operation.run_time_per_unit_h
- I-S03b: V06 Inventory.as_of_date

## 변환 단계 기록 (채점 제외)

- I-S01b: {'notes': 1, 'kinds': ['ill_typed_literal'], 'expected_items_also_flagged_at_conversion': ['rec_133c1310b14b6c9d|valid_from']}
- I-S02a: {'notes': 1, 'kinds': ['ill_typed_literal'], 'expected_items_also_flagged_at_conversion': ['rec_ae7d3885fe9886f2|unit_cost']}
- I-S02b: {'notes': 1, 'kinds': ['ill_typed_literal'], 'expected_items_also_flagged_at_conversion': ['rec_1010133c49a93880|run_time_per_unit_h']}
- I-S03a: {'notes': 1, 'kinds': ['ill_typed_literal'], 'expected_items_also_flagged_at_conversion': ['rec_5ee648ee9a69daf6|due_date']}
- I-S03b: {'notes': 1, 'kinds': ['ill_typed_literal'], 'expected_items_also_flagged_at_conversion': ['rec_86fc41700e5b9227|as_of_date']}
- C-3: {'notes': 1, 'kinds': ['ill_typed_literal'], 'expected_items_also_flagged_at_conversion': ['rec_7a020872c9aedc5c|due_date']}
