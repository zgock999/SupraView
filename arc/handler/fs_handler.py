"""
物理ファイルシステムハンドラ

ローカルファイルシステムへのアクセスを提供し、
ArchiveHandlerインタフェースを実装するハンドラ
"""

import os
import stat
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, BinaryIO, Dict

from arc.arc import EntryInfo, EntryType
from .handler import ArchiveHandler  # 重複import修正

class FileSystemHandler(ArchiveHandler):
    """
    物理ファイルシステムへのアクセスを提供するハンドラ
    
    ローカルディスク上のファイルやディレクトリを、
    ArchiveHandlerインタフェースを通じて操作できるようにする
    """
    
    # アーカイブとして認識する拡張子
    KNOWN_ARCHIVE_EXTENSIONS = [
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', 
        '.lha', '.lzh', '.cab', '.iso'
    ]
    
    @property
    def supported_extensions(self) -> List[str]:
        """
        このハンドラがサポートするファイル拡張子のリスト
        物理ファイルシステムハンドラはファイル拡張子を持たない
        
        Returns:
            空のリスト (物理ファイルシステムには拡張子の概念がない)
        """
        return []
    
    def set_archive_extensions(self, extensions: List[str]) -> None:
        """
        アーカイブファイル拡張子のリストを設定する
        
        Args:
            extensions: アーカイブファイル拡張子のリスト
        """
        self.KNOWN_ARCHIVE_EXTENSIONS = extensions
        
    def can_handle(self, path: str) -> bool:
        """
        指定されたパスを処理できるかどうかを判定する
        
        Args:
            path: 判定対象のパス
            
        Returns:
            物理ファイルシステムのパスであればTrue
        """
        # 絶対パスに変換
        abs_path = self._to_absolute_path(path)
        
        try:
            # パスが物理的に存在するかチェック
            return os.path.exists(abs_path)
        except (OSError, ValueError):
            return False
    
    def list_entries(self, path: str) -> List[EntryInfo]:
        """
        指定されたディレクトリ内のファイルとサブディレクトリのリストを取得する
        
        Args:
            path: リストを取得するディレクトリのパス
            
        Returns:
            EntryInfoオブジェクトのリスト
        """
        abs_path = self._to_absolute_path(path)
        entries = []
        
        try:
            # パスが存在するかチェック
            if not os.path.exists(abs_path):
                # 部分一致検索を試みる
                fuzzy_entries = self._fuzzy_match_entries(abs_path)
                if fuzzy_entries:
                    print(f"FileSystemHandler: パスを部分一致で検索しました: {abs_path} -> {len(fuzzy_entries)} エントリ")
                    return fuzzy_entries
                
                # 見つからなければ空のリストを返す
                print(f"FileSystemHandler: パスが見つかりません: {abs_path}")
                return []
            
            # ディレクトリが存在するか確認
            if not os.path.isdir(abs_path):
                # ファイルの場合は、そのファイル自体の情報をリストとして返す
                if os.path.isfile(abs_path):
                    entry = self.get_entry_info(abs_path)
                    if entry:
                        # ZIPファイルの場合は確実にARCHIVEタイプにする
                        if entry.type == EntryType.FILE:
                            _, ext = os.path.splitext(abs_path.lower())
                            if ext in self.KNOWN_ARCHIVE_EXTENSIONS:
                                entry.type = EntryType.ARCHIVE
                                print(f"FileSystemHandler: ファイル {abs_path} をARCHIVEタイプに修正")
                        return [entry]
                    
                return []
            
            # ディレクトリ内のエントリを列挙
            with os.scandir(abs_path) as scanner:
                for entry in scanner:
                    try:
                        # エントリの基本情報を取得
                        name = entry.name
                        full_path = os.path.join(abs_path, name)
                        
                        # ファイルタイプを判定
                        if entry.is_dir():
                            entry_type = EntryType.DIRECTORY
                        else:
                            # 拡張子をチェックしてアーカイブかどうかを判定
                            _, ext = os.path.splitext(name.lower())
                            if ext in self.KNOWN_ARCHIVE_EXTENSIONS:
                                entry_type = EntryType.ARCHIVE
                            else:
                                entry_type = EntryType.FILE
                        
                        # ファイル属性を取得
                        stat_info = entry.stat()
                        
                        # タイムスタンプをDatetime型に変換
                        ctime = datetime.fromtimestamp(stat_info.st_ctime)
                        mtime = datetime.fromtimestamp(stat_info.st_mtime)
                        
                        # 隠しファイルかどうかを判定（プラットフォーム依存）
                        is_hidden = name.startswith('.') if os.name != 'nt' else bool(stat_info.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN) if hasattr(stat_info, 'st_file_attributes') else False
                        
                        # 絶対パスと相対パスの両方を設定したEntryInfoオブジェクトを作成
                        entry_info = self.create_entry_info(
                            name=name,
                            abs_path=full_path,
                            type=entry_type,
                            size=stat_info.st_size,
                            created_time=ctime,
                            modified_time=mtime,
                            is_hidden=is_hidden
                        )
                        entries.append(entry_info)
                    except (OSError, PermissionError) as e:
                        print(f"エントリの読み取りエラー: {entry.path}, {e}")
                        continue
                
            return entries
            
        except (OSError, PermissionError) as e:
            print(f"ディレクトリの読み取りエラー: {abs_path}, {e}")
            return []
    
    def _fuzzy_match_entries(self, path: str) -> List[EntryInfo]:
        """
        パスを部分一致で検索し、一致するエントリを返す
        
        Args:
            path: 部分一致検索するパス
            
        Returns:
            一致したエントリのリスト
        """
        # パス部分とファイル名部分に分割
        dir_path = os.path.dirname(path)
        search_name = os.path.basename(path)
        
        if not search_name:
            return []
        
        # 検索対象のディレクトリを特定
        search_dir = dir_path or os.getcwd()
        search_dir = search_dir.replace('\\', '/')
        
        # 存在確認
        if not os.path.isdir(search_dir):
            return []
        
        # 柔軟な部分一致検索（ワイルドカード対応）
        results = []
        try:
            # 正規表現に変換（*.zip -> .*\.zip$）
            if '*' in search_name or '?' in search_name:
                pattern = search_name.replace('.', '\\.')
                pattern = pattern.replace('*', '.*')
                pattern = pattern.replace('?', '.')
                pattern = f"^{pattern}$"
                regex = re.compile(pattern, re.IGNORECASE)
                
                # ディレクトリ内のファイルをチェック
                for item in os.listdir(search_dir):
                    if regex.match(item):
                        item_path = os.path.join(search_dir, item).replace('\\', '/')
                        
                        if os.path.isfile(item_path):
                            # ファイル情報を取得
                            size = os.path.getsize(item_path)
                            mtime = os.path.getmtime(item_path)
                            modified_time = datetime.fromtimestamp(mtime)
                            
                            # アーカイブファイルかどうかをチェック
                            file_type = EntryType.FILE
                            _, ext = os.path.splitext(item.lower())
                            if ext in self.KNOWN_ARCHIVE_EXTENSIONS:
                                file_type = EntryType.ARCHIVE
                            
                            # create_entry_infoを使用してエントリを作成
                            entry = self.create_entry_info(
                                name=item,
                                abs_path=item_path,
                                type=file_type,
                                size=size,
                                modified_time=modified_time
                            )
                            results.append(entry)
            else:
                # 部分一致検索
                search_name_lower = search_name.lower()
                
                for item in os.listdir(search_dir):
                    if search_name_lower in item.lower():
                        item_path = os.path.join(search_dir, item).replace('\\', '/')
                        
                        if os.path.isfile(item_path):
                            # ファイル情報を取得
                            size = os.path.getsize(item_path)
                            mtime = os.path.getmtime(item_path)
                            modified_time = datetime.fromtimestamp(mtime)
                            
                            # アーカイブファイルかどうかをチェック
                            file_type = EntryType.FILE
                            _, ext = os.path.splitext(item.lower())
                            if ext in self.KNOWN_ARCHIVE_EXTENSIONS:
                                file_type = EntryType.ARCHIVE
                            
                            # create_entry_infoを使用してエントリを作成
                            entry = self.create_entry_info(
                                name=item,
                                abs_path=item_path,
                                type=file_type,
                                size=size,
                                modified_time=modified_time
                            )
                            results.append(entry)
            
        except Exception as e:
            print(f"FileSystemHandler: 部分一致検索エラー: {e}")
            
        return results
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するエントリのパス
            
        Returns:
            エントリ情報。存在しない場合はNone
        """
        abs_path = self._to_absolute_path(path)
        
        try:
            # パスが存在するか確認
            if not os.path.exists(abs_path):
                return None
            
            # 基本情報を取得
            name = os.path.basename(abs_path)
            
            # ファイルタイプを判定
            if os.path.isdir(abs_path):
                entry_type = EntryType.DIRECTORY
            elif os.path.isfile(abs_path):
                # 拡張子をチェックしてアーカイブかどうかを判定
                _, ext = os.path.splitext(name.lower())
                if ext in self.KNOWN_ARCHIVE_EXTENSIONS:
                    entry_type = EntryType.ARCHIVE
                else:
                    entry_type = EntryType.FILE
            else:
                # シンボリックリンクなど
                entry_type = EntryType.UNKNOWN
            
            # ファイル属性を取得
            stat_info = os.stat(abs_path)
            
            # タイムスタンプをDatetime型に変換
            ctime = datetime.fromtimestamp(stat_info.st_ctime)
            mtime = datetime.fromtimestamp(stat_info.st_mtime)
            
            # 隠しファイルかどうかを判定（プラットフォーム依存）
            is_hidden = name.startswith('.') if os.name != 'nt' else bool(stat_info.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN) if hasattr(stat_info, 'st_file_attributes') else False
            
            # 絶対パスと相対パスの両方を設定したEntryInfoオブジェクトを作成
            return self.create_entry_info(
                name=name,
                abs_path=abs_path,
                rel_path=path,
                name_in_arc=path,
                type=entry_type,
                size=stat_info.st_size,
                created_time=ctime,
                modified_time=mtime,
                is_hidden=is_hidden
            )
            
        except (OSError, PermissionError) as e:
            print(f"エントリ情報取得エラー: {abs_path}, {e}")
            return None
    
    def read_archive_file(self, archive_path: str, file_path: str) -> Optional[bytes]:
        """
        ファイルシステム上のファイルを読み込む
        
        Args:
            archive_path: ファイルまたはディレクトリのパス
            file_path: サブパス (空の場合はarchive_path自体を読み込む)
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        try:
            # 両方のパスを正規化
            norm_archive_path = self.normalize_path(archive_path)
            norm_file_path = self.normalize_path(file_path) if file_path else ""
            
            if norm_file_path:
                # サブパスが指定されている場合は結合
                full_path = os.path.join(norm_archive_path, norm_file_path).replace('\\', '/')
                print(f"FileSystemHandler: 結合パスからファイル読み込み: {full_path}")
            else:
                # サブパスが空の場合はarchive_path自体を読み込む
                full_path = norm_archive_path
                print(f"FileSystemHandler: 単一パスからファイル読み込み: {full_path}")
            
            # 絶対パスに変換
            abs_path = self._to_absolute_path(full_path)
            
            # ファイルが存在し、通常のファイルであるか確認
            if not os.path.isfile(abs_path):
                print(f"FileSystemHandler: パス {abs_path} はファイルではありません")
                return None
            
            # ファイルを読み込む
            with open(abs_path, 'rb') as f:
                content = f.read()
                print(f"FileSystemHandler: {len(content):,} バイトを読み込みました")
                return content
                
        except (OSError, PermissionError) as e:
            print(f"FileSystemHandler: ファイル読み込みエラー: {e}")
            return None
    
    def get_stream(self, path: str) -> Optional[BinaryIO]:
        """
        指定されたファイルのストリームを取得する
        
        Args:
            path: ストリームを取得するファイルのパス
            
        Returns:
            ファイルストリーム。取得できない場合はNone
        """
        abs_path = self._to_absolute_path(path)
        
        try:
            # ファイルが存在し、通常のファイルであるか確認
            if not os.path.isfile(abs_path):
                return None
            
            # ファイルストリームを開く
            # 注: 呼び出し元はこのストリームをcloseする責任がある
            return open(abs_path, 'rb')
                
        except (OSError, PermissionError) as e:
            print(f"ファイルストリーム取得エラー: {abs_path}, {e}")
            return None

    def get_parent_path(self, path: str) -> str:
        """
        指定したパスの親ディレクトリのパスを取得する
        
        Args:
            path: 親ディレクトリを取得するパス
            
        Returns:
            親ディレクトリのパス。親がない場合は空文字列
        """
        abs_path = self._to_absolute_path(path)
        
        # ルートディレクトリの場合は空文字列を返す
        if not abs_path or abs_path == '/':
            return ''
        
        # 親ディレクトリを取得
        parent_dir = os.path.dirname(abs_path)
        
        return parent_dir

    def is_directory(self, path: str) -> bool:
        """
        指定したパスがディレクトリかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            ディレクトリの場合はTrue、そうでない場合はFalse
        """
        abs_path = self._to_absolute_path(path)
        
        try:
            # パスがディレクトリかどうかを確認
            return os.path.isdir(abs_path)
        except:
            return False

    def list_all_entries(self, path: str) -> List[EntryInfo]:
        """
        指定したディレクトリ内のすべてのエントリを再帰的に取得する（フィルタリングなし）
        
        Args:
            path: ディレクトリのパス
            
        Returns:
            ディレクトリ内のすべてのエントリのリスト
        """
        # 空の場合やパスが指定されていない場合は、現在のパスをデフォルトとして使用
        if not path:
            if self.current_path:
                abs_path = self.current_path
            else:
                abs_path = os.getcwd()
        else:
            abs_path = self._to_absolute_path(path)
        
        print(f"FileSystemHandler: list_all_entries 開始 - パス: {abs_path}")
        
        # ディレクトリが存在するか確認
        if not os.path.isdir(abs_path):
            print(f"FileSystemHandler: ディレクトリが存在しません: {abs_path}")
            return []
        
        # すべてのエントリを格納するリスト
        all_entries = []
        
        try:
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
                print(f"FileSystemHandler: ルートディレクトリエントリを追加: {root_name} ({abs_path})")
            
            # ディレクトリを再帰的に走査
            for root, dirs, files in os.walk(abs_path):
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
                        all_entries.append(entry)
                        
                    except Exception as e:
                        print(f"FileSystemHandler: ディレクトリ情報取得エラー: {dir_path} - {e}")
                        # 最小限の情報でエントリを作成して追加
                        rel_path = self.to_relative_path(dir_path)
                        all_entries.append(self.create_entry_info(
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
                                               
                        # create_entry_infoを使用してファイルエントリを作成
                        rel_path = self.to_relative_path(file_path)
                        entry = self.create_entry_info(
                            name=file_name,
                            rel_path=rel_path,
                            name_in_arc=rel_path,
                            type=EntryType.FILE,
                            size=size,
                            modified_time=mtime,
                            created_time=ctime,
                            is_hidden=is_hidden
                        )
                        all_entries.append(entry)
                        
                    except Exception as e:
                        print(f"FileSystemHandler: ファイル情報取得エラー ({file_path}): {e}")
                        # エラーが発生しても最低限の情報でエントリを追加
                        rel_path = self.to_relative_path(file_path)
                        all_entries.append(self.create_entry_info(
                            name=file_name,
                            rel_path=rel_path,
                            name_in_arc=rel_path,
                            type=EntryType.FILE,
                            size=0
                        ))
            
            print(f"FileSystemHandler: {len(all_entries)} エントリを取得しました")
            return all_entries
            
        except Exception as e:
            print(f"FileSystemHandler: エントリ一覧取得中にエラー: {e}")
            import traceback
            traceback.print_exc()
            return all_entries if all_entries else []

    def list_all_entries_from_bytes(self, archive_data: bytes, path: str = "") -> List[EntryInfo]:
        """
        メモリ上のデータからすべてのエントリを再帰的に取得する（未サポート）
        
        ファイルシステムハンドラではメモリからのエントリ取得はサポートしていません。
        
        Args:
            archive_data: バイトデータ（未使用）
            path: パス（未使用）
            
        Returns:
            常に空リスト
        """
        print(f"FileSystemHandler: メモリデータからのエントリ取得はサポートしていません")
        return []

    def use_absolute(self) -> bool:
        """
        絶対パスを使用するかどうかを返す
        ファイルシステムハンドラは絶対パスを使用する
        
        Returns:
            True (常に絶対パスを使用)
        """
        return True

    def _to_absolute_path(self, path: str) -> str:
        """
        相対パスを絶対パスに変換する
        
        Args:
            path: 変換する相対または絶対パス
            
        Returns:
            絶対パス
        """
        # パスを正規化
        norm_path = self.normalize_path(path)
        
        # 空のパスが渡された場合は、現在のパスをそのまま返す
        if not norm_path:
            if self.current_path:
                return self.current_path
            else:
                return os.getcwd()
        
        # 既に絶対パスならそのまま返す
        if os.path.isabs(norm_path):
            return norm_path
            
        # カレントパスが設定されていない場合はカレントディレクトリを基準にする
        if not self.current_path:
            return os.path.abspath(norm_path)
            
        # カレントパスを基準に絶対パスに変換
        abs_path = os.path.join(self.current_path, norm_path).replace('\\', '/')
        return abs_path

    def can_archive(self) -> bool:
        """
        このハンドラがアーカイバとして機能するかどうかを返す
        
        FileSystemHandlerはアーカイバとして機能しない（圧縮/解凍機能を持たない）
        
        Returns:
            常にFalse（アーカイバではない）
        """
        return False  # ファイルシステムハンドラはアーカイバではない


    def _calc_relative_path(self, path: str) -> str:
        """
        current_pathに対する相対パスを計算する
        
        Args:
            path: 計算する絶対パス
            
        Returns:
            相対パス。current_pathが設定されていない場合やパスが含まれない場合は
            元のパスをそのまま返す
        """
        if not self.current_path:
            return path
            
        norm_current = self.current_path.rstrip('/').replace('\\', '/')
        norm_path = path.replace('\\', '/')
        
        # カレントパスの配下かどうか確認
        if norm_path.startswith(norm_current):
            # カレントパスからの相対パスを返す
            if len(norm_path) > len(norm_current):
                if norm_path[len(norm_current)] == '/':
                    # スラッシュがある場合は、その後の部分を返す
                    return norm_path[len(norm_current) + 1:]
            
            # カレントパスと完全一致する場合は空文字を返す
            if norm_path == norm_current:
                return ""
                
        # カレントパスの配下でない場合は、絶対パスをそのまま返す
        return norm_path
