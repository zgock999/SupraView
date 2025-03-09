"""
7-Zipベースのアーカイブハンドラ

7-Zipコマンドラインツールを使用してアーカイブ操作を行うハンドラ
OS非依存で動作し、7-Zipがインストールされている環境で利用可能
"""

import os
import datetime
import tempfile
import shutil
from typing import List, Optional, Dict, Any, BinaryIO, Tuple, Set

from .arc import ArchiveHandler, EntryInfo, EntryType
from .archive_utils import (
    find_executable, parse_7z_list_output, build_structure_from_files, run_command
)


class Archive7zHandler(ArchiveHandler):
    """
    7-Zipを使用したアーカイブハンドラ
    
    OS非依存で7-Zipコマンドラインツールを使用し、様々なアーカイブ形式をサポート
    """
    
    # 7-Zipでサポートされるアーカイブ形式の拡張子リスト
    SUPPORTED_FORMATS = [
        # アーカイブ
        '.7z', '.zip', '.rar', '.tar', '.gz', '.bz2', '.xz', '.wim', 
        '.tgz', '.tbz', '.tbz2', '.txz', 
        # その他
        '.cab', '.arj', '.cpio', '.deb', '.rpm', '.iso'
    ]
    
    # パイプモードをサポートするアーカイブ形式
    PIPE_SUPPORTED_FORMATS = ['.7z', '.gz', '.gzip']
    
    def __init__(self):
        """アーカイブハンドラを初期化する"""
        # 7-Zipの実行パスを検索
        self.seven_zip_path = self._find_7z_executable()
        if not self.seven_zip_path:
            print("Archive7zHandler: 7-Zipが見つかりませんでした。このハンドラは使用できません。")
            self._supported_formats = []
            return
            
        print(f"Archive7zHandler: 7-Zipを検出しました: {self.seven_zip_path}")
        
        # キャッシュディレクトリの設定
        self._cache_dir = os.path.join(tempfile.gettempdir(), "supraview_7z_cache")
        os.makedirs(self._cache_dir, exist_ok=True)
        print(f"Archive7zHandler: キャッシュディレクトリ: {self._cache_dir}")
        
        # キャッシュ
        self.structure_cache: Dict[str, Dict[str, Dict]] = {}
        self.extract_cache: Dict[str, str] = {}
        self._temp_files_cache: Dict[str, str] = {}
        
        # サポートされる形式
        self._supported_formats = self.SUPPORTED_FORMATS
        print(f"Archive7zHandler: サポートされている形式: {', '.join(self._supported_formats)}")
    
    def _find_7z_executable(self) -> str:
        """7-Zipの実行ファイルのパスを検索する（OS非依存）"""
        # まず、環境変数PATHから検索
        path = find_executable('7z')
        if path:
            return path
            
        # 代表的なインストールパスを試す
        if os.name == 'nt':  # Windows
            paths = [
                r"C:\Program Files\7-Zip\7z.exe",
                r"C:\Program Files (x86)\7-Zip\7z.exe"
            ]
            for p in paths:
                if os.path.exists(p):
                    return p
        else:  # Unix系
            paths = [
                "/usr/bin/7z"
                "/usr/local/bin/7z",
                "/opt/local/bin/7z"
            ]
            for p in paths:
                if os.path.exists(p):
                    return p
        
        # 見つからない場合は空文字列
        return ""
    
    @property
    def supported_extensions(self) -> List[str]:
        """このハンドラがサポートするファイル拡張子のリスト"""
        return self._supported_formats
    
    def can_handle(self, path: str) -> bool:
        """
        このハンドラがパスを処理できるか判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            処理可能な場合はTrue、そうでない場合はFalse
        """
        # 7-Zipが利用できない場合
        if not self.seven_zip_path:
            return False
            
        # ファイルが存在しない場合
        if not os.path.isfile(path):
            # アーカイブ内のパスかどうか確認
            archive_path, _ = self._split_path(path)
            if not archive_path:
                return False
            path = archive_path
            
            if not os.path.isfile(path):
                return False
        
        # 拡張子で判定
        _, ext = os.path.splitext(path.lower())
        return ext in self._supported_formats
    
    def can_handle_bytes(self, data: bytes = None, path: str = None) -> bool:
        """
        バイトデータまたはパス指定でバイトデータ解凍が可能かどうかを判定する
        
        Args:
            data: 判定するバイトデータ（省略可能）
            path: 判定するファイルのパス（省略可能、拡張子での判定に使用）
            
        Returns:
            バイトデータから解凍可能な場合はTrue、そうでなければFalse
        """
        # 7-Zipが使用可能でなければFalse
        if not self.seven_zip_path:
            return False
            
        # パスが指定されていれば、その拡張子をチェック
        if path:
            _, ext = os.path.splitext(path.lower())
            return ext in self._supported_formats
        
        # バイトデータが指定されておらず、パスからも判定できない場合はFalse
        if not data:
            return False
            
        # バイトデータの場合は簡易的なシグネチャチェックを行う
        # よく使われるアーカイブ形式のシグネチャ
        signatures = {
            b'PK\x03\x04': '.zip',    # ZIP
            b'Rar!\x1a\x07': '.rar',  # RAR
            b'7z\xbc\xaf\x27\x1c': '.7z',  # 7z
            b'\x1f\x8b': '.gz',        # gzip
            b'BZh': '.bz2',           # bzip2
        }
        
        # 最初の数バイトをチェック
        for sig, ext in signatures.items():
            if data.startswith(sig) and ext in self._supported_formats:
                return True
                
        # 形式が判別できない場合は、とりあえず試させる（オプション）
        return True  # 7-Zipはほとんどのアーカイブ形式を扱えるため、最終的にはTrue
    
    def _extract_archive(self, archive_path: str) -> Optional[str]:
        """
        アーカイブを一時ディレクトリに展開
        
        Args:
            archive_path: アーカイブファイルのパス
            
        Returns:
            展開先ディレクトリのパス、または失敗時にNone
        """
        # キャッシュを確認
        if archive_path in self.extract_cache:
            cache_dir = self.extract_cache[archive_path]
            if os.path.exists(cache_dir):
                return cache_dir
        
        # アーカイブのハッシュに基づく一意的なディレクトリ名を作成
        import hashlib
        archive_hash = hashlib.md5(archive_path.encode('utf-8')).hexdigest()
        extract_dir = os.path.join(self._cache_dir, archive_hash)
        
        # 既に展開されている場合はそのまま返す
        if os.path.exists(extract_dir) and os.listdir(extract_dir):
            self.extract_cache[archive_path] = extract_dir
            return extract_dir
        
        # ディレクトリがなければ作成
        os.makedirs(extract_dir, exist_ok=True)
        
        try:
            # 7-Zipコマンドでアーカイブを展開
            print(f"Archive7zHandler: アーカイブを展開しています: {archive_path}")
            cmd = [self.seven_zip_path, "x", "-y", f"-o{extract_dir}", archive_path]
            retcode, stdout, stderr = run_command(cmd)
            
            if retcode != 0:
                print(f"Archive7zHandler: アーカイブ展開エラー: {stderr}")
                return None
                
            print(f"Archive7zHandler: アーカイブ展開完了: {extract_dir}")
            self.extract_cache[archive_path] = extract_dir
            return extract_dir
        except Exception as e:
            print(f"Archive7zHandler: アーカイブ展開中に例外が発生: {str(e)}")
            return None
    
    def list_entries(self, path: str) -> Optional[List[EntryInfo]]:
        """
        指定したパスのエントリ一覧を取得する
        
        Args:
            path: 一覧を取得するパス
            
        Returns:
            エントリ情報のリスト、またはNone（取得できない場合）
        """
        if not self.seven_zip_path:
            return None
        
        print(f"Archive7zHandler: エントリ一覧を取得: {path}")
        
        # パスがアーカイブ自体かアーカイブ内のパスかを判定
        archive_path, internal_path = self._split_path(path)
        
        if not archive_path or not os.path.isfile(archive_path):
            print(f"Archive7zHandler: 有効なアーカイブファイルが見つかりません: {path}")
            return None
        
        print(f"Archive7zHandler: アーカイブパス: {archive_path}, 内部パス: {internal_path}")
        
        # アーカイブ構造を取得（非展開のファイル一覧取得を優先）
        structure = self._get_archive_structure(archive_path)
        
        # 構造情報から一覧を生成
        if structure:
            return self._get_entries_from_structure(path, structure, internal_path)
            
        # 構造取得に失敗した場合のみ、展開を試みる
        print(f"Archive7zHandler: 構造解析に失敗したためアーカイブ展開を試みます: {archive_path}")
        extract_dir = self._extract_archive(archive_path)
        if not extract_dir:
            print(f"Archive7zHandler: アーカイブの展開に失敗しました: {archive_path}")
            return None
            
        # 展開したディレクトリから直接取得
        return self._get_entries_from_extracted_dir(path, extract_dir, internal_path)
    
    def _get_archive_structure(self, archive_path: str) -> Optional[Dict]:
        """
        アーカイブ内の構造を解析する
        
        Args:
            archive_path: アーカイブファイルのパス
            
        Returns:
            ディレクトリ構造の辞書、またはNone（取得できない場合）
        """
        # キャッシュ確認
        if archive_path in self.structure_cache:
            return self.structure_cache[archive_path]
        
        print(f"Archive7zHandler: アーカイブ構造を解析中: {archive_path}")
        file_list = []
        
        # 7zコマンドでアーカイブの内容を一覧表示
        try:
            # UTF-8エンコードでまず試行
            cmd = [self.seven_zip_path, "-scsUTF-8", "l", archive_path]
            print(f"Archive7zHandler: 7zコマンドを実行: {' '.join(cmd)}")
            
            retcode, stdout, stderr = run_command(cmd)
            
            # 結果を表示
            print(f"Archive7zHandler: 7zコマンド実行結果: コード={retcode}")
            print(f"Archive7zHandler: stderr出力: {stderr[:100]}{'...' if len(stderr) > 100 else ''}")
            
            if retcode == 0:
                # 成功した場合、出力を解析
                parsed_files = parse_7z_list_output(stdout)
                if parsed_files:
                    file_list = parsed_files
                    print(f"Archive7zHandler: 7z出力から {len(file_list)} 件のファイル情報を抽出")
                else:
                    print(f"Archive7zHandler: 7z出力の解析に失敗しました")
            else:
                print(f"Archive7zHandler: 7zコマンド実行エラー: {stderr}")
        except Exception as e:
            print(f"Archive7zHandler: 7z実行例外: {str(e)}")
        
        # それでもファイルリストが得られない場合は失敗
        if not file_list:
            print(f"Archive7zHandler: すべての方法でファイル一覧の取得に失敗しました: {archive_path}")
            return None
        
        # ファイルリストからディレクトリ構造を構築
        # 初期構造を作成
        structure = {'': {'dirs': {}, 'files': {}}}
        
        # ファイルとディレクトリを整理
        for path in file_list:
            # パスの正規化（バックスラッシュをスラッシュに）
            path = path.replace('\\', '/')
            
            # Macの隠しフォルダをスキップ
            if '__MACOSX' in path:
                continue
                
            # ディレクトリか判定
            is_dir = path.endswith('/')
            
            if is_dir:
                # ディレクトリの場合
                dir_path = path
                
                # 全ての親ディレクトリを登録
                parent_path = ''
                parts = dir_path.rstrip('/').split('/')
                
                for i, part in enumerate(parts):
                    if not part:  # 空の部分はスキップ
                        continue
                    
                    # 現在のパスと親を計算
                    current_path = '/'.join(parts[:i+1]) + '/'
                    parent = '/'.join(parts[:i]) + '/' if i > 0 else ''
                    
                    # 親が辞書に存在しなければ追加
                    if parent not in structure:
                        structure[parent] = {'dirs': {}, 'files': {}}
                    
                    # 親にこのディレクトリを追加
                    structure[parent]['dirs'][part] = True
                    
                    # 現在のディレクトリが辞書に存在しなければ追加
                    if current_path not in structure:
                        structure[current_path] = {'dirs': {}, 'files': {}}
            else:
                # ファイルの場合
                file_dir = os.path.dirname(path)
                if file_dir:
                    file_dir += '/'
                file_name = os.path.basename(path)
                
                # 親ディレクトリが存在しなければ追加
                if file_dir not in structure:
                    structure[file_dir] = {'dirs': {}, 'files': {}}
                    
                    # 親ディレクトリの階層を作成
                    parent = ''
                    parts = file_dir.rstrip('/').split('/')
                    
                    for i, part in enumerate(parts):
                        if not part:  # 空の部分はスキップ
                            continue
                            
                        # 現在のパスと親を計算
                        current_path = '/'.join(parts[:i+1]) + '/'
                        current_parent = '/'.join(parts[:i]) + '/' if i > 0 else ''
                        
                        # 親が辞書に存在しなければ追加
                        if current_parent not in structure:
                            structure[current_parent] = {'dirs': {}, 'files': {}}
                        
                        # 親にこのディレクトリを追加
                        structure[current_parent]['dirs'][part] = True
                        
                        # 現在のディレクトリが辞書に存在しなければ追加
                        if current_path not in structure:
                            structure[current_path] = {'dirs': {}, 'files': {}}
                
                # ファイルを親ディレクトリに追加
                structure[file_dir]['files'][file_name] = {'size': 0}
        
        # キャッシュに格納
        self.structure_cache[archive_path] = structure
        return structure

    def _get_entries_from_structure(self, original_path: str, structure: Dict, internal_path: str) -> List[EntryInfo]:
        """
        構造情報からエントリ情報を取得する
        
        Args:
            original_path: 元のパス
            structure: ディレクトリ構造辞書
            internal_path: アーカイブ内の相対パス
        
        Returns:
            エントリ情報のリスト
        """
        result_entries = []
        
        # 要求されたパスの正規化
        norm_internal_path = internal_path
        if norm_internal_path and not norm_internal_path.endswith('/'):
            norm_internal_path += '/'
        
        # 内部パスがアーカイブファイルを指している場合は特別処理
        _, ext = os.path.splitext(internal_path.lower())
        if ext in self._supported_formats and not internal_path.endswith('/'):
            # アーカイブファイルそのものとして処理
            # ファイル情報を検索
            dir_path = os.path.dirname(internal_path)
            if dir_path:
                dir_path += '/'
            file_name = os.path.basename(internal_path)
            
            # 構造から該当ファイルを探す（正確なパスでなくても名前で検出）
            if dir_path in structure and file_name in structure[dir_path]['files']:
                # ファイル情報を取得
                file_info = structure[dir_path]['files'][file_name]
                
                # アーカイブファイルとしてエントリを作成
                result_entries.append(EntryInfo(
                    name=file_name,
                    path=original_path,
                    size=file_info.get('size', 0),
                    modified_time=file_info.get('mtime', None),
                    type=EntryType.ARCHIVE
                ))
                
                print(f"Archive7zHandler: ネストされたアーカイブファイル {file_name} を検出")
                return result_entries
            
            # ファイルが見つからない場合もあるので、部分一致で探索
            for dir_key in structure.keys():
                if dir_key.endswith('/'):
                    for file_key, file_info in structure[dir_key]['files'].items():
                        if file_key == file_name or file_key.endswith('/' + file_name):
                            # ファイルが見つかった
                            result_entries.append(EntryInfo(
                                name=file_name,
                                path=original_path,
                                size=file_info.get('size', 0),
                                modified_time=file_info.get('mtime', None),
                                type=EntryType.ARCHIVE
                            ))
                            
                            print(f"Archive7zHandler: ファイル名部分一致でネストされたアーカイブ {file_name} を検出")
                            return result_entries
        
        # 指定されたディレクトリが存在するか確認
        if norm_internal_path and norm_internal_path not in structure:
            print(f"Archive7zHandler: 要求されたパス '{norm_internal_path}' がアーカイブ内に存在しません")
            print(f"  アーカイブ内のパス: {', '.join(list(structure.keys())[:10])}")
            
            # パスが直接マッチしない場合、部分一致を試みる
            best_match = ""
            for struct_path in structure.keys():
                # 完全に含まれる場合
                if norm_internal_path.rstrip('/') in struct_path:
                    if not best_match or len(struct_path) < len(best_match):
                        best_match = struct_path
            
            if best_match:
                print(f"Archive7zHandler: 部分一致するパスを見つけました: {best_match}")
                internal_path = best_match
                norm_internal_path = best_match
            else:
                return []
        
        if not norm_internal_path:
            norm_internal_path = ''  # ルートディレクトリを参照
        
        # このディレクトリの子（ファイルとサブフォルダ）を取得
        try:
            current_dir = structure[norm_internal_path]
        except KeyError:
            print(f"Archive7zHandler: パス '{norm_internal_path}' に対応するディレクトリが構造内に見つかりません")
            print(f"  構造内のパス: {', '.join(list(structure.keys())[:10])}")
            return []
        
        # サブディレクトリをリストに追加
        for dir_name in current_dir['dirs']:
            dir_path = os.path.join(original_path, dir_name).replace('\\', '/')
            
            # 空のディレクトリ名はスキップ
            if not dir_name:
                continue
                
            result_entries.append(EntryInfo(
                name=dir_name,
                path=dir_path,
                size=0,
                modified_time=None,
                type=EntryType.DIRECTORY
            ))
        
        # ファイルをリストに追加
        for file_name, info in current_dir['files'].items():
            # 空のファイル名はスキップ
            if not file_name:
                continue
                
            file_path = os.path.join(original_path, file_name).replace('\\', '/')
            
            # ファイルの拡張子をチェックしてアーカイブなら特別に処理
            _, ext = os.path.splitext(file_name.lower())
            entry_type = EntryType.ARCHIVE if ext in self._supported_formats else EntryType.FILE
            
            result_entries.append(EntryInfo(
                name=file_name,
                path=file_path,
                size=info.get('size', 0),
                modified_time=info.get('mtime', None),
                type=entry_type
            ))
        
        print(f"Archive7zHandler: アーカイブ構造から {len(result_entries)} エントリを取得しました")
        # デバッグ情報：どのようなエントリが含まれているかを出力
        for entry in result_entries[:5]:  # 最初の5つだけ表示
            print(f"  エントリ: 名前={entry.name}, パス={entry.path}, タイプ={entry.type}")
        
        return result_entries

    def _get_entries_from_extracted_dir(self, original_path: str, extract_dir: str, internal_path: str) -> List[EntryInfo]:
        """
        展開されたディレクトリからエントリを取得する
        
        Args:
            original_path: 元のリクエストパス 
            extract_dir: 展開されたディレクトリのパス
            internal_path: アーカイブ内の相対パス
            
        Returns:
            エントリ情報のリスト
        """
        result_entries = []
        
        # 内部パスからファイルシステム上のパスを構築
        target_dir = os.path.join(extract_dir, internal_path.replace('/', os.sep))
        
        # ディレクトリが存在するか確認
        if not os.path.exists(target_dir):
            print(f"Archive7zHandler: パス '{target_dir}' が存在しません")
            return []
        
        if not os.path.isdir(target_dir):
            print(f"Archive7zHandler: パス '{target_dir}' はディレクトリではありません")
            return []
        
        # ディレクトリのエントリを取得
        try:
            for entry in os.scandir(target_dir):
                # エントリタイプを判定
                if entry.is_dir():
                    entry_type = EntryType.DIRECTORY
                    size = 0
                    mtime = None
                else:
                    # ファイルの拡張子をチェック
                    _, ext = os.path.splitext(entry.name.lower())
                    entry_type = EntryType.ARCHIVE if ext in self._supported_formats else EntryType.FILE
                    
                    # ファイル情報を取得
                    stat_info = entry.stat()
                    size = stat_info.st_size
                    mtime = datetime.datetime.fromtimestamp(stat_info.st_mtime)
                
                # パスを構築
                if internal_path:
                    rel_path = os.path.join(internal_path, entry.name)
                else:
                    rel_path = entry.name
                
                entry_path = os.path.join(original_path, entry.name).replace('\\', '/')
                
                # エントリを作成
                result_entries.append(EntryInfo(
                    name=entry.name,
                    path=entry_path,
                    size=size,
                    modified_time=mtime,
                    type=entry_type
                ))
                
            print(f"Archive7zHandler: 展開ディレクトリから {len(result_entries)} エントリを取得しました")
            return result_entries
        except Exception as e:
            print(f"Archive7zHandler: 展開ディレクトリからのエントリ取得エラー: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定したパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するパス
            
        Returns:
            エントリ情報、またはNone（取得できない場合）
        """
        if not self.seven_zip_path:
            return None
        
        print(f"Archive7zHandler: エントリ情報を取得: {path}")
        
        # パスがアーカイブ自体かアーカイブ内のパスかを判定
        archive_path, internal_path = self._split_path(path)
        
        # アーカイブファイル自体の場合
        if not internal_path:
            if not os.path.isfile(archive_path):
                return None
            
            # アーカイブファイルの情報を返す
            file_stat = os.stat(archive_path)
            return EntryInfo(
                name=os.path.basename(archive_path),
                path=archive_path,
                size=file_stat.st_size,
                modified_time=datetime.datetime.fromtimestamp(file_stat.st_mtime),
                type=EntryType.ARCHIVE
            )
        
        # アーカイブ内のエントリの情報を取得
        # アーカイブ構造を取得
        structure = self._get_archive_structure(archive_path)
        
        if structure:
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
                    
                    # ファイルの拡張子をチェックしてアーカイブなら特別に処理
                    _, ext = os.path.splitext(file_name.lower())
                    entry_type = EntryType.ARCHIVE if ext in self._supported_formats else EntryType.FILE
                    
                    return EntryInfo(
                        name=file_name,
                        path=path,
                        size=file_info.get('size', 0),
                        modified_time=file_info.get('mtime', None),
                        type=entry_type
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
        
        # 構造から情報が得られなかった場合のみアーカイブを展開
        print(f"Archive7zHandler: 構造から情報が得られなかったためアーカイブ展開を試みます: {archive_path}")
        extract_dir = self._extract_archive(archive_path)
        if not extract_dir:
            print(f"Archive7zHandler: アーカイブの展開に失敗しました: {archive_path}")
            return None
        
        # 展開されたファイルシステムから情報を取得
        file_path = os.path.join(extract_dir, internal_path.replace('/', os.sep))
        
        if os.path.exists(file_path):
            if os.path.isdir(file_path):
                return EntryInfo(
                    name=os.path.basename(internal_path),
                    path=path,
                    size=0,
                    modified_time=datetime.datetime.fromtimestamp(os.path.getmtime(file_path)),
                    type=EntryType.DIRECTORY
                )
            elif os.path.isfile(file_path):
                stat_info = os.stat(file_path)
                
                # ファイルの拡張子をチェックしてアーカイブなら特別に処理
                _, ext = os.path.splitext(file_path.lower())
                entry_type = EntryType.ARCHIVE if ext in self._supported_formats else EntryType.FILE
                
                return EntryInfo(
                    name=os.path.basename(internal_path),
                    path=path,
                    size=stat_info.st_size,
                    modified_time=datetime.datetime.fromtimestamp(stat_info.st_mtime),
                    type=entry_type
                )
                
        # 見つからなかった
        return None

    def read_file(self, path: str) -> Optional[bytes]:
        """
        指定したパスのファイルを読み込む
        
        Args:
            path: 読み込むファイルのパス
            
        Returns:
            ファイルの内容、またはNone（読み込めない場合）
        """
        if not self.seven_zip_path:
            return None
        
        print(f"Archive7zHandler: ファイル読み込み: {path}")
        
        # パスがアーカイブ自体かアーカイブ内のパスかを判定
        archive_path, internal_path = self._split_path(path)
        
        # アーカイブファイル自体なら読み込めない
        if not internal_path:
            return None
        
        # この部分を変更: まとめて処理するreadArchiveFile関数に委譲
        return self.read_archive_file(archive_path, internal_path)

    def read_archive_file(self, archive_path: str, file_path: str) -> Optional[bytes]:
        """
        アーカイブファイル内のファイルの内容を読み込む
        
        Args:
            archive_path: アーカイブファイルのパス
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容（バイト配列）。読み込みに失敗した場合はNone
        """
        if not self.seven_zip_path:
            return None
        
        print(f"Archive7zHandler: アーカイブ内ファイル読み込み: {archive_path} -> {file_path}")
        
        # 直接7zコマンドでファイルを抽出できるか試みる
        try:
            # パスの正規化
            file_path_for_cmd = file_path.replace('\\', '/')
            
            cmd = [self.seven_zip_path, "e", "-so", archive_path, file_path_for_cmd]
            print(f"Archive7zHandler: 7zで直接ファイルを抽出: {file_path_for_cmd}")
            print(f"実行コマンド: {' '.join(cmd)}")
            
            retcode, stdout, stderr = run_command(cmd)
            
            if retcode == 0 and stdout:
                # stdout が文字列なら、バイト配列に変換
                if isinstance(stdout, str):
                    stdout = stdout.encode('utf-8')
                
                print(f"Archive7zHandler: 直接抽出に成功: {len(stdout)}バイト")
                return stdout
            else:
                print(f"Archive7zHandler: 直接抽出でエラー: {stderr}")
        except Exception as e:
            print(f"Archive7zHandler: 直接抽出で例外発生: {str(e)}")
        
        # 直接抽出が失敗した場合は展開してから読み込む
        extract_dir = self._extract_archive(archive_path)
        if not extract_dir:
            print(f"Archive7zHandler: アーカイブの展開に失敗しました: {archive_path}")
            return None
                
        # ファイルパスを構築
        file_path_norm = file_path.replace('/', os.sep)
        file_path_abs = os.path.join(extract_dir, file_path_norm)
        
        # ファイルが存在するか確認
        if not os.path.isfile(file_path_abs):
            print(f"Archive7zHandler: ファイルが見つかりません: {file_path_abs}")
            return None
                
        # ファイルを読み込む
        try:
            with open(file_path_abs, 'rb') as f:
                content = f.read()
            
            print(f"Archive7zHandler: アーカイブ内ファイル読み込み完了: {archive_path} -> {file_path}, {len(content)}バイト")
            return content
        except Exception as e:
            print(f"Archive7zHandler: ファイル読み込みエラー: {str(e)}")
            return None

    def get_stream(self, path: str) -> Optional[BinaryIO]:
        """
        指定されたパスのファイルのストリームを取得する
        
        Args:
            path: ストリームを取得するファイルのパス
            
        Returns:
            ファイルストリーム。取得できない場合はNone
        """
        if not self.seven_zip_path:
            return None
        
        print(f"Archive7zHandler: ファイルストリーム取得: {path}")
            
        # パスがアーカイブファイル自体かアーカイブ内のパスかを判定
        archive_path, internal_path = self._split_path(path)
        
        # アーカイブファイルの場合は通常のファイルとして扱う
        if not internal_path:
            if os.path.isfile(archive_path):
                return open(archive_path, 'rb')
            return None
        
        # アーカイブ内のファイルの場合、まず内容を読み込んでメモリストリームとして返す
        try:
            content = self.read_archive_file(archive_path, internal_path)
            if content is not None:
                import io
                return io.BytesIO(content)
        except Exception as e:
            print(f"Archive7zHandler: メモリストリーム作成エラー: {str(e)}")
                
        # 読み込みが失敗した場合はアーカイブを展開
        extract_dir = self._extract_archive(archive_path)
        if not extract_dir:
            print(f"Archive7zHandler: アーカイブの展開に失敗しました: {archive_path}")
            return None
                
        # ファイルパスを構築
        file_path = os.path.join(extract_dir, internal_path.replace('/', os.sep))
        
        # ファイルが存在するか確認
        if not os.path.isfile(file_path):
            print(f"Archive7zHandler: ファイルが見つかりません: {file_path}")
            return None
                
        # ファイルをストリームとして返す
        return open(file_path, 'rb')

    def _split_path(self, path: str) -> Tuple[str, str]:
        """
        パスをアーカイブファイルのパスと内部パスに分割する
        
        Args:
            path: 分割するパス
            
        Returns:
            (アーカイブファイルのパス, 内部パス) のタプル
        """
        # パスが異常に長い場合は処理を中止
        if len(path) > 2000:
            print(f"Archive7zHandler: パスが異常に長いため分割を中止: {len(path)} 文字")
            return "", ""
            
        # パスの正規化 (バックスラッシュをスラッシュに変換)
        norm_path = self.normalize_path(path)
        
        # アーカイブファイル自体かどうか確認（これは高速判定）
        if os.path.isfile(norm_path):
            try:
                # 拡張子のチェック（高速）
                _, ext = os.path.splitext(norm_path.lower())
                if ext in self._supported_formats:
                    if self.can_handle(norm_path):
                        # パス自体がアーカイブファイル
                        return norm_path, ""
            except:
                pass
        
        # 非再帰的にアーカイブファイルを検索
        # パスの先頭から探索を開始
        components = norm_path.split('/')
        test_path = ''
        for i in range(len(components)):
            # 現在のコンポーネントを追加
            if test_path:
                test_path += '/'
            test_path += components[i]
            
            # これがアーカイブファイルかどうか確認（存在することを確認）
            if os.path.isfile(test_path):
                # 拡張子と処理可能性をチェック
                _, ext = os.path.splitext(test_path.lower())
                if ext in self._supported_formats and self.can_handle(test_path):
                    # アーカイブファイルを発見
                    internal_path = '/'.join(components[i+1:])
                    print(f"Archive7zHandler: アーカイブを検出: {test_path}")
                    return test_path, internal_path
                    
        # アーカイブファイルが見つからなかった
        print(f"Archive7zHandler: アーカイブファイルが見つかりません: {path[:100]}{'...' if len(path) > 100 else ''}")
        return "", ""

    def _get_files_from_directory(self, base_dir: str, prefix: str = "") -> List[str]:
        """
        ディレクトリ内のファイル一覧を再帰的に取得
        
        Args:
            base_dir: 基準ディレクトリ
            prefix: パスプレフィックス
            
        Returns:
            ファイルパスのリスト
        """
        result = []
        
        # ディレクトリ内のエントリを取得
        for entry in os.scandir(os.path.join(base_dir, prefix)):
            rel_path = os.path.join(prefix, entry.name).replace('\\', '/')
            
            if entry.is_file():
                result.append(rel_path)
            elif entry.is_dir():
                # ディレクトリとして追加
                result.append(rel_path + '/')
                # サブディレクトリを再帰的に処理
                result.extend(self._get_files_from_directory(base_dir, rel_path))
        
        return result

    def get_parent_path(self, path: str) -> str:
        """
        指定したパスの親ディレクトリのパスを取得する
        
        Args:
            path: 親ディレクトリを取得するパス
            
        Returns:
            親ディレクトリのパス。親がない場合は空文字列
        """
        # パスがアーカイブ自体かアーカイブ内のパスかを判定
        archive_path, internal_path = self._split_path(path)
        
        # internal_pathが空ならアーカイブファイル自体なので、その親を返す
        if not internal_path:
            return os.path.dirname(archive_path)
        
        # アーカイブ内のパスの親を計算
        parent_dir = os.path.dirname(internal_path.rstrip('/'))
        
        # ルートの場合はアーカイブファイル自体を返す
        if not parent_dir:
            return archive_path
            
        # 親ディレクトリのパスを作成して返す
        return self._join_paths(archive_path, parent_dir)

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

    def list_entries_from_bytes(self, archive_data: bytes, path: str = "") -> List[EntryInfo]:
        """
        メモリ上のアーカイブデータからエントリのリストを返す
        
        Args:
            archive_data: アーカイブデータのバイト配列
            path: アーカイブ内のパス（デフォルトはルート）
            
        Returns:
            エントリ情報のリスト
        """
        try:
            print(f"Archive7zHandler: メモリ上のアーカイブデータ ({len(archive_data)} バイト) からエントリリストを取得")
            
            # アーカイブの拡張子を推測
            ext = '.7z'  # デフォルト
            if path:
                _, ext = os.path.splitext(path.lower())
            
            # パイプモードをサポートするか確認（.7z, .gz, .gzipのみサポート）
            use_pipe_mode = ext in self.PIPE_SUPPORTED_FORMATS
            file_list = []
            
            if use_pipe_mode:
                # パイプモード（標準入力から処理）を試す
                try:
                    import subprocess
                    
                    cmd = [self.seven_zip_path, "-scsUTF-8", "l", "-si"]
                    print(f"Archive7zHandler: パイプモードで7zコマンドを実行: {' '.join(cmd)}")
                    
                    p = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    
                    stdout_data, stderr_data = p.communicate(input=archive_data)
                    
                    if p.returncode == 0:
                        try:
                            stdout_text = stdout_data.decode('utf-8', errors='replace')
                        except UnicodeDecodeError:
                            stdout_text = stdout_data.decode('cp932', errors='replace')
                            
                        file_list = parse_7z_list_output(stdout_text)
                        if file_list:
                            print(f"Archive7zHandler: パイプモードで {len(file_list)} 件のファイル情報を抽出")
                        else:
                            print(f"Archive7zHandler: パイプモードでの解析に失敗")
                    else:
                        print(f"Archive7zHandler: パイプモードでコマンド実行エラー: {p.returncode}")
                        print(f"  エラー: {stderr_data.decode('utf-8', errors='replace')}")
                except Exception as e:
                    print(f"Archive7zHandler: パイプモードでの例外: {str(e)}")
            else:
                # パイプモード非対応の場合はメッセージを出力
                print(f"Archive7zHandler: 拡張子 '{ext}' はパイプモードをサポートしていないため一時ファイルモードを使用します")
            
            # パイプモードが失敗したか、対象外の形式の場合は一時ファイルを使用
            if not file_list:
                print(f"Archive7zHandler: 一時ファイルモードを使用します")
                temp_file = None
                
                try:
                    # 一時ファイルの作成
                    temp_file = self.save_to_temp_file(archive_data, ext)
                    if not temp_file:
                        print(f"Archive7zHandler: 一時ファイルの作成に失敗")
                        return []
                    
                    # 一時ファイルでコマンドを実行
                    cmd = [self.seven_zip_path, "-scsUTF-8", "l", temp_file]
                    print(f"Archive7zHandler: 一時ファイルで7zコマンドを実行: {' '.join(cmd)}")
                    
                    retcode, stdout, stderr = run_command(cmd)
                    
                    if retcode == 0:
                        file_list = parse_7z_list_output(stdout)
                        print(f"Archive7zHandler: 一時ファイルから {len(file_list)} 件のファイル情報を抽出")
                    else:
                        print(f"Archive7zHandler: 一時ファイルでコマンド実行エラー: {retcode}")
                        print(f"  エラー: {stderr}")
                finally:
                    # キャッシュのために保持しない一時ファイルの場合は削除
                    if temp_file and not getattr(self, '_keep_temp_files', False):
                        try:
                            os.unlink(temp_file)
                            print(f"Archive7zHandler: 一時ファイルを削除: {temp_file}")
                        except:
                            pass
            
            if not file_list:
                print(f"Archive7zHandler: ファイル一覧の取得に失敗しました")
                return []
            
            # ファイルリストからエントリリストを構築
            return self._build_entries_from_file_list(file_list, path)
            
        except Exception as e:
            print(f"Archive7zHandler.list_entries_from_bytes エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def _build_entries_from_file_list(self, file_list: List[str], path: str) -> List[EntryInfo]:
        """
        ファイルリストからエントリリストを構築する
    
        Args:
            file_list: ファイルパスのリスト
            path: 対象のパス
            
        Returns:
            エントリ情報のリスト
        """
        # ディレクトリ構造を構築
        structure = {'': {'dirs': set(), 'files': set()}}
        
        # ファイルリストを処理
        for file_path in file_list:
            is_dir = file_path.endswith('/')
            
            if is_dir:
                # ディレクトリの場合
                dir_path = file_path
                parent_path = ''
                parts = dir_path.rstrip('/').split('/')
                
                for i, part in enumerate(parts):
                    if not part:  # 空の部分はスキップ
                        continue
                    
                    # 現在のパスと親を計算
                    current_path = '/'.join(parts[:i+1]) + '/'
                    parent = '/'.join(parts[:i]) + '/' if i > 0 else ''
                    
                    # 親が辞書に存在しなければ追加
                    if parent not in structure:
                        structure[parent] = {'dirs': set(), 'files': set()}
                    
                    # 親にこのディレクトリを追加
                    structure[parent]['dirs'].add(part)
                    
                    # 現在のディレクトリが辞書に存在しなければ追加
                    if current_path not in structure:
                        structure[current_path] = {'dirs': set(), 'files': set()}
            else:
                # ファイルの場合
                file_dir = os.path.dirname(file_path)
                if file_dir:
                    file_dir += '/'
                file_name = os.path.basename(file_path)
                
                # 親ディレクトリが存在しなければ追加
                if file_dir not in structure:
                    structure[file_dir] = {'dirs': set(), 'files': set()}
                    
                    # 親ディレクトリの階層を作成
                    parent = ''
                    parts = file_dir.rstrip('/').split('/')
                    
                    for i, part in enumerate(parts):
                        if not part:  # 空の部分はスキップ
                            continue
                            
                        # 現在のパスと親を計算
                        current_path = '/'.join(parts[:i+1]) + '/'
                        current_parent = '/'.join(parts[:i]) + '/' if i > 0 else ''
                        
                        # 親が辞書に存在しなければ追加
                        if current_parent not in structure:
                            structure[current_parent] = {'dirs': set(), 'files': set()}
                        
                        # 親にこのディレクトリを追加
                        structure[current_parent]['dirs'].add(part)
                        
                        # 現在のディレクトリが辞書に存在しなければ追加
                        if current_path not in structure:
                            structure[current_path] = {'dirs': set(), 'files': set()}
                
                # ファイルを親ディレクトリに追加
                structure[file_dir]['files'].add(file_name)
        
        # 指定したパスがルート以外の場合、そのディレクトリ内のエントリだけを返す
        target_path = path if path.endswith('/') or not path else path + '/'
        
        # エントリリストを作成
        entries = []
        
        # パスが存在するかチェック
        if target_path in structure:
            # ディレクトリの内容を追加
            for dir_name in structure[target_path]['dirs']:
                entries.append(EntryInfo(
                    name=dir_name,
                    path=os.path.join(path, dir_name).replace('\\', '/'),
                    size=0,
                    modified_time=None,
                    type=EntryType.DIRECTORY
                ))
            
            # ファイルを追加
            for file_name in structure[target_path]['files']:
                # ファイルの拡張子をチェックしてアーカイブなら特別に処理
                _, ext = os.path.splitext(file_name.lower())
                entry_type = EntryType.ARCHIVE if ext in self._supported_formats else EntryType.FILE
                
                entries.append(EntryInfo(
                    name=file_name,
                    path=os.path.join(path, file_name).replace('\\', '/'),
                    size=0,  # サイズ情報は取得できない
                    modified_time=None,
                    type=entry_type
                ))
        else:
            print(f"Archive7zHandler: 指定されたパス '{target_path}' が見つかりません")
        
        print(f"Archive7zHandler: {len(entries)} エントリを返します")
        return entries

    def read_file_from_bytes(self, archive_data: bytes, file_path: str) -> Optional[bytes]:
        """
        メモリ上のアーカイブデータから特定のファイルを読み込む
        
        Args:
            archive_data: アーカイブデータのバイト配列
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        try:
            print(f"Archive7zHandler: メモリ上のアーカイブデータからファイル読み込み: {file_path}")
            
            # アーカイブの拡張子を推測
            ext = '.7z'  # デフォルト
            if path := getattr(self, '_last_archive_path', ''):
                _, ext = os.path.splitext(path.lower())
            
            # 一時ファイルの作成
            temp_file = None
            try:
                # 一時ファイルの作成（元の拡張子を維持）
                temp_file = self.save_to_temp_file(archive_data, ext)
                if not temp_file:
                    print(f"Archive7zHandler: 一時ファイルの作成に失敗")
                    return None
                
                # パスの正規化（スラッシュに統一）
                file_path_for_cmd = file_path.replace('\\', '/')
                
                # 7-Zipでファイル抽出（標準出力に直接出力）
                cmd = [self.seven_zip_path, "e", "-so", temp_file, file_path_for_cmd]
                print(f"Archive7zHandler: ファイルを抽出: {' '.join(cmd)}")
                
                retcode, stdout, stderr = run_command(cmd)
                
                if retcode == 0 and stdout:
                    # 成功した場合はバイト配列として返す
                    if isinstance(stdout, bytes):
                        content = stdout
                    else:
                        content = stdout.encode('utf-8')
                    
                    print(f"Archive7zHandler: ファイル抽出に成功: {len(content)} バイト")
                    return content
                
                print(f"Archive7zHandler: ファイル抽出エラー: {stderr}")
                
                # 展開を試す（標準出力ではなく実ファイルに）
                extract_dir = tempfile.mkdtemp(prefix="7z_extract_")
                try:
                    cmd = [self.seven_zip_path, "e", "-y", f"-o{extract_dir}", temp_file, file_path_for_cmd]
                    print(f"Archive7zHandler: 通常抽出を試みる: {' '.join(cmd)}")
                    
                    retcode, stdout, stderr = run_command(cmd)
                    
                    if retcode == 0:
                        # 抽出されたファイルを探す
                        file_name = os.path.basename(file_path)
                        extracted_file = os.path.join(extract_dir, file_name)
                        
                        if os.path.exists(extracted_file):
                            with open(extracted_file, 'rb') as f:
                                content = f.read()
                            print(f"Archive7zHandler: ファイル読み込みに成功: {len(content)} バイト")
                            return content
                    
                    print(f"Archive7zHandler: 通常抽出も失敗: {stderr}")
                finally:
                    # 抽出ディレクトリを削除
                    try:
                        shutil.rmtree(extract_dir, ignore_errors=True)
                    except:
                        pass
                
                return None
            
            finally:
                # 一時ファイルを削除
                if temp_file and not getattr(self, '_keep_temp_files', False):
                    try:
                        os.unlink(temp_file)
                        print(f"Archive7zHandler: 一時ファイルを削除: {temp_file}")
                    except:
                        pass
                    
        except Exception as e:
            print(f"Archive7zHandler.read_file_from_bytes エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def save_to_temp_file(self, content: bytes, extension: str) -> Optional[str]:
        """
        バイナリコンテンツを一時ファイルに保存する
        
        Args:
            content: 保存するコンテンツ
            extension: ファイルの拡張子（.rarなど）
            
        Returns:
            一時ファイルパス、または失敗時はNone
        """
        import tempfile
        import hashlib
        import time
        import os
        import random
        
        # 拡張子の正規化
        if not extension.startswith('.'):
            extension = '.' + extension
        
        # 拡張子が不明な場合はデフォルトを使用
        if extension not in self._supported_formats:
            extension = '.bin'
        
        # 一時ディレクトリ
        temp_dir = os.path.join(tempfile.gettempdir(), "supraview_temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # ファイル名の生成
        timestamp = int(time.time() * 1000)  # ミリ秒まで
        random_part = os.urandom(4).hex()  # ランダム要素
        content_hash = hashlib.md5(content[:4096] if len(content) > 4096 else content).hexdigest()
        file_name = f"supraview_{content_hash}_{timestamp}_{random_part}{extension}"
        temp_path = os.path.join(temp_dir, file_name)
        
        print(f"Archive7zHandler: 一時ファイル作成: {temp_path}")
        
        try:
            # 既存ファイルを削除（念のため）
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    print(f"Archive7zHandler: 既存ファイル削除エラー: {e}")
                    # 別の名前を試す
                    random_suffix = ''.join(random.choices('0123456789abcdef', k=8))
                    file_name = f"supraview_{content_hash}_{timestamp}_{random_suffix}{extension}"
                    temp_path = os.path.join(temp_dir, file_name)
            
            # ファイルへ書き込み
            with open(temp_path, 'wb') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # 確実にディスクに書き込む
            
            # ファイルサイズ検証
            actual_size = os.path.getsize(temp_path)
            if actual_size != len(content):
                print(f"Archive7zHandler: 書き込み検証エラー: サイズ不一致 ({actual_size} != {len(content)})")
                return None
                
            print(f"Archive7zHandler: 一時ファイル作成に成功: {temp_path} ({actual_size} バイト)")
            return temp_path
            
        except Exception as e:
            print(f"Archive7zHandler: 一時ファイル作成エラー: {e}")
            import traceback
            traceback.print_exc()
            return None

    def cleanup_temp_files(self):
        """
        キャッシュされた一時ファイルをすべて削除する
        """
        if hasattr(self, '_temp_files_cache'):
            print(f"Archive7zHandler: {len(self._temp_files_cache)} 個の一時ファイルを削除します")
            for key, temp_file in list(self._temp_files_cache.items()):
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                        print(f"Archive7zHandler: 一時ファイルを削除: {temp_file}")
                except Exception as e:
                    print(f"Archive7zHandler: 一時ファイル削除エラー: {e}")
            
            # キャッシュをクリア
            self._temp_files_cache = {}

    def list_all_entries(self, path: str) -> List[EntryInfo]:
        """
        指定したパスのアーカイブ内のすべてのエントリを再帰的に取得する（フィルタリングなし）
        
        Args:
            path: アーカイブファイルのパス
            
        Returns:
            アーカイブ内のすべてのエントリのリスト
        """
        # パスが7zファイル自体かどうかを確認
        if not os.path.isfile(path) or not self.can_handle(path):
            print(f"Archive7zHandler: 有効な7zファイルではありません: {path}")
            return []
        
        # すべてのファイルを取得
        try:
            # 7z コマンドでアーカイブ内の全てのファイルを一覧表示
            cmd = [self.seven_zip_path, "l", "-r", "-slt", path]
            stdout, stderr = run_command(cmd)
            
            if stderr:
                print(f"Archive7zHandler: コマンド実行エラー: {stderr}")
                return []
            
            # 出力を解析してファイルリストを取得
            file_list = parse_7z_list_output(stdout)
            
            # すべてのエントリをEntryInfoに変換
            all_entries = self._build_entries_from_file_list(file_list, path)
            print(f"Archive7zHandler: {len(all_entries)} エントリを取得しました")
            
            return all_entries
            
        except Exception as e:
            print(f"Archive7zHandler: エントリ一覧取得中にエラー: {e}")
            import traceback
            traceback.print_exc()
            return []

    def list_all_entries_from_bytes(self, archive_data: bytes, path: str = "") -> List[EntryInfo]:
        """
        メモリ上のアーカイブデータからすべてのエントリを再帰的に取得する（フィルタリングなし）
        
        Args:
            archive_data: アーカイブデータのバイト配列
            path: ベースパス（結果のEntryInfoに反映される）
            
        Returns:
            アーカイブ内のすべてのエントリのリスト
        """
        # 7-Zipが利用可能か確認
        if not self.seven_zip_path:
            print(f"Archive7zHandler: 7-Zipが利用できません")
            return []
        
        # サポートされている形式かチェック
        if not self.can_handle_bytes(archive_data):
            print(f"Archive7zHandler: サポートされていないバイトデータです")
            return []
        
        print(f"Archive7zHandler: メモリデータからすべてのエントリを取得中 ({len(archive_data)} バイト)")
        
        # 一時ファイルに保存して処理
        temp_file = self.save_to_temp_file(archive_data, '.7z')
        if not temp_file:
            print(f"Archive7zHandler: 一時ファイル作成に失敗しました")
            return []
        
        try:
            # 一時ファイルからすべてのエントリを取得
            return self.list_all_entries(temp_file)
        finally:
            # 一時ファイルをクリーンアップ
            self.cleanup_temp_file(temp_file)





