"""
アーカイブハンドラ基底クラス

アーカイブハンドラの抽象基底クラスを定義
"""
import os
import tempfile
from typing import List, Optional, BinaryIO, Dict, Any

from ..arc import EntryInfo, EntryType
# loggingモジュールからlogutilsへの参照変更
from logutils import log_print, log_trace, DEBUG, INFO, WARNING, ERROR, CRITICAL


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
    
    def debug_print(self, message: Any, *args, level: int = INFO, trace: bool = False, **kwargs):
        """
        デバッグ出力のラッパーメソッド
        
        Args:
            message: 出力するメッセージ
            *args: メッセージのフォーマット用引数
            level: ログレベル（デフォルトはINFO）
            trace: Trueならスタックトレース情報も出力する（デフォルトはFalse）
            **kwargs: 追加のキーワード引数
        """
        # クラス名をログの名前空間として使用
        name = f"arc.handler.{self.__class__.__name__}"
        
        if trace:
            log_trace(None, level, message, *args, name=name, **kwargs)
        else:
            log_print(level, message, *args, name=name, **kwargs)
    
    def debug_debug(self, message: Any, *args, trace: bool = False, **kwargs):
        """DEBUGレベルのログ出力"""
        self.debug_print(message, *args, level=DEBUG, trace=trace, **kwargs)
    
    def debug_info(self, message: Any, *args, trace: bool = False, **kwargs):
        """INFOレベルのログ出力"""
        self.debug_print(message, *args, level=INFO, trace=trace, **kwargs)
    
    def debug_warning(self, message: Any, *args, trace: bool = False, **kwargs):
        """WARNINGレベルのログ出力"""
        self.debug_print(message, *args, level=WARNING, trace=trace, **kwargs)
    
    def debug_error(self, message: Any, *args, trace: bool = False, **kwargs):
        """ERRORレベルのログ出力"""
        self.debug_print(message, *args, level=ERROR, trace=trace, **kwargs)
        
    def debug_critical(self, message: Any, *args, trace: bool = False, **kwargs):
        """CRITICALレベルのログ出力"""
        self.debug_print(message, *args, level=CRITICAL, trace=trace, **kwargs)

    def set_current_path(self, path: str) -> None:
        """
        現在のベースパスを設定する
        
        Args:
            path: 設定するベースパス
        """
        self.current_path = path.replace('\\', '/')
        
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
            path: リストを取得する書庫のパス
            
        Returns:
            エントリ情報のリスト。失敗した場合は空リスト
        """
        # デフォルト実装では、list_entriesを再帰的に呼び出す
        # サブクラスで効率的な実装に置き換えることを推奨
        result = []
        entries = self.list_entries("")
        
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
            self.debug_error(f"一時ファイル作成エラー: {e}")
            return ""
    
    def cleanup_temp_file(self, filepath: str) -> None:
        """
        一時ファイルを削除する
        
        Args:
            filepath: 削除する一時ファイルのパス
        """
        if filepath and os.path.exists(filepath):
            try:
                os.unlink(filepath)
            except Exception as e:
                if self.debug:
                    self.debug_error(f"一時ファイルの削除に失敗しました: {e}")

    @staticmethod
    def normalize_path(path: str) -> str:
        """
        パスを正規化する
        
        Args:
            path: 正規化するパス
            
        Returns:
            正規化されたパス
        """
        # パスの区切り文字を統一
        normalized = path.replace('\\', '/')
        
        # 連続するスラッシュを1つに
        while '//' in normalized:
            normalized = normalized.replace('//', '/')
        
        # 末尾のスラッシュを除去
        if normalized.endswith('/') and len(normalized) > 1:
            normalized = normalized[:-1]
            
        return normalized

    def to_relative_path(self, abs_path: str) -> str:
        """
        絶対パスを現在のベースパスからの相対パスに変換する
        
        Args:
            abs_path: 変換する絶対パス
            
        Returns:
            相対パス（カレントパスからの相対）
        """
        if not abs_path:
            return ""
        
        # パスを正規化
        norm_path = self.normalize_path(abs_path)
        
        # カレントパスが設定されていない場合はそのまま返す
        if not self.current_path:
            return norm_path
        
        # カレントパスを正規化
        norm_current = self.normalize_path(self.current_path)
        
        # カレントパスでの接頭辞チェック
        if norm_path.startswith(norm_current):
            # カレントパスを除去（先頭のスラッシュも含む）
            rel_path = norm_path[len(norm_current):]
            # スラッシュで始まる場合は削除
            if rel_path.startswith('/'):
                rel_path = rel_path[1:]
            return rel_path
        
        # カレントパスの接頭辞がなければそのまま返す
        return norm_path
    
    def create_entry_info(self, name: str, rel_path: str, type: EntryType, name_in_arc: str, **kwargs) -> EntryInfo:
        """
        必須情報だけは保証したEntryInfoオブジェクトを作成する
        
        Args:
            name: エントリの名前
            rel_path: エントリへの書庫からのパス（マネージャ層で完成させるためのもの）
            type: エントリのタイプ
            name_in_arc: アーカイブ内のエントリ名(エンコードされていない生の名前)
            **kwargs: その他のEntryInfo引数
            
        Returns:
            相対パスが設定されたEntryInfoオブジェクト
        """
        
        # EntryInfoオブジェクトを作成して返す
        return EntryInfo(
            name=name,
            type=type,
            rel_path=rel_path,
            name_in_arc=name_in_arc,
            **kwargs
        )
