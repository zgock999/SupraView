"""
ファイルプレビューウィジェット

様々なファイルタイプに対応したプレビューを表示するためのQt Widget
"""

import os
import sys
import traceback
from typing import Optional

# 親パッケージからインポートできるようにパスを調整
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QLabel, QTextEdit, QScrollArea,
        QSplitter, QHBoxLayout, QSizePolicy
    )
    from PySide6.QtCore import Qt, QSize, QByteArray
    from PySide6.QtGui import QResizeEvent, QPixmap, QImage

    # アーカイブマネージャーのインポート
    from arc.manager import get_archive_manager
    from arc.arc import EntryInfo, EntryType
except ImportError as e:
    print(f"エラー: 必要なライブラリの読み込みに失敗しました: {e}")
    sys.exit(1)


class FilePreviewWidget(QWidget):
    """ファイルプレビューを表示するウィジェット"""
    
    # プレビュー可能なファイルタイプ
    TEXT_EXTENSIONS = [
        '.txt', '.md', '.json', '.xml', '.html', '.htm', '.css', '.js',
        '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.ini', '.cfg',
        '.log', '.csv', '.yaml', '.yml', '.toml', '.sh', '.bat', '.ps1'
    ]
    
    IMAGE_EXTENSIONS = [
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.webp'
    ]
    
    def __init__(self, parent=None):
        """初期化"""
        super().__init__(parent)
        self._manager = get_archive_manager()
        self._current_entry = None
        self._current_content = None
        self._setup_ui()
    
    def _setup_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # マージンを削除してプレビューを最大化
        
        # プレビュー情報を表示するヘッダー
        self._header_label = QLabel("プレビュー")
        self._header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._header_label)
        
        # テキストプレビュー用
        self._text_preview = QTextEdit()
        self._text_preview.setReadOnly(True)
        self._text_preview.setLineWrapMode(QTextEdit.WidgetWidth)
        self._text_preview.setVisible(False)
        layout.addWidget(self._text_preview)
        
        # 画像プレビュー用
        self._image_scroll_area = QScrollArea()
        self._image_scroll_area.setWidgetResizable(True)
        self._image_scroll_area.setVisible(False)
        
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setScaledContents(False)
        self._image_scroll_area.setWidget(self._image_label)
        layout.addWidget(self._image_scroll_area)
        
        # 一般プレビュー（ファイル情報のみ）
        self._info_label = QLabel("ファイルを選択してください")
        self._info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._info_label)
        
        # デフォルト表示
        self._reset_preview()
    
    def _reset_preview(self):
        """プレビューをリセット"""
        self._header_label.setText("プレビュー")
        self._text_preview.setVisible(False)
        self._image_scroll_area.setVisible(False)
        self._info_label.setVisible(True)
        self._info_label.setText("ファイルを選択してください")
        # 現在のエントリとコンテンツをクリア
        self._current_entry = None
        self._current_content = None
    
    def show_entry_preview(self, entry: EntryInfo, relative_path: str):
        """
        エントリのプレビューを表示
        
        Args:
            entry: プレビューするエントリ
            relative_path: current_pathからの相対パス
        """
        if not entry:
            self._reset_preview()
            return
            
        self._current_entry = entry
        
        # ヘッダー情報を更新
        self._header_label.setText(f"{entry.name}")
        
        # ディレクトリの場合は情報のみ表示
        if entry.type in [EntryType.DIRECTORY, EntryType.ARCHIVE]:
            self._text_preview.setVisible(False)
            self._image_scroll_area.setVisible(False)
            self._info_label.setVisible(True)
            
            if entry.type == EntryType.DIRECTORY:
                self._info_label.setText("フォルダです")
            else:
                self._info_label.setText(f"アーカイブファイルです\nサイズ: {entry.size:,} バイト")
            return
        
        # ファイル内容をロード
        try:
            entry_rel_path = relative_path
            if entry_rel_path and not entry_rel_path.endswith('/'):
                entry_rel_path += '/'
            entry_rel_path += entry.name
            
            content = self._manager.read_file(entry_rel_path)
            self._current_content = content
            
            if content is None:
                self._info_label.setText("ファイル内容を読み込めませんでした")
                self._info_label.setVisible(True)
                self._text_preview.setVisible(False)
                self._image_scroll_area.setVisible(False)
                return
                
            # ファイル拡張子から種類を判断
            _, ext = os.path.splitext(entry.name.lower())
            
            # テキストファイル
            if ext in self.TEXT_EXTENSIONS:
                self._show_text_preview(content)
            # 画像ファイル
            elif ext in self.IMAGE_EXTENSIONS:
                self._show_image_preview(content)
            # その他のファイル形式
            else:
                self._show_binary_preview(content, ext, entry.size)
            
        except Exception as e:
            print(f"プレビューエラー: {e}")
            traceback.print_exc()
            self._info_label.setText(f"プレビュー中にエラーが発生しました:\n{str(e)}")
            self._info_label.setVisible(True)
            self._text_preview.setVisible(False)
            self._image_scroll_area.setVisible(False)
    
    def _show_text_preview(self, content: bytes):
        """
        テキストプレビューを表示
        
        Args:
            content: ファイル内容のバイナリデータ
        """
        # バイナリの文字コード判定
        encoding = 'utf-8'  # デフォルト
        
        # よく使用される文字エンコーディングを順番に試す
        encodings = ['utf-8', 'shift_jis', 'euc-jp', 'iso-2022-jp', 'cp932', 'latin-1']
        detected_text = None
        detected_encoding = None
        
        for enc in encodings:
            try:
                text = content.decode(enc)
                detected_text = text
                detected_encoding = enc
                break
            except UnicodeDecodeError:
                continue
        
        # どのエンコーディングでも失敗した場合は強制的にASCIIとして処理（不明文字は置換）
        if detected_text is None:
            detected_text = content.decode('ascii', errors='replace')
            detected_encoding = 'ascii (fallback)'
        
        # テキストプレビューを更新
        self._text_preview.setText(detected_text)
        
        # エンコーディング情報をヘッダーに追加
        current_header = self._header_label.text()
        self._header_label.setText(f"{current_header} (エンコーディング: {detected_encoding})")
        
        # テキストプレビューを表示
        self._text_preview.setVisible(True)
        self._info_label.setVisible(False)
        self._image_scroll_area.setVisible(False)
    
    def _show_image_preview(self, content: bytes):
        """
        画像プレビューを表示
        
        Args:
            content: ファイル内容のバイナリデータ
        """
        # QImageでバイナリから画像を読み込み
        image = QImage.fromData(QByteArray(content))
        
        if image.isNull():
            self._info_label.setText("画像を読み込めませんでした")
            self._info_label.setVisible(True)
            self._text_preview.setVisible(False)
            self._image_scroll_area.setVisible(False)
            return
            
        # 画像情報をヘッダーに追加
        current_header = self._header_label.text()
        self._header_label.setText(f"{current_header} ({image.width()}x{image.height()})")
        
        # QPixmapに変換
        pixmap = QPixmap.fromImage(image)
        
        # ウィジェットに合わせてリサイズ
        preview_width = self._image_scroll_area.width() - 20  # 余白を確保
        if pixmap.width() > preview_width:
            pixmap = pixmap.scaledToWidth(preview_width, Qt.SmoothTransformation)
        
        # 画像を表示
        self._image_label.setPixmap(pixmap)
        self._image_label.adjustSize()
        
        self._image_scroll_area.setVisible(True)
        self._info_label.setVisible(False)
        self._text_preview.setVisible(False)
    
    def _show_binary_preview(self, content: bytes, ext: str, size: int):
        """
        バイナリファイルのプレビュー情報を表示
        
        Args:
            content: ファイル内容のバイナリデータ
            ext: ファイルの拡張子
            size: ファイルサイズ
        """
        # ファイルタイプを判定
        file_type = self._detect_file_type(content, ext)
        
        # ファイル情報を表示
        info_text = f"ファイル形式: {file_type}\nサイズ: {size:,} バイト"
        
        # バイナリデータの先頭部分をヘキサダンプ表示
        hex_preview = self._create_hex_preview(content)
        if hex_preview:
            info_text += f"\n\nHexダンプ (先頭128バイト):\n{hex_preview}"
        
        self._info_label.setText(info_text)
        self._info_label.setVisible(True)
        self._text_preview.setVisible(False)
        self._image_scroll_area.setVisible(False)
    
    def _detect_file_type(self, content: bytes, ext: str) -> str:
        """
        バイナリデータの種類を判定
        
        Args:
            content: ファイル内容のバイナリデータ
            ext: ファイルの拡張子
            
        Returns:
            ファイルタイプの説明
        """
        # 拡張子がある場合はそれを利用
        if ext:
            ext_type = ext[1:].upper()  # 先頭の.を除去して大文字に
        else:
            ext_type = "不明"
        
        # マジックナンバーに基づく判定
        if not content or len(content) < 4:
            return f"{ext_type} ファイル (バイナリ)"
        
        # 代表的なファイル形式のマジックナンバーをチェック
        if content.startswith(b'\xff\xd8\xff'):
            return "JPEG イメージ"
        elif content.startswith(b'\x89PNG\r\n\x1a\n'):
            return "PNG イメージ"
        elif content.startswith(b'GIF8'):
            return "GIF イメージ"
        elif content.startswith(b'BM'):
            return "BMP イメージ"
        elif content.startswith(b'PK\x03\x04'):
            return "ZIP アーカイブ"
        elif content.startswith(b'Rar!\x1a\x07'):
            return "RAR アーカイブ"
        elif content.startswith(b'7z\xbc\xaf\x27\x1c'):
            return "7-Zip アーカイブ"
        elif content.startswith(b'\x1f\x8b\x08'):
            return "GZIP アーカイブ"
        elif content.startswith(b'%PDF'):
            return "PDF ドキュメント"
        
        # 拡張子を元にした表示
        return f"{ext_type} ファイル (バイナリ)"
    
    def _create_hex_preview(self, content: bytes, max_bytes: int = 128) -> str:
        """
        バイナリデータのヘキサダンプを作成
        
        Args:
            content: バイナリデータ
            max_bytes: 表示する最大バイト数
            
        Returns:
            ヘキサダンプの文字列表現
        """
        if not content:
            return ""
        
        # 表示バイト数を制限
        display_bytes = content[:max_bytes]
        
        # ヘキサダンプと文字表示を作成
        hex_lines = []
        for i in range(0, len(display_bytes), 16):
            chunk = display_bytes[i:i+16]
            # アドレス表示
            line = f"{i:04x}: "
            
            # ヘキサ表示
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            line += f"{hex_part:<47}"  # 最大16バイトx3文字（2桁の16進数 + スペース）
            
            # ASCII表示（表示可能な文字のみ）
            ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            line += f" | {ascii_part}"
            
            hex_lines.append(line)
        
        return "\n".join(hex_lines)
    
    def resizeEvent(self, event: QResizeEvent):
        """
        リサイズ時に画像サイズを調整
        
        Args:
            event: リサイズイベント
        """
        super().resizeEvent(event)
        
        # 画像プレビュー表示中の場合、サイズを再調整
        if self._image_scroll_area.isVisible() and self._image_label.pixmap() is not None:
            pixmap = self._image_label.pixmap()
            preview_width = self._image_scroll_area.width() - 20
            if pixmap.width() > preview_width:
                resized_pixmap = pixmap.scaledToWidth(preview_width, Qt.SmoothTransformation)
                self._image_label.setPixmap(resized_pixmap)
                self._image_label.adjustSize()
