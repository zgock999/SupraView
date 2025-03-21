"""
ワーカーイベント管理モジュール

ワーカープロセスから発行されるイベントを処理するための機能を提供します。
"""

import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union
from .worker import WorkerStatus

class WorkerEvent:
    """ワーカーから発行されるイベントを表現するクラス"""
    
    def __init__(self, worker_id: str, target_name: str, status: WorkerStatus, 
                 result: Any = None, args: tuple = (), kwargs: Optional[Dict] = None):
        """
        ワーカーイベントを初期化
        
        Args:
            worker_id: イベントを発行したワーカーのID
            target_name: 実行されたターゲット関数の名前
            status: イベント発行時のワーカーの状態
            result: ワーカーの処理結果
            args: ワーカーに渡された位置引数
            kwargs: ワーカーに渡されたキーワード引数
        """
        self.worker_id = worker_id
        self.target_name = target_name
        self.status = status
        self.result = result
        self.args = args
        self.kwargs = kwargs or {}
        self.timestamp = time.time()
    
    def __str__(self):
        """イベントの文字列表現"""
        return f"WorkerEvent(id={self.worker_id}, status={self.status.name}, target={self.target_name})"

class EventQueue:
    """ワーカーイベントを管理するキュークラス"""
    
    def __init__(self):
        """イベントキューを初期化"""
        self._queue = queue.Queue()
        self._listeners = []
        self._lock = threading.RLock()
        self._running = False
        self._process_thread = None
    
    def publish(self, event: WorkerEvent) -> None:
        """
        イベントをキューに追加
        
        Args:
            event: 追加するワーカーイベント
        """
        self._queue.put(event)
    
    def subscribe(self, callback: Callable[[WorkerEvent], None]) -> None:
        """
        イベントリスナーを登録
        
        Args:
            callback: イベント発生時に呼び出されるコールバック関数
        """
        with self._lock:
            self._listeners.append(callback)
    
    def unsubscribe(self, callback: Callable[[WorkerEvent], None]) -> bool:
        """
        イベントリスナーを登録解除
        
        Args:
            callback: 登録解除するコールバック関数
            
        Returns:
            bool: 登録解除に成功したかどうか
        """
        with self._lock:
            try:
                self._listeners.remove(callback)
                return True
            except ValueError:
                return False
    
    def start_processing(self, daemon: bool = True) -> None:
        """
        イベント処理スレッドを開始
        
        Args:
            daemon: デーモンスレッドとして実行するかどうか
        """
        if self._running:
            return
        
        self._running = True
        self._process_thread = threading.Thread(
            target=self._process_events,
            daemon=daemon
        )
        self._process_thread.start()
    
    def stop_processing(self, timeout: Optional[float] = None) -> bool:
        """
        イベント処理スレッドを停止
        
        Args:
            timeout: 処理スレッドの終了を待機する最大時間（秒）
            
        Returns:
            bool: 処理スレッドが正常に終了したかどうか
        """
        if not self._running:
            return True
        
        self._running = False
        
        if self._process_thread and self._process_thread.is_alive():
            self._process_thread.join(timeout)
            return not self._process_thread.is_alive()
        
        return True
    
    def get_events(self, max_events: int = 10, timeout: Optional[float] = 0.1) -> List[WorkerEvent]:
        """
        キューからイベントを取得
        
        Args:
            max_events: 取得する最大イベント数
            timeout: 待機する最大時間（秒）
            
        Returns:
            List[WorkerEvent]: 取得したイベントのリスト
        """
        events = []
        try:
            # 最初のイベントは指定されたタイムアウトで待機
            events.append(self._queue.get(timeout=timeout))
            
            # その他のイベントは待機せずに取得できるだけ取得
            for _ in range(max_events - 1):
                try:
                    events.append(self._queue.get_nowait())
                except queue.Empty:
                    break
        except queue.Empty:
            pass
        
        return events
    
    def _process_events(self) -> None:
        """イベントを処理するスレッドのメイン処理"""
        while self._running:
            try:
                # イベントを取得（タイムアウト付き）
                event = self._queue.get(timeout=0.5)
                
                # リスナーに通知
                with self._lock:
                    listeners = list(self._listeners)
                
                for listener in listeners:
                    try:
                        listener(event)
                    except Exception as e:
                        print(f"イベントリスナーでエラーが発生しました: {e}")
                
                # 処理完了を通知
                self._queue.task_done()
            
            except queue.Empty:
                # タイムアウト - 次のループへ
                continue
            
            except Exception as e:
                print(f"イベント処理中にエラーが発生しました: {e}")
                continue

# グローバルイベントキュー（シングルトン）
global_event_queue = EventQueue()

# ユーティリティ関数
def get_event_queue() -> EventQueue:
    """グローバルイベントキューを取得"""
    return global_event_queue

def publish_event(event: WorkerEvent) -> None:
    """イベントをグローバルキューに発行"""
    global_event_queue.publish(event)

def subscribe_to_events(callback: Callable[[WorkerEvent], None]) -> None:
    """グローバルイベントキューにリスナーを登録"""
    global_event_queue.subscribe(callback)

def unsubscribe_from_events(callback: Callable[[WorkerEvent], None]) -> bool:
    """グローバルイベントキューからリスナーを登録解除"""
    return global_event_queue.unsubscribe(callback)

def start_event_processing(daemon: bool = True) -> None:
    """グローバルイベントキューの処理を開始"""
    global_event_queue.start_processing(daemon)

def stop_event_processing(timeout: Optional[float] = None) -> bool:
    """グローバルイベントキューの処理を停止"""
    return global_event_queue.stop_processing(timeout)
