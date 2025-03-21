"""
超解像ビューワアプリケーション起動スクリプト
"""
import sys
from pathlib import Path
import os

# プロジェクトのルートディレクトリをパスに追加
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def run():
    """アプリケーションを起動する"""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
    except ImportError:
        print("エラー: PySide6がインストールされていません。")
        print("pip install PySide6 を実行してインストールしてください。")
        return 1

    # アプリケーションモジュールのインポート
    try:
        from sr.viewer.viewer import MainWindow
    except ImportError as e:
        print(f"エラー: モジュールの読み込みに失敗しました: {e}")
        return 1

    # ハイDPI対応
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    # アプリケーション起動
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(run())
