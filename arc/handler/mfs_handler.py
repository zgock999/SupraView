"""
マルチスレッド対応物理ファイルシステムハンドラ

従来のFileSystemHandlerを拡張し、ディレクトリの再帰的走査を
マルチスレッドで行うことで高速化を図ったハンドラ
"""

import os
import stat
import re
from datetime import datetime
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Set, Tuple, Any

from arc.arc import EntryInfo, EntryType
from .fs_handler import FileSystemHandler

# procユーティリティモジュールをインポート
from proc.util import get_cpu_count, get_optimal_worker_count, get_system_info


class MultiThreadedFileSystemHandler(FileSystemHandler):
    """
    マルチスレッド対応物理ファイルシステムハンドラ
    
    FileSystemHandlerの機能を継承しつつ、ディレクトリの走査を
    マルチスレッドで実行することでパフォーマンスを向上させる
    """
    
    # マルチスレッド設定
    MIN_ENTRIES_FOR_THREADING = 20  # この数以上のエントリがある場合にマルチスレッドを使用
    # ファイルシステム操作に最適なワーカー数の上限
    WORKER_LIMIT = 8  # 実験的に24程度が最適（これを超えるとパフォーマンスが悪化）
    
    def __init__(self, *args, **kwargs):
        """
        コンストラクタ
        
        Args:
            max_workers: 最大スレッド数（オプション）
        """
        # システム情報に基づいて最適な最大ワーカー数を設定
        optimal_workers = get_optimal_worker_count(
            cpu_intensive=False,  # ファイルシステム操作はI/O主体
            io_bound=True,
            memory_intensive=False
        )
        
        # 最適なワーカー数を上限値以内に制限
        default_workers = min(optimal_workers, self.WORKER_LIMIT)
        
        # 指定されたワーカー数またはデフォルト値を使用（ただし上限を超えないようにする）
        user_workers = kwargs.pop('max_workers', default_workers)
        self.max_workers = min(user_workers, self.WORKER_LIMIT)
        
        # 親クラスの初期化
        super().__init__(*args, **kwargs)
        
        # スレッド管理用変数
        self.thread_local = threading.local()
        
        self.debug_info(f"マルチスレッドファイルシステムハンドラ初期化 (max_workers={self.max_workers})")
        self.debug_info(f"物理コア数: {get_cpu_count(logical=False)}, 論理コア数: {get_cpu_count(logical=True)}")
        self.debug_info(f"推奨ワーカー数: {optimal_workers}, 使用ワーカー数: {self.max_workers}, 上限: {self.WORKER_LIMIT}")
        
        # パフォーマンス警告：WORKERが多すぎる場合
        if self.max_workers > self.WORKER_LIMIT:
            self.debug_warning(f"ワーカー数 {self.max_workers} は推奨上限({self.WORKER_LIMIT})を超えています。パフォーマンスが低下する可能性があります。")
    
    def set_max_workers(self, max_workers: int) -> None:
        """
        マルチスレッド処理で使用する最大ワーカー数を設定する
        
        Args:
            max_workers: 最大ワーカー数（1以上の整数）
        """
        if max_workers > 0:
            # 設定された値を上限以内に制限
            limited_workers = min(max_workers, self.WORKER_LIMIT)
            if limited_workers != max_workers:
                self.debug_info(f"指定されたワーカー数 {max_workers} はパフォーマンス上限を超えています。{limited_workers} に制限しました。")
            
            self.max_workers = limited_workers
            self.debug_info(f"最大ワーカー数を設定: {self.max_workers}")
        else:
            self.debug_warning(f"無効なワーカー数が指定されました: {max_workers}, デフォルト値を使用します")
    
    def list_all_entries(self, path: str) -> List[EntryInfo]:
        """
        指定したディレクトリ内のすべてのエントリを再帰的に取得する（フィルタリングなし）
        マルチスレッドを使用して高速に走査します。
        
        Args:
            path: ディレクトリのパス
            
        Returns:
            ディレクトリ内のすべてのエントリのリスト
            
        Raises:
            FileNotFoundError: 指定されたパスに存在しない場合
            IOError: ディレクトリの読み込みに失敗した場合
        """
        # 空の場合やパスが指定されていない場合は、現在のパスをデフォルトとして使用
        if not path:
            if self.current_path:
                abs_path = self.current_path
            else:
                abs_path = os.getcwd()
        else:
            abs_path = self._to_absolute_path(path)
        
        self.debug_info(f"list_all_entries 開始 - パス: {abs_path} (マルチスレッド対応)")
        
        # ディレクトリが存在するか確認
        if not os.path.exists(abs_path):
            self.debug_error(f"パスが存在しません: {abs_path}")
            raise FileNotFoundError(f"パスが存在しません: {abs_path}")
        
        if not os.path.isdir(abs_path):
            self.debug_error(f"パスはディレクトリではありません: {abs_path}")
            raise NotADirectoryError(f"パスはディレクトリではありません: {abs_path}")
        
        # すべてのエントリを格納するリスト
        all_entries = []
        
        try:
            # 処理時間計測開始
            start_time = datetime.now()
            
            # まずルートディレクトリ自体をエントリとして追加
            root_name = os.path.basename(abs_path.rstrip('/'))
            if not root_name and abs_path:
                # ルートディレクトリの場合（例：C:/ や Z:/）
                if ':' in abs_path:
                    # Windowsのドライブレターの場合
                    drive_parts = abs_path.split(':')
                    if len(drive_parts) > 0:
                        root_name = drive_parts[0] + ":"
                else:
                    root_name = abs_path
            
            if root_name:
                # create_entry_infoを使用してルートエントリを作成
                rel_path = self.to_relative_path(abs_path)
                root_entry = self.create_entry_info(
                    name=root_name,
                    rel_path=rel_path,
                    name_in_arc=rel_path,
                    type=EntryType.DIRECTORY,
                    size=0,
                    modified_time=None
                )
                all_entries.append(root_entry)
                self.debug_info(f"ルートディレクトリエントリを追加: {root_name} ({abs_path})")
            
            # マルチスレッド処理でディレクトリ走査
            collected_entries = self._scan_directory_multithreaded(abs_path)
            all_entries.extend(collected_entries)
            
            # 処理時間計測終了と結果ログ出力
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.debug_info(f"{len(all_entries)} エントリを取得しました (処理時間: {duration:.2f}秒)")
            return all_entries
            
        except PermissionError as e:
            self.debug_error(f"ディレクトリへのアクセス権限がありません: {abs_path} - {e}", trace=True)
            raise IOError(f"ディレクトリへのアクセス権限がありません: {abs_path} - {str(e)}")
        except Exception as e:
            self.debug_error(f"エントリ一覧取得中にエラー: {e}", trace=True)
            import traceback
            traceback.print_exc()
            raise IOError(f"ディレクトリ読み込みエラー: {abs_path} - {str(e)}")
    
    def _scan_directory_multithreaded(self, root_path: str) -> List[EntryInfo]:
        """
        ディレクトリを並列処理で再帰的に走査する
        
        Args:
            root_path: 走査を開始するルートディレクトリのパス
            
        Returns:
            すべてのエントリのリスト
        """
        # 最初のレベルのサブディレクトリとファイルを取得
        top_level_dirs = []
        entries = []
        
        try:
            # ルートディレクトリ直下のエントリを取得
            with os.scandir(root_path) as scanner:
                for entry in scanner:
                    try:
                        if entry.is_dir():
                            top_level_dirs.append(entry.path)
                        
                        # ルートディレクトリ直下のエントリを追加
                        entry_info = self._create_entry_info_from_scandir(entry)
                        if entry_info:
                            entries.append(entry_info)
                    except (OSError, PermissionError) as e:
                        self.debug_warning(f"エントリの読み取りエラー: {entry.path}, {e}")
            
            # サブディレクトリが少ない場合はシングルスレッドで処理
            if len(top_level_dirs) < self.MIN_ENTRIES_FOR_THREADING:
                self.debug_info(f"シングルスレッドで処理 (サブディレクトリ数: {len(top_level_dirs)})")
                for subdir in top_level_dirs:
                    entries.extend(self._scan_subdirectory(subdir))
                return entries
            
            # ThreadPoolExecutorを使用して並列処理
            # パフォーマンス実験結果に基づいたワーカー数を計算
            subdirs_count = len(top_level_dirs)
            # IO処理向けの調整係数（サブディレクトリ数に応じて調整）
            io_factor = 0.5 if subdirs_count < 1000 else 0.3 if subdirs_count < 10000 else 0.2
            # ファイルシステム処理向けの最適ワーカー数：物理コア数の一定割合が良い
            fs_optimal_workers = max(1, int(get_cpu_count(logical=False) * io_factor))
            
            # 上限を考慮した最終的なワーカー数
            actual_workers = min(subdirs_count, fs_optimal_workers, self.max_workers)
            self.debug_info(f"マルチスレッドで処理 (サブディレクトリ数: {subdirs_count}, ワーカー数: {actual_workers})")
            
            with ThreadPoolExecutor(max_workers=actual_workers) as executor:
                # 各サブディレクトリを並列に処理
                futures = {executor.submit(self._scan_subdirectory, subdir): subdir for subdir in top_level_dirs}
                
                # 結果を集計
                for future in concurrent.futures.as_completed(futures):
                    subdir = futures[future]
                    try:
                        subdir_entries = future.result()
                        entries.extend(subdir_entries)
                    except Exception as e:
                        self.debug_warning(f"サブディレクトリ {subdir} の処理中にエラー: {e}")
            
            return entries
            
        except Exception as e:
            self.debug_error(f"マルチスレッドスキャン中にエラー: {e}", trace=True)
            # エラーが発生しても収集したエントリは返す
            return entries

    def _scan_subdirectory(self, dir_path: str) -> List[EntryInfo]:
        """
        サブディレクトリを再帰的に走査する（シングルスレッド）
        
        Args:
            dir_path: 走査するディレクトリのパス
            
        Returns:
            ディレクトリ内のすべてのエントリのリスト
        """
        entries = []
        
        try:
            for root, dirs, files in os.walk(dir_path):
                # ディレクトリエントリを追加
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name).replace('\\', '/')
                    
                    # ディレクトリの統計情報を取得
                    try:
                        stat_info = os.stat(dir_path)
                        mtime = datetime.fromtimestamp(stat_info.st_mtime)
                        ctime = datetime.fromtimestamp(stat_info.st_ctime)
                        
                        # 隠しディレクトリかどうか判定
                        is_hidden = False
                        if os.name == 'nt' and hasattr(stat_info, 'st_file_attributes'):
                            is_hidden = bool(stat_info.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
                        else:
                            is_hidden = dir_name.startswith('.')
                        
                        # create_entry_infoを使用してディレクトリエントリを作成
                        rel_path = self.to_relative_path(dir_path)
                        entry = self.create_entry_info(
                            name=dir_name,
                            path=dir_path,
                            abs_path=dir_path,
                            rel_path=rel_path,
                            name_in_arc=rel_path,
                            type=EntryType.DIRECTORY,
                            size=0,
                            modified_time=mtime,
                            created_time=ctime,
                            is_hidden=is_hidden
                        )
                        entries.append(entry)
                        
                    except Exception as e:
                        self.debug_warning(f"ディレクトリ情報取得エラー: {dir_path} - {e}")
                        # 最小限の情報でエントリを作成して追加
                        rel_path = self.to_relative_path(dir_path)
                        entries.append(self.create_entry_info(
                            name=dir_name,
                            rel_path=rel_path,
                            name_in_arc=rel_path,
                            type=EntryType.DIRECTORY,
                            size=0
                        ))
                
                # ファイルエントリを追加
                for file_name in files:
                    file_path = os.path.join(root, file_name).replace('\\', '/')
                    
                    try:
                        # ファイル情報を取得
                        stat_info = os.stat(file_path)
                        size = stat_info.st_size
                        mtime = datetime.fromtimestamp(stat_info.st_mtime)
                        ctime = datetime.fromtimestamp(stat_info.st_ctime)
                        
                        # 隠しファイルかどうか判定
                        is_hidden = False
                        if os.name == 'nt' and hasattr(stat_info, 'st_file_attributes'):
                            is_hidden = bool(stat_info.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
                        else:
                            is_hidden = file_name.startswith('.')
                        
                        # すべてのファイルをFILEとして扱う
                        entry_type = EntryType.FILE
                                               
                        # create_entry_infoを使用してファイルエントリを作成
                        rel_path = self.to_relative_path(file_path)
                        entry = self.create_entry_info(
                            name=file_name,
                            rel_path=rel_path,
                            name_in_arc=rel_path,
                            type=entry_type,
                            size=size,
                            modified_time=mtime,
                            created_time=ctime,
                            is_hidden=is_hidden
                        )
                        entries.append(entry)
                        
                    except Exception as e:
                        self.debug_warning(f"ファイル情報取得エラー ({file_path}): {e}")
                        # エラーが発生しても最低限の情報でエントリを追加
                        rel_path = self.to_relative_path(file_path)
                        entries.append(self.create_entry_info(
                            name=file_name,
                            rel_path=rel_path,
                            name_in_arc=rel_path,
                            type=EntryType.FILE,
                            size=0
                        ))
            
            return entries
        
        except Exception as e:
            self.debug_warning(f"サブディレクトリ {dir_path} の走査中にエラー: {e}")
            return entries

    def _create_entry_info_from_scandir(self, entry) -> Optional[EntryInfo]:
        """
        os.DirEntryオブジェクトからEntryInfoを作成する
        
        Args:
            entry: os.DirEntryオブジェクト
            
        Returns:
            EntryInfoオブジェクト。エラー時はNone
        """
        try:
            name = entry.name
            full_path = entry.path.replace('\\', '/')
            
            # ファイルタイプを判定（アーカイブ判定を削除）
            if entry.is_dir():
                entry_type = EntryType.DIRECTORY
            elif entry.is_file():
                # すべてのファイルをFILEとして扱う
                entry_type = EntryType.FILE
            else:
                # シンボリックリンクなど
                entry_type = EntryType.UNKNOWN
            
            # ファイル属性を取得
            stat_info = entry.stat()
            
            # タイムスタンプをDatetime型に変換
            ctime = datetime.fromtimestamp(stat_info.st_ctime)
            mtime = datetime.fromtimestamp(stat_info.st_mtime)
            
            # 隠しファイルかどうかを判定（プラットフォーム依存）
            is_hidden = name.startswith('.') if os.name != 'nt' else bool(stat_info.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN) if hasattr(stat_info, 'st_file_attributes') else False
            
            # 相対パスを計算
            rel_path = self.to_relative_path(full_path)
            
            # EntryInfoオブジェクトを作成
            return self.create_entry_info(
                name=name,
                abs_path=full_path,
                rel_path=rel_path,
                name_in_arc=rel_path,
                type=entry_type,
                size=stat_info.st_size if entry_type != EntryType.DIRECTORY else 0,
                created_time=ctime,
                modified_time=mtime,
                is_hidden=is_hidden
            )
            
        except Exception as e:
            self.debug_warning(f"エントリ情報作成エラー: {entry.path}, {e}")
            return None
            
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        パフォーマンス統計情報を取得する
        
        Returns:
            パフォーマンス統計情報を含む辞書
        """
        # 現在のスレッド設定と追加のシステム情報を返す
        stats = {
            "max_workers": self.max_workers,
            "min_entries_for_threading": self.MIN_ENTRIES_FOR_THREADING,
            "worker_limit": self.WORKER_LIMIT,
            "physical_cores": get_cpu_count(logical=False),
            "logical_cores": get_cpu_count(logical=True),
            "recommended_workers": get_optimal_worker_count(io_bound=True),
        }
        
        # システムメモリ情報を追加
        try:
            import psutil
            vm = psutil.virtual_memory()
            stats["total_memory_gb"] = round(vm.total / (1024**3), 2)
            stats["available_memory_gb"] = round(vm.available / (1024**3), 2)
            stats["memory_percent"] = vm.percent
        except ImportError:
            pass
            
        return stats
