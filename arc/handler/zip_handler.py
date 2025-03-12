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
            print(f"ZIPエントリ列挙エラー: {str(e)}")
            traceback.print_exc()
            return None
    
    def _process_entries(self, zip_file: Union[zipfile.ZipFile, io.BytesIO], 
                         original_path: str, 
                         archive_path: str, 
                         internal_path: str,
                         from_memory: bool = False) -> List[EntryInfo]:
        """
        ZIPエントリを処理する共通メソッド
        
        Args:
            zip_file: ZipFileオブジェクトまたはByteIOオブジェクト
            original_path: 元のリクエストパス
            archive_path: アーカイブのパス（メモリの場合は"memory_zip"などの識別子）
            internal_path: アーカイブ内のパス
            from_memory: メモリからの処理かどうか
            
        Returns:
            エントリ情報のリスト
        """
        # エントリリストを作成
        result_entries = []
        
        # ZIPファイル構造を取得/更新
        structure = self._get_zip_structure(archive_path, zip_file)
        
        # デバッグ情報：内部パスと構造の確認
        print(f"ZIPハンドラ list_entries: 処理する内部パス [{internal_path}]")
        print(f"ZIPハンドラ list_entries: 構造キーの一部: {list(structure.keys())[:5]}")
        
        # 要求されたパスの正規化
        if internal_path and not internal_path.endswith('/'):
            internal_path += '/'
        
        # 指定されたディレクトリが存在するか確認
        if internal_path not in structure:
            if internal_path:  # ルートでなければ、類似パスを探す
                print(f"ZIPハンドラ: 内部パス '{internal_path}' が構造内に見つかりません")
                
                # 末尾のスラッシュ有無で正規化したパスで検索
                normalized_path = internal_path.rstrip('/')
                for struct_path in structure.keys():
                    struct_normalized = struct_path.rstrip('/')
                    if normalized_path == struct_normalized:
                        print(f"ZIPハンドラ: 正規化したパスが一致: {struct_path}")
                        internal_path = struct_path
                        break
                else:
                    # 前方一致で探す（親ディレクトリ判定のため）
                    for struct_path in structure.keys():
                        if struct_path.startswith(internal_path):
                            print(f"ZIPハンドラ: 前方一致するパスが見つかりました: {struct_path}")
                            internal_path = struct_path
                            break
                    else:
                        print(f"ZIPハンドラ: 類似パスも見つかりません")
                        return []
            else:
                internal_path = ''  # ルートの場合は空文字に正規化
        
        # このディレクトリの子（ファイルとサブフォルダ）を取得
        current_dir = structure[internal_path]
        
        # サブディレクトリをリストに追加
        for dir_name in current_dir['dirs']:
            dir_path = os.path.join(original_path, dir_name).replace('\\', '/')
            
            # 相対パスを設定したEntryInfoを作成
            result_entries.append(self.create_entry_info(
                name=dir_name,
                abs_path=dir_path,
                type=EntryType.DIRECTORY
            ))
        
        # ファイルをリストに追加
        for file_name in current_dir['files']:
            file_path_in_zip = internal_path + file_name
            file_path = os.path.join(original_path, file_name).replace('\\', '/')
            
            # ファイル情報を取得
            try:
                # 実際のZIPエントリ情報を取得するときに、name_in_arcが必要な場合は使用
                original_name = None
                if internal_path in structure and file_name in structure[internal_path]['file_map']:
                    original_name = structure[internal_path]['file_map'][file_name]
                    file_path_in_zip = internal_path + original_name
                    
                file_info = None
                try:
                    # まず変換後の名前で試す
                    file_info = zip_file.getinfo(file_path_in_zip)
                except KeyError:
                    # 失敗したら元の名前で試す
                    if original_name:
                        try:
                            orig_path = internal_path + original_name
                            file_info = zip_file.getinfo(orig_path)
                        except KeyError:
                            # どちらでも見つからなければ次のファイルへ
                            print(f"  ファイル情報取得失敗: {file_path_in_zip}")
                            continue
                    else:
                        # 元の名前がなく、かつ変換後の名前でも見つからなければ次へ
                        print(f"  ファイル情報取得失敗: {file_path_in_zip}")
                        continue
                
                # タイムスタンプを変換
                timestamp = None
                if file_info.date_time != (0, 0, 0, 0, 0, 0):
                    try:
                        timestamp = datetime.datetime(*file_info.date_time)
                    except:
                        pass
                
                # ファイルの拡張子をチェックしてアーカイブなら特別に処理
                _, ext = os.path.splitext(file_name.lower())
                entry_type = EntryType.ARCHIVE if ext in self.supported_extensions else EntryType.FILE
                    
                # 相対パスを設定したファイルEntryInfoを作成
                entry = self.create_entry_info(
                    name=file_name,
                    abs_path=file_path,
                    type=entry_type,
                    size=file_info.file_size,
                    modified_time=timestamp,
                    name_in_arc=original_name
                )
                
                result_entries.append(entry)
            except Exception as e:
                # エラーが発生しても最低限の情報でエントリを追加
                print(f"ZIPファイル情報取得エラー: {file_path_in_zip}, {str(e)}")
                result_entries.append(self.create_entry_info(
                    name=file_name,
                    abs_path=file_path,
                    type=EntryType.FILE,
                    size=0,
                    name_in_arc=original_name  # これも渡しておく
                ))
        
        # デバッグ情報
        print(f"ZIPハンドラ: {original_path} で {len(result_entries)} エントリを発見")
        print(f"  内訳: {sum(1 for e in result_entries if e.type == EntryType.FILE)} ファイル, " 
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
                print(f"ZIPファイル解析エラー: {str(e)}, パス: {zip_path}")
                return {}
                
        # BytesIOオブジェクトからZipFileを取得する場合
        if isinstance(zf, io.BytesIO):
            try:
                zf = zipfile.ZipFile(zf)
                should_close = True
            except Exception as e:
                print(f"ZIPファイル解析エラー（BytesIOから）: {str(e)}")
                return {}
                
        try:
            # ディレクトリ構造を初期化 - file_mapを追加して元ファイル名と変換後のファイル名のマッピングを保存
            structure = {'': {'dirs': set(), 'files': set(), 'file_map': {}}}
            
            print(f"ZIPファイル解析: {zip_path} の構造を構築します")
            
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
                                if decoded != original_name and not any(ord(c) < 32 for c in decoded):
                                    name = decoded
                                    #print(f"  エンコーディング変換({encoding}): {original_name} -> {name}")
                                    break
                            except UnicodeError:
                                continue
                except Exception as e:
                    # どんな例外が発生してもオリジナルのファイル名を使用
                    print(f"  ファイル名エンコーディング処理エラー: {e}")
                    name = info.filename
                    original_name = name
                
                # Macの隠しフォルダをスキップ
                if '__MACOSX' in name:
                    continue
                    
                # ディレクトリか判定
                is_dir = name.endswith('/')
                
                # デバッグ出力
                #print(f"  エントリ: {name} ({'ディレクトリ' if is_dir else 'ファイル'})")
                
                # 既に処理済みのパスをスキップ
                if name in structure:
                    continue
                    
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
            
            # 結果を報告
            print(f"ZIPファイル解析完了: {zip_path}, {len(structure)} ディレクトリエントリ")
            for dir_path, contents in structure.items():
                print(f"  ディレクトリ: {dir_path}: {len(contents['dirs'])} サブディレクトリ, {len(contents['files'])} ファイル")
                
                # マッピング情報の出力（デバッグ用）
                mapping_count = 0
                for display_name, original_name in contents.get('file_map', {}).items():
                    if display_name != original_name:
                        mapping_count += 1
                        if mapping_count <= 5:  # 最大5件のみ表示
                            print(f"    マッピング: {display_name} -> {original_name}")
                
                if mapping_count > 5:
                    print(f"    ...他 {mapping_count - 5} 件のマッピング")
            
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
            path: 情報を取得するパス
            
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
                    size=file_stat.st_size,
                    modified_time=datetime.datetime.fromtimestamp(file_stat.st_mtime),
                    type=EntryType.ARCHIVE  # ZIPファイルはARCHIVEタイプ
                )
            except:
                return None
        
        # ZIPファイル内のエントリの情報を取得
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # ZIP構造を取得
                structure = self._get_zip_structure(zip_path, zf)
                
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
                        try:
                            # ファイル情報を取得
                            file_path_in_zip = file_dir + file_name
                            file_info = zf.getinfo(file_path_in_zip)
                            timestamp = None
                            if file_info.date_time != (0, 0, 0, 0, 0, 0):
                                timestamp = datetime.datetime(*file_info.date_time)
                                
                            # name_in_arcにオリジナルのファイル名を設定
                            original_name = None
                            if file_dir in structure and file_name in structure[file_dir]['file_map']:
                                original_name = structure[file_dir]['file_map'][file_name]
                                
                            # ファイルの拡張子をチェックしてアーカイブなら特別に処理
                            _, ext = os.path.splitext(file_name.lower())
                            entry_type = EntryType.ARCHIVE if ext in self.supported_extensions else EntryType.FILE
                                
                            return EntryInfo(
                                name=file_name,
                                path=path,
                                size=file_info.file_size,
                                modified_time=timestamp,
                                type=entry_type,
                                name_in_arc=original_name
                            )
                        except:
                            # 最低限の情報でエントリを作成
                            return EntryInfo(
                                name=file_name,
                                path=path,
                                size=0,
                                modified_time=None,
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
            print(f"ZIPエントリ情報の取得でエラー: {str(e)}")
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
        # パスがZIPファイル自体かZIP内のパスかを判定
        zip_path, internal_path = self._split_path(path)
        
        # ZIPファイル自体なら読み込めない
        if not internal_path:
            return None
        
        # ZIPファイル内のファイルを読み込む
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # エントリ情報を取得してname_in_arcをチェック
                dir_path = os.path.dirname(internal_path)
                if dir_path:
                    dir_path += '/'
                file_name = os.path.basename(internal_path)
                
                # 構造から情報を取得
                structure = self._get_zip_structure(zip_path, zf)
                
                # name_in_arcを使って正しいパスを取得
                actual_path = internal_path
                if dir_path in structure and file_name in structure[dir_path]['files']:
                    name_in_arc = structure[dir_path]['file_map'].get(file_name, file_name)
                    if name_in_arc != file_name:
                        actual_path = dir_path + name_in_arc
                
                try:
                    with zf.open(actual_path) as f:
                        return f.read()
                except KeyError:
                    # 元のパスでも試す
                    try:
                        with zf.open(internal_path) as f:
                            return f.read()
                    except KeyError:
                        print(f"ZIPファイル内のファイルが見つかりません: {internal_path}")
                        return None
        except Exception as e:
            print(f"ZIPファイルの読み込みでエラー: {str(e)}")
            return None
    
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
            # アーカイブパスがZIPファイルであることを確認
            if not os.path.isfile(archive_path) or not archive_path.lower().endswith(tuple(self.supported_extensions)):
                print(f"指定されたパスはZIPファイルではありません: {archive_path}")
                return None
                
            print(f"ZIPファイル内のファイル読み込み: {archive_path} -> {file_path}")
            
            # ファイルパスを正規化
            norm_file_path = file_path.replace('\\', '/')
            
            with zipfile.ZipFile(archive_path, 'r') as zip_file:
                # 構造から情報を取得
                structure = self._get_zip_structure(archive_path, zip_file)
                
                # ディレクトリパスとファイル名に分解
                dir_path = os.path.dirname(norm_file_path)
                if dir_path:
                    dir_path += '/'
                file_name = os.path.basename(norm_file_path)
                
                # name_in_arcを使って正しいパスを取得
                actual_path = norm_file_path
                if dir_path in structure and file_name in structure[dir_path]['files']:
                    name_in_arc = structure[dir_path]['file_map'].get(file_name, file_name)
                    if name_in_arc != file_name:
                        actual_path = dir_path + name_in_arc
                        print(f"  実際のパスを使用: {norm_file_path} -> {actual_path}")
                
                # ファイルの存在確認
                try:
                    with zip_file.open(actual_path) as f:
                        content = f.read()
                        print(f"  ファイルを読み込みました: {len(content)} バイト")
                        return content
                except KeyError:
                    # 元のパスでも試す
                    try:
                        with zip_file.open(norm_file_path) as f:
                            content = f.read()
                            print(f"  元のパスでファイルを読み込みました: {len(content)} バイト")
                            return content
                    except KeyError:
                        # 直接一致しない場合、すべてのエントリを検索
                        for info in zip_file.infolist():
                            try:
                                if self.normalize_path(info.filename) == self.normalize_path(norm_file_path):
                                    print(f"ZIPファイル内のファイルを読み込み: {info.filename}")
                                    return zip_file.read(info.filename)
                            except:
                                # normalize_pathメソッドがない場合
                                if info.filename.replace('\\', '/') == norm_file_path:
                                    print(f"ZIPファイル内のファイルを読み込み: {info.filename}")
                                    return zip_file.read(info.filename)

                        print(f"  ファイルが見つかりません: {norm_file_path}")
                        print(f"  ZIP内のファイル一覧: {[info.filename for info in zip_file.infolist()[:10]]}")
                        return None
                        
        except Exception as e:
            print(f"ZIPアーカイブ内のファイル読み込みエラー: {e}")
            traceback.print_exc()
            return None
    
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
            print(f"ファイルストリーム取得エラー: {e}")
            traceback.print_exc()
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
                
            print(f"ZipHandler: メモリデータからエントリリストを取得中 ({len(archive_data)} バイト)")
            
            # 内部パスが指定されている場合、name_in_arcの考慮が必要
            internal_path = path
            if internal_path:
                # パスを正規化
                internal_path = internal_path.replace('\\', '/')
                print(f"ZipHandler: 内部パスが指定されています: {internal_path}")
                
                # ディレクトリパスの末尾にスラッシュを追加（一貫性のため）
                if not internal_path.endswith('/') and self.is_directory_path(internal_path):
                    internal_path += '/'
                    print(f"ZipHandler: ディレクトリパスに末尾スラッシュを追加: {internal_path}")
            
            # メモリ上のZIPを開く
            bytes_io = io.BytesIO(archive_data)
            with zipfile.ZipFile(bytes_io) as zf:
                # 共通処理メソッドを呼び出し
                entries = self._process_entries(zf, path, "memory_zip", internal_path, from_memory=True)
                print(f"ZipHandler: メモリデータから {len(entries)} 個のエントリを取得")
                return entries
        except Exception as e:
            print(f"ZipHandler: メモリデータからのエントリリスト取得エラー: {e}")
            traceback.print_exc()
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
        """
        try:
            # ファイルパスを正規化
            norm_file_path = file_path.replace('\\', '/')
            print(f"ZipHandler: メモリからファイル読み込み: {norm_file_path}")
            
            # メモリ上でZIPを開く
            with zipfile.ZipFile(io.BytesIO(archive_data)) as zip_file:
                # ZIPファイル構造を取得（name_in_arcなどのマッピング情報取得のため）
                structure = self._get_zip_structure("memory_zip", zip_file)
                
                # ディレクトリパスとファイル名に分解
                dir_path = os.path.dirname(norm_file_path)
                if dir_path:
                    dir_path += '/'
                file_name = os.path.basename(norm_file_path)
                
                # name_in_arcを使って正しいパスを取得
                actual_path = norm_file_path
                if dir_path in structure and file_name in structure[dir_path]['files']:
                    name_in_arc = structure[dir_path]['file_map'].get(file_name, file_name)
                    if name_in_arc != file_name:
                        actual_path = dir_path + name_in_arc
                        print(f"  実際のパスを使用: {norm_file_path} -> {actual_path}")
                
                try:
                    # 実際のパスでファイルを読み込む
                    return zip_file.read(actual_path)
                except KeyError:
                    # 元のパスでも試す
                    try:
                        return zip_file.read(norm_file_path)
                    except KeyError:
                        # 直接一致しない場合、すべてのエントリを検索
                        for info in zip_file.infolist():
                            if info.filename.replace('\\', '/') == norm_file_path:
                                print(f"  完全一致するファイル名を発見: {info.filename}")
                                return zip_file.read(info.filename)
                            
                            # ファイル名部分だけで比較
                            if os.path.basename(info.filename) == file_name:
                                print(f"  ファイル名部分が一致: {info.filename}")
                                return zip_file.read(info.filename)
                                
                        print(f"  ファイルが見つかりません: {norm_file_path}")
                        print(f"  ZIP内のファイル一覧: {[info.filename for info in zip_file.infolist()[:10]]}")
                        return None
        except Exception as e:
            print(f"ZipHandler.read_file_from_bytes エラー: {e}")
            traceback.print_exc()
            return None

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
                print(f"警告: ZIPファイルが見つかりません: {norm_path}")
                return "", ""
            
            # 内部パスを結合
            internal_path = '/'.join(internal_path_parts)
            
            # デバッグ出力を追加
            print(f"ZIPパス分解: {norm_path} → ZIP:{zip_path}, 内部:{internal_path}")
            
            return zip_path, internal_path
        except Exception as e:
            print(f"ZIPパス分解エラー: {str(e)}, パス: {path}")
            traceback.print_exc()
            return "", ""

    def needs_encoding_conversion(self) -> bool:
        """
        このハンドラが文字コード変換を必要とするかどうかを返す
        
        ZIPファイルは特に日本語ファイル名を含む場合にエンコーディング変換が必要
        
        Returns:
            常にTrue（ZIPファイルはエンコーディング変換が必要）
        """
        return True

    def list_all_entries(self, path: str) -> List[EntryInfo]:
        """
        指定したZIPアーカイブ内のすべてのエントリを再帰的に取得する（フィルタリングなし）
        
        Args:
            path: ZIPアーカイブファイルのパス
            
        Returns:
            アーカイブ内のすべてのエントリのリスト
        """
        # パスがZIPファイル自体かZIP内のパスかを判定
        zip_path, internal_path = self._split_path(path)
        
        if not zip_path or not os.path.isfile(zip_path):
            print(f"ZipHandler: 有効なZIPファイルが見つかりません: {path}")
            return []
        
        # 内部パスが指定されている場合はエラー（このメソッドではアーカイブ全体を対象とする）
        if internal_path:
            print(f"ZipHandler: list_all_entriesでは内部パスを指定できません。アーカイブ全体が対象です: {path}")
            # 内部パスを無視してアーカイブファイル全体を処理
        
        # すべてのエントリを格納するリスト
        all_entries = []
        
        try:
            # ZIPファイルを開く
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # ZIP構造を取得
                structure = self._get_zip_structure(zip_path, zf)
                
                # すべてのエントリを処理
                for info in zf.infolist():
                    # Macの隠しフォルダなどをスキップ
                    if '__MACOSX' in info.filename:
                        continue
                        
                    # ファイル名のエンコーディング問題を処理
                    try:
                        # 元のファイル名を保存
                        original_name = info.filename
                        name = original_name
                        
                        # ZIPファイルのエンコーディング問題を修正
                        if hasattr(info, 'orig_filename'):
                            # エンコーディングを試す順序
                            encodings_to_try = ['cp932', 'utf-8', 'euc_jp', 'iso-2022-jp', 'cp437']
                            
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
                        print(f"  ファイル名エンコーディング処理エラー: {e}")
                        name = info.filename
                        original_name = name
                    
                    # ディレクトリかどうかの判定
                    is_dir = name.endswith('/')
                    
                    # ファイル情報からエントリ情報を作成
                    if is_dir:
                        # ディレクトリの場合
                        dir_name = os.path.basename(name.rstrip('/'))
                        entry_path = f"{zip_path}/{name}"
                        
                        all_entries.append(self.create_entry_info(
                            name=dir_name,
                            abs_path=entry_path,
                            size=0,
                            modified_time=None,
                            type=EntryType.DIRECTORY,
                            name_in_arc=original_name
                        ))
                    else:
                        # ファイルの場合
                        file_name = os.path.basename(name)
                        file_path = f"{zip_path}/{name}"
                        
                        # 日付情報の取得
                        timestamp = None
                        if info.date_time != (0, 0, 0, 0, 0, 0):
                            try:
                                timestamp = datetime.datetime(*info.date_time)
                            except:
                                pass
                        
                        # ファイルの拡張子をチェックしてアーカイブなら特別に処理
                        _, ext = os.path.splitext(file_name.lower())
                        entry_type = EntryType.ARCHIVE if ext in self.supported_extensions else EntryType.FILE
                            
                        all_entries.append(self.create_entry_info(
                            name=file_name,
                            abs_path=file_path,
                            size=info.file_size,
                            modified_time=timestamp,
                            type=entry_type,
                            name_in_arc=original_name
                        ))
                        
            print(f"ZipHandler: {zip_path} 内の全エントリ数: {len(all_entries)}")
            return all_entries
            
        except Exception as e:
            print(f"ZipHandler: 全エントリ取得中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            return []

    def list_all_entries_from_bytes(self, archive_data: bytes, path: str = "") -> List[EntryInfo]:
        """
        メモリ上のZIPデータからすべてのエントリを再帰的に取得する（フィルタリングなし）
        
        Args:
            archive_data: ZIPデータのバイト配列
            path: ベースパス（結果のEntryInfoに反映される）
            
        Returns:
            アーカイブ内のすべてのエントリのリスト
        """
        try:
            if not self.can_handle_bytes(archive_data):
                print(f"ZipHandler: このバイトデータは処理できません")
                return []
                
            print(f"ZipHandler: メモリデータからすべてのエントリを取得中 ({len(archive_data)} バイト)")
            
            # メモリ上のZIPを開く
            bytes_io = io.BytesIO(archive_data)
            
            # すべてのエントリを格納するリスト
            all_entries = []
            
            try:
                with zipfile.ZipFile(bytes_io) as zf:
                    # 共通実装を呼び出す（list_all_entriesのメモリバージョン）
                    
                    # エンコーディングを試す順序（一般的な日本語環境向け）
                    encodings_to_try = ['cp932', 'utf-8', 'euc_jp', 'iso-2022-jp', 'cp437']
                    
                    # すべてのエントリを処理
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
                                        if decoded != original_name and not any(ord(c) < 32 for c in decoded):
                                            name = decoded
                                            break
                                    except UnicodeError:
                                        continue
                        except Exception as e:
                            # どんな例外が発生してもオリジナルのファイル名を使用
                            print(f"  ファイル名エンコーディング処理エラー: {e}")
                            name = info.filename
                            original_name = name
                        
                        # Macの隠しフォルダなどをスキップ
                        if '__MACOSX' in name:
                            continue
                            
                        # ディレクトリか判定
                        is_dir = name.endswith('/')
                        
                        # ファイル情報からエントリ情報を作成
                        if is_dir:
                            # ディレクトリの場合
                            dir_name = os.path.basename(name.rstrip('/'))
                            entry_path = f"{path}/{name}" if path else name
                            
                            all_entries.append(self.create_entry_info(
                                name=dir_name,
                                abs_path=entry_path,
                                size=0,
                                modified_time=None,
                                type=EntryType.DIRECTORY,
                                name_in_arc=original_name
                            ))
                        else:
                            # ファイルの場合
                            file_name = os.path.basename(name)
                            file_path = f"{path}/{name}" if path else name
                            
                            # 日付情報の取得
                            timestamp = None
                            if info.date_time != (0, 0, 0, 0, 0, 0):
                                try:
                                    timestamp = datetime.datetime(*info.date_time)
                                except:
                                    pass
                            
                            # ファイルの拡張子をチェックしてアーカイブなら特別に処理
                            _, ext = os.path.splitext(file_name.lower())
                            entry_type = EntryType.ARCHIVE if ext in self.supported_extensions else EntryType.FILE
                                
                            all_entries.append(self.create_entry_info(
                                name=file_name,
                                abs_path=file_path,
                                size=info.file_size,
                                modified_time=timestamp,
                                type=entry_type,
                                name_in_arc=original_name
                            ))
                    
                    print(f"ZipHandler: メモリデータから全 {len(all_entries)} エントリを取得しました")
                    return all_entries
            except Exception as e:
                print(f"ZipHandler: ZIPファイルオープンエラー: {e}")
                traceback.print_exc()
                return []
                
        except Exception as e:
            print(f"ZipHandler: メモリからの全エントリ取得エラー: {e}")
            traceback.print_exc()
            return []
