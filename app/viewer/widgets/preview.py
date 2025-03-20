"""
画像プレビューウィンドウ

アーカイブ内の画像ファイルをプレビュー表示するためのウィンドウ
"""

import os
import sys

# プロジェクトルートへのパスを追加（必要に応じて）
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logutils import log_print, INFO, ERROR

try:
    from PySide6.QtWidgets import (
        QApplication
    )
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)

# 分割したモジュールからImagePreviewWindowをインポート
from .preview.window import ImagePreviewWindow

# 互換性のために旧実装をそのまま再エクスポート
__all__ = ['ImagePreviewWindow']


# 単体テスト用のコード
if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    # テスト用の画像ファイルパス
    test_image_path = None
    if len(sys.argv) > 1:
        test_image_path = sys.argv[1]
    
    window = ImagePreviewWindow()
    window.show()
    
    # テスト用の画像ファイルが指定された場合は読み込み
    if test_image_path and os.path.isfile(test_image_path):
        # ローカルファイルを直接読み込むテスト
        try:
            from .preview.image_processor import load_image_from_bytes
            
            with open(test_image_path, 'rb') as f:
                image_data = f.read()
            
            # 新しい画像処理モジュールを使用
            pixmap, numpy_array, info = load_image_from_bytes(image_data, test_image_path)
            if pixmap:
                window._current_pixmap = pixmap
                window._original_pixmap = pixmap
                window._numpy_image = numpy_array
                window._image_info = info
                window._current_image_path = test_image_path
                window._current_image_data = image_data
                window._adjust_image_size()
                window._update_status_info()
                window.setWindowTitle(f"画像プレビュー - {os.path.basename(test_image_path)}")
        except Exception as e:
            log_print(ERROR, f"画像の読み込みに失敗しました: {e}")
    
    sys.exit(app.exec())
