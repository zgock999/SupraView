"""
アーカイブ処理コンポーネント

アーカイブの読み込みと処理を担当します。
"""

import os
from typing import List, Optional, Dict, Set

from ...arc import EntryInfo, EntryType, EntryStatus

class ArchiveProcessor:
    """
    アーカイブ処理クラス
    
    アーカイブファイルの処理、内部エントリの抽出と登録を行います。
    """
    
    # 最大ネスト階層の深さ制限（元の実装と同様に）
    MAX_NEST_DEPTH = 5
    
    def __init__(self, manager):
        """
        アーカイブプロセッサーを初期化する
        
        Args:
            manager: 親となるEnhancedArchiveManagerインスタンス
        """
        self._manager = manager
        # 処理中のネストレベル（再帰制限用）
        self._current_nest_level = 0
    
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
        # 循環参照防止とネスト深度チェック
        if self._current_nest_level >= self.MAX_NEST_DEPTH:
            self._manager.debug_warning(f"最大ネスト階層 ({self.MAX_NEST_DEPTH}) に達しました")
            return []
        
        # 再帰レベルを増加
        self._current_nest_level += 1
        
        try:
            archive_path = arc_entry.path
            self._manager.debug_info(f"アーカイブ処理: {archive_path}")
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
                            # ネストされたエントリのパスを修正
                            entries = self._manager.finalize_entries(entries, archive_path)
                            # 結果を返す前にEntryTypeをマーク
                            marked_entries = self._mark_archive_entries(entries)
                            self._manager.debug_info(f"物理アーカイブから {len(marked_entries)} エントリを取得")
                            return marked_entries
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
                
            # 7. エントリリストの処理 - パスの修正とファイナライズを同時に行う
            result_entries = []
            
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
                
                # エントリを結果に追加
                result_entries.append(finalized_entry)
            
            # 8. アーカイブエントリを識別
            marked_entries = self._mark_archive_entries(result_entries)
            
            # 9. キャッシュに保存 - 各エントリを個別に登録（オリジナルの実装方法を使用）
            self._manager.debug_info(f"{len(result_entries)} エントリをキャッシュに登録")
            
            # 各エントリを個別にキャッシュに追加（パスをキーとして使用）
            for entry in result_entries:
                # キャッシュ登録用のキー（相対パス）を取得し、末尾の/を取り除く
                entry_key = entry.rel_path.rstrip('/')
                # キャッシュに登録（オリジナルの方法で直接エントリを登録）
                if entry_key or entry_key == "":  # 空文字列キー（ルート）も登録可能に
                    self._manager._entry_cache.register_entry(entry_key, entry)
                    self._manager.debug_debug(f"エントリ {entry_key} をキャッシュに登録")
            
            # キャッシュ状態のデバッグ情報
            self._manager.debug_debug(f"キャッシュ状況:")
            self._manager.debug_debug(f"  書庫キャッシュ: arc_entry.cache {'あり' if arc_entry.cache is not None else 'なし'}")
            sample_paths = [e.path for e in marked_entries[:min(3, len(marked_entries))]]
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
        finally:
            # 再帰レベルを減少
            self._current_nest_level -= 1
    
    def _mark_archive_entries(self, entries: List[EntryInfo]) -> List[EntryInfo]:
        """
        エントリリストの中からファイル拡張子がアーカイブのものをアーカイブタイプとしてマーク
        
        Args:
            entries: 処理するエントリリスト
            
        Returns:
            処理後のエントリリスト
        """
        if not entries:
            return []
            
        for entry in entries:
            if entry.type == EntryType.FILE and self._manager._path_resolver.is_archive_by_extension(entry.name):
                entry.type = EntryType.ARCHIVE
        return entries
    
    def list_all_entries(self, path: str, recursive: bool = True) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるすべてのエントリを再帰的に取得する
        
        Args:
            path: リストを取得するディレクトリやアーカイブのパス（ベースパス）
            recursive: 再帰的に探索するかどうか（デフォルトはTrue）
            
        Returns:
            すべてのエントリ情報のリスト
        """
        # 探索済みエントリとプロセス済みパスをリセット
        self._manager._entry_cache.clear_cache()
        self._manager._processed_paths = set()
        
        # パスを正規化
        path = path.replace('\\', '/')
        
        try:
            # キャッシュをクリアした後、最初にルートエントリをキャッシュに追加
            self._manager.debug_debug(f"[list_all_entries] _ensure_root_entry 呼び出し前")
            self._manager._root_manager.ensure_root_entry(path)
            
            # 1. 最初にルートパス自身のエントリ情報を取得
            root_entry_info = self._manager.get_entry_info("")
            
            # 2. ハンドラを取得（ファイル種別に合わせて適切なハンドラ）
            handler = self._manager.get_handler(path)
            if not handler:
                self._manager.debug_warning(f"パス '{path}' のハンドラが見つかりません")
                # ルートエントリがあれば、それだけを返す
                if root_entry_info:
                    return [root_entry_info]
                return []
            
            self._manager.debug_info(f"'{handler.__class__.__name__}' を使用して再帰的にエントリを探索します")
            
            # 3. 最初のレベルのエントリリストを取得
            try:
                raw_base_entries = handler.list_all_entries(path)
                # 成功したらルートエントリをREADYに設定
                if root_entry_info and hasattr(root_entry_info, 'status'):
                    root_entry_info.status = EntryStatus.READY
            except (IOError, PermissionError) as e:
                # IO/Permissionエラーの場合はエントリステータスをBROKENに設定し処理を続行
                self._manager.debug_error(f"ベースレベルのエントリリスト取得中にIO/Permissionエラー: {e}", trace=True)
                if root_entry_info and hasattr(root_entry_info, 'status'):
                    root_entry_info.status = EntryStatus.BROKEN
                # エントリが取得できなくても、ルートエントリ自体は返す
                return [root_entry_info] if root_entry_info else []
            except Exception as e:
                self._manager.debug_error(f"ベースレベルのエントリリスト取得中にエラー: {e}", trace=True)
                # エントリが取得できなくても、ルートエントリ自体は返す
                return [root_entry_info] if root_entry_info else []
                
            if not raw_base_entries:
                self._manager.debug_warning(f"エントリが見つかりませんでした: {path}")
                # エントリが取得できなくても、ルートエントリ自体は返す
                if root_entry_info:
                    self._manager.debug_info(f"ルートエントリのみを返します")
                    return [root_entry_info]
                return []
            
            # ハンドラが返したエントリを一つずつファイナライズ処理する
            base_entries = []
            for entry in raw_base_entries:
                finalized_entry = self._manager.finalize_entry(entry, path)
                base_entries.append(finalized_entry)
            
            self._manager.debug_info(f"ベースレベルで {len(base_entries)} エントリを取得しました")
            
            # 5. 結果リストを構築（ルートエントリを先頭に）
            all_entries = []
            
            # ルートエントリが取得できた場合は、リストの最初に追加
            if root_entry_info:
                # ファイナライズでアーカイブ判定が行われるため、ここではfinalize_entryを適用
                root_entry_info = self._manager.finalize_entry(root_entry_info, path)
                self._manager.debug_info(f"ルートエントリをリストに追加: {root_entry_info.path}")
                all_entries.append(root_entry_info)
            
            # ベースエントリを結果リストに追加
            all_entries.extend(base_entries)
            
            # 6. キャッシュに保存 - 各エントリを個別に登録
            for entry in base_entries:
                # 相対パスをキャッシュのキーとして使用し、末尾の/を取り除く
                entry_key = entry.rel_path.rstrip('/')
                # 空でない相対パスのみ登録
                if entry_key or entry_key == "":  # 空文字列キー（ルート）も登録可能に
                    self._manager._entry_cache.register_entry(entry_key, entry)
                    self._manager.debug_debug(f"ベースエントリ {entry_key} をキャッシュに登録")
            
            # 7. アーカイブエントリを再帰的に処理
            if recursive:
                processed_archives = set()  # 処理済みアーカイブの追跡
                archive_queue = []  # 処理するアーカイブのキュー
                
                # 最初のレベルでアーカイブを検索
                for entry in base_entries:
                    if entry.type == EntryType.ARCHIVE:
                        archive_queue.append(entry)
                
                self._manager.debug_info(f"{len(archive_queue)} 個のネスト書庫を検出")
                
                # アーカイブを処理
                while archive_queue:
                    arc_entry = archive_queue.pop(0)
                    
                    # 既に処理済みならスキップ
                    if arc_entry.path in processed_archives:
                        continue
                    
                    # 処理済みとしてマーク
                    processed_archives.add(arc_entry.path)
                    
                    # アーカイブの内容を処理（さらに下のレベルへ）
                    try:
                        nested_entries = self.process_archive_for_all_entries(path, arc_entry)
                        
                        # 結果を追加
                        if nested_entries:
                            all_entries.extend(nested_entries)
                            
                            # ネスト書庫内の各エントリを個別に登録
                            for nested_entry in nested_entries:
                                # エントリキー（相対パス）を正規化
                                entry_key = nested_entry.rel_path
                                # キーの正規化（先頭のスラッシュを削除、末尾のスラッシュを削除）
                                if entry_key.startswith('/'):
                                    entry_key = entry_key[1:]
                                entry_key = entry_key.rstrip('/')
                                
                                # 空でない相対パスのみ登録
                                if entry_key or entry_key == "":  # 空文字列キー（ルート）も登録可能に
                                    self._manager._entry_cache.register_entry(entry_key, nested_entry)
                                    
                                    # ネストされたアーカイブも処理するためにキューに追加
                                    if nested_entry.type == EntryType.ARCHIVE and nested_entry.path not in processed_archives:
                                        archive_queue.append(nested_entry)
                    except (IOError, PermissionError) as e:
                        # IO/Permissionエラーの場合はエントリステータスをBROKENに設定し処理を続行
                        self._manager.debug_error(f"アーカイブ処理中にIO/Permissionエラー: {arc_entry.path} - {e}")
                        if hasattr(arc_entry, 'status'):
                            arc_entry.status = EntryStatus.BROKEN
                        else:
                            arc_entry.status = EntryStatus.BROKEN
                        continue
                    except Exception as e:
                        # エラーが発生してもBROKENとマークして処理を継続
                        self._manager.debug_error(f"アーカイブ処理中にエラー: {arc_entry.path} - {e}")
                        continue
            
            return all_entries
        except (IOError, PermissionError) as e:
            # IO/Permissionエラーの場合はメッセージを記録し、可能であればルートエントリを返す
            self._manager.debug_error(f"list_all_entries でIO/Permissionエラー: {e}", trace=True)
            # エラーが発生しても、ルートエントリが取得できていれば返す
            if 'root_entry_info' in locals() and root_entry_info:
                if hasattr(root_entry_info, 'status'):
                    root_entry_info.status = EntryStatus.BROKEN
                return [root_entry_info]
            return []
        except Exception as e:
            self._manager.debug_error(f"list_all_entries エラー: {e}", trace=True)
            # エラーが発生しても、ルートエントリが取得できていれば返す
            if 'root_entry_info' in locals() and root_entry_info:
                return [root_entry_info]
            return []
