"""
ファイルリストビュー

アーカイブ内のファイルやフォルダのリストを表示するビューコンポーネント
"""

import os
import sys
from typing import Dict, List, Any, Optional, Callable

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logutils import log_print, DEBUG, INFO, WARNING, ERROR

try:
    from PySide6.QtWidgets import (
        QListView, QAbstractItemView, QMenu, QStyle, QApplication
    )
    from PySide6.QtCore import (
        Qt, Signal, QSize, QPoint, QModelIndex
    )
    from PySide6.QtGui import (
        QStandardItemModel, QStandardItem, QContextMenuEvent, QIcon
    )
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)

# 既存の自然順ソートユーティリティをインポート
from app.viewer.utils.sort import natural_sort_key, safe_sort_key

# デコーダーサポートの拡張子を取得
from decoder.interface import get_supported_image_extensions

# サムネイルジェネレータをインポート
from .thumbnail_generator import ThumbnailGenerator


class FileListModel(QStandardItemModel):
    """ファイルリスト表示用のデータモデル"""
    
    def __init__(self, parent=None):
        super().__init__(0, 1, parent)
        self.debug_mode = False
        
        # アイコンマッピング
        self.folder_icon = None
        self.file_icon = None
        self.image_icon = None
        self.parent_dir_icon = None  # 親ディレクトリ用アイコン
        self.archive_icon = None     # アーカイブ用アイコンを追加
        
        # アイコンを初期化
        self._init_icons()
        
        # 現在のファイルアイテムを保持
        self.file_items = []
        
        # サポートされている画像形式の拡張子のリスト
        self.supported_image_extensions = get_supported_image_extensions()
    
    def _init_icons(self):
        """アイコンを初期化する"""
        # システムアイコンを使用
        style = QApplication.style()
        
        # フォルダアイコン
        self.folder_icon = style.standardIcon(QStyle.SP_DirIcon)
        
        # 親ディレクトリ用アイコン
        self.parent_dir_icon = style.standardIcon(QStyle.SP_ArrowUp)  # 上へ矢印アイコン
        
        # ファイルアイコン（デフォルト）
        self.file_icon = style.standardIcon(QStyle.SP_FileIcon)
        
        # 画像ファイルアイコン
        self.image_icon = style.standardIcon(QStyle.SP_FileIcon)  # 一時的にファイルアイコンと同じ
        
        # アーカイブファイルアイコン
        self.archive_icon = style.standardIcon(QStyle.SP_DriveFDIcon)  # アーカイブ用に適切なアイコン
    
    def set_items(self, items: List[Dict[str, Any]], in_root: bool = False):
        """
        モデルにアイテムを設定
        
        Args:
            items: ファイル情報のリスト
                  [{'name': 'filename', 'is_dir': True, 'size': 1234, ...}, ...]
            in_root: ルートディレクトリかどうか
        """
        # モデルをクリア
        self.clear()
        
        # 現在のファイルアイテムを保存
        self.file_items = items.copy()
        
        # 親ディレクトリ項目を追加（ルートディレクトリでない場合）
        if not in_root:
            parent_item = QStandardItem(self.parent_dir_icon, "..")  # フォルダアイコンから親ディレクトリアイコンに変更
            parent_item.setData(True, Qt.UserRole)  # isDir
            parent_item.setData("..", Qt.UserRole + 1)  # name
            self.appendRow(parent_item)
        
        # ディレクトリ項目とファイル項目をそれぞれ分ける
        dirs = [item for item in items if item.get('is_dir', False)]
        files = [item for item in items if not item.get('is_dir', False)]
        
        try:
            # 安全なソートを試みる - エラーが発生した場合は安全なキー関数を使用
            try:
                # ディレクトリを自然順でソート（既存のモジュールを使用）
                dirs.sort(key=lambda x: natural_sort_key(x['name']))
            except TypeError:
                # 型エラーが発生した場合は、安全なキー関数を使用
                log_print(WARNING, "自然順ソート中にエラーが発生したため、安全なソート関数を使用します")
                dirs.sort(key=lambda x: safe_sort_key(x['name']))
        except Exception as e:
            # それでもエラーが発生する場合は文字列に変換してソート
            log_print(ERROR, f"ディレクトリのソート中にエラーが発生しました: {e}")
            dirs.sort(key=lambda x: str(x.get('name', '')))
        
        # ディレクトリ項目を上部に表示
        for item in dirs:
            # アーカイブかどうかをチェック
            is_archive = item.get('type', '') == 'ARCHIVE'
            
            # アイコンを選択（アーカイブならアーカイブアイコン、そうでなければフォルダアイコン）
            icon = self.archive_icon if is_archive else self.folder_icon
            
            standard_item = QStandardItem(icon, str(item['name']))  # 文字列に明示的に変換
            standard_item.setData(True, Qt.UserRole)  # isDir
            standard_item.setData(str(item['name']), Qt.UserRole + 1)  # name
            # type情報を追加
            standard_item.setData(item.get('type', ''), Qt.UserRole + 2)  # type
            # その他の属性を設定する場合はここに追加
            self.appendRow(standard_item)
        
        try:
            # 安全なソートを試みる - エラーが発生した場合は安全なキー関数を使用
            try:
                # ファイル項目も自然順でソート（既存のモジュールを使用）
                files.sort(key=lambda x: natural_sort_key(x['name']))
            except TypeError:
                # 型エラーが発生した場合は、安全なキー関数を使用
                log_print(WARNING, "自然順ソート中にエラーが発生したため、安全なソート関数を使用します")
                files.sort(key=lambda x: safe_sort_key(x['name']))
        except Exception as e:
            # それでもエラーが発生する場合は文字列に変換してソート
            log_print(ERROR, f"ファイルのソート中にエラーが発生しました: {e}")
            files.sort(key=lambda x: str(x.get('name', '')))
        
        # ファイル項目を下部に表示
        for item in files:
            name = str(item['name'])  # 文字列に明示的に変換
            # デフォルトアイコンを設定
            icon = self._get_icon_for_file(name)
            standard_item = QStandardItem(icon, name)
            standard_item.setData(False, Qt.UserRole)  # isDir
            standard_item.setData(name, Qt.UserRole + 1)  # name
            # type情報を追加
            standard_item.setData(item.get('type', ''), Qt.UserRole + 2)  # type
            # その他の属性を設定する場合はここに追加
            self.appendRow(standard_item)
    
    def _get_icon_for_file(self, filename: str) -> QIcon:
        """
        ファイル名に応じたアイコンを取得
        
        Args:
            filename: ファイル名
            
        Returns:
            QIcon: ファイルに対応するアイコン
        """
        _, ext = os.path.splitext(filename.lower())
        
        # 画像ファイルの場合
        if ext in self.supported_image_extensions:
            return self.image_icon
        
        # その他のファイル
        return self.file_icon
    
    def _update_thumbnail(self, filename: str, icon: QIcon):
        """
        生成したサムネイルでアイコンを更新
        
        Args:
            filename: 更新するファイル名
            icon: 新しいアイコン
        """
        log_print(INFO, f"サムネイル更新開始: {filename}")
        
        updated = False
        # ファイル名に一致するアイテムを探して更新
        for row in range(self.rowCount()):
            index = self.index(row, 0)
            is_dir = self.data(index, Qt.UserRole)
            
            # ディレクトリはスキップ
            if is_dir:
                continue
            
            name = self.data(index, Qt.UserRole + 1)
            log_print(DEBUG, f"アイテム比較: '{name}' vs '{filename}'")
            
            if name == filename:
                # アイコンを更新
                self.setData(index, icon, Qt.DecorationRole)
                log_print(INFO, f"サムネイル更新成功: {filename}")
                updated = True
                
                # モデルを明示的に更新（このアイテムが変更されたことを通知）
                self.dataChanged.emit(index, index, [Qt.DecorationRole])
                break
        
        if not updated:
            log_print(WARNING, f"サムネイル更新失敗: '{filename}' に該当するアイテムが見つかりません")
    
    def set_debug_mode(self, enabled: bool):
        """デバッグモードを設定"""
        self.debug_mode = enabled


class FileListView(QListView):
    """カスタムリストビュー"""
    
    # カスタムシグナル
    item_activated = Signal(str, bool)  # filename, is_dir
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # リストビューの表示設定 - Windowsエクスプローラーの特大アイコン表示に合わせて調整
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setWrapping(True)
        self.setSpacing(20)  # アイテム間のスペースを広げる
        self.setUniformItemSizes(True)
        self.setIconSize(QSize(96, 96))  # 特大アイコン表示に合わせて大きくする
        self.setGridSize(QSize(120, 140))  # グリッドサイズも設定（アイコン+テキスト用のスペース）
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setTextElideMode(Qt.ElideRight)
        self.setWordWrap(True)
        self.setDragEnabled(False)  # ドラッグアンドドロップは無効化
        
        # Windowsエクスプローラースタイルに近いスタイルシート
        self.setStyleSheet("""
            QListView {
                background-color: white;
                border: none;
                padding: 5px;
            }
            QListView::item {
                color: #333;
                border-radius: 5px;
                padding: 5px;
                text-align: center;
            }
            QListView::item:selected {
                background-color: #cce8ff;
                border: 1px solid #99d1ff;
            }
            QListView::item:hover:!selected {
                background-color: #e5f3ff;
            }
        """)
        
        # カスタムモデルを設定
        self.file_model = FileListModel(self)
        self.setModel(self.file_model)
        
        # サムネイルジェネレータの初期化
        self.thumbnail_generator = ThumbnailGenerator(debug_mode=False)
        
        # サムネイル生成状態の追跡
        self._thumbnail_generation_active = False
        
        # シグナルをスロットに接続
        self.doubleClicked.connect(self._handle_item_activated)
        
        # シングルクリックイベントを処理するために clicked シグナルも接続
        self.clicked.connect(self._handle_item_clicked)
        
        # アーカイブマネージャへの参照（後で設定）
        self.archive_manager = None
    
    def set_archive_manager(self, archive_manager):
        """
        アーカイブマネージャを設定
        
        Args:
            archive_manager: アーカイブマネージャインスタンス
        """
        self.archive_manager = archive_manager
    
    def _handle_item_activated(self, index: QModelIndex):
        """
        アイテムがダブルクリックされたときの処理
        
        Args:
            index: アクティベートされたアイテムのインデックス
        """
        is_dir = self.model().data(index, Qt.UserRole)
        name = self.model().data(index, Qt.UserRole + 1)
        
        # シグナルを発行
        self.item_activated.emit(name, is_dir)
    
    def _handle_item_clicked(self, index: QModelIndex):
        """
        アイテムがクリックされたときの処理（シングルクリック）
        
        Args:
            index: クリックされたアイテムのインデックス
        """
        is_dir = self.model().data(index, Qt.UserRole)
        name = self.model().data(index, Qt.UserRole + 1)
        
        # 親ディレクトリ(..)の場合のみシングルクリックで移動
        if is_dir and name == "..":
            self.item_activated.emit(name, is_dir)
    
    def _get_selected_items(self) -> List[Dict[str, Any]]:
        """
        選択されているアイテムの情報を取得
        
        Returns:
            選択されたアイテムの情報のリスト
        """
        selected_indexes = self.selectedIndexes()
        items = []
        
        for index in selected_indexes:
            is_dir = self.model().data(index, Qt.UserRole)
            name = self.model().data(index, Qt.UserRole + 1)
            
            items.append({
                'name': name,
                'is_dir': is_dir
            })
        
        return items
    
    def set_debug_mode(self, enabled: bool):
        """デバッグモードを設定"""
        self.file_model.set_debug_mode(enabled)
        self.thumbnail_generator.debug_mode = enabled
    
    def handle_folder_changed(self):
        """
        フォルダが変更されたときの処理
        既存のサムネイル生成タスクをキャンセルします。
        """
        # 進行中のサムネイル生成タスクをキャンセル
        if hasattr(self, 'thumbnail_generator'):
            self.thumbnail_generator.cancel_current_task()
            log_print(INFO, "ディレクトリ変更: すべてのサムネイル生成タスクをキャンセルしました")
        
        # サムネイル生成状態をリセット
        self._thumbnail_generation_active = False
    
    def generate_thumbnails(self):
        """
        画像ファイルのサムネイルを生成
        """
        if not self.archive_manager:
            log_print(WARNING, "アーカイブマネージャがNoneのため、サムネイル生成をスキップします")
            return
        
        try:
            # サムネイル生成タスクをキャンセル
            self.thumbnail_generator.cancel_current_task()
            
            # 明示的なログ出力を追加
            log_print(INFO, f"FileListView: サムネイル生成を開始します - 現在のディレクトリ: {self.archive_manager.current_directory}")
            log_print(INFO, f"FileListView: ファイルアイテム数: {len(self.file_model.file_items)}")
            
            # サムネイル生成状態を更新
            self._thumbnail_generation_active = True
            
            # サムネイル生成完了時のコールバックを追加
            def on_all_completed():
                self._thumbnail_generation_active = False
                log_print(INFO, "サムネイル生成が完了しました")
            
            # サムネイル生成を開始
            self.thumbnail_generator.generate_thumbnails(
                archive_manager=self.archive_manager,
                file_items=self.file_model.file_items,
                on_thumbnail_ready=self._update_thumbnail_callback,
                on_all_completed=on_all_completed,  # 完了時コールバックを追加
                thumbnail_size=QSize(64, 64),
                current_directory=self.archive_manager.current_directory  # 現在のディレクトリ情報を追加
            )
            
            if self.file_model.debug_mode:
                log_print(DEBUG, f"サムネイル生成を開始しました")
        except Exception as e:
            log_print(ERROR, f"サムネイル生成の開始中にエラーが発生しました: {e}")
            self._thumbnail_generation_active = False
    
    def _update_thumbnail_callback(self, filename: str, icon: QIcon):
        """
        サムネイル更新のコールバック（モデルのメソッドを実行）
        
        Args:
            filename: 更新するファイル名
            icon: 新しいアイコン
        """
        try:
            # モデルの更新メソッドを呼び出す
            self.file_model._update_thumbnail(filename, icon)
            
            # 更新を確実にビューに反映するために明示的にビューを更新
            self.viewport().update()
        except Exception as e:
            log_print(ERROR, f"サムネイル更新コールバック実行中にエラーが発生しました: {e}")
    
    def contextMenuEvent(self, event: QContextMenuEvent):
        """コンテキストメニューイベント処理"""
        # 親クラスのイベント処理を呼び出し
        super().contextMenuEvent(event)
        
        # 選択アイテムを取得
        selected_items = self._get_selected_items()
        
        if not selected_items:
            return
        
        # イベント位置でヒットテストを行い、アイテムを取得
        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        
        # メニューを作成して表示
        menu = QMenu(self)
        
        # メニュー項目の追加（例）
        open_action = menu.addAction("開く")
        if len(selected_items) == 1:
            # 単一選択の場合
            item = selected_items[0]
            if item['is_dir']:
                open_action.setText("フォルダを開く")
            else:
                # ファイル種別に応じたアクション
                _, ext = os.path.splitext(item['name'].lower())
                if ext in self.file_model.supported_image_extensions:
                    open_action.setText("画像を表示")
        
        # メニューを表示して選択されたアクションを取得
        action = menu.exec(event.globalPos())
        
        # アクション処理
        if action == open_action:
            # 現在は選択されたアイテムをアクティベートするだけ
            if len(selected_items) == 1:
                item = selected_items[0]
                self.item_activated.emit(item['name'], item['is_dir'])


# 単体テスト用のコード
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMainWindow
    import sys
    
    app = QApplication(sys.argv)
    
    main_window = QMainWindow()
    main_window.setWindowTitle("ファイルリストビュー テスト")
    main_window.setGeometry(100, 100, 800, 600)
    
    # リストビューを作成
    file_list_view = FileListView()
    
    # 中央ウィジェットとして設定
    main_window.setCentralWidget(file_list_view)
    
    # テスト用アイテムを設定
    test_items = [
        {'name': 'folder1', 'is_dir': True},
        {'name': 'folder2', 'is_dir': True},
        {'name': 'document.txt', 'is_dir': False},
        {'name': 'image.jpg', 'is_dir': False},
        {'name': 'image2.png', 'is_dir': False},
    ]
    
    file_list_view.file_model.set_items(test_items)
    
    main_window.show()
    sys.exit(app.exec())
