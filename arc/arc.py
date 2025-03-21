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


class EntryStatus(Enum):
    """エントリのステータスを表す列挙型"""
    READY = auto()     # エントリは使用可能
    BROKEN = auto()    # 物理エラーもしくは論理エラーで使用不可
    SCANNING = auto()  # 書庫もしくはディレクトリのエントリを非同期で構築中なのでまだ使用不可


class EntryInfo:
    """
    アーカイブ内のファイル/ディレクトリの情報を表すクラス
    
    エントリの基本情報（名前、パス、種別、サイズ、更新日時）を保持します。
    """
    
    def __init__(self, 
                 name: str,
                 path: str = "",  # path を非必須に変更
                 rel_path: Optional[str] = None, 
                 type: EntryType = EntryType.FILE,
                 size: int = 0, 
                 modified_time: Optional[datetime.datetime] = None,
                 created_time: Optional[datetime.datetime] = None,
                 is_hidden: bool = False,
                 name_in_arc: Optional[str] = None,  # デフォルト値を None に変更
                 attrs: Optional[Dict[str, Any]] = None,
                 abs_path: str = "",
                 status: EntryStatus = EntryStatus.READY
                 ):
        """
        エントリ情報を初期化する
        
        Args:
            name: エントリ名（ファイル名またはディレクトリ名）
            path: エントリのパス（省略可能）
            rel_path: 基準ディレクトリからの相対パス
            type: エントリのタイプ（FILE, DIRECTORY, ARCHIVE）
            size: サイズ（バイト）
            modified_time: 更新日時
            created_time: 作成日時
            is_hidden: 隠しファイル/ディレクトリかどうか
            name_in_arc: アーカイブ内での名前（Noneの場合はnameが使用される）
            attrs: その他の属性（辞書型）
            abs_path: 絶対パス（指定がなければpathが使用される）
            status: エントリの状態（READY, BROKEN, SCANNING）
        """
        self.name = name
        self.path = path
        # rel_pathをそのまま使用（pathで置き換える処理を撤廃）
        self.rel_path = rel_path
        self.type = type
        self.size = size
        self.modified_time = modified_time
        self.created_time = created_time
        self.is_hidden = is_hidden
        self.name_in_arc = name if name_in_arc is None else name_in_arc  # None の場合のみ name を使用
        self.attrs = attrs or {}
        self.abs_path = abs_path if abs_path else path
        self.status = status

# ArchiveManager クラスの宣言 (循環インポートを避けるため)
class ArchiveManager:
    """アーカイブマネージャーインターフェースクラス (前方宣言)"""
    pass

# 前方宣言の移動
# manager.manager モジュールに実際の実装があることを示すコメントを追加
# 実際の実装は manager/manager.py に移動