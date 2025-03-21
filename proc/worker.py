"""
ワーカースレッド実装モジュール

定期的なコールバック呼び出しとキャンセル機能を備えたワーカースレッドを提供します。
"""

import time
import multiprocessing
import threading
import enum
import uuid
import traceback
import pickle
import inspect
import functools
from typing import Any, Callable, Dict, Optional, Tuple, Union

class WorkerStatus(enum.Enum):
    """ワーカーの状態を表す列挙型"""
    PENDING = "pending"     # 実行待ち
    RUNNING = "running"     # 実行中
    COMPLETED = "completed" # 完了
    CANCELLED = "cancelled" # キャンセル済み
    ERROR = "error"         # エラー発生

# 問題のあるパッケージをインポートしないようにするフラグ
_SAFE_IMPORT = True

def _safe_import(module_name):
    """安全にモジュールをインポートするユーティリティ関数"""
    if not _SAFE_IMPORT:
        return None
    
    try:
        import importlib
        return importlib.import_module(module_name)
    except Exception as e:
        print(f"モジュール '{module_name}' のインポートに失敗しました: {e}")
        return None

def _is_picklable(obj):
    """オブジェクトがピクル化可能かどうかを確認する"""
    try:
        pickle.dumps(obj)
        return True
    except Exception:
        return False

def _wrap_target_function(target_func, result_queue, cancel_event, args=(), kwargs=None):
    """
    ターゲット関数を実行してその結果をキューに戻す
    
    Args:
        target_func: 実行する関数
        result_queue: 結果を返すためのキュー
        cancel_event: キャンセル状態を通知するイベント
        args: 関数に渡す位置引数
        kwargs: 関数に渡すキーワード引数
    """
    if kwargs is None:
        kwargs = {}
    
    try:
        # キャンセル状態の確認方法を関数に提供するための関数
        def is_cancelled():
            return cancel_event.is_set()
        
        # is_cancelledを追加の引数として渡す（指定されていない場合）
        if 'is_cancelled' not in kwargs:
            kwargs['is_cancelled'] = is_cancelled
        
        # 処理の実行
        result = target_func(*args, **kwargs)
        
        # ジェネレータの場合はリストに変換（シリアライズ可能にする）
        if hasattr(result, '__iter__') and hasattr(result, '__next__'):
            try:
                result = list(result)
            except Exception as e:
                result_queue.put(('error', {
                    'error': f"イテレータ処理中のエラー: {e}",
                    'traceback': traceback.format_exc()
                }))
                return
        
        # キャンセルされたかチェック
        if cancel_event.is_set():
            result_queue.put(('cancelled', None))
        else:
            result_queue.put(('completed', result))
    
    except Exception as e:
        result_queue.put(('error', {
            'error': str(e),
            'traceback': traceback.format_exc()
        }))
    
    # キューが確実に処理されるように小さな遅延を追加
    time.sleep(0.1)

class Worker:
    """
    定期的にコールバックを返すことができ、キャンセル可能なワーカースレッド
    """
    
    def __init__(self, target: Callable, args: Tuple = (), kwargs: Optional[Dict] = None, 
                 callback: Optional[Callable] = None, callback_interval: float = 1.0,
                 publish_events: bool = True):
        """
        ワーカースレッドを初期化
        
        Args:
            target: 実行する関数
            args: 関数に渡す位置引数のタプル
            kwargs: 関数に渡すキーワード引数の辞書
            callback: 進捗報告用コールバック関数(worker, status, result)の形
            callback_interval: コールバック呼び出し間隔（秒）
            publish_events: イベントを発行するかどうか
        """
        self.id = str(uuid.uuid4())
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.callback = callback
        self.callback_interval = callback_interval
        self.publish_events = publish_events
        
        # ピクル化不可能なオブジェクトをチェック
        if not self._check_picklability():
            raise ValueError("ターゲット関数または引数がピクル化できません")
        
        self.status = WorkerStatus.PENDING
        self.result = None
        self.error = None
        self.start_time = None
        self.end_time = None
        
        # プロセス間通信用のキュー
        self._result_queue = multiprocessing.Queue()
        self._cancel_event = multiprocessing.Event()
        
        # 実際のプロセス
        self._process = None
        self._callback_thread = None
        self._running = False
    
    def _check_picklability(self):
        """ターゲット関数と引数がピクル化可能かどうかをチェック"""
        try:
            # ターゲット関数のチェック
            if not _is_picklable(self.target):
                print(f"警告: ターゲット関数 '{self.target.__name__}' はピクル化できません")
                return False
            
            # 位置引数のチェック
            for i, arg in enumerate(self.args):
                if not _is_picklable(arg):
                    print(f"警告: 引数 {i} はピクル化できません: {type(arg)}")
                    return False
            
            # キーワード引数のチェック
            for key, value in self.kwargs.items():
                if not _is_picklable(value):
                    print(f"警告: キーワード引数 '{key}' はピクル化できません: {type(value)}")
                    return False
            
            return True
        except Exception as e:
            print(f"ピクル化チェック中にエラーが発生しました: {e}")
            return False
    
    def start(self):
        """ワーカープロセスを開始する"""
        if self.status != WorkerStatus.PENDING:
            return False
            
        self.start_time = time.time()
        self.status = WorkerStatus.RUNNING
        self._running = True
        
        try:
            # 関数をラップすることでマルチプロセスのピクル化問題を回避
            self._process = multiprocessing.Process(
                target=_wrap_target_function,
                args=(self.target, self._result_queue, self._cancel_event, 
                      self.args, self.kwargs)
            )
            self._process.daemon = True
            self._process.start()
            
            # コールバック用のスレッドを開始
            if self.callback or self.publish_events:
                self._callback_thread = threading.Thread(
                    target=self._callback_worker,
                    daemon=True
                )
                self._callback_thread.start()
            
            # イベント発行（ステータス変更）
            self._publish_status_event()
            
            return True
        except Exception as e:
            self.status = WorkerStatus.ERROR
            self.error = {
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            print(f"ワーカー起動エラー: {e}")
            return False
    
    def cancel(self):
        """ワーカーの実行をキャンセルする"""
        if self.status != WorkerStatus.RUNNING:
            return False
            
        self._cancel_event.set()
        return True
    
    def join(self, timeout=None):
        """
        ワーカーの完了を待機する
        
        Args:
            timeout: タイムアウト時間（秒）
            
        Returns:
            bool: ワーカーが完了したかどうか
        """
        if self._process is None:
            return True
            
        self._process.join(timeout)
        return not self._process.is_alive()
    
    def get_status(self):
        """現在の状態を取得する"""
        return self.status
    
    def get_result(self):
        """処理結果を取得する"""
        return self.result
    
    def _callback_worker(self):
        """
        コールバック関数を定期的に呼び出すスレッド
        """
        while self._running and self.status == WorkerStatus.RUNNING:
            # コールバック関数を呼び出す
            if self.callback:
                try:
                    self.callback(self, self.status, None)
                except Exception as e:
                    print(f"コールバック実行中にエラーが発生しました: {e}")
            
            # イベント発行（進捗）
            if self.publish_events:
                self._publish_progress_event()
            
            # 結果キューをチェック
            try:
                status, result = self._result_queue.get(timeout=self.callback_interval)
                self._running = False
                
                # 結果に基づいて状態を更新
                if status == 'completed':
                    self.status = WorkerStatus.COMPLETED
                    self.result = result
                elif status == 'cancelled':
                    self.status = WorkerStatus.CANCELLED
                    self.result = None
                elif status == 'error':
                    self.status = WorkerStatus.ERROR
                    self.error = result
                    self.result = None
                
                self.end_time = time.time()
                
                # イベント発行（ステータス変更）
                if self.publish_events:
                    self._publish_status_event()
                
                # 最終コールバック
                if self.callback:
                    try:
                        self.callback(self, self.status, self.result)
                    except Exception as e:
                        print(f"完了コールバック実行中にエラーが発生しました: {e}")
                
                break
                
            except (multiprocessing.queues.Empty, EOFError):
                # タイムアウトまたはキューが閉じられた - 次のループへ
                continue
    
    def _publish_status_event(self):
        """ステータス変更イベントを発行"""
        if not self.publish_events:
            return
        
        try:
            # 安全にモジュールをインポート
            events_module = _safe_import("proc.events")
            if events_module:
                # 動的インポート
                event = events_module.WorkerEvent(
                    worker_id=self.id,
                    target_name=self.target.__name__,
                    status=self.status,
                    result=self.result,
                    args=self.args,
                    kwargs=self.kwargs
                )
                
                events_module.publish_event(event)
        except Exception as e:
            print(f"イベント発行中にエラーが発生しました: {e}")
    
    def _publish_progress_event(self):
        """進捗イベントを発行"""
        if not self.publish_events:
            return
        
        try:
            # 安全にモジュールをインポート
            events_module = _safe_import("proc.events")
            if events_module:
                # 動的インポート
                event = events_module.WorkerEvent(
                    worker_id=self.id,
                    target_name=self.target.__name__,
                    status=WorkerStatus.RUNNING,
                    result=None,
                    args=self.args,
                    kwargs=self.kwargs
                )
                
                events_module.publish_event(event)
        except Exception as e:
            print(f"進捗イベント発行中にエラーが発生しました: {e}")
