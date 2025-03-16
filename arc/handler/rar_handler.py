"""
rarfileパッケージを利用したRARアーカイブハンドラ

rarfileパッケージを使用してRARアーカイブ操作を行うハンドラモジュール
より安定したRAR形式の処理を提供するため、専用のハンドラとして実装
"""
import os
import io
import tempfile
import traceback
import datetime
from typing import List, Optional, Dict, BinaryIO, Tuple

try:
    import rarfile
    RARFILE_AVAILABLE = True
except ImportError:
    RARFILE_AVAILABLE = False
    # printを置き換え
    from logutils import log_print, ERROR
    log_print(ERROR, "RarHandler: rarfileパッケージが見つかりません。'pip install rarfile'でインストールしてください。", name="arc.handler.RarHandler")
    log_print(ERROR, "RarHandler: また、UnRARが必要です - Windows版は自動的にダウンロードされます。", name="arc.handler.RarHandler")
    log_print(ERROR, "RarHandler: Unix系では別途UnRARをインストールしてください。", name="arc.handler.RarHandler")

from ..arc import EntryInfo, EntryType
from .handler import ArchiveHandler


class RarHandler(ArchiveHandler):
    """
    rarfileパッケージを使用したRARアーカイブハンドラ
    
    RARファイルをより確実に処理するための専用ハンドラ
    """
    
    # RARファイルの拡張子
    SUPPORTED_FORMATS = ['.rar']

    
    def __init__(self):
        """RARアーカイブハンドラを初期化する"""
        super().__init__()  # 親クラス初期化を追加
        # rarfileが利用可能かチェック
        if not RARFILE_AVAILABLE:
            self._available = False
            self._supported_formats = []
            return
        self.debug = False
            
        self.debug_info(f"rarfileパッケージが利用可能です (バージョン: {rarfile.__version__})")
        
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
            if os.name != 'nt':
                # Linux/Macなどでは通常別途インストールが必要
                pass
        except Exception as e:
            self.debug_error(f"rarfileの設定中にエラーが発生しました: {e}")
    
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
                  
        # 正規化したパスを使用
        norm_path = path.replace('\\', '/')
        
        # パスの末尾にスラッシュがある場合は削除して判定する
        if norm_path.endswith('/'):
            norm_path = norm_path[:-1]
        
        # 拡張子のみでチェック
        _, ext = os.path.splitext(norm_path.lower())
        self.debug_info(f"拡張子チェック: {ext}")
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
            self.debug_info(f"エントリ一覧を取得: {path}")
            # RARファイルを開く
            with rarfile.RarFile(path) as rf:
                self.debug_info(f"RARアーカイブパス: {path}, 内部パス: {internal_path}")
                
                # エントリ一覧を取得する共通関数を呼び出す
                result = self._get_entries_from_rarfile(rf, internal_path)
                
                self.debug_info(f"{len(result)} エントリを返します")
                return result
        except Exception as e:
            if self.debug:
                self.debug_error(f"エントリ一覧取得エラー: {e}", trace=True)
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
                # 相対パスを設定したファイルエントリを作成
                entry = self.create_entry_info(
                    name=os.path.basename(internal_path),
                    abs_path=internal_path,
                    size=file_info.file_size,
                    modified_time=datetime.datetime(*file_info.date_time),
                    type=EntryType.FILE if not file_info.is_dir() else EntryType.DIRECTORY,
                    name_in_arc=internal_path  # オリジナルの内部パスを設定
                )
                result.append(entry)
                return result
            except Exception as e:
                if self.debug:
                    self.debug_error(f"内部パスの情報取得エラー: {e}", trace=True)
                    
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
                        dir_full_path = dir_path + '/'  # ディレクトリの場合は末尾にスラッシュを追加
                        
                        # 相対パスを設定したディレクトリエントリを作成
                        result.append(self.create_entry_info(
                            name=dir_name,
                            abs_path=dir_path,
                            size=0,
                            modified_time=None,
                            type=EntryType.DIRECTORY,
                            name_in_arc=dir_full_path  # 書庫内の相対パス
                        ))
                    continue
            
            # 相対パスを設定したエントリ情報を作成
            entry = self.create_entry_info(
                name=os.path.basename(item_path),
                abs_path=item_path,
                size=item.file_size,
                modified_time=datetime.datetime(*item.date_time),
                type=EntryType.FILE if not item.is_dir() else EntryType.DIRECTORY,
                name_in_arc=item_path  # 書庫内の相対パス
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
            self.debug_info(f"メモリ上のRARデータ ({len(data)} バイト) からエントリリスト取得")
            
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
                    
            self.debug_info(f"{len(result)} エントリを返します")
            return result
        except Exception as e:
            if self.debug:
                self.debug_error(f"バイトデータからのエントリ一覧取得エラー: {e}", trace=True)
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
                    return self.create_entry_info(
                        name=os.path.basename(internal_path),
                        abs_path=internal_path,
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
                            # ディレクトリとして存在する
                            return self.create_entry_info(
                                name=os.path.basename(internal_path.rstrip('/')),
                                abs_path=internal_path,
                                size=0,
                                type=EntryType.DIRECTORY
                            )
                            
                    return None
        except Exception as e:
            if self.debug:
                self.debug_error(f"エントリ情報取得エラー: {e}", trace=True)
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
                self.debug_error(f"ファイル読み込みエラー: {e}", trace=True)
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
        
        self.debug_info(f"アーカイブ内ファイル読み込み: {archive_path} -> {file_path}")
        
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
                # ディレクトリ内容は空バイトを返す
                return b''
            
            # ファイルが存在するか確認
            try:
                info = rf.getinfo(normal_path)
            except KeyError:
                self.debug_error(f"ファイルが見つかりません: {normal_path}")
                return None
                
            # ディレクトリの場合は読み込みをスキップ
            if info.isdir():
                return b''
            
            # ファイルを読み込む
            with rf.open(normal_path) as f:
                content = f.read()
                
            self.debug_info(f"ファイル読み込み成功: {len(content)} バイト")
            return content
            
        except rarfile.BadRarFile as e:
            self.debug_error(f"不正なRARファイル: {e}")
            return None
        except rarfile.RarCRCError as e:
            self.debug_error(f"CRCエラー: {e}")
            return None
        except rarfile.PasswordRequired as e:
            self.debug_error(f"パスワードが必要: {e}")
            return None
        except rarfile.NeedFirstVolume as e:
            self.debug_error(f"最初のボリュームが必要: {e}")
            return None
        except io.UnsupportedOperation as e:
            # ディレクトリの読み込み試行時に発生
            self.debug_error(f"サポートされていない操作: {e}")
            return None
        except Exception as e:
            self.debug_error(f"ファイル読み込み中にエラー: {e}", trace=True)
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
        
        self.debug_info(f"ファイルストリーム取得: {path}")
        
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
            self.debug_error(f"メモリストリーム作成エラー: {e}", trace=True)
        
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
            self.debug_warning(f"有効なRARファイルが見つかりません: {path}")
            return []
        
        # 内部パスが指定されている場合はエラー（このメソッドではアーカイブ全体を対象とする）
        if internal_path:
            self.debug_warning(f"list_all_entriesでは内部パスを指定できません。アーカイブ全体が対象です: {path}")
            # 内部パスを無視してアーカイブファイル全体を処理
        
        try:
            # RARファイルを開く
            with rarfile.RarFile(archive_path) as rf:
                # 共通関数を使用してすべてのエントリを取得
                all_entries = self._get_all_entries_from_rarfile(rf, archive_path)
                self.debug_info(f"{archive_path} 内の全エントリ数: {len(all_entries)}")
                return all_entries
        except Exception as e:
            self.debug_error(f"全エントリ取得中にエラーが発生しました: {e}", trace=True)
            return []

    def _get_all_entries_from_rarfile(self, rf: 'rarfile.RarFile', archive_path: 'str') -> List[EntryInfo]:
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
            
            # 相対パスを設定したファイル情報からエントリ情報を作成
            if is_dir:
                # ディレクトリの場合
                dir_name = os.path.basename(item_path.rstrip('/'))
                
                all_entries.append(self.create_entry_info(
                    name=dir_name,
                    rel_path=item_path,
                    name_in_arc=item_path,  # 書庫内の相対パス
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
                #print(f"RarHandler: エントリ: {file_name}, パス: {item_path}")
                all_entries.append(self.create_entry_info(
                    name=file_name,
                    rel_path=item_path,
                    name_in_arc=item_path,  # 書庫内の相対パス
                    size=info.file_size,
                    modified_time=mod_time,
                    type=EntryType.FILE
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
                self.debug_warning(f"このバイトデータは処理できません")
                return []
                    
            self.debug_info(f"メモリデータからすべてのエントリを取得中 ({len(archive_data)} バイト)")
            
            # 一時ファイルに保存
            temp_file = self.save_to_temp_file(archive_data, '.rar')
            if not temp_file:
                self.debug_error(f"一時ファイル作成に失敗しました")
                return []
            
            try:
                # 一時ファイルを使用してRARを開く
                with rarfile.RarFile(temp_file) as rf:
                    # 共通関数を使用してすべてのエントリを取得
                    all_entries = self._get_all_entries_from_rarfile(rf,"")
                    self.debug_info(f"メモリデータから全 {len(all_entries)} エントリを取得しました")
                    return all_entries
            finally:
                # 一時ファイルを削除
                self.cleanup_temp_file(temp_file)
        
        except Exception as e:
            self.debug_error(f"メモリからの全エントリ取得エラー: {e}", trace=True)
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
            
        self.debug_info(f"メモリ上のRARデータから '{file_path}' を読み込み中")
        
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
                    content = rf.read(normal_path)
                    self.debug_info(f"ファイル読み込み成功: {len(content)} バイト")
                    return content
                except KeyError:
                    self.debug_error(f"ファイルが見つかりません: {normal_path}")
                    return None
                except Exception as e:
                    self.debug_error(f"ファイル読み込み中にエラー: {e}", trace=True)
                    return None
            except Exception as e:
                self.debug_error(f"RARファイルをオープンできません: {e}", trace=True)
                return None
        except Exception as e:
            self.debug_error(f"メモリデータからの読み込みエラー: {e}", trace=True)
            return None
        finally:
            # 一時ファイルを削除
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    self.debug_warning(f"一時ファイル削除エラー: {e}")


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
