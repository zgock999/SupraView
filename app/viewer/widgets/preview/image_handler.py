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
        
        # 超解像マネージャへの参照（初期はNone）
        self.sr_manager = None
        
        # 超解像処理の遅延リクエスト用タイマー
        self.sr_delay_timer = QTimer()
        self.sr_delay_timer.setSingleShot(True)
        self.sr_delay_timer.setInterval(100)  # 100ms遅延
        self.sr_delay_timer.timeout.connect(self._process_delayed_superres)
        
        # 遅延リクエスト用のキュー
        self._delayed_sr_requests = {}  # {index: current_path}
        
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
            # 画像情報をフォーマット
            if pixmap is None:
                log_print(ERROR, f"画像の表示に失敗しました: {path}")
                self._show_status_message(f"画像の表示に失敗しました: {path}")
                return False
            
            # 画像モデルに画像情報を設定
            if self.image_model:
                self.image_model.set_image(index, pixmap, image_data, numpy_array, info, path)
                # モデルの表示モードは変更せず、現状を維持
                
                # 既存のリクエストがあればキャンセル
                if self.sr_manager and self.image_model.has_sr_request(index):
                    old_request_id = self.image_model.get_sr_request(index)
                    if old_request_id:
                        self.sr_manager.cancel_superres(old_request_id)
                        log_print(DEBUG, f"既存の超解像リクエスト {old_request_id} をキャンセルしました")
                
                # 超解像処理のリクエスト - 自動処理が有効な場合は遅延リクエスト
                if self.sr_manager and numpy_array is not None and self.sr_manager.auto_process:
                    # 遅延リクエストを登録（現在のパスを記録）
                    self._schedule_delayed_superres(index, path)
            
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
    
    def _schedule_delayed_superres(self, index: int, path: str):
        """
        超解像処理リクエストを遅延スケジュールする（画像切り替え時の連続リクエスト防止）
        
        Args:
            index: 画像インデックス
            path: 画像パス
        """
        # 現在のリクエストを記録
        self._delayed_sr_requests[index] = path
        log_print(DEBUG, f"超解像処理の遅延リクエストを登録: index={index}, path={os.path.basename(path)}")
        
        # 遅延タイマーを開始（すでに開始されている場合は再起動）
        self.sr_delay_timer.start()
    
    def _process_delayed_superres(self):
        """
        遅延リクエストされた超解像処理を実行する（タイマーコールバック）
        画像が同じままであれば処理を実行、そうでなければスキップする
        """
        # 登録されていたリクエストを処理
        for index, path in list(self._delayed_sr_requests.items()):
            # 現在の画像パスを取得
            current_path = None
            if self.image_model and self.image_model.has_image(index):
                current_path = self.image_model.get_path(index)
            
            # 画像パスが変わっていなければ超解像処理を実行
            if current_path and current_path == path:
                log_print(DEBUG, f"遅延された超解像処理を実行: index={index}, path={os.path.basename(path)}")
                self._process_single_image(index)
            else:
                log_print(DEBUG, f"画像が変更されたため超解像処理をスキップ: index={index}, "
                               f"requested={os.path.basename(path)}, current={os.path.basename(current_path) if current_path else 'None'}")
        
        # 処理済みのリクエストをクリア
        self._delayed_sr_requests.clear()
    
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
    
    def set_superres_manager(self, sr_manager):
        """
        超解像処理マネージャを設定
        
        Args:
            sr_manager: 超解像処理を行うマネージャ（EnhancedSRManager）
        """
        self.sr_manager = sr_manager
        log_print(INFO, "超解像処理マネージャを設定しました")
        
    def cancel_superres_request(self, index: int) -> bool:
        """
        指定インデックスの超解像処理リクエストをキャンセル
        
        Args:
            index: 画像インデックス
            
        Returns:
            bool: キャンセルに成功したかどうか
        """
        if not self.sr_manager or not self.image_model:
            return False
            
        # リクエストIDを取得
        request_id = self.image_model.get_sr_request(index)
        if not request_id:
            return False
            
        # 超解像処理をキャンセル
        success = self.sr_manager.cancel_superres(request_id)
        
        # 成功したらモデルからリクエストIDをクリア
        if success:
            self.image_model.set_sr_request(index, None)
            log_print(INFO, f"超解像処理リクエスト {request_id} をキャンセルしました")
            
        return success
    
    def run_superres(self, index: int = None) -> bool:
        """
        手動で超解像処理を実行
        
        Args:
            index: 処理する画像のインデックス（Noneの場合、モードに応じて自動選択）
            
        Returns:
            bool: 処理リクエストに成功したかどうか
        """
        # 必要なコンポーネントの存在確認
        if not self.sr_manager or not self.image_model:
            log_print(ERROR, "超解像処理マネージャまたは画像モデルが設定されていません")
            self._show_status_message("超解像処理の準備ができていません")
            return False
        
        # 遅延リクエストをキャンセル（手動実行が優先）
        if self.sr_delay_timer.isActive():
            self.sr_delay_timer.stop()
        self._delayed_sr_requests.clear()
        
        # インデックスが指定されていない場合、現在のモードに応じて処理対象を決定
        if index is None:
            # デュアルモードかどうかをチェック
            is_dual_mode = False
            if hasattr(self.image_model, 'is_dual_view'):
                is_dual_mode = self.image_model.is_dual_view()
            
            if is_dual_mode:
                # デュアルモードの場合は両方の画像を処理
                log_print(INFO, "デュアルモード: 両方の画像に対して超解像処理を実行します")
                
                # 両方の画像にそれぞれ超解像処理を実行（少なくとも1つ成功すればTrueを返す）
                success1 = self._process_single_image(0)
                success2 = self._process_single_image(1)
                
                return success1 or success2
            else:
                # シングルモードの場合は画像0のみを処理
                log_print(INFO, "シングルモード: 画像0に対して超解像処理を実行します")
                return self._process_single_image(0)
        else:
            # インデックスが指定されている場合は、その画像のみを処理
            log_print(INFO, f"指定されたインデックス {index} の画像に対して超解像処理を実行します")
            return self._process_single_image(index)
    
    def _process_single_image(self, index: int) -> bool:
        """
        指定インデックスの画像に対して超解像処理を実行
        
        Args:
            index: 処理する画像のインデックス
            
        Returns:
            bool: 処理リクエストに成功したかどうか
        """
        # 画像が読み込まれているか確認
        if not self.image_model.has_image(index):
            log_print(ERROR, f"インデックス {index} に画像が読み込まれていません")
            self._show_status_message("処理する画像がありません")
            return False
        
        # NumPy配列形式の画像データを取得
        _, _, numpy_array, _, path = self.image_model.get_image(index)
        
        if numpy_array is None:
            log_print(ERROR, f"画像データが無効です: {path}")
            self._show_status_message("画像データが処理できない形式です")
            return False
        
        # 既存のリクエストがあればキャンセル
        if self.image_model.has_sr_request(index):
            old_request_id = self.image_model.get_sr_request(index)
            if old_request_id:
                self.sr_manager.cancel_superres(old_request_id)
                log_print(DEBUG, f"既存の超解像リクエスト {old_request_id} をキャンセルしました")
        
        # 処理状態をユーザーに通知
        filename = os.path.basename(path)
        self._show_status_message(f"超解像処理を開始しています: {filename}...")
        
        # 超解像処理用のコールバックを定義
        def on_superres_completed(request_id, processed_array):
            """超解像処理完了時のコールバック"""
            try:
                # 対応するリクエストIDがどの画像に関連するか確認
                current_request_id = self.image_model.get_sr_request(index)
                
                # 現在の画像とリクエストIDが一致するかチェック
                target_index = index
                if current_request_id == request_id:
                    # リクエストIDが一致する場合は通常通り処理
                    log_print(INFO, f"画像 {index} の超解像処理が完了しました: {request_id}")
                else:
                    # 一致しない場合、もう一方の画像をチェック（デュアルビューの場合）
                    other_index = 1 if index == 0 else 0
                    other_request_id = self.image_model.get_sr_request(other_index)
                    
                    if other_request_id == request_id:
                        # もう一方の画像のリクエストと一致した場合は、インデックスを切り替え
                        log_print(INFO, f"もう一方の画像 {other_index} の超解像処理が完了しました: {request_id}")
                        target_index = other_index
                    else:
                        # どちらの画像とも一致しない場合（古いリクエストなど）
                        log_print(WARNING, f"リクエストIDが一致しません: current={current_request_id}, other={other_request_id}, callback={request_id}")
                        return
                
                # 処理結果がNoneでないことを確認
                if processed_array is None:
                    log_print(ERROR, f"超解像処理が失敗しました: {request_id}")
                    self._show_status_message("超解像処理に失敗しました")
                    return
                
                # 結果を画像モデルに設定（これによりピクスマップも再構築され、sr_requestもクリアされる）
                success = self.image_model.set_sr_array(target_index, processed_array)
                
                if success:
                    log_print(INFO, f"超解像処理結果を受け取りました: index={target_index}, request_id={request_id}")
                    
                    # 表示を更新
                    if target_index < len(self.image_areas) and self.image_areas[target_index]:
                        # 更新されたピクスマップを取得
                        pixmap = self.image_model.get_pixmap(target_index)
                        if pixmap:
                            # 画像をエリアに設定
                            self._set_image_to_area(pixmap, target_index)
                            log_print(INFO, f"画像エリア {target_index} の表示を更新しました")
                    
                    # ユーザーに処理完了を通知
                    filename = os.path.basename(self.image_model.get_path(target_index))
                    self._show_status_message(f"超解像処理が完了しました: {filename}")
                    
                    # 画像情報をステータスバーに表示
                    self._update_status_info()
                else:
                    log_print(ERROR, f"超解像処理結果の適用に失敗しました: {request_id}")
                    self._show_status_message("処理結果の適用に失敗しました")
                
            except Exception as e:
                log_print(ERROR, f"超解像処理コールバック中にエラー: {e}")
                self._show_status_message("処理結果の適用中にエラーが発生しました")
                import traceback
                log_print(DEBUG, traceback.format_exc())
        
        # 超解像処理をリクエスト
        try:
            request_id = self.sr_manager.add_image_to_superres(numpy_array, on_superres_completed)
            
            # リクエストIDをモデルに保存
            self.image_model.set_sr_request(index, request_id)
            
            log_print(INFO, f"超解像処理をリクエストしました: index={index}, request_id={request_id}, file={filename}")
            self._show_status_message(f"超解像処理を開始しました: {filename}")
            
            return True
            
        except Exception as e:
            log_print(ERROR, f"超解像処理リクエスト中にエラー: {e}")
            self._show_status_message(f"超解像処理の開始に失敗しました: {str(e)}")
            import traceback
            log_print(DEBUG, traceback.format_exc())
            return False
