"""
拡張された超解像処理マネージャ

アプリケーション用に拡張されたSuperResolutionManagerの実装
"""

import os
import time
import uuid
import threading
import queue
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from enum import Enum

import cv2
import numpy as np
from PySide6.QtCore import QObject, QThread

from sr.sr_base import SuperResolutionBase, SRMethod, SRResult
from sr.sr_utils import is_cuda_available, get_gpu_info, get_sr_method_from_string
from app.viewer.superres.sr_manager import SuperResolutionManager


# タスクの状態を表す列挙型
class TaskState(Enum):
    PENDING = 1    # 処理待ち
    RUNNING = 2    # 処理中
    COMPLETED = 3  # 完了
    CANCELED = 4   # キャンセル済み
    FAILED = 5     # 失敗


class EnhancedSRManager(SuperResolutionManager):
    """
    アプリケーション用に拡張された超解像マネージャ
    
    SuperResolutionManagerを拡張し、設定管理やメソッド間の調整機能を追加
    """
    
    def __init__(self):
        """初期化"""
        super().__init__()
        self.is_initializing = False
        self.is_reinitializing = False  # 再初期化フラグを追加
        self.auto_process = True  # 自動処理有効

        # オプション保存
        self._cached_options = {}
        
        # コールバック関数
        self._progress_callback = None
        self._completion_callback = None
        self._settings_callback = None
        
        # モデル固有のデフォルト設定
        self.method_defaults = {
            SRMethod.REALESRGAN: {
                'variant': 'denoise',
                'denoise_strength': 0.5,
                'face_enhance': False,
                'half_precision': True
            },
            SRMethod.SWINIR_LIGHTWEIGHT: {
                'window_size': 8,
                'jpeg_artifact': False,
                'half_precision': True
            },
            SRMethod.SWINIR_REAL: {
                'window_size': 8,
                'jpeg_artifact': True,
                'half_precision': True
            },
            SRMethod.SWINIR_CLASSICAL: {
                'window_size': 8,
                'jpeg_artifact': False,
                'half_precision': True
            },
            SRMethod.SWINIR_LARGE: {
                'window_size': 8,
                'jpeg_artifact': False,
                'half_precision': True
            }
        }
        
        # 超解像処理タスク管理
        self._task_queue = queue.Queue()  # タスクキュー
        self._task_dict = {}  # タスク辞書 {request_id: (task_info)}
        self._processing_lock = threading.Lock()  # 処理ロック
        self._current_thread = None  # 現在実行中のスレッド
    
    def set_callbacks(self, progress_callback: Callable[[str], None] = None, 
                     completion_callback: Callable[[bool], None] = None, 
                     settings_callback: Callable[[Dict[str, Any]], None] = None):
        """
        コールバック関数を設定
        
        Args:
            progress_callback: 進捗通知用コールバック関数 (message)
            completion_callback: 完了通知用コールバック関数 (success)
            settings_callback: 設定変更通知用コールバック関数 (settings)
        """
        self._progress_callback = progress_callback
        self._completion_callback = completion_callback
        self._settings_callback = settings_callback

    def _notify_progress(self, message: str):
        """進捗メッセージを通知"""
        # コールバック呼び出し
        if self._progress_callback:
            try:
                self._progress_callback(message)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"進捗コールバック呼び出し中にエラー: {e}")

    def _notify_completion(self, success: bool):
        """完了を通知"""
        # コールバック呼び出し
        if self._completion_callback:
            try:
                self._completion_callback(success)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"完了コールバック呼び出し中にエラー: {e}")

    def _notify_settings_changed(self, settings: Dict[str, Any]):
        """設定変更を通知"""
        # コールバック呼び出し
        if self._settings_callback:
            try:
                self._settings_callback(settings)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"設定変更コールバック呼び出し中にエラー: {e}")

    def update_settings_with_callback(self, settings: Dict[str, Any], callback=None):
        """
        設定を更新し、完了時にコールバックを呼び出す
        
        Args:
            settings: 新しい設定
            callback: 完了時に呼び出すコールバック (success, message)
        """
        # 一時的に完了コールバックを保存
        original_callback = self._settings_callback
        
        def on_complete(success):
            # 元のコールバックを復元
            self._settings_callback = original_callback
            
            # 結果メッセージを作成
            message = "設定を更新しました" if success else "設定の更新に失敗しました"
            
            # 渡されたコールバックを呼び出す
            if callback:
                try:
                    callback(success, message)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"設定更新コールバック呼び出し中にエラー: {e}")
        
        # 完了コールバックを設定
        self._settings_callback = on_complete
        
        # 設定を更新
        return self.update_settings(settings)

    def initialize(self, method: SRMethod, scale: int = 2, options: Dict[str, Any] = None) -> bool:
        """
        超解像モデルを初期化する
        
        Args:
            method: 使用する超解像メソッド
            scale: 拡大倍率
            options: 初期化オプション
            
        Returns:
            bool: 初期化に成功したかどうか
        """
        try:
            # 初期化中フラグを設定
            self.is_initializing = True
            
            # 進捗通知
            self._notify_progress(f"モデル {method.name} (x{scale}) の初期化を開始します")
            
            # デフォルトのオプションを取得してユーザー設定で上書き
            processed_options = self._get_processed_options(method, options)
            
            # 基底クラスの初期化メソッドを呼び出し
            success = super().initialize(method, scale, processed_options)
            
            if success:
                # 成功時の処理
                self._notify_progress(f"モデル {method.name} (x{scale}) の初期化が完了しました")
                
                # キャッシュオプションを更新
                self._cached_options = processed_options.copy()
            else:
                # 失敗時の処理
                self._notify_progress(f"モデル {method.name} (x{scale}) の初期化に失敗しました")
                # 初期化中フラグをクリア
                self.is_initializing = False
                self.is_reinitializing = False
                self._notify_completion(False)
                return False
            
            # 初期化中フラグをクリア
            self.is_initializing = False
            self.is_reinitializing = False
            
            # 完了通知
            self._notify_completion(success)
            
            return success
            
        except Exception as e:
            # エラー処理
            import traceback
            traceback.print_exc()
            
            error_msg = f"モデル初期化中にエラー: {str(e)}"
            self._notify_progress(error_msg)
            
            # 初期化中フラグをクリア
            self.is_initializing = False
            self.is_reinitializing = False
            
            # 完了通知（失敗）
            self._notify_completion(False)
            
            return False
    
    def reinitialize(self, method: SRMethod, scale: int = 2, options: Dict[str, Any] = None) -> bool:
        """
        超解像モデルを再初期化する（設定変更用）
        初期化と異なりエラーやキャンセル時にアプリケーションが終了しない
        
        Args:
            method: 使用する超解像メソッド
            scale: 拡大倍率
            options: 初期化オプション
            
        Returns:
            bool: 初期化に成功したかどうか
        """
        try:
            # 初期化中フラグを設定
            self.is_initializing = True
            self.is_reinitializing = True
            
            # 進捗通知
            self._notify_progress(f"モデル {method.name} (x{scale}) の再初期化を開始します")
            
            # デフォルトのオプションを取得してユーザー設定で上書き
            processed_options = self._get_processed_options(method, options)
            
            # 基底クラスのモデルをクリーンアップ
            if self._model is not None:
                self._model.cleanup()
                self._model = None
            
            # 新しいモデルを作成
            self._model = SuperResolutionBase.create(method, scale, processed_options)
            if self._model is None:
                self._notify_progress(f"モデル {method.name} の作成に失敗しました")
                self.is_initializing = False
                self.is_reinitializing = False
                self._notify_completion(False)
                return False
            
            # モデルを初期化
            if not self._model.initialize(processed_options):
                self._notify_progress(f"モデル {method.name} の初期化に失敗しました")
                self.is_initializing = False
                self.is_reinitializing = False
                self._notify_completion(False)
                return False
            
            # 初期化成功
            self._method = method
            self._scale = scale
            self._options = processed_options
            self._initialized = True
            
            # 成功時の処理
            self._notify_progress(f"モデル {method.name} (x{scale}) の再初期化が完了しました")
            
            # キャッシュオプションを更新
            self._cached_options = processed_options.copy()
            
            # 初期化中フラグをクリア
            self.is_initializing = False
            self.is_reinitializing = False
            
            # 完了通知
            self._notify_completion(True)
            
            return True
            
        except Exception as e:
            # 予期せぬ例外をキャッチして適切に処理
            import traceback
            traceback.print_exc()
            
            error_msg = f"モデル再初期化中に予期せぬエラー: {str(e)}"
            self._notify_progress(error_msg)
            
            # 初期化中フラグをクリア
            self.is_initializing = False
            self.is_reinitializing = False
            
            # 完了通知（失敗）
            self._notify_completion(False)
            
            return False
    
    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """
        設定を更新し、必要に応じてモデルを再初期化する
        
        Args:
            settings: 新しい設定
            
        Returns:
            bool: 更新に成功したかどうか
        """
        try:
            # 設定変更中にプログレス通知
            self._notify_progress("設定を更新中...")
            
            # 現在の設定を保存
            old_method = self._method
            old_scale = self._scale
            old_options = self._options.copy() if self._options else {}
            
            # 新しい設定を取得
            new_method = settings.get('method', old_method)
            new_scale = settings.get('scale', old_scale)
            new_options = settings.get('options', {})
            
            # 自動処理設定を更新
            if 'auto_process' in settings:
                self.auto_process = settings['auto_process']
            
            # 再初期化が必要か判定（例外を完全に捕捉）
            try:
                reinit_needed = self._is_reinit_needed(old_method, old_scale, old_options, new_method, new_scale, new_options)
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_msg = f"再初期化判定中にエラー: {str(e)}"
                self._notify_progress(error_msg)
                
                # エラー発生時は安全側に倒して再初期化が必要と判断
                reinit_needed = True
            
            # 再初期化が必要な場合は再初期化を実行
            if reinit_needed:
                # 初期化中フラグを設定
                self.is_initializing = True
                self.is_reinitializing = True
                
                # メソッドとスケールを更新（先に更新することで進捗表示に反映される）
                self._method = new_method
                self._scale = new_scale
                self._options = new_options
                
                # 再初期化を実行（例外はreinitializeメソッド内で完全に捕捉）
                success = self.reinitialize(new_method, new_scale, new_options)
                
                if not success:
                    # 初期化失敗時は設定を戻す
                    self._method = old_method
                    self._scale = old_scale
                    self._options = old_options
                    
                    # エラーメッセージを表示
                    self._notify_progress("設定の更新に失敗しました。元の設定に戻します")
                    return False
            else:
                # 再初期化が不要な場合は設定だけ更新
                try:
                    self._method = new_method
                    self._scale = new_scale
                    self._options = new_options
                    self._notify_progress("設定を更新しました")
                except Exception as e:
                    # 設定更新中の例外を捕捉
                    import traceback
                    traceback.print_exc()
                    error_msg = f"設定更新中にエラー: {str(e)}"
                    self._notify_progress(error_msg)
                    
                    # 設定を戻す
                    self._method = old_method
                    self._scale = old_scale
                    self._options = old_options
                    return False
            
            # 設定変更通知を発行（例外を捕捉）
            try:
                settings_copy = settings.copy()  # 安全のためコピーを作成
                self._notify_settings_changed(settings_copy)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._notify_progress(f"設定変更通知中にエラー: {str(e)}")
                # 通知の失敗は全体の成功には影響しない
            
            return True
        
        except Exception as e:
            # 設定更新全体の例外処理
            import traceback
            traceback.print_exc()
            
            error_msg = f"設定更新中に予期しないエラー: {str(e)}"
            self._notify_progress(error_msg)
            
            # フラグをクリア
            self.is_initializing = False
            self.is_reinitializing = False
            
            # 失敗通知を発行
            self._notify_completion(False)
            
            return False
    
    def add_image_to_superres(self, image: np.ndarray, callback: Callable[[str, Optional[np.ndarray]], None]) -> str:
        """
        超解像処理のためにイメージを登録し、処理キューに追加
        
        Args:
            image: 処理する画像（NumPy配列）
            callback: 処理完了時のコールバック関数
            
        Returns:
            str: リクエストID
        """
        # リクエストIDを生成
        request_id = str(uuid.uuid4())
        
        # タスク情報を作成
        task_info = {
            'request_id': request_id,
            'image': image.copy(),  # 画像データのコピーを作成
            'callback': callback,   # コールバック関数
            'thread': None,         # 処理スレッド（初期はNone）
            'state': TaskState.PENDING,  # 初期状態は処理待ち
            'result': None          # 処理結果（初期はNone）
        }
        
        # キューと辞書に登録
        self._task_queue.put(task_info)
        self._task_dict[request_id] = task_info
        
        # 処理を開始
        self._process_next_task()
        
        return request_id
    
    def _process_next_task(self):
        """キューから次のタスクを処理"""
        # 処理ロックを取得
        with self._processing_lock:
            # 現在処理中のタスクがある場合は何もしない
            if self._current_thread is not None and self._current_thread.is_alive():
                return
            
            # 処理対象のタスクを探す
            task_to_process = None
            
            # キューが空になるまでキャンセル済みのタスクをスキップ
            while not self._task_queue.empty():
                task = self._task_queue.get()
                request_id = task['request_id']
                
                # キャンセル済みのタスクは辞書から削除して次へ
                if task['state'] == TaskState.CANCELED:
                    if request_id in self._task_dict:
                        del self._task_dict[request_id]
                    continue
                
                # 処理中のタスクがある場合はループを抜ける
                if task['state'] == TaskState.RUNNING:
                    # キューに戻す
                    self._task_queue.put(task)
                    break
                
                # 処理待ちのタスクが見つかった
                if task['state'] == TaskState.PENDING:
                    task_to_process = task
                    break
            
            # 処理するタスクがなければ終了
            if task_to_process is None:
                return
            
            # タスクの状態を処理中に更新
            task_to_process['state'] = TaskState.RUNNING
            
            # 処理スレッドを作成して開始
            thread = threading.Thread(
                target=self._process_superres_task,
                args=(task_to_process,),
                daemon=True
            )
            
            # スレッド参照を保存
            task_to_process['thread'] = thread
            self._current_thread = thread
            
            # スレッドを開始
            thread.start()
            
            # キューに戻す（処理中の状態で）
            self._task_queue.put(task_to_process)
    
    def _process_superres_task(self, task):
        """
        超解像処理タスクを実行
        
        Args:
            task: 処理するタスク情報
        """
        request_id = task['request_id']
        image = task['image']
        
        try:
            # キャンセルチェック
            if task['state'] == TaskState.CANCELED:
                # タスクがキャンセルされた場合は何もせず終了
                return
            
            # モデルが初期化されていない場合はエラー
            if not self.is_initialized:
                self._superres_completed(request_id, None)
                return
            
            # 超解像処理を実行
            result = self.process(image, self._options)
            
            # キャンセルチェック
            if task['state'] == TaskState.CANCELED:
                # 処理後でもタスクがキャンセルされた場合は結果を破棄
                return
            
            # 処理に失敗した場合
            if result is None:
                self._superres_completed(request_id, None)
                return
            
            # 処理結果を取得
            processed_image = result.image
            
            # 処理完了コールバックを呼び出し
            self._superres_completed(request_id, processed_image)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # エラー発生時はNoneを結果として渡す
            self._superres_completed(request_id, None)
    
    def _superres_completed(self, request_id: str, processed_image: Optional[np.ndarray]):
        """
        超解像処理完了時の処理
        
        Args:
            request_id: リクエストID
            processed_image: 処理された画像、またはNone（失敗時）
        """
        # タスク辞書からタスク情報を取得
        if request_id not in self._task_dict:
            return
            
        task = self._task_dict[request_id]
        
        # タスクが実行中の場合のみ処理
        if task['state'] == TaskState.RUNNING:
            # コールバックを呼び出し
            callback = task['callback']
            if callback:
                try:
                    callback(request_id, processed_image)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
            
            # タスクをキューと辞書から削除
            # 辞書からの削除
            del self._task_dict[request_id]
            
            # キューの再構築（キャンセル済みタスクも除去）
            new_queue = queue.Queue()
            
            while not self._task_queue.empty():
                q_task = self._task_queue.get()
                q_request_id = q_task['request_id']
                
                # このタスクまたはキャンセル済みのタスクは除外
                if q_request_id == request_id or q_task['state'] == TaskState.CANCELED:
                    continue
                
                # その他のタスクは新しいキューに追加
                new_queue.put(q_task)
            
            # キューを更新
            self._task_queue = new_queue
        
        # 次のタスクを処理
        self._current_thread = None
        self._process_next_task()
        
    def cancel_superres(self, request_id: str) -> bool:
        """
        超解像処理をキャンセル
        
        Args:
            request_id: キャンセルするリクエストID
            
        Returns:
            bool: キャンセルに成功したかどうか
        """
        # リクエストIDが辞書に存在するか確認
        if request_id not in self._task_dict:
            return False
            
        # タスク情報を取得
        task = self._task_dict[request_id]
        
        # タスクの状態に応じた処理
        if task['state'] == TaskState.RUNNING:
            # 処理中のタスクはCANCELEDにし、スレッドにキャンセルを送る
            task['state'] = TaskState.CANCELED
            # 現在のスレッドはこのタスクのスレッドか？
            if self._current_thread == task['thread']:
                # 現在のスレッドをNoneに設定（次のタスク処理のため）
                self._current_thread = None
            return True
        elif task['state'] == TaskState.PENDING:
            # 処理待ちのタスクはキューと辞書から削除
            task['state'] = TaskState.CANCELED
            # 辞書から削除
            del self._task_dict[request_id]
            # キューはそのまま（取り出し時にCANCELEDをチェックしてスキップ）
            return True
        
        # 既に完了またはキャンセル済みの場合
        return False
    
    def _get_processed_options(self, method: SRMethod, user_options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        指定されたメソッドとユーザーオプションからオプションを準備する
        
        Args:
            method: 超解像メソッド
            user_options: ユーザー指定オプション
            
        Returns:
            Dict[str, Any]: 処理されたオプション
        """
        # 基本オプション（すべてのメソッドで共通）
        options = {
            'tile': 512,  # タイルサイズ
            'tile_pad': 32,  # パディングサイズ
        }
        
        # ユーザーオプションが提供されている場合は基本オプションを上書き
        if user_options:
            for key in ['tile', 'tile_pad']:
                if key in user_options:
                    options[key] = user_options[key]
        
        # メソッド固有のデフォルト設定がある場合は追加
        if method in self.method_defaults:
            method_defaults = self.method_defaults[method]
            for key, value in method_defaults.items():
                options[key] = value
        
        # メソッド固有のユーザー設定で上書き
        method_key = method.name.lower()
        
        # RealESRGAN用のオプション
        if method == SRMethod.REALESRGAN:
            # バリアントオプション
            if user_options and 'variant' in user_options:
                options['variant'] = user_options['variant']
            
            # デノイズ強度
            if user_options and 'denoise_strength' in user_options:
                options['denoise_strength'] = user_options['denoise_strength']
            
            # 顔強調
            if user_options and 'face_enhance' in user_options:
                options['face_enhance'] = user_options['face_enhance']
            
            # 半精度設定
            if user_options and 'half_precision' in user_options:
                options['half_precision'] = user_options['half_precision']
                
        # SwinIR用のオプション
        elif method in [SRMethod.SWINIR_LIGHTWEIGHT, SRMethod.SWINIR_REAL, 
                      SRMethod.SWINIR_LARGE, SRMethod.SWINIR_CLASSICAL]:
            # ウィンドウサイズ
            if user_options and 'window_size' in user_options:
                options['window_size'] = user_options['window_size']
            
            # JPEG圧縮アーティファクト対応
            if user_options and 'jpeg_artifact' in user_options:
                options['jpeg_artifact'] = user_options['jpeg_artifact']
            
            # 半精度設定
            if user_options and 'half_precision' in user_options:
                options['half_precision'] = user_options['half_precision']
        
        return options
    
    def _is_reinit_needed(self, old_method, old_scale, old_options, new_method=None, new_scale=None, new_options=None):
        """
        モデルの再初期化が必要かどうかを判定する
        
        Args:
            old_method: 以前のメソッド
            old_scale: 以前のスケール
            old_options: 以前のオプション
            new_method: 新しいメソッド（指定がなければ現在の設定）
            new_scale: 新しいスケール（指定がなければ現在の設定）
            new_options: 新しいオプション（指定がなければ現在の設定）
            
        Returns:
            bool: 再初期化が必要な場合はTrue
        """
        # 引数がない場合は現在の設定を使用
        if new_method is None:
            new_method = self._method
        if new_scale is None:
            new_scale = self._scale
        if new_options is None:
            new_options = self._options
        
        # メソッドまたはスケールが変更された場合は必ず再初期化
        if old_method != new_method or old_scale != new_scale:
            return True
        
        # RealESRGANの場合、特定のオプション変更で再初期化が必要
        if new_method == SRMethod.REALESRGAN:
            # 変更前後のオプションを取得
            old_variant = old_options.get('variant', 'denoise')
            new_variant = new_options.get('variant', 'denoise')
            
            # 半精度処理設定の変更チェック
            old_half_precision = old_options.get('half_precision', True)
            new_half_precision = new_options.get('half_precision', True)
            
            # 顔強調設定の変更チェック
            old_face_enhance = old_options.get('face_enhance', False)
            new_face_enhance = new_options.get('face_enhance', False)
            
            # モデル種類、半精度処理設定、顔強調設定のいずれかが変更された場合は再初期化が必要
            if (old_variant != new_variant or 
                old_half_precision != new_half_precision or 
                old_face_enhance != new_face_enhance):
                return True
        
        # SwinIRの場合、特定のオプション変更で再初期化が必要
        elif new_method in [SRMethod.SWINIR_LIGHTWEIGHT, SRMethod.SWINIR_REAL, 
                            SRMethod.SWINIR_LARGE, SRMethod.SWINIR_CLASSICAL]:
            # ウィンドウサイズの変更チェック
            old_window_size = old_options.get('window_size', 8)
            new_window_size = new_options.get('window_size', 8)
            
            # 半精度処理設定の変更チェック
            old_half_precision = old_options.get('half_precision', True)
            new_half_precision = new_options.get('half_precision', True)
            
            # JPEG圧縮対応設定の変更チェック（実写向けモデル用）
            old_jpeg_artifact = old_options.get('jpeg_artifact', False)
            new_jpeg_artifact = new_options.get('jpeg_artifact', False)
            
            # ウィンドウサイズ、半精度処理設定、JPEG圧縮対応設定のいずれかが変更された場合は再初期化が必要
            if (old_window_size != new_window_size or 
                old_half_precision != new_half_precision or 
                old_jpeg_artifact != new_jpeg_artifact):
                return True
        
        # OpenCV DNNモデルの場合、モデルタイプの変更で再初期化が必要
        elif new_method in [SRMethod.OPENCV_EDSR, SRMethod.OPENCV_ESPCN, 
                          SRMethod.OPENCV_FSRCNN, SRMethod.OPENCV_LAPSRN]:
            # モデルタイプの変更チェック
            old_model_type = old_options.get('model_type', '標準')
            new_model_type = new_options.get('model_type', '標準')
            
            # モデルタイプが変更された場合は再初期化が必要
            if old_model_type != new_model_type:
                return True
        
        # タイルサイズの変更チェック（全メソッド共通）
        old_tile = old_options.get('tile', 512)
        new_tile = new_options.get('tile', 512)
        
        # タイルパディングの変更チェック
        old_tile_pad = old_options.get('tile_pad', 32)
        new_tile_pad = new_options.get('tile_pad', 32)
        
        # タイルサイズまたはパディングが変更された場合（0から非0、非0から0を含む）
        if ((old_tile == 0 and new_tile != 0) or 
            (old_tile != 0 and new_tile == 0) or
            (old_tile_pad != new_tile_pad)):
            return True
        
        # その他の変更は再初期化不要
        return False

    def get_method_display_name(self, method: SRMethod) -> str:
        """
        メソッドの表示名を取得
        
        Args:
            method: 超解像メソッド
            
        Returns:
            str: 表示用の名前
        """
        method_names = {
            SRMethod.OPENCV_CUBIC: "OpenCV Bicubic",
            SRMethod.OPENCV_LANCZOS: "OpenCV Lanczos4",
            SRMethod.OPENCV_NEAREST: "OpenCV Nearest",
            SRMethod.REALESRGAN: "Real-ESRGAN",
            SRMethod.SWINIR_LIGHTWEIGHT: "SwinIR 軽量モデル",
            SRMethod.SWINIR_REAL: "SwinIR 実写向け",
            SRMethod.SWINIR_LARGE: "SwinIR 高品質モデル",
            SRMethod.SWINIR_CLASSICAL: "SwinIR 標準モデル"
        }
        return method_names.get(method, method.name)
    
    def get_production_methods(self) -> List[SRMethod]:
        """
        実運用に適した超解像メソッドのリストを取得（OpenCVメソッドを除外）
        
        Returns:
            List[SRMethod]: 実運用に適したメソッドのリスト
        """
        all_methods = self.get_available_methods()
        production_methods = []
        
        # OpenCV以外のメソッドを抽出
        for method in all_methods:
            method_name = method.name.lower()
            if not method_name.startswith('opencv'):
                production_methods.append(method)
        
        return production_methods
    
    @staticmethod
    def is_cuda_available() -> bool:
        """CUDAが利用可能かどうかを確認"""
        return is_cuda_available()
    
    @staticmethod
    def get_gpu_info() -> Dict[str, Any]:
        """GPU情報を取得"""
        return get_gpu_info()
