"""
rarfileパッケージを利用したRARアーカイブハンドラ

rarfileパッケージを使用してRARアーカイブ操作を行うハンドラモジュール
より安定したRAR形式の処理を提供するため、専用のハンドラとして実装
"""

import os
import datetime
import tempfile
import io
from typing import List, Optional, Dict, BinaryIO, Tuple

try:
    import rarfile
    RARFILE_AVAILABLE = True
except ImportError:
    RARFILE_AVAILABLE = False
    print("RarHandler: rarfileパッケージが見つかりません。'pip install rarfile'でインストールしてください。")
    print("RarHandler: また、UnRARが必要です - Windows版は自動的にダウンロードされます。")
    print("RarHandler: Unix系では別途UnRARをインストールしてください。")

from .arc import ArchiveHandler, EntryInfo, EntryType


class RarHandler(ArchiveHandler):
    """
    rarfileパッケージを使用したRARアーカイブハンドラ
    
    RARファイルをより確実に処理するための専用ハンドラ
    """
    
    # RARファイルの拡張子
    SUPPORTED_FORMATS = ['.rar']
    
    def __init__(self):
        """RARアーカイブハンドラを初期化する"""
        # rarfileが利用可能かチェック
        if not RARFILE_AVAILABLE:
            self._available = False
            self._supported_formats = []
            return
            
        print(f"RarHandler: rarfileパッケージが利用可能です (バージョン: {rarfile.__version__})")
        
        # rarfileの設定
        self._configure_rarfile()
        
        # キャッシュとメタデータ
        self._rar_cache: Dict[str, rarfile.RarFile] = {}
        self._temp_files_cache: Dict[str, str] = {}
        
        # ハンドラが利用可能
        self._available = True
        self._supported_formats = self.SUPPORTED_FORMATS

    def _configure_rarfile(self) -> None:
        """rarfileパッケージの設定を行う"""
        try:
            # パスワードなしでも可能な限り処理する
            rarfile.HANDLE_BAD_PASSWORD = True
            
            # Unicode文字をサポート
            rarfile.PATH_SEP = '/'
            
            # 一時ディレクトリを設定
            rarfile.EXTRACT_BUFFERED_MEMORY = True  # メモリバッファを使う

            rarfile.USE_DATETIME = True  # datetime型を使用
            
            # WinRAR/UnRAR実行ファイルのパスを設定（Windows以外）
            if os.name != 'nt':  # Windowsでない場合
                # Linuxの一般的な場所をチェック
                unrar_paths = [
                    '/usr/bin/unrar',
                    '/usr/local/bin/unrar',
                    '/opt/local/bin/unrar'
                ]
                for path in unrar_paths:
                    if os.path.exists(path):
                        rarfile.UNRAR_TOOL = path
                        print(f"RarHandler: UnRAR実行ファイルを検出: {path}")
                        break
        except Exception as e:
            print(f"RarHandler: rarfileの設定中にエラーが発生しました: {e}")
    
    @property
    def supported_extensions(self) -> List[str]:
        """このハンドラがサポートするファイル拡張子のリスト"""
        return self._supported_formats
    
    def can_handle(self, path: str) -> bool:
        """
        指定されたパスをこのハンドラで処理できるかどうかを判定する
        
        Args:
            path: 判定対象のパス
            
        Returns:
            処理可能な場合はTrue、そうでなければFalse
        """
        # rarfileが利用できない場合は常にFalse
        if not RARFILE_AVAILABLE or not self._available:
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
        
        # RARファイルかチェック
        if ext not in self._supported_formats:
            return False
            
        # 実際にRARファイルとして開けるかチェック
        try:
            with rarfile.RarFile(path) as rf:
                return True
        except Exception as e:
            print(f"RarHandler: {path} をRARとして処理できません: {e}")
            return False
    
    def can_handle_bytes(self, data: bytes = None, path: str = None) -> bool:
        """
        バイトデータまたはパス指定でバイトデータ解凍が可能かどうかを判定する
        
        Args:
            data: 判定するバイトデータ（省略可能）
            path: 判定するファイルのパス（省略可能、拡張子での判定に使用）
            
        Returns:
            バイトデータから解凍可能な場合はTrue、そうでなければFalse
        """
        # rarfileが利用できない場合はFalse
        if not RARFILE_AVAILABLE or not self._available:
            return False
            
        # パスが指定されていれば、その拡張子をチェック
        if path:
            _, ext = os.path.splitext(path.lower())
            return ext in self._supported_formats
        
        # バイトデータが指定されていない場合はFalse
        if not data:
            return False
            
        # バイトデータがRARのシグネチャで始まるかチェック
        return data.startswith(b'Rar!\x1a\x07')
    
    def list_entries(self, path: str, internal_path: str = "") -> List[EntryInfo]:
        """
        RARアーカイブ内のエントリ一覧を取得する
        
        Args:
            path: RARファイルへのパス
            internal_path: アーカイブ内の相対パス（指定した場合はそのディレクトリ内のエントリのみ取得）
            
        Returns:
            エントリ情報のリスト
        """
        if not self.can_handle(path):
            return []
            
        result = []
        
        if not RARFILE_AVAILABLE:
            return result
            
        try:
            print(f"RarHandler: エントリ一覧を取得: {path}")
            # RARファイルを開く
            with rarfile.RarFile(path) as rf:
                print(f"RarHandler: RARアーカイブパス: {path}, 内部パス: {internal_path}")
                
                # エントリ一覧を取得する共通関数を呼び出す
                result = self._get_entries_from_rarfile(rf, internal_path)
                
                print(f"RarHandler: {len(result)} エントリを返します")
                return result
        except Exception as e:
            if self.debug:
                print(f"RarHandler: エントリ一覧取得エラー: {e}")
            return []

    def _get_entries_from_rarfile(self, rf: 'rarfile.RarFile', internal_path: str = "") -> List[EntryInfo]:
        """
        rarfileオブジェクトからエントリ一覧を取得する共通関数
        
        Args:
            rf: rarfileオブジェクト
            internal_path: アーカイブ内の相対パス（指定した場合はそのディレクトリ内のエントリのみ取得）
            
        Returns:
            エントリ情報のリスト
        """
        result = []
        
        # 内部パスがファイルの場合は単一エントリを返す
        if internal_path and not internal_path.endswith('/'):
            try:
                file_info = rf.getinfo(internal_path)
                # ファイルエントリを作成
                entry = EntryInfo(
                    name=os.path.basename(internal_path),
                    path=internal_path,  # 相対パスを使用
                    size=file_info.file_size,
                    modified_time=datetime.datetime(*file_info.date_time),
                    type=EntryType.FILE if not file_info.is_dir() else EntryType.DIRECTORY
                )
                result.append(entry)
                return result
            except Exception as e:
                if self.debug:
                    print(f"RarHandler: 内部パスの情報取得エラー: {e}")
                    
        # 一意なディレクトリパスを追跡するセット
        unique_dirs = set()
        
        # 全エントリを走査
        for item in rf.infolist():
            item_path = item.filename
            
            # MacOSXのメタデータは無視
            if '__MACOSX/' in item_path or '.DS_Store' in item_path:
                continue
            
            # 内部パスが指定されている場合はフィルタリング
            if internal_path:
                if not item_path.startswith(internal_path):
                    continue
                    
                # 内部パスより深い階層のアイテムは除外されないように修正
                rel_path = item_path[len(internal_path):]
                if rel_path.startswith('/'):
                    rel_path = rel_path[1:]
                    
                # ディレクトリ直下のファイル/ディレクトリのみを追加
                parts = rel_path.split('/')
                if len(parts) > 1:
                    # サブディレクトリの場合、最初の部分だけをディレクトリとして追加
                    dir_name = parts[0]
                    if dir_name and dir_name not in unique_dirs:
                        unique_dirs.add(dir_name)
                        dir_path = os.path.join(internal_path, dir_name).replace('\\', '/')
                        
                        # ディレクトリエントリを作成
                        result.append(EntryInfo(
                            name=dir_name,
                            path=dir_path,
                            size=0,
                            modified_time=None,
                            type=EntryType.DIRECTORY
                        ))
                    continue
            
            # エントリ情報を作成
            entry = EntryInfo(
                name=os.path.basename(item_path),
                path=item_path,  # 相対パスを使用
                size=item.file_size,
                modified_time=datetime.datetime(*item.date_time),
                type=EntryType.FILE if not item.is_dir() else EntryType.DIRECTORY
            )
            result.append(entry)
        
        return result

    def list_entries_from_bytes(self, data: bytes, internal_path: str = "") -> List[EntryInfo]:
        """
        バイトデータからRARアーカイブ内のエントリ一覧を取得する
        
        Args:
            data: RARファイルのバイトデータ
            internal_path: アーカイブ内の相対パス（指定した場合はそのディレクトリ内のエントリのみ取得）
            
        Returns:
            エントリ情報のリスト
        """
        if not self.can_handle_bytes(data):
            return []
            
        result = []
        
        if not RARFILE_AVAILABLE:
            return result
            
        try:
            print(f"RarHandler: メモリ上のRARデータ ({len(data)} バイト) からエントリリスト取得")
            
            # 一時ファイルを作成
            with tempfile.NamedTemporaryFile(delete=False, suffix='.rar') as tmp:
                tmp_path = tmp.name
                tmp.write(data)
            
            try:
                # 一時ファイルからRARを開く
                with rarfile.RarFile(tmp_path) as rf:
                    # 共通関数を使用してエントリを取得
                    result = self._get_entries_from_rarfile(rf, internal_path)
            finally:
                # 一時ファイルを削除
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
            print(f"RarHandler: {len(result)} エントリを返します")
            return result
        except Exception as e:
            if self.debug:
                print(f"RarHandler: バイトデータからのエントリ一覧取得エラー: {e}")
            return []

    def get_entry_info(self, path: str) -> Optional[EntryInfo]:
        """
        指定されたパスのエントリ情報を取得する
        
        Args:
            path: 'rarファイルのパス/内部ファイルパス' 形式の文字列
            
        Returns:
            エントリ情報、または存在しない場合はNone
        """
        if not RARFILE_AVAILABLE:
            return None
            
        try:
            # パスからRARファイルと内部パスを抽出
            archive_path, internal_path = self._split_path(path)
            
            if not archive_path or not internal_path:
                return None
                
            # RARファイルを開いてエントリ情報を取得
            with rarfile.RarFile(archive_path) as rf:
                try:
                    info = rf.getinfo(internal_path)
                    return EntryInfo(
                        name=os.path.basename(internal_path),
                        path=internal_path,  # 相対パスを使用
                        size=info.file_size,
                        modified_time=datetime.datetime(*info.date_time),
                        type=EntryType.FILE if not info.is_dir() else EntryType.DIRECTORY
                    )
                except:
                    # 指定されたパスがディレクトリの場合（RARは明示的なディレクトリエントリを持たない場合がある）
                    if not internal_path.endswith('/'):
                        internal_path += '/'
                    
                    # そのディレクトリ内に何かファイルがあるか確認
                    for item in rf.infolist():
                        if item.filename.startswith(internal_path):
                            return EntryInfo(
                                name=os.path.basename(internal_path.rstrip('/')),
                                path=internal_path,  # 相対パスを使用
                                size=0,
                                modified_time=None,
                                type=EntryType.DIRECTORY
                            )
                            
                    return None
        except Exception as e:
            if self.debug:
                print(f"RarHandler: エントリ情報取得エラー: {e}")
            return None
    
    def read_file(self, path: str) -> Optional[bytes]:
        """
        RARアーカイブ内のファイルを読み込む
        
        Args:
            path: 'rarファイルのパス/内部ファイルパス' 形式の文字列
            
        Returns:
            ファイルの内容のバイト列、または読み込めない場合はNone
        """
        if not RARFILE_AVAILABLE:
            return None
            
        try:
            # パスからRARファイルと内部パスを抽出
            archive_path, internal_path = self._split_path(path)
            
            if not archive_path or not internal_path:
                return None
                
            # RARファイルを開いて内部ファイルを読み込む
            with rarfile.RarFile(archive_path) as rf:
                return rf.read(internal_path)
        except Exception as e:
            if self.debug:
                print(f"RarHandler: ファイル読み込みエラー: {e}")
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
        if not RARFILE_AVAILABLE or not self._available:
            return None
        
        print(f"RarHandler: アーカイブ内ファイル読み込み: {archive_path} -> {file_path}")
        
        try:
            # RARファイルを開く
            if archive_path in self._rar_cache:
                rf = self._rar_cache[archive_path]
            else:
                rf = rarfile.RarFile(archive_path)
                self._rar_cache[archive_path] = rf
            
            # 正規化されたパス
            normal_path = file_path.replace('\\', '/')
            
            # まずエントリ情報を取得して、ディレクトリかファイルかを確認
            entry_info = self.get_entry_info(self._join_paths(archive_path, file_path))
            
            # ディレクトリの場合は特別に処理
            if entry_info and entry_info.type == EntryType.DIRECTORY:
                print(f"RarHandler: 指定されたパスはディレクトリです: {file_path}")
                return None
            
            # ファイルが存在するか確認
            try:
                info = rf.getinfo(normal_path)
            except KeyError:
                print(f"RarHandler: ファイルが見つかりません: {normal_path}")
                
                # 末尾にスラッシュを追加して、ディレクトリとして再試行
                if not normal_path.endswith('/'):
                    try:
                        dir_path = normal_path + '/'
                        info = rf.getinfo(dir_path)
                        print(f"RarHandler: 指定されたパスはディレクトリです: {dir_path}")
                        return None
                    except KeyError:
                        pass
                
                return None
                
            # ディレクトリの場合は読み込みをスキップ
            if info.isdir():
                print(f"RarHandler: 指定されたパスはディレクトリです: {normal_path}")
                return None
            
            # ファイルを読み込む
            with rf.open(normal_path) as f:
                content = f.read()
                
            print(f"RarHandler: ファイル読み込み成功: {len(content)} バイト")
            return content
            
        except rarfile.BadRarFile as e:
            print(f"RarHandler: 不正なRARファイル: {e}")
            return None
        except rarfile.RarCRCError as e:
            print(f"RarHandler: CRCエラー: {e}")
            return None
        except rarfile.PasswordRequired as e:
            print(f"RarHandler: パスワードが必要: {e}")
            return None
        except rarfile.NeedFirstVolume as e:
            print(f"RarHandler: 最初のボリュームが必要: {e}")
            return None
        except io.UnsupportedOperation as e:
            # ディレクトリの読み込み試行時に発生
            print(f"RarHandler: サポートされていない操作: {e}")
            return None
        except Exception as e:
            print(f"RarHandler: ファイル読み込み中にエラー: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_stream(self, path: str) -> Optional[BinaryIO]:
        """
        指定されたパスのファイルのストリームを取得する
        
        Args:
            path: ストリームを取得するファイルのパス
            
        Returns:
            ファイルストリーム。取得できない場合はNone
        """
        if not RARFILE_AVAILABLE or not self._available:
            return None
        
        print(f"RarHandler: ファイルストリーム取得: {path}")
        
        # パスがアーカイブファイル自体かアーカイブ内のパスかを判定
        archive_path, internal_path = self._split_path(path)
        
        # アーカイブファイルの場合は通常のファイルとして扱う
        if not internal_path:
            if os.path.isfile(archive_path):
                return open(archive_path, 'rb')
            return None
        
        # アーカイブ内のファイルの場合は、メモリにロードしてからIOオブジェクトとして返す
        try:
            content = self.read_archive_file(archive_path, internal_path)
            if content is not None:
                return io.BytesIO(content)
        except Exception as e:
            print(f"RarHandler: メモリストリーム作成エラー: {e}")
        
        return None
    
    def is_directory(self, path: str) -> bool:
        """
        指定したパスがディレクトリかどうかを判定する
        
        Args:
            path: 判定するパス
            
        Returns:
            ディレクトリの場合はTrue、そうでない場合はFalse
        """
        entry_info = self.get_entry_info(path)
        return entry_info is not None and entry_info.type == EntryType.DIRECTORY
    
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
    
    def _split_path(self, path: str) -> Tuple[str, str]:
        """
        パスをアーカイブファイルのパスと内部パスに分割する
        
        Args:
            path: 分割するパス
            
        Returns:
            (アーカイブファイルのパス, 内部パス) のタプル
        """
        # パスの正規化 (バックスラッシュをスラッシュに変換)
        norm_path = self.normalize_path(path)
        
        # アーカイブファイル自体かどうか確認
        if os.path.isfile(norm_path):
            _, ext = os.path.splitext(norm_path.lower())
            if ext in self._supported_formats:
                # パス自体がアーカイブファイル
                return norm_path, ""
        
        # パスを分解して、RARファイルを含むかをチェック
        components = norm_path.split('/')
        test_path = ''
        
        for i in range(len(components)):
            # 現在のコンポーネントを追加
            if test_path:
                test_path += '/'
            test_path += components[i]
            
            # これがRARファイルかどうか確認
            if os.path.isfile(test_path):
                _, ext = os.path.splitext(test_path.lower())
                if ext in self._supported_formats:
                    # RARファイルを発見
                    internal_path = '/'.join(components[i+1:])
                    return test_path, internal_path
        
        # RARファイルが見つからなかった
        return "", ""
    
    def list_all_entries(self, path: str) -> List[EntryInfo]:
        """
        指定したRARアーカイブ内のすべてのエントリを再帰的に取得する（フィルタリングなし）
        
        Args:
            path: RARアーカイブファイルのパス
            
        Returns:
            アーカイブ内のすべてのエントリのリスト
        """
        # パスがRARファイル自体かRAR内のパスかを判定
        archive_path, internal_path = self._split_path(path)
        
        if not archive_path or not os.path.isfile(archive_path):
            print(f"RarHandler: 有効なRARファイルが見つかりません: {path}")
            return []
        
        # 内部パスが指定されている場合はエラー（このメソッドではアーカイブ全体を対象とする）
        if internal_path:
            print(f"RarHandler: list_all_entriesでは内部パスを指定できません。アーカイブ全体が対象です: {path}")
            # 内部パスを無視してアーカイブファイル全体を処理
        
        try:
            # RARファイルを開く
            with rarfile.RarFile(archive_path) as rf:
                # 共通関数を使用してすべてのエントリを取得
                all_entries = self._get_all_entries_from_rarfile(rf)
                print(f"RarHandler: {archive_path} 内の全エントリ数: {len(all_entries)}")
                return all_entries
        except Exception as e:
            print(f"RarHandler: 全エントリ取得中にエラーが発生しました: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return []

    def _get_all_entries_from_rarfile(self, rf: 'rarfile.RarFile') -> List[EntryInfo]:
        """
        rarfileオブジェクトからすべてのエントリを取得する共通関数
        
        Args:
            rf: rarfileオブジェクト
            
        Returns:
            すべてのエントリ情報のリスト
        """
        all_entries = []
        
        # 全エントリを走査
        for info in rf.infolist():
            # MacOSXのメタデータなどをスキップ
            if '__MACOSX/' in info.filename or '.DS_Store' in info.filename:
                continue
            
            item_path = info.filename
            
            # ディレクトリかどうかの判定
            is_dir = info.isdir()
            
            # ファイル情報からエントリ情報を作成
            if is_dir:
                # ディレクトリの場合
                dir_name = os.path.basename(item_path.rstrip('/'))
                
                all_entries.append(EntryInfo(
                    name=dir_name,
                    path=item_path,  # 相対パスを使用
                    size=0,
                    modified_time=None,
                    type=EntryType.DIRECTORY
                ))
            else:
                # ファイルの場合
                file_name = os.path.basename(item_path)
                
                # 日付情報の取得
                try:
                    mod_time = datetime.datetime(*info.date_time)
                except:
                    mod_time = None
                
                # ファイルの拡張子をチェックしてアーカイブなら特別に処理
                _, ext = os.path.splitext(file_name.lower())
                entry_type = EntryType.ARCHIVE if ext in self.supported_extensions else EntryType.FILE
                    
                all_entries.append(EntryInfo(
                    name=file_name,
                    path=item_path,  # 相対パスを使用
                    size=info.file_size,
                    modified_time=mod_time,
                    type=entry_type
                ))
        
        return all_entries

    def list_all_entries_from_bytes(self, archive_data: bytes, path: str = "") -> List[EntryInfo]:
        """
        メモリ上のRARデータからすべてのエントリを再帰的に取得する（フィルタリングなし）
        
        Args:
            archive_data: RARデータのバイト配列
            path: ベースパス（結果のEntryInfoに反映される）
            
        Returns:
            アーカイブ内のすべてのエントリのリスト。サポートしていない場合は空リスト
        """
        try:
            if not self.can_handle_bytes(archive_data):
                print(f"RarHandler: このバイトデータは処理できません")
                return []
                    
            print(f"RarHandler: メモリデータからすべてのエントリを取得中 ({len(archive_data)} バイト)")
            
            # 一時ファイルに保存
            temp_file = self.save_to_temp_file(archive_data, '.rar')
            if not temp_file:
                print(f"RarHandler: 一時ファイル作成に失敗しました")
                return []
            
            try:
                # 一時ファイルを使用してRARを開く
                with rarfile.RarFile(temp_file) as rf:
                    # 共通関数を使用してすべてのエントリを取得
                    all_entries = self._get_all_entries_from_rarfile(rf)
                    print(f"RarHandler: メモリデータから全 {len(all_entries)} エントリを取得しました")
                    return all_entries
            finally:
                # 一時ファイルを削除
                self.cleanup_temp_file(temp_file)
        
        except Exception as e:
            print(f"RarHandler: メモリからの全エントリ取得エラー: {e}")
            import traceback
            traceback.print_exc()
            return []

    def read_file_from_bytes(self, archive_data: bytes, file_path: str) -> Optional[bytes]:
        """
        メモリ上のアーカイブデータから特定のファイルを読み込む
        
        Args:
            archive_data: アーカイブデータのバイト配列
            file_path: アーカイブ内のファイルパス
            
        Returns:
            ファイルの内容。読み込みに失敗した場合はNone
        """
        if not RARFILE_AVAILABLE or not self._available:
            return None
            
        print(f"RarHandler: メモリ上のRARデータから '{file_path}' を読み込み中")
        
        # 一時ファイルを使用して確実に処理
        temp_file = None
        try:
            # 一時ファイルに保存
            with tempfile.NamedTemporaryFile(delete=False, suffix='.rar') as tmp:
                temp_file = tmp.name
                tmp.write(archive_data)
                
            # RARファイルを開く
            try:
                rf = rarfile.RarFile(temp_file)
                
                # 正規化されたパス（相対パス）
                normal_path = file_path.replace('\\', '/')
                
                # ファイルを読み込む
                try:
                    with rf.open(normal_path) as f:
                        content = f.read()
                        
                    print(f"RarHandler: ファイル読み込み成功: {len(content)} バイト")
                    return content
                except KeyError:
                    print(f"RarHandler: ファイルが見つかりません: {normal_path}")
                    return None
                except Exception as e:
                    print(f"RarHandler: ファイル読み込みエラー: {e}")
                    return None
            except Exception as e:
                print(f"RarHandler: RARファイルをオープンできません: {e}")
                return None
        except Exception as e:
            print(f"RarHandler: メモリデータからの読み込みエラー: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return None
        finally:
            # 一時ファイルを削除
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass

    def save_to_temp_file(self, data: bytes, suffix: str = '.tmp') -> Optional[str]:
        """
        バイトデータを一時ファイルに保存する
        
        Args:
            data: 保存するバイトデータ
            suffix: 一時ファイルの拡張子
            
        Returns:
            一時ファイルのパス。失敗した場合はNone
        """
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = tmp.name
                tmp.write(data)
                return tmp_path
        except Exception as e:
            print(f"一時ファイルの作成に失敗しました: {e}")
            return None

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
                    print(f"一時ファイルの削除に失敗しました: {e}")

    def _join_paths(self, base_path: str, rel_path: str) -> str:
        """
        ベースパスと相対パスを結合する
        
        Args:
            base_path: ベースパス
            rel_path: 相対パス
            
        Returns:
            結合されたパス
        """
        if rel_path:
            # スラッシュを統一
            base = base_path.rstrip('/')
            rel = rel_path.lstrip('/')
            return f"{base}/{rel}"
        return base_path
