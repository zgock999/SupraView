"""
デコーダーインターフェース

様々な画像形式をデコードするためのインターフェースを定義し、
適切なデコーダーに処理を振り分けるサービスを提供します。
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Tuple, Union, Any, Set, Type
import numpy as np
from pathlib import Path

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logutils import setup_logging, log_print, DEBUG, INFO, WARNING, ERROR

# 基本デコーダーとイメージデコーダーをインポート
from decoder.base import BaseDecoder
from decoder.decoder import ImageDecoder
from decoder.common import DecodingError

# 実体デコーダー群のインポート
# 注: 現在実装されているデコーダーのみをインポート
try:
    from decoder.mag_decoder import MAGImageDecoder
    from decoder.cv2_decoder import CV2ImageDecoder
    # 将来的に他のデコーダーが実装されたらここに追加
except ImportError as e:
    log_print(WARNING, f"一部のデコーダーのインポートに失敗しました: {e}")


class DecoderManager:
    """
    各種デコーダーを管理し、適切なデコーダーにデコード処理を振り分けるマネージャークラス
    """
    
    def __init__(self):
        """デコーダーマネージャーの初期化"""
        # デコーダークラスとサポートする拡張子のマッピングを初期化
        # ImageDecoderのサブクラスとして型情報を修正
        self._decoders: Dict[Type[ImageDecoder], List[str]] = {}
        self._ext_to_decoder: Dict[str, Type[ImageDecoder]] = {}
        
        # 利用可能なデコーダーを登録
        self._register_decoders()
        
        # サポート形式がない場合のフォールバック（エラー防止）
        if not self._ext_to_decoder:
            log_print(WARNING, "有効なデコーダーが登録されていません。基本的な画像フォーマットをサポート対象に追加します。")
            self._add_fallback_extensions()
        
        log_print(INFO, f"デコーダーマネージャーが初期化されました。サポート形式: {', '.join(self.get_supported_extensions())}")
    
    def _register_decoders(self):
        """利用可能なデコーダーを登録する"""
        # デコーダークラスのリスト 
        # 明示的に ImageDecoder のサブクラスとして処理
        decoder_classes: List[Type[ImageDecoder]] = []
        
        # MAGImageDecoderの登録
        try:
            from decoder.mag_decoder import MAGImageDecoder
            decoder_classes.append(MAGImageDecoder)
            log_print(DEBUG, "MAGImageDecoderを登録候補に追加しました")
        except ImportError as e:
            log_print(WARNING, f"MAGImageDecoderが見つかりません: {e}")
        
        # CV2ImageDecoderの登録
        try:
            from decoder.cv2_decoder import CV2ImageDecoder
            decoder_classes.append(CV2ImageDecoder)
            log_print(DEBUG, "CV2ImageDecoderを登録候補に追加しました")
        except ImportError as e:
            log_print(WARNING, f"CV2ImageDecoderが見つかりません: {e}")
        
        log_print(DEBUG, f"登録候補のデコーダー数: {len(decoder_classes)}")
        
        # 各デコーダーを登録（ImageDecoderのサブクラスである前提で処理）
        for decoder_class in decoder_classes:
            try:
                # ImageDecoderのサブクラスか確認
                if not issubclass(decoder_class, ImageDecoder):
                    log_print(WARNING, f"{decoder_class.__name__} はImageDecoderを継承していないためスキップします")
                    continue
                
                # インスタンスを作成して拡張子を取得
                # ImageDecoderのサブクラスなので supported_extensions プロパティが必ず存在する
                decoder_instance = decoder_class()
                extensions = decoder_instance.supported_extensions
                
                # デバッグ出力
                log_print(DEBUG, f"デコーダー {decoder_class.__name__} のサポート拡張子: {extensions}")
                
                # 有効な拡張子リストか確認
                if isinstance(extensions, list) and extensions:
                    self._decoders[decoder_class] = extensions
                    
                    # 拡張子から対応するデコーダーへのマッピングを作成
                    for ext in extensions:
                        # 小文字に正規化してドット付きに
                        if not ext.startswith('.'):
                            norm_ext = '.' + ext.lower()
                        else:
                            norm_ext = ext.lower()
                            
                        if norm_ext not in self._ext_to_decoder:
                            self._ext_to_decoder[norm_ext] = decoder_class
                            log_print(DEBUG, f"拡張子 '{norm_ext}' を {decoder_class.__name__} に登録しました")
                        else:
                            # 既に別のデコーダーが登録されている場合は警告
                            log_print(WARNING, 
                                f"拡張子 '{ext}' は既に {self._ext_to_decoder[norm_ext].__name__} に"
                                f"登録されていますが、{decoder_class.__name__} も対応しています。"
                                f"先に登録されたデコーダーが優先されます。"
                            )
                else:
                    log_print(WARNING, f"デコーダー {decoder_class.__name__} からサポート拡張子を取得できませんでした")
                
                log_print(DEBUG, f"デコーダー {decoder_class.__name__} を登録しました")
            except Exception as e:
                log_print(ERROR, f"デコーダー {decoder_class.__name__} の登録中にエラーが発生しました: {e}")
                import traceback
                traceback.print_exc()
    
    def _add_fallback_extensions(self):
        """
        サポート形式が見つからない場合のフォールバック
        基本的な画像形式を手動で追加して機能停止を防ぐ
        """
        # 共通して使われる画像フォーマットを追加
        common_formats = [
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', 
            '.webp', '.tiff', '.tif', '.ico'
        ]
        
        for ext in common_formats:
            # MAGデコーダーがあれば、それをデフォルトとして使用
            decoder_class = None
            try:
                decoder_class = MAGImageDecoder
            except NameError:
                try:
                    decoder_class = CV2ImageDecoder
                except NameError:
                    pass
            
            # デコーダーが見つかったら登録
            if decoder_class and issubclass(decoder_class, ImageDecoder):
                self._ext_to_decoder[ext] = decoder_class
                
                # デコーダー対応表にも追加
                if decoder_class not in self._decoders:
                    self._decoders[decoder_class] = []
                self._decoders[decoder_class].append(ext)
                
                log_print(DEBUG, f"フォールバック: 拡張子 '{ext}' を {decoder_class.__name__} に登録しました")
        
        log_print(INFO, f"フォールバック設定を適用しました。サポート形式: {', '.join(self.get_supported_extensions())}")
    
    def get_supported_extensions(self) -> List[str]:
        """
        サポートされている拡張子のリストを取得する
        
        Returns:
            サポートされている拡張子のリスト
        """
        extensions = sorted(list(self._ext_to_decoder.keys()))
        log_print(DEBUG, f"サポートされている拡張子: {extensions}")
        return extensions
    
    def get_decoder_for_extension(self, extension: str) -> Optional[Type[ImageDecoder]]:
        """
        指定された拡張子に対応するデコーダークラスを取得する
        
        Args:
            extension: ファイルの拡張子（.jpgなど、ドット付き）
            
        Returns:
            対応するデコーダークラス、見つからない場合はNone
        """
        # 小文字に正規化し、先頭のドットを確保
        if not extension.startswith('.'):
            extension = '.' + extension
        extension = extension.lower()
        
        return self._ext_to_decoder.get(extension)
    
    def get_decoder_for_file(self, filename: str) -> Optional[Type[ImageDecoder]]:
        """
        ファイル名から適切なデコーダークラスを取得する
        
        Args:
            filename: デコードするファイル名
            
        Returns:
            対応するデコーダークラス、見つからない場合はNone
        """
        # 拡張子を取得して小文字に変換
        _, ext = os.path.splitext(filename.lower())
        if not ext:
            return None
            
        return self.get_decoder_for_extension(ext)
    
    def decode_file(self, filename: str, data: bytes) -> Optional[np.ndarray]:
        """
        ファイル名とバイトデータから画像をデコードし、numpy配列として返す
        
        Args:
            filename: デコードするファイル名（拡張子から適切なデコーダーを選択）
            data: デコードするバイトデータ
            
        Returns:
            デコードされた画像のnumpy配列、失敗した場合はNone
        """
        # ファイル名から適切なデコーダーを取得
        decoder_class = self.get_decoder_for_file(filename)
        if not decoder_class:
            log_print(ERROR, f"ファイル '{filename}' に対応するデコーダーが見つかりません")
            return None
        
        try:
            # デコーダーのインスタンスを作成
            decoder = decoder_class()
            
            # データをデコードしてnumpy配列に変換
            image_array = decoder.decode(data)
            return image_array
            
        except DecodingError as e:
            log_print(ERROR, f"ファイル '{filename}' のデコード中にエラーが発生しました: {e}")
            return None
        except Exception as e:
            log_print(ERROR, f"予期しないエラーが発生しました: {e}")
            return None
    
    def get_decoder_info(self) -> Dict[str, List[str]]:
        """
        登録されているすべてのデコーダーとそのサポート拡張子の情報を取得する
        
        Returns:
            デコーダー名と対応する拡張子のリストを含む辞書
        """
        info = {}
        for decoder_class, extensions in self._decoders.items():
            info[decoder_class.__name__] = extensions
        return info


# シングルトンインスタンス
_decoder_manager = None

def get_decoder_manager() -> DecoderManager:
    """
    デコーダーマネージャーのシングルトンインスタンスを取得する
    
    Returns:
        DecoderManagerのインスタンス
    """
    global _decoder_manager
    if (_decoder_manager is None):
        _decoder_manager = DecoderManager()
    return _decoder_manager


def decode_image(filename: str, data: bytes) -> Optional[np.ndarray]:
    """
    ファイル名とバイトデータから画像をデコードするユーティリティ関数
    
    Args:
        filename: デコードするファイル名（拡張子から適切なデコーダーを選択）
        data: デコードするバイトデータ
        
    Returns:
        デコードされた画像のnumpy配列、失敗した場合はNone
    """
    manager = get_decoder_manager()
    return manager.decode_file(filename, data)


def get_supported_image_extensions() -> List[str]:
    """
    サポートされている画像拡張子のリストを取得する
    
    Returns:
        サポートされている拡張子のリスト
    """
    manager = get_decoder_manager()
    extensions = manager.get_supported_extensions()
    
    # デバッグ出力を追加
    log_print(DEBUG, f"サポートされている画像拡張子: {extensions}")
    
    return extensions


def select_image_decoder(filepath: str) -> Optional[ImageDecoder]:
    """
    ファイルパスからそのファイルに適切なデコーダーを選択してインスタンスを返す
    
    Args:
        filepath: デコードする画像ファイルのパス
        
    Returns:
        選択されたImageDecoderのインスタンス、対応するデコーダーがない場合はNone
    """
    _, ext = os.path.splitext(filepath.lower())
    if not ext:
        log_print(WARNING, f"拡張子が指定されていません: {filepath}")
        return None
    
    manager = get_decoder_manager()
    decoder_class = manager.get_decoder_for_extension(ext)
    
    if decoder_class is None:
        log_print(WARNING, f"拡張子'{ext}'に対応するデコーダーが見つかりません: {filepath}")
        return None
    
    try:
        return decoder_class()
    except Exception as e:
        log_print(ERROR, f"デコーダーのインスタンス化に失敗しました: {e}")
        return None


# テスト用のコード
if __name__ == "__main__":
    # ロギングを設定
    setup_logging(DEBUG)
    
    # デコーダーマネージャーを取得
    manager = get_decoder_manager()
    
    # サポートされている拡張子を表示
    extensions = manager.get_supported_extensions()
    log_print(INFO, f"サポートしている拡張子: {', '.join(extensions)}")
    
    # デコーダー情報を表示
    decoder_info = manager.get_decoder_info()
    log_print(INFO, "登録されているデコーダー:")
    for decoder_name, exts in decoder_info.items():
        log_print(INFO, f"  {decoder_name}: {', '.join(exts)}")
    
    # テスト画像をデコード（テスト用画像があれば）
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        if os.path.isfile(test_file):
            try:
                with open(test_file, 'rb') as f:
                    data = f.read()
                
                log_print(INFO, f"ファイル {test_file} をデコードします...")
                image_array = decode_image(test_file, data)
                
                if image_array is not None:
                    log_print(INFO, f"デコード成功: 形状={image_array.shape}, dtype={image_array.dtype}")
                else:
                    log_print(ERROR, "デコードに失敗しました")
            except Exception as e:
                log_print(ERROR, f"テスト中にエラーが発生しました: {e}")
