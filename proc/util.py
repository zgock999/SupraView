"""
プロセスとスレッドのユーティリティ関数

CPU数、適切なワーカー数の計算など、マルチプロセス/マルチスレッド
アプリケーションで必要となる共通ユーティリティ関数を提供します。
"""

import os
import sys
import platform
import multiprocessing
import psutil
import logging
from typing import Optional, Dict, Any, Union, Tuple

# ロガーの設定
logger = logging.getLogger(__name__)

def get_cpu_count(logical: bool = True) -> int:
    """
    システムで利用可能なCPU数を取得する
    
    Args:
        logical: 論理コア数を返す場合はTrue、物理コア数の場合はFalse
        
    Returns:
        CPU数（コア数）
    """
    try:
        if logical:
            # 論理CPUコア数（ハイパースレッディング含む）
            return multiprocessing.cpu_count()
        else:
            # 物理CPUコア数（ハイパースレッディングを除外）
            # psutilが利用可能な場合
            try:
                return psutil.cpu_count(logical=False) or 1
            except (AttributeError, ImportError):
                # psutilが使えない場合は論理コア数を返す
                return multiprocessing.cpu_count()
    except Exception as e:
        logger.warning(f"CPU数の取得に失敗しました: {e}")
        return 1  # エラーの場合は1を返す


def get_optimal_worker_count(cpu_intensive: bool = True, 
                           io_bound: bool = False, 
                           memory_intensive: bool = False,
                           max_workers: Optional[int] = None) -> int:
    """
    ワークロードの特性に基づいて最適なワーカー数を計算する
    
    Args:
        cpu_intensive: CPUを多く使用する処理の場合True
        io_bound: I/O待ちが多い処理の場合True
        memory_intensive: メモリを多く使用する処理の場合True
        max_workers: 最大ワーカー数の上限（Noneの場合は自動計算）
        
    Returns:
        推奨されるワーカー数
    """
    # 論理コア数と物理コア数を取得
    logical_cores = get_cpu_count(logical=True)
    physical_cores = get_cpu_count(logical=False)
    
    # 基本のワーカー数を決定
    if cpu_intensive:
        # CPU集約型の場合は物理コア数が基本
        # オーバーヘッドを避けるため
        workers = physical_cores
    elif io_bound:
        # I/O待ちの多い処理は論理コア数の2倍まで許容
        # I/O待ち時間が多いのでCPUはそれほど使わない
        workers = logical_cores * 2
    else:
        # デフォルトは論理コア数
        workers = logical_cores
        
    # メモリ集約型の場合は調整
    if memory_intensive:
        # メモリ使用量の多い処理は少なめのワーカー数が良い
        workers = max(1, min(workers, physical_cores // 2 + 1))
        
    # システムの合計メモリに基づく調整
    try:
        # 利用可能な合計メモリを取得（GB単位）
        if hasattr(psutil, 'virtual_memory'):
            total_memory_gb = psutil.virtual_memory().total / (1024 ** 3)
            
            # メモリが少ない場合はワーカー数を減らす
            if total_memory_gb < 4:  # 4GB未満
                workers = min(workers, 2)
            elif total_memory_gb < 8:  # 8GB未満
                workers = min(workers, physical_cores, 4)
    except Exception as e:
        logger.debug(f"メモリ情報の取得に失敗しました: {e}")
    
    # 最大ワーカー数の制限を適用
    if max_workers is not None:
        workers = min(workers, max_workers)
    
    # 最低でも1つのワーカーを確保
    return max(1, workers)


def get_system_info() -> Dict[str, Any]:
    """
    システム情報を収集する
    
    Returns:
        システム情報を含む辞書
    """
    info = {
        "platform": platform.platform(),
        "python_version": sys.version,
        "cpu_count_logical": get_cpu_count(logical=True),
        "cpu_count_physical": get_cpu_count(logical=False),
    }
    
    # メモリ情報
    try:
        if hasattr(psutil, 'virtual_memory'):
            vm = psutil.virtual_memory()
            info["total_memory_gb"] = vm.total / (1024 ** 3)
            info["available_memory_gb"] = vm.available / (1024 ** 3)
    except Exception as e:
        logger.debug(f"メモリ情報の取得に失敗しました: {e}")
        
    # CPU情報
    try:
        if hasattr(psutil, 'cpu_freq'):
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                info["cpu_freq_mhz"] = cpu_freq.current
    except Exception as e:
        logger.debug(f"CPU周波数の取得に失敗しました: {e}")
    
    # OSごとの情報
    if platform.system() == 'Windows':
        try:
            info["windows_edition"] = platform.win32_edition()
        except:
            pass
    
    return info


def estimate_memory_usage(data_size: int, processing_factor: float = 5.0) -> float:
    """
    データサイズに基づいて予想されるメモリ使用量を計算する
    
    Args:
        data_size: 入力データのサイズ（バイト単位）
        processing_factor: 処理中に必要となる追加メモリの係数
                         （例: 5.0ならデータサイズの5倍のメモリが必要と予測）
        
    Returns:
        予想されるメモリ使用量（バイト単位）
    """
    # 最低でも10MBを見積もる
    base_overhead = 10 * 1024 * 1024  # 10MB
    
    # データサイズと処理係数に基づいて計算
    estimated = base_overhead + (data_size * processing_factor)
    
    return estimated


def adjust_workers_for_memory(
    total_data_size: int, 
    workers: int, 
    memory_per_worker_factor: float = 5.0,
    memory_limit_percent: float = 75.0
) -> int:
    """
    利用可能なメモリに基づいてワーカー数を調整する
    
    Args:
        total_data_size: 処理する合計データサイズ（バイト単位）
        workers: 初期ワーカー数
        memory_per_worker_factor: ワーカーあたりのメモリ使用量係数
        memory_limit_percent: 使用を許可するシステムメモリの最大パーセンテージ
        
    Returns:
        調整後のワーカー数
    """
    try:
        # 利用可能なメモリを取得（バイト単位）
        if hasattr(psutil, 'virtual_memory'):
            vm = psutil.virtual_memory()
            total_memory = vm.total
            
            # 使用を許可するメモリ量
            allowed_memory = total_memory * (memory_limit_percent / 100.0)
            
            # ワーカーあたりの推定メモリ使用量
            worker_size = estimate_memory_usage(total_data_size / workers, memory_per_worker_factor)
            
            # 調整後のワーカー数
            adjusted_workers = min(workers, int(allowed_memory / worker_size))
            
            # 最低でも1つのワーカーを確保
            return max(1, adjusted_workers)
    except Exception as e:
        logger.warning(f"メモリ使用量に基づくワーカー数の調整に失敗しました: {e}")
    
    # エラー時や計算不能時は元のワーカー数を返す
    return workers


# モジュールのインポート時にログに情報を出力
if __name__ != "__main__":
    try:
        logger.debug(f"システム情報: {get_system_info()}")
        logger.debug(f"論理CPU数: {get_cpu_count(logical=True)}")
        logger.debug(f"物理CPU数: {get_cpu_count(logical=False)}")
        logger.debug(f"推奨ワーカー数 (CPU集約型): {get_optimal_worker_count(cpu_intensive=True)}")
        logger.debug(f"推奨ワーカー数 (I/O集約型): {get_optimal_worker_count(io_bound=True)}")
    except Exception as e:
        logger.error(f"システム情報収集時にエラーが発生しました: {e}")


# 直接実行された場合はテスト出力
if __name__ == "__main__":
    # 簡易的なログ設定
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    print("===== システム情報 =====")
    system_info = get_system_info()
    for key, value in system_info.items():
        print(f"{key}: {value}")
    
    print("\n===== CPU情報 =====")
    print(f"論理CPU数: {get_cpu_count(logical=True)}")
    print(f"物理CPU数: {get_cpu_count(logical=False)}")
    
    print("\n===== 推奨ワーカー数 =====")
    print(f"CPU集約型処理: {get_optimal_worker_count(cpu_intensive=True)}")
    print(f"I/O集約型処理: {get_optimal_worker_count(io_bound=True)}")
    print(f"メモリ集約型処理: {get_optimal_worker_count(memory_intensive=True)}")
    print(f"バランス型処理: {get_optimal_worker_count()}")
    
    # メモリベースの調整をテスト
    data_size = 100 * 1024 * 1024  # 100MB
    print(f"\n100MBのデータを処理する場合の推定メモリ使用量: {estimate_memory_usage(data_size) / (1024 * 1024):.2f}MB")
    
    workers = get_optimal_worker_count()
    adjusted = adjust_workers_for_memory(data_size * 100, workers)
    print(f"メモリ制約による調整: {workers} → {adjusted} ワーカー")
