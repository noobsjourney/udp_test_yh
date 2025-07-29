import sys
from pathlib import Path
# 获取项目根目录（假设此文件在项目根目录）
PROJECT_ROOT = Path(__file__).resolve().parent
# 添加到sys.path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
