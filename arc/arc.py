"""
アーカイブエントリ情報と型定義

アーカイブ内のファイル/ディレクトリ情報を表すクラス
"""

import os
import sys
import datetime
from enum import Enum, auto
from typing import Dict, Any, Optional

# ArchiveHandler クラスは handler.handler モジュールに移動したため、
# 循環インポートを避けるために import を削除


class EntryType(Enum):
    """エントリタイプを表す列挙型"""
    UNKNOWN = 0
    FILE = 1
    DIRECTORY = 2
    ARCHIVE = 3
    SYMLINK = 4
    
    def is_dir(self) -> bool:
        """ディレクトリタイプかどうかを判定する"""
        return self == EntryType.DIRECTORY
        
    def is_file(self) -> bool:
        """ファイルタイプかどうかを判定する"""
        return self == EntryType.FILE or self == EntryType.ARCHIVE


class EntryInfo:
    """
    アーカイブ内のファイル/ディレクトリの情報を表すクラス
    
    エントリの基本情報（名前、パス、種別、サイズ、更新日時）を保持します。
    """
    
    def __init__(self, 
                 name: str, 
                 path: str = "",
                 type: EntryType = EntryType.UNKNOWN,
                 size: int = 0,
                 modified_time: Optional[datetime.datetime] = None,
                 created_time: Optional[datetime.datetime] = None,
                 is_hidden: bool = False,
                 name_in_arc: str = "",
                 attrs: Dict[str, Any] = None,
                 rel_path: str = "",  # 追加: 親アーカイブからの相対パス
                 cache: Any = None):  # 追加: キャッシュを保持するためのプロパティ
        """
        エントリ情報を初期化する
        
        Args:
            name: エントリの名前
            path: エントリの絶対パス
            type: エントリの種別 (ファイル/ディレクトリ)
            size: ファイルサイズ (バイト単位)
            modified_time: 更新日時
            created_time: 作成日時
            is_hidden: 隠しファイルかどうか
            name_in_arc: アーカイブ内での名前 (エンコーディング対応用)
            attrs: その他の属性を格納する辞書
            rel_path: アーカイブパスからの相対パス
            cache: キャッシュデータ (バイト列やパスなど)
        """
        self.name = name
        self.path = path
        self.type = type
        self.size = size
        self.modified_time = modified_time
        self.created_time = created_time
        self.is_hidden = is_hidden
        self.name_in_arc = name_in_arc if name_in_arc else name
        self.attrs = attrs if attrs is not None else {}
        self.rel_path = rel_path if rel_path else path  # 相対パスが指定されていなければパスを使用
        self.cache = cache  # キャッシュを保持するためのプロパティ

# ArchiveManager クラスの宣言 (循環インポートを避けるため)
class ArchiveManager:
    """アーカイブマネージャーインターフェースクラス (前方宣言)"""
    pass