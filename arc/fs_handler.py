"""
物理ファイルシステムハンドラ

ローカルファイルシステムへのアクセスを提供し、
ArchiveHandlerインタフェースを実装するハンドラ
"""

import os
import stat
from datetime import datetime
from pathlib import Path
from typing import List, Optional, BinaryIO, Dict

from .arc import ArchiveHandler, EntryInfo, EntryType


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
    
    def can_handle(self, path: str) -> bool:
        """
        指定されたパスを処理できるかどうかを判定する
        
        Args:
            path: 判定対象のパス
            
        Returns:
            物理ファイルシステムのパスであればTrue
        """
        # 正規化したパスを使用
        norm_path = self.normalize_path(path)
        
        try:
            # パスが物理的に存在するかチェック
            return os.path.exists(norm_path)
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
        norm_path = self.normalize_path(path)
        entries = []
        
        try:
            # ディレクトリが存在するか確認
            if not os.path.exists(norm_path) or not os.path.isdir(norm_path):
                return []
            
            # ディレクトリ内のエントリを列挙
            with os.scandir(norm_path) as scanner:
                for entry in scanner:
                    try:
                        # エントリの基本情報を取得
                        name = entry.name
                        full_path = os.path.join(norm_path, name)
                        
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
                        
                        # EntryInfoオブジェクトを作成
                        entry_info = EntryInfo(
                            name=name,
                            path=full_path,
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
            print(f"ディレクトリの読み取りエラー: {norm_path}, {e}")
            return []
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するエントリのパス
            
        Returns:
            エントリ情報。存在しない場合はNone
        """
        norm_path = self.normalize_path(path)
        
        try:
            # パスが存在するか確認
            if not os.path.exists(norm_path):
                return None
            
            # 基本情報を取得
            name = os.path.basename(norm_path)
            
            # ファイルタイプを判定
            if os.path.isdir(norm_path):
                entry_type = EntryType.DIRECTORY
            elif os.path.isfile(norm_path):
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
            stat_info = os.stat(norm_path)
            
            # タイムスタンプをDatetime型に変換
            ctime = datetime.fromtimestamp(stat_info.st_ctime)
            mtime = datetime.fromtimestamp(stat_info.st_mtime)
            
            # 隠しファイルかどうかを判定（プラットフォーム依存）
            is_hidden = name.startswith('.') if os.name != 'nt' else bool(stat_info.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN) if hasattr(stat_info, 'st_file_attributes') else False
            
            # EntryInfoオブジェクトを作成
            return EntryInfo(
                name=name,
                path=norm_path,
                type=entry_type,
                size=stat_info.st_size,
                created_time=ctime,
                modified_time=mtime,
                is_hidden=is_hidden
            )
            
        except (OSError, PermissionError) as e:
            print(f"エントリ情報取得エラー: {norm_path}, {e}")
            return None
    
    def read_file(self, path: str) -> Optional[bytes]:
        """
        指定されたファイルの内容を読み込む
        
        Args:
            path: 読み込むファイルのパス
            
        Returns:
            ファイルの内容（バイト配列）。読み込みに失敗した場合はNone
        """
        norm_path = self.normalize_path(path)
        
        try:
            # ファイルが存在し、通常のファイルであるか確認
            if not os.path.isfile(norm_path):
                return None
            
            # ファイルを読み込む
            with open(norm_path, 'rb') as f:
                return f.read()
                
        except (OSError, PermissionError) as e:
            print(f"ファイル読み込みエラー: {norm_path}, {e}")
            return None
    
    def get_stream(self, path: str) -> Optional[BinaryIO]:
        """
        指定されたファイルのストリームを取得する
        
        Args:
            path: ストリームを取得するファイルのパス
            
        Returns:
            ファイルストリーム。取得できない場合はNone
        """
        norm_path = self.normalize_path(path)
        
        try:
            # ファイルが存在し、通常のファイルであるか確認
            if not os.path.isfile(norm_path):
                return None
            
            # ファイルストリームを開く
            # 注: 呼び出し元はこのストリームをcloseする責任がある
            return open(norm_path, 'rb')
                
        except (OSError, PermissionError) as e:
            print(f"ファイルストリーム取得エラー: {norm_path}, {e}")
            return None
    
    def read_archive_file(self, archive_path: str, file_path: str) -> Optional[bytes]:
        """
        アーカイブファイル内のファイルの内容を読み込む
        
        このハンドラではアーカイブファイル内のファイル読み込みはサポートしていないため常にNoneを返す
        
        Args:
            archive_path: アーカイブファイルのパス
            file_path: アーカイブ内のファイルパス
            
        Returns:
            常にNone
        """
        # ファイルシステムハンドラではアーカイブ内のファイル読み込みはサポートしていない
        print(f"FileSystemHandler: アーカイブ読み込みはサポートされていません ({archive_path}/{file_path})")
        return None

    def get_parent_path(self, path: str) -> str:
        """
        指定したパスの親ディレクトリのパスを取得する
        
        Args:
            path: 親ディレクトリを取得するパス
            
        Returns:
            親ディレクトリのパス。親がない場合は空文字列
        """
        norm_path = self.normalize_path(path)
        
        # ルートディレクトリの場合は空文字列を返す
        if not norm_path or norm_path == '/':
            return ''
        
        # 親ディレクトリを取得
        parent_dir = os.path.dirname(norm_path)
        
        return parent_dir

    def is_directory(self, path: str) -> bool:
        """
        指定したパスがディレクトリかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            ディレクトリの場合はTrue、そうでない場合はFalse
        """
        norm_path = self.normalize_path(path)
        
        try:
            # パスがディレクトリかどうかを確認
            return os.path.isdir(norm_path)
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
        # ディレクトリが存在するか確認
        if not os.path.isdir(path):
            print(f"FileSystemHandler: ディレクトリが存在しません: {path}")
            return []
        
        # すべてのエントリを格納するリスト
        all_entries = []
        
        try:
            # ディレクトリを再帰的に走査
            for root, dirs, files in os.walk(path):
                # ディレクトリエントリを追加
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name).replace('\\', '/')
                    rel_path = os.path.relpath(dir_path, path).replace('\\', '/')
                    
                    # ディレクトリの統計情報を取得
                    try:
                        stat = os.stat(dir_path)
                        mtime = datetime.fromtimestamp(stat.st_mtime)
                        ctime = datetime.fromtimestamp(stat.st_ctime)
                    except:
                        mtime = None
                        ctime = None
                    
                    # 隠しディレクトリかどうか判定
                    is_hidden = dir_name.startswith('.') or bool(os.stat(dir_path).st_file_attributes & 0x2) if hasattr(os.stat(dir_path), 'st_file_attributes') else dir_name.startswith('.')
                    
                    # ディレクトリエントリを作成
                    entry = EntryInfo(
                        name=dir_name,
                        path=dir_path,
                        type=EntryType.DIRECTORY,
                        size=0,
                        modified_time=mtime,
                        created_time=ctime,
                        is_hidden=is_hidden
                    )
                    
                    all_entries.append(entry)
                
                # ファイルエントリを追加
                for file_name in files:
                    file_path = os.path.join(root, file_name).replace('\\', '/')
                    rel_path = os.path.relpath(file_path, path).replace('\\', '/')
                    
                    try:
                        # ファイル情報を取得
                        stat = os.stat(file_path)
                        size = stat.st_size
                        mtime = datetime.fromtimestamp(stat.st_mtime)
                        ctime = datetime.fromtimestamp(stat.st_ctime)
                        
                        # 隠しファイルかどうか判定
                        is_hidden = file_name.startswith('.') or bool(stat.st_file_attributes & 0x2) if hasattr(stat, 'st_file_attributes') else file_name.startswith('.')
                        
                        # アーカイブファイルかどうか判定
                        _, ext = os.path.splitext(file_name.lower())
                        if ext in self.KNOWN_ARCHIVE_EXTENSIONS:
                            entry_type = EntryType.ARCHIVE
                        else:
                            entry_type = EntryType.FILE
                        
                        # ファイルエントリを作成
                        entry = EntryInfo(
                            name=file_name,
                            path=file_path,
                            type=entry_type,
                            size=size,
                            modified_time=mtime,
                            created_time=ctime,
                            is_hidden=is_hidden
                        )
                        
                        all_entries.append(entry)
                        
                    except Exception as e:
                        print(f"FileSystemHandler: ファイル情報取得エラー ({file_path}): {e}")
                        # エラーが発生しても最低限の情報でエントリを追加
                        all_entries.append(EntryInfo(
                            name=file_name,
                            path=file_path,
                            type=EntryType.FILE,
                            size=0
                        ))
            
            print(f"FileSystemHandler: {len(all_entries)} エントリを取得しました")
            return all_entries
            
        except Exception as e:
            print(f"FileSystemHandler: エントリ一覧取得中にエラー: {e}")
            import traceback
            traceback.print_exc()
            return []

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
