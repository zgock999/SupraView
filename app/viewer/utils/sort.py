"""
ソートユーティリティ

ファイル名などを自然順（数値部分を数値として）ソートするための関数
"""

import re
from typing import Any, List


def natural_sort_key(text: str) -> List[Any]:
    """
    自然順ソート用のキーを生成（数値部分を数値として扱う）
    
    Args:
        text: ソートする文字列
        
    Returns:
        数値と文字列のリスト（数値は数値型）
    """
    # テキストがNoneまたは数値の場合の対応
    if text is None:
        return [""]
    
    # 文字列に変換して処理（数値など文字列以外の場合に対応）
    text_str = str(text)
    
    # 数値と非数値に分割する正規表現パターン
    pattern = r'(\d+)|(\D+)'
    
    # 結果リスト
    parts = []
    
    # 見つかったすべての部分を処理
    for digit, non_digit in re.findall(pattern, text_str):
        if digit:
            # 数値部分は数値型として追加
            parts.append(int(digit))
        else:
            # 非数値部分は小文字に変換して追加（大文字小文字を区別しないため）
            parts.append(non_digit.lower())
    
    # 空の場合は空文字を入れておく
    if not parts:
        parts.append("")
    
    return parts


def get_sorted_keys(keys, ignore_case=True):
    """
    キーのリストを自然順にソートする
    
    Args:
        keys: ソートするキーのリスト
        ignore_case: 大文字小文字を区別しない場合はTrue
        
    Returns:
        ソートされたキーのリスト
    """
    if ignore_case:
        return sorted(keys, key=lambda x: str(x).lower())
    return sorted(keys)


def get_stable_sort_key(sort_key):
    """
    ソートに使用する安全なキーを取得する
    型の不一致によるエラーを防ぐための特別なキーを生成
    
    Args:
        sort_key: アイテムのソートキーデータ
        
    Returns:
        比較可能なソートキー
    """
    # NoneやUndefinedの場合は空リストを返す
    if sort_key is None:
        return []
        
    # すでにリストの場合
    if isinstance(sort_key, list):
        # リスト内の要素を安全に比較できる形式に変換
        result = []
        for item in sort_key:
            if isinstance(item, int):
                # 整数部分は文字列表現の前に0を詰めて桁数を揃える（最大20桁）
                result.append(f"{item:020d}")
            elif isinstance(item, str):
                # 文字列はそのまま（ただし小文字に統一）
                result.append(item.lower())
            else:
                # その他の型は文字列に変換
                result.append(str(item))
        return result
        
    # リストでない場合は単一の値として処理
    if isinstance(sort_key, int):
        return [f"{sort_key:020d}"]
    elif isinstance(sort_key, str):
        return [sort_key.lower()]
    else:
        return [str(sort_key)]
