"""
ナビゲーションバーウィジェット

画像プレビューウィンドウの下部に表示されるナビゲーションバー
"""

import os
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QStyle, QApplication
from PySide6.QtCore import Qt, Signal, QTimer, QEvent, QSize
from PySide6.QtGui import QEnterEvent, QFont, QIcon, QCursor

from logutils import log_print, INFO, DEBUG


class NavigationBar(QWidget):
    """
    画像プレビュー用ナビゲーションバー
    
    マウスカーソルがウィンドウ下部に移動した時に表示され、
    マウスが離れると自動的に非表示になる。
    """
    
    # ナビゲーションシグナル
    first_image_requested = Signal()    # 全体先頭へ
    first_folder_requested = Signal()   # フォルダ先頭へ（新規追加）
    prev_folder_requested = Signal()    # 前のフォルダ
    prev_image_requested = Signal()     # 前へ
    toggle_fullscreen_requested = Signal() # フルスクリーンモード切替
    next_image_requested = Signal()     # 次へ
    last_folder_requested = Signal()    # フォルダ末尾へ（新規追加）
    next_folder_requested = Signal()    # 次のフォルダ
    last_image_requested = Signal()     # 全体末尾へ
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 表示状態
        self._visible = False
        
        # 右から左モード（デュアルモードで右が第一画面の時）
        self._right_to_left = False
        
        # 検出エリアの割合（下部からの割合）- 感度を上げるために25%に設定
        self._detection_area_ratio = 0.25
        
        # ウィジェットの透明度を設定
        self.setWindowOpacity(0.9)
        
        # 自動非表示用タイマー
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide_bar)
        
        # レイアウト設定
        self._setup_ui()
        
        # ボタンのツールチップを設定
        self._setup_tooltips()
        
        # 初期状態は非表示
        self.hide()
        
        # マウス追跡を有効化（マウスの出入りを検出するため）
        self.setMouseTracking(True)
        
        # イベントフィルターを設定して親ウィジェットのイベントを監視
        if parent:
            parent.installEventFilter(self)
        
        # 親ウィンドウに対する相対位置を設定
        self._set_position()
        
        # マウス位置更新用タイマー（マウスが動かない場合でも定期的にチェック）
        self._check_mouse_timer = QTimer(self)
        self._check_mouse_timer.setInterval(500)  # 500ミリ秒ごとにチェック
        self._check_mouse_timer.timeout.connect(self._check_mouse_position)
        self._check_mouse_timer.start()
    
    def _setup_ui(self):
        """UIコンポーネントをセットアップ"""
        # 水平レイアウトを作成
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # 標準アイコン取得用のStyleオブジェクト
        style = self.style()
        
        # ボタンを作成
        self.first_image_button = QPushButton()
        self.first_image_button.setIcon(style.standardIcon(QStyle.SP_MediaSkipBackward))
        
        self.prev_folder_button = QPushButton()
        self.prev_folder_button.setIcon(style.standardIcon(QStyle.SP_DirIcon))
        
        self.first_folder_button = QPushButton()
        self.first_folder_button.setIcon(style.standardIcon(QStyle.SP_FileDialogStart))
        
        self.prev_image_button = QPushButton()
        self.prev_image_button.setIcon(style.standardIcon(QStyle.SP_MediaSeekBackward))
        
        self.fullscreen_button = QPushButton()
        self.fullscreen_button.setIcon(style.standardIcon(QStyle.SP_TitleBarMaxButton))
        
        self.next_image_button = QPushButton()
        self.next_image_button.setIcon(style.standardIcon(QStyle.SP_MediaSeekForward))
        
        self.last_folder_button = QPushButton()
        self.last_folder_button.setIcon(style.standardIcon(QStyle.SP_FileDialogEnd))
        
        self.next_folder_button = QPushButton()
        self.next_folder_button.setIcon(style.standardIcon(QStyle.SP_DirLinkIcon))
        
        self.last_image_button = QPushButton()
        self.last_image_button.setIcon(style.standardIcon(QStyle.SP_MediaSkipForward))
        
        # すべてのボタンを正方形に設定してアイコンを中央に配置
        for button in [self.first_image_button, self.prev_folder_button, self.first_folder_button, 
                      self.prev_image_button, self.fullscreen_button,
                      self.next_image_button, self.last_folder_button, self.next_folder_button, 
                      self.last_image_button]:
            button.setFixedSize(48, 48)  # 正方形のボタン
            button.setIconSize(QSize(32, 32))  # アイコンサイズを大きめに
            button.setFlat(True)  # フラットスタイル
        
        # フルスクリーンボタンを少し大きくする
        self.fullscreen_button.setFixedSize(56, 56)
        self.fullscreen_button.setIconSize(QSize(40, 40))
        
        # 中央配置のために縦横比を明示的に制御
        self.setFixedHeight(70)  # 固定高さを設定
        
        # レイアウト構造を単純化し、フルスクリーンボタンを中央に配置
        # 中央揃えのためにコンテナウィジェットを作成
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(10)
        
        # 左側ボタングループを追加
        container_layout.addWidget(self.first_image_button)
        container_layout.addWidget(self.prev_folder_button)
        container_layout.addWidget(self.first_folder_button)
        container_layout.addWidget(self.prev_image_button)
        
        # フルスクリーンボタンとの間に小さな余白
        container_layout.addSpacing(5)
        
        # フルスクリーンボタンを追加
        container_layout.addWidget(self.fullscreen_button)
        
        # フルスクリーンボタンとの間に小さな余白
        container_layout.addSpacing(5)
        
        # 右側ボタングループを追加
        container_layout.addWidget(self.next_image_button)
        container_layout.addWidget(self.last_folder_button)
        container_layout.addWidget(self.next_folder_button)
        container_layout.addWidget(self.last_image_button)
        
        # コンテナをメインレイアウトに追加し、中央配置
        layout.addStretch(1)
        layout.addWidget(container, 0, Qt.AlignCenter)
        layout.addStretch(1)
        
        # シグナルとスロットを接続
        self.first_image_button.clicked.connect(self.first_image_requested)
        self.first_folder_button.clicked.connect(self.first_folder_requested)
        self.prev_folder_button.clicked.connect(self.prev_folder_requested)
        self.prev_image_button.clicked.connect(self.prev_image_requested)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen_requested)
        self.next_image_button.clicked.connect(self.next_image_requested)
        self.last_folder_button.clicked.connect(self.last_folder_requested)
        self.next_folder_button.clicked.connect(self.next_folder_requested)
        self.last_image_button.clicked.connect(self.last_image_requested)
        
        # モダンなアイコンボタン用のスタイルシート - 白い半透明背景と縁取りを追加
        self.setStyleSheet("""
            NavigationBar {
                background-color: rgba(40, 40, 40, 180);
                border-radius: 8px;
                border: 1px solid rgba(200, 200, 200, 100);
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 160);  /* 白い半透明背景 */
                border-radius: 24px;
                border: 2px solid rgba(64, 64, 64, 200);  /* 白い縁取り */
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 200);  /* ホバー時は少し明るく */
                border: 2px solid rgba( 0,  0,  0, 255);  /* ホバー時は縁を完全に白く */
            }
            QPushButton:pressed {
                background-color: rgba(220, 220, 220, 230);  /* 押下時は少し暗く */
                border: 2px solid rgba(180, 180, 180, 255);  /* 押下時は縁を少し暗く */
            }
            /* アイコンの色が見づらい場合にはアイコン自体に影をつける */
            QPushButton::icon {
                color: rgba(0, 0, 0, 200);  /* アイコンの色を黒に */
            }
        """)
    
    def _setup_tooltips(self):
        """ボタンのツールチップを設定"""
        self.first_image_button.setToolTip("全体の先頭画像へ移動 (Home)")
        self.first_folder_button.setToolTip("フォルダ内の先頭画像へ移動")
        self.prev_folder_button.setToolTip("前のフォルダへ移動")
        self.prev_image_button.setToolTip("前の画像へ移動 (Left/PageUp)")
        self.fullscreen_button.setToolTip("フルスクリーンモード切替 (F11)")
        self.next_image_button.setToolTip("次の画像へ移動 (Right/PageDown)")
        self.last_folder_button.setToolTip("フォルダ内の最後の画像へ移動")
        self.next_folder_button.setToolTip("次のフォルダへ移動")
        self.last_image_button.setToolTip("全体の最後の画像へ移動 (End)")
    
    def set_right_to_left_mode(self, enabled: bool):
        """
        右から左モードを設定（デュアルモードで右が第一画面の時用）
        
        Args:
            enabled: 右から左モードを有効にするかどうか
        """
        if self._right_to_left != enabled:
            self._right_to_left = enabled
            
            if enabled:
                # 右から左モード: ボタン機能を反転
                self.first_image_button.clicked.disconnect()
                self.first_folder_button.clicked.disconnect()
                self.prev_folder_button.clicked.disconnect()
                self.prev_image_button.clicked.disconnect()
                self.next_image_button.clicked.disconnect()
                self.last_folder_button.clicked.disconnect()
                self.next_folder_button.clicked.disconnect()
                self.last_image_button.clicked.disconnect()
                
                # 反転した接続
                self.first_image_button.clicked.connect(self.last_image_requested)
                self.first_folder_button.clicked.connect(self.last_folder_requested)
                self.prev_folder_button.clicked.connect(self.next_folder_requested)
                self.prev_image_button.clicked.connect(self.next_image_requested)
                self.next_image_button.clicked.connect(self.prev_image_requested)
                self.last_folder_button.clicked.connect(self.first_folder_requested)
                self.next_folder_button.clicked.connect(self.prev_folder_requested)
                self.last_image_button.clicked.connect(self.first_image_requested)
                
                # ツールチップも反転
                self.first_image_button.setToolTip("全体の最後の画像へ移動 (End)")
                self.first_folder_button.setToolTip("フォルダ内の最後の画像へ移動")
                self.prev_folder_button.setToolTip("次のフォルダへ移動")
                self.prev_image_button.setToolTip("次の画像へ移動 (Right/PageDown)")
                self.next_image_button.setToolTip("前の画像へ移動 (Left/PageUp)")
                self.last_folder_button.setToolTip("フォルダ内の先頭画像へ移動")
                self.next_folder_button.setToolTip("前のフォルダへ移動")
                self.last_image_button.setToolTip("全体の先頭画像へ移動 (Home)")
            else:
                # 左から右モード（通常）: 元の接続に戻す
                self.first_image_button.clicked.disconnect()
                self.first_folder_button.clicked.disconnect()
                self.prev_folder_button.clicked.disconnect()
                self.prev_image_button.clicked.disconnect()
                self.next_image_button.clicked.disconnect()
                self.last_folder_button.clicked.disconnect()
                self.next_folder_button.clicked.disconnect()
                self.last_image_button.clicked.disconnect()
                
                # 通常の接続
                self.first_image_button.clicked.connect(self.first_image_requested)
                self.first_folder_button.clicked.connect(self.first_folder_requested)
                self.prev_folder_button.clicked.connect(self.prev_folder_requested)
                self.prev_image_button.clicked.connect(self.prev_image_requested)
                self.next_image_button.clicked.connect(self.next_image_requested)
                self.last_folder_button.clicked.connect(self.last_folder_requested)
                self.next_folder_button.clicked.connect(self.next_folder_requested)
                self.last_image_button.clicked.connect(self.last_image_requested)
                
                # 通常のツールチップ
                self.first_image_button.setToolTip("全体の先頭画像へ移動 (Home)")
                self.first_folder_button.setToolTip("フォルダ内の先頭画像へ移動")
                self.prev_folder_button.setToolTip("前のフォルダへ移動")
                self.prev_image_button.setToolTip("前の画像へ移動 (Left/PageUp)")
                self.next_image_button.setToolTip("次の画像へ移動 (Right/PageDown)")
                self.last_folder_button.setToolTip("フォルダ内の最後の画像へ移動")
                self.next_folder_button.setToolTip("次のフォルダへ移動")
                self.last_image_button.setToolTip("全体の最後の画像へ移動 (End)")
    
    def _set_position(self):
        """親ウィンドウの下部中央に配置"""
        if self.parentWidget():
            parent_width = self.parentWidget().width()
            parent_height = self.parentWidget().height()
            
            # ナビゲーションバーの幅を親ウィンドウに合わせて調整
            width = min(900, parent_width - 40)  # 親の幅 - 左右マージン
            height = 70  # 固定高さを更新
            
            # 中央配置を確実にするため、計算を調整
            x = max(0, (parent_width - width) // 2)
            y = parent_height - height - 20  # 下部から20px上
            
            # ナビゲーションバーをリサイズして移動
            self.resize(width, height)  # まずサイズを設定
            self.move(x, y)  # 次に位置を設定
            
            log_print(DEBUG, f"ナビゲーションバーの位置を設定: ({x}, {y}), サイズ: {width}x{height}, 親幅: {parent_width}")
    
    def show_bar(self):
        """バーを表示"""
        if not self._visible or not self.isVisible():
            # 表示前に位置を更新
            self._set_position()  # 位置を再設定
            
            self._visible = True
            self.show()
            # UI更新を即時反映
            QApplication.processEvents()
            log_print(DEBUG, "ナビゲーションバーを表示")
        
        # 自動非表示タイマーをリセット
        self._hide_timer.stop()
    
    def _hide_bar(self):
        """バーを非表示"""
        if self._visible:
            # マウス位置を再確認して、まだ検出エリア内にある場合は非表示にしない
            if self.parentWidget():
                mouse_pos = self.parentWidget().mapFromGlobal(QCursor.pos())
                parent_height = self.parentWidget().height()
                detection_area_height = int(parent_height * self._detection_area_ratio)
                
                if (parent_height - detection_area_height) < mouse_pos.y() < parent_height:
                    # まだ検出エリア内にいるので、タイマーをリセットして表示を維持
                    self._hide_timer.start(1500)
                    return
            
            self._visible = False
            self.hide()
            # UI更新を即時反映
            QApplication.processEvents()
            log_print(DEBUG, "ナビゲーションバーを非表示")
    
    def set_bottom_margin(self, margin):
        """
        バーの下部マージンを設定
        
        Args:
            margin: ウィンドウ下端からのマージン（ピクセル）
        """
        if self.parentWidget():
            parent_width = self.parentWidget().width()
            parent_height = self.parentWidget().height()
            
            # 幅を親ウィンドウに合わせて調整
            width = min(900, parent_width - 40)
            height = self.height()
            
            # 中央配置を確実にするため、再計算
            x = max(0, (parent_width - width) // 2)
            y = parent_height - height - margin
            
            # サイズを調整してから移動
            self.resize(width, height)
            self.move(x, y)
            
            log_print(DEBUG, f"マージン調整: ({x}, {y}), サイズ: {width}x{height}, マージン: {margin}")
    
    def _check_mouse_position(self):
        """定期的にマウス位置をチェックし、必要に応じてナビゲーションバーを表示/非表示"""
        if not self.parentWidget():
            return
        
        # 親ウィジェット上でのマウス位置を取得
        mouse_pos = self.parentWidget().mapFromGlobal(QCursor.pos())
        parent_height = self.parentWidget().height()
        detection_area_height = int(parent_height * self._detection_area_ratio)
        
        # マウスが検出エリア内にある場合はバーを表示
        if (parent_height - detection_area_height) < mouse_pos.y() < parent_height:
            if not self._visible or not self.isVisible():
                self.show_bar()
        elif self._visible and not self._hide_timer.isActive():
            # 検出エリア外かつ非表示タイマーが動いていない場合は非表示タイマーを開始
            self._hide_timer.start(1500)  # 1.5秒後に非表示
    
    def eventFilter(self, watched, event):
        """
        親ウィジェットのイベントをフィルタリング
        
        Args:
            watched: 監視対象ウィジェット
            event: 発生したイベント
            
        Returns:
            イベントを処理した場合はTrue
        """
        # マウス移動イベントを処理
        if event.type() == QEvent.MouseMove and self.parentWidget():
            parent_height = self.parentWidget().height()
            detection_area_height = int(parent_height * self._detection_area_ratio)
            mouse_y = event.pos().y()
            
            # マウスが検出エリア内にある場合はバーを表示
            if (parent_height - detection_area_height) < mouse_y < parent_height:
                # 明示的にshow_barを呼び出し
                if not self._visible or not self.isVisible():
                    self.show_bar()
                    log_print(DEBUG, f"マウス検出: y={mouse_y}, 検出エリア: {parent_height-detection_area_height}-{parent_height}")
            elif self._visible and not self._hide_timer.isActive():
                # 検出エリア外かつ非表示タイマーが動いていない場合は非表示タイマーを開始
                self._hide_timer.start(1500)  # 1.5秒後に非表示
        
        # イベントはそのまま親ウィジェットに渡す
        return super().eventFilter(watched, event)
    
    def enterEvent(self, event):
        """マウスがウィジェットに入った時の処理"""
        # 自動非表示タイマーを停止
        self._hide_timer.stop()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """マウスがウィジェットから出た時の処理"""
        # 1.5秒後に非表示
        self._hide_timer.start(1500)
        super().leaveEvent(event)
