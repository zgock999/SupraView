"""
ZIPアーカイブハンドラ

ZIPアーカイブファイルへのアクセスを提供するハンドラ
"""
import os
import io
import zipfile
import traceback
import datetime
from typing import List, Optional, Dict, Any, BinaryIO, Tuple, Set, Union

from arc.arc import EntryInfo, EntryType
from .handler import ArchiveHandler  # 重複import修正


class ZipHandler(ArchiveHandler):
    """
    ZIPアーカイブハンドラ
    
    ZIPアーカイブファイルの内容にアクセスするためのハンドラ実装
    """
    
    def __init__(self):
        """ZIPアーカイブハンドラを初期化する"""
        super().__init__()  # 親クラス初期化を追加
        # ZIP構造キャッシュの追加
        self.structure_cache: Dict[str, Dict[str, Dict]] = {}
        
    @property
    def supported_extensions(self) -> List[str]:
        """このハンドラがサポートするファイル拡張子のリスト"""
        return ['.zip', '.cbz', '.epub']
    
    def can_handle(self, path: str) -> bool:
        """
        このハンドラがパスを処理できるか判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            処理可能な場合はTrue、そうでない場合はFalse
        """
        # 正規化したパスを使用
        norm_path = path.replace('\\', '/')
        
        # パスの末尾にスラッシュがある場合は削除して判定する
        if norm_path.endswith('/'):
            norm_path = norm_path[:-1]
           
        # 拡張子のみでチェック
        _, ext = os.path.splitext(norm_path.lower())
        return ext in self.supported_extensions
    
    def can_handle_bytes(self, data: bytes = None, path: str = None) -> bool:
        """
        バイトデータまたはパス指定でバイトデータ解凍が可能かどうかを判定する
        
        Args:
            data: 判定するバイトデータ（省略可能）
            path: 判定するファイルのパス（省略可能、拡張子での判定に使用）
            
        Returns:
            バイトデータから解凍可能な場合はTrue、そうでなければFalse
        """
        # パスが指定されていれば、その拡張子をチェック
        if path:
            _, ext = os.path.splitext(path.lower())
            return ext in self.supported_extensions
        
        # バイトデータが指定されていない場合はFalse
        if not data:
            return False
            
        # バイトデータがZIPのシグネチャで始まるかチェック
        return data.startswith(b'PK\x03\x04')
    
    def list_entries(self, path: str) -> Optional[List[EntryInfo]]:
        """
        指定したパスのエントリ一覧を取得する
        
        Args:
            path: 一覧を取得するパス（ZIPファイル、またはZIP内のディレクトリ）
            
        Returns:
            エントリ情報のリスト、またはNone（取得できない場合）
        """
        # パスがZIPファイル自体かZIP内のパスかを判定
        zip_path, internal_path = self._split_path(path)
        
        if not zip_path:
            return None
        
        # ZIPファイルを開く
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # 共通処理メソッドを呼び出し
                return self._process_entries(zf, path, zip_path, internal_path, from_memory=False)
        except Exception as e:
            self.debug_error(f"ZIPエントリ列挙エラー: {str(e)}", trace=True)
            return None
    
    def _process_entries(self, zip_file: Union[zipfile.ZipFile, io.BytesIO], 
                         original_path: str, 
                         archive_path: str, 
                         internal_path: str,
                         from_memory: bool = False) -> List[EntryInfo]:
        """
        指定されたパスのエントリを処理するメソッド
        _process_all_entriesの結果を内部パスでフィルタリングして返す
        
        Args:
            zip_file: ZipFileオブジェクト
            original_path: 元のリクエストパス
            archive_path: アーカイブのパス
            internal_path: アーカイブ内のパス
            from_memory: メモリからの処理かどうか
            
        Returns:
            フィルタリングされたエントリ情報のリスト
        """
        # まず全エントリを取得
        all_entries = self._process_all_entries(zip_file, archive_path)
        
        # 結果を格納するリスト
        result_entries = []
        
        # 内部パスの正規化
        if internal_path and not internal_path.endswith('/'):
            internal_path += '/'
        
        # ルートディレクトリをリクエストされた場合
        if not internal_path:
            internal_path = ''
        
        self.debug_info(f"ZIPハンドラ _process_entries: 内部パス [{internal_path}] で {len(all_entries)} エントリをフィルタリング")
        
        # 指定された内部パスの直下にあるエントリだけをフィルタリング
        for entry in all_entries:
            rel_path = entry.rel_path if entry.rel_path else ""
            
            # ディレクトリの場合と、ファイルの場合に分けてフィルタリング
            if entry.type == EntryType.DIRECTORY:
                # ディレクトリエントリの場合: そのディレクトリが指定パスの直下にある場合のみ追加
                if rel_path.startswith(internal_path) and rel_path != internal_path:
                    # ディレクトリ階層レベルをチェック (一階層下のみ)
                    remaining_path = rel_path[len(internal_path):]
                    if '/' not in remaining_path.rstrip('/'):
                        result_entries.append(entry)
            else:
                # ファイルエントリの場合: そのファイルの親ディレクトリが指定パスと一致する場合のみ追加
                parent_dir = os.path.dirname(rel_path)
                if parent_dir:
                    parent_dir += '/'
                    
                if parent_dir == internal_path:
                    result_entries.append(entry)

        self.debug_info(f"ZIPハンドラ _process_entries: {original_path} で {len(result_entries)} エントリを返却")
        self.debug_info(f"  内訳: {sum(1 for e in result_entries if e.type == EntryType.FILE)} ファイル, " 
              f"{sum(1 for e in result_entries if e.type == EntryType.DIRECTORY)} ディレクトリ")
        
        return result_entries
    
    def _get_zip_structure(self, zip_path: str, zf: Union[zipfile.ZipFile, io.BytesIO] = None) -> Dict:
        """
        ZIPファイルの内部構造を解析し、ディレクトリ構造を構築する
        
        Args:
            zip_path: ZIPファイルのパス (メモリからの場合は識別子)
            zf: 既に開かれているZipFileオブジェクトまたはBytesIOオブジェクト
            
        Returns:
            ディレクトリ構造の辞書
        """
        # キャッシュ確認
        if zip_path in self.structure_cache:
            return self.structure_cache[zip_path]
            
        # ZipFileを取得
        should_close = False
        if zf is None:
            try:
                zf = zipfile.ZipFile(zip_path, 'r')
                should_close = True
            except Exception as e:
                self.debug_error(f"ZIPファイル解析エラー: {str(e)}, パス: {zip_path}")
                return {}
                
        # BytesIOオブジェクトからZipFileを取得する場合
        if isinstance(zf, io.BytesIO):
            try:
                zf = zipfile.ZipFile(zf)
                should_close = True
            except Exception as e:
                self.debug_error(f"ZIPファイル解析エラー（BytesIOから）: {str(e)}")
                return {}
                
        try:
            # ディレクトリ構造を初期化 - file_mapを追加して元ファイル名と変換後のファイル名のマッピングを保存
            structure = {'': {'dirs': set(), 'files': set(), 'file_map': {}}}
            
            self.debug_info(f"ZIPファイル解析: {zip_path} の構造を構築します")
            
            # エンコーディングを試す順序（一般的な日本語環境向け）
            encodings_to_try = ['cp932', 'utf-8', 'euc_jp', 'iso-2022-jp', 'cp437']
            
            # すべてのZIPエントリを処理
            for info in zf.infolist():
                # ファイル名のエンコーディング問題を処理
                try:
                    # 元のファイル名を保存
                    original_name = info.filename
                    name = original_name
                    
                    # ZIPファイルのエンコーディング問題を修正
                    if hasattr(info, 'orig_filename'):
                        # 複数のエンコーディングを順番に試す
                        for encoding in encodings_to_try:
                            try:
                                decoded = info.orig_filename.encode('cp437').decode(encoding, errors='replace')
                                # デコードしたファイル名が元と違うかつ制御文字が少ない場合は採用
                                if (decoded != original_name and not any(ord(c) < 32 for c in decoded) and
                                        decoded not in structure['']['file_map']):
                                    name = decoded
                                    break
                            except UnicodeError:
                                continue
                except Exception as e:
                    # どんな例外が発生してもオリジナルのファイル名を使用
                    self.debug_error(f"  ファイル名エンコーディング処理エラー: {e}")
                    name = info.filename
                    original_name = name
                
                # Macの隠しフォルダをスキップ
                if '__MACOSX' in name:
                    continue
                    
                # ディレクトリか判定
                is_dir = name.endswith('/')
                
                if is_dir:
                    # ディレクトリの場合
                    dir_path = name
                    
                    # 親ディレクトリのパスを取得（末尾のスラッシュと自身の名前を除去）
                    parent_path = os.path.dirname(dir_path[:-1])
                    if parent_path:
                        parent_path += '/'
                        
                    # このディレクトリの名前
                    dir_name = os.path.basename(dir_path[:-1])
                    
                    # 構造を順に構築
                    current_path = ""
                    parts = dir_path.strip('/').split('/')
                    
                    for i in range(len(parts)):
                        part = parts[i]
                        if not part:  # 空の部分はスキップ
                            continue
                            
                        # 現在のパスを計算
                        if current_path:
                            current_path += '/'
                        current_path += part
                        
                        # 親のパスを計算
                        parent = '/'.join(parts[:i]) + '/' if i > 0 else ''
                        current_path_with_slash = current_path + '/'
                        
                        # 親ディレクトリがまだ構造に存在しない場合は作成
                        if parent not in structure:
                            structure[parent] = {'dirs': set(), 'files': set(), 'file_map': {}}
                        
                        # 親ディレクトリに現在のディレクトリを追加
                        structure[parent]['dirs'].add(part)
                        
                        # 現在のディレクトリが構造にまだ存在しない場合は作成
                        if current_path_with_slash not in structure:
                            structure[current_path_with_slash] = {'dirs': set(), 'files': set(), 'file_map': {}}
                else:
                    # ファイルの場合
                    file_path = name
                    original_file_path = original_name
                    
                    # ファイルのディレクトリパスとファイル名を分解
                    dir_path = os.path.dirname(file_path)
                    if dir_path:
                        dir_path += '/'
                    file_name = os.path.basename(file_path)
                    
                    # 元のファイル名も保持
                    original_file_name = os.path.basename(original_file_path)
                    
                    # ファイルの親ディレクトリの階層を作成
                    parts = dir_path.strip('/').split('/')
                    current_path = ""
                    
                    for i, part in enumerate(parts):
                        if not part:  # 空の部分はスキップ
                            continue
                            
                        # 現在のディレクトリパスを計算
                        if current_path:
                            current_path += '/'
                        current_path += part
                        current_path_with_slash = current_path + '/'
                        
                        # 親のパスを計算
                        parent = '/'.join(parts[:i]) + '/' if i > 0 else ''
                        
                        # 親ディレクトリがまだ構造に存在しない場合は作成
                        if parent not in structure:
                            structure[parent] = {'dirs': set(), 'files': set(), 'file_map': {}}
                        
                        # 親ディレクトリに現在のディレクトリを追加
                        structure[parent]['dirs'].add(part)
                        
                        # 現在のディレクトリが構造にまだ存在しない場合は作成
                        if current_path_with_slash not in structure:
                            structure[current_path_with_slash] = {'dirs': set(), 'files': set(), 'file_map': {}}
                    
                    # ファイルの親ディレクトリが存在しなければ作成
                    if dir_path not in structure:
                        structure[dir_path] = {'dirs': set(), 'files': set(), 'file_map': {}}
                    
                    # ファイルをディレクトリに追加
                    structure[dir_path]['files'].add(file_name)
                    
                    # 元のファイル名と変換後のファイル名のマッピングを追加（元ファイル名は常に保存）
                    structure[dir_path]['file_map'][file_name] = original_file_name
                    
                # 暗黙的なディレクトリ構造の構築
                # ファイルのパスから親ディレクトリを推測し、存在しない場合は作成する
                implicit_dirs = []
                if is_dir:
                    path_parts = name.rstrip('/').split('/')
                    for i in range(1, len(path_parts)):
                        partial_path = '/'.join(path_parts[:i]) + '/'
                        if partial_path not in structure:
                            implicit_dirs.append((partial_path, path_parts[i-1]))
                else:
                    dir_path = os.path.dirname(name)
                    if dir_path:
                        path_parts = dir_path.split('/')
                        for i in range(1, len(path_parts) + 1):
                            partial_path = '/'.join(path_parts[:i]) + '/'
                            if partial_path not in structure:
                                # ディレクトリ階層を作成
                                structure[partial_path] = {'dirs': set(), 'files': set(), 'file_map': {}}
                                
                                # このディレクトリの親ディレクトリに追加
                                if i > 1:
                                    parent_path = '/'.join(path_parts[:i-1]) + '/'
                                    if parent_path not in structure:
                                        structure[parent_path] = {'dirs': set(), 'files': set(), 'file_map': {}}
                                    structure[parent_path]['dirs'].add(path_parts[i-1])
                                else:
                                    # ルートディレクトリの場合
                                    if '' not in structure:
                                        structure[''] = {'dirs': set(), 'files': set(), 'file_map': {}}
                                    structure['']['dirs'].add(path_parts[0])
            
            # 結果を報告
            self.debug_info(f"ZIPファイル解析完了: {zip_path}, {len(structure)} ディレクトリエントリ")
            for dir_path, contents in structure.items():
                self.debug_info(f"  ディレクトリ: {dir_path}: {len(contents['dirs'])} サブディレクトリ, {len(contents['files'])} ファイル")
                
                # マッピング情報の出力（デバッグ用）
                mapping_count = 0
                for display_name, original_name in contents.get('file_map', {}).items():
                    if display_name != original_name:
                        mapping_count += 1
                        if mapping_count <= 5:  # 最大5件のみ表示
                            self.debug_info(f"    マッピング: {display_name} -> {original_name}")
                
                if mapping_count > 5:
                    self.debug_info(f"    ...他 {mapping_count - 5} 件のマッピング")
            
            # キャッシュに追加
            self.structure_cache[zip_path] = structure
            return structure
        finally:
            if should_close and zf:
                zf.close()
    
    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定したパスのエントリ情報を取得する
        
        Args:
            path: 情報を取得するパス(カレントパスからの相対パス)
            
        Returns:
            エントリ情報、またはNone（取得できない場合）
        """
        # パスがZIPファイル自体かZIP内のパスかを判定
        zip_path, internal_path = self._split_path(path)
        
        # internal_pathが空ならZIPファイル自体
        if not internal_path:
            if not os.path.isfile(zip_path):
                return None
                
            # ZIPファイル自体の情報を返す
            try:
                file_stat = os.stat(zip_path)
                return self.create_entry_info(
                    name=os.path.basename(zip_path),
                    abs_path=zip_path,
                    rel_path=path,
                    name_in_arc=path,
                    size=file_stat.st_size,
                    modified_time=datetime.datetime.fromtimestamp(file_stat.st_mtime),
                    type=EntryType.ARCHIVE  # ZIPファイルはARCHIVEタイプ
                )
            except:
                return None
        
        # ZIPファイル内のエントリの情報を取得
        # まずall_entriesを取得する
        entries = self.list_all_entries(zip_path)
        if not entries:
            # エントリから相対パスが一致するエントリを探す
            for entry in entries:
                if entry.rel_path == path:
                    return entry
        return None
    
    def read_archive_file(self, archive_path: str, file_path: str) -> Optional[bytes]:
        """
        アーカイブファイル内のファイルの内容を読み込む
        
        Args:
            archive_path: アーカイブファイルのパス
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容（バイト配列）。読み込みに失敗した場合はNone
            
        Raises:
            FileNotFoundError: 指定されたアーカイブやファイルが存在しない場合
            IOError: アーカイブが壊れているなど読み込みに失敗した場合
            PermissionError: ファイルへのアクセス権限がない場合
        """
        # アーカイブパスがZIPファイルであることを確認
        if not os.path.isfile(archive_path):
            raise FileNotFoundError(f"指定されたアーカイブが存在しません: {archive_path}")
            
        if not archive_path.lower().endswith(tuple(self.supported_extensions)):
            raise ValueError(f"指定されたパスはZIPファイルではありません: {archive_path}")
                
        self.debug_info(f"ZIPファイル内のファイル読み込み: {archive_path} -> {file_path}")
        
        # ファイルパスを正規化
        norm_file_path = file_path.replace('\\', '/')
        
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_file:
                try:
                    # 指定されたパスでファイルを直接読み込む
                    content = zip_file.read(norm_file_path)
                    self.debug_info(f"  ファイルを読み込みました: {len(content)} バイト")
                    return content
                except KeyError:
                    # ファイルが見つからない場合はエラーを返す
                    self.debug_warning(f"  ファイルが見つかりません: {norm_file_path}")
                    raise FileNotFoundError(f"ZIPファイル内のファイルが見つかりません: {norm_file_path}")
                        
        except zipfile.BadZipFile as e:
            # ZIP書庫が壊れている場合、詳細なメッセージをつけてIOErrorをスロー
            error_msg = f"ZIPファイルが破損しています: {archive_path} - {str(e)}"
            self.debug_error(error_msg)
            raise IOError(error_msg)
        except PermissionError as e:
            # アクセス権限エラーの場合はそのまま再スロー
            self.debug_error(f"ZIPファイルへのアクセス権限がありません: {archive_path} - {str(e)}")
            raise
        except FileNotFoundError:
            # 既に適切なFileNotFoundErrorが発生している場合はそのまま再スロー
            raise
        except Exception as e:
            # その他の例外はIOErrorとして再スロー
            self.debug_error(f"ZIPアーカイブ内のファイル読み込みエラー: {archive_path} - {str(e)}")
            raise IOError(f"ZIPアーカイブ読み込みエラー: {archive_path} - {str(e)}")
    
    def get_stream(self, path: str) -> Optional[BinaryIO]:
        """
        指定されたパスのファイルのストリームを取得する
        
        ZIPファイル内のファイルの場合は、一時的にファイル全体を読み込んでメモリ上のストリームとして返す
        
        Args:
            path: ストリームを取得するファイルのパス
            
        Returns:
            ファイルストリーム。取得できない場合はNone
        """
        try:
            # パスがZIPファイル自体かZIP内のパスかを判定
            zip_path, internal_path = self._split_path(path)
            
            # ZIPファイルの場合は通常のファイルとして扱う
            if not internal_path:
                if os.path.isfile(zip_path):
                    return open(zip_path, 'rb')
                return None
                
            # ZIPファイル内のファイルの場合、そのファイル内容を取得してメモリストリームとして返す
            file_content = self.read_file(path)
            if file_content is not None:
                return io.BytesIO(file_content)
                
            return None
        except Exception as e:
            self.debug_error(f"ファイルストリーム取得エラー: {e}", trace=True)
            return None

    def list_entries_from_bytes(self, archive_data: bytes, path: str = "") -> List[EntryInfo]:
        """
        メモリ上のZIPデータからエントリのリストを返す
        
        Args:
            archive_data: ZIPデータのバイト配列
            path: アーカイブ内のパス（デフォルトはルート）
            
        Returns:
            エントリ情報のリスト
        """
        try:
            if not self.can_handle_bytes(archive_data):
                return []
                
            self.debug_info(f"ZipHandler: メモリデータからエントリリストを取得中 ({len(archive_data)} バイト)")
            
            # 内部パスが指定されている場合、name_in_arcの考慮が必要
            internal_path = path
            if internal_path:
                # パスを正規化
                internal_path = internal_path.replace('\\', '/')
                self.debug_info(f"ZipHandler: 内部パスが指定されています: {internal_path}")
                
                # ディレクトリパスの末尾にスラッシュを追加（一貫性のため）
                if not internal_path.endswith('/') and self.is_directory_path(internal_path):
                    internal_path += '/'
                    self.debug_info(f"ZipHandler: ディレクトリパスに末尾スラッシュを追加: {internal_path}")
            
            # メモリ上のZIPを開く
            bytes_io = io.BytesIO(archive_data)
            with zipfile.ZipFile(bytes_io) as zf:
                # 共通処理メソッドを呼び出し
                entries = self._process_entries(zf, path, "memory_zip", internal_path, from_memory=True)
                self.debug_info(f"ZipHandler: メモリデータから {len(entries)} 個のエントリを取得")
                return entries
        except Exception as e:
            self.debug_error(f"ZipHandler: メモリデータからのエントリリスト取得エラー: {e}", trace=True)
            return []

    def is_directory_path(self, path: str) -> bool:
        """
        指定されたパスがディレクトリパスかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            ディレクトリパスと思われる場合はTrue、そうでなければFalse
        """
        # '.' や拡張子がない場合はディレクトリの可能性が高い
        if '.' not in os.path.basename(path):
            return True
            
        # よく使われるアーカイブ/画像拡張子のいずれかを持っていたらファイル
        file_extensions = ['.zip', '.rar', '.7z', '.cbz', '.cbr', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.pdf']
        _, ext = os.path.splitext(path.lower())
        if ext in file_extensions:
            return False
            
        # 特殊ケース: ディレクトリ名に拡張子のような部分が含まれる場合は、
        # パス内のファイル数をチェックして判断する
        
        # デフォルトではディレクトリと仮定
        return True

    def read_file_from_bytes(self, archive_data: bytes, file_path: str) -> Optional[bytes]:
        """
        メモリ上のZIPデータから特定のファイルを読み込む
        
        Args:
            archive_data: ZIPデータのバイト配列
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
            
        Raises:
            ValueError: データがZIPフォーマットでない場合
            FileNotFoundError: 指定されたファイルが存在しない場合
            IOError: 書庫が壊れているなど読み込みに失敗した場合
        """
        # バイトデータがZIPフォーマットでない場合
        if not self.can_handle_bytes(archive_data):
            error_msg = "データはZIP形式ではありません"
            self.debug_warning(f"ZipHandler: {error_msg}")
            raise ValueError(error_msg)
            
        # ファイルパスを正規化
        norm_file_path = file_path.replace('\\', '/')
        self.debug_info(f"ZipHandler: メモリからファイル読み込み: {norm_file_path}")
        
        try:
            # メモリ上でZIPを開く
            bytes_io = io.BytesIO(archive_data)
            with zipfile.ZipFile(bytes_io) as zip_file:
                try:
                    # 指定されたパスでファイルを直接読み込む
                    content = zip_file.read(norm_file_path)
                    self.debug_info(f"  ファイルを読み込みました: {len(content)} バイト")
                    return content
                except KeyError:
                    # ファイルが見つからない場合はエラーを返す
                    self.debug_warning(f"  ファイルが見つかりません: {norm_file_path}")
                    raise FileNotFoundError(f"ZIPファイル内のファイルが見つかりません: {norm_file_path}")
                
        except zipfile.BadZipFile as e:
            # ZIP書庫が壊れている場合、詳細なメッセージをつけてIOErrorをスロー
            error_msg = f"メモリ上のZIPデータが破損しています - {str(e)}"
            self.debug_error(error_msg)
            raise IOError(error_msg)
        except FileNotFoundError:
            # 既に適切なFileNotFoundErrorが発生している場合はそのまま再スロー
            raise
        except Exception as e:
            # その他の例外はIOErrorとして再スロー
            self.debug_error(f"ZipHandler.read_file_from_bytes エラー: {str(e)}")
            raise IOError(f"メモリ上のZIPデータ読み込みエラー: {str(e)}")

    def _is_archive_by_extension(self, filename: str) -> bool:
        """ファイル名の拡張子がアーカイブかどうかを判定する"""
        _, ext = os.path.splitext(filename.lower())
        return ext in ['.zip', '.cbz', '.epub', '.rar', '.7z', '.tar', '.gz']
    
    def get_parent_path(self, path: str) -> str:
        """
        指定したパスの親ディレクトリのパスを取得する
        
        Args:
            path: 親ディレクトリを取得するパス
            
        Returns:
            親ディレクトリのパス。親がない場合は空文字列
        """
        # パスがZIPファイル自体かZIP内のパスかを判定
        zip_path, internal_path = self._split_path(path)
        
        # internal_pathが空ならZIPファイル自体なので、その親を返す
        if not internal_path:
            return os.path.dirname(zip_path)
        
        # ZIP内のパスの親を計算
        parent_dir = os.path.dirname(internal_path.rstrip('/'))
        
        # ルートの場合はZIPファイル自体を返す
        if not parent_dir:
            return zip_path
            
        # 親ディレクトリのパスを作成して返す
        return self._join_paths(zip_path, parent_dir)
    
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
        パスをZIPファイルのパスと内部パスに分割する
        
        Args:
            path: 分割するパス
            
        Returns:
            (ZIPファイルのパス, 内部パス) のタプル
        """
        # パスの正規化 (バックスラッシュをスラッシュに変換)
        norm_path = path.replace('\\', '/')
        
        # ZIPファイル自体かどうか確認
        if os.path.isfile(norm_path) and norm_path.lower().endswith('.zip'):
            # パス自体がZIPファイル
            return norm_path, ""
            
        # もっと厳密なパス解析を行う
        try:
            # パスを分解してZIPファイル部分を見つける
            parts = norm_path.split('/')
            
            # ZIPファイルのパスを見つける
            zip_path = ""
            internal_path_parts = []
            
            for i in range(len(parts)):
                # パスの部分を結合してテスト
                test_path = '/'.join(parts[:i+1])
                
                # ZIPファイルかどうか確認
                if os.path.isfile(test_path) and test_path.lower().endswith('.zip'):
                    zip_path = test_path
                    # 残りの部分が内部パス
                    internal_path_parts = parts[i+1:]
                    break
            
            # ZIPファイルが見つからなければ無効
            if not zip_path:
                self.debug_warning(f"警告: ZIPファイルが見つかりません: {norm_path}")
                return "", ""
            
            # 内部パスを結合
            internal_path = '/'.join(internal_path_parts)
            
            # デバッグ出力を追加
            self.debug_info(f"ZIPパス分解: {norm_path} → ZIP:{zip_path}, 内部:{internal_path}")
            
            return zip_path, internal_path
        except Exception as e:
            self.debug_error(f"ZIPパス分解エラー: {str(e)}, パス: {path}", trace=True)
            return "", ""

    def needs_encoding_conversion(self) -> bool:
        """
        このハンドラが文字コード変換を必要とするかどうかを返す
        
        ZIPファイルは特に日本語ファイル名を含む場合にエンコーディング変換が必要
        
        Returns:
            常にTrue（ZIPファイルはエンコーディング変換が必要）
        """
        return True

    def _process_all_entries(self, zf: zipfile.ZipFile, zip_path: str, base_path: str = "") -> List[EntryInfo]:
        """
        ZIPファイル内のすべてのエントリを処理する共通メソッド
        
        Args:
            zf: ZipFileオブジェクト
            zip_path: ZIPファイルのパス（またはメモリデータを識別する文字列）
            base_path: ベースパス（使用しない、インターフェース互換性のため）
            
        Returns:
            エントリ情報のリスト
        """
        # すべてのエントリを格納するリスト
        all_entries = []
        
        # エンコーディングを試す順序（一般的な日本語環境向け）
        encodings_to_try = ['cp932', 'utf-8', 'euc_jp', 'iso-2022-jp', 'cp437']
        
        # ファイル情報を格納する辞書
        file_entries_dict = {}
        
        # ディレクトリエントリを追跡する辞書 (パス -> True)
        directory_entries = {}

        # エンコード変換前の元のファイル名を格納するセット（重複排除用）
        original_filenames = set()
        
        # まずinfolistからエントリ情報を取得
        for info in zf.infolist():
            # パスの正規化
            original_name = info.filename
            norm_path = original_name.replace('\\', '/')
            
            # 元のファイル名を記録（後で重複チェック用）
            original_filenames.add(norm_path)
            
            # Macの隠しフォルダなどをスキップ
            if '__MACOSX' in norm_path:
                continue
            
            # ファイル名のエンコーディング問題を処理
            try:
                name = original_name
                
                # ZIPファイルのエンコーディング問題を修正
                if hasattr(info, 'orig_filename'):
                    # 複数のエンコーディングを順番に試す
                    for encoding in encodings_to_try:
                        try:
                            decoded = info.orig_filename.encode('cp437').decode(encoding, errors='replace')
                            # デコードしたファイル名が元と違うかつ制御文字が少ない場合は採用
                            if decoded != original_name and not any(ord(c) < 32 for c in decoded):
                                name = decoded
                                break
                        except UnicodeError:
                            continue
            except Exception as e:
                # どんな例外が発生してもオリジナルのファイル名を使用
                self.debug_error(f"  ファイル名エンコーディング処理エラー: {e}")
                name = original_name
            
            # ディレクトリエントリか判定
            is_dir = name.endswith('/')
            
            # 辞書に情報を保存
            file_entries_dict[name] = {
                'info': info,
                'original_name': original_name,
                'size': info.file_size,
                'date_time': info.date_time,
                'is_dir': is_dir
            }
            
            if is_dir:
                # ディレクトリの場合、階層化された親ディレクトリも全て作成
                dir_parts = name.rstrip('/').split('/')
                for i in range(1, len(dir_parts) + 1):
                    parent_dir = '/'.join(dir_parts[:i]) + '/'
                    directory_entries[parent_dir] = True
        
        # namelistからもエントリを収集し、infolistに含まれていない場合は処理
        for name in zf.namelist():
            norm_path = name.replace('\\', '/')
            
            # すでに処理済みのエントリはスキップ
            if norm_path in original_filenames:
                continue
                
            # Macの隠しフォルダなどをスキップ
            if '__MACOSX' in norm_path:
                continue
                
            # ディレクトリエントリか判定
            is_dir = norm_path.endswith('/')
            
            if is_dir and norm_path not in file_entries_dict:
                # ディレクトリの場合、辞書に追加
                file_entries_dict[norm_path] = {
                    'info': None,
                    'original_name': norm_path,
                    'size': 0,
                    'date_time': (0, 0, 0, 0, 0, 0),
                    'is_dir': True
                }
                
                # ディレクトリ階層も登録
                dir_parts = norm_path.rstrip('/').split('/')
                for i in range(1, len(dir_parts) + 1):
                    parent_dir = '/'.join(dir_parts[:i]) + '/'
                    directory_entries[parent_dir] = True
        
        # ファイルパスから親ディレクトリを推測・構築
        for name, entry_data in file_entries_dict.items():
            if not entry_data['is_dir']:  # ファイルエントリについて処理
                # パスからディレクトリ部分を抽出
                dir_path = os.path.dirname(name)
                if dir_path:
                    # 親ディレクトリパスを階層的に構築
                    dir_parts = dir_path.split('/')
                    for i in range(1, len(dir_parts) + 1):
                        parent_dir = '/'.join(dir_parts[:i]) + '/'
                        directory_entries[parent_dir] = True
        
        # ディレクトリエントリを作成
        for dir_path in sorted(directory_entries.keys()):
            # ルートディレクトリはスキップ
            if not dir_path or dir_path == '/':
                continue
                
            dir_name = os.path.basename(dir_path.rstrip('/'))
            if not dir_name:  # 空の名前の場合はスキップ
                continue
            
            # EntryInfoオブジェクトを作成
            all_entries.append(self.create_entry_info(
                name=dir_name,
                rel_path=dir_path,
                size=0,
                modified_time=None,
                type=EntryType.DIRECTORY,
                name_in_arc=dir_path
            ))
        
        # ファイルエントリを作成
        for name, entry_data in file_entries_dict.items():
            if entry_data['is_dir']:
                continue  # ディレクトリはすでに処理済み
            
            # ファイル名を取得
            file_name = os.path.basename(name)
            
            # タイムスタンプを変換
            timestamp = None
            if entry_data['date_time'] != (0, 0, 0, 0, 0, 0):
                try:
                    timestamp = datetime.datetime(*entry_data['date_time'])
                except:
                    pass
            
            # ファイルの拡張子をチェックしてアーカイブなら特別に処理
            _, ext = os.path.splitext(file_name.lower())
            entry_type = EntryType.ARCHIVE if ext in self.supported_extensions else EntryType.FILE
            
            # EntryInfoオブジェクトを作成
            all_entries.append(self.create_entry_info(
                name=file_name,
                rel_path=name,
                size=entry_data['size'],
                modified_time=timestamp,
                type=entry_type,
                name_in_arc=entry_data['original_name']
            ))
        
        self.debug_info(f"ZipHandler: {zip_path} から {len(all_entries)} 個のエントリを取得しました")
        self.debug_info(f"  内訳: {sum(1 for e in all_entries if e.type != EntryType.DIRECTORY)} ファイル, " 
              f"{sum(1 for e in all_entries if e.type == EntryType.DIRECTORY)} ディレクトリ")
        
        return all_entries

    def list_all_entries(self, path: str) -> List[EntryInfo]:
        """
        指定したZIPアーカイブ内のすべてのエントリを再帰的に取得する（フィルタリングなし）
        (この時点ではエントリの内容は読み込まない)
        (この時点では不完全なエントリ情報であり、マネージャによる追加情報が必要)
        
        Args:
            path: ZIPアーカイブファイルのパス
            
        Returns:
            アーカイブ内のすべてのエントリのリスト
            
        Raises:
            FileNotFoundError: 指定されたパスに書庫が存在しない場合
            IOError: 書庫が壊れているなど読み込みに失敗した場合
        """
        # パスがZIPファイル自体かZIP内のパスかを判定
        zip_path, internal_path = self._split_path(path)
        
        # ファイルが存在しない場合は、FileNotFoundErrorをスローする
        if not zip_path:
            self.debug_error(f"ZIPファイルが見つかりません: {path}")
            raise FileNotFoundError(f"ZIPファイルが見つかりません: {path}")
        elif not os.path.isfile(zip_path):
            self.debug_error(f"ZIPファイルが存在しません: {zip_path}")
            raise FileNotFoundError(f"ZIPファイルが存在しません: {zip_path}")
        
        # 内部パスが指定されている場合は警告（このメソッドではアーカイブ全体を対象とする）
        if internal_path:
            self.debug_warning(f"ZipHandler: list_all_entriesでは内部パスを指定できません。アーカイブ全体が対象です: {path}")
            # 内部パスを無視してアーカイブファイル全体を処理
        
        try:
            # ZIPファイルを開く
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # 共通処理メソッドを呼び出し
                return self._process_all_entries(zf, zip_path)
        except zipfile.BadZipFile as e:
            # ZIP書庫が壊れている場合、詳細なメッセージをつけてIOErrorをスロー
            error_msg = f"ZIPファイルが破損しています: {zip_path} - {str(e)}"
            self.debug_error(error_msg)
            raise IOError(error_msg)
        except PermissionError as e:
            # ファイルへのアクセス権限がない場合
            error_msg = f"ZIPファイルへのアクセス権限がありません: {zip_path} - {str(e)}"
            self.debug_error(error_msg)
            raise IOError(error_msg)
        except Exception as e:
            # その他の例外はIOErrorとして再スロー
            self.debug_error(f"ZipHandler: 全エントリ取得中にエラーが発生しました: {e}")
            raise IOError(f"ZIPファイル読み込みエラー: {zip_path} - {str(e)}")

    def list_all_entries_from_bytes(self, archive_data: bytes, path: str = "") -> List[EntryInfo]:
        """
        メモリ上のZIPデータからすべてのエントリを再帰的に取得する（フィルタリングなし）
        
        Args:
            archive_data: ZIPデータのバイト配列
            path: ベースパス（引数は受け取るが使用しない、インターフェース互換性のため）
            
        Returns:
            アーカイブ内のすべてのエントリのリスト
            
        Raises:
            ValueError: データがZIPフォーマットでない場合
            IOError: 書庫が壊れているなど読み込みに失敗した場合
        """
        # バイトデータがZIPフォーマットでない場合
        if not self.can_handle_bytes(archive_data):
            error_msg = "データはZIP形式ではありません"
            self.debug_warning(f"ZipHandler: {error_msg}")
            raise ValueError(error_msg)
            
        self.debug_info(f"ZipHandler: メモリデータからすべてのエントリを取得中 ({len(archive_data)} バイト)")
        
        try:
            # メモリ上のZIPを開く
            bytes_io = io.BytesIO(archive_data)
            
            try:
                with zipfile.ZipFile(bytes_io) as zf:
                    # 共通処理メソッドを呼び出し（パスパラメータは不要）
                    return self._process_all_entries(zf, "memory_zip")
            except zipfile.BadZipFile as e:
                # ZIP書庫が壊れている場合、詳細なメッセージをつけてIOErrorをスロー
                error_msg = f"メモリ上のZIPデータが破損しています - {str(e)}"
                self.debug_error(error_msg)
                raise IOError(error_msg)
            except Exception as e:
                # その他の例外はIOErrorとして再スロー
                self.debug_error(f"ZipHandler: ZIPファイルオープンエラー: {e}")
                raise IOError(f"メモリ上のZIPデータ処理エラー: {str(e)}")
        except IOError:
            # IOError例外はそのまま再スロー
            raise
        except Exception as e:
            # その他の例外はIOErrorとして再スロー
            self.debug_error(f"ZipHandler: メモリからの全エントリ取得エラー: {e}")
            raise IOError(f"メモリ上のZIPデータ処理エラー: {str(e)}")
