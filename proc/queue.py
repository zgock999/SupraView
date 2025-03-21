"""
実行キュー管理モジュール

複数のワーカースレッドの実行順序と並行実行数を管理します。
"""

import threading
import time
from collections import deque
from typing import List, Optional, Dict

from .worker import Worker, WorkerStatus

class WorkerQueue:
    """
    ワーカースレッドの実行キューを管理するクラス
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        ワーカーキューを初期化
        
        Args:
            max_workers: 同時実行可能なワーカーの最大数（None=制限なし）
        """
        self.max_workers = max_workers
        self._queue = deque()  # 待機中のワーカー
        self._active = {}      # 実行中のワーカー (id -> worker)
        self._results = {}     # 完了したワーカーの結果 (id -> result)
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._shutdown = False
        
        # ワーカー管理スレッド
        self._manager_thread = threading.Thread(
            target=self._manage_workers,
            daemon=True
        )
        self._manager_thread.start()
    
    def submit(self, worker: Worker) -> str:
        """
        ワーカーをキューに追加
        
        Args:
            worker: 追加するワーカー
            
        Returns:
            str: ワーカーID
        """
        with self._lock:
            if self._shutdown:
                raise RuntimeError("キューはシャットダウン中です")
            
            self._queue.append(worker)
            self._condition.notify_all()  # 変更: notify_all()を使用して確実に通知
            return worker.id
    
    def submit_all(self, workers: List[Worker]) -> List[str]:
        """
        複数のワーカーをキューに追加
        
        Args:
            workers: 追加するワーカーのリスト
            
        Returns:
            List[str]: ワーカーIDのリスト
        """
        worker_ids = []
        with self._lock:
            if self._shutdown:
                raise RuntimeError("キューはシャットダウン中です")
            
            for worker in workers:
                self._queue.append(worker)
                worker_ids.append(worker.id)
            
            self._condition.notify_all()  # 変更: notify_all()を使用して確実に通知
            return worker_ids
    
    def cancel(self, worker_id: str) -> bool:
        """
        指定したワーカーをキャンセル
        
        Args:
            worker_id: キャンセルするワーカーのID
            
        Returns:
            bool: キャンセルできたかどうか
        """
        with self._lock:
            # キュー内のワーカーを探す
            for i, worker in enumerate(self._queue):
                if worker.id == worker_id:
                    worker.status = WorkerStatus.CANCELLED
                    self._queue.remove(worker)
                    self._results[worker_id] = (WorkerStatus.CANCELLED, None)
                    self._condition.notify_all()  # 変更: 状態変化を通知
                    return True
            
            # 実行中のワーカーを探す
            if worker_id in self._active:
                worker = self._active[worker_id]
                result = worker.cancel()
                self._condition.notify_all()  # 変更: 状態変化を通知
                return result
            
            return False
    
    def cancel_all(self) -> int:
        """
        すべてのワーカーをキャンセル
        
        Returns:
            int: キャンセルされたワーカーの数
        """
        cancelled_count = 0
        with self._lock:
            # キュー内のワーカーをキャンセル
            for worker in list(self._queue):
                worker.status = WorkerStatus.CANCELLED
                self._results[worker.id] = (WorkerStatus.CANCELLED, None)
                cancelled_count += 1
            
            self._queue.clear()
            
            # 実行中のワーカーをキャンセル
            for worker in self._active.values():
                if worker.cancel():
                    cancelled_count += 1
            
            self._condition.notify_all()  # 変更: 状態変化を通知
        
        return cancelled_count
    
    def get_result(self, worker_id: str, wait: bool = True, timeout: Optional[float] = None) -> tuple:
        """
        ワーカーの結果を取得
        
        Args:
            worker_id: ワーカーID
            wait: 完了するまで待機するかどうか
            timeout: タイムアウト時間（秒）
            
        Returns:
            tuple: (status, result) - 状態と結果のタプル
        """
        if not wait:
            with self._lock:
                if worker_id in self._results:
                    return self._results[worker_id]
                
                # キュー内または実行中のワーカーを探す
                for worker in self._queue:
                    if worker.id == worker_id:
                        return (worker.status, None)
                
                if worker_id in self._active:
                    worker = self._active[worker_id]
                    return (worker.status, worker.get_result())  # 変更: 結果も取得
                
                return (None, None)  # ワーカーが見つからない
        
        # 完了するまで待機
        end_time = None if timeout is None else time.time() + timeout
        
        while True:
            with self._lock:
                if worker_id in self._results:
                    return self._results[worker_id]
                
                # キュー内または実行中のワーカーを探す
                worker_found = False
                for worker in self._queue:
                    if worker.id == worker_id:
                        worker_found = True
                        break
                
                if not worker_found and worker_id not in self._active:
                    return (None, None)  # ワーカーが見つからない
                
                # タイムアウトチェック
                if timeout is not None:
                    remaining = end_time - time.time()
                    if remaining <= 0:
                        if worker_id in self._active:
                            worker = self._active[worker_id]
                            return (worker.status, worker.get_result())  # 変更: 結果も取得
                        return (WorkerStatus.PENDING, None)
                    wait_time = remaining
                else:
                    wait_time = None
            
            # 通知を待機
            with self._condition:
                self._condition.wait(wait_time)
    
    def get_status(self) -> Dict:
        """
        キューのステータスを取得
        
        Returns:
            Dict: キューの状態情報
        """
        with self._lock:
            return {
                'pending': len(self._queue),
                'active': len(self._active),
                'completed': len(self._results),
                'max_workers': self.max_workers
            }
    
    def shutdown(self, wait: bool = True, cancel_pending: bool = False) -> None:
        """
        キューをシャットダウンする
        
        Args:
            wait: 実行中のワーカーが完了するまで待機するかどうか
            cancel_pending: 待機中のワーカーをキャンセルするかどうか
        """
        with self._lock:
            self._shutdown = True
            
            if cancel_pending:
                # 待機中のワーカーをすべてキャンセル
                for worker in list(self._queue):
                    worker.status = WorkerStatus.CANCELLED
                    self._results[worker.id] = (WorkerStatus.CANCELLED, None)
                
                self._queue.clear()
            
            # 条件変数に通知して管理スレッドを終了させる
            self._condition.notify_all()
        
        if wait:
            # 実行中のワーカーがすべて完了するまで待機
            active_workers = []
            with self._lock:
                active_workers = list(self._active.values())
            
            for worker in active_workers:
                worker.join()
    
    def _manage_workers(self) -> None:
        """
        ワーカーを管理するスレッド
        """
        while not self._shutdown:
            need_notification = False  # 状態変化があるかどうかを追跡
            
            # 完了したワーカーを確認して結果を保存
            with self._lock:
                for worker_id in list(self._active.keys()):
                    worker = self._active[worker_id]
                    status = worker.get_status()
                    if status in (WorkerStatus.COMPLETED, WorkerStatus.CANCELLED, WorkerStatus.ERROR):
                        # 完了したワーカーを結果リストに移動
                        self._results[worker_id] = (status, worker.get_result())
                        del self._active[worker_id]
                        need_notification = True  # 状態が変化した
                
                # 新しいワーカーを開始
                while self._queue and (self.max_workers is None or len(self._active) < self.max_workers):
                    worker = self._queue.popleft()
                    self._active[worker.id] = worker
                    worker.start()
                    need_notification = True  # 状態が変化した
                
                # 状態が変化した場合は条件変数に通知
                if need_notification:
                    self._condition.notify_all()
            
            # 短い待機（ロックの外で）
            time.sleep(0.1)
            
            # 条件変数でも待機（効率的なスレッド制御のため）
            with self._condition:
                # キューが空で、実行中ワーカーがない場合は、通知があるまで待機
                if not self._queue and not self._active and not self._shutdown:
                    self._condition.wait(1.0)
