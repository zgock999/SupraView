"""
画像プレビューウィンドウ

アーカイブ内の画像ファイルをプレビュー表示するためのメインウィンドウ
"""

import os
import sys
from typing import Optional, Dict, Any

# プロジェクトルートへのパスを追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logutils import log_print, INFO, WARNING, ERROR

try:
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QLabel,
        QScrollArea, QSizePolicy, QStatusBar
    )
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QPixmap, QResizeEvent, QWheelEvent, QKeyEvent
except ImportError:
    log_print(ERROR, "PySide6が必要です。pip install pyside6 でインストールしてください。")
    sys.exit(1)

# 内部モジュールをインポート
from .image_processor import (
    get_supported_extensions, load_image_from_bytes, format_image_info
)


class ImagePreviewWindow(QMainWindow):
    """画像ファイルをプレビュー表示するためのウィンドウ"""
    
    # サポートする画像形式の拡張子
    SUPPORTED_EXTENSIONS = get_supported_extensions()
    
    def __init__(self, parent=None, archive_manager=None):
        """
        画像プレビューウィンドウの初期化
        
        Args:
            parent: 親ウィジェット（省略可能）
            archive_manager: 画像データを取得するためのアーカイブマネージャ
        """
        super().__init__(parent)
        
        # ウィンドウの基本設定
        self.setWindowTitle("画像プレビュー")
        self.resize(800, 600)
        
        # アーカイブマネージャの参照を保存
        self.archive_manager = archive_manager
        
        # UIコンポーネントのセットアップ
        self._setup_ui()
        
        # インスタンス変数の初期化
        self._current_image_path = None
        self._current_pixmap = None
        self._current_image_data = None
        self._original_pixmap = None
        self._zoom_factor = 1.0
        self._image_info = {}
        self._numpy_image = None
        
        # キーボードフォーカスを有効化
        self.setFocusPolicy(Qt.StrongFocus)
        
        log_print(INFO, "画像プレビューウィンドウが初期化されました")
    
    def _setup_ui(self):
        """UIコンポーネントの初期化"""
        # 中央ウィジェットとレイアウトの設定
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # スクロールエリアの作成
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        
        # 画像ラベルの作成
        self.image_label = QLabel("画像が読み込まれていません")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # スクロールエリアにラベルを設定
        self.scroll_area.setWidget(self.image_label)
        
        # レイアウトにスクロールエリアを追加
        self.layout.addWidget(self.scroll_area)
        
        # ステータスバーを追加
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
    
    def load_image_from_path(self, path: str) -> bool:
        """
        アーカイブ内の指定パスから画像を読み込む
        
        Args:
            path: アーカイブ内の画像ファイルパス（カレントディレクトリからの相対パス）
            
        Returns:
            読み込みに成功した場合はTrue、失敗した場合はFalse
        """
        if not self.archive_manager:
            log_print(ERROR, "アーカイブマネージャが設定されていません")
            self.statusbar.showMessage("エラー: アーカイブマネージャが設定されていません")
            return False
        
        try:
            # ファイル名の拡張子を確認
            _, ext = os.path.splitext(path.lower())
            if ext not in self.SUPPORTED_EXTENSIONS:
                log_print(WARNING, f"サポートされていない画像形式です: {ext}")
                self.statusbar.showMessage(f"サポートされていない画像形式です: {ext}")
                return False
            
            # アーカイブマネージャを使用して画像データを取得
            # extract_file から extract_item に変更
            image_data = self.archive_manager.extract_item(path)
            if not image_data:
                log_print(ERROR, f"画像データの読み込みに失敗しました: {path}")
                self.statusbar.showMessage(f"画像データの読み込みに失敗しました: {path}")
                return False
            
            # 画像処理モジュールを使用して画像を読み込み
            pixmap, numpy_array, info = load_image_from_bytes(image_data, path)
            
            if pixmap is None:
                log_print(ERROR, f"画像の表示に失敗しました: {path}")
                self.statusbar.showMessage(f"画像の表示に失敗しました: {path}")
                return False
            
            # 画像表示の設定
            self._current_image_path = path
            self._current_image_data = image_data
            self._current_pixmap = pixmap
            self._original_pixmap = pixmap
            self._numpy_image = numpy_array
            self._image_info = info
            
            # 画像をウィンドウサイズに合わせて表示
            self._adjust_image_size()
            
            # ウィンドウタイトルを更新
            self.setWindowTitle(f"画像プレビュー - {os.path.basename(path)}")
            
            # 画像情報をステータスバーに表示
            self._update_status_info()
            
            return True
            
        except Exception as e:
            log_print(ERROR, f"画像の読み込み中にエラーが発生しました: {e}")
            self.statusbar.showMessage(f"エラー: {str(e)}")
            return False
    
    def _update_status_info(self):
        """ステータスバーに画像情報を表示"""
        if not self._current_pixmap:
            return
            
        try:
            # 基本情報の表示
            filename = os.path.basename(self._current_image_path) if self._current_image_path else "画像"
            width = self._current_pixmap.width()
            height = self._current_pixmap.height()
            size_kb = len(self._current_image_data) / 1024 if self._current_image_data else 0
            
            # NumPy情報があれば追加
            if self._numpy_image is not None:
                channels = 1 if len(self._numpy_image.shape) == 2 else self._numpy_image.shape[2]
                status_msg = f"{filename} - {width}x{height} - {channels}チャンネル ({size_kb:.1f} KB)"
            else:
                status_msg = f"{filename} - {width}x{height} ({size_kb:.1f} KB)"
                
            self.statusbar.showMessage(status_msg)
            
        except Exception as e:
            log_print(ERROR, f"ステータス情報の更新に失敗しました: {e}")
    
    def _adjust_image_size(self):
        """画像サイズをウィンドウに合わせて調整する"""
        if not self._current_pixmap:
            return
        
        # スクロールエリアのサイズを取得
        viewport_size = self.scroll_area.viewport().size()
        
        # 原画像のサイズを取得
        img_size = self._current_pixmap.size()
        
        # 表示サイズを計算（ズーム係数を適用）
        scaled_width = int(img_size.width() * self._zoom_factor)
        scaled_height = int(img_size.height() * self._zoom_factor)
        
        # ビューポートのサイズに収まるかどうかを確認
        if scaled_width <= viewport_size.width() and scaled_height <= viewport_size.height():
            # ビューポート内に収まる場合は、そのままのサイズで表示
            self.image_label.setPixmap(self._current_pixmap.scaled(
                scaled_width, scaled_height, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            ))
        else:
            # ビューポートより大きい場合は、縮小して表示
            self.image_label.setPixmap(self._current_pixmap.scaled(
                viewport_size.width(), viewport_size.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
    
    def zoom_in(self):
        """画像を拡大する"""
        self._zoom_factor *= 1.25
        self._adjust_image_size()
        self.statusbar.showMessage(f"ズーム: {self._zoom_factor:.2f}x")
    
    def zoom_out(self):
        """画像を縮小する"""
        self._zoom_factor *= 0.8
        self._adjust_image_size()
        self.statusbar.showMessage(f"ズーム: {self._zoom_factor:.2f}x")
    
    def reset_zoom(self):
        """ズームをリセットする"""
        self._zoom_factor = 1.0
        self._adjust_image_size()
        self.statusbar.showMessage(f"ズーム: 1.00x")
    
    def keyPressEvent(self, event: QKeyEvent):
        """キーが押されたときのイベント処理"""
        # エスケープキーでウィンドウを閉じる
        if event.key() == Qt.Key_Escape:
            self.close()
        # プラスキーで拡大
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self.zoom_in()
        # マイナスキーで縮小
        elif event.key() == Qt.Key_Minus:
            self.zoom_out()
        # 0キーでズームリセット
        elif event.key() == Qt.Key_0:
            self.reset_zoom()
        else:
            super().keyPressEvent(event)
    
    def wheelEvent(self, event: QWheelEvent):
        """マウスホイールイベント処理（ズーム用）"""
        # マウスホイールが上に回転した場合は拡大、下に回転した場合は縮小
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        
        event.accept()  # イベントを処理したことを通知
    
    def resizeEvent(self, event: QResizeEvent):
        """ウィンドウリサイズイベント処理"""
        # リサイズ時に画像サイズを調整
        self._adjust_image_size()
        super().resizeEvent(event)
    
    def show_image_info(self):
        """画像の詳細情報を表示する"""
        if not self._image_info:
            self.statusbar.showMessage("画像情報がありません")
            return
            
        # 画像情報を整形して表示
        info_text = format_image_info(self._image_info)
        
        # ここに情報表示用のダイアログを実装することもできます
        self.statusbar.showMessage("画像情報を表示しました")
        log_print(INFO, f"画像情報: \n{info_text}")


# 単体テスト用のコード
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # テスト用の画像ファイルパス
    test_image_path = None
    if len(sys.argv) > 1:
        test_image_path = sys.argv[1]
    
    window = ImagePreviewWindow()
    window.show()
    
    # テスト用の画像ファイルが指定された場合は読み込み
    if test_image_path and os.path.isfile(test_image_path):
        # ローカルファイルを直接読み込むテスト
        try:
            with open(test_image_path, 'rb') as f:
                image_data = f.read()
            # 画像処理モジュールを使用
            pixmap, numpy_array, info = load_image_from_bytes(image_data, test_image_path)
            if pixmap:
                window._current_pixmap = pixmap
                window._original_pixmap = pixmap
                window._numpy_image = numpy_array
                window._image_info = info
                window._current_image_path = test_image_path
                window._current_image_data = image_data
                window._adjust_image_size()
                window._update_status_info()
                window.setWindowTitle(f"画像プレビュー - {os.path.basename(test_image_path)}")
        except Exception as e:
            print(f"画像の読み込みに失敗しました: {e}")
    
    sys.exit(app.exec())
