"""
ワーカースレッドサービス

バックグラウンドでタスクを実行するためのQt対応ワーカースレッドフレームワーク。
サムネイル生成などの重い処理をUIスレッドから分離するために使用します。
"""

import os
import sys
import time
import traceback
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ロギングユーティリティをインポート
from logutils import log_print, DEBUG, INFO, WARNING, ERROR

try:
    from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)


class WorkerSignals(QObject):
    """
    ワーカースレッドで使用するシグナル定義
    
    シグナル:
        started: タスク開始時に発行
        finished: タスク完了時に発行（成功・失敗にかかわらず）
        error: エラー発生時に例外情報を含めて発行
        result: タスク成功時に結果を含めて発行
        progress: 進捗情報を通知
    """
    started = Signal(str)  # タスクID
    finished = Signal(str)  # タスクID
    error = Signal(str, tuple)  # タスクID, (例外タイプ, 例外値, トレースバック)
    result = Signal(str, object)  # タスクID, 結果
    progress = Signal(str, int, str)  # タスクID, 進捗率, メッセージ


class Worker(QRunnable):
    """
    タスクを実行するワーカークラス
    
    QRunnableを継承し、QThreadPoolで実行できる形式で、
    任意の関数を実行し結果を通知します。
    """
    
    def __init__(
        self, 
        fn: Callable, 
        *args, 
        **kwargs
    ):
        """
        ワーカーの初期化
        
        Args:
            fn: 実行する関数
            *args, **kwargs: 関数に渡す引数
        """
        super(Worker, self).__init__()
        
        # タスクの一意なIDを生成
        self.task_id = str(uuid.uuid4())
        
        # 実行する関数と引数
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        
        # キーワード引数から進捗コールバックを取得（あれば）
        self.progress_callback = kwargs.pop('progress_callback', None)
        
        # シグナルオブジェクト
        self.signals = WorkerSignals()
        
        # コールバック設定（オプション）
        self.on_started = None
        self.on_finished = None
        self.on_error = None
        self.on_result = None
        self.on_progress = None
        
        # キャンセルフラグ
        self.is_cancelled = False
        
        # デバッグモードフラグ
        self.debug_mode = kwargs.pop('debug_mode', False)
    
    def cancel(self):
        """タスクをキャンセルする（実際の停止は実行関数の協力が必要）"""
        self.is_cancelled = True
    
    def progress_fn(self, percent: int, message: str = ""):
        """
        進捗を通知する関数（処理関数内から呼び出される）
        
        Args:
            percent: 進捗率（0-100）
            message: 進捗メッセージ（オプション）
        """
        if self.debug_mode:
            log_print(DEBUG, f"タスク {self.task_id} 進捗: {percent}% - {message}")
            
        # シグナルで進捗を通知
        self.signals.progress.emit(self.task_id, percent, message)
        
        # 直接コールバックがあれば呼び出す
        if self.progress_callback is not None:
            self.progress_callback(percent, message)
        
        # on_progressコールバックがあれば呼び出す
        if self.on_progress is not None:
            self.on_progress(self.task_id, percent, message)
    
    @Slot()
    def run(self):
        """
        QRunnableの実行メソッド
        
        スレッドプールにより新しいスレッドで実行され、
        指定された関数を実行し、結果を通知します。
        """
        # タスク開始を通知
        self.signals.started.emit(self.task_id)
        
        if self.on_started is not None:
            self.on_started(self.task_id)
        
        if self.debug_mode:
            log_print(DEBUG, f"タスク {self.task_id} 開始")
        
        # タスク開始時刻
        start_time = time.time()
        
        try:
            # 進捗関数をキーワード引数に追加
            self.kwargs['progress_callback'] = self.progress_fn
            self.kwargs['is_cancelled'] = lambda: self.is_cancelled
            
            # 関数を実行し結果を取得
            result = self.fn(*self.args, **self.kwargs)
            
            # 実行時間
            execution_time = time.time() - start_time
            
            if self.debug_mode:
                log_print(DEBUG, f"タスク {self.task_id} 正常終了 - 実行時間: {execution_time:.2f}秒")
            
            # キャンセルされていない場合のみ結果を通知
            if not self.is_cancelled:
                # 結果を通知
                self.signals.result.emit(self.task_id, result)
                
                if self.on_result is not None:
                    self.on_result(self.task_id, result)
            else:
                if self.debug_mode:
                    log_print(DEBUG, f"タスク {self.task_id} はキャンセルされました")
                
        except Exception as e:
            # 実行時間
            execution_time = time.time() - start_time
            
            # 例外情報を取得
            error_type = type(e)
            error_value = str(e)
            error_traceback = traceback.format_exc()
            
            log_print(ERROR, f"タスク {self.task_id} 実行中にエラーが発生しました: {error_value}")
            log_print(ERROR, error_traceback)
            
            # エラー情報を通知
            error_info = (error_type, error_value, error_traceback)
            self.signals.error.emit(self.task_id, error_info)
            
            if self.on_error is not None:
                self.on_error(self.task_id, error_info)
        
        finally:
            # タスク終了を通知（成功・失敗にかかわらず）
            self.signals.finished.emit(self.task_id)
            
            if self.on_finished is not None:
                self.on_finished(self.task_id)
            
            if self.debug_mode:
                log_print(DEBUG, f"タスク {self.task_id} 終了処理完了")


class WorkerManager:
    """
    ワーカーの管理を行うマネージャクラス
    
    タスクの追加、キャンセル、進捗追跡などを管理します。
    """
    
    def __init__(self, max_threads: int = None, debug_mode: bool = False):
        """
        ワーカーマネージャの初期化
        
        Args:
            max_threads: 最大スレッド数（Noneの場合はQThreadPoolのデフォルト値を使用）
            debug_mode: デバッグモードフラグ
        """
        # スレッドプールの取得と設定
        self.thread_pool = QThreadPool.globalInstance()
        
        if max_threads is not None:
            self.thread_pool.setMaxThreadCount(max_threads)
        
        # アクティブな全ワーカーを管理するディクショナリ
        self.workers: Dict[str, Worker] = {}
        
        # デバッグモード設定
        self.debug_mode = debug_mode
        
        # ロギング
        count = self.thread_pool.maxThreadCount()
        log_print(INFO, f"WorkerManager初期化: 最大{count}スレッド")
    
    def start_task(
        self, 
        fn: Callable, 
        *args, 
        on_started: Callable[[str], None] = None,
        on_finished: Callable[[str], None] = None,
        on_error: Callable[[str, tuple], None] = None,
        on_result: Callable[[str, Any], None] = None,
        on_progress: Callable[[str, int, str], None] = None,
        **kwargs
    ) -> str:
        """
        新しいタスクをスレッドプールで開始する
        
        Args:
            fn: 実行する関数
            *args: 関数に渡す位置引数
            on_started: タスク開始時のコールバック (task_id)
            on_finished: タスク終了時のコールバック (task_id)
            on_error: エラー発生時のコールバック (task_id, error_info)
            on_result: 結果受信時のコールバック (task_id, result)
            on_progress: 進捗通知時のコールバック (task_id, percent, message)
            **kwargs: 関数に渡すキーワード引数
            
        Returns:
            str: タスクID（キャンセルなどに使用）
        """
        # デバッグモードをキーワード引数に追加
        kwargs['debug_mode'] = self.debug_mode
        
        # ワーカーインスタンスの作成
        worker = Worker(fn, *args, **kwargs)
        
        # コールバックの設定
        worker.on_started = on_started
        worker.on_finished = on_finished
        worker.on_error = on_error
        worker.on_result = on_result
        worker.on_progress = on_progress
        
        # ワーカー管理用シグナル接続
        worker.signals.finished.connect(lambda task_id: self._remove_worker(task_id))
        
        # ワーカーを保存
        task_id = worker.task_id
        self.workers[task_id] = worker
        
        if self.debug_mode:
            log_print(DEBUG, f"タスク {task_id} をキューに追加")
        
        # スレッドプールでワーカーを実行
        self.thread_pool.start(worker)
        
        return task_id
    
    def cancel_task(self, task_id: str) -> bool:
        """
        指定したタスクをキャンセル
        
        Args:
            task_id: キャンセルするタスクのID
            
        Returns:
            bool: タスクが見つかりキャンセルフラグを設定できた場合はTrue
        """
        if task_id in self.workers:
            worker = self.workers[task_id]
            worker.cancel()
            
            if self.debug_mode:
                log_print(DEBUG, f"タスク {task_id} をキャンセル")
            
            return True
        
        return False
    
    def cancel_all_tasks(self):
        """すべてのタスクをキャンセル"""
        task_ids = list(self.workers.keys())
        
        for task_id in task_ids:
            self.cancel_task(task_id)
        
        if self.debug_mode:
            log_print(DEBUG, f"全{len(task_ids)}個のタスクをキャンセル")
        
        # 確実にワーカーリストをクリアする（改善点）
        if len(self.workers) > 0:
            log_print(WARNING, f"キャンセル後も {len(self.workers)} 個のタスクが残っています。強制クリアします")
            self.workers.clear()
    
    def _remove_worker(self, task_id: str):
        """
        完了したワーカーを管理リストから削除
        
        Args:
            task_id: 完了したタスクのID
        """
        if task_id in self.workers:
            del self.workers[task_id]
            
            if self.debug_mode:
                log_print(DEBUG, f"タスク {task_id} を管理リストから削除（残り{len(self.workers)}個）")
    
    def active_task_count(self) -> int:
        """
        現在アクティブなタスク数を取得
        
        Returns:
            int: アクティブなタスク数
        """
        return len(self.workers)
    
    def wait_for_all(self, msecs: int = -1):
        """
        すべてのスレッドの完了を待機
        
        Args:
            msecs: 待機する最大ミリ秒数（-1の場合は無期限）
            
        Returns:
            bool: タイムアウト前にすべてのスレッドが完了した場合はTrue
        """
        return self.thread_pool.waitForDone(msecs)


# 単体テスト用コード
if __name__ == "__main__":
    import time
    from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
    
    # テスト関数
    def example_task(n, progress_callback=None, is_cancelled=None):
        """進捗報告を含むサンプルタスク"""
        result = 0
        
        for i in range(n):
            if is_cancelled and is_cancelled():
                return "キャンセルされました"
                
            # 進捗報告
            if progress_callback:
                percent = int((i + 1) * 100 / n)
                progress_callback(percent, f"ステップ {i+1}/{n} 処理中...")
            
            # 重い処理をシミュレート
            time.sleep(0.5)
            result += i
        
        return result
    
    # サンプルアプリケーション
    class TestApp(QMainWindow):
        def __init__(self):
            super().__init__()
            
            self.setWindowTitle("ワーカースレッドテスト")
            self.setGeometry(100, 100, 400, 200)
            
            # UI作成
            self.central_widget = QWidget()
            self.setCentralWidget(self.central_widget)
            
            self.layout = QVBoxLayout(self.central_widget)
            self.status_label = QLabel("準備完了")
            self.progress_label = QLabel("進捗: - ")
            
            self.layout.addWidget(self.status_label)
            self.layout.addWidget(self.progress_label)
            
            # ワーカーマネージャ作成
            self.worker_manager = WorkerManager(debug_mode=True)
            
            # テストタスク開始
            self.start_test_task()
        
        def start_test_task(self):
            self.status_label.setText("タスク実行中...")
            
            # タスク開始
            self.worker_manager.start_task(
                example_task, 10,  # 10ステップのタスク
                on_result=self.handle_result,
                on_error=self.handle_error,
                on_progress=self.handle_progress
            )
        
        def handle_result(self, task_id, result):
            self.status_label.setText(f"完了: 結果 = {result}")
        
        def handle_error(self, task_id, error_info):
            error_type, error_value, _ = error_info
            self.status_label.setText(f"エラー: {error_type.__name__} - {error_value}")
        
        def handle_progress(self, task_id, percent, message):
            self.progress_label.setText(f"進捗: {percent}% - {message}")
    
    # テスト実行
    app = QApplication(sys.argv)
    window = TestApp()
    window.show()
    sys.exit(app.exec())
