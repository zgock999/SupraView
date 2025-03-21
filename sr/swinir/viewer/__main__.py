"""
SwinIR画像超解像ビューアのエントリーポイント
'python -m sr.swinir.viewer'で実行可能
"""
import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# プロジェクトのルートディレクトリをPythonパスに追加
current_dir = Path(__file__).parent.absolute()
root_dir = current_dir.parent.parent.parent  # sr/swinir/viewer -> viewer
sys.path.insert(0, str(root_dir))

# 現在の作業ディレクトリを設定
os.chdir(root_dir)

# MainWindowをインポート
try:
    from sr.swinir.viewer.viewer import MainWindow
except ImportError as e:
    print(f"インポートエラー: {e}")
    print(f"sys.path: {sys.path}")
    print(f"カレントディレクトリ: {os.getcwd()}")
    sys.exit(1)

def main():
    """メインエントリーポイント"""
    print("SwinIR画像超解像ビューアを開始します")
    print(f"現在の作業ディレクトリ: {os.getcwd()}")
    
    # ハイDPI対応
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        print(f"エラーが発生しました: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
