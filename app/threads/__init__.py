"""
スレッド処理モジュール

バックグラウンドでの処理を実装するためのスレッド関連ユーティリティを提供します。
"""

from .worker import Worker, WorkerManager

# 外部からインポートできるようにエクスポート
__all__ = ['Worker', 'WorkerManager']
