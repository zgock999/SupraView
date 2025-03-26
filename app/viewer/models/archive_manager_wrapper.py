"""
アーカイブマネージャーラッパー

EnhancedArchiveManagerをラップして、アプリケーション固有の機能を追加する
"""

import os
import sys
import time
import traceback
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# 親パッケージからインポートできるようにパスを調整
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# ロギングユーティリティをインポート
from logutils import log_print, log_trace, DEBUG, INFO, WARNING, ERROR, CRITICAL

try:
    # CLIツールと同様のインポート
    from arc.manager.enhanced import EnhancedArchiveManager
    from arc.interface import get_archive_manager
    from arc.arc import EntryInfo, EntryType
    from arc.path_utils import normalize_path
except ImportError as e:
    log_print(ERROR, f"エラー: バックエンドライブラリのインポートに失敗しました: {e}")
    sys.exit(1)

from ..debug_utils import ViewerDebugMixin

# アーカイブブラウザのインポート
from arc.browser.factory import get_browser
from arc.browser.browser import ArchiveBrowser


class ArchiveManagerWrapper(ViewerDebugMixin):
    """
    アーカイブマネージャーのラッパークラス
    
    ビューアアプリケーション用にアーカイブマネージャーの機能を提供する
    """
    
    def __init__(self):
        """初期化"""
        # ViewerDebugMixinの初期化
        self._init_debug_mixin("ArchiveManagerWrapper")
        
        # CLIツールと同様に、interfaceモジュールからマネージャーを取得
        self.debug_info("アーカイブマネージャーの初期化")
        self._manager = get_archive_manager()
        self._current_path = ""  # ベースパス（最初に開いたパス）
        self._current_directory = ""  # カレントディレクトリ（ベースパスからの相対パス）
        self._debug_mode = False
        
        # エントリキャッシュ
        self._cached_entries = {}
        self.debug_info("アーカイブマネージャーの初期化完了")
        self._browser = None  # ブラウザインスタンスを保持する変数
    
    @property
    def current_path(self) -> str:
        """現在開いているベースパス"""
        return self._current_path
    
    @property
    def current_directory(self) -> str:
        """カレントディレクトリ（ベースパスからの相対パス）"""
        return self._current_directory
    
    @property
    def debug_mode(self) -> bool:
        """デバッグモード"""
        return self._debug_mode
    
    @debug_mode.setter
    def debug_mode(self, value: bool):
        """デバッグモードを設定"""
        self._debug_mode = value
    
    def open(self, path: str) -> bool:
        """
        指定されたパスを開く
        
        Args:
            path: 開くパス（フォルダまたはアーカイブファイル）
            
        Returns:
            bool: 成功したかどうか
        """
        if not os.path.exists(path):
            self.debug_error(f"指定されたパスが存在しません: {path}")
            return False
        
        # パスを正規化
        path = normalize_path(path)
        self.debug_info(f"パスを開きます: {path}")
        
        try:
            # CLIツールと同様に、EnhancedArchiveManagerならset_current_pathを使用
            if isinstance(self._manager, EnhancedArchiveManager):
                # エラー検出を抑制し、成功かどうかだけを確認
                try:
                    self._manager.set_current_path(path)
                except Exception as e:
                    # エラーは記録するが、処理は続行（フォルダアクセスなど基本操作のため）
                    self.debug_warning(f"パス設定エラー（無視して続行）: {e}")
            
            # キャッシュを更新
            self._cached_entries = self._manager.get_entry_cache() or {}
            
            # 現在のパスとカレントディレクトリを更新
            self._current_path = path
            self._current_directory = ""  # 初期状態はルートディレクトリ
            
            self.debug_info(f"パスが正常に開かれました: {path}")
            self.debug_info(f"カレントディレクトリをリセットしました: '{self._current_directory}'")
            
            # ブラウザインスタンスをリセット
            self._browser = None
            
            return True
        except Exception as e:
            self.debug_error(f"パスを開く際にエラーが発生しました: {e}", trace=self._debug_mode)
            return False
    
    def list_items(self) -> List[Dict[str, Any]]:
        """
        現在のディレクトリのアイテムを取得
        
        Returns:
            List[Dict[str, Any]]: アイテムのリスト
        """
        try:
            # ベースパスからの相対パスとしてカレントディレクトリを使用
            rel_path = self._current_directory
            self.debug_info(f"ディレクトリ内容を取得: '{rel_path}'")
            
            # マネージャーからエントリを取得
            entries = self._manager.list_entries(rel_path)
            
            # UIで使いやすい形式に変換
            result = []
            for entry in entries:
                item = {
                    'name': entry.name,
                    'is_dir': entry.type == EntryType.DIRECTORY or entry.type == EntryType.ARCHIVE,
                    'size': entry.size if entry.type == EntryType.FILE else 0,
                    'modified': entry.modified_time.strftime("%Y-%m-%d %H:%M:%S") if entry.modified_time else "",
                    'type': entry.type.name,
                    'path': entry.rel_path
                }
                result.append(item)
            
            self.debug_info(f"{len(result)} アイテムが見つかりました")
            return result
        except Exception as e:
            self.debug_error(f"ディレクトリ内容の取得に失敗しました: {e}", trace=self._debug_mode)
            return []
    
    def change_directory(self, path: str) -> bool:
        """
        カレントディレクトリを変更
        
        Args:
            path: 移動先のディレクトリパス
                - 絶対パス(/)で始まる場合はベースパスからの絶対パス
                - 相対パスの場合は現在のディレクトリからの相対パス
                - ".." は親ディレクトリに移動
                - "." は現在のディレクトリのまま
            
        Returns:
            bool: 成功したかどうか
        """
        try:
            # パスを正規化
            path = normalize_path(path)
            self.debug_info(f"ディレクトリ変更: '{path}'")
            
            # 特殊なパス処理は維持（基本的なナビゲーション機能）
            if path == ".":
                # 現在のディレクトリのまま
                return True
            elif path == "..":
                # 親ディレクトリに移動
                if not self._current_directory or self._current_directory == "/":
                    # ルートディレクトリの場合は何もしない
                    self._current_directory = ""
                    self.debug_info("既にルートディレクトリにいるため、親ディレクトリに移動できません")
                    return True
                else:
                    # 最後の/までを削除して親ディレクトリに移動
                    current = self._current_directory.rstrip('/')
                    if '/' in current:
                        parent_dir = current.rsplit('/', 1)[0]
                        # 空文字列の場合はルートを表す
                        self._current_directory = parent_dir if parent_dir != "" else ""
                        self.debug_info(f"親ディレクトリに移動: '{self._current_directory}'")
                    else:
                        # 既にルートの子ディレクトリの場合はルートに移動
                        self._current_directory = ""
                        self.debug_info("ルートディレクトリに移動")
                    return True
                    
            # パスが絶対パスかどうかを判定
            if path.startswith("/"):
                # 絶対パスの場合は直接設定（先頭の/は除去）
                new_path = path[1:] if len(path) > 1 else ""
                self.debug_info(f"絶対パスが指定されました: {path} -> {new_path}")
            else:
                new_path = path
                self.debug_info(f"相対パスをそのまま使用: {path}")
            
            # パスの正規化
            new_path = normalize_path(new_path)
            
            # 存在チェックは行わない - マネージャーに任せる
            # 新しいパスを設定
            self._current_directory = new_path
            self.debug_info(f"カレントディレクトリを変更しました: '{self._current_directory}'")
            
            return True
        except Exception as e:
            self.debug_error(f"ディレクトリの変更に失敗しました: {e}", trace=self._debug_mode)
            return False

    def navigate_to_item(self, item_name: str) -> bool:
        """
        現在のディレクトリからアイテム（フォルダ）に移動する
        
        Args:
            item_name: 移動先のアイテム名 (現在のディレクトリからの相対パス)
            
        Returns:
            bool: 成功したかどうか
        """
        try:
            # パスを正規化
            norm_item = normalize_path(item_name)
            
            # カレントディレクトリと結合
            if self._current_directory:
                # パス結合（OSのパス区切り文字ではなく、アーカイブ内での区切り文字を使用）
                full_path = os.path.join(self._current_directory, norm_item).replace('\\', '/')
            else:
                full_path = norm_item
            
            self.debug_info(f"アイテムに移動中: {full_path} (カレントディレクトリ: {self._current_directory})")
            
            # ディレクトリ変更
            return self.change_directory(full_path)
        except Exception as e:
            self.debug_error(f"アイテムへの移動に失敗しました: {item_name} - {e}", trace=self._debug_mode)
            return False
    
    def get_current_directory(self) -> str:
        """
        現在のディレクトリパスを取得
        
        Returns:
            str: 現在のディレクトリパス（ベースパスからの相対パス）
        """
        return self._current_directory
    
    def get_full_path(self) -> str:
        """
        現在の完全なパス（ベースパス + カレントディレクトリ）を取得
        
        Returns:
            str: 表示用の完全なパス
        """
        if not self._current_path:
            return ""
        
        if not self._current_directory:
            return self._current_path
        
        # キャッシュから現在のパスのエントリ情報を取得
        cache = self.get_entry_cache()
        root_entry = cache.get("", None) if cache else None
        
        # エントリ情報からアーカイブかどうかを判断
        # EntryType.ARCHIVE または既知のアーカイブ拡張子でチェック
        is_archive = False
        if root_entry and hasattr(root_entry, 'type'):
            is_archive = root_entry.type == EntryType.ARCHIVE
        
        # アーカイブ内パスの場合は特殊なセパレータを使用
        if is_archive:
            return f"{self._current_path}:/{self._current_directory}"
        else:
            # フォルダの場合は単純に結合
            return os.path.join(self._current_path, self._current_directory)
    
    def extract_file(self, file_path: str) -> Optional[bytes]:
        """
        ファイルの内容を抽出
        
        Args:
            file_path: ファイルパス (カレントディレクトリからの相対パスまたは絶対パス)
            
        Returns:
            Optional[bytes]: ファイルの内容、失敗した場合はNone
        """
        try:
            # パスを正規化
            norm_path = normalize_path(file_path)
            
            self.debug_info(f"ファイルを読み込み中: {norm_path} (相対パス)")
            return self._manager.read_file(norm_path)
        except Exception as e:
            self.debug_error(f"ファイルの読み込みに失敗しました: {file_path} - {e}", trace=self._debug_mode)
            return None

    def extract_item(self, item_name: str) -> Optional[bytes]:
        """
        現在のディレクトリからアイテムを抽出する
        
        Args:
            item_name: 抽出するアイテム名 (現在のディレクトリからの相対パス)
            
        Returns:
            Optional[bytes]: アイテムの内容、失敗した場合はNone
        """
        try:
            # パスを正規化
            norm_item = normalize_path(item_name)
            
            # カレントディレクトリと結合
            if self._current_directory:
                # パス結合（OSのパス区切り文字ではなく、アーカイブ内での区切り文字を使用）
                full_path = os.path.join(self._current_directory, norm_item).replace('\\', '/')
            else:
                full_path = norm_item
            
            self.debug_info(f"アイテムを読み込み中: {full_path} (カレントディレクトリ: {self._current_directory})")
            return self._manager.read_file(full_path)
        except Exception as e:
            self.debug_error(f"アイテムの読み込みに失敗しました: {item_name} - {e}", trace=self._debug_mode)
            return None
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        エントリ情報を取得
        
        Args:
            path: パス
            
        Returns:
            Optional[EntryInfo]: エントリ情報、失敗した場合はNone
        """
        try:
            path = normalize_path(path)
            # マネージャーからエントリ情報を取得するメソッドを呼び出し
            if hasattr(self._manager, 'get_entry_info'):
                return self._manager.get_entry_info(path)
            return None
        except Exception:
            return None
    
    def get_entry_cache(self) -> Dict[str, EntryInfo]:
        """
        エントリキャッシュを取得
        
        Returns:
            Dict[str, EntryInfo]: エントリキャッシュ
        """
        try:
            return self._manager.get_entry_cache()
        except Exception:
            return {}
    
    def get_archive_info(self) -> Dict[str, Any]:
        """
        現在のアーカイブの情報を取得
        
        Returns:
            Dict[str, Any]: アーカイブ情報
        """
        # マネージャーが直接アーカイブ情報を提供するメソッドを持っていればそれを使う
        if hasattr(self._manager, 'get_archive_info'):
            try:
                return self._manager.get_archive_info()
            except Exception as e:
                if self._debug_mode:
                    self.debug_error(f"アーカイブ情報取得中のエラー: {e}", trace=True)
        
        # なければ基本情報のみ返す
        result = {
            'path': self._current_path,
            'entries': 0,
            'size': 0,
            'modified': '',
            'type': '',
        }
        
        # マネージャーからエントリ数を取得（シンプルな処理）
        try:
            cache = self.get_entry_cache()
            if cache:
                result['entries'] = len(cache)
        except Exception:
            pass
            
        return result
    
    def close(self) -> None:
        """現在開いているアーカイブまたはディレクトリを閉じる"""
        try:
            self._manager.close()
        except Exception:
            pass
        self._current_path = ""
        self._cached_entries = {}
    
    def get_browser(self, exts: List[str] = None, current_path: str = "", pages: int = 1, shift: bool = False) -> ArchiveBrowser:
        """
        アーカイブブラウザを取得または作成
        
        Args:
            exts: ブラウズ対象の拡張子リスト（省略可能）
            current_path: 現在のパス（省略可能）
            pages: ページ数（1または2）（省略可能）
            shift: シフトフラグ（省略可能）
            
        Returns:
            ArchiveBrowserインスタンス
        """
        # 既存のブラウザインスタンスが存在しない、または再作成が必要な場合
        if self._browser is None:
            if self._debug_mode:
                log_print(INFO, f"ブラウザを作成: exts={exts}, path={current_path}, pages={pages}, shift={shift}")
            
            # デフォルト拡張子の設定
            if exts is None:
                from decoder.interface import get_supported_image_extensions
                exts = get_supported_image_extensions()
                
            # ブラウザインスタンスを作成
            self._browser = get_browser(self._manager, current_path, exts, pages, shift)
            
        return self._browser
    
    def update_browser(self, current_path: str = "", pages: int = 1, shift: bool = False) -> ArchiveBrowser:
        """
        既存のブラウザパラメータを更新
        
        Args:
            current_path: 現在のパス（省略可能）
            pages: ページ数（1または2）（省略可能）
            shift: シフトフラグ（省略可能）
            
        Returns:
            更新されたArchiveBrowserインスタンス
        """
        # 前回と同じ拡張子を使用
        exts = None
        if self._browser is not None:
            # ブラウザを再作成
            if self._debug_mode:
                log_print(INFO, f"ブラウザを更新: path={current_path}, pages={pages}, shift={shift}")
            
            # ブラウザインスタンスを作成し直す（前回と同じ拡張子）
            self._browser = get_browser(self._manager, current_path, exts, pages, shift)
            
        else:
            # 既存のブラウザがない場合は新規作成
            if self._debug_mode:
                log_print(INFO, f"ブラウザを新規作成: path={current_path}, pages={pages}, shift={shift}")
            
            # デフォルト拡張子の設定
            from decoder.interface import get_supported_image_extensions
            exts = get_supported_image_extensions()
            
            # ブラウザインスタンスを作成
            self._browser = get_browser(self._manager, current_path, exts, pages, shift)
            
        return self._browser