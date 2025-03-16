"""
アーカイブビューワー

PySide6ベースのGUIアプリケーション。
アーカイブファイルやフォルダの内容をブラウズ可能。
ネスト化されたアーカイブファイルにも対応。
"""

# 標準ライブラリ
import os
import sys
import traceback
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
import argparse  # コマンドライン引数解析用に追加

# 親パッケージからインポートできるようにパスを調整
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# ロギングシステム
from logutils import setup_logging, log_print, log_trace, DEBUG, INFO, WARNING, ERROR, CRITICAL

# サードパーティライブラリ（PySide6）
from PySide6.QtCore import (
    Qt, QDir, QModelIndex, QItemSelectionModel, Signal, Slot,
    QObject, QSize, QUrl, QMimeData, QByteArray
)
from PySide6.QtGui import (
    QAction, QIcon, QStandardItemModel, QStandardItem, QKeySequence,
    QDragEnterEvent, QDropEvent, QResizeEvent
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTreeView, QFileSystemModel,
    QVBoxLayout, QHBoxLayout, QWidget, QLabel, QMessageBox,
    QPushButton, QToolBar, QStatusBar, QFileDialog, QMenu, QHeaderView,
    QStyle
)

# アプリケーション固有のモジュール
from arc.arc import EntryInfo, EntryType
from arc.interface import get_archive_manager
from arc.manager.enhanced import EnhancedArchiveManager
from arc.viewer.imageviewer import ImageViewerWindow
from arc.viewer.preview import FilePreviewWidget
    

class ArchiveViewModel(QStandardItemModel):
    """アーカイブ内のファイル/フォルダを表示するためのモデル"""
    
    def __init__(self, parent=None):
        """モデルを初期化"""
        super().__init__(parent)
        self.setHorizontalHeaderLabels(["名前", "サイズ", "種類", "更新日時"])
        self._manager = get_archive_manager()
        self._current_path = ""

    def load_entries(self, path: str) -> bool:
        """
        指定されたパスのエントリを読み込む
        
        Args:
            path: 表示する相対パス
            
        Returns:
            成功したらTrue
        """
        try:
            self.clear()
            self.setHorizontalHeaderLabels(["名前", "サイズ", "種類", "更新日時"])
            
            self._current_path = path
            log_print(INFO, f"ViewModel: 相対パス '{path}' のエントリを読み込みます")
            
            # アーカイブマネージャーからエントリを取得
            # 注: manager.current_pathからの相対パスとして処理される
            entries = self._manager.list_entries(path)
            
            if not entries:
                log_print(WARNING, f"ViewModel: パス '{path}' にエントリがありません")
                return False
                
            log_print(INFO, f"ViewModel: {len(entries)} エントリを読み込みました")
            
            # エントリをモデルに追加
            for entry in sorted(entries, key=lambda e: (e.type.value, e.name)):
                self._add_entry_to_model(entry)
                
            return True
            
        except Exception as e:
            log_print(ERROR, f"ViewModel エラー: {e}")
            traceback.print_exc()
            return False
    
    def _add_entry_to_model(self, entry: EntryInfo) -> None:
        """
        エントリをモデルに追加
        
        Args:
            entry: 追加するエントリ情報
        """
        # 名前アイテム
        name_item = QStandardItem(entry.name)
        
        # アイコン設定
        if entry.type == EntryType.DIRECTORY:
            name_item.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        elif entry.type == EntryType.ARCHIVE:
            # アーカイブはフォルダとして表示するが、特別なアイコンを使用
            # SP_DriveZipIconは存在しないのでSP_DriveFDIcon（フロッピーディスク）を使用
            name_item.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DriveFDIcon))
        else:
            name_item.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        
        # サイズアイテム
        size_str = "-" if entry.type == EntryType.DIRECTORY else f"{entry.size:,}"
        size_item = QStandardItem(size_str)
        size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # 種類アイテム
        type_str = "フォルダ" if entry.type == EntryType.DIRECTORY else "アーカイブ" if entry.type == EntryType.ARCHIVE else "ファイル"
        type_item = QStandardItem(type_str)
        
        # 更新日時アイテム
        date_str = "-" if entry.modified_time is None else entry.modified_time.strftime("%Y/%m/%d %H:%M:%S")
        date_item = QStandardItem(date_str)
        
        # データを保存
        name_item.setData(entry, Qt.UserRole)
        
        # 行を追加
        self.appendRow([name_item, size_item, type_item, date_item])
    
    def get_entry_at(self, index: QModelIndex) -> Optional[EntryInfo]:
        """
        指定インデックスのエントリを取得
        
        Args:
            index: モデルインデックス
            
        Returns:
            EntryInfo または None
        """
        if not index.isValid():
            return None
            
        # 同じ行の最初の列（名前）のアイテムからデータを取得
        name_index = self.index(index.row(), 0, index.parent())
        return self.data(name_index, Qt.UserRole)


class ArchiveViewerWindow(QMainWindow):
    """アーカイブビューワーのメインウィンドウ"""
    
    def __init__(self):
        """ウィンドウの初期化"""
        super().__init__()
        
        # アーカイブマネージャーのインスタンス
        self._manager = get_archive_manager()
        
        # 現在のパス (manager.current_pathからの相対パス)
        self._relative_path = ""  # 現在のmanager.current_pathからの相対パス
        self._path_history = []   # 相対パスの履歴
        self._history_index = -1
        
        # ウィンドウの設定
        self.setWindowTitle("SupraView - アーカイブビューワー")
        self.setMinimumSize(800, 600)
        
        # ウィンドウのアイコン設定
        self.setWindowIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        
        # UI初期化
        self._setup_ui()
        
        # D&Dの設定
        self.setAcceptDrops(True)
    
    def _setup_ui(self):
        """UIの初期化"""
        # メインウィジェットとレイアウト
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # ツールバーの作成
        self._create_toolbar()
        
        # スプリッターの作成
        splitter = QSplitter(Qt.Horizontal)
        
        # ファイルリストモデル
        self._file_model = ArchiveViewModel(self)
        
        # ファイルリストビュー
        self._file_view = QTreeView()
        self._file_view.setModel(self._file_model)
        self._file_view.setSelectionBehavior(QTreeView.SelectRows)
        self._file_view.doubleClicked.connect(self._on_item_double_clicked)
        self._file_view.clicked.connect(self._on_item_clicked)  # プレビュー表示用
        self._file_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._file_view.customContextMenuRequested.connect(self._show_context_menu)
        
        # ヘッダーの設定
        header = self._file_view.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # 名前列を伸縮
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # サイズ列をコンテンツに合わせる
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 種類列をコンテンツに合わせる
        
        # プレビューエリア
        self._preview_widget = FilePreviewWidget()
        
        # スプリッターにウィジェットを追加
        splitter.addWidget(self._file_view)
        splitter.addWidget(self._preview_widget)
        
        # スプリッターの初期サイズ比
        splitter.setSizes([int(self.width() * 0.4), int(self.width() * 0.6)])
        
        # メインレイアウトにスプリッターを追加
        main_layout.addWidget(splitter)
        
        # ステータスバーの作成
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # パス表示ラベル
        self._path_label = QLabel("")
        self.statusBar.addWidget(self._path_label, 1)
        
        # エントリ数表示
        self._count_label = QLabel("")
        self.statusBar.addPermanentWidget(self._count_label)
        
        # メインウィジェットをウィンドウに設定
        self.setCentralWidget(main_widget)
    
    def _create_toolbar(self):
        """ツールバーの作成"""
        toolbar = QToolBar("メインツールバー")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)
        
        # 戻るアクション
        self._back_action = QAction(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack), "戻る", self)
        self._back_action.setShortcut(QKeySequence.Back)
        self._back_action.triggered.connect(self._go_back)
        self._back_action.setEnabled(False)
        toolbar.addAction(self._back_action)
        
        # 進むアクション
        self._forward_action = QAction(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward), "進む", self)
        self._forward_action.setShortcut(QKeySequence.Forward)
        self._forward_action.triggered.connect(self._go_forward)
        self._forward_action.setEnabled(False)
        toolbar.addAction(self._forward_action)
        
        # 上へアクション
        self._up_action = QAction(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp), "上へ", self)
        self._up_action.setShortcut(QKeySequence("Alt+Up"))
        self._up_action.triggered.connect(self._go_up)
        self._up_action.setEnabled(False)
        toolbar.addAction(self._up_action)
        
        toolbar.addSeparator()
        
        # 開くアクション
        open_action = QAction(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "開く", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_archive)
        toolbar.addAction(open_action)
        
        # 更新アクション
        refresh_action = QAction(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "更新", self)
        refresh_action.setShortcut(QKeySequence.Refresh)
        refresh_action.triggered.connect(self._refresh_view)
        toolbar.addAction(refresh_action)
    
    def _update_status_bar(self):
        """ステータスバーを更新"""
        # manager.current_path と relative_path を組み合わせて表示
        root_path = self._manager.current_path if hasattr(self._manager, 'current_path') else ""
        
        if self._relative_path:
            # パスをフォーマットしてスラッシュが重複しないように組み合わせる
            if root_path:
                if root_path.endswith('/') or self._relative_path.startswith('/'):
                    display_path = f"{root_path}{self._relative_path}"
                else:
                    display_path = f"{root_path}/{self._relative_path}"
            else:
                display_path = self._relative_path
        else:
            display_path = root_path
            
        # パス表示を更新
        self._path_label.setText(f"場所: {display_path}")
        
        # エントリ数表示を更新
        count = self._file_model.rowCount()
        self._count_label.setText(f"{count} アイテム")
        
        # アクションの有効/無効を更新
        self._back_action.setEnabled(self._history_index > 0)
        self._forward_action.setEnabled(self._history_index < len(self._path_history) - 1)
        # ルート以外なら「上へ」を有効化
        self._up_action.setEnabled(bool(self._relative_path))
    
    def _join_relative_paths(self, base_path: str, child_name: str) -> str:
        """
        相対パスを結合する
        
        Args:
            base_path: 基準相対パス
            child_name: 子要素名
            
        Returns:
            結合された相対パス
        """
        if not base_path:
            return child_name
        else:
            # スラッシュが重複しないように結合
            return f"{base_path}/{child_name}"
    
    def _on_item_clicked(self, index):
        """
        アイテムがクリックされたときの処理（プレビュー表示用）
        
        Args:
            index: クリックされたアイテムのインデックス
        """
        # エントリを取得
        entry = self._file_model.get_entry_at(index)
        if not entry:
            return
            
        # プレビューを表示
        self._preview_widget.show_entry_preview(entry, self._relative_path)
    
    def _on_item_double_clicked(self, index):
        """
        アイテムがダブルクリックされたときの処理
        
        Args:
            index: クリックされたアイテムのインデックス
        """
        # エントリを取得
        entry = self._file_model.get_entry_at(index)
        if not entry:
            return
            
        # ディレクトリかアーカイブの場合は開く
        if entry.type in [EntryType.DIRECTORY, EntryType.ARCHIVE]:
            # 相対パスを構築
            new_path = self._join_relative_paths(self._relative_path, entry.name)
            self._navigate_to(new_path)
        # 通常ファイルの場合はプレビュー
        elif entry.type == EntryType.FILE:
            # エントリの相対パスを構築
            entry_rel_path = self._join_relative_paths(self._relative_path, entry.name)
            
            try:
                # ファイルを読み込む
                content = self._manager.read_file(entry_rel_path)
                if content is None:
                    QMessageBox.warning(
                        self,
                        "プレビューエラー",
                        f"ファイル '{entry.name}' の読み込みに失敗しました。"
                    )
                    return
                
                # 画像ファイルかどうかを拡張子で判定
                _, ext = os.path.splitext(entry.name.lower())
                image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.webp']
                
                if ext in image_extensions:
                    # 画像の場合は専用ビューアーで表示
                    self._show_image_viewer(entry.name, content)
                else:
                    # それ以外はプレビューパネルに表示
                    self._preview_widget.show_entry_preview(entry, self._relative_path)
                
                # ステータスバーにメッセージを表示
                self.statusBar.showMessage(f"'{entry.name}' をプレビュー中", 3000)  # 3秒間表示
                
            except Exception as e:
                print(f"プレビューエラー: {e}")
                traceback.print_exc()
                QMessageBox.critical(
                    self,
                    "プレビューエラー",
                    f"ファイルのプレビュー中にエラーが発生しました:\n{str(e)}"
                )
    
    def _show_image_viewer(self, image_name: str, image_data: bytes):
        """
        画像ビューアーを表示
        
        Args:
            image_name: 画像ファイル名
            image_data: 画像データ
        """
        # 画像ビューアーウィンドウを作成
        viewer = ImageViewerWindow(f"画像プレビュー: {image_name}", self)
        
        # 画像をセット
        success = viewer.set_image(image_data, image_name)
        
        if success:
            # ウィンドウを表示
            viewer.show()
        else:
            QMessageBox.warning(
                self,
                "画像表示エラー",
                f"画像 '{image_name}' の読み込みに失敗しました。"
            )
            viewer.close()
    
    def _navigate_to(self, relative_path: str):
        """
        指定された相対パスに移動
        
        Args:
            relative_path: current_pathからの相対パス
        """
        log_print(INFO, f"相対パス '{relative_path}' に移動します")
        
        # パスを正規化
        relative_path = relative_path.replace('\\', '/')
        
        try:
            # 履歴を更新
            if self._relative_path != relative_path:
                # 現在位置から新しい場所に移動する場合、それ以降の履歴を削除
                if self._history_index < len(self._path_history) - 1:
                    self._path_history = self._path_history[:self._history_index + 1]
                
                # 現在のパスを履歴に追加
                if self._relative_path:  # 空でない場合のみ追加
                    self._path_history.append(self._relative_path)
                    self._history_index = len(self._path_history) - 1
            
            # 現在の相対パスを更新
            self._relative_path = relative_path
            
            # ファイルリストを更新
            if not self._file_model.load_entries(relative_path):
                # 読み込みに失敗した場合、エラーメッセージを表示
                QMessageBox.warning(
                    self, 
                    "読み込みエラー",
                    f"パス '{relative_path}' の内容を読み込めませんでした。"
                )
                
                # 前の場所に戻す
                if self._path_history:
                    self._relative_path = self._path_history.pop()
                    self._history_index = len(self._path_history) - 1
                    self._file_model.load_entries(self._relative_path)
                else:
                    # 履歴がない場合はルートに戻る
                    self._relative_path = ""
                    self._file_model.load_entries("")
            
            # ステータスバーを更新
            self._update_status_bar()
            
            # ウィンドウタイトルを更新（パスを含める）
            root_path = self._manager.current_path if hasattr(self._manager, 'current_path') else ""
            base_name = os.path.basename(root_path) if root_path else "ルート"
            
            if self._relative_path:
                # ネスト深度が表現できるようにタイトルに現在の相対パスも付加
                parts = self._relative_path.split('/')
                if len(parts) > 2:
                    # パスが長い場合は省略表示
                    path_display = f"{parts[0]}/.../{parts[-1]}"
                else:
                    path_display = self._relative_path
                
                self.setWindowTitle(f"SupraView - {base_name} - {path_display}")
            else:
                self.setWindowTitle(f"SupraView - {base_name}")
            
        except Exception as e:
            log_print(ERROR, f"ナビゲーションエラー: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self, 
                "エラー",
                f"パス '{relative_path}' への移動中にエラーが発生しました:\n{str(e)}"
            )
    
    def _go_back(self):
        """履歴を戻る"""
        if self._history_index > 0:
            self._history_index -= 1
            path = self._path_history[self._history_index]
            
            # 現在の相対パスを更新して表示を更新
            self._relative_path = path
            self._file_model.load_entries(path)
            self._update_status_bar()
    
    def _go_forward(self):
        """履歴を進む"""
        if self._history_index < len(self._path_history) - 1:
            self._history_index += 1
            path = self._path_history[self._history_index]
            
            # 現在の相対パスを更新して表示を更新
            self._relative_path = path
            self._file_model.load_entries(path)
            self._update_status_bar()
    
    def _go_up(self):
        """親ディレクトリへ移動"""
        if not self._relative_path:
            return  # ルートの場合は何もしない
            
        # パスを正規化
        path = self._relative_path.replace('\\', '/')
        
        # 末尾のスラッシュを削除
        if path.endswith('/') and len(path) > 1:
            path = path[:-1]
        
        # スラッシュが含まれない場合はルートに戻る
        if '/' not in path:
            self._navigate_to("")
            return
            
        # カスタム親パス抽出（マネージャーのget_parent_pathよりも優先）
        last_slash_index = path.rfind('/')
        if last_slash_index > 0:
            # 最後のスラッシュより前の部分を親パスとする
            parent_path = path[:last_slash_index]
        else:
            # スラッシュが先頭にあるか、見つからない場合はルート
            parent_path = ""
            
        log_print(INFO, f"親ディレクトリへ移動: {path} -> {parent_path}")
        
        # 親パスへ移動
        self._navigate_to(parent_path)
    
    def _open_archive(self):
        """アーカイブファイルを開く"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "アーカイブファイルまたはディレクトリを開く",
            "",
            "すべてのファイル (*.*)"
        )
        
        if file_path:
            self._set_archive_path(file_path)
    
    def _refresh_view(self):
        """ビューを更新"""
        self._file_model.load_entries(self._relative_path)
        self._update_status_bar()
    
    def _show_context_menu(self, position):
        """
        コンテキストメニューを表示
        
        Args:
            position: マウス位置
        """
        # 選択されたインデックスを取得
        indexes = self._file_view.selectedIndexes()
        if not indexes:
            return
            
        # 複数列を選択した場合に重複を除去
        selected_rows = set()
        selected_entries = []
        
        for index in indexes:
            if index.row() not in selected_rows:
                selected_rows.add(index.row())
                entry = self._file_model.get_entry_at(index)
                if entry:
                    selected_entries.append(entry)
        
        if not selected_entries:
            return
            
        # メニューを作成
        menu = QMenu(self)
        
        # 単一選択の場合
        if len(selected_entries) == 1:
            entry = selected_entries[0]
            
            if entry.type in [EntryType.DIRECTORY, EntryType.ARCHIVE]:
                open_action = menu.addAction("開く")
                open_action.triggered.connect(lambda: self._on_item_double_clicked(indexes[0]))
            
            # ファイルまたはアーカイブのみ抽出可能
            if entry.type != EntryType.DIRECTORY:
                extract_action = menu.addAction("抽出...")
                extract_action.triggered.connect(lambda: self._extract_entry(entry))
            
            menu.addSeparator()
            
        # 複数選択の場合も抽出を可能にする
        if len(selected_entries) > 1:
            # 非フォルダ（ファイルとアーカイブ）の数を数える
            non_dir_count = sum(1 for e in selected_entries if e.type != EntryType.DIRECTORY)
            
            if non_dir_count > 0:
                extract_all_action = menu.addAction(f"選択した {non_dir_count} 項目を抽出...")
                extract_all_action.triggered.connect(lambda: self._extract_entries(selected_entries))
        
        # メニューを表示
        menu.exec(self._file_view.viewport().mapToGlobal(position))
    
    def _extract_entry(self, entry: EntryInfo):
        """
        エントリを抽出
        
        Args:
            entry: 抽出するエントリ
        """
        # ディレクトリの場合
        if entry.type == EntryType.DIRECTORY:
            QMessageBox.information(
                self,
                "情報",
                f"フォルダ '{entry.name}' の抽出はまだサポートされていません。"
            )
            return
        
        # 保存先を選択
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"{entry.name} を保存",
            entry.name,
            "すべてのファイル (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            # エントリの相対パスを構築
            entry_rel_path = self._join_relative_paths(self._relative_path, entry.name)
            
            # ファイルの内容を読み込む
            content = self._manager.read_file(entry_rel_path)
            
            if content is None:
                QMessageBox.warning(
                    self,
                    "抽出エラー",
                    f"ファイル '{entry.name}' の読み込みに失敗しました。"
                )
                return
                
            # ファイルに保存
            with open(file_path, 'wb') as f:
                f.write(content)
                
            QMessageBox.information(
                self,
                "抽出完了",
                f"ファイル '{entry.name}' を '{file_path}' に抽出しました。"
            )
            
        except Exception as e:
            log_print(ERROR, f"抽出エラー: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "抽出エラー",
                f"ファイルの抽出中にエラーが発生しました:\n{str(e)}"
            )
    
    def _extract_entries(self, entries: List[EntryInfo]):
        """
        複数のエントリを抽出
        
        Args:
            entries: 抽出するエントリのリスト
        """
        # 保存先フォルダを選択
        directory = QFileDialog.getExistingDirectory(
            self,
            "抽出先フォルダを選択",
            ""
        )
        
        if not directory:
            return
            
        success_count = 0
        error_count = 0
        
        for entry in entries:
            # ディレクトリはスキップ（アーカイブは抽出可能）
            if entry.type == EntryType.DIRECTORY:
                continue
                
            try:
                # エントリの相対パスを構築
                entry_rel_path = self._join_relative_paths(self._relative_path, entry.name)
                
                # ファイルの内容を読み込む
                content = self._manager.read_file(entry_rel_path)
                
                if content is None:
                    log_print(ERROR, f"ファイル '{entry.name}' の読み込みに失敗しました")
                    error_count += 1
                    continue
                    
                # 保存先のパスを構築
                save_path = os.path.join(directory, entry.name)
                
                # 既存ファイルチェック
                if os.path.exists(save_path):
                    # 名前の衝突を回避
                    base, ext = os.path.splitext(entry.name)
                    counter = 1
                    while os.path.exists(save_path):
                        new_name = f"{base}_{counter}{ext}"
                        save_path = os.path.join(directory, new_name)
                        counter += 1
                
                # ファイルに保存
                with open(save_path, 'wb') as f:
                    f.write(content)
                    
                success_count += 1
                
            except Exception as e:
                log_print(ERROR, f"抽出エラー ({entry.name}): {e}")
                error_count += 1
        
        # 結果を表示
        if error_count == 0:
            QMessageBox.information(
                self,
                "抽出完了",
                f"{success_count} ファイルを '{directory}' に抽出しました。"
            )
        else:
            QMessageBox.warning(
                self,
                "抽出完了",
                f"{success_count} ファイルを抽出しました。{error_count} ファイルの処理中にエラーが発生しました。"
            )
    
    def _set_archive_path(self, path: str) -> bool:
        """
        アーカイブパスを設定
        
        Args:
            path: アーカイブファイルへのパス
            
        Returns:
            成功した場合はTrue、失敗した場合はFalse
        """
        # パスを正規化
        path = path.replace('\\', '/')
        
        if not os.path.exists(path):
            QMessageBox.warning(
                self,
                "エラー",
                f"ファイルが見つかりません: {path}"
            )
            return False
            
        if not os.path.isfile(path) and not os.path.isdir(path):
            QMessageBox.warning(
                self,
                "エラー",
                f"指定されたパスはファイルまたはディレクトリではありません: {path}"
            )
            return False
            
        try:
            # 履歴をクリア
            self._path_history = []
            self._history_index = -1
            
            # マネージャーにcurrent_pathを設定（EnhancedArchiveManagerの場合）
            if isinstance(self._manager, EnhancedArchiveManager):
                log_print(INFO, f"マネージャーに現在のパスを設定: {path}")
                self._manager.set_current_path(path)
            
            # 相対パスをリセット（ルートから開始）
            self._relative_path = ""
            
            # ウィンドウタイトルを更新
            self.setWindowTitle(f"SupraView - {os.path.basename(path)}")
            
            # ファイルリストを更新（空の相対パスでルートのエントリを表示）
            if not self._file_model.load_entries(""):
                # 読み込みに失敗した場合、エラーメッセージを表示
                QMessageBox.warning(
                    self, 
                    "読み込みエラー",
                    f"パス '{path}' の内容を読み込めませんでした。"
                )
                return False
            
            # ステータスバーを更新
            self._update_status_bar()
            
            return True
            
        except Exception as e:
            log_print(ERROR, f"アーカイブ設定エラー: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "エラー",
                f"アーカイブの設定に失敗しました: {str(e)}"
            )
            return False
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """
        ドラッグ操作の開始時処理
        
        Args:
            event: ドラッグイベント
        """
        # ファイルをドロップできるようにする
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """
        ドロップ時の処理
        
        Args:
            event: ドロップイベント
        """
        # ドロップされたURLを取得
        urls = event.mimeData().urls()
        if not urls:
            return
            
        # 最初のURLのみ処理
        file_path = urls[0].toLocalFile()
        
        if file_path:
            self._set_archive_path(file_path)


def main():
    """メイン関数"""
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description="アーカイブビューワー")
    parser.add_argument('archive', nargs='?', help="開くアーカイブファイルのパス")
    parser.add_argument('--debug', action='store_true', help="デバッグモードを有効化")
    
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    
    # ロギングシステムの初期化（デフォルトはERRORレベル）
    log_level = DEBUG if args.debug else ERROR
    setup_logging(log_level)
    
    if args.debug:
        log_print(DEBUG, "デバッグモードで起動しました")
    
    # スタイルの設定
    app.setStyle('Fusion')
    
    # メインウィンドウを作成
    window = ArchiveViewerWindow()
    window.show()
    
    # コマンドライン引数で指定されたファイルを開く
    if args.archive:
        window._set_archive_path(args.archive)
    
    # イベントループを開始
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
