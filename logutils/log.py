"""
ロギング用ユーティリティ

アプリケーション全体でのロギング操作を統一的に扱うためのユーティリティ関数群
"""
import os
import sys
import traceback
import datetime
from typing import Optional, Any, Union, TextIO

# Pythonの標準loggingモジュールをインポート
import logging as py_logging

# ログレベルの定数定義
DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40
CRITICAL = 50

# デフォルトのログレベル（ERRORに変更）
_log_level = ERROR

# ロガーオブジェクトの格納用辞書
_loggers = {}

# ロギング先のファイル
_log_file = None

def setup_logging(level: int = ERROR, logfile: str = None) -> None:
    """
    ロギングシステムをセットアップする
    
    Args:
        level: ログレベル（デフォルトはERROR）
        logfile: ログの出力先ファイル（デフォルトはNone）
    """
    global _log_level, _log_file
    _log_level = level
    
    # 既存のロガーのレベルを更新
    for logger in _loggers.values():
        logger.setLevel(_log_level)
    
    if logfile:
        try:
            # ログディレクトリが存在しない場合は作成
            log_dir = os.path.dirname(logfile)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # ファイルを開いてログ出力先として設定
            _log_file = open(logfile, 'a', encoding='utf-8')
        except Exception as e:
            sys.stderr.write(f"ログファイルを開けませんでした: {e}\n")
            _log_file = None

def get_logger(name: str) -> py_logging.Logger:
    """
    名前付きのロガーを取得する
    
    Args:
        name: ロガー名
        
    Returns:
        設定済みのロガーオブジェクト
    """
    if name in _loggers:
        return _loggers[name]
    
    # 新しいロガーを作成
    logger = py_logging.getLogger(name)
    logger.setLevel(_log_level)
    
    # フォーマッターを設定
    formatter = py_logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    
    # コンソールハンドラーを追加
    console = py_logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    # ファイルハンドラーも設定されていれば追加
    if _log_file:
        file_handler = py_logging.FileHandler(_log_file.name)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    _loggers[name] = logger
    return logger

def log_print(level: int, message: Any, *args, name: str = None, **kwargs) -> None:
    """
    指定したレベルでメッセージをログに出力する
    
    Args:
        level: ログレベル
        message: 出力するメッセージ
        *args: メッセージのフォーマット引数
        name: ロガー名（デフォルトは'app'）
        **kwargs: その他のキーワード引数
    """
    if level < _log_level:
        return
    
    logger_name = name or 'app'
    logger = get_logger(logger_name)
    
    # レベルに応じたログメソッドを使用
    if level >= CRITICAL:
        logger.critical(message, *args, **kwargs)
    elif level >= ERROR:
        logger.error(message, *args, **kwargs)
    elif level >= WARNING:
        logger.warning(message, *args, **kwargs)
    elif level >= INFO:
        logger.info(message, *args, **kwargs)
    else:
        logger.debug(message, *args, **kwargs)

def log_trace(e: Optional[Exception], level: int, message: Any, *args, name: str = None, **kwargs) -> None:
    """
    例外のトレース情報を含めてログに出力する
    
    Args:
        e: 例外オブジェクト（NoneでもOK）
        level: ログレベル
        message: 出力するメッセージ
        *args: メッセージのフォーマット引数
        name: ロガー名（デフォルトは'app'）
        **kwargs: その他のキーワード引数
    """
    if level < _log_level:
        return
    
    # まずメッセージを出力
    log_print(level, message, *args, name=name, **kwargs)
    
    # スタックトレースを取得して出力
    if e:
        stack = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
    else:
        stack = ''.join(traceback.format_stack()[:-1])  # 自分自身の呼び出しを除外
    
    # スタックトレースを出力
    logger_name = name or 'app'
    logger = get_logger(logger_name)
    
    # レベルに応じたログメソッドを使用
    if level >= CRITICAL:
        logger.critical(f"スタックトレース:\n{stack}")
    elif level >= ERROR:
        logger.error(f"スタックトレース:\n{stack}")
    elif level >= WARNING:
        logger.warning(f"スタックトレース:\n{stack}")
    elif level >= INFO:
        logger.info(f"スタックトレース:\n{stack}")
    else:
        logger.debug(f"スタックトレース:\n{stack}")
