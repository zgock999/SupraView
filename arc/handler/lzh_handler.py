"""
LZHアーカイブハンドラ

LZHアーカイブファイルへのアクセスを提供するハンドラ
最新のlhafileライブラリはPure Python実装で、外部コマンドに依存しない
"""

import os
import datetime
from typing import List, Optional, Dict, Any, BinaryIO, Tuple

from ..arc import ArchiveHandler, EntryInfo, EntryType

# lhafileモジュールが必要（Pure Python実装）
try:
    import lhafile
    LHAFILE_AVAILABLE = True
except ImportError:
    print("警告: LZHファイルサポートには 'lhafile' モジュールが必要です")
    print("pip install lhafile でインストールしてください")
    LHAFILE_AVAILABLE = False
    raise ImportError("LZHサポートに必要なモジュールがインストールされていません")


class LzhHandler(ArchiveHandler):
    """
    LZHアーカイブハンドラ
    
    LZHアーカイブファイルの内容にアクセスするためのハンドラ実装
    Pure Python実装で外部ツールに依存しない
    """
    
    def __init__(self):
        """LZHアーカイブハンドラを初期化する"""
        # LZH構造キャッシュの追加
        self.structure_cache: Dict[str, Dict[str, Dict]] = {}
        
    @property
    def supported_extensions(self) -> List[str]:
        """このハンドラがサポートするファイル拡張子のリスト"""
        return ['.lzh', '.lha']
    
    def can_handle(self, path: str) -> bool:
        """
        このハンドラがパスを処理できるか判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            処理可能な場合はTrue、そうでない場合はFalse
        """
        if not os.path.isfile(path):
            return False
            
        # 拡張子で簡易判定
        _, ext = os.path.splitext(path.lower())
        if ext not in ['.lzh', '.lha']:
            return False
            
        # LZHファイルとして開けるかどうか確認
        try:
            with lhafile.Lhafile(path) as lf:
                return True
        except:
            return False
    
    def list_entries(self, path: str) -> Optional[List[EntryInfo]]:
        """
        指定したパスのエントリ一覧を取得する
        
        Args:
            path: 一覧を取得するパス（LZHファイル、またはLZH内のディレクトリ）
            
        Returns:
            エントリ情報のリスト、またはNone（取得できない場合）
        """
        # パスがLZHファイル自体かLZH内のパスかを判定
        lzh_path, internal_path = self._split_path(path)
        
        if not lzh_path:
            return None
        
        # LZHファイルを開く
        try:
            with lhafile.Lhafile(lzh_path, 'r') as lf:
                # エントリリストを作成
                
                result_entries = []
                
                # LZHファイル構造を取得/更新
                structure = self._get_lzh_structure(lzh_path, lf)
                
                # 要求されたパスの正規化
                if internal_path and not internal_path.endswith('/'):
                    internal_path += '/'
                
                # 指定されたディレクトリが存在するか確認
                if internal_path not in structure:
                    if internal_path:  # ルートでなければ空を返す
                        return []
                    internal_path = ''  # ルートの場合は空文字に正規化
                
                # このディレクトリの子（ファイルとサブフォルダ）を取得
                current_dir = structure[internal_path]
                
                # サブディレクトリをリストに追加
                for dir_name in current_dir['dirs']:
                    dir_path = os.path.join(path, dir_name).replace('\\', '/')
                    
                    result_entries.append(EntryInfo(
                        name=dir_name,
                        path=dir_path,
                        size=0,
                        modified_time=None,
                        type=EntryType.DIRECTORY
                    ))
                
                # ファイルをリストに追加
                for file_name, info in current_dir['files'].items():
                    file_path = os.path.join(path, file_name).replace('\\', '/')
                    
                    result_entries.append(EntryInfo(
                        name=file_name,
                        path=file_path,
                        size=info.get('size', 0),
                        modified_time=info.get('mtime', None),
                        type=EntryType.FILE
                    ))
                
                return result_entries
        except Exception as e:
            print(f"LZHエントリ列挙エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_lzh_structure(self, lzh_path: str, lf = None) -> Dict:
        """
        LZHファイルの内部構造を解析し、ディレクトリ構造を構築する
        
        Args:
            lzh_path: LZHファイルのパス
            lf: 既に開かれているLhafileオブジェクト（オプション）
            
        Returns:
            ディレクトリ構造の辞書
        """
        # キャッシュ確認
        if lzh_path in self.structure_cache:
            return self.structure_cache[lzh_path]
            
        # Lhafileを取得
        should_close = False
        if lf is None:
            try:
                lf = lhafile.Lhafile(lzh_path, 'r')
                should_close = True
            except Exception as e:
                print(f"LZHファイル解析エラー: {str(e)}, パス: {lzh_path}")
                return {}
                
        try:
            # ディレクトリ構造を初期化
            structure = {'': {'dirs': set(), 'files': {}}}
            
            # すべてのLZHエントリを処理
            for i in range(len(lf.namelist())):
                info = lf.infolist()[i]
                name = lf.namelist()[i]
                
                # ディレクトリか判定（LZHは通常明示的なディレクトリエントリを持たないので、末尾のスラッシュで判定）
                is_dir = name.endswith('/')
                
                # 日時情報の変換
                try:
                    timestamp = datetime.datetime(
                        info.date_time[0], 
                        info.date_time[1],
                        info.date_time[2],
                        info.date_time[3],
                        info.date_time[4],
                        info.date_time[5]
                    )
                except:
                    timestamp = None
                
                if is_dir:
                    # ディレクトリの場合
                    dir_path = name
                    
                    # 全ての親ディレクトリを登録
                    parent_path = ''
                    for part in dir_path.split('/'):
                        if not part:  # 空文字列をスキップ
                            continue
                        
                        # 親パスと現在のパスを取得
                        current_path = parent_path + part + '/'
                        
                        # 親が存在しなければ作成
                        if parent_path not in structure:
                            structure[parent_path] = {'dirs': set(), 'files': {}}
                        
                        # 親にこのディレクトリを追加
                        if part:
                            structure[parent_path]['dirs'].add(part)
                        
                        # 現在のディレクトリが存在しなければ作成
                        if current_path not in structure:
                            structure[current_path] = {'dirs': set(), 'files': {}}
                        
                        # 親パスを更新
                        parent_path = current_path
                else:
                    # ファイルの場合
                    file_path = name
                    
                    # ファイルのディレクトリパスとファイル名を分解
                    dir_path = os.path.dirname(file_path)
                    if dir_path:
                        dir_path += '/'
                    file_name = os.path.basename(file_path)
                    
                    # ディレクトリパス全体を構築
                    parent_paths = []
                    current_path = ''
                    for part in dir_path.split('/'):
                        if not part:  # 空文字列をスキップ
                            continue
                        current_path += part + '/'
                        parent_paths.append((current_path, part))
                    
                    # 親パスがあれば、全ての親ディレクトリを登録
                    parent_path = ''
                    for current_path, part in parent_paths:
                        # 親が存在しなければ作成
                        if parent_path not in structure:
                            structure[parent_path] = {'dirs': set(), 'files': {}}
                        
                        # 親にこのディレクトリを追加
                        structure[parent_path]['dirs'].add(part)
                        
                        # 現在のディレクトリが存在しなければ作成
                        if current_path not in structure:
                            structure[current_path] = {'dirs': set(), 'files': {}}
                        
                        # 親パスを更新
                        parent_path = current_path
                    
                    # ファイルの親ディレクトリが存在しなければ作成
                    if dir_path not in structure:
                        structure[dir_path] = {'dirs': set(), 'files': {}}
                    
                    # ファイル情報を登録
                    structure[dir_path]['files'][file_name] = {
                        'size': info.file_size,
                        'mtime': timestamp,
                        'index': i  # LHAファイル内のインデックスを保持
                    }
            
            # キャッシュに追加
            self.structure_cache[lzh_path] = structure
            return structure
        finally:
            if should_close and lf:
                lf.close()
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定したパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するパス
            
        Returns:
            エントリ情報、またはNone（取得できない場合）
        """
        # パスがLZHファイル自体かLZH内のパスかを判定
        lzh_path, internal_path = self._split_path(path)
        
        # internal_pathが空ならLZHファイル自体
        if not internal_path:
            if not os.path.isfile(lzh_path):
                return None
                
            # LZHファイル自体の情報を返す
            try:
                file_stat = os.stat(lzh_path)
                return EntryInfo(
                    name=os.path.basename(lzh_path),
                    path=lzh_path,
                    size=file_stat.st_size,
                    modified_time=datetime.datetime.fromtimestamp(file_stat.st_mtime),
                    type=EntryType.ARCHIVE  # LZHファイルはARCHIVEタイプ
                )
            except:
                return None
        
        # LZHファイル内のエントリの情報を取得
        try:
            with lhafile.Lhafile(lzh_path, 'r') as lf:
                # LZH構造を取得
                structure = self._get_lzh_structure(lzh_path, lf)
                
                # パスの正規化
                if internal_path.endswith('/'):
                    # ディレクトリパスの場合
                    dir_path = internal_path
                    parent_dir = os.path.dirname(dir_path.rstrip('/'))
                    if parent_dir:
                        parent_dir += '/'
                    dir_name = os.path.basename(dir_path.rstrip('/'))
                    
                    # ディレクトリが存在するか確認
                    if dir_path in structure:
                        return EntryInfo(
                            name=dir_name,
                            path=path,
                            size=0,
                            modified_time=None,
                            type=EntryType.DIRECTORY
                        )
                    elif parent_dir in structure and dir_name in structure[parent_dir]['dirs']:
                        return EntryInfo(
                            name=dir_name,
                            path=path,
                            size=0,
                            modified_time=None,
                            type=EntryType.DIRECTORY
                        )
                else:
                    # ファイルパスの場合
                    file_dir = os.path.dirname(internal_path)
                    if file_dir:
                        file_dir += '/'
                    file_name = os.path.basename(internal_path)
                    
                    # ファイルが存在するか確認
                    if file_dir in structure and file_name in structure[file_dir]['files']:
                        # ファイル情報を取得
                        file_info = structure[file_dir]['files'][file_name]
                                
                        return EntryInfo(
                            name=file_name,
                            path=path,
                            size=file_info.get('size', 0),
                            modified_time=file_info.get('mtime', None),
                            type=EntryType.FILE
                        )
                            
                    # ディレクトリとして試す
                    dir_path = internal_path + '/'
                    if dir_path in structure:
                        return EntryInfo(
                            name=os.path.basename(internal_path),
                            path=path,
                            size=0,
                            modified_time=None,
                            type=EntryType.DIRECTORY
                        )
                        
                # 見つからなかった
                return None
        except Exception as e:
            print(f"LZHエントリ情報の取得でエラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def read_file(self, path: str) -> Optional[bytes]:
        """
        指定したパスのファイルを読み込む
        
        Args:
            path: 読み込むファイルのパス
            
        Returns:
            ファイルの内容、またはNone（読み込めない場合）
        """
        # パスがLZHファイル自体かLZH内のパスかを判定
        lzh_path, internal_path = self._split_path(path)
        
        # LZHファイル自体なら読み込めない
        if not internal_path:
            return None
        
        # LZHファイル内のファイルを読み込む
        try:
            with lhafile.Lhafile(lzh_path, 'r') as lf:
                # LZH構造を取得
                structure = self._get_lzh_structure(lzh_path, lf)
                
                # ファイルのディレクトリとファイル名を分解
                file_dir = os.path.dirname(internal_path)
                if file_dir:
                    file_dir += '/'
                file_name = os.path.basename(internal_path)
                
                # ファイルが存在するか確認
                if file_dir in structure and file_name in structure[file_dir]['files']:
                    # ファイルのインデックスを取得
                    index = structure[file_dir]['files'][file_name].get('index', -1)
                    
                    if index >= 0:
                        # ファイルを読み込む
                        return lf.read(lf.namelist()[index])
                
                # ファイル名で直接検索
                try:
                    return lf.read(internal_path)
                except:
                    # 指定したファイルがLZH内に存在しない
                    return None
        except Exception as e:
            print(f"LZHファイルの読み込みでエラー: {str(e)}")
            return None
    
    def get_parent_path(self, path: str) -> str:
        """
        指定したパスの親ディレクトリのパスを取得する
        
        Args:
            path: 親ディレクトリを取得するパス
            
        Returns:
            親ディレクトリのパス。親がない場合は空文字列
        """
        # パスがLZHファイル自体かLZH内のパスかを判定
        lzh_path, internal_path = self._split_path(path)
        
        # internal_pathが空ならLZHファイル自体なので、その親を返す
        if not internal_path:
            return os.path.dirname(lzh_path)
        
        # LZH内のパスの親を計算
        parent_dir = os.path.dirname(internal_path.rstrip('/'))
        
        # ルートの場合はLZHファイル自体を返す
        if not parent_dir:
            return lzh_path
            
        # 親ディレクトリのパスを作成して返す
        return self._join_paths(lzh_path, parent_dir)
    
    def is_directory(self, path: str) -> bool:
        """
        指定したパスがディレクトリかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            ディレクトリの場合はTrue、そうでない場合はFalse
        """
        # エントリ情報を取得
        entry_info = self.get_entry_info(path)
        
        # ディレクトリかアーカイブなら真
        return entry_info is not None and (entry_info.type == EntryType.DIRECTORY or entry_info.type == EntryType.ARCHIVE)
    
    def _split_path(self, path: str) -> Tuple[str, str]:
        """
        パスをLZHファイルのパスと内部パスに分割する
        
        Args:
            path: 分割するパス
            
        Returns:
            (LZHファイルのパス, 内部パス) のタプル
        """
        # パスの正規化 (バックスラッシュをスラッシュに変換)
        norm_path = path.replace('\\', '/')
        
        # LZHファイル自体かどうか確認
        if os.path.isfile(norm_path) and (norm_path.lower().endswith('.lzh') or norm_path.lower().endswith('.lha')):
            # パス自体がLZHファイル
            return norm_path, ""
            
        # もっと厳密なパス解析を行う
        try:
            # パスを分解してLZHファイル部分を見つける
            parts = norm_path.split('/')
            
            # LZHファイルのパスを見つける
            lzh_path = ""
            internal_path_parts = []
            
            for i in range(len(parts)):
                # パスの部分を結合してテスト
                test_path = '/'.join(parts[:i+1])
                
                # LZHファイルかどうか確認
                if os.path.isfile(test_path) and (test_path.lower().endswith('.lzh') or test_path.lower().endswith('.lha')):
                    lzh_path = test_path
                    # 残りの部分が内部パス
                    internal_path_parts = parts[i+1:]
                    break
            
            # LZHファイルが見つからなければ無効
            if not lzh_path:
                return "", ""
            
            # 内部パスを結合
            internal_path = '/'.join(internal_path_parts)
            
            return lzh_path, internal_path
        except Exception as e:
            print(f"LZHパス分解エラー: {str(e)}, パス: {path}")
            import traceback
            traceback.print_exc()
            return "", ""
    
    def read_archive_file(self, archive_path: str, file_path: str) -> Optional[bytes]:
        """
        アーカイブファイル内のファイルの内容を読み込む
        
        Args:
            archive_path: アーカイブファイルのパス
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容（バイト配列）。読み込みに失敗した場合はNone
        """
        try:
            # アーカイブパスがLZHファイルであることを確認
            if not os.path.isfile(archive_path) or not (archive_path.lower().endswith('.lzh') or archive_path.lower().endswith('.lha')):
                print(f"指定されたパスはLZHファイルではありません: {archive_path}")
                return None
                
            # ファイルパスを正規化
            norm_file_path = self.normalize_path(file_path)
            
            with lhafile.Lhafile(archive_path, 'r') as lzh_file:
                # LZH構造を取得
                structure = self._get_lzh_structure(archive_path, lzh_file)
                
                # ファイルのディレクトリとファイル名を分解
                file_dir = os.path.dirname(norm_file_path)
                if file_dir:
                    file_dir += '/'
                file_name = os.path.basename(norm_file_path)
                
                # ファイルが存在するか確認
                if file_dir in structure and file_name in structure[file_dir]['files']:
                    # ファイルのインデックスを取得
                    index = structure[file_dir]['files'][file_name].get('index', -1)
                    
                    if index >= 0:
                        # ファイルを読み込む
                        return lzh_file.read(lzh_file.namelist()[index])
                
                # 直接一致しない場合、すべてのエントリを検索
                for i, name in enumerate(lzh_file.namelist()):
                    if self.normalize_path(name) == norm_file_path:
                        return lzh_file.read(name)
                
                # ファイルが見つからない場合
                print(f"LZHファイル内にファイルが見つかりません: {file_path}")
                return None
        except Exception as e:
            print(f"LZHアーカイブ内のファイル読み込みエラー: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_stream(self, path: str) -> Optional[BinaryIO]:
        """
        指定されたパスのファイルのストリームを取得する
        
        LZHファイル内のファイルの場合は、一時的にファイル全体を読み込んでメモリ上のストリームとして返す
        
        Args:
            path: ストリームを取得するファイルのパス
            
        Returns:
            ファイルストリーム。取得できない場合はNone
        """
        try:
            # パスがLZHファイル自体かLZH内のパスかを判定
            lzh_path, internal_path = self._split_path(path)
            
            # LZHファイルの場合は通常のファイルとして扱う
            if not internal_path:
                if os.path.isfile(lzh_path):
                    return open(lzh_path, 'rb')
                return None
                
            # LZHファイル内のファイルの場合、そのファイル内容を取得してメモリストリームとして返す
            file_content = self.read_file(path)
            if file_content is not None:
                import io
                return io.BytesIO(file_content)
                
            return None
        except Exception as e:
            print(f"ファイルストリーム取得エラー: {e}")
            import traceback
            traceback.print_exc()
            return None

