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

from logutils import log_print,log_trace, DEBUG, INFO, WARNING, ERROR

# EntryInfo型をインポート
from arc.arc import EntryInfo, EntryType

try:
    from PySide6.QtWidgets import (
        QListView, QAbstractItemView, QMenu, QStyle, QApplication, QFileDialog
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

# 共有のファイルリストモデルをインポート
from ..models.file_list_model import FileListModel

# デコーダーサポートの拡張子を取得
from decoder.interface import get_supported_image_extensions

# サムネイルジェネレータをインポート
from .thumbnail_generator import ThumbnailGenerator


class FileListView(QListView):
    """カスタムリストビュー"""
    
    # カスタムシグナル - EntryInfo型を使用
    item_activated = Signal(EntryInfo)
    
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
        
        # 新しいモデルクラスを使用
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
        
        # デバッグモードフラグ
        self.debug_mode = False
        
        # サポートされている画像形式の拡張子のリスト
        self.supported_image_extensions = get_supported_image_extensions()
    
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
        # 新しいモデルの構造に合わせてデータ取得方法を変更
        is_dir = self.model().data(index, Qt.UserRole + 1)  # モデルの変更に伴いUserRoleを調整
        name = self.model().itemFromIndex(index).text()
        path = self.model().data(index, Qt.UserRole + 4)  # パス情報はUserRole+4に格納
        
        # 「..」アイテムの場合は何もしない（シングルクリックで処理済み）
        if name == "..":
            return
        
        # 親ディレクトリ以外の場合は通常のシグナル送出
        # パスの末尾の/を削除
        path = path.rstrip('/')
        
        # アーカイブマネージャーを通じてEntryInfo型のオブジェクトを取得
        entry_info = self.archive_manager.get_entry_info(path)
        
        # シグナルを発行 - EntryInfo型のオブジェクトを使用
        self.item_activated.emit(entry_info)
    
    def _handle_item_clicked(self, index: QModelIndex):
        """
        アイテムがクリックされたときの処理（シングルクリック）
        
        Args:
            index: クリックされたアイテムのインデックス
        """
        # 新しいモデルの構造に合わせてデータ取得方法を変更
        is_dir = self.model().data(index, Qt.UserRole + 1)  # フォルダかどうか
        name = self.model().itemFromIndex(index).text()
        
        # 親ディレクトリ(..)の場合のみシングルクリックで移動
        if is_dir and name == "..":
            # ベースパス相対のパスを構築
            if self.archive_manager and self.archive_manager.current_directory:
                current = self.archive_manager.current_directory.rstrip('/')
                if '/' in current:
                    parent_dir = current.rsplit('/', 1)[0]
                else:
                    parent_dir = ""
                log_print(INFO, f"親ディレクトリに移動: {parent_dir}")
                # アーカイブマネージャーを通じてEntryInfo型のオブジェクトを取得 
                entry_info = self.archive_manager.get_entry_info(parent_dir)
            
                # シグナルを発行 - EntryInfo型のオブジェクトを使用
                self.item_activated.emit(entry_info)               
            else:
                # ルートの場合は何もしない
                if self.debug_mode:
                    log_print(DEBUG, "既にルートディレクトリにいるため移動しません")
    
    def _get_selected_items(self) -> List[Dict[str, Any]]:
        """
        選択されているアイテムの情報を取得
        
        Returns:
            選択されたアイテムの情報のリスト
        """
        selected_indexes = self.selectedIndexes()
        items = []
        
        for index in selected_indexes:
            is_dir = self.model().data(index, Qt.UserRole + 1)  # フォルダかどうか
            name = self.model().itemFromIndex(index).text()
            path = self.model().data(index, Qt.UserRole + 4)  # パス情報
            
            items.append({
                'name': name,
                'is_dir': is_dir,
                'path': path
            })
        
        return items
    
    def set_debug_mode(self, enabled: bool):
        """デバッグモードを設定"""
        self.debug_mode = enabled
        self.thumbnail_generator.debug_mode = enabled
    
    def handle_folder_changed(self):
        """
        フォルダが変更されたときの処理
        既存のサムネイル生成タスクをキャンセルします。
        """
        # 進行中のサムネイル生成タスクをキャンセル
        if hasattr(self, 'thumbnail_generator'):
            self.thumbnail_generator.cancel_current_task()
            if self.debug_mode:
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
            
            # モデルからすべてのアイテムを抽出
            file_items = []
            for row in range(self.model().rowCount()):
                index = self.model().index(row, 0)
                is_dir = self.model().data(index, Qt.UserRole + 1)
                
                # ディレクトリはスキップ
                if (is_dir):
                    continue
                
                name = self.model().itemFromIndex(index).text()
                path = self.model().data(index, Qt.UserRole + 4)
                
                # 画像ファイルのみ対象
                _, ext = os.path.splitext(name.lower())
                if ext in self.supported_image_extensions:
                    file_items.append({
                        'name': name,
                        'path': path,
                        'is_dir': False
                    })
            
            log_print(INFO, f"FileListView: サムネイル対象ファイル数: {len(file_items)}")
            
            # サムネイル生成状態を更新
            self._thumbnail_generation_active = True
            
            # サムネイル生成完了時のコールバックを追加
            def on_all_completed():
                self._thumbnail_generation_active = False
                log_print(INFO, "サムネイル生成が完了しました")
            
            # サムネイル生成を開始
            self.thumbnail_generator.generate_thumbnails(
                archive_manager=self.archive_manager,
                file_items=file_items,
                on_thumbnail_ready=self._update_thumbnail_callback,
                on_all_completed=on_all_completed,  # 完了時コールバックを追加
                thumbnail_size=QSize(64, 64),
                current_directory=self.archive_manager.current_directory  # 現在のディレクトリ情報を追加
            )
            
            if self.debug_mode:
                log_print(DEBUG, f"サムネイル生成を開始しました")
        except Exception as e:
            log_print(ERROR, f"サムネイル生成の開始中にエラーが発生しました: {e}")
            self._thumbnail_generation_active = False
    
    def _update_thumbnail_callback(self, filename: str, icon: QIcon):
        """
        サムネイル更新のコールバック
        
        Args:
            filename: 更新するファイル名
            icon: 新しいアイコン
        """
        try:
            log_print(INFO, f"サムネイル更新開始: {filename}")
            
            updated = False
            # ファイル名に一致するアイテムを探して更新
            for row in range(self.model().rowCount()):
                index = self.model().index(row, 0)
                is_dir = self.model().data(index, Qt.UserRole + 1)
                
                # ディレクトリはスキップ
                if is_dir:
                    continue
                
                name = self.model().itemFromIndex(index).text()
                
                if name == filename:
                    # アイコンを更新
                    self.model().setData(index, icon, Qt.DecorationRole)
                    log_print(INFO, f"サムネイル更新成功: {filename}")
                    updated = True
                    
                    # モデルを明示的に更新（このアイテムが変更されたことを通知）
                    self.model().dataChanged.emit(index, index, [Qt.DecorationRole])
                    break
            
            if not updated:
                log_print(WARNING, f"サムネイル更新失敗: '{filename}' に該当するアイテムが見つかりません")
            
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
        
        # メニュー項目の追加
        open_action = menu.addAction("開く")
        if len(selected_items) == 1:
            # 単一選択の場合
            item = selected_items[0]
            if item['is_dir']:
                open_action.setText("フォルダを開く")
            else:
                # ファイル種別に応じたアクション
                _, ext = os.path.splitext(item['name'].lower())
                if ext in self.supported_image_extensions:
                    open_action.setText("画像を表示")
        
        # ファイルの抽出アクションを追加
        if any(not item['is_dir'] for item in selected_items):
            extract_action = menu.addAction("抽出...")
        else:
            extract_action = None
        
        # メニューを表示して選択されたアクションを取得
        action = menu.exec(event.globalPos())
        
        # アクション処理
        if action == open_action:
            # 現在は選択されたアイテムをアクティベートするだけ
            if len(selected_items) == 1:
                item = selected_items[0]
                # パスを取得
                path = item['path'].rstrip('/')
                
                # アーカイブマネージャーを通じてEntryInfo型のオブジェクトを取得
                entry_info = self.archive_manager.get_entry_info(path)
                
                # シグナルを発行 - EntryInfo型のオブジェクトを使用
                self.item_activated.emit(entry_info)
        
        elif action == extract_action:
            # ファイル抽出処理
            self._extract_selected_files(selected_items)

    def _extract_selected_files(self, selected_items):
        """選択されたファイルを抽出する"""
        # フォルダ選択ダイアログを表示
        dest_dir = QFileDialog.getExistingDirectory(
            self, "抽出先フォルダを選択", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if not dest_dir:
            return  # キャンセルされた場合
        
        # 選択されたアイテムでフォルダでないものだけを抽出
        files_to_extract = []
        for item in selected_items:
            if not item['is_dir']:
                files_to_extract.append(item['path'])
        
        # ステータスメッセージを更新
        if hasattr(self.parent(), 'update_status'):
            self.parent().update_status(f"{len(files_to_extract)}個のファイルを抽出しています...")
        
        # アーカイブマネージャーを使用してファイルを抽出
        if self.archive_manager and files_to_extract:
            try:
                extracted_count = 0
                for file_path in files_to_extract:
                    # ファイルデータを取得
                    file_data = self.archive_manager.extract_file(file_path)
                    if file_data is None:
                        log_print(ERROR, f"ファイルの抽出に失敗: {file_path}")
                        continue
                    
                    # 保存先パスを構築
                    out_path = os.path.join(dest_dir, os.path.basename(file_path))
                    
                    # ファイルに書き込み
                    with open(out_path, 'wb') as f:
                        f.write(file_data)
                    
                    extracted_count += 1
                
                # 完了メッセージを表示
                if hasattr(self.parent(), 'update_status'):
                    self.parent().update_status(f"{extracted_count}個のファイルを抽出しました")
                
            except Exception as e:
                log_print(ERROR, f"ファイル抽出中にエラーが発生しました: {e}")
                if hasattr(self.parent(), 'update_status'):
                    self.parent().update_status(f"エラー: ファイル抽出に失敗しました")

    def set_items(self, items: List[Dict[str, Any]]):
        """
        ディレクトリ内のアイテムを設定
        
        Args:
            items: ディレクトリ内のアイテムリスト
        """
        # 進行中のサムネイル生成タスクをキャンセル
        self.handle_folder_changed()
        
        # モデルにアイテムを設定
        self.file_model.set_items(items, self.archive_manager and not self.archive_manager.current_directory)
        
        # デバッグ情報
        if self.debug_mode:
            log_print(INFO, f"FileListView: {len(items)}個のアイテムを設定しました")
        
        # 常に左から右、上から下への横並び・縦スクロール表示に設定
        self.setFlow(QListView.LeftToRight)
        
        # アイテム設定後、自動的にサムネイル生成を開始
        self.generate_thumbnails()

    def clear_items(self):
        """アイテムをクリア"""
        if hasattr(self, 'file_model'):
            self.file_model.clear()
            if self.debug_mode:
                log_print(INFO, "FileListView: アイテムをクリアしました")
    
    def get_optimal_icon_column_width(self):
        """アイコン表示に最適な列の幅を計算"""
        # アイコンモードでは特に必要ないので0を返す
        return 0


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
