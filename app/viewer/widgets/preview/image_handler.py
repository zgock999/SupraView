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
    from PySide6.QtCore import Qt, QSize, QTimer, QObject
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


class ImageHandler(QObject):  # QObjectを継承して明示的にオブジェクトライフサイクルを管理
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
        super().__init__(parent)  # QObjectの初期化を正しく行う
        self.parent_widget = parent  # 親ウィジェットの参照を保持
        self.archive_manager = archive_manager
        self.image_model = image_model
        
        # 画像表示エリアの参照を保存
        self.image_areas = []
        
        # 超解像マネージャへの参照（初期はNone）
        self.sr_manager = None
        
        # 超解像処理の遅延リクエスト用タイマー - 親の設定を明示
        self.sr_delay_timer = QTimer(self)  # 親をselfに明示的に設定
        self.sr_delay_timer.setSingleShot(True)
        self.sr_delay_timer.setInterval(100)  # 100ms遅延
        self.sr_delay_timer.timeout.connect(self._process_delayed_superres)
        
        # 遅延リクエスト用のキュー
        self._delayed_sr_requests = {}  # {index: current_path}
        
        # 表示更新中フラグ - 再帰的な画面更新を防止
        self._updating_display = False
        
        log_print(DEBUG, f"ImageHandler: 初期化完了 (モデル参照: {self.image_model is not None})")
    
    def setup_image_areas(self, image_areas: List[QScrollArea]):
        """
        画像表示エリアを設定
        
        Args:
            image_areas: 画像表示用のスクロールエリアのリスト
        """
        if not image_areas:
            log_print(WARNING, "有効な画像エリアがありません")
            return
            
        # 以前の画像エリアをクリア
        self.image_areas = []
        
        # 新しい画像エリアを設定
        self.image_areas = image_areas
        log_print(DEBUG, f"画像表示エリアを設定: {len(image_areas)}個")
        
        # 既存の画像データがあれば表示を更新
        self._update_display_from_model()
    
    def _update_display_from_model(self):
        """画像モデルから画像データを取得して表示を更新"""
        if not self.image_model:
            return
            
        # 既に更新中なら、再帰的な呼び出しを避ける
        if self._updating_display:
            log_print(WARNING, "既に表示更新中のため、重複呼び出しをスキップします")
            return
            
        try:
            # 更新中フラグを設定
            self._updating_display = True
            
            # 画像モデルから表示モード情報を取得
            fit_to_window_mode = self.image_model.is_fit_to_window()
            zoom_factor = self.image_model.get_zoom_factor()
                
            # モデルに画像データが存在するか確認
            for index in [0, 1]:
                if index >= len(self.image_areas) or not self.image_areas[index]:
                    continue
                    
                if self.image_model.has_image(index):
                    pixmap = self.image_model.get_pixmap(index)
                    if (pixmap):
                        # 表示エリアに画像を設定
                        self._set_image_to_area(pixmap, index, adjust_display=False)
                        
                        # 表示モードも明示的に設定
                        area = self.image_areas[index]
                        if hasattr(area, 'set_fit_to_window'):
                            area.set_fit_to_window(fit_to_window_mode)
                            
                            # 非fit_to_windowモードの場合はズーム倍率も設定
                            if not fit_to_window_mode and hasattr(area, 'set_zoom'):
                                area.set_zoom(zoom_factor)
                        
                        # 表示を調整（一度だけ呼び出す）
                        if hasattr(area, '_adjust_image_size'):
                            area._adjust_image_size()
                            
                        log_print(DEBUG, f"画像データをモデルから復元: index={index}, fit={fit_to_window_mode}")
                        
            log_print(DEBUG, "画面表示を画像モデルと同期しました")
            
        finally:
            # 必ず更新中フラグをクリア
            self._updating_display = False
    
    def load_image_from_path(self, path: str, index: int = 0, use_browser_path: bool = False) -> bool:
        """
        アーカイブ内の指定パスから画像を読み込む
        
        Args:
            path: 画像ファイルパス
            index: 画像を表示するインデックス（0: 左/単一, 1: 右）
            use_browser_path: パスの解釈方法
                
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
            
            # 拡張子チェックを修正 - すべて小文字化して比較
            supported_exts_lower = [e.lower() for e in self.SUPPORTED_EXTENSIONS]
            if ext.lower() not in supported_exts_lower:
                log_print(WARNING, f"サポートされていない画像形式です: {ext}")
                self._show_status_message(f"サポートされていない画像形式です: {ext}")
                return False
            
            # パスの解釈に基づいて適切なメソッドで画像データを取得
            if use_browser_path:
                log_print(INFO, f"ブラウザパスから画像を読み込み中: {path}")
                image_data = self.archive_manager.extract_file(path)
            else:
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
                # 画像モデルに情報を設定（内部でmodifiedとdisplay_update_neededフラグが立つ）
                self.image_model.set_image(index, pixmap, image_data, numpy_array, info, path)
                
                # 既存のリクエストがあればキャンセル
                if self.sr_manager and self.image_model.has_sr_request(index):
                    old_request_id = self.image_model.get_sr_request(index)
                    if old_request_id:
                        self.sr_manager.cancel_superres(old_request_id)
                        log_print(DEBUG, f"既存の超解像リクエスト {old_request_id} をキャンセルしました")
                
                # 超解像処理の自動リクエスト - タイマーが停止していることを確認
                if self.sr_manager and numpy_array is not None and self.sr_manager.auto_process:
                    # 既に実行中のタイマーをキャンセル
                    if self.sr_delay_timer.isActive():
                        self.sr_delay_timer.stop()
                    # 遅延リクエストを登録
                    self._schedule_delayed_superres(index, path)
                    
                # 親ウィンドウに表示更新が必要なことを通知
                if self.parent_widget and hasattr(self.parent_widget, '_refresh_display_after_load'):
                    self.parent_widget._refresh_display_after_load(index)
                    log_print(DEBUG, f"画像読み込み後に表示更新を通知: index={index}, path={os.path.basename(path)}")
                
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
        """超解像処理リクエストを遅延スケジュールする"""
        # 現在のリクエストを記録 - 完全なパスを保存するように修正
        self._delayed_sr_requests[index] = path
        log_print(DEBUG, f"超解像処理の遅延リクエストを登録: index={index}, path={path}")
        
        # 遅延タイマーを開始（すでに開始されている場合は再起動）
        if self.sr_delay_timer.isActive():
            self.sr_delay_timer.stop()
        self.sr_delay_timer.start()
    
    def _process_delayed_superres(self):
        """遅延リクエストされた超解像処理を実行する"""
        if not self._delayed_sr_requests:
            return
            
        try:
            # 登録されていたリクエストを処理
            for index, path in list(self._delayed_sr_requests.items()):
                    # 画像モデルから現在のパスを取得して比較
                    current_path = self.image_model.get_path(index) if self.image_model else None
                    log_print(DEBUG, f"遅延超解像処理のパス比較: 登録={path}, 現在={current_path}")
                    
                    if current_path and current_path == path:
                        log_print(DEBUG, f"遅延された超解像処理を実行: index={index}, path={path}")
                        self._process_single_image(index)
                    else:
                        log_print(DEBUG, f"画像が変更されたため超解像処理をスキップ: index={index}")
        except Exception as e:
            log_print(ERROR, f"遅延超解像処理中にエラー: {e}")
            import traceback
            log_print(DEBUG, traceback.format_exc())
        finally:
            # 処理済みのリクエストをクリア
            self._delayed_sr_requests.clear()
    
    def _set_image_to_area(self, pixmap: QPixmap, index: int, adjust_display: bool = True):
        """指定されたインデックスの表示エリアに画像を設定"""
        # インデックスの範囲チェック
        if index not in [0, 1] or index >= len(self.image_areas) or self.image_areas[index] is None:
            log_print(ERROR, f"無効な表示エリアインデックス: {index}")
            return
        
        # 既に更新中なら、再帰呼び出しを避ける
        if self._updating_display:
            log_print(DEBUG, f"表示更新中のため、_set_image_to_area({index})をスキップします")
            return
            
        try:
            # 更新中フラグを設定
            self._updating_display = True
            
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
            scroll_area.image_label.repaint()  # 明示的に再描画を要求
            
            # 表示モードに応じて明示的に表示を更新（オプションで無効化可能）
            if adjust_display and hasattr(scroll_area, '_adjust_image_size'):
                scroll_area._adjust_image_size()
                log_print(DEBUG, f"画像エリア {index} の表示を更新")
        finally:
            # 必ず更新中フラグをクリア
            self._updating_display = False
    
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
        if status_msg and self.parent_widget and hasattr(self.parent_widget, 'statusbar'):
            self.parent_widget.statusbar.showMessage(status_msg)
    
    def _show_status_message(self, message: str):
        """ステータスバーにメッセージを表示"""
        if self.parent_widget and hasattr(self.parent_widget, 'statusbar'):
            self.parent_widget.statusbar.showMessage(message)
    
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
        
        try:
            # インデックスが指定されていない場合、現在のモードに応じて処理対象を決定
            if index is None:
                # デュアルモードかどうかをチェック
                is_dual_mode = self.image_model.is_dual_view() if hasattr(self.image_model, 'is_dual_view') else False
                
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
                
        except Exception as e:
            log_print(ERROR, f"超解像処理の実行中にエラーが発生しました: {e}")
            import traceback
            log_print(DEBUG, traceback.format_exc())
            return False
    
    def _process_single_image(self, index: int) -> bool:
        """
        指定インデックスの画像に対して超解像処理を実行
        
        Args:
            index: 処理する画像のインデックス
            
        Returns:
            bool: 処理リクエストに成功したかどうか
        """
        # 画像が読み込まれているか確認
        if not self.image_model or not self.image_model.has_image(index):
            log_print(ERROR, f"インデックス {index} に画像が読み込まれていません")
            self._show_status_message("処理する画像がありません")
            return False
        
        # NumPy配列形式の画像データを取得
        _, _, numpy_array, _, path = self.image_model.get_image(index)
        
        if numpy_array is None:
            log_print(ERROR, f"画像データが無効です: {path}")
            self._show_status_message("画像データが処理できない形式です")
            return False
        
        # 超解像マネージャーの存在確認
        if not self.sr_manager:
            log_print(ERROR, "超解像処理マネージャが設定されていません")
            self._show_status_message("超解像処理の準備ができていません")
            return False
        
        try:
            # 既存のリクエストがあればキャンセル
            if self.image_model.has_sr_request(index):
                old_request_id = self.image_model.get_sr_request(index)
                if old_request_id:
                    self.sr_manager.cancel_superres(old_request_id)
                    log_print(DEBUG, f"既存の超解像リクエスト {old_request_id} をキャンセルしました")
            
            # 処理状態をユーザーに通知
            filename = os.path.basename(path)
            self._show_status_message(f"超解像処理を開始しています: {filename}...")
            
            # 超解像処理用のコールバックを定義 - self weak referenceの問題対策
            def _internal_callback(request_id, processed_array):
                """コールバックのセーフラッパー"""
                try:
                    # 既にオブジェクトが破棄されていないか確認
                    if not self or not hasattr(self, 'image_model') or not self.image_model:
                        log_print(WARNING, "コールバック実行時にオブジェクトが破棄されています")
                        return
                        
                    self._on_superres_completed(index, request_id, processed_array)
                except Exception as e:
                    log_print(ERROR, f"超解像コールバック内でエラー: {e}")
                    import traceback
                    log_print(DEBUG, traceback.format_exc())
            
            # 超解像処理をリクエスト
            request_id = self.sr_manager.add_image_to_superres(numpy_array, _internal_callback)
            
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
            
    def _on_superres_completed(self, original_index, request_id, processed_array):
        """超解像処理完了時の処理 - コールバックから分離してメソッド化"""
        # 対応するリクエストIDを確認
        target_index = original_index  # デフォルト
        
        try:
            # 現在のリクエストIDを取得
            current_request_id = self.image_model.get_sr_request(original_index)
            
            # 他の画像のインデックスを計算（0→1, 1→0）
            other_index = 1 if original_index == 0 else 0
            # 他の画像のリクエストIDを取得
            other_request_id = self.image_model.get_sr_request(other_index)
            
            # リクエストIDが一致するか確認
            if current_request_id == request_id:
                # 一致する場合は通常通り処理
                log_print(INFO, f"画像 {original_index} の超解像処理が完了しました: {request_id}")
            else:
                # 一致しない場合、もう一方の画像をチェック
                
                if (other_request_id == request_id):
                    log_print(INFO, f"もう一方の画像 {other_index} の超解像処理が完了しました: {request_id}")
                    target_index = other_index
                else:
                    # どちらの画像とも一致しない場合（古いリクエストなど）
                    log_print(WARNING, f"リクエストIDが一致しません: current={current_request_id}, other={other_request_id}, callback={request_id}")
                    return
            
            # 処理結果がNoneでないことを確認
            if processed_array is None:
                log_print(ERROR, f"超解像処理の結果がNullです: {request_id}")
                self._show_status_message("超解像処理に失敗しました")
                return
            
            # 結果を画像モデルに設定（表示更新のフラグも立てる）
            success = self.image_model.set_sr_array(target_index, processed_array)
            
            if success:
                log_print(INFO, f"超解像処理結果を受け取りました: index={target_index}, request_id={request_id}")
                
                # ユーザーに処理完了を通知
                filename = os.path.basename(self.image_model.get_path(target_index))
                self._show_status_message(f"超解像処理が完了しました: {filename}")
                
                # 画像情報をステータスバーに表示
                self._update_status_info()
                
                # 親ウィンドウに通知（任意：表示更新のために必要なら）
                if self.parent_widget and hasattr(self.parent_widget, 'display_handler'):
                    # 直接display_handlerを呼び出すのではなく、通知フラグを設定
                    # または必要に応じてシグナルを発行
                    log_print(DEBUG, f"親ウィンドウに超解像処理完了を通知: index={target_index}")
                    
                    # 表示更新はdisplay_handlerに委任する必要があることを示すログ
                    log_print(DEBUG, f"表示更新のためにdisplay_handlerの更新が必要")
                    
                    # 親ウィンドウのメソッドを通じて表示更新を依頼（例）
                    if hasattr(self.parent_widget, '_refresh_display_after_superres'):
                        self.parent_widget._refresh_display_after_superres(target_index)
            else:
                log_print(ERROR, f"超解像処理結果の適用に失敗しました: {request_id}")
                self._show_status_message("処理結果の適用に失敗しました")
                
        except Exception as e:
            log_print(ERROR, f"超解像処理結果の適用中にエラー: {e}")
            self._show_status_message("処理結果の適用中にエラーが発生しました")
            import traceback
            log_print(DEBUG, traceback.format_exc())

    def _show_status_message(self, message: str):
        """ステータスバーにメッセージを表示"""
        if self.parent_widget and hasattr(self.parent_widget, 'statusbar'):
            self.parent_widget.statusbar.showMessage(message)
    
    def _update_status_info(self):
        """ステータスバーに画像情報を表示"""
        status_msg = self.get_status_info()
        if status_msg and self.parent_widget and hasattr(self.parent_widget, 'statusbar'):
            self.parent_widget.statusbar.showMessage(status_msg)
