"""
汎用ワーカースレッドモジュール

multiprocessを使用して処理を行うワーカースレッドと実行キュー管理機能を提供します。
"""

from .worker import Worker, WorkerStatus
from .queue import WorkerQueue
from .events import (
    WorkerEvent, EventQueue, get_event_queue, publish_event, 
    subscribe_to_events, unsubscribe_from_events,
    start_event_processing, stop_event_processing
)

# インターフェース関数
def create_worker(target, args=(), kwargs=None, callback=None, callback_interval=1.0, 
                 publish_events=True):
    """
    新しいワーカーを作成する
    
    Args:
        target: 実行する関数
        args: 関数に渡す位置引数のタプル
        kwargs: 関数に渡すキーワード引数の辞書
        callback: 進捗報告用コールバック関数
        callback_interval: コールバック呼び出し間隔（秒）
        publish_events: イベントを発行するかどうか
        
    Returns:
        Worker: 作成されたワーカーインスタンス
    """
    return Worker(target, args, kwargs, callback, callback_interval, publish_events)

def create_queue(max_workers=None):
    """
    新しいワーカーキューを作成する
    
    Args:
        max_workers: 同時実行できるワーカーの最大数（None=制限なし）
        
    Returns:
        WorkerQueue: 作成されたワーカーキューインスタンス
    """
    return WorkerQueue(max_workers)

def initialize_event_system(auto_start=True):
    """
    イベントシステムを初期化する
    
    Args:
        auto_start: イベント処理を自動的に開始するかどうか
        
    Returns:
        EventQueue: イベントキューインスタンス
    """
    event_queue = get_event_queue()
    if auto_start:
        start_event_processing()
    return event_queue

__all__ = [
    # ワーカー関連
    'Worker', 'WorkerStatus', 'WorkerQueue',
    'create_worker', 'create_queue',
    
    # イベント関連
    'WorkerEvent', 'EventQueue', 
    'get_event_queue', 'publish_event',
    'subscribe_to_events', 'unsubscribe_from_events',
    'start_event_processing', 'stop_event_processing',
    'initialize_event_system'
]
