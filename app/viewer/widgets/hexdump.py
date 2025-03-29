"""
16進数ダンプビュー

ファイルの内容を16進数形式で表示するウィジェット
"""

import os
import sys
from typing import Optional, List, Dict, Any
import codecs

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QDialog, QTextEdit, 
        QLabel, QPushButton, QHBoxLayout, QApplication,
        QComboBox, QFileDialog, QMessageBox, QCheckBox
    )
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QFont, QFontDatabase
except ImportError:
    print("PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)


class HexDumpView(QDialog):
    """16進数ダンプビュー"""
    
    # サポートするエンコーディングの定義
    ENCODINGS = {
        "ASCII": "ascii",
        "Shift-JIS": "shift_jis",
        "UTF-8": "utf-8",
        "EUC-JP": "euc_jp"
    }
    
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
        self.setMinimumSize(750, 500)  # サイズを少し大きくして拡張UI向けに調整
        
        # データ保持用変数
        self._bytes_data = None
        self._max_bytes = max_bytes
        self._current_encoding = "ASCII"  # デフォルトエンコーディング
        self._show_ascii = True  # ASCII表示
        self._show_encoding = True  # その他エンコーディング表示
        
        # レイアウト
        self.layout = QVBoxLayout(self)
        
        # ヘッダラベル
        self.header_label = QLabel("ファイル先頭 256バイトの16進数ダンプ")
        self.layout.addWidget(self.header_label)
        
        # オプション設定エリア
        self._setup_options_area()
        
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
        
        # データ保存ボタンを追加
        self.save_button = QPushButton("データ保存...")
        self.save_button.clicked.connect(self._on_save_data)
        button_layout.addWidget(self.save_button)
        
        # スペーサー
        button_layout.addStretch()
        
        # 閉じるボタン
        self.close_button = QPushButton("閉じる")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        self.layout.addLayout(button_layout)
        
        # バイトデータを設定
        if bytes_data is not None:
            self.set_data(bytes_data, max_bytes)
    
    def _setup_options_area(self):
        """オプション設定エリアのセットアップ"""
        options_layout = QHBoxLayout()
        
        # エンコーディング選択ドロップダウン
        enc_label = QLabel("エンコーディング:")
        options_layout.addWidget(enc_label)
        
        self.encoding_combo = QComboBox()
        for enc_name in self.ENCODINGS.keys():
            self.encoding_combo.addItem(enc_name)
        self.encoding_combo.currentTextChanged.connect(self._on_encoding_changed)
        options_layout.addWidget(self.encoding_combo)
        
        # ASCII表示設定
        self.ascii_checkbox = QCheckBox("ASCII表示")
        self.ascii_checkbox.setChecked(self._show_ascii)
        self.ascii_checkbox.stateChanged.connect(self._on_display_option_changed)
        options_layout.addWidget(self.ascii_checkbox)
        
        # エンコーディング表示設定
        self.encoding_checkbox = QCheckBox("選択エンコーディング表示")
        self.encoding_checkbox.setChecked(self._show_encoding)
        self.encoding_checkbox.stateChanged.connect(self._on_display_option_changed)
        options_layout.addWidget(self.encoding_checkbox)
        
        # 右側に余白を追加
        options_layout.addStretch()
        
        self.layout.addLayout(options_layout)
    
    def _on_encoding_changed(self, encoding_name):
        """
        エンコーディング変更時の処理
        
        Args:
            encoding_name: 選択されたエンコーディング名
        """
        if encoding_name in self.ENCODINGS:
            self._current_encoding = encoding_name
            self._refresh_display()
    
    def _on_display_option_changed(self):
        """表示オプション変更時の処理"""
        self._show_ascii = self.ascii_checkbox.isChecked()
        self._show_encoding = self.encoding_checkbox.isChecked()
        self._refresh_display()
    
    def _refresh_display(self):
        """現在の設定で表示を更新"""
        if self._bytes_data is not None:
            self.set_data(self._bytes_data, self._max_bytes)
    
    def _on_save_data(self):
        """データ保存処理"""
        if not self._bytes_data:
            QMessageBox.warning(self, "保存エラー", "保存するデータがありません。")
            return
            
        try:
            # ファイル保存ダイアログを表示
            file_path, _ = QFileDialog.getSaveFileName(
                self, "データを保存", "", "バイナリファイル (*.bin);;すべてのファイル (*.*)"
            )
            
            if file_path:
                # ファイルに書き込み
                with open(file_path, 'wb') as f:
                    f.write(self._bytes_data)
                
                QMessageBox.information(self, "保存完了", f"データを {file_path} に保存しました。")
                
        except Exception as e:
            QMessageBox.critical(self, "保存エラー", f"データの保存中にエラーが発生しました:\n{str(e)}")
    
    def set_data(self, data: bytes, max_bytes: int = 256) -> None:
        """
        16進数ダンプを表示するためのデータを設定
        
        Args:
            data: バイトデータ
            max_bytes: 表示する最大バイト数
        """
        # データを保存
        self._bytes_data = data
        self._max_bytes = max_bytes
        
        # 表示するバイト数を制限
        display_data = data[:max_bytes]
        data_len = len(display_data)
        
        # 16進数ダンプと文字表示を生成
        result = []
        
        # ヘッダ行を追加
        header = "  オフセット   00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F"
        
        # エンコーディング表示用の列を追加
        if self._show_ascii:
            header += "  ASCII"
        if self._show_encoding:
            header += f"  {self._current_encoding}"
        
        result.append(header)
        result.append("  " + "-" * (78 + (0 if not self._show_ascii else 8) + (0 if not self._show_encoding else len(self._current_encoding) + 2)))
        
        # 選択されたエンコーディングの取得
        encoding = self.ENCODINGS.get(self._current_encoding, "ascii")
        
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
            
            # 行の基本部分
            line = f"  {offset}   {hex_str}"
            
            # ASCII文字表現（オプション）
            if self._show_ascii:
                ascii_str = ""
                for byte in chunk:
                    if 32 <= byte <= 126:  # 表示可能なASCII文字
                        ascii_str += chr(byte)
                    else:
                        ascii_str += "."
                line += f"  {ascii_str}"
            
            # 選択されたエンコーディングでの表示（オプション）
            if self._show_encoding and encoding != "ascii":
                enc_str = ""
                try:
                    # バイト列をデコードしてエンコーディングによる表示を生成
                    decoded = codecs.decode(chunk, encoding, errors='replace')
                    for char in decoded:
                        if ord(char) < 32:  # 制御文字
                            enc_str += "."
                        elif char == '�':  # 置換文字（デコード失敗）
                            enc_str += "."
                        else:
                            enc_str += char
                except Exception:
                    # デコードに失敗した場合は'.'で埋める
                    enc_str = "." * (len(chunk) // 2)  # マルチバイト文字を考慮
                
                # エンコーディング表示を追加
                line += f"  {enc_str}"
            
            result.append(line)
        
        # 全てのテキストを結合して表示
        self.hex_view.setPlainText("\n".join(result))
        
        # ヘッダラベルを更新
        if data_len < len(data):
            self.header_label.setText(f"ファイルの先頭 {data_len} バイト (全体は {len(data):,} バイト)")
        else:
            self.header_label.setText(f"ファイル全体 {len(data):,} バイト")
            
        # 保存ボタンの有効化
        self.save_button.setEnabled(len(data) > 0)


# テスト用コード
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # テスト用のデータ（ASCII、日本語Shift-JIS、UTF-8混在）
    test_data = bytearray(range(32, 128))  # ASCII可視範囲
    # 日本語文字列をShift-JISでエンコード
    sjis_text = "こんにちは世界".encode("shift_jis")
    utf8_text = "こんにちは世界".encode("utf-8")
    
    # テストデータに日本語を追加
    test_data.extend(sjis_text)
    test_data.extend(bytearray([0] * 16))  # 区切り
    test_data.extend(utf8_text)
    
    # ビューを作成して表示
    view = HexDumpView(title="テスト16進数ダンプ", bytes_data=test_data)
    view.show()
    
    sys.exit(app.exec())
