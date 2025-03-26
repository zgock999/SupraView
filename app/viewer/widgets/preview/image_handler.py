"""
画像ハンドラモジュール

プレビューウィンドウのイメージ読み込みと表示に関する処理を管理
"""

import os
import sys
from typing import Optional, Dict, Any, List, Tuple

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logutils import log_print, INFO, WARNING, ERROR, DEBUG, CRITICAL

try:
    from PySide6.QtWidgets import QScrollArea, QLabel
    from PySide6.QtCore import Qt, QSize, QTimer
    from PySide6.QtGui import QPixmap, QImage
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)

# 内部モジュールをインポート
from .image_processor import load_image_from_bytes, format_image_info
# 画像モデルをインポート
from .image_model import ImageModel
# 直接decoderモジュールからインポート
from decoder.interface import get_supported_image_extensions


class ImageHandler:
    """画像ファイルの読み込みと表示を管理するクラス"""
    
    # サポートする画像形式の拡張子を直接decoderから取得
    SUPPORTED_EXTENSIONS = get_supported_image_extensions()
    
    def __init__(self, parent=None, archive_manager=None, image_model=None):
        """
        画像ハンドラの初期化
        
        Args:
            parent: 親ウィジェット（主にステータスバーメッセージ表示用）
            archive_manager: 画像データを取得するためのアーカイブマネージャ
            image_model: 画像情報を管理するモデル
        """
        self.parent = parent
        self.archive_manager = archive_manager
        self.image_model = image_model
        
        # 画像表示エリアの参照を保存
        self.image_areas = []
        
        log_print(DEBUG, f"ImageHandler: 初期化完了 (モデル参照: {self.image_model is not None})")
    
    def setup_image_areas(self, image_areas: List[QScrollArea]):
        """
        画像表示エリアを設定
        
        Args:
            image_areas: 画像表示用のスクロールエリアのリスト
        """
        self.image_areas = image_areas
        log_print(DEBUG, f"画像表示エリアを設定: {len(image_areas)}個")
        
        # 既存の画像データがあれば表示を更新
        self._update_display_from_model()
    
    def _update_display_from_model(self):
        """画像モデルから画像データを取得して表示を更新"""
        if not self.image_model:
            return
            
        # 画像モデルから表示モード情報を取得
        fit_to_window_mode = self.image_model.is_fit_to_window()
        zoom_factor = self.image_model.get_zoom_factor()
            
        # モデルに画像データが存在するか確認
        for index in [0, 1]:
            if self.image_model.has_image(index):
                pixmap = self.image_model.get_pixmap(index)
                if pixmap and index < len(self.image_areas) and self.image_areas[index]:
                    # 表示エリアに画像と表示モードを設定
                    self._set_image_to_area(pixmap, index)
                    
                    # 表示モードも明示的に設定
                    if hasattr(self.image_areas[index], 'set_fit_to_window'):
                        self.image_areas[index].set_fit_to_window(fit_to_window_mode)
                        
                        # 非fit_to_windowモードの場合はズーム倍率も設定
                        if not fit_to_window_mode and hasattr(self.image_areas[index], 'set_zoom'):
                            self.image_areas[index].set_zoom(zoom_factor)
                    
                    log_print(DEBUG, f"画像データをモデルから復元: index={index}, fit={fit_to_window_mode}")
                    
        log_print(DEBUG, "画面表示を画像モデルと同期しました")
    
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
        if not self.archive_manager:
            log_print(ERROR, "アーカイブマネージャが設定されていません")
            self._show_status_message("エラー: アーカイブマネージャが設定されていません")
            return False
        
        # インデックスの範囲を確認
        if index not in [0, 1] or (index == 1 and (len(self.image_areas) < 2 or self.image_areas[1] is None)):
            log_print(ERROR, f"無効なインデックス: {index}")
            return False
        
        try:
            # ファイル名から拡張子を取得
            _, ext = os.path.splitext(path.lower())
            
            # デバッグ出力を追加
            log_print(DEBUG, f"ファイル拡張子: {ext}, サポートされている拡張子: {self.SUPPORTED_EXTENSIONS}")
            
            # 拡張子チェックを修正 - すべて小文字化して比較
            supported_exts_lower = [e.lower() for e in self.SUPPORTED_EXTENSIONS]
            if ext.lower() not in supported_exts_lower:
                log_print(WARNING, f"サポートされていない画像形式です: {ext}")
                self._show_status_message(f"サポートされていない画像形式です: {ext}")
                return False
            
            # パスの解釈に基づいて適切なメソッドで画像データを取得
            if use_browser_path:
                # ブラウザから取得したパスの場合はextract_fileを使用
                log_print(INFO, f"ブラウザパスから画像を読み込み中: {path}")
                image_data = self.archive_manager.extract_file(path)
            else:
                # カレントディレクトリ相対パスの場合はextract_itemを使用
                log_print(INFO, f"ディレクトリ相対パスから画像を読み込み中: {path}")
                image_data = self.archive_manager.extract_item(path)
            
            if not image_data:
                log_print(ERROR, f"画像データの読み込みに失敗しました: {path}")
                self._show_status_message(f"画像データの読み込みに失敗しました: {path}")
                return False
            
            # 画像処理モジュールを使用して画像を読み込み
            pixmap, numpy_array, info = load_image_from_bytes(image_data, path)
            
            if pixmap is None:
                log_print(ERROR, f"画像の表示に失敗しました: {path}")
                self._show_status_message(f"画像の表示に失敗しました: {path}")
                return False
            
            # 画像モデルに画像情報を設定
            if self.image_model:
                self.image_model.set_image(index, pixmap, image_data, numpy_array, info, path)
                # モデルの表示モードは変更せず、現状を維持
            
            # 画像を表示
            self._set_image_to_area(pixmap, index)
            
            # 画像表示エリアにも現在のフィットモードを適用
            if index < len(self.image_areas) and self.image_areas[index]:
                area = self.image_areas[index]
                if hasattr(area, 'set_fit_to_window') and self.image_model:
                    # モデルから現在のモード値を取得
                    fit_mode = self.image_model.is_fit_to_window()
                    area.set_fit_to_window(fit_mode)
                    # 表示エリアで明示的に表示を更新
                    if hasattr(area, '_adjust_image_size'):
                        log_print(DEBUG, f"表示エリア {index} で現在のモードを適用: fit={fit_mode}: {path}")
                        area._adjust_image_size()
            
            # 画像情報をステータスバーに表示
            self._update_status_info()
            
            return True
            
        except Exception as e:
            log_print(ERROR, f"画像の読み込み中にエラーが発生しました: {e}")
            self._show_status_message(f"エラー: {str(e)}")
            import traceback
            log_print(DEBUG, traceback.format_exc())
            return False
    
    def _set_image_to_area(self, pixmap: QPixmap, index: int):
        """
        指定されたインデックスの表示エリアに画像を設定
        
        Args:
            pixmap: 表示する画像
            index: 表示エリアのインデックス
        """
        # インデックスの範囲チェック
        if index not in [0, 1] or index >= len(self.image_areas) or self.image_areas[index] is None:
            log_print(ERROR, f"無効な表示エリアインデックス: {index}")
            return
        
        # QPixmapを表示エリアに設定
        scroll_area = self.image_areas[index]
        
        # 表示ラベルが無い場合は作成
        if not hasattr(scroll_area, 'image_label'):
            scroll_area.image_label = QLabel()
            scroll_area.image_label.setAlignment(Qt.AlignCenter)
            scroll_area.setWidget(scroll_area.image_label)
        
        # 画像エリアの_current_pixmapも更新
        if hasattr(scroll_area, '_current_pixmap'):
            scroll_area._current_pixmap = pixmap
        
        # QPixmapを設定
        scroll_area.image_label.setPixmap(pixmap)
        scroll_area.image_label.adjustSize()
        
        # 表示モードに応じて明示的に表示を更新
        if hasattr(scroll_area, '_adjust_image_size'):
            scroll_area._adjust_image_size()
            log_print(DEBUG, f"画像エリア {index} の表示を更新")
    
    def clear_image(self, index: int):
        """
        指定されたインデックスの画像表示をクリア
        
        Args:
            index: クリアする画像のインデックス
        """
        # インデックスの範囲チェック
        if index not in [0, 1] or index >= len(self.image_areas) or self.image_areas[index] is None:
            log_print(ERROR, f"無効な表示エリアインデックス: {index}")
            return
        
        # 表示をクリア
        scroll_area = self.image_areas[index]
        if hasattr(scroll_area, 'image_label'):
            scroll_area.image_label.clear()
            scroll_area.image_label.setText("画像なし")
        
        # モデル内の画像情報もクリア
        if self.image_model:
            self.image_model.clear_image(index)
    
    def get_image_info(self, index: int) -> Dict[str, Any]:
        """
        指定されたインデックスの画像情報を取得
        
        Args:
            index: 画像のインデックス
            
        Returns:
            画像情報の辞書（情報がない場合は空の辞書）
        """
        if self.image_model:
            return self.image_model.get_info(index)
        return {}
    
    def get_status_info(self) -> str:
        """
        ステータスバー表示用の画像情報を取得
        
        Returns:
            表示用の画像情報文字列
        """
        if self.image_model:
            return self.image_model.get_status_info()
        return ""
    
    def _update_status_info(self):
        """ステータスバーに画像情報を表示"""
        status_msg = self.get_status_info()
        if status_msg and self.parent and hasattr(self.parent, 'statusbar'):
            self.parent.statusbar.showMessage(status_msg)
    
    def _show_status_message(self, message: str):
        """ステータスバーにメッセージを表示"""
        if self.parent and hasattr(self.parent, 'statusbar'):
            self.parent.statusbar.showMessage(message)
    
    def set_archive_manager(self, archive_manager):
        """
        アーカイブマネージャを設定
        
        Args:
            archive_manager: 画像データを取得するためのアーカイブマネージャ
        """
        self.archive_manager = archive_manager
        log_print(INFO, "アーカイブマネージャを設定しました")
    
    def set_image_model(self, image_model: ImageModel):
        """
        画像モデルを設定
        
        Args:
            image_model: 画像情報を管理するモデル
        """
        self.image_model = image_model
        log_print(INFO, "画像モデルを設定しました")
        # 既存の画像データがあれば表示を更新
        self._update_display_from_model()
    
    def is_image_loaded(self, index: int) -> bool:
        """
        指定されたインデックスに画像が読み込まれているかを確認
        
        Args:
            index: 確認する画像のインデックス
            
        Returns:
            画像が読み込まれている場合はTrue
        """
        if self.image_model:
            return self.image_model.has_image(index)
        return False
