# procモジュール

procモジュールは、マルチプロセスでバックグラウンド処理を簡単に実行するためのモジュールです。
ワーカープロセスの作成、管理、通信、監視を簡素化します。

## 主な機能

- マルチプロセスのワーカー管理
- 実行キューによる処理の順次実行と並列処理
- 処理状態の監視とコールバック通知
- イベント駆動型の監視システム
- 柔軟なキャンセル処理

## モジュール構成

- `worker.py` - ワーカープロセスの基本実装
- `queue.py` - 実行キュー管理機能
- `events.py` - イベント処理システム
- `__init__.py` - 利便性のためのインターフェース関数

## 基本的な使い方

### 1. 単一ワーカーの作成と実行

```python
from proc import create_worker

# ワーカーを作成
worker = create_worker(
    target=your_function,  # 実行する関数
    args=(arg1, arg2),     # 関数の引数
    callback=your_callback # 進捗コールバック
)

# ワーカーを開始
worker.start()

# 完了を待機
worker.join()

# 結果を取得
result = worker.get_result()
```

### 2. 実行キューによる複数ワーカーの管理

```python
from proc import create_worker, create_queue

# キューを作成（最大3つの同時実行）
queue = create_queue(max_workers=3)

# 複数のワーカーを作成
workers = [
    create_worker(target=function, args=(i,))
    for i in range(10)
]

# キューに追加して実行
for worker in workers:
    queue.submit(worker)

# すべての処理が完了するまで待機
queue.shutdown(wait=True)

# 結果を取得
for worker in workers:
    status, result = queue.get_result(worker.id)
    print(f"Worker {worker.id}: {status.name}, {result}")
```

## 新機能: イベントシステム

### イベントシステムの初期化

```python
from proc import initialize_event_system, subscribe_to_events

# イベントシステムの初期化
initialize_event_system()

# イベントリスナーの登録
def event_listener(event):
    print(f"イベント受信: {event}")
    if event.status.name == "COMPLETED":
        print(f"完了: {event.worker_id}, 結果: {event.result}")

subscribe_to_events(event_listener)
```

### イベント発行するワーカーの作成

```python
from proc import create_worker

# イベントを発行するワーカー
worker = create_worker(
    target=your_function,
    args=(arg1, arg2),
    publish_events=True  # イベント発行を有効化
)

worker.start()
```

## 監視パターン

### 1. イベントベースの監視（単一プロセス内）

```python
from proc import initialize_event_system, subscribe_to_events, create_worker, create_queue

# イベント監視システムの初期化
initialize_event_system()

# 完了通知用のイベント
import threading
all_completed = threading.Event()

# イベントリスナー
def monitor_events(event):
    if event.status.name == "COMPLETED":
        print(f"タスク完了: {event.worker_id}")
        # すべて完了を確認したら通知
        check_all_completed()

# イベントリスナー登録
subscribe_to_events(monitor_events)

# ワーカー実行と待機
# ...
```

### 2. スレッドベースの監視（より強力）

```python
import threading
from proc import create_worker, create_queue, WorkerStatus

# 監視状態を管理
worker_states = {}
worker_lock = threading.RLock()

# 監視スレッド
def monitor_thread():
    while not stop_event.is_set():
        with worker_lock:
            # ワーカー状態の確認
            for worker_id, status in worker_states.items():
                if status == WorkerStatus.COMPLETED:
                    print(f"ワーカー {worker_id} が完了しました")
            
        time.sleep(0.5)

# ワーカーコールバック
def worker_callback(worker, status, result):
    with worker_lock:
        worker_states[worker.id] = status
```

## 注意事項

1. **ピクル化制限**: マルチプロセスで使用するため、関数と引数は`pickle`でシリアライズ可能である必要があります
2. **リソース管理**: 使用後は必ず`queue.shutdown()`を呼び出してリソースを解放してください
3. **例外処理**: ワーカー内の例外は自動的にキャプチャされ、`WorkerStatus.ERROR`として報告されます

## 高度な使用例

より高度な使用例は、`misc/check_proc.py`を参照してください。このファイルには、イベントベースの監視とスレッドベースの監視の両方の実装例が含まれています。

```bash
# イベントベースの監視の例を実行
python misc/check_proc.py --pass 1

# スレッドベースの監視の例を実行
python misc/check_proc.py --pass 2
```
