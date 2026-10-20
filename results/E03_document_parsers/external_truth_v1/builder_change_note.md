# 정답 작성기 변경 기록 (정답 v1 고정 이후)

- 2026-10-21: `scripts/e03_build_external_truth.py`에서 X-T01 SmartArt 공식 노드 문자열 11개(ts-pptx `test/read/diagram.test.ts` NODE_TEXT)를 코드 상수에서 제거하고,
  로컬(Git 제외) 공식 테스트 파일 `data/raw/external_documents/truth_sources/ts-pptx_diagram.test.ts`에서 읽도록 바꿈 (D-025: 외부 원문 문자열을 공개 코드에 두지 않음).
- 정답 파일은 다시 만들지 않았다. `--verify-against-frozen`으로 바뀐 작성기의 출력이 고정된 v1과 `created`를 뺀 모든 필드(schema·version·rules·documents 등)에서 같음을 확인했다.
- 같은 날 X-T02 셀 기대값 2개(`table-merge-encoding.test.ts`)와 smartart-families 노드 접두어(README)도 코드 상수에서 빼고 로컬 공식 파일에서 읽도록 바꿈 → 다시 `--verify-against-frozen` 일치 확인.
- 공개용 `truth_manifest.json`의 단언 설명 3개에서 정답 문자열을 '(로컬 정답 참조)'로 가림 (`public_redaction` 필드). 정답 파일·해시는 그대로.
- 따라서 `truth_manifest.json`의 `builder_sha256`은 v1 작성 당시 작성기 해시이며 현재 파일 해시와 다르다. 정답 해시 `f253775a698e3582…`는 그대로다.
