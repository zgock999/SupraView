"""
デコーダービューアモジュールのエントリーポイント

このモジュールは `python -m decoder.viewer` コマンドで
直接実行できるようにするためのエントリーポイントです。
"""

from .viewer import run_viewer

if __name__ == "__main__":
    print("SupraView デコーダーテストビューアを起動しています...")
    print("Webブラウザで http://127.0.0.1:8050/ にアクセスしてください")
    run_viewer(debug=True, port=8050)
