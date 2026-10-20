# 개발환경 조사 결과 (E00 사전 기록)

- 조사일: 2026-10-20
- 조사 방법: Windows PowerShell 5.1 명령(`Get-CimInstance`, `Get-Command`, 각 도구의 `--version`), 레지스트리 설치 목록 조회(읽기 전용)
- 조사 범위: 정보 조회만 수행. 설치·설정 변경·외부 네트워크 호출 없음
- 개인정보·비밀값: 환경변수 값, API 키, 사용자 계정 정보는 조회·기록하지 않음. 실행 경로에 포함된 Windows 사용자 폴더명은 `<USER>`로 표기

## 1. 시스템

| 항목 | 결과 | 비고 |
|---|---|---|
| Windows 버전 | Windows 10 Pro 22H2, 빌드 19045.6466, 64비트 | |
| CPU | AMD Ryzen 5 5600G with Radeon Graphics | 물리 코어 6, 최대 클럭 3,901MHz |
| 논리 프로세서 수 | 12 | |
| 총 시스템 RAM | 15.38 GB | |
| 조사 시점 가용 RAM | 2.19 GB | 측정 시점 다른 프로그램 사용량에 따라 변동. 성능 측정 시 백그라운드 부하 기록 필요 |
| 디스크 여유 공간 | C: (NTFS) 전체 465.1 GB 중 여유 308.8 GB | 고정 디스크는 C: 1개 |
| GPU (참고) | AMD Radeon(TM) Graphics (CPU 내장 그래픽) | 드라이버 31.0.12027.9001. 전용 GPU·NVIDIA GPU 없음(`nvidia-smi` 미설치). CUDA 사용 불가 |
| PowerShell | 5.1.19041.6456 | `&&` 연산자 미지원 버전 |

## 2. 개발 도구

| 항목 | 결과 | 실행 경로 |
|---|---|---|
| Python | 설치됨, CPython 3.11.9 (64bit) | `C:\Users\<USER>\AppData\Local\Programs\Python\Python311\python.exe` |
| py 런처 | 설치됨, 등록 버전 3.11 (64bit) 1개 | `C:\Windows\py.exe` |
| `python3` 명령 | 실제 Python 아님 (Microsoft Store 실행 별칭) | `...\WindowsApps\python3.exe`, 실행 시 종료코드 9009. 스크립트에서는 `python` 또는 `py -3.11` 사용 |
| pip | 24.0 (python 3.11) | `...\Python311\Scripts\pip.exe` |
| uv | 0.11.28 | `...\Python311\Scripts\uv.exe` |
| Git | 2.55.0.windows.2 | `C:\Program Files\Git\cmd\git.exe` |
| VS Code CLI (`code`) | 사용 가능, 1.142.0 (x64) | `C:\Users\<USER>\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd` |
| Java | OpenJDK 21.0.11 LTS (Eclipse Temurin) | `C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot\bin\java.exe` — GraphDB 로컬 실행 검토 시 관련 |
| conda | 미설치 | |
| Docker | 미설치 | GraphDB 컨테이너 실행 방식은 현재 불가 |
| WSL | 설치됨, 배포판 `Ubuntu-24.04`(기본), `rocky` (모두 WSL2, 조사 시 Stopped) | Linux 전용 도구 필요 시 대안 후보 |

## 3. 문서 관련 소프트웨어 (파서 실험 관련)

| 항목 | 결과 | 영향 |
|---|---|---|
| Microsoft Excel | Excel 2013 (15.0.4569.1506) 설치 | xlsx 샘플 육안 확인 가능 |
| Microsoft Word | 설치 목록에서 확인되지 않음 | DOCX 육안 확인 도구 별도 필요 여부 확인 |
| 한컴오피스(한글) | 미설치 | HWP/HWPX 샘플 작성·육안 대조 불가 → E03 선행조건 |
| LibreOffice (`soffice`) | 미설치 | 변환기 기반 HWP/DOCX→PDF 비교 불가 |
| Tesseract / Ghostscript / Poppler | 설치 목록에서 확인되지 않음 | OCR·PDF 래스터화 대안 사용 시 설치 필요 |

## 4. 기존 Python 패키지 (전역 환경, 총 11개)

`et_xmlfile 2.0.0`, `lxml 6.1.1`, `openpyxl 3.1.5`, `pillow 12.3.0`, `pip 24.0`, `Pygments 2.20.0`, `pypdf 6.19.0`, `python-docx 1.2.0`, `setuptools 65.5.0`, `typing_extensions 4.16.0`, `uv 0.11.28`

실험 관련 미설치 패키지(확인 대상 중): pandas, numpy, PyMuPDF, pdfplumber, pydantic, rdflib, pyshacl, SPARQLWrapper, psutil, pytest, olefile, pyhwp.

> 전역 환경에 일부 패키지가 이미 설치되어 있으므로, 실험은 프로젝트 전용 가상환경에서 수행해야 재현성이 확보된다(E00).

## 5. 프로젝트 폴더 상태

| 항목 | 결과 |
|---|---|
| 프로젝트 루트 | `C:\chungpamo` |
| Git 저장소 여부 | 아님 (`git init` 미실행 — 사용자 확인 필요) |
| 가상환경(`.venv`) | 없음 |
| 기존 파일 | `docs/` 아래 PDF 2개, DOCX 1개 (변경하지 않음) |

## 6. 실행 중 오류·실패 명령

| 명령 | 결과 | 원인 | 조치 |
|---|---|---|---|
| `python -c "...docx 본문 출력..."` (기존 업무분장 DOCX 읽기) | `UnicodeEncodeError: 'cp949' codec can't encode character '\u2014'` | 콘솔 기본 인코딩이 cp949이고 문서에 em dash(—)가 포함됨 | UTF-8 파일로 출력 후 읽어 해결. 이후 실험 스크립트는 `PYTHONIOENCODING=utf-8` 또는 UTF-8 파일 출력 사용 권장 |
| `python3 --version` | 종료코드 9009, 버전 미출력 | Microsoft Store 실행 별칭으로 실제 인터프리터가 아님 | `python` 사용. 필요 시 Windows 설정 > 앱 실행 별칭에서 비활성화 가능(사용자 판단) |
| `Get-Command nvidia-smi` / `conda` / `docker` / `soffice` | 찾을 수 없음 | 미설치 | 기록만 함 |

## 7. 측정 불가·미확인 항목

- GPU 전용 메모리: `Win32_VideoController.AdapterRAM` 값 512MB가 보고되었으나 내장 그래픽의 공유 메모리 할당값으로, 실험에 의미 없음. 참고용으로만 기록
- 네트워크 환경(사내망, 프록시, 외부 API 접근 가능 여부): 미조사(외부 호출 금지 범위)
- 수요기업 서버 사양: 미확정

---

## 8. 2단계 환경 구축 결과 (2026-10-20 추가)

> §1~§7은 1단계 조사 기록이며 수정하지 않았다. 아래는 2단계에서 실제로 변경된 환경이다. §5 "프로젝트 폴더 상태"의 Git·가상환경 항목은 아래 내용으로 대체된다.

### 8.1 가상환경

| 항목 | 결과 |
|---|---|
| 생성 명령 | `py -3.11 -m venv .venv` (종료코드 0) |
| 가상환경 Python | 3.11.9, `C:\chungpamo\.venv\Scripts\python.exe` |
| 전역 site-packages 포함 | 아니오 (`pyvenv.cfg`: include-system-site-packages = false) |
| 실행 방식 | 활성화 없이 명시적 경로로 실행. PowerShell 실행 정책 변경 없음 |
| pip | 24.0 (가상환경 기본 포함, 업그레이드하지 않음) |

### 8.2 설치 패키지 (`requirements.lock`)

| 패키지 | 버전 | 구분 |
|---|---|---|
| pytest | 9.1.1 | 직접 설치 |
| psutil | 7.2.2 | 직접 설치 |
| colorama | 0.4.6 | pytest 의존성 |
| iniconfig | 2.3.1 | pytest 의존성 |
| packaging | 26.3 | pytest 의존성 |
| pluggy | 1.7.0 | pytest 의존성 |
| Pygments | 2.21.0 | pytest 의존성 |
| pip / setuptools | 24.0 / 65.5.0 | 가상환경 기본 포함 (lock 제외) |
| pydantic | 2.14.1 | 직접 설치 (2026-10-20 E01) |
| pydantic_core | 2.50.1 | pydantic 의존성 |
| annotated-types | 0.8.0 | pydantic 의존성 |
| typing-inspection | 0.4.4 | pydantic 의존성 |
| typing_extensions | 4.16.0 | pydantic 의존성 |
| openpyxl | 3.1.5 | 직접 설치 (2026-10-20 E01) |
| et_xmlfile | 2.0.0 | openpyxl 의존성 |

- `pip check`: "No broken requirements found." (E00 설치 후, E01 추가 설치 후 각각 확인)
- 전역 Python 환경은 변경하지 않았다(전역에 Pygments 2.20.0이 있으나 가상환경은 2.21.0을 별도 사용).

### 8.3 Git

| 항목 | 결과 |
|---|---|
| 저장소 | `git init` 완료, 브랜치 `master` |
| 원격 저장소 | 없음 (`git remote -v` 출력 없음) |
| 커밋 | 없음 (최초 커밋은 사용자 승인 대기) |
| 사용자 이름·이메일 | 설정하지 않음 |
| 추적 제외 확인 | `git check-ignore -v`로 비공개 PDF 2개·DOCX 1개, `.env`, `.venv/`, `data/raw/*` 제외 확인. `.env.example`, `data/raw/.gitkeep`은 추적 가능 |

### 8.4 E00 점검 시 측정값 (results/E00_environment/env_check.json, 2026-10-20 10:02)

| 항목 | 값 |
|---|---|
| CPU 물리 / 논리 코어 | 6 / 12 (psutil, os.cpu_count) |
| 전체 RAM | 16,517,812,224 bytes (15.38 GB) |
| 가용 RAM | 3.12 GB (20.3%) — 실행마다 변동. 메모리 확보 조치(프로세스 종료·설정 변경)는 하지 않음 |
| OS | Windows 10 Professional 22H2, 빌드 19045.6466 |
| 수집 오류 | 0건 |
