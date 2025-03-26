"""
ファイルリストビュー

ファイルとフォルダを大アイコン表示するためのリストビュー
"""

import os
import sys
from typing import Optional

try:
    from PySide6.QtWidgets import QListView, QAbstractItemView
    from PySide6.QtCore import Qt, QSize, QModelIndex, Signal
except ImportError:
    print("PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)

# 相対インポート
from ..models.file_list_model import FileListModel


class FileListView(QListView):
    """ファイルとフォルダのリストビュー"""
    
    # シグナルの定義を修正：name→pathに変更してパスを渡すようにする
    item_activated = Signal(str, bool)  # path, is_dir
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # ビューの設定
        self.setViewMode(QListView.IconMode)  # アイコンモード (大アイコン表示)
        self.setResizeMode(QListView.Adjust)  # ウィンドウサイズに合わせて調整
        self.setWrapping(True)  # アイテムの折り返し表示
        self.setSpacing(10)  # アイテム間のスペース
        self.setWordWrap(True)  # テキストの折り返し
        self.setUniformItemSizes(False)  # アイテムサイズは統一しない
        self.setIconSize(QSize(64, 64))  # アイコンサイズ
        self.setGridSize(QSize(100, 100))  # グリッドサイズ
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)  # 複数選択可能
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 編集不可
        self.setDragEnabled(False)  # ドラッグ無効
        self.setFlow(QListView.LeftToRight)  # エクスプローラー準拠の左から右へのフロー（横並び・縦スクロール）
        
        # モデルの設定
        self.file_model = FileListModel(self)
        self.setModel(self.file_model)
        
        # シグナル接続
        self.doubleClicked.connect(self._on_item_double_clicked)
        self.clicked.connect(self._on_item_clicked)  # シングルクリック処理を追加
    
    def _on_item_clicked(self, index: QModelIndex):
        """
        アイテムがクリックされたときの処理
        親ディレクトリ「..」アイテムの場合のみシングルクリックで処理
        """
        item = self.model().itemFromIndex(index)
        if item:
            # アイテムが「..」の場合のみシングルクリックで親ディレクトリに移動
            name = item.text()
            if name == "..":
                path = item.data(Qt.UserRole + 4)  # パス情報取得
                is_dir = item.data(Qt.UserRole + 1)  # ディレクトリかどうか
                
                # パスが空の場合は名前を使用
                if not path:
                    path = name
                
                # エントリキャッシュのキーは末尾/なしなのでrstrip
                path = path.rstrip('/') if is_dir else path
                
                # アイテムがアクティブになった（親ディレクトリへの移動）
                self.item_activated.emit(path, is_dir)
    
    def _on_item_double_clicked(self, index: QModelIndex):
        """アイテムがダブルクリックされたときの処理"""
        item = self.model().itemFromIndex(index)
        if item:
            # 「..」以外のアイテムをダブルクリックで処理
            name = item.text()
            if name != "..":
                path = item.data(Qt.UserRole + 4)  # ファイルパス情報を取得
                is_dir = item.data(Qt.UserRole + 1)
                
                # パスが空の場合は名前を使用
                if not path:
                    path = name
                    
                # エントリキャッシュのキーは末尾/なしなので、末尾のスラッシュを除去
                path = path.rstrip('/') if is_dir else path
                
                # FileActionHandlerに処理済みのパスを渡す
                self.item_activated.emit(path, is_dir)
