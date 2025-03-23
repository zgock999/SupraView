"""
ルートエントリ管理コンポーネント

ルートエントリの作成と管理を担当します。
"""

import os
import datetime
from typing import Optional, List, Set

from ...arc import EntryInfo, EntryType, EntryStatus

class RootEntryManager:
    """
    ルートエントリ管理クラス
    
    ルートエントリ（ベースディレクトリまたはアーカイブ）の作成と管理を行います。
    """
    
    def __init__(self, manager):
        """
        ルートエントリマネージャーを初期化する
        
        Args:
            manager: 親となるEnhancedArchiveManagerインスタンス
        """
        self._manager = manager
        # ネスト書庫候補を保存する属性を追加
        self._nested_archives = []
    
    def get_nested_archives(self) -> List[EntryInfo]:
        """
        ルートエントリの処理中に検出されたネスト書庫候補リストを取得する
        
        Returns:
            ネスト書庫エントリのリスト
        """
        return self._nested_archives
    
    def clear_nested_archives(self) -> None:
        """
        ネスト書庫候補リストをクリアする
        """
        self._nested_archives = []
        self._manager.debug_info("ネスト書庫候補リストをクリアしました")
    
    def ensure_root_entry(self, path: str) -> Optional[EntryInfo]:
        """
        ルートエントリをキャッシュに追加し、返す
        
        Args:
            path: ルートとなるパス
            
        Returns:
            ルートエントリ。作成に失敗した場合はNone
            
        Raises:
            FileNotFoundError: 指定されたパスが存在しない場合
            RuntimeError: ハンドラが見つからない場合
            Exception: その他の予期せぬエラーが発生した場合
        """
        try:
            # ネスト書庫候補リストをクリア
            self.clear_nested_archives()
            
            # 物理ファイルとして存在しないパスの場合は例外を投げる
            if not os.path.exists(path):
                self._manager.debug_error(f"パス '{path}' は物理ファイルとして存在しません")
                raise FileNotFoundError(f"指定されたパス '{path}' が見つかりません")
            
            # キャッシュが既に初期化されているかチェック
            if "" in self._manager._entry_cache.get_all_entries():
                self._manager.debug_info(f"ルートエントリはキャッシュに既に存在します")
                return self._manager._entry_cache.get_entry_info("")
            
            # 適切なハンドラを取得
            handler = self._manager.get_handler(path)
            
            if not handler:
                # ハンドラが見つからない場合は、プログラムのバグとして例外を発生させる
                error_msg = f"パス '{path}' に対するハンドラが見つかりません。ハンドラの登録に問題があります。"
                self._manager.debug_error(error_msg)
                raise RuntimeError(error_msg)
            
            # ハンドラの種類に関わらず、統一した方法でルートエントリを処理
            return self._process_root_with_handler(path, handler)
        except (FileNotFoundError, RuntimeError):
            # パスが存在しない場合やハンドラが見つからない場合は上位に例外を伝播させる
            raise
        except Exception as e:
            # その他の予期せぬエラーの場合は上位に例外を伝播させる
            self._manager.debug_error(f"ensure_root_entry で予期せぬエラー: {path} - {e}", trace=True)
            raise
    
    def _process_root_with_handler(self, path: str, handler) -> Optional[EntryInfo]:
        """
        ハンドラを使用してルートエントリを処理する
        
        Args:
            path: 処理するパス
            handler: 使用するハンドラ
            
        Returns:
            処理結果のルートエントリ
            
        Raises:
            Exception: 予期せぬエラーが発生した場合
        """
        try:
            self._manager.debug_info(f"ハンドラ {handler.__class__.__name__} を使用してルートエントリを処理: {path}")
            
            # ルートエントリを OS の情報に基づいて直接構築する
            try:
                # パスの情報を取得
                name = os.path.basename(path.rstrip('/\\')) or "Root"
                
                # ファイルタイプを判断
                entry_type = EntryType.UNKNOWN
                if os.path.isdir(path):
                    entry_type = EntryType.DIRECTORY
                elif os.path.isfile(path):
                    # アーカイブかどうかをハンドラ対応で判定
                    archive_handler = self._manager.get_handler(path)
                    if archive_handler and hasattr(archive_handler, 'can_archive') and archive_handler.can_archive():
                        entry_type = EntryType.ARCHIVE
                        self._manager.debug_info(f"アーカイブハンドラが利用可能: {archive_handler.__class__.__name__}")
                    else:
                        entry_type = EntryType.FILE
                
                # ファイル情報を取得
                stat_info = os.stat(path)
                size = stat_info.st_size if entry_type != EntryType.DIRECTORY else 0
                modified_time = datetime.datetime.fromtimestamp(stat_info.st_mtime)
                created_time = datetime.datetime.fromtimestamp(stat_info.st_ctime)
                
                # 隠しファイルかどうか判定
                is_hidden = False
                if os.name == 'nt' and hasattr(stat_info, 'st_file_attributes'):
                    import stat as stat_module
                    is_hidden = bool(stat_info.st_file_attributes & stat_module.FILE_ATTRIBUTE_HIDDEN)
                else:
                    is_hidden = name.startswith('.')
                
                # ルートエントリを作成
                root_info = EntryInfo(
                    name=name,
                    path=path,
                    rel_path="",
                    name_in_arc="",
                    type=entry_type,
                    size=size,
                    modified_time=modified_time,
                    created_time=created_time,
                    abs_path=path,
                    is_hidden=is_hidden,
                    status=EntryStatus.READY
                )
                
                self._manager.debug_info(f"OS情報からルートエントリを構築: {name} ({entry_type.name})")
            
            except (IOError, PermissionError) as e:
                # IO/権限エラーが発生した場合はBROKENなエントリを作成して続行
                self._manager.debug_error(f"ルートエントリ情報取得エラー: {path} - {e}")
                
                # ファイルタイプを推測
                entry_type = EntryType.UNKNOWN
                if os.path.isdir(path):
                    entry_type = EntryType.DIRECTORY
                elif os.path.isfile(path):
                    # アーカイブかどうかをハンドラ対応で判定
                    archive_handler = self._manager.get_handler(path)
                    if archive_handler and hasattr(archive_handler, 'can_archive') and archive_handler.can_archive():
                        entry_type = EntryType.ARCHIVE
                    else:
                        entry_type = EntryType.FILE
                
                # ファイル名/ディレクトリ名を抽出
                name = os.path.basename(path.rstrip('/\\')) or "Root"
                
                # BROKENステータスのエントリを作成
                root_info = EntryInfo(
                    name=name,
                    path=path,
                    rel_path="",
                    name_in_arc="",
                    type=entry_type,
                    size=0,
                    modified_time=None,
                    abs_path=path,
                    status=EntryStatus.BROKEN
                )
                
                # キャッシュに追加して返す
                self._manager._entry_cache.add_entry_to_cache(root_info)
                self._manager.debug_info(f"BROKENステータスのルートエントリを作成: {path}")
                return root_info
                    
            # ルートエントリをまずキャッシュに追加
            self._manager._entry_cache.add_entry_to_cache(root_info)
            self._manager.debug_info(f"ルートエントリをキャッシュに追加: {root_info.name}")
            
            # エントリの種類に応じた処理
            if os.path.isdir(path):
                # ディレクトリの場合
                self._manager.debug_info(f"ディレクトリのルートエントリを処理: {path}")
                self._process_container_entries(path, handler, root_info)
            elif os.path.isfile(path) and root_info.type == EntryType.ARCHIVE:
                # アーカイブファイルの場合
                self._manager.debug_info(f"アーカイブファイルのルートエントリを処理: {path}")
                self._process_container_entries(path, handler, root_info)
            else:
                # 通常のファイルの場合
                self._manager.debug_info(f"通常ファイルのルートエントリを処理: {path} (タイプ: {root_info.type.name})")
                # 特に追加の処理は必要ない
            
            return root_info
        
        except (IOError, PermissionError) as e:
            # IO/権限エラーはログに記録して処理を続行
            self._manager.debug_error(f"_process_root_with_handler で IO/権限エラー: {path} - {e}")
            
            # ファイルタイプを推測
            entry_type = EntryType.UNKNOWN
            if os.path.isdir(path):
                entry_type = EntryType.DIRECTORY
            elif os.path.isfile(path):
                # アーカイブかどうかをハンドラ対応で判定
                archive_handler = self._manager.get_handler(path)
                if archive_handler and hasattr(archive_handler, 'can_archive') and archive_handler.can_archive():
                    entry_type = EntryType.ARCHIVE
                else:
                    entry_type = EntryType.FILE
            
            # ファイル名/ディレクトリ名を抽出
            name = os.path.basename(path.rstrip('/\\')) or "Root"
            
            # BROKENステータスのエントリを作成
            entry = EntryInfo(
                name=name,
                path=path,
                rel_path="",
                name_in_arc="",
                type=entry_type,
                size=0,
                modified_time=None,
                abs_path=path,
                status=EntryStatus.BROKEN
            )
            
            # キャッシュに追加
            self._manager._entry_cache.add_entry_to_cache(entry)
            
            return entry
        except Exception as e:
            # その他の予期せぬエラーの場合は上位に例外を伝播させる
            self._manager.debug_error(f"_process_root_with_handler で予期せぬエラー: {path} - {e}", trace=True)
            raise
    
    def _process_container_entries(self, path: str, handler, root_info: EntryInfo) -> None:
        """
        ディレクトリまたはアーカイブエントリの内容を処理する（共通処理）
        
        Args:
            path: 対象パス
            handler: 使用するハンドラ
            root_info: ルートエントリ情報
            
        Raises:
            Exception: 予期せぬエラーが発生した場合
        """
        try:
            # アーカイブハンドラか確認（アーカイブの場合のみチェック）
            if root_info.type == EntryType.ARCHIVE and hasattr(handler, 'can_archive') and not handler.can_archive():
                self._manager.debug_info(f"ハンドラ {handler.__class__.__name__} はアーカイブをサポートしていません")
                return
            
            # コンテナ（ディレクトリまたはアーカイブ）種類の説明
            container_type = "ディレクトリ" if root_info.type == EntryType.DIRECTORY else "アーカイブ"
            
            # ハンドラの list_all_entries を使用して再帰的にすべてのエントリを取得
            self._manager.debug_info(f"{container_type}の再帰的なエントリを取得中: {path}")
            try:
                all_entries = handler.list_all_entries(path)
            except (IOError, PermissionError) as e:
                # 内容の取得に失敗した場合はルートエントリをBROKENとしてマーク
                self._manager.debug_error(f"{container_type}内容の取得エラー: {path} - {e}")
                root_info.status = EntryStatus.BROKEN
                return
            
            if all_entries:
                self._manager.debug_info(f"{container_type}から {len(all_entries)} エントリを取得 (再帰的)")
                
                # エントリをファイナライズしてから即時キャッシュに登録
                for entry in all_entries:
                    try:
                        # エントリをファイナライズ
                        finalized_entry = self._manager.finalize_entry(entry, path)
                        
                        # ファイナライズ後、即時にキャッシュに登録（二重ループ防止のため）
                        self._manager._entry_cache.add_entry_to_cache(finalized_entry)
                        
                        # アーカイブタイプのエントリは無条件にネスト書庫候補リストに追加
                        if finalized_entry.type == EntryType.ARCHIVE:
                            self._nested_archives.append(finalized_entry)
                            self._manager.debug_info(f"ネスト書庫候補を検出: {finalized_entry.path}")
                    except (IOError, PermissionError) as e:
                        # 個別エントリのエラーは無視して処理を続行（データ起因の問題）
                        error_context = "エントリ" if root_info.type == EntryType.DIRECTORY else "アーカイブエントリ"
                        self._manager.debug_warning(f"{error_context}処理エラー: {entry.path if hasattr(entry, 'path') else 'unknown'} - {e}")
                    except Exception as e:
                        # 予期せぬ例外（プログラム起因の問題）は伝播させる
                        error_context = "エントリ" if root_info.type == EntryType.DIRECTORY else "アーカイブエントリ"
                        self._manager.debug_error(f"{error_context}処理中に予期せぬエラー: {entry.path if hasattr(entry, 'path') else 'unknown'} - {e}", trace=True)
                        raise
                
                # 検出されたネスト書庫候補数を報告
                if self._nested_archives:
                    self._manager.debug_info(f"合計 {len(self._nested_archives)} 個のネスト書庫候補を検出しました")
            else:
                self._manager.debug_info(f"{container_type}は空です: {path}")
        except (IOError, PermissionError) as e:
            # IO/権限エラーは正常に処理できるエラー（データ起因）
            self._manager.debug_error(f"_process_container_entries で IO/権限エラー: {path} - {e}")
            root_info.status = EntryStatus.BROKEN
        except Exception as e:
            # その他の予期せぬエラー（プログラム起因）の場合は上位層に例外を伝播
            self._manager.debug_error(f"_process_container_entries で予期せぬエラー: {path} - {e}", trace=True)
            root_info.status = EntryStatus.BROKEN
            raise

    # 元のメソッドは削除または非推奨としてマーク
    def _process_directory_entries(self, path: str, handler, root_info: EntryInfo) -> None:
        """
        ディレクトリエントリの内容を処理する
        
        このメソッドは後方互換性のために維持されています。
        新しいコードでは _process_container_entries を使用してください。
        
        Args:
            path: ディレクトリパス
            handler: 使用するハンドラ
            root_info: ルートエントリ情報
        """
        self._process_container_entries(path, handler, root_info)

    def _process_archive_entries(self, path: str, handler, root_info: EntryInfo) -> None:
        """
        アーカイブファイルの内容を処理する
        
        このメソッドは後方互換性のために維持されています。
        新しいコードでは _process_container_entries を使用してください。
        
        Args:
            path: アーカイブファイルパス
            handler: 使用するハンドラ
            root_info: ルートエントリ情報
        """
        self._process_container_entries(path, handler, root_info)
