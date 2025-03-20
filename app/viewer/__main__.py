"""
アーカイブビューアのエントリポイント

このモジュールはパッケージとして実行された場合（python -m app.viewer）の
エントリポイントとして機能します。
"""

from app.viewer.viewer import main

if __name__ == "__main__":
    main()
