"""
アーカイブビューワーエントリーポイント

このモジュールは `python -m arc.viewer` コマンドで実行されたときに
viewer.py のメイン機能を呼び出します。
"""

# viewerモジュールからメイン関数をインポート
from .viewer import main

# メイン関数を実行
if __name__ == "__main__":
    main()
