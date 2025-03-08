"""
アーカイブマネージャーファクトリ

アーカイブマネージャーの生成と取得を行うファクトリモジュール
"""

import os
import tempfile
import shutil
from typing import List, Optional, BinaryIO, Tuple
from .arc import ArchiveManager, EntryInfo, EntryType, ArchiveHandler
from .handlers import register_standard_handlers  # handlers.py からインポート

# シングルトンインスタンス
_instance: ArchiveManager = None


class EnhancedArchiveManager(ArchiveManager):
    """
    強化されたアーカイブマネージャー
    
    アーカイブ内のアーカイブ（ネスト構造）をサポートするための拡張
    ハンドラに処理を委譲し、アーカイブ形式に依存しないインターフェースを提供
    """
    
    # 最大ネスト階層の深さ制限
    MAX_NEST_DEPTH = 5
    
    def __init__(self):
        """拡張アーカイブマネージャを初期化する"""
        super().__init__()
        # サポートされるアーカイブ拡張子のリスト
        self._archive_extensions = []
        # 現在処理中のアーカイブパスを追跡するセット（循環参照防止）
        self._processing_archives = set()
        # 処理中のネストレベル（再帰制限用）
        self._current_nest_level = 0
    
    def _update_archive_extensions(self):
        """サポートされているアーカイブ拡張子のリストを更新する"""
        # 各ハンドラからサポートされている拡張子を収集
        self._archive_extensions = []
        for handler in self.handlers:
            self._archive_extensions.extend(handler.supported_extensions)
        # 重複を除去
        self._archive_extensions = list(set(self._archive_extensions))
    
    def _is_archive_by_extension(self, path: str) -> bool:
        """パスがアーカイブの拡張子を持つかどうかを判定する"""
        if not self._archive_extensions:
            self._update_archive_extensions()
            
        _, ext = os.path.splitext(path.lower())
        return ext in self._archive_extensions
    
    def list_entries(self, path: str) -> List[EntryInfo]:
        """
        指定されたパスの配下にあるエントリのリストを取得する
        
        Args:
            path: リストを取得するディレクトリのパス
            
        Returns:
            エントリ情報のリスト。失敗した場合は空リスト
        """
        # 循環参照防止とネスト深度チェック
        if path in self._processing_archives:
            print(f"EnhancedArchiveManager: 循環参照を検出しました: {path}")
            return []
        
        if self._current_nest_level >= self.MAX_NEST_DEPTH:
            print(f"EnhancedArchiveManager: 最大ネスト階層 ({self.MAX_NEST_DEPTH}) に達しました")
            return []
            
        # 再帰レベルを増加
        self._current_nest_level += 1
        
        try:
            # アーカイブ拡張子のリストを更新
            if not self._archive_extensions:
                self._update_archive_extensions()
            
            # エントリ情報を取得する
            entry_info = self.get_entry_info(path)
            
            # 1. エントリがアーカイブファイル自体の場合
            if entry_info and entry_info.type == EntryType.ARCHIVE:
                print(f"EnhancedArchiveManager: アーカイブ自体のエントリリストを取得: {path}")
                
                # アーカイブがネスト内にあるか分析
                parent_archive_path, internal_archive_path = self._analyze_path(path)
                
                # ネストされたアーカイブの場合（親アーカイブが存在する）
                if parent_archive_path and internal_archive_path:
                    print(f"EnhancedArchiveManager: ネストされたアーカイブを検出: {parent_archive_path} -> {internal_archive_path}")
                    
                    # 一時的に処理中として記録（循環参照防止）
                    self._processing_archives.add(path)
                    
                    try:
                        # 親アーカイブのハンドラを取得
                        parent_handler = super().get_handler(parent_archive_path)
                        if not parent_handler:
                            print(f"EnhancedArchiveManager: 親アーカイブのハンドラが見つかりません: {parent_archive_path}")
                            return []
                        
                        # 親アーカイブからネストされたアーカイブファイルの内容を読み込む
                        print(f"EnhancedArchiveManager: 親アーカイブから内部アーカイブファイルを読み込み中...")
                        nested_archive_content = parent_handler.read_archive_file(parent_archive_path, internal_archive_path)
                        if not nested_archive_content:
                            print(f"EnhancedArchiveManager: ネストアーカイブコンテンツの読み込み失敗: {path}")
                            return []
                            
                        print(f"EnhancedArchiveManager: 内部アーカイブファイルを取得成功 ({len(nested_archive_content)} バイト)")
                        
                        # 拡張子に基づいてハンドラを検索
                        file_ext = os.path.splitext(internal_archive_path.lower())[1]
                        nested_handler = self._find_handler_for_extension(file_ext)
                        
                        if nested_handler:
                            print(f"EnhancedArchiveManager: ネストアーカイブハンドラを選択: {nested_handler.__class__.__name__}")
                            
                            # メモリ上でアーカイブ内容を直接処理
                            print(f"EnhancedArchiveManager: メモリ上でアーカイブ内容を処理中...")
                            entries = nested_handler.list_entries_from_bytes(nested_archive_content)
                            
                            if entries:
                                # パスをエミュレートしたパスで設定
                                print(f"EnhancedArchiveManager: 内部アーカイブから {len(entries)} エントリを取得")
                                self._fix_nested_entry_paths(entries, path)
                                return entries
                            else:
                                # メモリからの読み込みに失敗した場合は、一時ファイル経由で処理を試みる
                                print(f"EnhancedArchiveManager: メモリからの処理に失敗、一時ファイル経由で処理を試みます")
                                
                                # 一時ファイルに内容を保存
                                temp_file = None
                                try:
                                    temp_file = nested_handler.save_to_temp_file(nested_archive_content, file_ext)
                                    if temp_file:
                                        print(f"EnhancedArchiveManager: 一時ファイルを作成: {temp_file}")
                                        entries = nested_handler.list_entries(temp_file)
                                        if entries:
                                            # 一時ファイルパスを元のエミュレートパスに修正
                                            self._fix_entry_paths(entries, temp_file, path)
                                            return entries
                                finally:
                                    # 一時ファイルの削除
                                    if temp_file and os.path.exists(temp_file):
                                        nested_handler.cleanup_temp_file(temp_file)
                        else:
                            print(f"EnhancedArchiveManager: 拡張子 '{file_ext}' に対応するハンドラが見つかりません")
                    finally:
                        # 処理中のマークを解除
                        self._processing_archives.discard(path)
                
                # 通常のアーカイブファイル（ネストされていない）
                handler = super().get_handler(path)
                if handler:
                    entries = handler.list_entries(path)
                    return self._mark_archive_entries(entries)
                return []
            
            # 2. アーカイブ内の通常のパスの場合
            parent_archive_path, internal_path = self._analyze_path(path)
            
            if (parent_archive_path):
                handler = super().get_handler(parent_archive_path)
                if not handler:
                    return []
                
                # パスの子要素にアーカイブファイルがないか確認する必要がある
                entries = handler.list_entries(path)
                
                # エントリにアーカイブファイルがあれば、特別に処理
                nested_archive_entry = None
                for entry in entries:
                    if entry.type == EntryType.ARCHIVE:
                        # このエントリはネストされたアーカイブファイル
                        print(f"EnhancedArchiveManager: エントリリスト内にネストされたアーカイブを検出: {entry.path}")
                        nested_archive_entry = entry
                        break
                
                # ネストされたアーカイブが見つかり、そのパスが要求されたパスと一致する場合は、中身を展開
                if nested_archive_entry and nested_archive_entry.path == path:
                    print(f"EnhancedArchiveManager: ネストアーカイブの内容を取得します: {path}")
                    
                    # 循環参照チェック
                    if path in self._processing_archives:
                        print(f"EnhancedArchiveManager: 循環参照を検出しました: {path}")
                        return entries
                    
                    # 一時的に処理中として記録（循環参照防止）
                    self._processing_archives.add(path)
                    
                    try:
                        # ネストされたアーカイブの中身を取得
                        return self._process_nested_archive_content(parent_archive_path, internal_path, path)
                    finally:
                        # 処理中のマークを解除
                        self._processing_archives.discard(path)
                
                return self._mark_archive_entries(entries)
            
            # 3. 通常のディレクトリ
            handler = super().get_handler(path)
            if not handler:
                return []
            
            entries = handler.list_entries(path)
            return self._mark_archive_entries(entries)
        
        except Exception as e:
            print(f"EnhancedArchiveManager.list_entries エラー: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            # 再帰レベルを減少
            self._current_nest_level -= 1
    
    def _mark_archive_entries(self, entries: List[EntryInfo]) -> List[EntryInfo]:
        """エントリリストの中からファイル拡張子がアーカイブのものをアーカイブタイプとしてマーク"""
        if not entries:
            return []
            
        for entry in entries:
            if entry.type == EntryType.FILE and self._is_archive_by_extension(entry.name):
                entry.type = EntryType.ARCHIVE
        return entries
    
    def _join_paths(self, archive_path: str, internal_path: str) -> str:
        """アーカイブパスと内部パスを結合"""
        if not internal_path:
            return archive_path
        return f"{archive_path}/{internal_path}"
    
    def _analyze_path(self, path: str) -> Tuple[str, str]:
        """パスを解析し、アーカイブパスと内部パスに分割する"""
        # 正規化したパス
        norm_path = path.replace('\\', '/')
        
        # パスコンポーネントごとに分解
        parts = norm_path.split('/')
        
        # パスを順に構築し、アーカイブファイルを検出
        test_path = ""
        for i, part in enumerate(parts):
            if i > 0:
                test_path += "/"
            test_path += part
            
            # 現在のパスが物理ファイルとして存在するか確認
            if os.path.isfile(test_path):
                # アーカイブファイルかどうか判定
                handler = super().get_handler(test_path)
                if handler and self._is_archive_by_extension(test_path):
                    # アーカイブファイル発見
                    # 残りのコンポーネントが内部パス
                    internal_path = '/'.join(parts[i+1:])
                    return test_path, internal_path
        
        # アーカイブファイルが見つからなかった
        return "", ""
    
    def read_archive_file(self, archive_path: str, file_path: str) -> Optional[bytes]:
        """
        アーカイブファイル内のファイルの内容を読み込む (ネストアーカイブ対応)
        
        Args:
            archive_path: アーカイブファイルのパス
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        # 循環参照防止とネスト深度チェック
        if self._current_nest_level >= self.MAX_NEST_DEPTH:
            print(f"EnhancedArchiveManager: 最大ネスト階層 ({self.MAX_NEST_DEPTH}) に達しました")
            return None
            
        # 再帰レベルを増加
        self._current_nest_level += 1
        
        try:
            # まずは基本実装を試す
            handler = super().get_handler(archive_path)
            if not handler:
                print(f"EnhancedArchiveManager: アーカイブのハンドラが見つかりません: {archive_path}")
                return None
                
            # 通常の読み込みを試みる
            content = handler.read_archive_file(archive_path, file_path)
            if content is not None:
                return content
                
            # ファイルパスがネストされたアーカイブを指す可能性がある場合
            if '/' in file_path:
                # ディレクトリとファイル名に分解
                dir_path = os.path.dirname(file_path)
                file_name = os.path.basename(file_path)
                
                # ファイル名がアーカイブ拡張子を持つか確認
                _, ext = os.path.splitext(file_name.lower())
                if ext in self._archive_extensions:
                    print(f"EnhancedArchiveManager: {file_name} はネストされたアーカイブです")
                    
                    # 最初のレベルの内部アーカイブファイル内容取得
                    parent_archive_content = handler.read_archive_file(archive_path, file_path)
                    if not parent_archive_content:
                        print(f"EnhancedArchiveManager: 内部アーカイブの内容取得失敗: {file_path}")
                        return None
                    
                    # ネストされたアーカイブ内のファイルはここでは処理しない
                    # （そのケースはパスを変換して別途処理される）
                    return parent_archive_content
            
            return None
        finally:
            # 再帰レベルを減少
            self._current_nest_level -= 1
    
    def _find_handler_for_extension(self, extension: str) -> Optional[ArchiveHandler]:
        """拡張子に基づいて適切なハンドラを見つける"""
        for handler in self.handlers:
            if extension.lower() in [ext.lower() for ext in handler.supported_extensions]:
                return handler
        return None
    
    def _fix_nested_entry_paths(self, entries: List[EntryInfo], parent_path: str) -> None:
        """ネストされたアーカイブのエントリパスを修正する"""
        for entry in entries:
            # 元のパスは内部的な一時パスまたは相対パス
            # それを親アーカイブのパスを基準にした仮想パスに変更
            entry.path = f"{parent_path}/{entry.path}" if entry.path else parent_path
    
    def _find_handler_for_content(self, content: bytes, file_name: str) -> Optional[ArchiveHandler]:
        """内容と名前に基づいてアーカイブハンドラを選択する"""
        _, ext = os.path.splitext(file_name.lower())
        
        # 対応するハンドラを探す
        for handler in self.handlers:
            if ext in handler.supported_extensions:
                return handler
                
        return None
    
    def _can_handler_process_content(self, handler: ArchiveHandler, content: bytes, filename: str) -> bool:
        """ハンドラが指定されたコンテンツを処理できるかをチェック"""
        ext = os.path.splitext(filename.lower())[1]
        # 拡張子をサポートしているか確認
        if ext in handler.supported_extensions:
            return True
        return False
        
    def _fix_entry_paths(self, entries: List[EntryInfo], temp_path: str, original_path: str) -> None:
        """一時ファイルパスから元のパスにエントリパスを修正"""
        for entry in entries:
            if entry.path.startswith(temp_path):
                relative_path = entry.path[len(temp_path):]
                if relative_path.startswith('/') or relative_path.startswith('\\'):
                    relative_path = relative_path[1:]
                
                if relative_path:
                    entry.path = f"{original_path}/{relative_path}"
                else:
                    entry.path = original_path

    def _process_nested_archive_content(self, parent_archive_path: str, nested_archive_path: str, full_path: str) -> List[EntryInfo]:
        """
        ネストされたアーカイブの内容を処理する
        
        Args:
            parent_archive_path: 親アーカイブのパス
            nested_archive_path: 親アーカイブ内のネストされたアーカイブのパス
            full_path: 完全なパス (親 + ネスト)
            
        Returns:
            エントリ情報のリスト
        """
        print(f"EnhancedArchiveManager: ネストアーカイブ処理: {parent_archive_path} -> {nested_archive_path}")
        
        # 親アーカイブのハンドラを取得
        parent_handler = super().get_handler(parent_archive_path)
        if not parent_handler:
            print(f"EnhancedArchiveManager: 親アーカイブのハンドラが見つかりません: {parent_archive_path}")
            return []
        
        # ネストされたアーカイブファイルの内容を読み込む
        nested_archive_content = parent_handler.read_archive_file(parent_archive_path, nested_archive_path)
        if not nested_archive_content:
            print(f"EnhancedArchiveManager: ネストアーカイブの内容を取得できませんでした: {nested_archive_path}")
            return []
        
        print(f"EnhancedArchiveManager: ネストアーカイブファイル読み込み成功: {len(nested_archive_content)} バイト")
        
        # 拡張子に基づいて適切なハンドラを選択
        file_ext = os.path.splitext(nested_archive_path.lower())[1]
        nested_handler = self._find_handler_for_extension(file_ext)
        
        if not nested_handler:
            print(f"EnhancedArchiveManager: 拡張子 '{file_ext}' に対応するハンドラが見つかりません")
            return []
        
        print(f"EnhancedArchiveManager: ネストアーカイブ用ハンドラ: {nested_handler.__class__.__name__}")
        
        # メモリ上でアーカイブの内容を処理
        entries = nested_handler.list_entries_from_bytes(nested_archive_content)
        
        if entries:
            # 相対パスを絶対パスに変換
            self._fix_nested_entry_paths(entries, full_path)
            print(f"EnhancedArchiveManager: ネストアーカイブから {len(entries)} エントリを取得")
            return entries
        
        # メモリ処理に失敗した場合は一時ファイル経由で処理
        print("EnhancedArchiveManager: メモリ処理に失敗、一時ファイル経由で処理を試みます")
        
        temp_file = None
        try:
            temp_file = nested_handler.save_to_temp_file(nested_archive_content, file_ext)
            if temp_file:
                print(f"EnhancedArchiveManager: ネストアーカイブを一時ファイルとして保存: {temp_file}")
                entries = nested_handler.list_entries(temp_file)
                if entries:
                    self._fix_entry_paths(entries, temp_file, full_path)
                    print(f"EnhancedArchiveManager: 一時ファイル経由で {len(entries)} エントリを取得")
                    return entries
        finally:
            if temp_file and os.path.exists(temp_file):
                nested_handler.cleanup_temp_file(temp_file)
                
        print(f"EnhancedArchiveManager: ネストアーカイブの内容取得に失敗しました")
        return []


def get_archive_manager() -> ArchiveManager:
    """
    アプリケーション全体で共有するアーカイブマネージャーのシングルトンインスタンスを取得する
    
    Returns:
        設定済みのアーカイブマネージャー
    """
    global _instance
    
    if (_instance is None):
        _instance = create_archive_manager()
    
    return _instance


def create_archive_manager() -> ArchiveManager:
    """
    新しいアーカイブマネージャーのインスタンスを作成する
    
    Returns:
        設定済みの新しいアーカイブマネージャー
    """
    # 強化版のマネージャーを使用
    manager = EnhancedArchiveManager()
    try:
        register_standard_handlers(manager)
    except Exception as e:
        print(f"ハンドラの登録中にエラーが発生しました: {e}")
    return manager


def reset_manager() -> None:
    """
    シングルトンのアーカイブマネージャーをリセットする（主にテスト用）
    """
    global _instance
    _instance = None


# 以下はアプリケーション層向けの統一インターフェース
# アプリ層はArcManagerクラスを直接使わず、以下の関数を通して操作する

def list_entries(path: str) -> List[EntryInfo]:
    """
    指定されたパスの配下にあるエントリのリストを取得する
    
    Args:
        path: リストを取得するディレクトリのパス
            
    Returns:
        エントリ情報のリスト。失敗した場合は空リスト
    """
    return get_archive_manager().list_entries(path)


def get_entry_info(path: str) -> Optional[EntryInfo]:
    """
    指定されたパスのエントリ情報を取得する
    
    Args:
        path: 情報を取得するエントリのパス
            
    Returns:
        エントリ情報。存在しない場合はNone
    """
    return get_archive_manager().get_entry_info(path)


def read_file(path: str) -> Optional[bytes]:
    """
    指定されたパスのファイルの内容を読み込む
    
    Args:
        path: 読み込むファイルのパス
            
    Returns:
        ファイルの内容。読み込みに失敗した場合はNone
    """
    return get_archive_manager().read_file(path)


def read_archive_file(archive_path: str, file_path: str) -> Optional[bytes]:
    """
    アーカイブファイル内のファイルの内容を読み込む
    
    Args:
        archive_path: アーカイブファイルのパス
        file_path: アーカイブ内のファイルパス
            
    Returns:
        ファイルの内容。読み込みに失敗した場合はNone
    """
    # アーカイブファイルを処理するハンドラを取得
    handler = get_archive_manager().get_handler(archive_path)
    if handler is None:
        print(f"ArchiveManager: アーカイブ {archive_path} に対応するハンドラが見つかりません")
        return None
        
    # アーカイブ内のファイルを読み込む前に、EntryInfoを取得してname_in_arcをチェック
    full_path = f"{archive_path}/{file_path}"
    entry_info = get_archive_manager().get_entry_info(full_path)
    
    # name_in_arcが設定されている場合
    if entry_info and entry_info.name_in_arc:
        # name_in_arcが完全パスか、単なるファイル名かを判断
        if '/' in entry_info.name_in_arc:
            # name_in_arcが完全パス - そのまま使用
            corrected_path = entry_info.name_in_arc
        else:
            # name_in_arcがファイル名のみ - ディレクトリ部分を追加
            dir_path = os.path.dirname(file_path)
            if dir_path:
                dir_path += '/'
            corrected_path = dir_path + entry_info.name_in_arc
            
        # パスが異なる場合のみログを出力
        if corrected_path != file_path:
            print(f"ArchiveManager: name_in_arcを使用: {file_path} -> {corrected_path}")
            file_path = corrected_path
    
    # 通常のファイル読み込み
    print(f"ArchiveManager: {handler.__class__.__name__} でアーカイブファイル読み込み: {archive_path}/{file_path}")
    return handler.read_archive_file(archive_path, file_path)


def get_stream(path: str) -> Optional[BinaryIO]:
    """
    指定されたパスのファイルのストリームを取得する
    
    Args:
        path: ストリームを取得するファイルのパス
            
    Returns:
        ファイルストリーム。取得できない場合はNone
    """
    return get_archive_manager().get_stream(path)


def is_archive(path: str) -> bool:
    """
    指定されたパスがアーカイブファイルかどうかを判定する
    
    Args:
        path: 判定するパス
            
    Returns:
        アーカイブファイルならTrue、そうでなければFalse
    """
    return get_archive_manager().is_archive(path)


def is_directory(path: str) -> bool:
    """
    指定されたパスがディレクトリかどうかを判定する
    
    Args:
        path: 判定するパス
            
    Returns:
        ディレクトリの場合はTrue、それ以外の場合はFalse
    """
    return get_archive_manager().is_directory(path)


def get_parent_path(path: str) -> str:
    """
    親ディレクトリのパスを取得する
    
    Args:
        path: 対象のパス
            
    Returns:
        親ディレクトリのパス
    """
    return get_archive_manager().get_parent_path(path)
