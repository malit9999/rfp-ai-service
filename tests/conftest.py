import sys
from pathlib import Path

# 저장소 안에서 `pytest`만 쳐도 app 패키지를 찾도록 한다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
