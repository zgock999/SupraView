"""
アーカイブハンドラ基底クラス

アーカイブハンドラの抽象基底クラスを定義
"""

import os
import tempfile
from typing import List, Optional, BinaryIO, Dict, Any

from ..arc import EntryInfo, EntryType


class ArchiveHandler:
    """
    アーカイブハンドラの抽象基底クラス
    
    すべてのハンドラはこのクラスを継承する必要があります。
    アーカイブの種類に応じて、適切なメソッドをオーバーライドしてください。
    """
    
    # このハンドラがサポートするファイル拡張子のリスト
    supported_extensions = []
    
    def __init__(self):
        """ハンドラを初期化する"""
        self.current_path = ""
    
    def set_current_path(self, path: str) -> None:
        """
        現在のベースパスを設定する
        
        Args:
            path: 設定するベースパス
        """
        self.current_path = path.replace('\\', '/')
    
    def use_absolute(self) -> bool:
        """
        絶対パスを使用するかどうかを返す
        
        Returns:
            絶対パスを使用する場合はTrue、相対パスを使用する場合はFalse
        """
        return False
    
    def can_handle(self, path: str) -> bool:
        """
        指定されたパスがこのハンドラで処理可能かどうか
        
        Args:
            path: 処理するファイルのパス
            
        Returns:
            処理可能な場合はTrue、処理できない場合はFalse
        """
        # サブクラスで実装
        return False
    
    def can_archive(self) -> bool:
        """
        このハンドラがアーカイブファイルを処理できるかどうか
        
        Returns:
            アーカイブハンドラの場合はTrue、それ以外の場合はFalse
        """
        return len(self.supported_extensions) > 0
    
    def can_handle_bytes(self, data: bytes, name: str = "") -> bool:
        """
        指定されたバイトデータをこのハンドラで処理可能かどうか
        
        Args:
            data: 処理するデータ
            name: データの名前またはパス（オプション）
            
        Returns:
            処理可能な場合はTrue、処理できない場合はFalse
        """
        # デフォルトではメモリ内処理をサポートしない
        return False
    
    def list_entries(self, path: str) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるエントリのリストを取得する
        
        Args:
            path: リストを取得するディレクトリのパス
            
        Returns:
            エントリ情報のリスト。失敗した場合は空リスト
        """
        # サブクラスで実装
        return []
    
    def list_all_entries(self, path: str) -> List[EntryInfo]:
        """
        指定されたパスの配下にある全エントリを再帰的に取得する
        
        Args:
            path: リストを取得するディレクトリのパス
            
        Returns:
            エントリ情報のリスト。失敗した場合は空リスト
        """
        # デフォルト実装では、list_entriesを再帰的に呼び出す
        # サブクラスで効率的な実装に置き換えることを推奨
        result = []
        entries = self.list_entries(path)
        
        if not entries:
            return []
            
        result.extend(entries)
        
        # ディレクトリエントリの場合は再帰的に処理
        for entry in entries:
            if entry.type and entry.type.is_dir():
                subentries = self.list_all_entries(entry.path)
                if subentries:
                    result.extend(subentries)
                    
        return result
    
    def list_entries_from_bytes(self, data: bytes) -> List[EntryInfo]:
        """
        指定されたバイトデータからエントリのリストを取得する
        
        Args:
            data: 処理するデータ
            
        Returns:
            エントリ情報のリスト。失敗した場合は空リスト
        """
        # デフォルトではメモリ内処理をサポートしない
        return []
    
    def list_all_entries_from_bytes(self, data: bytes) -> List[EntryInfo]:
        """
        指定されたバイトデータから全エントリを再帰的に取得する
        
        Args:
            data: 処理するデータ
            
        Returns:
            エントリ情報のリスト。失敗した場合は空リスト
        """
        # デフォルトではlist_entries_from_bytesを使用
        # サブクラスで効率的な実装に置き換えることを推奨
        return self.list_entries_from_bytes(data)
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するエントリのパス
            
        Returns:
            エントリ情報。存在しない場合はNone
        """
        # サブクラスで実装
        return None
    
    def read_file(self, path: str) -> Optional[bytes]:
        """
        指定されたパスのファイルの内容を読み込む
        
        Args:
            path: 読み込むファイルのパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        # サブクラスで実装
        return None
    
    def read_file_from_bytes(self, data: bytes, internal_path: str) -> Optional[bytes]:
        """
        指定されたバイトデータからファイルの内容を読み込む
        
        Args:
            data: 処理するアーカイブデータ
            internal_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        # デフォルトではメモリ内処理をサポートしない
        return None
    
    def read_archive_file(self, archive_path: str, file_path: str) -> Optional[bytes]:
        """
        アーカイブファイル内のファイルの内容を読み込む
        
        Args:
            archive_path: アーカイブファイルのパス
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        # サブクラスで実装
        return None
    
    def get_stream(self, path: str) -> Optional[BinaryIO]:
        """
        指定されたパスのファイルのストリームを取得する
        
        Args:
            path: ストリームを取得するファイルのパス
            
        Returns:
            ファイルストリーム。取得できない場合はNone
        """
        # サブクラスで実装
        return None
    
    def is_directory(self, path: str) -> bool:
        """
        指定されたパスがディレクトリかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            ディレクトリの場合はTrue、それ以外の場合はFalse
        """
        # デフォルト実装、サブクラスでオーバーライド可能
        entry = self.get_entry_info(path)
        return entry is not None and entry.type and entry.type.is_dir()
    
    def get_parent_path(self, path: str) -> str:
        """
        親ディレクトリのパスを取得する
        
        Args:
            path: 対象のパス
            
        Returns:
            親ディレクトリのパス
        """
        # デフォルト実装
        norm_path = path.replace('\\', '/')
        last_slash = norm_path.rfind('/')
        if (last_slash >= 0):
            return norm_path[:last_slash]
        return ""
    
    def save_to_temp_file(self, data: bytes, ext: str = "") -> str:
        """
        バイトデータを一時ファイルに保存する
        
        Args:
            data: 保存するデータ
            ext: ファイル拡張子（ドットを含む）
            
        Returns:
            一時ファイルのパス。失敗した場合は空文字列
        """
        try:
            # 一時ファイルのプレフィックスとサフィックスを決定
            prefix = "arc_temp_"
            suffix = ext
            
            # 一時ファイル作成
            fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            
            # ファイルにデータを書き込み、クローズする
            with os.fdopen(fd, 'wb') as temp_file:
                temp_file.write(data)
            
            return temp_path.replace('\\', '/')
        except Exception as e:
            print(f"一時ファイル作成エラー: {e}")
            return ""
    
    def normalize_path(self, path: str) -> str:
        """
        OSに依存しないパス正規化関数
        
        Args:
            path: 正規化する元のパス文字列
            
        Returns:
            正規化されたパス文字列
        """
        if path is None:
            return ""
            
        # バックスラッシュをスラッシュに変換
        normalized = path.replace('\\', '/')
        
        # 連続するスラッシュを1つに
        while '//' in normalized:
            normalized = normalized.replace('//', '/')
        
        # WindowsドライブレターのUNIX形式表現を修正（例: /C:/path → C:/path）
        if len(normalized) > 2 and normalized[0] == '/' and normalized[2] == ':':
            normalized = normalized[1:]  # 先頭のスラッシュを削除
            
        return normalized
        
    def create_entry_info(self, name: str, abs_path: str, 
                         size: int = 0, modified_time = None, 
                         type: EntryType = EntryType.FILE,
                         name_in_arc: str = None) -> EntryInfo:
        """
        EntryInfoオブジェクトを作成するヘルパーメソッド
        
        Args:
            name: エントリの名前
            abs_path: エントリの絶対パス
            size: ファイルサイズ
            modified_time: 更新日時
            type: エントリタイプ
            name_in_arc: アーカイブ内の元の名前（エンコーディング問題対応用）
            
        Returns:
            作成されたEntryInfo
        """
        # 絶対パスと相対パスの処理
        abs_path = self.normalize_path(abs_path)
        
        # 相対パスを計算（カレントパスからの相対）
        rel_path = abs_path
        if self.current_path:
            current = self.normalize_path(self.current_path)
            # カレントパスがabsパスの先頭にある場合
            if abs_path.startswith(current + '/'):
                rel_path = abs_path[len(current) + 1:]  # +1 で '/' も除去
            elif abs_path == current:
                rel_path = ""
        
        # name_in_arcがない場合は名前を使用
        if name_in_arc is None:
            name_in_arc = name
            
        # EntryInfoを作成して返す
        return EntryInfo(
            name=name,
            path=abs_path,
            type=type,
            size=size,
            modified_time=modified_time,
            name_in_arc=name_in_arc,
            rel_path=rel_path
        )