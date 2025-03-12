"""
アーカイブ操作のユーティリティ関数

アーカイブ関連の共通操作を提供するヘルパー関数群
"""

import os
import subprocess
import shutil
from typing import List, Tuple, Dict, Any, Optional, Union


def find_executable(name: str) -> str:
    """
    指定した名前の実行ファイルをPATHから検索する
    
    Args:
        name: 検索する実行ファイル名
        
    Returns:
        実行ファイルのパス、見つからない場合は空文字列
    """
    return shutil.which(name) or ""


def run_command(cmd: List[str], timeout: int = None, encoding: str = None) -> Tuple[int, str, str]:
    """
    外部コマンドを実行し、結果を取得する
    
    Args:
        cmd: 実行するコマンドとその引数のリスト
        timeout: タイムアウト秒数（None=無制限）
        encoding: 出力のエンコーディング（None=自動検出）
        
    Returns:
        (リターンコード, 標準出力, 標準エラー出力) のタプル
    """
    try:
        # バイナリモードでプロセスを実行
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False  # シェルインジェクションを防止
        )
        
        # 出力を取得
        stdout_data, stderr_data = process.communicate(timeout=timeout)
        
        # エンコーディングが指定されていない場合は、OSに応じて適切なものを選択
        if encoding is None:
            if os.name == 'nt':
                encoding = 'cp932'  # Windows日本語環境
            else:
                encoding = 'utf-8'  # Unix系
        
        # デコードする
        try:
            stdout_text = stdout_data.decode(encoding, errors='replace')
            stderr_text = stderr_data.decode(encoding, errors='replace')
        except UnicodeDecodeError:
            # デコードに失敗した場合は別のエンコーディングを試す
            try:
                if encoding == 'cp932':
                    stdout_text = stdout_data.decode('utf-8', errors='replace')
                    stderr_text = stderr_data.decode('utf-8', errors='replace')
                else:
                    stdout_text = stdout_data.decode('cp932', errors='replace')
                    stderr_text = stderr_data.decode('cp932', errors='replace')
            except:
                # それでも失敗した場合はバイナリデータとして処理
                stdout_text = str(stdout_data)
                stderr_text = str(stderr_data)
            
        return process.returncode, stdout_text, stderr_text
    except subprocess.TimeoutExpired:
        # タイムアウトした場合はプロセスを強制終了
        process.kill()
        return -1, "", "Timeout expired"
    except Exception as e:
        # その他のエラー
        return -1, "", str(e)


def run_command_binary(cmd: List[str], timeout: int = None) -> Tuple[int, bytes, bytes]:
    """
    外部コマンドをバイナリモードで実行し、結果を取得する
    
    Args:
        cmd: 実行するコマンドとその引数のリスト
        timeout: タイムアウト秒数（None=無制限）
        
    Returns:
        (リターンコード, 標準出力(バイナリ), 標準エラー出力(バイナリ)) のタプル
    """
    try:
        # バイナリモードでプロセスを実行
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False  # シェルインジェクションを防止
        )
        
        # 出力を取得
        stdout_data, stderr_data = process.communicate(timeout=timeout)
        return process.returncode, stdout_data, stderr_data
    except subprocess.TimeoutExpired:
        # タイムアウトした場合はプロセスを強制終了
        process.kill()
        return -1, b"", b"Timeout expired"
    except Exception as e:
        # その他のエラー
        return -1, b"", str(e).encode('utf-8')


def run_command_with_input(cmd: List[str], input_data: bytes, timeout: int = None) -> Tuple[int, bytes, bytes]:
    """
    外部コマンドを実行し、標準入力にデータを送信し、結果を取得する
    
    Args:
        cmd: 実行するコマンドとその引数のリスト
        input_data: 標準入力に送信するバイナリデータ
        timeout: タイムアウト秒数（None=無制限）
        
    Returns:
        (リターンコード, 標準出力(バイナリ), 標準エラー出力(バイナリ)) のタプル
    """
    try:
        # バイナリモードで双方向通信可能なプロセスを生成
        import subprocess
        
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False  # シェルインジェクションを防止
        )
        
        # プロセスにデータを送信し、結果を取得
        stdout_data, stderr_data = process.communicate(input=input_data, timeout=timeout)
        return process.returncode, stdout_data, stderr_data
        
    except subprocess.TimeoutExpired:
        # タイムアウトした場合はプロセスを強制終了
        process.kill()
        return -1, b"", b"Timeout expired"
    except Exception as e:
        # その他のエラー
        return -1, b"", str(e).encode('utf-8')


def parse_7z_list_output(output: str) -> List[str]:
    """
    7zの`l`コマンド出力を解析してファイル一覧を取得する
    
    Args:
        output: 7zコマンド出力のテキスト
        
    Returns:
        ファイルパスのリスト
    """
    files = []
    seen_paths = set()  # 重複排除用
    in_file_list = False
    dash_line_count = 0
    
    # デバッグ情報: 出力の先頭部分を表示
    lines = output.splitlines()
    print(f"7z出力解析: 合計{len(lines)}行")
    print("===== 7z出力 =====")
    print(output)
    print("==========================")
    
    # ダッシュライン検出を改善
    try:
        import re
        
        # 7zリスト出力は言語によって異なるため、より柔軟に対応
        # 改良: 少なくとも10個以上の連続したダッシュがあるパターンを検出
        dash_pattern = re.compile(r'^-{10,}')  # 10個以上の連続するダッシュで始まる行
        
        # すべてのダッシュラインを検出
        dash_line_positions = []
        for i, line in enumerate(lines):
            if dash_pattern.match(line):
                dash_line_positions.append(i)
                print(f"ダッシュライン検出: 行 {i}: {line}")
        
        # ダッシュラインが2つ以上ある場合、最初と最後のダッシュラインの間がデータ部
        if len(dash_line_positions) >= 2:
            start_idx = dash_line_positions[0] + 1  # 最初のダッシュラインの次
            end_idx = dash_line_positions[-1]       # 最後のダッシュライン
            
            print(f"データ部: 行 {start_idx} から {end_idx}")
            
            # データ行を処理
            for i in range(start_idx, end_idx):
                line = lines[i].strip()
                if not line:  # 空行はスキップ
                    continue
                
                try:
                    # スペースで分割（日付、時間、属性、サイズ、圧縮サイズ、ファイル名）
                    parts = line.split(maxsplit=5)
                    
                    if len(parts) >= 6:  # 通常フォーマット
                        file_name = parts[5].strip()
                        
                        # 属性フィールドを確認してディレクトリかどうか判定
                        if len(parts) >= 3 and 'D' in parts[2]:
                            # ディレクトリの場合は末尾にスラッシュを追加
                            if not file_name.endswith('/'):
                                file_name = file_name + '/'
                                print(f"ディレクトリとして認識: {file_name}")
                        
                        # 重複排除
                        if file_name in seen_paths:
                            print(f"重複パスをスキップ: {file_name}")
                            continue
                            
                        files.append(file_name)
                        seen_paths.add(file_name)
                    elif len(parts) >= 5:  # 一部のシンプルフォーマット
                        file_name = parts[4].strip()
                        
                        # シンプルフォーマットの場合も属性を確認
                        if len(parts) >= 3 and parts[2].strip() and 'D' in parts[2]:
                            if not file_name.endswith('/'):
                                file_name = file_name + '/'
                                print(f"シンプルフォーマットでディレクトリとして認識: {file_name}")
                        
                        # 重複排除
                        if file_name in seen_paths:
                            print(f"重複パスをスキップ: {file_name}")
                            continue
                            
                        files.append(file_name)
                        seen_paths.add(file_name)
                except Exception as e:
                    print(f"行 {i} の解析エラー: {str(e)} - {line}")
        else:
            # ダッシュラインが見つからない場合は従来の方式を使用
            print("警告: ダッシュラインが十分に見つかりません。代替方法を使用します")
            return _parse_7z_list_output_legacy(output)
                
    except Exception as e:
        print(f"7z出力解析中にエラー発生: {str(e)}")
        import traceback
        traceback.print_exc()
        # フォールバックとして従来の実装を使用
        return _parse_7z_list_output_legacy(output)
    
    # 取得したファイルリストの件数と内容を表示
    print(f"7z出力の解析完了: {len(files)} 件のファイルを検出")
    
    # サンプル表示
    print("===== 検出されたファイル（最大5件） =====")
    for f in files[:5]:  # 最初の5件だけ表示
        print(f"  {f}")
    print("======================================")
    
    return files

def _parse_7z_list_output_legacy(output: str) -> List[str]:
    """
    7zの出力を従来の方法で解析する（フォールバック用）
    
    Args:
        output: 7zコマンド出力のテキスト
        
    Returns:
        ファイルパスのリスト
    """
    files = []
    seen_paths = set()  # 重複排除用
    in_file_list = False
    dash_line_count = 0
    
    print("従来のファイル一覧解析方法を使用")
    
    for line in output.splitlines():
        # ダッシュ行の検出を改善 - 少なくとも10個以上の連続したダッシュがある行
        if line.startswith("-----------"):
            dash_line_count += 1
            print(f"従来法でダッシュライン検出 #{dash_line_count}: {line[:20]}")
            if dash_line_count == 1:
                in_file_list = True
                continue
            elif dash_line_count == 2:
                break
                
        # ファイルリスト内でファイルエントリを検出
        if in_file_list and line.strip():
            try:
                # スペースで分割（日付、時間、属性、サイズ、圧縮サイズ、ファイル名）
                parts = line.split(maxsplit=5)
                
                if len(parts) >= 6:  # 通常フォーマット
                    file_name = parts[5].strip()
                    
                    # 属性フィールドを確認してディレクトリかどうか判定
                    if len(parts) >= 3 and 'D' in parts[2]:
                        # ディレクトリの場合は末尾にスラッシュを追加
                        if not file_name.endswith('/'):
                            file_name = file_name + '/'
                            print(f"従来法: ディレクトリとして認識: {file_name}")
                    
                    # 重複排除
                    if file_name not in seen_paths:
                        files.append(file_name)
                        seen_paths.add(file_name)
                        print(f"ファイル検出: {file_name}")
                    else:
                        print(f"重複パスをスキップ (legacy): {file_name}")
                        
                elif len(parts) >= 5:  # 一部のシンプルフォーマット
                    file_name = parts[4].strip()
                    
                    # シンプルフォーマットの場合も属性を確認
                    if len(parts) >= 3 and parts[2].strip() and 'D' in parts[2]:
                        if not file_name.endswith('/'):
                            file_name = file_name + '/'
                            print(f"従来法: シンプルフォーマットでディレクトリとして認識: {file_name}")
                    
                    # 重複排除
                    if file_name not in seen_paths:
                        files.append(file_name)
                        seen_paths.add(file_name)
                        print(f"ファイル検出 (シンプルフォーマット): {file_name}")
                    else:
                        print(f"重複パスをスキップ (legacy): {file_name}")
            except Exception as e:
                print(f"従来法での行の解析エラー: {str(e)}")
                continue
    
    print(f"従来の方法で {len(files)} 件のファイルを検出")
    return files


def build_structure_from_files(file_paths: List[str], remove_common_prefix: bool = False, flat_mode: bool = False) -> Dict[str, Dict]:
    """
    ファイルパスのリストからディレクトリ構造を構築する
    
    Args:
        file_paths: ファイルパスのリスト
        remove_common_prefix: 共通プレフィックスを削除するか
        flat_mode: フラットモード（階層化せずファイル名のみを使う）
    
    Returns:
        ディレクトリ構造を表す辞書
    """
    # 構造を初期化
    structure = {'': {'dirs': {}, 'files': {}}}
    
    # 共通プレフィックスを削除
    common_prefix = ""
    if remove_common_prefix and file_paths and len(file_paths) > 1:
        # 共通プレフィックスを計算
        common_path_parts = []
        split_paths = [path.split('/') for path in file_paths if path]
        if split_paths:
            min_len = min(len(parts) for parts in split_paths)
            
            for i in range(min_len):
                if all(parts[i] == split_paths[0][i] for parts in split_paths):
                    common_path_parts.append(split_paths[0][i])
                else:
                    break
                    
            if common_path_parts:
                common_prefix = '/'.join(common_path_parts)
                if not common_prefix.endswith('/'):
                    common_prefix += '/'
                    
                print(f"共通プレフィックスを検出: '{common_prefix}'")
                
    # ファイルパスを処理
    for path in file_paths:
        if flat_mode:
            # フラットモード：すべてをルートディレクトリに配置
            file_name = os.path.basename(path)
            
            # ファイルまたはディレクトリとして処理
            if path.endswith('/'):
                structure['']['dirs'][file_name] = True
            else:
                structure['']['files'][file_name] = {'size': 0}
        else:
            # 階層モード：正しい階層構造を維持
            
            # 共通プレフィックスを削除
            if common_prefix and path.startswith(common_prefix):
                path = path[len(common_prefix):]
            
            # パスがディレクトリを表すかどうか
            is_dir = path.endswith('/')
            
            # パスをディレクトリ部分とファイル名に分ける
            if is_dir:
                dir_path = path
                file_name = ""
            else:
                dir_path = os.path.dirname(path)
                if dir_path:
                    dir_path += '/'
                file_name = os.path.basename(path)
            
            # ディレクトリ構造を構築
            # まず、親ディレクトリが存在することを確認
            current_path = ""
            for dir_part in dir_path.split('/'):
                if not dir_part:  # 空文字列はスキップ
                    continue
                    
                # 親が存在しなければ作成
                if current_path not in structure:
                    structure[current_path] = {'dirs': {}, 'files': {}}
                
                # 親にこのディレクトリを追加
                new_path = current_path + dir_part + '/'
                structure[current_path]['dirs'][dir_part] = True
                
                # 現在のパスを更新
                current_path = new_path
            
            # ファイルの親ディレクトリが存在しなければ作成
            if dir_path not in structure:
                structure[dir_path] = {'dirs': {}, 'files': {}}
                
            # ファイル名が存在する場合はファイルを追加
            if file_name:
                structure[dir_path]['files'][file_name] = {'size': 0}
    
    return structure


def detect_encoding(data: Union[bytes, str]) -> str:
    """
    テキストデータのエンコーディングを自動判別する
    
    charset_normalizer を使用して高精度な文字コード判定を行う
    
    Args:
        data: 判別するデータ（バイト列または文字列）
        
    Returns:
        判別されたエンコーディング、判別できない場合は'utf-8'
    """
    # すでに文字列の場合はバイト列に変換
    if isinstance(data, str):
        data = data.encode('latin1', errors='replace')
    
    try:
        # charset_normalizer を使用
        import charset_normalizer
        
        # 検出を実行
        detection_result = charset_normalizer.detect(data)
        
        # 結果を取得
        encoding = detection_result.get('encoding')
        confidence = detection_result.get('confidence', 0)
        
        print(f"文字コード検出: {encoding} (信頼度: {confidence:.2f})")
        
        # 信頼度が低すぎる場合やNoneの場合はデフォルト値
        if not encoding or confidence < 0.5:
            # 日本語環境ならcp932も試す
            if os.name == 'nt':  # Windowsの場合
                try:
                    # cp932でデコードしてみる
                    data.decode('cp932', errors='strict')
                    return 'cp932'  # エラーがなければcp932
                except UnicodeDecodeError:
                    pass
            return 'utf-8'
            
        return encoding
    except ImportError:
        print("charset_normalizer がインストールされていません。代替方法を使用します。")
        # すべてのライブラリがない場合は、一般的なエンコーディングを試行
        encodings = ['utf-8', 'cp932', 'shift_jis', 'euc-jp', 'latin1']
        best_encoding = 'utf-8'  # デフォルト
        min_errors = float('inf')
        
        for enc in encodings:
            try:
                # エラー数をカウント
                error_count = 0
                test_decode = data.decode(enc, errors='replace')
                for c in test_decode:
                    if c == '\ufffd':  # 置換文字
                        error_count += 1
                
                if error_count < min_errors:
                    min_errors = error_count
                    best_encoding = enc
                
                # エラーがなければそれを採用
                if error_count == 0:
                    return enc
            except:
                continue
        
        return best_encoding