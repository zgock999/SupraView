"""
超解像処理をバックグラウンドで実行するためのワーカークラス
"""
import os
import time
import cv2
import numpy as np
from typing import Dict, Any, Optional, Union, Tuple
import threading
import queue
from PySide6.QtCore import QObject, Signal, QThread, QMutex

from sr.sr_base import SRMethod, SRResult
from app.viewer.superres.sr_manager import SuperResolutionManager

class SuperResolutionWorker(QThread):
    """超解像処理を実行するワーカースレッド"""
    
    # シグナル定義
    progress_signal = Signal(int)        # 進捗状況
    result_signal = Signal(object)       # 処理結果
    error_signal = Signal(str)           # エラーメッセージ
    completed_signal = Signal()          # 処理完了
    
    def __init__(self, parent=None):
        """初期化"""
        super().__init__(parent)
        
        # 超解像マネージャー
        self._sr_manager = SuperResolutionManager()
        
        # 処理用変数
        self._image = None
        self._method = None
        self._scale = 2
        self._options = None
        
        # 処理フラグ
        self._is_processing = False
        self._abort_requested = False
        
        # タスクキュー
        self._task_queue = queue.Queue()
        self._mutex = QMutex()
    
    def setup(self, method: SRMethod, scale: int, options: Dict[str, Any] = None) -> bool:
        """
        超解像モデルをセットアップ
        
        Args:
            method: 使用する超解像メソッド
            scale: 拡大倍率
            options: 初期化オプション
            
        Returns:
            bool: セットアップに成功したかどうか
        """
        # 処理中は設定を変更しない
        if self._is_processing:
            self.error_signal.emit("処理中は設定を変更できません")
            return False
            
        self._mutex.lock()
        try:
            self._method = method
            self._scale = scale
            self._options = options or {}
            
            # モデルを初期化
            success = self._sr_manager.initialize(method, scale, self._options)
            if not success:
                self.error_signal.emit(f"モデル初期化に失敗しました: {method.name}")
                return False
            
            return True
            
        except Exception as e:
            self.error_signal.emit(f"セットアップエラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            self._mutex.unlock()
    
    def process_image(self, image: np.ndarray, options: Dict[str, Any] = None) -> bool:
        """
        画像処理をキューに追加
        
        Args:
            image: 処理する画像
            options: 処理オプション
            
        Returns:
            bool: キューへの追加に成功したかどうか
        """
        if image is None:
            self.error_signal.emit("画像がありません")
            return False
            
        # タスクをキューに追加
        self._task_queue.put((image.copy(), options))
        
        # スレッドが実行中でなければ開始
        if not self.isRunning():
            self.start()
            
        return True
    
    def run(self):
        """スレッドのメイン処理"""
        while True:
            try:
                # タスクキューからタスクを取得
                if self._task_queue.empty():
                    break
                    
                image, options = self._task_queue.get(block=False)
                
                # 中断リクエストを確認
                if self._abort_requested:
                    break
                
                # 処理フラグを設定
                self._is_processing = True
                
                # モデルが初期化されていない場合は初期化
                if not self._sr_manager.is_initialized:
                    if not self._sr_manager.initialize(self._method, self._scale, self._options):
                        self.error_signal.emit("モデル初期化に失敗しました")
                        continue
                
                # 進捗状況を更新
                self.progress_signal.emit(10)
                
                # オプションを結合
                process_options = self._options.copy() if self._options else {}
                if options:
                    process_options.update(options)
                
                # 処理実行
                self.progress_signal.emit(30)
                result = self._sr_manager.process(image, process_options)
                
                # 結果チェック
                if result is None:
                    self.error_signal.emit("処理に失敗しました")
                    continue
                
                # 結果を通知
                self.progress_signal.emit(100)
                self.result_signal.emit(result)
                
            except queue.Empty:
                # キューが空の場合はループを抜ける
                break
                
            except Exception as e:
                self.error_signal.emit(f"処理エラー: {str(e)}")
                import traceback
                traceback.print_exc()
                
            finally:
                # 処理完了フラグをリセット
                self._is_processing = False
                
                # タスクキューが空でなければ次のタスクを処理
                if not self._task_queue.empty():
                    continue
                else:
                    # タスクキューが空の場合は完了を通知
                    self.completed_signal.emit()
                    break
    
    def abort(self):
        """処理の中断をリクエスト"""
        self._abort_requested = True
        
        # キューをクリア
        while not self._task_queue.empty():
            try:
                self._task_queue.get(block=False)
            except queue.Empty:
                break
    
    def cleanup(self):
        """リソースを解放"""
        self.abort()
        self._sr_manager.cleanup()
    
    @property
    def is_processing(self) -> bool:
        """処理中かどうか"""
        return self._is_processing
