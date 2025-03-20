"""
16進数ダンプビュー

ファイルの内容を16進数形式で表示するウィジェット
"""

import os
import sys
from typing import Optional, List

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QDialog, QTextEdit, 
        QLabel, QPushButton, QHBoxLayout, QApplication
    )
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QFont, QFontDatabase
except ImportError:
    print("PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)


class HexDumpView(QDialog):
    """16進数ダンプビュー"""
    
    def __init__(self, parent=None, title="16進数ダンプビュー", bytes_data=None, max_bytes=256):
        """
        初期化
        
        Args:
            parent: 親ウィジェット
            title: ウィンドウタイトル
            bytes_data: 表示するバイトデータ
            max_bytes: 表示する最大バイト数
        """
        super().__init__(parent)
        
        self.setWindowTitle(title)
        self.setMinimumSize(650, 400)
        
        # レイアウト
        self.layout = QVBoxLayout(self)
        
        # ヘッダラベル
        self.header_label = QLabel("ファイル先頭 256バイトの16進数ダンプ")
        self.layout.addWidget(self.header_label)
        
        # 16進数データ表示用のテキストエディタ
        self.hex_view = QTextEdit()
        self.hex_view.setReadOnly(True)
        
        # 等幅フォントを設定
        monospace_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        monospace_font.setPointSize(10)
        self.hex_view.setFont(monospace_font)
        
        # 背景色を少し暗めに
        self.hex_view.setStyleSheet("background-color: #F0F0F0;")
        
        self.layout.addWidget(self.hex_view)
        
        # ボタンレイアウト
        button_layout = QHBoxLayout()
        
        # 閉じるボタン
        self.close_button = QPushButton("閉じる")
        self.close_button.clicked.connect(self.close)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        self.layout.addLayout(button_layout)
        
        # バイトデータを設定
        if bytes_data is not None:
            self.set_data(bytes_data, max_bytes)
    
    def set_data(self, data: bytes, max_bytes: int = 256) -> None:
        """
        16進数ダンプを表示するためのデータを設定
        
        Args:
            data: バイトデータ
            max_bytes: 表示する最大バイト数
        """
        # 表示するバイト数を制限
        display_data = data[:max_bytes]
        data_len = len(display_data)
        
        # 16進数ダンプと文字表示を生成
        result = []
        result.append("  オフセット   00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F  文字表現")
        result.append("  " + "-" * 78)
        
        for i in range(0, data_len, 16):
            # 現在の行のバイト
            chunk = display_data[i:i+16]
            
            # オフセット
            offset = f"{i:08X}"
            
            # 16進数表現
            hex_values = []
            for j in range(16):
                if i + j < data_len:
                    hex_values.append(f"{chunk[j]:02X}")
                else:
                    hex_values.append("  ")
            
            # 8バイトごとに区切る
            hex_str = " ".join(hex_values[:8]) + "  " + " ".join(hex_values[8:])
            
            # ASCII文字表現
            ascii_str = ""
            for byte in chunk:
                if 32 <= byte <= 126:  # 表示可能なASCII文字
                    ascii_str += chr(byte)
                else:
                    ascii_str += "."
            
            # 行を結合
            line = f"  {offset}   {hex_str}  {ascii_str}"
            result.append(line)
        
        # 全てのテキストを結合して表示
        self.hex_view.setPlainText("\n".join(result))
        
        # ヘッダラベルを更新
        if data_len < len(data):
            self.header_label.setText(f"ファイルの先頭 {data_len} バイト (全体は {len(data):,} バイト)")
        else:
            self.header_label.setText(f"ファイル全体 {len(data):,} バイト")


# テスト用コード
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # テスト用のデータ
    test_data = bytes(range(256))  # 0〜255のバイト値
    
    # ビューを作成して表示
    view = HexDumpView(title="テスト16進数ダンプ", bytes_data=test_data)
    view.show()
    
    sys.exit(app.exec())
