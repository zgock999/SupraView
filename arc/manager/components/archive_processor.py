"""
アーカイブ処理コンポーネント

アーカイブの読み込みと処理を担当します。
"""

import os
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import threading
import queue
from typing import List, Optional, Dict, Set, Tuple, Deque
from collections import deque

from ...arc import EntryInfo, EntryType, EntryStatus
from proc.util import get_cpu_count, get_optimal_worker_count

class ArchiveProcessor:
    """
    アーカイブ処理クラス
    
    アーカイブファイルの処理、内部エントリの抽出と登録を行います。
    """
    
    # 絶対的な最大ネスト階層の深さ制限（無限ループ防止用の安全装置）
    MAX_NEST_DEPTH = 20
    
    # マルチスレッド設定
    MIN_ARCHIVES_FOR_THREADING = 3  # この数以上のアーカイブがある場合にマルチスレッドを使用
    MAX_THREADS = 8  # 最大スレッド数の上限
    
    def __init__(self, manager):
        """
        アーカイブプロセッサーを初期化する
        
        Args:
            manager: 親となるEnhancedArchiveManagerインスタンス
        """
        self._manager = manager
        # パス解析用のスレッドローカルストレージ
        self._thread_local = threading.local()
        
        # 最適なスレッド数を計算
        self._thread_count = min(
            get_optimal_worker_count(cpu_intensive=False, io_bound=True),
            self.MAX_THREADS
        )
        self._manager.debug_info(f"アーカイブプロセッサーを初期化しました (スレッド数: {self._thread_count})")
    
    def _get_archive_path_depth(self, path: str) -> int:
        """
        アーカイブパスのネスト深度を計算する
        
        ※キューベース処理方式では深度はループ検出のみに使用される
        
        Args:
            path: アーカイブパス
        
        Returns:
            ネスト深度（書庫の中に書庫がある回数）
        """
        if not hasattr(self._thread_local, 'archive_path_depths'):
            self._thread_local.archive_path_depths = {}
            
        # パスの深度がキャッシュされていればそれを返す
        if path in self._thread_local.archive_path_depths:
            return self._thread_local.archive_path_depths[path]
            
        # パスの深度を計算（親アーカイブの数をカウント）
        depth = 0
        current_path = path
        
        while True:
            # パスを分析して親書庫と内部パスを特定
            parent_path, internal_path = self._manager._path_resolver._analyze_path(current_path)
            
            # 親書庫が見つからなければ終了
            if not parent_path or parent_path == current_path:
                break
                
            # 親書庫が見つかった場合は深度を増加
            depth += 1
            current_path = parent_path
            
            # 安全装置：最大深度に達したら処理を中断（無限ループ防止）
            if depth >= self.MAX_NEST_DEPTH:
                self._manager.debug_warning(f"最大ネスト階層 ({self.MAX_NEST_DEPTH}) に達しました - パス: {path}. 潜在的な循環参照の可能性があります。")
                break
        
        # 結果をキャッシュ
        self._thread_local.archive_path_depths[path] = depth
        return depth
    
    def process_archive_for_all_entries(self, base_path: str, arc_entry: EntryInfo, preload_content: bool = False) -> List[EntryInfo]:
        """
        アーカイブエントリの内容を処理し、すべてのエントリを取得する
        
        Args:
            base_path: 基準となるパス
            arc_entry: 処理するアーカイブエントリ
            preload_content: 使用しません（将来の拡張用）
            
        Returns:
            アーカイブ内のすべてのエントリ
        """
        archive_path = arc_entry.path
        thread_id = threading.get_ident()
        
        # 循環参照を検出するためだけにパス深度をチェック
        depth = self._get_archive_path_depth(archive_path)
        if depth >= self.MAX_NEST_DEPTH:
            self._manager.debug_warning(f"安全装置: 最大ネスト階層に達しました - パス: {archive_path}, 深度: {depth} （スレッドID: {thread_id}）")
            return []
        
        try:
            self._manager.debug_info(f"アーカイブ処理: {archive_path} (ネスト階層: {depth}, スレッドID: {thread_id})")
            self._manager.debug_info(f"アーカイブエントリ ({arc_entry.path} )")

            # 書庫エントリの種別を確実にARCHIVEに設定
            if arc_entry.type != EntryType.ARCHIVE:
                self._manager.debug_info(f"エントリタイプをARCHIVEに修正: {arc_entry.path}")
                arc_entry.type = EntryType.ARCHIVE

            # 処理対象が物理ファイルであれば、適切な処理を行う
            if os.path.isfile(archive_path):
                self._manager.debug_info(f"物理ファイルを処理: {archive_path}")
                handler = self._manager.get_handler(archive_path)
                if handler:
                    try:
                        # アーカイブ内のすべてのエントリ情報を取得するには list_all_entries を使用
                        entries = handler.list_all_entries(archive_path)
                        if entries:
                            self._manager.debug_info(f"物理アーカイブから {len(entries)} エントリを取得")
                            
                            # スレッドセーフにキャッシュ登録するためのロック取得
                            cache_lock = getattr(self._manager, '_cache_lock', None)
                            if cache_lock is None:
                                self._manager._cache_lock = threading.RLock()
                                cache_lock = self._manager._cache_lock
                            
                            # 得られたエントリを一つずつファイナライズしてからキャッシュに登録
                            result_entries = []
                            with cache_lock:
                                for entry in entries:
                                    # エントリをファイナライズ
                                    finalized_entry = self._manager.finalize_entry(entry, archive_path)
                                    # ファイナライズしたエントリをキャッシュに追加
                                    entry_key = finalized_entry.rel_path.rstrip('/')
                                    if entry_key or entry_key == "":  # 空文字列キー（ルート）も登録可能に
                                        self._manager._entry_cache.register_entry(entry_key, finalized_entry)
                                        self._manager.debug_debug(f"物理ファイルのエントリを即時キャッシュに登録 (スレッドID: {thread_id}): {entry_key}")
                                    # 結果リストに追加
                                    result_entries.append(finalized_entry)
                            
                            return result_entries
                        else:
                            self._manager.debug_warning(f"ハンドラはエントリを返しませんでした: {handler.__class__.__name__}")
                    except (IOError, PermissionError) as e:
                        # IO/Permissionエラーの場合はエントリステータスをBROKENに設定し処理を続行
                        self._manager.debug_error(f"ハンドラの呼び出しでIO/Permissionエラー: {e}")
                        if hasattr(arc_entry, 'status'):
                            arc_entry.status = EntryStatus.BROKEN
                        else:
                            arc_entry.status = EntryStatus.BROKEN
                        # このアーカイブは処理できないので空リストを返す
                        return []
                    except Exception as e:
                        self._manager.debug_error(f"ハンドラの呼び出しでエラー: {e}", trace=True)
                else:
                    self._manager.debug_warning(f"ファイルを処理するハンドラが見つかりません: {archive_path}")
                
                # エラーまたは結果が空の場合は空リストを返す
                return []

            # 1. 親書庫のタイプと場所を判別
            parent_archive_path = None
            parent_archive_bytes = None
            parent_archive_temp_path = None
            
            # パスを詳細に分析して親書庫と内部パスを特定
            parent_path, internal_path = self._manager._path_resolver._analyze_path(archive_path)
            
            # パスを詳細に分析して親書庫と内部パスを特定
            if parent_path:
                parent_archive_path = parent_path
                self._manager.debug_info(f"親書庫を検出: {parent_archive_path}, 内部パス: {internal_path}")
            else:
                self._manager.debug_warning(f"親書庫が見つかりません: {archive_path}")
                return []
            
            # 絶対パスの確保
            if parent_archive_path and self._manager.current_path and not os.path.isabs(parent_archive_path):
                abs_path = os.path.join(self._manager.current_path, parent_archive_path).replace('\\', '/')
                self._manager.debug_info(f"相対パスを絶対パスに変換: {parent_archive_path} -> {abs_path}")
                parent_archive_path = abs_path
            
            # 2. 親書庫のハンドラを取得
            parent_handler = self._manager.get_handler(parent_archive_path)
            if not parent_handler:
                self._manager.debug_warning(f"親書庫のハンドラが見つかりません: {parent_archive_path}")
                return []
            
            # 3. ネスト書庫のコンテンツを取得
            self._manager.debug_info(f"親書庫からネスト書庫のコンテンツを取得: {parent_archive_path} -> {internal_path}")
            try:
                nested_archive_content = parent_handler.read_archive_file(parent_archive_path, internal_path)
            except (IOError, PermissionError) as e:
                # IO/Permissionエラーの場合はエントリステータスをBROKENに設定し処理を続行
                self._manager.debug_error(f"親書庫からネスト書庫のコンテンツ取得中にIO/Permissionエラー: {e}")
                if hasattr(arc_entry, 'status'):
                    arc_entry.status = EntryStatus.BROKEN
                else:
                    arc_entry.status = EntryStatus.BROKEN
                # このアーカイブは処理できないので空リストを返す
                return []
            
            if not nested_archive_content:
                self._manager.debug_warning(f"親書庫からネスト書庫のコンテンツ取得に失敗")
                return []
            
            self._manager.debug_info(f"親書庫からネスト書庫のコンテンツを取得成功: {len(nested_archive_content)} バイト")

            # 4. ネスト書庫のハンドラを取得
            handler = self._manager.get_handler(archive_path)
            if not handler:
                self._manager.debug_warning(f"書庫のハンドラが見つかりません: {archive_path}")
                return []
            
            # 5. ネスト書庫のコンテンツの処理方法を決定
            # バイトデータからエントリリストを取得できるか確認
            can_process_bytes = handler.can_handle_bytes(nested_archive_content, archive_path)

            # 現在のエントリにcacheプロパティがあるか確認
            if not hasattr(arc_entry, 'cache'):
                self._manager.debug_info(f"エントリにcacheプロパティがありません。作成します。")
                arc_entry.cache = None

            # キャッシュ処理 - 重要: ネスト書庫自身のコンテンツをキャッシュする
            if can_process_bytes:
                # バイトデータを直接処理できる場合、バイトデータをキャッシュ
                self._manager.debug_info(f"ネスト書庫のバイトデータをキャッシュします ({len(nested_archive_content)} バイト)")
                arc_entry.cache = nested_archive_content
                self._manager.debug_info(f"ネスト書庫のバイトデータをキャッシュしました ({arc_entry.path} )")
            else:
                # バイトデータを直接処理できない場合は一時ファイルを作成してパスをキャッシュ
                self._manager.debug_info(f"ネスト書庫の一時ファイルパスをキャッシュします")
                
                # 拡張子を取得
                _, ext = os.path.splitext(archive_path)
                if not ext:
                    ext = '.bin'  # デフォルト拡張子
                
                # 一時ファイルに書き込む
                try:
                    temp_file_path = self._manager._temp_file_manager.save_to_temp_file(nested_archive_content, ext)
                    if not temp_file_path:
                        self._manager.debug_error(f"一時ファイル作成に失敗しました")
                        return []
                    
                    self._manager.debug_info(f"一時ファイルを作成: {temp_file_path}")
                    # 一時ファイルパスをキャッシュ
                    arc_entry.cache = temp_file_path
                    self._manager._temp_files.add(temp_file_path)  # 後でクリーンアップするためにリストに追加
                except Exception as e:
                    self._manager.debug_error(f"一時ファイル処理中にエラー: {e}", trace=True)
                    if 'temp_file_path' in locals() and temp_file_path and os.path.exists(temp_file_path):
                        try:
                            self._manager._temp_file_manager.remove_temp_file(temp_file_path)
                        except Exception as e2:
                            self._manager.debug_error(f"一時ファイル削除中にエラー: {e2}")
                    return []
            
            # 6. エントリリストを取得
            entries = None
            
            try:
                # バイトデータから直接エントリリストを取得
                if can_process_bytes:
                    entries = handler.list_all_entries_from_bytes(nested_archive_content)
                    self._manager.debug_info(f"バイトデータから {len(entries) if entries else 0} エントリを取得")
                # 一時ファイルからエントリリストを取得
                elif 'temp_file_path' in locals() and temp_file_path:
                    entries = handler.list_all_entries(temp_file_path)
                    self._manager.debug_info(f"一時ファイルから {len(entries) if entries else 0} エントリを取得")
            except (IOError, PermissionError) as e:
                # IO/Permissionエラーの場合はエントリステータスをBROKENに設定し処理を続行
                self._manager.debug_error(f"エントリリスト取得中にIO/Permissionエラー: {e}", trace=True)
                if hasattr(arc_entry, 'status'):
                    arc_entry.status = EntryStatus.BROKEN
                else:
                    arc_entry.status = EntryStatus.BROKEN
                # このアーカイブは処理できないので空リストを返す
                return []
            except Exception as e:
                self._manager.debug_error(f"エントリリスト取得中にエラー: {e}", trace=True)
            
            # エラーチェック
            if not entries:
                self._manager.debug_warning(f"エントリが取得できませんでした")
                return []
                
            # 7. エントリリストの処理
            result_entries = []
            
            # スレッドセーフにキャッシュ登録するためのロック取得
            # すでにキャッシュロックがManagerにあるならそれを使用、なければ作成
            cache_lock = getattr(self._manager, '_cache_lock', None)
            if cache_lock is None:
                self._manager._cache_lock = threading.RLock()
                cache_lock = self._manager._cache_lock
            
            for entry in entries:
                # パスを構築
                entry_path = f"{archive_path}/{entry.rel_path}" if entry.path else archive_path
                
                # 新しいエントリを作成
                new_entry = handler.create_entry_info(
                    name=entry.name,
                    abs_path=entry_path,  # abs_pathにentry_pathを設定
                    rel_path=entry.rel_path,
                    type=entry.type,
                    size=entry.size,
                    modified_time=entry.modified_time,
                    created_time=entry.created_time,
                    is_hidden=entry.is_hidden,
                    name_in_arc=entry.name_in_arc,
                    attrs=entry.attrs,
                    path=entry_path  # pathにもentry_pathを設定
                )
                
                # 作成したエントリを即座にファイナライズ
                finalized_entry = self._manager.finalize_entry(new_entry, arc_entry.path)
                
                # ファイナライズしたエントリをすぐにキャッシュに登録（マルチスレッドセーフに）
                with cache_lock:
                    entry_key = finalized_entry.rel_path.rstrip('/')
                    if entry_key or entry_key == "":  # 空文字列キー（ルート）も登録可能に
                        self._manager._entry_cache.register_entry(entry_key, finalized_entry)
                        self._manager.debug_debug(f"エントリを即時キャッシュに登録 (スレッドID: {thread_id}): {entry_key}")
                
                # エントリを結果に追加
                result_entries.append(finalized_entry)
            
            # 9. キャッシュに保存 - スレッドセーフ対応のため、一括登録ではなく上記で個別登録済み
            self._manager.debug_info(f"{len(result_entries)} エントリをキャッシュに登録済み")
            
            # キャッシュ状態のデバッグ情報
            self._manager.debug_debug(f"キャッシュ状況:")
            self._manager.debug_debug(f"  書庫キャッシュ: arc_entry.cache {'あり' if arc_entry.cache is not None else 'なし'}")
            sample_paths = [e.path for e in result_entries[:min(3, len(result_entries))]]
            self._manager.debug_debug(f"  キャッシュされたエントリパス例: {sample_paths}")
            
            # 処理が成功したらステータスをREADYに設定
            if hasattr(arc_entry, 'status'):
                arc_entry.status = EntryStatus.READY
            else:
                arc_entry.status = EntryStatus.READY
            
            return result_entries
        
        except (IOError, PermissionError) as e:
            # IO/Permissionエラーの場合はエントリステータスをBROKENに設定し処理を続行
            self._manager.debug_error(f"_process_archive_for_all_entries でIO/Permissionエラー: {e}")
            if hasattr(arc_entry, 'status'):
                arc_entry.status = EntryStatus.BROKEN
            else:
                arc_entry.status = EntryStatus.BROKEN
            return []
        except Exception as e:
            self._manager.debug_error(f"_process_archive_for_all_entries でエラー: {e}", trace=True)
            return []
    
    def list_all_entries(self, path: str) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるすべてのエントリを再帰的に取得する
        
        Args:
            path: リストを取得するディレクトリやアーカイブのパス（ベースパス）
            
        Returns:
            すべてのエントリ情報のリスト
        """
        # パスを正規化
        norm_path = path.replace('\\', '/')
        
        # ループ検出 - 既に処理中のパスをチェック
        if not hasattr(self._manager, '_processing_paths'):
            self._manager._processing_paths = set()
            
        if norm_path in self._manager._processing_paths:
            self._manager.debug_warning(f"既に処理中のパスが再度呼び出されました: {norm_path}")
            return []  # 既に処理中なら空リストを返す
        
        # このパスを処理中としてマーク
        self._manager._processing_paths.add(norm_path)
        
        try:
            # 探索済みエントリとプロセス済みパスをリセット
            # キャッシュをリセットし、保持している一時ファイルも削除
            self._manager._entry_cache.reset_all_entries()
            self._manager._processed_paths = set()
            
            # パス深度のキャッシュをリセット
            if hasattr(self._thread_local, 'archive_path_depths'):
                self._thread_local.archive_path_depths = {}
            
            try:
                # ルートエントリを取得（この処理で全エントリが取得され、キャッシュに登録される）
                self._manager.debug_debug(f"[list_all_entries] ensure_root_entry 呼び出し開始: {path}")
                root_entry = self._manager._root_manager.ensure_root_entry(path)
                if not root_entry:
                    self._manager.debug_warning(f"ルートエントリの取得に失敗しました: {path}")
                    return []
                    
                self._manager.debug_info(f"ルートエントリを取得: {root_entry.path}")
                
                # ルートエントリ処理中に検出されたネスト書庫候補を取得
                nested_archives = self._manager._root_manager.get_nested_archives()
                self._manager.debug_info(f"ルートエントリ処理で {len(nested_archives)} 個のネスト書庫候補を検出")
                
                # ネストされたアーカイブを処理 - 初期キューにルート処理で見つかったネスト書庫を使用
                if nested_archives:
                    # ネスト書庫処理（キャッシュにエントリを追加するだけで結果は直接使わない）
                    self._process_nested_archives_with_initial_queue(path, [], nested_archives)
                    self._manager.debug_info(f"ネスト書庫の処理が完了しました")
                else:
                    self._manager.debug_info("ネスト書庫候補が見つからなかったため、ネスト処理をスキップします")
                
                # 最終的にキャッシュから全エントリリストを取得して返す
                all_entries = list(self._manager._entry_cache.get_all_entries().values())
                self._manager.debug_info(f"合計 {len(all_entries)} エントリを取得（ネスト書庫を含む）")
                
                return all_entries
            
            except (IOError, PermissionError) as e:
                # IO/Permissionエラーの場合はメッセージを記録し、可能であればルートエントリを返す
                self._manager.debug_error(f"list_all_entries でIO/Permissionエラー: {e}", trace=True)
                # エラーが発生しても、ルートエントリが取得できていれば返す
                if 'root_entry' in locals() and root_entry:
                    return [root_entry]
                return []
            except Exception as e:
                self._manager.debug_error(f"list_all_entries エラー: {e}", trace=True)
                # エラーが発生しても、ルートエントリが取得できていれば返す
                if 'root_entry' in locals() and root_entry:
                    return [root_entry]
                return []
        finally:
            # このパスの処理が完了したのでマークを解除
            self._manager._processing_paths.discard(norm_path)
    
    def _process_nested_archives_with_initial_queue(self, base_path: str, entries: List[EntryInfo], initial_archives: List[EntryInfo]) -> None:
        """
        ルートエントリ処理で見つかったネスト書庫をキューの初期値として処理する
        
        Args:
            base_path: 基準となるパス
            entries: 処理するエントリリスト（使用されない）
            initial_archives: 初期キューとして使用するネスト書庫リスト
        """
        # 処理済みアーカイブのパスを追跡するセット
        processed_archives = set()
        
        # ルート書庫(base_path)自体は処理対象外
        self._manager.debug_info(f"ルート書庫自身はネスト処理対象ではありません: {base_path}")
        processed_archives.add(base_path)
        
        # 初期キューを使用するので、エントリからアーカイブを抽出する必要はない
        if not initial_archives:
            self._manager.debug_info("初期ネスト書庫キューが空です")
            return
            
        self._manager.debug_info(f"初期キューに {len(initial_archives)} 個のネスト書庫があります")
        
        # アーカイブ処理に同期または非同期処理のどちらを使うか決定
        if len(initial_archives) < self.MIN_ARCHIVES_FOR_THREADING:
            self._manager.debug_info(f"単一スレッドのキューベース処理を使用します (書庫数: {len(initial_archives)})")
            self._process_nested_archives_with_queue(base_path, [], initial_archives, processed_archives)
        else:
            self._manager.debug_info(f"マルチスレッドのキューベース処理を使用します (書庫数: {len(initial_archives)}, スレッド数: {self._thread_count})")
            self._process_nested_archives_with_thread_pool(base_path, [], initial_archives, processed_archives)
    
    # 以下の方法は後方互換性のために維持し、内部で新しいメソッドを呼び出す
    def _process_nested_archives(self, base_path: str, entries: List[EntryInfo]) -> List[EntryInfo]:
        """
        ネストされたアーカイブを処理する（マルチスレッド対応）
        
        このメソッドは後方互換性のために維持されています。
        新しいコードでは _process_nested_archives_with_initial_queue を使用してください。
        
        Args:
            base_path: 基準となるパス
            entries: 処理するエントリリスト
            
        Returns:
            処理後の全エントリリスト（ネストされたアーカイブの内容を含む）
        """
        # 処理結果を格納するリスト（元のエントリリストのコピー）
        all_entries = list(entries)
        
        # 処理済みアーカイブのパスを追跡するセット
        processed_archives = set()
        
        # ルート書庫(base_path)自体は処理対象外
        self._manager.debug_info(f"ルート書庫自身はネスト処理対象ではありません: {base_path}")
        processed_archives.add(base_path)
        
        # エントリからアーカイブタイプのものだけを抽出（ルート書庫を除く）
        archive_entries = []
        for entry in entries:
            if entry.type == EntryType.ARCHIVE and entry.path != base_path:
                # ネスト構造の循環参照を検出するために深度を確認（安全装置）
                depth = self._get_archive_path_depth(entry.path)
                if depth < self.MAX_NEST_DEPTH:
                    archive_entries.append(entry)
                    self._manager.debug_info(f"処理対象ネスト書庫を検出: {entry.path} (階層: {depth})")
                else:
                    self._manager.debug_warning(f"潜在的な循環参照を検出 - スキップ: {entry.path} (階層: {depth})")
        
        # アーカイブが見つからない場合は元のリストをそのまま返す
        if not archive_entries:
            self._manager.debug_info("処理対象のネスト書庫が見つかりません")
            return all_entries
            
        self._manager.debug_info(f"{len(archive_entries)} 個のネスト書庫を検出")
        
        # アーカイブ処理に同期または非同期処理のどちらを使うか決定
        if len(archive_entries) < self.MIN_ARCHIVES_FOR_THREADING:
            self._manager.debug_info(f"単一スレッドのキューベース処理を使用します (書庫数: {len(archive_entries)})")
            return self._process_nested_archives_with_queue(base_path, all_entries, archive_entries, processed_archives)
        else:
            self._manager.debug_info(f"マルチスレッドのキューベース処理を使用します (書庫数: {len(archive_entries)}, スレッド数: {self._thread_count})")
            return self._process_nested_archives_with_thread_pool(base_path, all_entries, archive_entries, processed_archives)
    
    def _process_nested_archives_with_queue(
        self, base_path: str, entries: List[EntryInfo], 
        archive_entries: List[EntryInfo], processed_archives: Set[str]
    ) -> None:
        """
        キューを使用してネストされたアーカイブを順次処理する（シングルスレッド）
        
        Args:
            base_path: 基準となるパス
            entries: 処理するエントリリスト（使用されない）
            archive_entries: 処理するアーカイブエントリリスト（初期キュー）
            processed_archives: 処理済みアーカイブパスのセット
        """
        # 処理すべきアーカイブのキューを作成
        archive_queue = deque(archive_entries)
        
        # キューが空になるまで処理を続ける
        processed_count = 0
        while archive_queue:
            # キューから次のアーカイブを取得
            arc_entry = archive_queue.popleft()
            print("processing" + arc_entry.path)
            # 重複処理防止（既に処理済みならスキップ）
            if arc_entry.path in processed_archives:
                continue
            
            # 処理済みとしてマーク
            processed_archives.add(arc_entry.path)
            processed_count += 1
            
            # アーカイブ内のエントリを処理（深度制限のチェックはメソッド内で実施）
            try:
                nested_entries = self.process_archive_for_all_entries(base_path, arc_entry)
                
                if nested_entries:
                    # エントリはprocess_archive_for_all_entriesの中でキャッシュに登録済み
                    self._manager.debug_info(f"ネスト書庫から {len(nested_entries)} エントリを処理: {arc_entry.path}")
                    
                    # 新しく見つかったアーカイブをキューに追加（深度制限なし）
                    new_archives_found = 0
                    for nested_entry in nested_entries:
                        if nested_entry.type == EntryType.ARCHIVE and nested_entry.path not in processed_archives:
                            archive_queue.append(nested_entry)
                            new_archives_found += 1
                    
                    if new_archives_found > 0:
                        self._manager.debug_info(f"新しいネスト書庫 {new_archives_found} 個をキューに追加 (現在のキューサイズ: {len(archive_queue)})")
            except Exception as e:
                self._manager.debug_warning(f"ネスト書庫の処理でエラー: {arc_entry.path} - {e}")
                # エラーが発生しても処理を継続
        
        self._manager.debug_info(f"キュー処理完了: {processed_count} 個のアーカイブを処理")
    
    def _process_nested_archives_with_thread_pool(
        self, base_path: str, entries: List[EntryInfo], 
        archive_entries: List[EntryInfo], processed_archives: Set[str]
    ) -> None:
        """
        スレッドプールとキューを使用してネストされたアーカイブを並列処理する
        
        Args:
            base_path: 基準となるパス
            entries: 処理するエントリリスト（使用されない）
            archive_entries: 処理するアーカイブエントリリスト（初期キュー）
            processed_archives: 処理済みアーカイブパスのセット
        """
        # スレッド間で共有するキューとロック
        task_queue = queue.Queue()
        results_lock = threading.Lock()
        
        # 初期アーカイブをキューに追加
        for arc_entry in archive_entries:
            if arc_entry.path not in processed_archives:
                task_queue.put(arc_entry)
                processed_archives.add(arc_entry.path)
                
        # スレッドプールとワーカー関数を定義
        def worker():
            while True:
                try:
                    # キューから次のタスクを取得（非ブロッキング）
                    try:
                        arc_entry = task_queue.get(block=False)
                    except queue.Empty:
                        # キューが空になったら終了
                        break
                    
                    # アーカイブ情報の表示
                    thread_id = threading.get_ident()
                    depth = self._get_archive_path_depth(arc_entry.path)
                    self._manager.debug_info(f"スレッド処理: ネスト書庫 {arc_entry.path} (スレッドID: {thread_id}, 階層: {depth})")
                    
                    # アーカイブ内のエントリを処理
                    try:
                        nested_entries = self.process_archive_for_all_entries(base_path, arc_entry)
                        
                        if nested_entries:
                            # エントリはprocess_archive_for_all_entriesの中でキャッシュに登録済み
                            self._manager.debug_info(f"スレッド {thread_id}: ネスト書庫から {len(nested_entries)} エントリを処理: {arc_entry.path}")
                            
                            # 新しく見つかったアーカイブをキューに追加（深度制限なし）
                            for nested_entry in nested_entries:
                                if nested_entry.type == EntryType.ARCHIVE:
                                    # 処理済みかどうかをチェック（ロックで保護）
                                    with results_lock:
                                        if nested_entry.path not in processed_archives:
                                            # キューに追加し、処理済みとしてマーク
                                            task_queue.put(nested_entry)
                                            processed_archives.add(nested_entry.path)
                                            self._manager.debug_info(f"スレッド {thread_id}: 新しいネスト書庫をキューに追加: {nested_entry.path}")
                    except Exception as e:
                        self._manager.debug_warning(f"スレッド {thread_id}: ネスト書庫の処理でエラー: {arc_entry.path} - {e}")
                    
                    # タスク完了を通知
                    task_queue.task_done()
                    
                except Exception as e:
                    self._manager.debug_error(f"ワーカースレッドでエラー: {e}", trace=True)
                    # エラーが発生しても処理を継続
        
        # スレッドプールを作成して処理を開始
        self._manager.debug_info(f"スレッドプールを作成: {self._thread_count} スレッド")
        threads = []
        for _ in range(self._thread_count):
            thread = threading.Thread(target=worker)
            thread.daemon = True  # メインスレッドが終了したら一緒に終了するように
            thread.start()
            threads.append(thread)
        
        # すべてのスレッドが終了するまで待機
        for thread in threads:
            thread.join()
            
        processed_count = len(processed_archives) - len(entries)  # 元のエントリは除外
        self._manager.debug_info(f"並列処理完了: {processed_count} 個のアーカイブを処理")
    
    # 以下のメソッドは非推奨としてマーク
    def _process_nested_archives_sequential(
        self, base_path: str, entries: List[EntryInfo], 
        archive_entries: List[EntryInfo], processed_archives: Set[str]
    ) -> List[EntryInfo]:
        """
        ネストされたアーカイブを順次処理する（シングルスレッド）
        
        このメソッドは後方互換性のために維持されています。
        代わりに _process_nested_archives_with_queue を使用してください。
        
        Args:
            base_path: 基準となるパス
            entries: 処理するエントリリスト
            archive_entries: 処理するアーカイブエントリリスト
            processed_archives: 処理済みアーカイブパスのセット
            
        Returns:
            処理後の全エントリリスト
        """
        return self._process_nested_archives_with_queue(base_path, entries, archive_entries, processed_archives)
    
    def _process_nested_archives_parallel(
        self, base_path: str, entries: List[EntryInfo], 
        archive_entries: List[EntryInfo], processed_archives: Set[str]
    ) -> List[EntryInfo]:
        """
        ネストされたアーカイブを並列処理する（マルチスレッド）
        
        このメソッドは後方互換性のために維持されています。
        代わりに _process_nested_archives_with_thread_pool を使用してください。
        
        Args:
            base_path: 基準となるパス
            entries: 処理するエントリリスト
            archive_entries: 処理するアーカイブエントリリスト
            processed_archives: 処理済みアーカイブパスのセット
            
        Returns:
            処理後の全エントリリスト
        """
        return self._process_nested_archives_with_thread_pool(base_path, entries, archive_entries, processed_archives)
