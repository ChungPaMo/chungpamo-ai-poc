"""pytest 공통 설정.

openpyxl은 import 시점에 lxml 사용 여부(openpyxl.xml.LXML)를 정한다. 테스트 세션에서는 E01 생성기보다
다른 모듈(e01_verify, E02 파서)이 openpyxl을 먼저 불러오므로, 세션 시작 시 E01과 같은 기록 방식으로 고정한다.
(E01 커밋 산출물의 xlsx 바이트 재현용. 셀 값은 lxml 사용 여부와 무관하게 같다.)
"""

import os

os.environ.setdefault("OPENPYXL_LXML", "False")
