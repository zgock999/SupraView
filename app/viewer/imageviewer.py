"""
画像プレビューウィンドウ

画像ファイルをプレビュー表示するための専用ウィンドウ
"""

import os
import sys
from typing import Optional

# 親パッケージからインポートできるようにパスを調整
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from PySide6.QtWidgets import (
        QMainWindow, QLabel, QApplication, QScrollArea, QToolBar,
        QFileDialog, QMessageBox, QVBoxLayout, QWidget, QSlider, QStatusBar
    )
    from PySide6.QtCore import Qt, QSize, QByteArray
    from PySide6.QtGui import (
        QPixmap, QImage, QResizeEvent, QWheelEvent, QKeyEvent,
        QAction  # QActionはQtGuiからインポート
    )
except ImportError as e:
    print(f"エラー: 必要なライブラリの読み込みに失敗しました: {e}")
    sys.exit(1)


class ImageViewerWindow(QMainWindow):
    """
    画像プレビュー専用ウィンドウ
    
    画像の表示、拡大/縮小、回転などの機能を提供
    """
    
    def __init__(self, title: str = "画像プレビュー", parent=None):
        """
        初期化
        
        Args:
            title: ウィンドウタイトル
            parent: 親ウィジェット
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(600, 400)
        
        # 画像データ
        self._pixmap = None
        self._original_pixmap = None
        self._zoom_factor = 1.0
        self._rotation = 0
        
        # UI初期化
        self._setup_ui()
    
    def _setup_ui(self):
        """UIの初期化"""
        # ステータスバーを作成
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # メインウィジェット
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # スクロールエリア
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        
        # 画像表示用ラベル
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMinimumSize(1, 1)
        self._image_label.setScaledContents(False)
        
        self._scroll_area.setWidget(self._image_label)
        layout.addWidget(self._scroll_area)
        
        self.setCentralWidget(central_widget)
        
        # ツールバーの作成
        self._create_toolbar()
        
        # ズームスライダーの作成
        self._create_zoom_slider()
        
        # ステータスバーの初期表示
        self.statusBar.showMessage("画像が読み込まれていません")
        
        # キーボードイベント用のフォーカス設定
        self.setFocusPolicy(Qt.StrongFocus)
    
    def _create_toolbar(self):
        """ツールバーの作成"""
        toolbar = QToolBar("画像操作")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)
        
        # 元のサイズに戻すアクション
        self._original_size_action = QAction("原寸大(100%)", self)
        self._original_size_action.triggered.connect(self._reset_zoom)
        toolbar.addAction(self._original_size_action)
        
        # フィットサイズアクション
        self._fit_action = QAction("画面に合わせる", self)
        self._fit_action.triggered.connect(self._fit_to_window)
        toolbar.addAction(self._fit_action)
        
        toolbar.addSeparator()
        
        # 回転アクション
        self._rotate_left_action = QAction("左に回転", self)
        self._rotate_left_action.triggered.connect(lambda: self._rotate_image(-90))
        toolbar.addAction(self._rotate_left_action)
        
        self._rotate_right_action = QAction("右に回転", self)
        self._rotate_right_action.triggered.connect(lambda: self._rotate_image(90))
        toolbar.addAction(self._rotate_right_action)
        
        toolbar.addSeparator()
        
        # 保存アクション
        self._save_action = QAction("保存...", self)
        self._save_action.triggered.connect(self._save_image)
        toolbar.addAction(self._save_action)
    
    def _create_zoom_slider(self):
        """ズームスライダーの作成"""
        zoom_toolbar = QToolBar("ズーム")
        self.addToolBar(Qt.BottomToolBarArea, zoom_toolbar)
        
        # ズームアウトアクション
        self._zoom_out_action = QAction("縮小", self)
        self._zoom_out_action.triggered.connect(lambda: self._change_zoom(0.8))
        zoom_toolbar.addAction(self._zoom_out_action)
        
        # ズームスライダー
        self._zoom_slider = QSlider(Qt.Horizontal)
        self._zoom_slider.setRange(10, 400)  # 10%～400%
        self._zoom_slider.setValue(100)      # 初期値は100%
        self._zoom_slider.setTickPosition(QSlider.TicksBelow)
        self._zoom_slider.setTickInterval(50)
        self._zoom_slider.valueChanged.connect(self._zoom_by_slider)
        zoom_toolbar.addWidget(self._zoom_slider)
        
        # ズームインアクション
        self._zoom_in_action = QAction("拡大", self)
        self._zoom_in_action.triggered.connect(lambda: self._change_zoom(1.25))
        zoom_toolbar.addAction(self._zoom_in_action)
        
        # ズーム率表示ラベル
        self._zoom_label = QLabel("100%")
        self._zoom_label.setMinimumWidth(50)
        zoom_toolbar.addWidget(self._zoom_label)
    
    def set_image(self, image_data: bytes, title: str = None):
        """
        画像データをセットして表示
        
        Args:
            image_data: 画像データのバイト列
            title: 画像タイトル（指定があればウィンドウタイトルを更新）
        
        Returns:
            表示に成功したかどうか
        """
        try:
            # QImageを作成
            q_image = QImage.fromData(QByteArray(image_data))
            if q_image.isNull():
                return False
            
            # QPixmapに変換
            pixmap = QPixmap.fromImage(q_image)
            if pixmap.isNull():
                return False
            
            # 画像を保存
            self._pixmap = pixmap
            self._original_pixmap = pixmap
            
            # 表示
            self._update_image()
            
            # タイトル更新
            if title:
                self.setWindowTitle(f"画像プレビュー: {title}")
            
            # 画像情報を表示
            self.statusBar.showMessage(f"画像サイズ: {q_image.width()} x {q_image.height()}  |  {len(image_data):,} バイト")
            
            # ウィンドウをアクティブに
            self.raise_()
            self.activateWindow()
            
            return True
            
        except Exception as e:
            print(f"画像の表示に失敗しました: {e}")
            return False
    
    def _update_image(self):
        """画像表示を更新"""
        if not self._pixmap:
            return
        
        # 現在の回転を考慮
        pixmap = self._pixmap
        if self._rotation:
            pixmap = pixmap.transformed(self._create_transform())
        
        # 現在のズーム率を適用
        if self._zoom_factor != 1.0:
            scaled_width = int(pixmap.width() * self._zoom_factor)
            scaled_height = int(pixmap.height() * self._zoom_factor)
            pixmap = pixmap.scaled(scaled_width, scaled_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # 画像を表示
        self._image_label.setPixmap(pixmap)
        self._image_label.adjustSize()
        
        # ズーム率表示を更新
        zoom_percent = int(self._zoom_factor * 100)
        self._zoom_label.setText(f"{zoom_percent}%")
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(zoom_percent)
        self._zoom_slider.blockSignals(False)
    
    def _change_zoom(self, factor: float):
        """
        ズーム率を変更
        
        Args:
            factor: 現在のズーム率に掛け合わせる係数
        """
        new_zoom = self._zoom_factor * factor
        # 10%～400%の範囲に制限
        new_zoom = max(0.1, min(4.0, new_zoom))
        
        self._zoom_factor = new_zoom
        self._update_image()
    
    def _zoom_by_slider(self, value: int):
        """
        スライダーによるズーム
        
        Args:
            value: スライダー値（パーセント）
        """
        self._zoom_factor = value / 100.0
        self._update_image()
    
    def _reset_zoom(self):
        """ズーム率を100%にリセット"""
        self._zoom_factor = 1.0
        self._update_image()
    
    def _fit_to_window(self):
        """画像をウィンドウサイズに合わせる"""
        if not self._pixmap:
            return
        
        # 画像サイズとスクロールエリアサイズを取得
        pixmap = self._pixmap
        if self._rotation:
            pixmap = pixmap.transformed(self._create_transform())
        
        img_width = pixmap.width()
        img_height = pixmap.height()
        
        view_width = self._scroll_area.viewport().width()
        view_height = self._scroll_area.viewport().height()
        
        # 幅と高さの縮小率を計算
        width_ratio = view_width / img_width
        height_ratio = view_height / img_height
        
        # 小さいほうの比率を採用（画像全体が表示されるように）
        self._zoom_factor = min(width_ratio, height_ratio) * 0.95  # 少し余裕を持たせる
        
        self._update_image()
    
    def _create_transform(self):
        """回転変換を作成"""
        from PySide6.QtGui import QTransform
        transform = QTransform()
        transform.rotate(self._rotation)
        return transform
    
    def _rotate_image(self, degrees: int):
        """
        画像を回転
        
        Args:
            degrees: 回転角度（度数法）
        """
        if not self._pixmap:
            return
        
        # 回転角度を更新
        self._rotation = (self._rotation + degrees) % 360
        
        # 画像を更新
        self._update_image()
    
    def _save_image(self):
        """画像を保存"""
        if not self._pixmap:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "画像を保存",
            "",
            "PNG画像 (*.png);;JPEG画像 (*.jpg);;BMP画像 (*.bmp);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            # 現在表示している画像（回転・ズーム適用済み）を保存
            current_pixmap = self._image_label.pixmap()
            if current_pixmap and current_pixmap.save(file_path):
                QMessageBox.information(self, "保存完了", f"画像を保存しました: {file_path}")
            else:
                QMessageBox.warning(self, "保存エラー", "画像の保存に失敗しました")
        except Exception as e:
            QMessageBox.critical(self, "保存エラー", f"画像の保存中にエラーが発生しました:\n{str(e)}")
    
    def resizeEvent(self, event: QResizeEvent):
        """
        ウィンドウリサイズ時の処理
        
        Args:
            event: リサイズイベント
        """
        super().resizeEvent(event)
        
        # 自動フィットモードならリサイズ時に再フィット
        pass
    
    def wheelEvent(self, event: QWheelEvent):
        """
        マウスホイールイベント処理
        
        Args:
            event: ホイールイベント
        """
        # Ctrlキーが押されていればズーム、それ以外はスクロール
        if event.modifiers() & Qt.ControlModifier:
            angle_delta = event.angleDelta().y()
            if angle_delta > 0:
                self._change_zoom(1.1)  # ズームイン
            else:
                self._change_zoom(0.9)  # ズームアウト
        else:
            # 親クラスのスクロール処理を実行
            super().wheelEvent(event)
    
    def keyPressEvent(self, event: QKeyEvent):
        """
        キー押下イベント処理
        
        Args:
            event: キーイベント
        """
        # キーショートカット
        if event.key() == Qt.Key_Plus:  # +キー
            self._change_zoom(1.1)
        elif event.key() == Qt.Key_Minus:  # -キー
            self._change_zoom(0.9)
        elif event.key() == Qt.Key_0:  # 0キー
            self._reset_zoom()
        elif event.key() == Qt.Key_F:  # Fキー
            self._fit_to_window()
        elif event.key() == Qt.Key_R:  # Rキー
            self._rotate_image(90)
        elif event.key() == Qt.Key_L:  # Lキー
            self._rotate_image(-90)
        elif event.key() == Qt.Key_S and event.modifiers() & Qt.ControlModifier:  # Ctrl+S
            self._save_image()
        else:
            super().keyPressEvent(event)


# スタンドアロン実行用
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageViewerWindow()
    
    # テスト用に画像を読み込む
    try:
        if len(sys.argv) > 1:
            image_path = sys.argv[1]
            with open(image_path, 'rb') as f:
                image_data = f.read()
            window.set_image(image_data, os.path.basename(image_path))
    except:
        pass
    
    window.show()
    sys.exit(app.exec())
