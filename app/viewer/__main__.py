"""
SupraViewメインエントリポイント

Pythonモジュールとして実行するためのエントリポイント
`python -m app.viewer` として実行することができます
"""

import sys
from app.viewer.viewer import main

if __name__ == "__main__":
    sys.exit(main())
