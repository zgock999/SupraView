"""
パスナビゲーションバー

現在のパスを表示し、パス履歴の管理と移動を行うウィジェット
"""

import os
import sys
from typing import List, Optional, Dict, Tuple

try:
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QApplication, QStyle
    from PySide6.QtGui import QIcon
    from PySide6.QtCore import Qt, Signal, QSize
except ImportError:
    print("PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)


class PathNavigationBar(QWidget):
    """パスナビゲーションバー"""
    
    # パスが変更されたときのシグナル（相対パス）
    path_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # レイアウト
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 戻るボタン
        self.back_button = QPushButton()
        self.back_button.setIcon(QApplication.style().standardIcon(QStyle.SP_ArrowBack))
        self.back_button.setToolTip("前に戻る")
        self.back_button.clicked.connect(self._go_back)
        layout.addWidget(self.back_button)
        
        # パス表示用のラベル（編集不可）
        self.path_label = QLabel()
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # テキスト選択のみ可能
        self.path_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 2px 5px; }")
        layout.addWidget(self.path_label)
        
        # 履歴 - 相対パスのみを保存
        self.path_history: List[str] = []
        self.current_history_pos = -1
        
        # 最初は戻るボタンを無効化
        self.back_button.setEnabled(False)
    
    def set_path(self, display_path: str, rel_path: str = "", add_to_history: bool = True):
        """
        現在のパスを設定
        
        Args:
            display_path: 表示用パス（完全なパス）- 現在は使用しない
            rel_path: 内部参照用の相対パス
            add_to_history: 履歴に追加するかどうか
        """
        # 相対パスが指定されていない場合は空文字列を使用
        path_to_use = rel_path if rel_path else ""
        
        # UIには相対パスを表示（ルートの場合は特別な表示）
        if not path_to_use:
            self.path_label.setText("/ (ルート)")
        else:
            self.path_label.setText(f"/{path_to_use}")
        
        if add_to_history:
            # 新しいパスを履歴に追加
            if self.current_history_pos < len(self.path_history) - 1:
                # 途中で履歴が分岐した場合は、以降の履歴を削除
                self.path_history = self.path_history[:self.current_history_pos + 1]
            
            # 同じパスが連続しないように
            if not self.path_history or self.path_history[-1] != path_to_use:
                # 履歴には相対パスのみを保存
                self.path_history.append(path_to_use)
                self.current_history_pos = len(self.path_history) - 1
            
            # 戻るボタンの有効状態を更新
            self.back_button.setEnabled(self.current_history_pos > 0)
    
    def _go_back(self):
        """履歴を戻る"""
        if self.current_history_pos > 0:
            self.current_history_pos -= 1
            # 履歴から相対パスを取得
            rel_path = self.path_history[self.current_history_pos]
            
            # 相対パスをラベルに設定
            if not rel_path:
                self.path_label.setText("/ (ルート)")
            else:
                self.path_label.setText(f"/{rel_path}")
            
            # 相対パスを送信（内部処理用）
            self.path_changed.emit(rel_path)
            
            # 戻るボタンの有効状態を更新
            self.back_button.setEnabled(self.current_history_pos > 0)
