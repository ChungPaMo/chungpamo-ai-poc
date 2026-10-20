# E00 결과 요약 — 개발환경 및 재현성 확인

> scripts/run_e00.py가 측정값으로 자동 생성한 문서다. 측정하지 못한 값은 `미측정`으로 표기한다.

- 실행 일시: 2026-10-20T10:02:15+09:00
- 실험 상태: **COMPLETED**

## 환경 (env_check.json)

| 항목 | 값 |
|---|---|
| Python | 3.11.9 (CPython, 64bit) |
| Python 실행 경로 | `C:\chungpamo\.venv\Scripts\python.exe` |
| 가상환경 사용 / 프로젝트 .venv | True / True |
| 전역 site-packages 포함 | False |
| OS | Windows 10 Professional 22H2 (빌드 19045.6466, AMD64) |
| CPU | AMD Ryzen 5 5600G with Radeon Graphics |
| 물리 / 논리 코어 | 6 / 12 |
| 전체 RAM | 15.38 GB |
| 실행 시점 가용 RAM | 3.12 GB (20.3%) |
| pytest / psutil | 9.1.1 / 7.2.2 |
| Git | 2.55.0.windows.2 |
| 프로젝트 루트 | `C:\chungpamo` (Git 저장소: True) |
| 수집 오류 건수 | 0 |

> 가용 RAM: 측정 시점 전체의 20.3%. 메모리 확보를 위한 프로세스 종료·시스템 설정 변경은 하지 않았다. 이후 성능 측정 실험에서는 측정 당시 가용 RAM을 함께 기록한다.

## 재현성

- 방법: check_environment.py를 같은 가상환경에서 별도 프로세스로 2회 실행 후 STABLE_FIELDS 비교
- 비교 필드 수: 25 / 제외(변동) 필드: run_timestamp, elapsed_seconds, memory.available_bytes, memory.available_percent, errors
- 결과: 일치

## 테스트 (pytest)

- 전체 16 / 통과 16 / 실패 0 / 오류 0 / 스킵 0
- 상세 로그: `pytest_output.txt`, `pytest_report.xml`

## Git

- 브랜치: master / 커밋: 커밋 없음 (최초 커밋은 사용자 승인 대기)
- 원격 저장소: 없음

## 실패 명령

- 없음

## 의존성 잠금

- `requirements.lock` sha256 `9adcbb8e64b34a587459af79519c4a86ced2fcedf41ede7664872f1ee48849f9`
