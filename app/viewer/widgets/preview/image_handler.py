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
        
        # 超解像マネージャへの参照（初期はNone）
        self.sr_manager = None
        
        # 超解像処理の遅延リクエスト用タイマー - 親の設定を明示
        self.sr_delay_timer = QTimer(self)  # 親をselfに明示的に設定
        self.sr_delay_timer.setSingleShot(True)
        self.sr_delay_timer.setInterval(100)  # 100ms遅延
        self.sr_delay_timer.timeout.connect(self._process_delayed_superres)
        
        # 遅延リクエスト用のキュー
        self._delayed_sr_requests = {}  # {index: current_path}
        
        # 現在の画像パス（インデックスごと）を保存するディクショナリを追加
        self._current_image_paths = {0: None, 1: None}
        
        log_print(DEBUG, f"ImageHandler: 初期化完了 (モデル参照: {self.image_model is not None})")
    
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
        if index not in [0, 1]:
            log_print(ERROR, f"無効なインデックス: {index} (0または1のみ有効)")
            return False
        
        try:
            # 新しい画像読み込み時には、まず過去のエラー情報をクリアする
            if self.image_model:
                self.image_model.clear_error_info(index)
                log_print(DEBUG, f"インデックス {index} のエラー情報をクリアしました")
            
            # ファイル名から拡張子を取得
            _, ext = os.path.splitext(path.lower())
            
            # 拡張子チェック - すべて小文字化して比較
            supported_exts_lower = [e.lower() for e in self.SUPPORTED_EXTENSIONS]
            if (ext.lower() not in supported_exts_lower):
                log_print(WARNING, f"サポートされていない画像形式です: {ext}")
                self._show_status_message(f"サポートされていない画像形式です: {ext}")
                
                # モデルにエラー情報を保存
                if self.image_model:
                    error_info = {
                        'type': 'format_error',
                        'message': f"サポートされていない画像形式です: {ext}",
                        'path': path
                    }
                    self.image_model.set_error_info(index, error_info)
                    
                    # 親ウィンドウに表示更新が必要なことを通知
                    if self.parent_widget and hasattr(self.parent_widget, '_refresh_display_after_load'):
                        self.parent_widget._refresh_display_after_load(index)
                
                # エラーが発生したので超解像処理は行わない
                return False
            
            # パスの解釈に基づいて適切なメソッドで画像データを取得
            try:
                if use_browser_path:
                    log_print(INFO, f"ブラウザパスから画像を読み込み中: {path}")
                    image_data = self.archive_manager.extract_file(path)
                else:
                    log_print(INFO, f"ディレクトリ相対パスから画像を読み込み中: {path}")
                    image_data = self.archive_manager.extract_item(path)
            except IOError as e:
                log_print(ERROR, f"画像ファイルの読み込みにIOエラーが発生しました: {e}")
                self._show_status_message(f"ファイル読み込みエラー: {str(e)}")
                
                # モデルにエラー情報を保存
                if self.image_model:
                    error_info = {
                        'type': 'io_error',
                        'message': f"ファイル読み込みエラー: {str(e)}",
                        'path': path,
                        'exception': str(e)
                    }
                    self.image_model.set_error_info(index, error_info)
                    
                    # 親ウィンドウに表示更新が必要なことを通知
                    if self.parent_widget and hasattr(self.parent_widget, '_refresh_display_after_load'):
                        self.parent_widget._refresh_display_after_load(index)
                
                # エラーが発生したので超解像処理は行わない
                return False
            
            if not image_data:
                log_print(ERROR, f"画像データの読み込みに失敗しました: {path}")
                self._show_status_message(f"画像データの読み込みに失敗しました: {path}")
                
                # モデルにエラー情報を保存
                if self.image_model:
                    error_info = {
                        'type': 'empty_data',
                        'message': f"画像データの読み込みに失敗しました",
                        'path': path
                    }
                    self.image_model.set_error_info(index, error_info)
                    
                    # 親ウィンドウに表示更新が必要なことを通知
                    if self.parent_widget and hasattr(self.parent_widget, '_refresh_display_after_load'):
                        self.parent_widget._refresh_display_after_load(index)
                
                # エラーが発生したので超解像処理は行わない
                return False
            
            # 画像処理モジュールを使用して画像を読み込み
            try:
                pixmap, numpy_array, info = load_image_from_bytes(image_data, path)
            except ValueError as e:
                log_print(ERROR, f"画像のデコードに失敗しました: {e}")
                self._show_status_message(f"画像のデコードエラー: {str(e)}")
                
                # モデルにエラー情報を保存
                if self.image_model:
                    error_info = {
                        'type': 'decode_error',
                        'message': f"画像のデコードに失敗しました: {str(e)}",
                        'path': path,
                        'exception': str(e)
                    }
                    self.image_model.set_error_info(index, error_info)
                    
                    # 親ウィンドウに表示更新が必要なことを通知
                    if self.parent_widget and hasattr(self.parent_widget, '_refresh_display_after_load'):
                        self.parent_widget._refresh_display_after_load(index)
                
                # エラーが発生したので超解像処理は行わない
                return False
            
            if pixmap is None:
                log_print(ERROR, f"画像の表示に失敗しました: {path}")
                self._show_status_message(f"画像の表示に失敗しました: {path}")
                
                # モデルにエラー情報を保存
                if self.image_model:
                    error_info = {
                        'type': 'display_error',
                        'message': f"画像の表示に失敗しました",
                        'path': path
                    }
                    self.image_model.set_error_info(index, error_info)
                    
                    # 親ウィンドウに表示更新が必要なことを通知
                    if self.parent_widget and hasattr(self.parent_widget, '_refresh_display_after_load'):
                        self.parent_widget._refresh_display_after_load(index)
                
                # エラーが発生したので超解像処理は行わない
                return False
            
            # 画像モデルに画像情報を設定
            if self.image_model:
                # 画像モデルに情報を設定（内部でmodifiedとdisplay_update_neededフラグが立つ）
                self.image_model.set_image(index, pixmap, image_data, numpy_array, info, path)
                
                # 現在のパスを保存（後で整合性チェックに使用）
                self._current_image_paths[index] = path
                
                # 画像モデルにもパス情報を保存
                if self.image_model:
                    self.image_model.set_image_property(index, 'path', path)
                
                # 既存の超解像リクエストがあればキャンセル
                if self.sr_manager and self.image_model.has_sr_request(index):
                    old_request_id = self.image_model.get_sr_request(index)
                    if old_request_id:
                        self.sr_manager.cancel_superres(old_request_id)
                        log_print(DEBUG, f"既存の超解像リクエスト {old_request_id} をキャンセルしました")
                
                # エラーがないことを確認してから自動超解像処理をスケジュール
                if self.sr_manager and numpy_array is not None and self.sr_manager.auto_process:
                    # エラー情報があるか確認
                    if not self.image_model.has_error(index):
                        # 既に実行中のタイマーをキャンセル
                        if self.sr_delay_timer.isActive():
                            self.sr_delay_timer.stop()
                        # 遅延リクエストを登録
                        self._schedule_delayed_superres(index, path)
                    else:
                        log_print(INFO, f"インデックス {index} にエラーが発生しているため、自動超解像処理をスキップします")
                
                # 親ウィンドウに表示更新が必要なことを通知
                if self.parent_widget and hasattr(self.parent_widget, '_refresh_display_after_load'):
                    # MVCパターンに従い、親に通知するだけで表示層に直接介入しない
                    self.parent_widget._refresh_display_after_load(index)
                    log_print(DEBUG, f"画像読み込み後に更新を通知: index={index}, path={os.path.basename(path)}")
            
            # 画像情報をステータスバーに表示
            status_msg = self.get_status_info()
            if status_msg:
                self._show_status_message(status_msg)
            
            return True
            
        except Exception as e:
            log_print(ERROR, f"画像の読み込み中にエラーが発生しました: {e}")
            self._show_status_message(f"エラー: {str(e)}")
            import traceback
            log_print(DEBUG, traceback.format_exc())
            
            # モデルにエラー情報を保存
            if self.image_model:
                error_info = {
                    'type': 'unknown_error',
                    'message': f"画像の読み込み中にエラーが発生しました: {str(e)}",
                    'path': path,
                    'exception': str(e),
                    'traceback': traceback.format_exc()
                }
                self.image_model.set_error_info(index, error_info)
                
                # 親ウィンドウに表示更新が必要なことを通知
                if self.parent_widget and hasattr(self.parent_widget, '_refresh_display_after_load'):
                    self.parent_widget._refresh_display_after_load(index)
            
            # エラーが発生したので超解像処理は行わない
            return False
    
    def _schedule_delayed_superres(self, index: int, path: str):
        """超解像処理リクエストを遅延スケジュールする"""
        # エラーがある場合は超解像処理をスケジュールしない
        if self.image_model and self.image_model.has_error(index):
            log_print(INFO, f"インデックス {index} にエラーがあるため、遅延超解像処理はスケジュールしません")
            return
            
        # 現在のリクエストを記録 - 完全なパスを保存
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
                # エラー確認を追加
                if self.image_model and self.image_model.has_error(index):
                    log_print(INFO, f"インデックス {index} にエラーが発生しているため、遅延超解像処理をスキップします")
                    continue
                
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
    
    def clear_image(self, index: int):
        """
        指定されたインデックスの画像をクリア
        
        Args:
            index: クリアする画像のインデックス
        """
        # インデックスの範囲チェック
        if index not in [0, 1]:
            log_print(ERROR, f"無効なインデックス: {index}")
            return
        
        # モデル内の画像情報をクリア
        if self.image_model:
            self.image_model.clear_image(index)
            
            # 親ウィンドウに表示更新が必要なことを通知
            if self.parent_widget and hasattr(self.parent_widget, '_refresh_display_after_load'):
                self.parent_widget._refresh_display_after_load(index)
    
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
        
        Args:
            image_model: 画像情報を管理するモデル
        """
        self.image_model = image_model
        log_print(INFO, "画像モデルを設定しました")
        # 初期化段階では画像はないため、表示更新通知は不要
    
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
        
        # エラー確認を追加
        if self.image_model.has_error(index):
            log_print(INFO, f"インデックス {index} にエラーが発生しているため、超解像処理をスキップします")
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
            
            # 超解像処理実行前に、現在の画像パスを確認して保存
            if path != self._current_image_paths.get(index):
                log_print(DEBUG, f"現在のパス情報を更新: {path} (旧: {self._current_image_paths.get(index)})")
                self._current_image_paths[index] = path
                
            # モデルにもパス情報を保存して整合性を確保
            if self.image_model:
                current_model_path = self.image_model.get_image_property(index, 'path')
                if current_model_path != path:
                    log_print(DEBUG, f"モデルのパス情報を更新: {path} (旧: {current_model_path})")
                    self.image_model.set_image_property(index, 'path', path)
            
            # 超解像処理用のコールバックを定義
            def _internal_callback(request_id, processed_array):
                """コールバックのセーフラッパー"""
                try:
                    # 既にオブジェクトが破棄されていないか確認
                    if not self or not hasattr(self, 'image_model') or not self.image_model:
                        log_print(WARNING, "コールバック実行時にオブジェクトが破棄されています")
                        return
                        
                    # 直接処理メソッドを呼び出す
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
                
            # 画像パスの整合性を検証 - Noneの場合の適切な処理を追加
            path_at_request = self.image_model.get_image_property(target_index, 'path')
            current_path = self._current_image_paths[target_index]
            
            # パス比較ロジックの改善
            if path_at_request is None and current_path is not None:
                # モデルのパスプロパティが未設定の場合は、現在のパスを基準とする
                log_print(DEBUG, f"モデルのパスプロパティが未設定のため、現在のパスを使用: {current_path}")
                
                # 整合性確保のため、モデルにパスを設定
                self.image_model.set_image_property(target_index, 'path', current_path)
                path_at_request = current_path
            elif current_path is None and path_at_request is not None:
                # キャッシュ側のパスがない場合はモデルのパスを使う
                log_print(DEBUG, f"キャッシュのパスが未設定のため、モデルのパスを使用: {path_at_request}")
                self._current_image_paths[target_index] = path_at_request
                current_path = path_at_request
            
            # 詳細なデバッグ情報を出力
            log_print(DEBUG, f"パス比較: モデル={path_at_request}, キャッシュ={current_path}")
            
            # パスが一致しない場合のみ警告
            if path_at_request is not None and current_path is not None and path_at_request != current_path:
                log_print(WARNING, f"画像パス不一致: 超解像結果を無視します (index={target_index}, パス={path_at_request}, 現在={current_path})")
                self._show_status_message("画像変更のため超解像処理結果を適用できません")
                return
            
            # ※※※ 新規コード追加：エラーがある場合は超解像処理結果を破棄 ※※※
            if self.image_model.has_error(target_index):
                log_print(WARNING, f"インデックス {target_index} にエラーがあるため、超解像処理結果を破棄します")
                self._show_status_message("画像エラーのため超解像処理結果を適用できません")
                return
            
            # 結果を画像モデルに設定（表示更新のフラグも立てる）
            success = self.image_model.set_sr_array(target_index, processed_array)
            
            if success:
                log_print(INFO, f"超解像処理結果を受け取りました: index={target_index}, request_id={request_id}")
                
                # ユーザーに処理完了を通知
                filename = os.path.basename(self.image_model.get_path(target_index))
                self._show_status_message(f"超解像処理が完了しました: {filename}")
                
                # 親ウィンドウに表示更新が必要なことを通知
                if self.parent_widget and hasattr(self.parent_widget, '_refresh_display_after_superres'):
                    # MVCパターンに従い、親に通知するだけで表示層に直接関与しない
                    self.parent_widget._refresh_display_after_superres(target_index)
                    log_print(DEBUG, f"親ウィンドウに超解像処理完了を通知: index={target_index}")
            else:
                log_print(ERROR, f"超解像処理結果の適用に失敗しました: {request_id}")
                self._show_status_message("処理結果の適用に失敗しました")
                
        except Exception as e:
            log_print(ERROR, f"超解像処理結果の適用中にエラー: {e}")
            self._show_status_message("処理結果の適用中にエラーが発生しました")
            import traceback
            log_print(DEBUG, traceback.format_exc())
