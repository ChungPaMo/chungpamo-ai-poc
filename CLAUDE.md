# CLAUDE.md — 충파모 과제 7 사전 기술 PoC 작업 규칙

## 프로젝트 성격
- 이 프로젝트는 **실험 기반 사전 PoC**다. 제품 개발이 아니라, 본개발에 적용할 기술의 적합성을 실측 근거로 판단하는 것이 목적이다.
- 실험 계획·평가 기준·결정 기록: `docs/experiment_plan.md`, `docs/evaluation_protocol.md`, `docs/decisions.md`, `docs/environment_inventory.md`

## 역할
- ChatGPT: 기술 설계, 평가 기준 수립, 결과 검토·검증, 기술 채택 판단
- Claude Code: 코드 구현, 환경 구축, 테스트 실행, 성능 측정, 결과 파일 작성
- 사용자: 작업 승인 및 단계별 진행 결정

## 실행 환경
- Windows 로컬 Python 3.11.9 + 표준 `venv` + `pip`. uv·conda 등 다른 도구는 사용하지 않는다.
- 의존성은 `requirements.lock`(pip freeze 형식)으로 고정한다. 새 패키지는 승인 후 설치하고 lock을 갱신한다.
- 가상환경을 활성화하지 않고 명시적 경로로 실행한다: `.\.venv\Scripts\python.exe ...` (PowerShell 실행 정책 변경 금지)
- 전역 Python 패키지를 실험에 사용하지 않는다.
- PowerShell 5.1 기준으로 명령을 작성한다 (`&&` 미지원). 콘솔은 cp949이므로 결과는 UTF-8 파일로 저장한다.
- GPU가 필요한 실험만 별도 승인 후 Google Colab에서 수행한다.

## 진행 규칙
- 실험은 E00부터 순서대로 단계별 수행한다.
- 이전 단계 결과를 사용자·ChatGPT가 검토하기 전에 다음 단계를 자동으로 시작하지 않는다.
- 실험 상태는 `NOT_STARTED / RUNNING / COMPLETED / BLOCKED / INVALID`로 기록한다. 실험 완료가 기술 채택을 의미하지 않는다.

## 결과 기록 규칙
- 측정하지 않은 성능을 추정하거나 성공으로 기록하지 않는다. 측정하지 않은 값은 `미측정`으로 적는다.
- 테스트 결과나 비교 결과를 수동으로 True/통과 처리하지 않는다. 실패는 로그와 함께 보존한다.
- 정량 목표값을 근거 없이 정하지 않는다 (`팀 합의 필요`).
- 결과 파일에 Windows 사용자 이름·홈 경로, API 키, 비밀값을 기록하지 않는다.

## 데이터·보안 규칙
- 실제 기업 데이터를 외부 API로 전송하지 않는다. 외부 API 테스트는 합성·공개 데이터만, 승인 후 사용한다.
- `docs/` 아래의 원본 PDF/DOCX는 비공개 자료다. 이동·삭제·수정하지 않으며 Git에 추적하지 않는다.
- 실제 기업 데이터는 `data/raw/`에만 두고 Git에 추적하지 않는다.

## Git 규칙
- 원격 저장소: `origin` = https://github.com/ChungPaMo/chungpamo-ai-poc (**Public**), 기준 브랜치 `main`. 2026-10-20 사용자 승인으로 연결·최초 푸시 완료(decisions.md DEC-20261020-04).
- 커밋과 푸시는 **매번 사용자 승인 후에만** 한다. Force push 금지, 기존 커밋 삭제 금지.
- Public 저장소이므로 커밋 전에 스테이징 대상의 실제 내용을 검사한다: 비공개 원본, 팀원 실명, 외부 공개가 제한된 평가 자료의 내용, API 키·토큰, 사용자 이름·PC 이름·홈 경로, 공개 데이터 원본 파일(`data/raw/`)을 올리지 않는다.
- `git add -A` / `git add .`를 사용하지 않고 파일을 명시적으로 스테이징한다.
- 작성자 이메일은 이 저장소 로컬 설정의 GitHub noreply 주소를 쓴다. Git 사용자 이름·이메일을 임의로 바꾸지 않는다.

## 범위 제한
- 불필요한 FastAPI/React/웹 UI를 구현하지 않는다.
- 실험 범위 밖의 코드(후속 실험 코드 선행 작성 포함)를 만들지 않는다.
- OWL 추론은 필요성이 확인되기 전까지 구현하지 않는다.

## 자주 쓰는 명령
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe scripts\check_environment.py
.\.venv\Scripts\python.exe scripts\run_e00.py      # E00 전체(2회 실행 비교 + pytest + run_meta/summary)
.\.venv\Scripts\python.exe -m pytest -v
```
