"""
アーカイブビューワーパッケージ

アーカイブファイルやディレクトリの内容をGUIで表示するためのクラスと機能を提供
"""

# PySide6ベースのビューワーをインポート
try:
    from arc.viewer.pyside_viewer import ArchiveViewer, ArchiveViewerWindow
    __all__ = ['ArchiveViewer', 'ArchiveViewerWindow']
except ImportError:
    # PySide6が利用できない場合は空のリストを設定
    __all__ = []
    print("警告: PySide6ビューワーが利用できません。'pip install pyside6'でインストールしてください。")
