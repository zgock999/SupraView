"""
ルートエントリ管理コンポーネント

ルートエントリの作成と管理を担当します。
"""

import os
import datetime
from typing import Optional

from ...arc import EntryInfo, EntryType

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
    
    def get_raw_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するパス
            
        Returns:
            エントリ情報。取得できない場合はNone
        """
        if not os.path.exists(path):
            self._manager.debug_warning(f"パス '{path}' は存在しません")
            return None
        
        if os.path.isdir(path):
            # フォルダの場合
            return self._create_folder_entry(path)
        elif os.path.isfile(path):
            # ファイルの場合
            return self._create_file_entry(path)
        
        return None
    
    def _create_folder_entry(self, path: str) -> EntryInfo:
        """
        フォルダのEntryInfoを作成する
        
        Args:
            path: フォルダのパス
            
        Returns:
            フォルダのEntryInfo
        """
        folder_name = os.path.basename(path.rstrip('/\\'))
        if not folder_name:
            if ':' in path:
                # Windowsのドライブルート (C:\ など)
                drive = path.split(':')[0]
                folder_name = f"{drive}:"
            elif path.startswith('//') or path.startswith('\\\\'):
                # ネットワークパス
                parts = path.replace('\\', '/').strip('/').split('/')
                folder_name = parts[0] if parts else "Network"
            elif path.startswith('/'):
                # UNIXのルートディレクトリ
                folder_name = "/"
            else:
                # その他の特殊ケース
                folder_name = path.rstrip('/\\') or "Root"
        
        return EntryInfo(
            name=folder_name,
            path=path,
            rel_path="",
            type=EntryType.DIRECTORY,
            size=0,
            modified_time=None,
            abs_path=path
        )
    
    def _create_file_entry(self, path: str) -> EntryInfo:
        """
        ファイルのEntryInfoを作成する
        
        Args:
            path: ファイルのパス
            
        Returns:
            ファイルのEntryInfo
        """
        try:
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            modified_time = datetime.datetime.fromtimestamp(mtime)
            
            # アーカイブかどうか判定
            file_type = EntryType.FILE
            _, ext = os.path.splitext(path.lower())
            if ext in self._manager._archive_extensions:
                file_type = EntryType.ARCHIVE
                
            return EntryInfo(
                name=os.path.basename(path),
                path=path,
                rel_path="",
                type=file_type,
                size=size,
                modified_time=modified_time,
                abs_path=path
            )
        except Exception as e:
            self._manager.debug_error(f"ファイル情報取得エラー: {path} - {e}", trace=True)
            # エラーが発生した場合も最低限の情報で作成
            return EntryInfo(
                name=os.path.basename(path),
                path=path,
                rel_path="",
                type=EntryType.FILE,
                size=0,
                modified_time=None,
                abs_path=path
            )
    
    def ensure_root_entry(self, path: str) -> Optional[EntryInfo]:
        """
        ルートエントリをキャッシュに追加し、返す
        
        Args:
            path: ルートとなるパス
            
        Returns:
            ルートエントリ。作成に失敗した場合はNone
        """
        # 物理ファイルとして存在しないパスの場合は例外を投げる
        if not os.path.exists(path):
            self._manager.debug_error(f"パス '{path}' は物理ファイルとして存在しません")
            raise FileNotFoundError(f"指定されたパス '{path}' が見つかりません")
        
        # キャッシュが既に初期化されているかチェック
        if "" in self._manager._entry_cache.get_all_entries():
            self._manager.debug_info(f"ルートエントリはキャッシュに既に存在します")
            return self._manager._entry_cache.get_entry_info("")
        
        # カレントパスの種類に応じて処理を分ける
        if os.path.isdir(path):
            # フォルダの場合
            root_entry = self._process_folder_root(path)
        elif os.path.isfile(path):
            # ファイルの場合
            root_entry = self._process_file_root(path)
        else:
            self._manager.debug_error(f"パス '{path}' は未対応の種類です")
            return None
        
        # 重要な属性を明示的に設定する
        if root_entry:
            root_entry.rel_path = ""
            root_entry.abs_path = path
            
            # ルートエントリをキャッシュに追加
            self._manager._entry_cache.add_entry_to_cache(root_entry)
            
            # ルートエントリを返す
            return root_entry
        
        return None
    
    def _process_folder_root(self, path: str) -> Optional[EntryInfo]:
        """
        フォルダのルートエントリを処理する
        
        Args:
            path: フォルダのパス
            
        Returns:
            処理結果のルートエントリ
        """
        self._manager.debug_info(f"物理フォルダのルートエントリを作成: {path}")
        
        # フォルダ用のルートエントリを作成
        root_info = self._create_folder_entry(path)
        
        # 物理フォルダの内容をキャッシュに追加
        try:
            folder_contents = []
            
            for item in os.listdir(path):
                item_path = os.path.join(path, item).replace('\\', '/')
                rel_path = item  # ルートからの相対パス
                
                if os.path.isdir(item_path):
                    # フォルダエントリの作成と追加
                    entry = EntryInfo(
                        name=item,
                        path=item_path,
                        rel_path=rel_path,
                        type=EntryType.DIRECTORY,
                        size=0,
                        modified_time=None,
                        abs_path=item_path
                    )
                    folder_contents.append(entry)
                    
                    # エントリをキャッシュに追加
                    self._manager._entry_cache.add_entry_to_cache(entry)
                else:
                    # ファイルエントリの作成と追加
                    try:
                        size = os.path.getsize(item_path)
                        mtime = os.path.getmtime(item_path)
                        modified_time = datetime.datetime.fromtimestamp(mtime)
                        
                        # アーカイブかどうか判定
                        file_type = EntryType.FILE
                        _, ext = os.path.splitext(item_path.lower())
                        if ext in self._manager._archive_extensions:
                            file_type = EntryType.ARCHIVE
                        
                        entry = EntryInfo(
                            name=item,
                            path=item_path,
                            rel_path=rel_path,
                            type=file_type,
                            size=size,
                            modified_time=modified_time,
                            abs_path=item_path
                        )
                        folder_contents.append(entry)
                        
                        # エントリをキャッシュに追加
                        self._manager._entry_cache.add_entry_to_cache(entry)
                    except Exception as e:
                        self._manager.debug_error(f"ファイル情報取得エラー: {item_path} - {e}", trace=True)
            
            self._manager.debug_info(f"フォルダ内容を処理: {path} ({len(folder_contents)} アイテム)")
            
        except Exception as e:
            self._manager.debug_error(f"フォルダ内容の取得エラー: {path} - {e}", trace=True)
        
        return root_info
    
    def _process_file_root(self, path: str) -> Optional[EntryInfo]:
        """
        ファイルのルートエントリを処理する
        
        Args:
            path: ファイルのパス
            
        Returns:
            処理結果のルートエントリ
        """
        self._manager.debug_info(f"アーカイブファイルのルートエントリを作成: {path}")
        
        # ファイル用のルートエントリを作成
        root_info = self._create_file_entry(path)
        
        # アーカイブの場合、アーカイブ内のエントリを取得・登録
        if root_info.type == EntryType.ARCHIVE:
            try:
                # ハンドラを取得
                handler = self._manager.get_handler(path)
                if handler:
                    # ハンドラから直接エントリリストを取得
                    direct_children = handler.list_all_entries(path)
                    if direct_children:
                        self._manager.debug_info(f"アーカイブから {len(direct_children)} エントリを取得")
                        
                        # エントリをファイナライズしてアーカイブを識別
                        for entry in direct_children:
                            finalized_entry = self._manager.finalize_entry(entry, path)
                            
                            # エントリをキャッシュに追加
                            self._manager._entry_cache.add_entry_to_cache(finalized_entry)
                    else:
                        self._manager.debug_info(f"アーカイブは空です: {path}")
            except Exception as e:
                self._manager.debug_error(f"アーカイブのエントリ取得中にエラー: {e}", trace=True)
        
        return root_info
