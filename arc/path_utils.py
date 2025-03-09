"""
複数のエンコーディングでパスを処理するためのユーティリティ

アーカイブ内の非ASCII文字やエンコーディング問題を解決するためのヘルパー関数
"""

import os
import sys
from typing import List, Optional


def normalize_path(path: str) -> str:
    """
    OSに依存しないパス正規化関数
    
    Args:
        path: 正規化する元のパス文字列
        
    Returns:
        正規化されたパス文字列
    """
    if path is None:
        return ""
        
    # バックスラッシュをスラッシュに変換
    normalized = path.replace('\\', '/')
    
    # 連続するスラッシュを1つに
    while '//' in normalized:
        normalized = normalized.replace('//', '/')
    
    # WindowsドライブレターのUNIX形式表現を修正（例: /C:/path → C:/path）
    if len(normalized) > 2 and normalized[0] == '/' and normalized[2] == ':':
        normalized = normalized[1:]  # 先頭のスラッシュを削除
        
    return normalized


def try_decode_path(path_bytes: bytes) -> str:
    """
    複数のエンコーディングでパスをデコードする試行を行う
    
    Args:
        path_bytes: デコードするバイト列
        
    Returns:
        デコードされた文字列。どのエンコーディングでも失敗した場合はreplace付きutf-8でデコード
    """
    encodings = ['utf-8', 'shift_jis', 'cp932', 'euc-jp', 'iso-2022-jp']
    
    for enc in encodings:
        try:
            return path_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    
    # すべて失敗した場合はreplaceオプション付きでutf-8で強制デコード
    return path_bytes.decode('utf-8', errors='replace')


def safe_normpath(path: str) -> str:
    """
    非ASCII文字を含むパスも安全に正規化する
    
    Args:
        path: 正規化するパス
        
    Returns:
        正規化されたパス
    """
    # まず通常の正規化を試みる
    try:
        return os.path.normpath(path).replace('\\', '/')
    except:
        # パスをバイトに変換して処理
        try:
            path_bytes = path.encode('utf-8')
            norm_bytes = os.path.normpath(path_bytes)
            return norm_bytes.decode('utf-8').replace('\\', '/')
        except:
            # それでも失敗する場合はそのまま返す（最低限の正規化だけ行う）
            return normalize_path(path)


def fix_garbled_filename(filename: str) -> str:
    """
    文字化けしたファイル名を修復する試み
    
    Args:
        filename: 修復する可能性のある文字化けしたファイル名
        
    Returns:
        修復を試みたファイル名
    """
    # 文字化けの一般的なパターン: CP437でエンコードされたCP932文字列
    try:
        # 一度CP437として解釈してバイト列に戻す
        bytes_data = filename.encode('cp437')
        # CP932として再解釈
        return bytes_data.decode('cp932', errors='replace')
    except:
        return filename


def detect_archive_encoding(sample_names: List[str]) -> str:
    """
    アーカイブ内のファイル名からエンコーディングを推測する
    
    Args:
        sample_names: アーカイブ内のファイル名サンプル
        
    Returns:
        推測されたエンコーディング名
    """
    if not sample_names:
        return 'utf-8'
    
    # 候補エンコーディング
    encodings = ['utf-8', 'cp932', 'shift_jis', 'euc-jp']
    scores = {enc: 0 for enc in encodings}
    
    for name in sample_names:
        # 各エンコーディングでエンコード→デコードを試み、元の文字列と一致するか確認
        for enc in encodings:
            try:
                decoded = name.encode(enc).decode(enc)
                if decoded == name:
                    scores[enc] += 1
            except:
                pass
    
    # 最も高いスコアのエンコーディングを返す
    return max(scores.items(), key=lambda x: x[1])[0]
