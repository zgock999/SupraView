"""
アーカイブ内のエンコーディング問題を解決するためのユーティリティ

異なるエンコーディング間の変換や検出を行うヘルパー関数を提供
"""

import os
import re
from typing import List, Dict, Tuple, Optional, Set


def is_ascii(text: str) -> bool:
    """
    文字列がASCII文字のみで構成されているかチェック
    
    Args:
        text: チェックする文字列
        
    Returns:
        ASCII文字のみの場合はTrue、そうでなければFalse
    """
    return all(ord(c) < 128 for c in text)


def detect_encoding(byte_data: bytes) -> str:
    """
    バイトデータからエンコーディングを推測
    
    Args:
        byte_data: エンコーディングを判定するバイトデータ
        
    Returns:
        推測されるエンコーディング名
    """
    # BOMの確認
    if byte_data.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    elif byte_data.startswith(b'\xff\xfe'):
        return 'utf-16-le'
    elif byte_data.startswith(b'\xfe\xff'):
        return 'utf-16-be'
    
    # ASCII文字のみかチェック
    if all(b < 128 for b in byte_data):
        return 'ascii'
    
    # 日本語エンコーディングの特徴をチェック
    # CP932/Shift-JISの特徴: 連続する2バイト文字の1バイト目は0x81-0x9FまたはE0-FCの範囲
    sjis_chars = 0
    for i in range(len(byte_data) - 1):
        if (0x81 <= byte_data[i] <= 0x9F or 0xE0 <= byte_data[i] <= 0xFC) and \
           (0x40 <= byte_data[i+1] <= 0xFC):
            sjis_chars += 1
    
    # EUC-JPの特徴: 連続する2バイト文字の1バイト目は0xA1-0xFEの範囲
    euc_chars = 0
    for i in range(len(byte_data) - 1):
        if 0xA1 <= byte_data[i] <= 0xFE and 0xA1 <= byte_data[i+1] <= 0xFE:
            euc_chars += 1
    
    # UTF-8の特徴: マルチバイト文字の1バイト目は0xC0以上、続くバイトは0x80-0xBFの範囲
    utf8_chars = 0
    i = 0
    while i < len(byte_data):
        if byte_data[i] >= 0xC0:
            # 2バイト以上の文字の先頭バイト
            bytes_count = 0
            if byte_data[i] >= 0xF0:
                bytes_count = 4  # 4バイト文字
            elif byte_data[i] >= 0xE0:
                bytes_count = 3  # 3バイト文字
            elif byte_data[i] >= 0xC0:
                bytes_count = 2  # 2バイト文字
            
            # 後続バイトが0x80-0xBFの範囲かチェック
            valid = True
            for j in range(1, bytes_count):
                if i+j < len(byte_data) and 0x80 <= byte_data[i+j] <= 0xBF:
                    continue
                valid = False
                break
                
            if valid:
                utf8_chars += 1
                i += bytes_count
                continue
        i += 1
    
    # 特徴的な出現回数から最も可能性の高いエンコーディングを選択
    if utf8_chars > sjis_chars and utf8_chars > euc_chars:
        return 'utf-8'
    if sjis_chars > euc_chars:
        return 'cp932'
    if euc_chars > 0:
        return 'euc-jp'
    
    # デフォルト
    return 'utf-8'


def try_decode_with_encodings(byte_data: bytes) -> Tuple[str, str]:
    """
    複数のエンコーディングでデコードを試み、最も可能性の高いものを選択
    
    Args:
        byte_data: デコードするバイトデータ
        
    Returns:
        (デコードされた文字列, 使用したエンコーディング)のタプル
    """
    # 試すエンコーディングの順序（優先度順）
    encodings = ['utf-8', 'cp932', 'shift_jis', 'euc-jp', 'iso-2022-jp', 'cp437']
    
    # まず特定のエンコーディングを推測
    detected = detect_encoding(byte_data)
    if detected != 'ascii' and detected != 'utf-8':
        encodings.insert(0, detected)
    
    # 各エンコーディングでデコードを試す
    for encoding in encodings:
        try:
            decoded = byte_data.decode(encoding)
            return decoded, encoding
        except UnicodeDecodeError:
            continue
    
    # どれも失敗した場合はエラー置き換えモードでUTF-8でデコード
    return byte_data.decode('utf-8', errors='replace'), 'utf-8-replace'


def fix_path_encoding(path: str) -> List[str]:
    """
    パスのエンコーディング問題を解決するための候補を生成
    
    Args:
        path: 問題のあるパス文字列
        
    Returns:
        試すべきパス文字列の候補リスト（優先度順）
    """
    result = [path]  # 元のパスを最初に試す
    
    # CP437とCP932の変換
    try:
        # CP437としてバイト列に変換してからShift-JISとして解釈
        cp437_bytes = path.encode('cp437')
        sjis_path = cp437_bytes.decode('cp932', errors='replace')
        if sjis_path != path:
            result.append(sjis_path)
    except (UnicodeError, LookupError):
        pass
    
    # パス区切り文字の正規化
    normalized = path.replace('\\', '/')
    if normalized != path and normalized not in result:
        result.append(normalized)
    
    # ディレクトリ区切りの有無による候補
    if not path.endswith('/'):
        path_with_slash = path + '/'
        if path_with_slash not in result:
            result.append(path_with_slash)
    else:
        path_without_slash = path.rstrip('/')
        if path_without_slash not in result:
            result.append(path_without_slash)
    
    return result
