"""
画像処理モジュール

画像データの処理やメタデータ取得などの機能を提供
"""

import os
from typing import Tuple, Dict, Any, Optional
import numpy as np

from logutils import log_print, INFO, WARNING, ERROR, DEBUG

try:
    from PySide6.QtGui import QPixmap, QImage
except ImportError:
    log_print(ERROR, "PySide6がインストールされていません")

# decoderモジュールをインポート
try:
    from decoder import select_image_decoder, decode_image
    DECODER_AVAILABLE = True
except ImportError:
    log_print(ERROR, "decoderモジュールがインポートできません。このアプリケーションの実行には必須です。")
    DECODER_AVAILABLE = False


def load_image_from_bytes(image_data: bytes, file_path: str = "") -> Tuple[Optional[QPixmap], Optional[np.ndarray], Dict[str, Any]]:
    """
    バイトデータから画像をロードし、QtのPixmapとNumpyの配列とメタデータ情報を返す
    
    Args:
        image_data: 画像データのバイト列
        file_path: 画像のファイルパス（メタデータ取得用）
        
    Returns:
        (QPixmap, Numpy配列, メタデータ情報) のタプル
        失敗した場合は (None, None, {})
    """
    if not image_data:
        return None, None, {}
    
    # 基本情報の初期化
    info = {}
    
    # ファイル名から拡張子を取得（小文字化）    
    _, ext = os.path.splitext(file_path.lower()) if file_path else ("", "")
    
    # ファイルサイズをメタデータに追加
    info["file_size"] = len(image_data)
    info["file_name"] = os.path.basename(file_path) if file_path else ""
    
    try:
        # モジュールが利用できない場合はエラー
        if not DECODER_AVAILABLE:
            raise ImportError("decoderモジュールが利用できないため、画像を読み込めません")
        
        # デコードの詳細ログを追加
        log_print(DEBUG, f"画像デコード開始: '{file_path}', サイズ: {len(image_data)} バイト")
        
        # select_image_decoderを使用して適切なデコーダーを選択
        decoder = select_image_decoder(file_path)
        if not decoder:
            raise ValueError(f"ファイル '{file_path}' に対応するデコーダーが見つかりません")
        
        log_print(DEBUG, f"選択されたデコーダー: {decoder.__class__.__name__}")
        
        # デコーダーを使用して画像をデコード
        numpy_array = decoder.decode(image_data)
        if numpy_array is None:
            raise ValueError(f"画像のデコードに失敗しました: {file_path}")
        
        # numpy_arrayから画像情報を取得
        height, width = numpy_array.shape[:2]
        channels = 1 if len(numpy_array.shape) == 2 else numpy_array.shape[2]
        
        log_print(DEBUG, f"デコード成功: {width}x{height}, チャンネル数: {channels}")
        
        info.update({
            "width": width,
            "height": height,
            "channels": channels,
            "format": ext[1:].upper() if ext else "Unknown",
            "decoder": decoder.__class__.__name__
        })
        
        # NumPy配列からQImageを作成
        if channels == 1:  # グレースケール
            img = QImage(numpy_array.data, width, height, width, QImage.Format_Grayscale8)
        elif channels == 3:  # RGB
            img = QImage(numpy_array.data, width, height, width * 3, QImage.Format_RGB888)
        elif channels == 4:  # RGBA
            img = QImage(numpy_array.data, width, height, width * 4, QImage.Format_RGBA8888)
        else:
            raise ValueError(f"サポートされていないチャンネル数: {channels}")
                
        # QImageからQPixmapを作成
        pixmap = QPixmap.fromImage(img)
        log_print(DEBUG, f"QPixmap作成完了: {pixmap.width()}x{pixmap.height()}")
        
        return pixmap, numpy_array, info
            
    except Exception as e:
        log_print(ERROR, f"画像の読み込みに失敗しました: {e}")
        import traceback
        log_print(ERROR, traceback.format_exc())
        return None, None, info


def format_image_info(info: Dict[str, Any]) -> str:
    """
    画像情報を整形して文字列として返す
    
    Args:
        info: 画像情報の辞書
        
    Returns:
        整形された画像情報の文字列
    """
    if not info:
        return "情報がありません"
    
    lines = []
    
    # 基本情報
    if "file_name" in info:
        lines.append(f"ファイル名: {info['file_name']}")
    
    if "width" in info and "height" in info:
        lines.append(f"サイズ: {info['width']}x{info['height']}ピクセル")
    
    if "format" in info:
        lines.append(f"フォーマット: {info['format']}")
    
    if "mode" in info:
        lines.append(f"モード: {info['mode']}")
    
    if "channels" in info:
        lines.append(f"チャンネル数: {info['channels']}")
    
    if "decoder" in info:
        lines.append(f"使用デコーダー: {info['decoder']}")
    
    if "file_size" in info:
        size_kb = info["file_size"] / 1024
        lines.append(f"ファイルサイズ: {size_kb:.1f} KB")
    
    # decoderから取得した追加情報（例えば画像の特殊な特性など）
    if "decoder_info" in info:
        lines.append("\nデコーダー情報:")
        for key, value in info["decoder_info"].items():
            if key not in ["width", "height"]:  # 既に表示済みの基本情報を除外
                lines.append(f"  {key}: {value}")
    
    return "\n".join(lines)
