"""
画像プレビューウィンドウ

アーカイブ内の画像ファイルをプレビュー表示するためのメインウィンドウ
"""

import os
import sys
from time import sleep
from typing import Optional, Dict, Any, List, Tuple

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if (project_root not in sys.path):
    sys.path.insert(0, project_root)

from logutils import log_print, INFO, WARNING, ERROR, DEBUG, CRITICAL

try:
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QSplitter, QStatusBar
    )
    from PySide6.QtCore import Qt, QTimer, QEvent
    from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent, QContextMenuEvent, QResizeEvent, QPixmap
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)

# 内部モジュールをインポート
from .image_processor import load_image_from_bytes, format_image_info
# 画像ハンドラをインポート
from .image_handler import ImageHandler
# 新しい画像モデルをインポート
from .image_model import ImageModel
# 直接decoderモジュールからインポート
from decoder.interface import get_supported_image_extensions
from .navigation_bar import NavigationBar
from .information_bar import InformationBar  # インフォメーションバーをインポート
from .context_menu import PreviewContextMenu
from .display_handler import ImageScrollArea, DisplayHandler
from .event_handler import EventHandler


class ImagePreviewWindow(QMainWindow):
    """画像ファイルをプレビュー表示するためのメインウィンドウ"""
    
    # サポートする画像形式の拡張子を直接decoderから取得
    SUPPORTED_EXTENSIONS = get_supported_image_extensions()
    
    def __init__(self, parent=None, archive_manager=None, initial_path=None, dual_view=False, sr_manager=None):
        """
        画像プレビューウィンドウの初期化
        
        Args:
            parent: 親ウィジェット（省略可能）
            archive_manager: 画像データを取得するためのアーカイブマネージャ
            initial_path: 初期表示する画像の相対パス（省略可能）
            dual_view: デュアルビューを有効にするかどうか（デフォルトはFalse）
            sr_manager: 超解像処理マネージャ（省略可能）
        """
        super().__init__(parent)
        
        # イベント処理をブロックするためのフラグ
        self._is_updating_images = False
        
        # ウィンドウの基本設定
        self.setWindowTitle("画像プレビュー")
        self.resize(1024, 768)
        
        # アーカイブマネージャの参照を保存
        self.archive_manager = archive_manager
        
        # 初期表示パスの保存
        self._initial_path = initial_path
        
        # 画像モデルを初期化
        self.image_model = ImageModel()
        # 初期状態ではウィンドウに合わせるモードをONに設定
        self.image_model.set_display_mode(True)
        
        # デュアルビュー設定をモデルに反映
        if dual_view:
            self.image_model.set_view_mode("dual_lr")  # デフォルトは左右
        else:
            self.image_model.set_view_mode("single")
        
        # アーカイブブラウザの参照を初期化
        self._browser = None
        
        # 画像ハンドラの初期化（画像モデルを渡す）
        self.image_handler = ImageHandler(self, archive_manager, self.image_model)
        
        # 超解像マネージャをセット（省略可能）
        if sr_manager:
            self.image_handler.set_superres_manager(sr_manager)
            log_print(INFO, "超解像マネージャをプレビューウィンドウに設定しました")
        
        # ハンドラクラスの初期化（画像モデルを渡す）
        self.display_handler = DisplayHandler(self, self.image_model)
        self.event_handler = EventHandler(self)
        
        # UIコンポーネントのセットアップ
        self._setup_ui()
        
        # イベントハンドラにコールバックを登録
        self._register_callbacks()
        
        # キーボードフォーカスを有効化（強力なフォーカスに設定）
        self.setFocusPolicy(Qt.StrongFocus)
        
        # ナビゲーションバーの初期化
        self._setup_navigation_bar()
        
        # インフォメーションバーの初期化
        self._setup_information_bar()
        
        # コンテキストメニューの初期化
        self._setup_context_menu()
        
        # マウストラッキング有効化（マウス移動イベントを取得するため）
        self.setMouseTracking(True)
        self.central_widget.setMouseTracking(True)
        if self.image_model.is_dual_view():
            self.splitter.setMouseTracking(True)
            self.image_areas[0].setMouseTracking(True)
            self.image_areas[1].setMouseTracking(True)
        else:
            self.image_areas[0].setMouseTracking(True)
        
        # アーカイブマネージャがあればブラウザを初期化
        if self.archive_manager:
            self._init_browser(initial_path)
        
        # デフォルトでウィンドウに合わせるモードにする
        self.fit_to_window()
        
        # 初期情報を表示する（インフォメーションバーを一度表示する）
        self._update_status_info()
        self._show_information_bar()
        
        # フォーカスイベントのデバッグ出力を追加
        self.installEventFilter(self)
        
        log_print(INFO, "画像プレビューウィンドウが初期化されました")
    
    def _register_callbacks(self):
        """イベントハンドラにコールバックを登録"""
        # ナビゲーション関連
        self.event_handler.register_callback('prev_image', self._on_prev_image)
        self.event_handler.register_callback('next_image', self._on_next_image)
        self.event_handler.register_callback('first_image', self._on_first_image)
        self.event_handler.register_callback('last_image', self._on_last_image)
        self.event_handler.register_callback('prev_folder', self._on_prev_folder)
        self.event_handler.register_callback('next_folder', self._on_next_folder)
        
        # 明示的にフォルダ先頭と末尾へのコールバックを登録
        self.event_handler.register_callback('first_folder_image', self._on_first_folder_image)
        self.event_handler.register_callback('last_folder_image', self._on_last_folder_image)
        
        # フルスクリーン関連コールバックを追加
        self.event_handler.register_callback('toggle_fullscreen', self._on_toggle_fullscreen)
        
        # 表示モード関連
        self.event_handler.register_callback('toggle_dual_view', self.toggle_dual_view)
        self.event_handler.register_callback('toggle_shift_mode', self.toggle_shift_mode)
        
        # 超解像処理のコールバックを追加
        self.event_handler.register_callback('apply_superres', self._on_superres)
        
        # ウィンドウ関連
        self.event_handler.register_callback('close', self.close)
        self.event_handler.register_callback('show_navigation', self._show_navigation_bar)
        self.event_handler.register_callback('hide_navigation', self._hide_navigation_bar)
        self.event_handler.register_callback('show_information', self._show_information_bar)  # 追加
        self.event_handler.register_callback('hide_information', self._hide_information_bar)  # 追加
        self.event_handler.register_callback('adjust_navigation_size', self._adjust_navigation_size)
        self.event_handler.register_callback('adjust_information_size', self._adjust_information_size)  # 追加
        self.event_handler.register_callback('show_context_menu', self._show_context_menu)
        
        # 全ての登録済みコールバックをログに出力
        log_print(INFO, f"登録されたコールバック: {list(self.event_handler.callbacks.keys())}")
    
    def _init_browser(self, path: str):
        print("init_browser:", path)
        """アーカイブブラウザの初期化"""
        if self.archive_manager:
            try:
                # デコーダが対応している拡張子リストを取得
                supported_exts = get_supported_image_extensions()
                
                # 画像モデルからブラウザの設定を取得
                browser_pages = self.image_model.get_browser_pages()
                browser_shift = self.image_model.is_browser_shift()
                
                # ブラウザを初期化（初期パスは指定せずに作成）
                self._browser = self.archive_manager.get_browser(
                    exts=supported_exts,
                    current_path=path,
                    pages=browser_pages,
                    shift=browser_shift
                )
                log_print(INFO, f"アーカイブブラウザを初期化しました: pages={browser_pages}, shift={browser_shift}")
                
                # 初期パスが指定されていれば、明示的にjumpを呼び出して移動
                if self._initial_path:
                    self._browser.jump(self._initial_path)
                    log_print(INFO, f"初期パス '{self._initial_path}' へジャンプしました")
                    
                    # ブラウザの内容を表示に反映
                    self._update_images_from_browser()
                    
                    # ウィンドウタイトルを初期パスのファイル名で更新
                    filename = os.path.basename(self._initial_path)
                    self.setWindowTitle(f"画像プレビュー - {filename}")
            except Exception as e:
                log_print(ERROR, f"アーカイブブラウザの初期化に失敗しました: {e}")
    
    def _setup_ui(self):
        """UIコンポーネントの初期化"""
        # 中央ウィジェットとレイアウトの設定
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 背景色を黒に設定
        self.central_widget.setStyleSheet("background-color: black;")
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 画像エリアの作成
        self.image_areas = []
        
        if self.image_model.is_dual_view():
            # デュアルビューの場合はスプリッターを使用
            self.splitter = QSplitter(Qt.Horizontal)
            # スプリッターの背景も黒に設定
            self.splitter.setStyleSheet("background-color: black;")
            self.main_layout.addWidget(self.splitter)
            
            # 左右の画像エリアを作成
            for i in range(2):
                scroll_area = ImageScrollArea()
                scroll_area.setFocusPolicy(Qt.StrongFocus)  # キーボードフォーカスを有効化
                self.image_areas.append(scroll_area)
                self.splitter.addWidget(scroll_area)
            
            # スプリッターの位置を50:50に設定
            self.splitter.setSizes([500, 500])
        else:
            # シングルビューの場合は単純にスクロールエリアを追加
            scroll_area = ImageScrollArea()
            scroll_area.setFocusPolicy(Qt.StrongFocus)  # キーボードフォーカスを有効化
            self.image_areas.append(scroll_area)
            self.main_layout.addWidget(scroll_area)
            
            # 2画面用に配列を2要素にする（未使用でも統一的に扱えるように）
            self.image_areas.append(None)
        
        # 表示ハンドラに画像エリアを設定
        self.display_handler.setup_image_areas(self.image_areas)
                
        # ステータスバーを追加
        self.statusbar = QStatusBar()
        # ステータスバーの背景は変更しない（OSのテーマに合わせるため）
        self.setStatusBar(self.statusbar)
        
        # 中央ウィジェットにキーボードフォーカスを設定
        self.central_widget.setFocusPolicy(Qt.StrongFocus)
    
    def _setup_navigation_bar(self):
        """ナビゲーションバーのセットアップ"""
        self.navigation_bar = NavigationBar(self)
        
        # ナビゲーションバーのシグナルを接続
        self.navigation_bar.first_image_requested.connect(self._on_first_image)
        self.navigation_bar.prev_image_requested.connect(self._on_prev_image)
        self.navigation_bar.next_image_requested.connect(self._on_next_image)
        self.navigation_bar.last_image_requested.connect(self._on_last_image)
        self.navigation_bar.prev_folder_requested.connect(self._on_prev_folder)
        self.navigation_bar.next_folder_requested.connect(self._on_next_folder)
        
        # フォルダ先頭/末尾用のシグナルを接続
        self.navigation_bar.first_folder_requested.connect(self._on_first_folder_image)
        self.navigation_bar.last_folder_requested.connect(self._on_last_folder_image)
        
        # フルスクリーン切り替えシグナルを接続
        self.navigation_bar.toggle_fullscreen_requested.connect(self._on_toggle_fullscreen)
        
        # イベントハンドラにナビゲーションバーのシグナル情報を登録
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.register_navigation_bar_signals(self.navigation_bar)
        
        # 親がQMainWindowであることが前提
        # 初期状態では非表示
        self.navigation_bar.hide()
    
    def _setup_information_bar(self):
        """インフォメーションバーのセットアップ"""
        self.information_bar = InformationBar(self)
        
        # 初期状態では非表示
        self.information_bar.hide()
    
    def _setup_context_menu(self):
        """コンテキストメニューの初期化"""
        self.context_menu = PreviewContextMenu(self)
    
    def _show_navigation_bar(self):
        """ナビゲーションバーを表示"""
        if hasattr(self, 'navigation_bar'):
            self.navigation_bar.show_bar()
            # 隠すタイマーをリセット
            self.navigation_bar._hide_timer.stop()
            return True
        return False
    
    def _hide_navigation_bar(self):
        """ナビゲーションバーを非表示"""
        if hasattr(self, 'navigation_bar') and self.navigation_bar._visible:
            # 1.5秒後に隠す
            self.navigation_bar._hide_timer.start(1500)
            return True
        return False
    
    def _adjust_navigation_size(self, width: int):
        """ナビゲーションバーのサイズを調整"""
        if hasattr(self, 'navigation_bar'):
            # 完全な再配置を行う
            self.navigation_bar._set_position()
            
            if self.navigation_bar.isVisible():
                self.navigation_bar.set_bottom_margin(10)
            
            log_print(DEBUG, f"ナビゲーションバーのサイズを調整: 幅={width}")
            return True
        return False
    
    def _show_information_bar(self):
        """インフォメーションバーを表示"""
        if hasattr(self, 'information_bar'):
            # 画像情報を取得してバーに設定
            self._update_information_bar_text()
            self.information_bar.show_bar()
            # 隠すタイマーをリセット
            self.information_bar._hide_timer.stop()
            log_print(DEBUG, "インフォメーションバーを表示リクエスト")
            return True
        return False
    
    def _hide_information_bar(self):
        """インフォメーションバーを非表示"""
        if hasattr(self, 'information_bar') and self.information_bar._visible:
            # 1.5秒後に隠す
            self.information_bar._hide_timer.start(1500)
            return True
        return False
    
    def _adjust_information_size(self, width: int):
        """インフォメーションバーのサイズを調整"""
        if hasattr(self, 'information_bar'):
            # 完全な再配置を行う
            self.information_bar._set_position()
            
            log_print(DEBUG, f"インフォメーションバーのサイズを調整: 幅={width}")
            return True
        return False
    
    def _update_information_bar_text(self):
        """インフォメーションバーの表示テキストを更新"""
        if hasattr(self, 'information_bar'):
            # 画像モデルからステータス情報を取得
            status_msg = self.image_model.get_status_info()
            if status_msg:
                # テキストを更新 (set_info_textではなくinfo_labelに直接設定して再帰を防ぐ)
                if self.information_bar._visible and self.information_bar.isVisible():
                    self.information_bar.info_label.setText(status_msg)
                else:
                    self.information_bar.set_info_text(status_msg)
                log_print(DEBUG, f"インフォメーション更新: {status_msg}")
    
    def _update_status_info(self):
        """ステータスバーに画像情報を表示"""
        status_msg = self.image_model.get_status_info()
        if status_msg:
            self.statusbar.showMessage(status_msg)
            
            # インフォメーションバーのテキストを更新し、常に表示する
            if hasattr(self, 'information_bar'):
                # 新しい情報でインフォメーションバーを常に表示する
                self.information_bar.set_info_text(status_msg)
                # 確実に表示する（非表示になっていても）
                self.information_bar.show_bar()
                log_print(DEBUG, "ステータス更新でインフォメーションバーを表示")
    
    def _update_images_from_browser(self, index: int = None, force_reload: bool = False):
        """
        ブラウザで選択されたインデックスから画像を更新
        
        Args:
            index: 更新するインデックス（Noneの場合は現在のインデックスを使用）
            force_reload: 強制再読み込みするかどうか
        """
        # デバッグ出力
        log_print(INFO, f"画像更新開始: インデックス={index if index is not None else '現在位置'}, 強制再読み込み={force_reload}")
        
        # 画像更新中フラグを設定
        self._is_updating_images = True
        
        try:
            # 更新中フラグが既にセットされているので再設定は不要
            
            if not self._browser:
                log_print(WARNING, "ブラウザが初期化されていません")
                return
            
            # 現在の表示モード（ウィンドウ合わせか原寸大か）を保存
            fit_to_window_mode = self.image_model.is_fit_to_window()
            
            # ブラウザから現在の画像パスを取得
            paths = self._browser.get_current()
            
            # 画像モデルから表示モード情報を取得
            dual_view = self.image_model.is_dual_view()
            right_to_left = self.image_model.is_right_to_left()
            
            log_print(DEBUG, f"ブラウザから取得したパス: {paths}, デュアルモード: {dual_view}")
            log_print(DEBUG, f"現在のブラウザ設定: pages={self._browser._pages}, shift={self._browser._shift}")
            
            # 取得したパスを画像に読み込み
            if paths:
                # ブラウザから取得したパスの数をログ出力
                log_print(DEBUG, f"取得したパス数: {len(paths)}")
                
                # 画像エリアの状態を確認
                log_print(DEBUG, f"画像エリア: len={len(self.image_areas)}, 有効=[{self.image_areas[0] is not None}, {self.image_areas[1] is not None if len(self.image_areas) > 1 else False}]")
                
                if len(paths) == 1:
                    # 1画面の場合は画面中央に表示
                    self.load_image_from_path(paths[0], 0, use_browser_path=True)
                    # 2画面目をクリア（デュアルビュー設定がONでも1画像だけなら2画面目はクリア）
                    if len(self.image_areas) > 1 and self.image_areas[1]:
                        log_print(DEBUG, "2画面目をクリアします（1画像のみ）")
                        self.display_handler.clear_image(1)
                elif len(paths) >= 2 and dual_view:
                    # 2画面の場合（デュアルビューが有効の場合のみ）
                    # 右左設定に応じてインデックスを調整
                    if right_to_left:
                        # 右から左への表示（index 0:右側, 1:左側）
                        self.load_image_from_path(paths[0], 0, use_browser_path=True)
                        self.load_image_from_path(paths[1], 1, use_browser_path=True)
                    else:
                        # 左から右への表示（index 0:左側, 1:右側）
                        self.load_image_from_path(paths[0], 0, use_browser_path=True)
                        self.load_image_from_path(paths[1], 1, use_browser_path=True)
                    
                    log_print(DEBUG, f"デュアルモードで2画像を表示: RTL={right_to_left}")
                else:
                    # デュアルビューが無効または2つ以上のパスがある場合は最初の画像のみ表示
                    self.load_image_from_path(paths[0], 0, use_browser_path=True)
                    if len(self.image_areas) > 1 and self.image_areas[1]:
                        log_print(DEBUG, "2画面目をクリアします（デュアルビュー無効または画像不足）")
                        self.display_handler.clear_image(1)
                
                # 以前の表示モードを引き継ぐ
                # 明示的に表示モードを適用（_refresh_display_modeを使用して一貫性を保つ）
                self._refresh_display_mode(fit_to_window_mode)
                
                # 画像更新時に必ずインフォメーションバーを表示
                self._show_information_bar()
                
                log_print(DEBUG, f"画像更新後の表示モード: fit_to_window={fit_to_window_mode}")
        except Exception as e:
            log_print(ERROR, f"ブラウザからの画像更新に失敗しました: {e}")
            import traceback
            log_print(ERROR, traceback.format_exc())
        finally:
            # 更新完了後、フラグをリセット
            self._is_updating_images = False
            
            # イベントハンドラのロックを解除する確実な場所
            if hasattr(self, 'event_handler') and self.event_handler:
                log_print(INFO, "画像更新完了 - ナビゲーションロックを解除します")
                # 少し待機して確実にフラグを反映してからロック解除
                sleep(0.1)
                self.event_handler.unlock_navigation_events()
            
            # デバッグ出力
            log_print(INFO, "画像更新完了、キー操作を再開します")
    
    def load_image_from_path(self, path: str, index: int = 0, use_browser_path: bool = False) -> bool:
        """
        アーカイブ内の指定パスから画像を読み込む
        
        Args:
            path: 画像ファイルパス
                - use_browser_path=True: ブラウザが返すベースパス相対パス
                - use_browser_path=False: カレントディレクトリからの相対パス
            index: 画像を表示するインデックス（0: 左/単一, 1: 右）
            use_browser_path: パスの解釈方法
                - True: ブラウザパスモード（ベースパス相対、extract_fileを使用）
                - False: ビューモード（カレントディレクトリ相対、extract_itemを使用）
                
        Returns:
            読み込みに成功した場合はTrue、失敗した場合はFalse
        """
        # image_handlerに処理を委譲
        success = self.image_handler.load_image_from_path(path, index, use_browser_path)
        
        if success:
            # ウィンドウタイトルを更新（1画面目のみ）
            if index == 0:
                self.setWindowTitle(f"画像プレビュー - {os.path.basename(path)}")
            
            # 画像情報をステータスバーに表示
            self._update_status_info()
            
            # 画像読み込み後に表示を更新
            self._refresh_display_after_load(index)
            
            # 画像読み込み成功後、ブラウザが未初期化の場合は現在のパスを基準に初期化
            if self.archive_manager and not self._browser:
                try:
                    supported_exts = get_supported_image_extensions()
                    # まずブラウザを初期化
                    self._browser = self.archive_manager.get_browser(
                        exts=supported_exts,
                        pages=self.image_model.get_browser_pages(),
                        shift=self.image_model.is_browser_shift()
                    )
                    # 明示的にパスを指定してジャンプ
                    self._browser.jump(path)
                    log_print(INFO, f"アーカイブブラウザを初期化し、'{path}'へジャンプしました")
                except Exception as e:
                    log_print(ERROR, f"アーカイブブラウザの初期化に失敗しました: {e}")
        return success
    
    def _update_status_info(self):
        """ステータスバーに画像情報を表示"""
        status_msg = self.image_model.get_status_info()
        if status_msg:
            self.statusbar.showMessage(status_msg)
            # インフォメーションバーも同時に更新
            if hasattr(self, 'information_bar') and self.information_bar._visible:
                self.information_bar.set_info_text(status_msg)
    
    def fit_to_window(self):
        """画像をウィンドウに合わせる"""
        # 画像モデルに表示モードを設定
        if self.image_model:
            self.image_model.set_display_mode(True)
            self.image_model.set_zoom_factor(1.0)  # ズーム倍率も明示的にリセット
        
        # 表示ハンドラで実際の表示を更新
        result = self.display_handler.fit_to_window()
        
        # メソッド実行結果を確認してステータスを更新
        if result:
            self.statusbar.showMessage("ウィンドウサイズに合わせました")
            # コンテキストメニューの表示状態を更新
            if hasattr(self, 'context_menu'):
                self.context_menu.update_display_mode(True)
        else:
            self.statusbar.showMessage("表示モード更新失敗")
        
        # デバッグログを追加
        log_print(DEBUG, "fit_to_window メソッドを実行: 画像モデル更新")
        return result
    
    def show_original_size(self):
        """原寸大で表示"""
        # 画像モデルに表示モードを設定
        if self.image_model:
            self.image_model.set_display_mode(False)
            self.image_model.set_zoom_factor(1.0)  # 原寸大は倍率1.0
        
        # 表示ハンドラで実際の表示を更新
        result = self.display_handler.show_original_size()
        
        # メソッド実行結果を確認してステータスを更新
        if result:
            self.statusbar.showMessage("原寸大表示")
            # コンテキストメニューの表示状態を更新
            if hasattr(self, 'context_menu'):
                self.context_menu.update_display_mode(False)
        else:
            self.statusbar.showMessage("表示モード更新失敗")
        
        return result
    
    def rotate_left(self):
        """画像を左に90度回転"""
        self.statusbar.showMessage("左に回転（未実装）")
    
    def rotate_right(self):
        """画像を右に90度回転"""
        self.statusbar.showMessage("右に回転（未実装）")
    
    def save_image_as(self):
        """画像を別名で保存"""
        self.statusbar.showMessage("名前を付けて保存（未実装）")
    
    def copy_to_clipboard(self):
        """クリップボードに画像をコピー"""
        self.statusbar.showMessage("クリップボードにコピー（未実装）")
    
    def toggle_dual_view(self):
        """デュアルビューの切り替え"""
        # 現在の状態を画像モデルから取得
        dual_view = self.image_model.is_dual_view()
        right_to_left = self.image_model.is_right_to_left()
        browser_shift = self.image_model.is_browser_shift()
        
        # デュアルモードとシングルモード間の切り替え
        if dual_view:
            # デュアルモードからシングルモードへ
            self.set_view_mode("single")
        else:
            # シングルモードからデュアルモードへ（左右設定を保持）
            if browser_shift:
                if right_to_left:
                    self.set_view_mode("dual_rl_shift")
                else:
                    self.set_view_mode("dual_lr_shift")
            else:
                if right_to_left:
                    self.set_view_mode("dual_rl")
                else:
                    self.set_view_mode("dual_lr")
        
        return True
    
    def toggle_shift_mode(self):
        """シフトモードの切り替え"""
        # 現在の状態を画像モデルから取得
        dual_view = self.image_model.is_dual_view()
        right_to_left = self.image_model.is_right_to_left()
        browser_shift = self.image_model.is_browser_shift()
        
        # シフトモードの切り替え（他の設定は保持）
        if browser_shift:
            # シフトオンからオフへ
            if dual_view:
                if right_to_left:
                    self.set_view_mode("dual_rl")
                else:
                    self.set_view_mode("dual_lr")
            else:
                self.set_view_mode("single")
        else:
            # シフトオフからオンへ
            if dual_view:
                if right_to_left:
                    self.set_view_mode("dual_rl_shift")
                else:
                    self.set_view_mode("dual_lr_shift")
            else:
                # シングルモードでシフトを有効にするのは意味がないので無視
                pass
        
        return True
    
    def set_view_mode(self, mode: str):
        """
        表示モードを設定
        
        Args:
            mode: 表示モード
                - "single": シングルモード
                - "dual_rl": デュアルモード（右左）
                - "dual_lr": デュアルモード（左右）
                - "dual_rl_shift": デュアルモード（右左シフト）
                - "dual_lr_shift": デュアルモード（左右シフト）
        """
        # DisplayHandlerに処理を委譲
        return self.display_handler.set_view_mode(mode, self)

    def _refresh_display_mode(self, fit_to_window: bool = True):
        """現在の表示モードを再適用して表示を更新する"""
        # DisplayHandlerに処理を委譲
        self.display_handler.refresh_display_mode(fit_to_window)

    def show_image_info(self):
        """画像の詳細情報を表示する"""
        has_info = False
        
        # 左側画像の情報
        info_text = ""
        left_info = self.display_handler.get_image_info(0)
        if left_info:
            has_info = True
            info_text += f"左画像: {format_image_info(left_info)}"
        
        # 右側画像の情報（デュアルビューの場合）
        right_info = self.display_handler.get_image_info(1)
        if self.image_model.is_dual_view() and right_info:
            has_info = True
            if info_text:
                info_text += "\n\n"
            info_text += f"右画像: {format_image_info(right_info)}"
        
        if not has_info:
            self.statusbar.showMessage("画像情報がありません")
            return
        
        # 情報表示（現在はログ出力のみ）
        self.statusbar.showMessage("画像情報を表示しました")
        log_print(INFO, f"画像情報: \n{info_text}")
    
    # イベント処理方法
    def keyPressEvent(self, event: QKeyEvent):
        """キーが押されたときのイベント処理"""
        # 画像更新中はイベントを無視（すべてのキーを無視）
        if self._is_updating_images:
            log_print(DEBUG, f"画像更新中のため、キーイベントをウィンドウレベルでブロック: キーコード {event.key()}")
            event.accept()  # イベントを処理済みとしてマーク
            return
        
        # イベントハンドラに処理を委譲
        if not self.event_handler.handle_key_press(event):
            # 処理されなかった場合は親クラスに渡す
            super().keyPressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """マウス移動イベント処理"""
        # イベントハンドラに処理を委譲
        if not self.event_handler.handle_mouse_move(event, self.height()):
            # 処理されなかった場合は親クラスに渡すt
            super().mouseMoveEvent(event)
    
    def contextMenuEvent(self, event: QContextMenuEvent):
        """コンテキストメニューイベント処理"""
        # イベントハンドラに処理を委譲
        if not self.event_handler.handle_context_menu(event):
            # 処理されなかった場合は親クラスに渡す
            super().contextMenuEvent(event)
    
    def wheelEvent(self, event: QWheelEvent):
        """マウスホイールイベント処理"""
        # イベントハンドラに処理を委譲
        if not self.event_handler.handle_wheel(event):
            # 処理されなかった場合は親クラスに渡す
            super().wheelEvent(event)
    
    def resizeEvent(self, event: QResizeEvent):
        """リサイズイベント処理"""
        # イベントハンドラでナビゲーションバーとインフォメーションバーのサイズを調整
        self.event_handler.handle_resize(self.width())
        
        # ナビゲーションバーの位置も調整
        if hasattr(self, 'navigation_bar') and self.navigation_bar._visible:
            self.navigation_bar._set_position()
        
        # インフォメーションバーの位置も調整
        if hasattr(self, 'information_bar') and self.information_bar._visible:
            self.information_bar._set_position()
        
        # 基底クラスの処理も呼び出す
        super().resizeEvent(event)
    
    def _on_prev_image(self):
        """前の画像に移動"""
        if self._is_updating_images:
            log_print(DEBUG, "画像更新中のため、移動イベントをブロック")
            return True
        if self._browser:
            try:
                path = self._browser.prev()
                self.statusbar.showMessage(f"前の画像に移動: {path}")
                # 更新前に現在のパス情報をログ出力
                log_print(DEBUG, f"前の画像への移動: {path}, 現在のブラウザ状態: pages={self._browser._pages}, shift={self._browser._shift}")
                self._update_images_from_browser()
                # 画像移動時に必ずインフォメーションバーを表示（_update_images_from_browserに含まれている場合は不要）
                # self._show_information_bar()
                return True
            except Exception as e:
                log_print(ERROR, f"前の画像への移動に失敗しました: {e}")
                self.statusbar.showMessage("前の画像への移動に失敗しました")
        return False
    
    def _on_next_image(self):
        """次の画像に移動"""
        if self._is_updating_images:
            log_print(DEBUG, "画像更新中のため、移動イベントをブロック")
            return True
        if self._browser:
            try:
                path = self._browser.next()
                self.statusbar.showMessage(f"次の画像に移動: {path}")
                # 更新前に現在のパス情報をログ出力
                log_print(DEBUG, f"次の画像への移動: {path}, 現在のブラウザ状態: pages={self._browser._pages}, shift={self._browser._shift}")
                
                # ナビゲーション中のロック状態をログ出力
                if hasattr(self, 'event_handler'):
                    locked = self.event_handler.is_navigation_locked()
                    in_progress = self.event_handler._navigation_in_progress
                    signals_connected = self.event_handler._navigation_signals_connected
                    log_print(DEBUG, f"ナビゲーション状態: ロック中={locked}, 処理中={in_progress}, シグナル接続={signals_connected}")
                
                # 画像更新
                self._update_images_from_browser()
                return True
            except Exception as e:
                log_print(ERROR, f"次の画像への移動に失敗しました: {e}")
                self.statusbar.showMessage("次の画像への移動に失敗しました")
                # エラー発生時も確実にロックを解除
                if hasattr(self, 'event_handler'):
                    self.event_handler.unlock_navigation_events()
        return False
    
    def _on_first_image(self):
        """最初の画像に移動"""
        if self._is_updating_images:
            log_print(DEBUG, "画像更新中のため、移動イベントをブロック")
            return True
        if self._browser:
            try:
                path = self._browser.go_first()
                self.statusbar.showMessage(f"最初の画像に移動: {path}")
                self._update_images_from_browser()
                return True
            except Exception as e:
                log_print(ERROR, f"最初の画像への移動に失敗しました: {e}")
                self.statusbar.showMessage("最初の画像への移動に失敗しました")
        return False
    
    def _on_last_image(self):
        """最後の画像に移動"""
        if self._is_updating_images:
            log_print(DEBUG, "画像更新中のため、移動イベントをブロック")
            return True
        if self._browser:
            try:
                path = self._browser.go_last()
                self.statusbar.showMessage(f"最後の画像に移動: {path}")
                self._update_images_from_browser()
                return True
            except Exception as e:
                log_print(ERROR, f"最後の画像への移動に失敗しました: {e}")
                self.statusbar.showMessage("最後の画像への移動に失敗しました")
        return False
    
    def _on_prev_folder(self):
        """前のフォルダに移動"""
        if self._is_updating_images:
            log_print(DEBUG, "画像更新中のため、フォルダ移動イベントをブロック")
            return True
        if self._browser:
            try:
                path = self._browser.prev_folder()
                self.statusbar.showMessage(f"前のフォルダに移動: {path}")
                self._update_images_from_browser()
                return True
            except Exception as e:
                log_print(ERROR, f"前のフォルダへの移動に失敗しました: {e}")
                self.statusbar.showMessage("前のフォルダへの移動に失敗しました")
        return False
    
    def _on_next_folder(self):
        """次のフォルダに移動"""
        if self._is_updating_images:
            log_print(DEBUG, "画像更新中のため、フォルダ移動イベントをブロック")
            return True
        if self._browser:
            try:
                path = self._browser.next_folder()
                self.statusbar.showMessage(f"次のフォルダに移動: {path}")
                self._update_images_from_browser()
                return True
            except Exception as e:
                log_print(ERROR, f"次のフォルダへの移動に失敗しました: {e}")
                self.statusbar.showMessage("次のフォルダへの移動に失敗しました")
        return False

    def _on_first_folder_image(self):
        """フォルダ内の先頭画像に移動"""
        if self._is_updating_images:
            log_print(DEBUG, "画像更新中のため、移動イベントをブロック")
            return True
        if self._browser:
            try:
                path = self._browser.go_top()
                self.statusbar.showMessage(f"フォルダ内の先頭画像に移動: {path}")
                self._update_images_from_browser()
                return True
            except Exception as e:
                log_print(ERROR, f"フォルダ内の先頭画像への移動に失敗しました: {e}")
                self.statusbar.showMessage("フォルダ内の先頭画像への移動に失敗しました")
        return False

    def _on_last_folder_image(self):
        """フォルダ内の最後の画像に移動"""
        if self._is_updating_images:
            log_print(DEBUG, "画像更新中のため、移動イベントをブロック")
            return True
        if self._browser:
            try:
                path = self._browser.go_end()
                self.statusbar.showMessage(f"フォルダ内の最後の画像に移動: {path}")
                self._update_images_from_browser()
                return True
            except Exception as e:
                log_print(ERROR, f"フォルダ内の最後の画像への移動に失敗しました: {e}")
                self.statusbar.showMessage("フォルダ内の最後の画像への移動に失敗しました")
        return False

    def _on_toggle_fullscreen(self):
        """フルスクリーンモードの切り替え"""
        # フルスクリーン切り替え時に、もしナビゲーションロックがあれば解除する
        if hasattr(self, 'event_handler') and self.event_handler:
            # ナビゲーション処理中フラグをリセット（念のため）
            self.event_handler._navigation_in_progress = False
            
            # ロックされている場合のみ解除（不要なシグナル解除を防止）
            if self.event_handler.is_navigation_locked():
                log_print(INFO, "フルスクリーン切り替え時にナビゲーションロックを解除します")
                self.event_handler.unlock_navigation_events()

        if self.isFullScreen():
            self.showNormal()
            self.statusbar.showMessage("ウィンドウモードに戻りました")
        else:
            self.showFullScreen()
            self.statusbar.showMessage("フルスクリーンモードに切り替えました")
        
        # フルスクリーン切り替え後にナビゲーションバーとインフォメーションバーの位置を再調整
        # 遅延を少し長めに設定して、ウィンドウのリサイズが完全に終わった後に実行
        QTimer.singleShot(300, self._adjust_bars)
        
        return True

    def _adjust_bars(self):
        """ナビゲーションバーとインフォメーションバーのサイズと位置を調整"""
        # ナビゲーションバーの調整
        self._adjust_navigation_size(self.width())
        
        # インフォメーションバーの調整
        if hasattr(self, 'information_bar'):
            # インフォメーションバーの位置を再設定
            self.information_bar._set_position()
            
            if self.information_bar._visible:
                # 必要に応じて追加の調整を行う
                pass
            
            log_print(DEBUG, f"インフォメーションバーの位置を調整しました（ウィンドウサイズ: {self.width()}x{self.height()}）")

    def eventFilter(self, watched, event):
        """イベントフィルタ - フォーカスやキーイベントをデバッグ出力"""
        if event.type() == QEvent.FocusIn:
            log_print(DEBUG, f"フォーカスイン: {watched}")
        elif event.type() == QEvent.FocusOut:
            log_print(DEBUG, f"フォーカスアウト: {watched}")
        elif event.type() == QEvent.KeyPress:
            log_print(DEBUG, f"キープレスイベント: {event.key()}, ウィジェット: {watched}")
        
        # イベントを通常通り処理
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        """ウィンドウ表示時のイベント処理"""
        super().showEvent(event)
        # 確実にフォーカスを取得
        self.setFocus()
        self.activateWindow()
        # デバッグ出力
        log_print(INFO, "プレビューウィンドウが表示され、フォーカスを取得しました")

    def closeEvent(self, event):
        """ウィンドウが閉じられる際のイベント処理"""
        try:
            # 超解像処理のキャンセル処理
            log_print(INFO, "プレビューウィンドウが閉じられます。超解像処理をキャンセルします。")
            
            # ナビゲーションバーとインフォメーションバーのタイマーを停止
            if hasattr(self, 'navigation_bar') and self.navigation_bar:
                # 隠すタイマーを停止
                self.navigation_bar._hide_timer.stop()
                # マウス位置チェックタイマーを停止
                if hasattr(self.navigation_bar, '_check_mouse_timer') and self.navigation_bar._check_mouse_timer:
                    self.navigation_bar._check_mouse_timer.stop()
                log_print(DEBUG, "ナビゲーションバーのタイマーを停止しました")
                
            if hasattr(self, 'information_bar') and self.information_bar:
                # 隠すタイマーを停止
                self.information_bar._hide_timer.stop()
                # マウス位置チェックタイマーを停止
                if hasattr(self.information_bar, '_check_mouse_timer') and self.information_bar._check_mouse_timer:
                    self.information_bar._check_mouse_timer.stop()
                log_print(DEBUG, "インフォメーションバーのタイマーを停止しました")
            
            # 実行中の超解像処理をキャンセル
            if hasattr(self, 'image_model') and self.image_model:
                # 各画像の超解像リクエストをチェック
                for index in [0, 1]:
                    if self.image_model.has_sr_request(index):
                        request_id = self.image_model.get_sr_request(index)
                        if request_id:
                            log_print(INFO, f"超解像リクエスト {request_id} をキャンセルします")
                            
                            # 画像ハンドラがあればキャンセル処理を委譲
                            if hasattr(self, 'image_handler') and self.image_handler:
                                self.image_handler.cancel_superres_request(index)
                            # 直接sr_managerにアクセス
                            elif hasattr(self, 'sr_manager') and self.sr_manager:
                                self.sr_manager.cancel_superres(request_id)
                                self.image_model.set_sr_request(index, None)
            
            # 基底クラスのcloseEventを呼び出し
            super().closeEvent(event)
            
        except Exception as e:
            # 例外が発生してもウィンドウは閉じる
            log_print(ERROR, f"ウィンドウを閉じる際に例外が発生しました: {e}")
            import traceback
            log_print(DEBUG, traceback.format_exc())
            
            # 基底クラスのcloseEventを呼び出し
            super().closeEvent(event)

    def _on_superres(self):
        """超解像処理の実行"""
        # 親ウィンドウのimage_handlerがあるかどうか確認
        success = self.image_handler.run_superres()
        if success:
            log_print(INFO, "超解像処理を開始しました")
        else:
            log_print(ERROR, "超解像処理の実行に失敗しました")

    def _refresh_display_after_superres(self, index: int):
        """超解像処理完了後に表示を更新"""
        # 画像モデルから表示更新フラグをチェックして更新
        if hasattr(self, 'display_handler') and self.display_handler:
            # display_handlerに処理を委譲
            self.display_handler.check_model_updates()
            
            # ステータス表示も更新
            self._update_status_info()
            log_print(DEBUG, f"超解像処理完了後に表示を更新しました: index={index}")

    def _refresh_display_after_load(self, index: int):
        """画像読み込み後に表示を更新"""
        # 画像モデルから表示更新フラグをチェックして更新
        if hasattr(self, 'display_handler') and self.display_handler:
            # 画像読み込み後のエラーチェック処理
            if hasattr(self, 'image_model'):
                error_info = self.image_model.get_error_info(index)
                if error_info and index < len(self.image_areas) and self.image_areas[index]:
                    try:
                        # エラー情報がある場合はエラーメッセージを表示
                        error_message = error_info.get('message', "画像を読み込めませんでした")
                        path = error_info.get('path', "")
                        filename = os.path.basename(path) if path else ""
                        
                        # ファイル名を添えたエラーメッセージ
                        display_message = f"{error_message}\n\n{filename}" if filename else error_message
                        
                        area = self.image_areas[index]
                        area._current_pixmap = None
                        area.image_label.setText(display_message)
                        area.image_label.setStyleSheet("color: white; background-color: black; font-size: 14px;")
                        area.image_label.setAlignment(Qt.AlignCenter)
                        area.image_label.setPixmap(QPixmap())  # 空のピクスマップを明示的にセット
                        
                        log_print(INFO, f"画像読み込みエラーを表示: {error_message} (ファイル: {filename})")
                        
                        # エラー表示後は更新フラグをクリア
                        self.image_model.clear_display_update_flag(index)
                    except Exception as e:
                        log_print(ERROR, f"エラー表示中にエラーが発生: {e}")
            
            # エラーがない場合は通常の表示更新処理
            self.display_handler.check_model_updates()
            
            # ステータス表示も更新
            self._update_status_info()
            log_print(DEBUG, f"読み込み後に表示を更新しました: index={index}")

    def _show_context_menu(self, pos):
        """コンテキストメニューを表示"""
        if hasattr(self, 'context_menu'):
            self.context_menu.popup(pos)
            return True
        return False

# 単体テスト用のコード
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # テスト用のパラメータ処理
    dual_view = False 
    if len(sys.argv) > 1 and sys.argv[1].lower() == "dual":
        dual_view = True
    
    # アーカイブマネージャーなしでプレビューウィンドウ作成
    window = ImagePreviewWindow(dual_view=dual_view)
    window.show()
    
    sys.exit(app.exec())
