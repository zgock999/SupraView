"""
デバッグユーティリティ

アプリケーション全体で統一されたデバッグ出力機能を提供する
"""

import os
import sys
from typing import Any

# 親パッケージからインポートできるようにパスを調整
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from logutils import log_print, log_trace, DEBUG, INFO, WARNING, ERROR, CRITICAL


class ViewerDebugMixin:
    """
    デバッグ出力機能を提供するMixinクラス
    
    このMixinをクラスに組み込むことで、統一されたデバッグ出力機能を使用できます。
    """
    
    def _init_debug_mixin(self, class_name: str = None):
        """
        デバッグMixinを初期化する
        
        Args:
            class_name: クラス名（指定がない場合は自動取得）
        """
        if class_name is None:
            class_name = self.__class__.__name__
        self._debug_class_name = class_name
    
    def debug_print(self, message: Any, *args, level: int = INFO, trace: bool = False, **kwargs):
        """
        デバッグ出力のラッパーメソッド
        
        Args:
            message: 出力するメッセージ
            *args: メッセージのフォーマット用引数
            level: ログレベル（デフォルトはINFO）
            trace: Trueならスタックトレース情報も出力する（デフォルトはFalse）
            **kwargs: 追加のキーワード引数
        """
        # クラス名をログの名前空間として使用
        name = f"arc.viewer.{self._debug_class_name}"
        
        if trace:
            log_trace(None, level, message, *args, name=name, **kwargs)
        else:
            log_print(level, message, *args, name=name, **kwargs)
    
    def debug_debug(self, message: Any, *args, trace: bool = False, **kwargs):
        """DEBUGレベルのログ出力"""
        self.debug_print(message, *args, level=DEBUG, trace=trace, **kwargs)
    
    def debug_info(self, message: Any, *args, trace: bool = False, **kwargs):
        """INFOレベルのログ出力"""
        self.debug_print(message, *args, level=INFO, trace=trace, **kwargs)
    
    def debug_warning(self, message: Any, *args, trace: bool = False, **kwargs):
        """WARNINGレベルのログ出力"""
        self.debug_print(message, *args, level=WARNING, trace=trace, **kwargs)
    
    def debug_error(self, message: Any, *args, trace: bool = False, **kwargs):
        """ERRORレベルのログ出力"""
        self.debug_print(message, *args, level=ERROR, trace=trace, **kwargs)
    
    def debug_critical(self, message: Any, *args, trace: bool = False, **kwargs):
        """CRITICALレベルのログ出力"""
        self.debug_print(message, *args, level=CRITICAL, trace=trace, **kwargs)
