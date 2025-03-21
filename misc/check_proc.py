#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
procモジュールの単体テスト用スクリプト
複数のスリープタスクをワーカーで実行し、その進捗を監視する
"""

import os
import sys
import time
import threading
import argparse

# プロジェクトルートを追加して、procモジュールをインポートできるようにする
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from proc import (
    create_worker, create_queue, WorkerStatus, WorkerEvent,
    initialize_event_system, subscribe_to_events, unsubscribe_from_events
)

# グローバル変数
all_workers = []  # 全ワーカーを直接追跡するリスト
all_workers_completed = threading.Event()  # 完了イベント
monitor_should_exit = threading.Event()  # 監視終了イベント
monitor_timeout = 30  # 監視タイムアウト（秒）
debug_enabled = False  # デバッグ出力の有効/無効

def debug_print(msg):
    """デバッグメッセージを出力する（debug_enabled=Trueの場合のみ）"""
    if debug_enabled:
        print(msg)

def sleep_task(sleep_time, is_cancelled=None):
    """
    指定された時間だけスリープする単純なタスク
    
    Args:
        sleep_time (int): スリープ時間（秒）
        is_cancelled (callable, optional): キャンセル確認用関数
    
    Returns:
        int: スリープした時間
    """
    print(f"[Worker] {sleep_time}秒のタスクを開始します")
    
    # 0.1秒ごとにスリープして、キャンセルをチェック
    for i in range(int(sleep_time * 10)):
        if is_cancelled and is_cancelled():
            print(f"[Worker] {sleep_time}秒のタスクがキャンセルされました")
            return i / 10
        time.sleep(0.1)
    
    print(f"[Worker] {sleep_time}秒のタスクが完了しました")
    return sleep_time

def monitor_task(worker_ids, worker_queue, report_interval=1.0, is_cancelled=None):
    """
    複数のワーカーを監視し、その状態を定期的に報告するタスク
    
    Args:
        worker_ids (list): 監視対象のワーカーIDのリスト
        worker_queue: ワーカーの情報を取得するキュー
        report_interval (float): 報告間隔（秒）
        is_cancelled (callable, optional): キャンセル確認用関数
    
    Returns:
        dict: 各ワーカーの最終状態と結果
    """
    print(f"[Monitor] {len(worker_ids)}個のワーカーの監視を開始します")
    
    results = {}
    all_completed = False
    
    while not all_completed:
        # キャンセルチェック
        if is_cancelled and is_cancelled():
            print("[Monitor] 監視タスクがキャンセルされました")
            break
        
        # 状態カウント
        completed = 0
        running = 0
        pending = 0
        
        # 各ワーカーの状態をチェック
        for worker_id in worker_ids:
            # キューから状態と結果を取得
            status, result = worker_queue.get_result(worker_id, wait=False)
            
            if status == WorkerStatus.COMPLETED:
                completed += 1
                if worker_id not in results:
                    # キューから最終的な結果を取得
                    final_status, final_result = worker_queue.get_result(worker_id, wait=True, timeout=0.1)
                    
                    # 実行時間は直接測定不可能なので、時間情報は省略
                    results[worker_id] = {
                        "status": final_status,
                        "result": final_result,
                        "execution_time": None  # 実行時間は取得できない
                    }
                    print(f"[Monitor] ワーカー {worker_id[:8]} が完了しました (結果: {final_result})")
            elif status == WorkerStatus.RUNNING:
                running += 1
            elif status == WorkerStatus.PENDING:
                pending += 1
        
        # 進捗を報告
        print(f"\r[Monitor] 進捗: 完了={completed}/{len(worker_ids)}, 実行中={running}, 待機中={pending}", end="")
        
        # すべてのワーカーが完了したか確認
        if completed == len(worker_ids):
            print("\n[Monitor] すべてのワーカーが完了しました！")
            all_completed = True
            break
        
        # 次の報告まで待機
        time.sleep(report_interval)
    
    print(f"[Monitor] 監視完了: {len(results)}/{len(worker_ids)}個のワーカーが完了")
    return results

#
# Pass 1: イベントリスナーを使用した監視
#
def event_listener(event):
    """
    ワーカーイベントを処理するリスナー関数
    
    Args:
        event (WorkerEvent): ワーカーから発行されたイベント
    """
    # スリープタスクのイベントのみを処理
    if event.target_name == "sleep_task":
        if event.status == WorkerStatus.COMPLETED:
            sleep_time = event.args[0] if event.args else "不明"
            print(f"[Event] {sleep_time}秒タスク完了イベント発行 - ステータス: {event.status.name}")
            
            # 全てのワーカーが完了したかチェック
            check_all_completed()
    
    # 全てのイベントをデバッグ出力
    debug_print(f"[Debug] イベント受信: {event}")

def check_all_completed():
    """全てのワーカーが完了したかチェックし、完了イベントを設定"""
    global all_workers
    
    completed_count = 0
    total_workers = len(all_workers)
    
    # 各ワーカーの実際の状態を直接チェック
    for worker in all_workers:
        if worker.get_status() == WorkerStatus.COMPLETED:
            completed_count += 1
    
    print(f"[Check] 実際の状態: 完了={completed_count}/{total_workers}")
    
    # 全ワーカーが完了したかチェック
    if completed_count == total_workers:
        print(f"[Check] すべてのワーカーが完了しました！({completed_count}/{total_workers})")
        all_workers_completed.set()
        monitor_should_exit.set()
        return True
    
    return False

def run_pass1():
    """Pass 1: イベントリスナーを使った単純な監視"""
    global all_workers
    
    print("\n==== Pass 1: イベントリスナーを使用した監視 ====\n")
    
    # イベントシステムを初期化
    initialize_event_system(auto_start=True)
    
    # イベントリスナーを登録
    subscribe_to_events(event_listener)
    
    # 各種イベントをリセット
    all_workers_completed.clear()
    monitor_should_exit.clear()
    
    try:
        # 複数のワーカーを作成（5秒から1秒の降順）
        workers = []
        for sleep_time in range(5, 0, -1):  # 5, 4, 3, 2, 1秒の順
            worker = create_worker(
                target=sleep_task,
                args=(sleep_time,),
                callback=None,  # イベントシステムを使用するためコールバックは不要
                callback_interval=0.5,
                publish_events=True  # イベントを発行する
            )
            workers.append(worker)
        
        # グローバル変数に保存
        all_workers = workers
        
        # キューを作成
        worker_queue = create_queue(max_workers=3)
        
        print(f"合計{len(workers)}個のワーカーを作成しました（同時実行数: {worker_queue.max_workers}）")
        print("5秒から1秒の降順でタスクを実行します")
        
        # スリープワーカーをキューに追加
        for worker in workers:
            worker_queue.submit(worker)
        
        # すべてのワーカーが完了するまで待機
        print("すべてのワーカーの完了を待機しています...")
        wait_result = all_workers_completed.wait(timeout=monitor_timeout)
        
        if not wait_result:
            print("タイムアウト: すべてのワーカーが完了しませんでした。")
        else:
            print("すべてのワーカーが完了しました！")
        
        # 結果を表示（元の順序に合わせて表示）
        print("\n--- 処理結果 ---")
        for idx, worker in enumerate(reversed(workers)):  # 順序を逆にして1秒から表示
            sleep_time = 5 - idx  # 5,4,3,2,1の順のworkerを1,2,3,4,5秒として表示
            status, result = worker_queue.get_result(worker.id, wait=False)
            print(f"{sleep_time}秒ワーカー: 状態={status.name if status else 'UNKNOWN'}, 結果={result}")
        
        # リソースを解放
        worker_queue.shutdown(wait=True)
        
    except KeyboardInterrupt:
        print("\n処理をキャンセルします...")
        worker_queue.cancel_all()
        worker_queue.shutdown(wait=True)
    finally:
        # イベントリスナーを登録解除
        unsubscribe_from_events(event_listener)
        print("Pass 1 終了")

def monitor_task_simple(worker_ids, report_interval=1.0, is_cancelled=None):
    """
    複数のワーカーの完了状態だけを監視する簡素化したタスク
    （マルチプロセス実行用、キューオブジェクトを必要としない）
    
    Args:
        worker_ids (list): 監視対象のワーカーIDのリスト
        report_interval (float): 報告間隔（秒）
        is_cancelled (callable, optional): キャンセル確認用関数
    
    Returns:
        list: 完了したワーカーIDのリスト
    """
    print(f"[Monitor] {len(worker_ids)}個のワーカーIDの監視を開始します")
    
    # 完了したワーカーIDのリスト（戻り値として使用）
    completed_ids = []
    
    # メインプロセスに知らせるための結果
    result = {"message": "モニタータスクが正常に完了しました"}
    
    # 10秒ごとにメッセージを表示（実際の監視はメインプロセスで行う）
    intervals = 0
    while intervals < 20:  # 最大100秒（20 * 5秒）
        if is_cancelled and is_cancelled():
            result["message"] = "監視タスクがキャンセルされました"
            break
        
        # 進捗表示
        print(f"[Monitor] シンプル監視中... ({intervals * 5}秒経過)")
        intervals += 1
        
        time.sleep(5)  # 5秒ごとに表示
    
    print("[Monitor] シンプル監視タスクが終了しました")
    return result

#
# Pass 2: 監視機能をスレッドベースで実装
#
def run_pass2():
    """Pass 2: スレッドベースの監視処理を使用"""
    print("\n==== Pass 2: スレッドベースの監視 ====\n")
    
    # 監視完了フラグ
    workers_completed = threading.Event()
    monitor_stop = threading.Event()
    
    # ワーカーの状態を追跡する辞書
    worker_states = {}
    worker_results = {}
    workers_lock = threading.RLock()
    
    # 監視タスク（メインスレッド内の別スレッドで実行）
    def thread_monitor():
        print("[ThreadMonitor] ワーカー監視スレッドを開始しました")
        
        while not monitor_stop.is_set():
            with workers_lock:
                total = len(worker_states)
                completed = sum(1 for status in worker_states.values() if status == WorkerStatus.COMPLETED)
                running = sum(1 for status in worker_states.values() if status == WorkerStatus.RUNNING)
                pending = sum(1 for status in worker_states.values() if status == WorkerStatus.PENDING)
                
                # 進捗状況を表示
                print(f"\r[ThreadMonitor] 進捗: 完了={completed}/{total}, 実行中={running}, 待機中={pending}", end="")
                
                # すべてのワーカーが完了した場合
                if completed == total and total > 0:
                    print("\n[ThreadMonitor] すべてのワーカーが完了しました！")
                    workers_completed.set()
                    break
            
            # 次の確認まで待機
            time.sleep(0.5)
        
        print("[ThreadMonitor] 監視スレッドが終了しました")
    
    # ワーカーのコールバック関数
    def worker_callback(worker, status, result):
        with workers_lock:
            worker_states[worker.id] = status
            if status == WorkerStatus.COMPLETED:
                worker_results[worker.id] = result
                print(f"\n[Callback] ワーカー {worker.id[:8]} が完了しました (結果: {result})")
    
    try:
        # 監視スレッドを開始
        monitor_thread = threading.Thread(target=thread_monitor, daemon=True)
        monitor_thread.start()
        
        # キューを作成
        worker_queue = create_queue(max_workers=3)
        
        # 複数のワーカーを作成（5秒から1秒の降順）
        sleep_workers = []
        
        for sleep_time in range(5, 0, -1):  # 5, 4, 3, 2, 1秒の順
            worker = create_worker(
                target=sleep_task,
                args=(sleep_time,),
                callback=worker_callback,  # コールバックを設定
                callback_interval=0.5,
                publish_events=False
            )
            sleep_workers.append(worker)
            
            # 初期状態を設定
            with workers_lock:
                worker_states[worker.id] = WorkerStatus.PENDING
        
        # 準備完了メッセージ
        print(f"監視対象ワーカー: {len(sleep_workers)}個（同時実行数: {worker_queue.max_workers}）")
        print("5秒から1秒の降順でタスクを実行します")
        
        # スリープワーカーをキューに追加
        for worker in sleep_workers:
            worker_queue.submit(worker)
        
        # すべてのワーカーが完了するまで待機
        print("すべてのワーカーの完了を待機しています...")
        wait_result = workers_completed.wait(timeout=monitor_timeout)
        
        if not wait_result:
            print("タイムアウト: すべてのワーカーが完了しませんでした。")
        else:
            print("すべてのワーカーが完了しました！")
        
        # 監視スレッドを停止
        monitor_stop.set()
        monitor_thread.join(timeout=3)
        
        # 結果を表示
        print("\n--- 処理結果 ---")
        
        # 時間順にソートして表示（1秒から5秒の順）
        sorted_workers = sorted(sleep_workers, key=lambda w: w.args[0] if w.args else 0)
        
        for worker in sorted_workers:
            sleep_time = worker.args[0] if worker.args else "不明"
            status = worker_states.get(worker.id, "不明")
            result = worker_results.get(worker.id, "なし")
            
            status_name = status.name if hasattr(status, "name") else str(status)
            print(f"{sleep_time}秒ワーカー (ID: {worker.id[:8]}): 状態={status_name}, 結果={result}")
        
        # リソースを解放
        worker_queue.shutdown(wait=True)
        
    except KeyboardInterrupt:
        print("\n処理をキャンセルします...")
        monitor_stop.set()
        worker_queue.cancel_all()
        worker_queue.shutdown(wait=True)
    
    print("Pass 2 終了")

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='procモジュールの単体テスト')
    parser.add_argument('--pass', type=int, choices=[1, 2], dest='pass_num',
                      help='実行するパス (1: イベントベース, 2: 監視ワーカー使用)', default=1)
    parser.add_argument('--debug', action='store_true', help='デバッグ出力を有効にする')
    
    args = parser.parse_args()
    
    # デバッグフラグをセット
    global debug_enabled
    debug_enabled = args.debug
    
    print("procモジュールの単体テストを開始します...")
    
    # 指定されたパスを実行
    if args.pass_num == 1:
        run_pass1()
    else:
        run_pass2()
    
    print("テスト終了")

if __name__ == "__main__":
    main()
