"""
インフォメーションバーウィジェット

画像プレビューウィンドウの上部に表示される情報バー
"""

import os
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QApplication
from PySide6.QtCore import Qt, Signal, QTimer, QSize, QEvent, QThread
from PySide6.QtGui import QFont, QCursor

from logutils import log_print, INFO, DEBUG


class InformationBar(QWidget):
    """
    画像プレビュー用インフォメーションバー
    
    マウスカーソルがウィンドウ上部に移動した時に表示され、
    マウスが離れると自動的に非表示になる。
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 表示状態
        self._visible = False
        
        # 検出エリアの割合（上部からの割合）- 感度を上げるために25%に設定
        self._detection_area_ratio = 0.25
        
        # ウィジェットの透明度を設定
        self.setWindowOpacity(0.9)
        
        # 自動非表示用タイマー
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide_bar)
        
        # レイアウト設定
        self._setup_ui()
        
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
        
        # UI構築が終わってから、メインスレッドでタイマーを開始
        QTimer.singleShot(0, self._check_mouse_timer.start)
    
    def _setup_ui(self):
        """UIコンポーネントをセットアップ"""
        # 水平レイアウトを作成
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # 情報表示用ラベル
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignCenter)
        # ラベルのフォント設定 - 14ptに設定（4ポイント大きく）
        font = QFont()
        font.setPointSize(14)
        self.info_label.setFont(font)
        # テキストの色を黄色に設定
        self.info_label.setStyleSheet("color: yellow;")
        
        # レイアウトにラベルを追加
        layout.addWidget(self.info_label, 1)  # stretch=1で水平方向に拡張
        
        # インフォメーションバーの高さを調整（フォントサイズ変更に対応）
        self.setFixedHeight(50)  # 固定高さを大きめに設定
        
        # スタイルシートをより単純に直接設定 (問題が発生している可能性がある部分)
        self.setStyleSheet("""
            background-color: rgba(0, 0, 0, 200);  /* より暗い半透明背景 */
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 0, 100);  /* 黄色系の枠線 */
        """)
        
        # オブジェクト名を設定
        self.setObjectName("InformationBar")
    
    def set_info_text(self, text):
        """
        情報テキストを設定し、バーを表示する
        
        新しい情報が設定された時、マウスの位置に関わらずバーを表示し、
        一定時間後に自動的に非表示になる
        """
        # 現在のテキストと異なる場合または非表示状態の場合は処理
        if self.info_label.text() != text or not self._visible or not self.isVisible():
            # 新しいテキストを設定
            self.info_label.setText(text)
            
            # バーを表示
            self.show_bar()
            
            # タイマーをセット（3秒後に非表示） - スレッドセーフに
            if QThread.currentThread() == self.thread():
                self._hide_timer.start(3000)
            else:
                QTimer.singleShot(0, lambda: self._hide_timer.start(3000))
            
            log_print(DEBUG, f"インフォメーションバーに新しいテキストを設定: {text}")
    
    def _set_position(self):
        """親ウィンドウの上部中央に配置"""
        if self.parentWidget():
            parent_width = self.parentWidget().width()
            
            # インフォメーションバーの幅を親ウィンドウに合わせて調整
            width = min(900, parent_width - 40)  # 親の幅 - 左右マージン
            height = 50  # 固定高さを_setup_uiと同じに設定（50px）
            
            # 中央配置を確実にするため、計算を調整
            x = max(0, (parent_width - width) // 2)
            y = 20  # 上部から20px下
            
            # インフォメーションバーをリサイズして移動
            self.resize(width, height)  # まずサイズを設定
            self.move(x, y)  # 次に位置を設定
            
            log_print(DEBUG, f"インフォメーションバーの位置を設定: ({x}, {y}), サイズ: {width}x{height}, 親幅: {parent_width}")
    
    def show_bar(self):
        """バーを表示"""
        # 表示前に位置を確実に更新
        self._set_position()
        
        # 既に表示中かつ可視状態であれば何もしない
        if self._visible and self.isVisible():
            return
        
        # 表示状態を更新
        self._visible = True
        
        # 明示的に表示し、前面に持ってくる
        self.show()
        self.raise_()
        
        # UI更新を即時反映（再帰的なrepaintを避ける）
        QApplication.processEvents()
        
        log_print(DEBUG, "インフォメーションバーを表示")
        
        # 自動非表示タイマーをリセット - スレッドセーフに
        if QThread.currentThread() == self.thread():
            self._hide_timer.stop()
        else:
            QTimer.singleShot(0, self._hide_timer.stop)
    
    def _hide_bar(self):
        """バーを非表示"""
        if self._visible:
            # マウス位置を再確認して、まだ検出エリア内にある場合は非表示にしない
            if self.parentWidget():
                mouse_pos = self.parentWidget().mapFromGlobal(QCursor.pos())
                parent_height = self.parentWidget().height()
                detection_area_height = int(parent_height * self._detection_area_ratio)
                
                if 0 <= mouse_pos.y() < detection_area_height:
                    # まだ検出エリア内にいるので、タイマーをリセットして表示を維持 - スレッドセーフに
                    if QThread.currentThread() == self.thread():
                        self._hide_timer.start(1500)
                    else:
                        QTimer.singleShot(0, lambda: self._hide_timer.start(1500))
                    return
            
            self._visible = False
            self.hide()
            # UI更新を即時反映
            QApplication.processEvents()
            log_print(DEBUG, "インフォメーションバーを非表示")
    
    def _check_mouse_position(self):
        """定期的にマウス位置をチェックし、必要に応じてインフォメーションバーを表示/非表示"""
        if not self.parentWidget():
            return
        
        # 親ウィジェット上でのマウス位置を取得
        mouse_pos = self.parentWidget().mapFromGlobal(QCursor.pos())
        parent_height = self.parentWidget().height()
        detection_area_height = int(parent_height * self._detection_area_ratio)
        
        # マウスが検出エリア内にある場合はバーを表示
        if 0 <= mouse_pos.y() < detection_area_height:
            if not self._visible or not self.isVisible():
                self.show_bar()
        elif self._visible and not self._hide_timer.isActive():
            # 検出エリア外かつ非表示タイマーが動いていない場合は非表示タイマーを開始 - スレッドセーフに
            if QThread.currentThread() == self.thread():
                self._hide_timer.start(1500)  # 1.5秒後に非表示
            else:
                QTimer.singleShot(0, lambda: self._hide_timer.start(1500))
    
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
            if 0 <= mouse_y < detection_area_height:
                # 明示的にshow_barを呼び出し
                if not self._visible or not self.isVisible():
                    self.show_bar()
                    log_print(DEBUG, f"マウス検出: y={mouse_y}, 検出エリア: 0-{detection_area_height}")
            elif self._visible and not self._hide_timer.isActive():
                # 検出エリア外かつ非表示タイマーが動いていない場合は非表示タイマーを開始 - スレッドセーフに
                if QThread.currentThread() == self.thread():
                    self._hide_timer.start(1500)  # 1.5秒後に非表示
                else:
                    QTimer.singleShot(0, lambda: self._hide_timer.start(1500))
        
        # イベントはそのまま親ウィジェットに渡す
        return super().eventFilter(watched, event)
    
    def enterEvent(self, event):
        """マウスがウィジェットに入った時の処理"""
        # 自動非表示タイマーを停止 - スレッドセーフに
        if QThread.currentThread() == self.thread():
            self._hide_timer.stop()
        else:
            QTimer.singleShot(0, self._hide_timer.stop)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """マウスがウィジェットから出た時の処理"""
        # 1.5秒後に非表示 - スレッドセーフに
        if QThread.currentThread() == self.thread():
            self._hide_timer.start(1500)
        else:
            QTimer.singleShot(0, lambda: self._hide_timer.start(1500))
        super().leaveEvent(event)
    
    def stop_timers(self):
        """全てのタイマーを停止"""
        # 自動非表示タイマーを停止
        if self._hide_timer and self._hide_timer.isActive():
            if QThread.currentThread() == self.thread():
                self._hide_timer.disconnect()
                self._hide_timer.stop()
            else:
                QTimer.singleShot(0, lambda: self._hide_timer.disconnect())
                QTimer.singleShot(0, self._hide_timer.stop)
        
        # マウス位置チェックタイマーを停止
        if self._check_mouse_timer and self._check_mouse_timer.isActive():
            if QThread.currentThread() == self.thread():
                self._check_mouse_timer.disconnect()
                self._check_mouse_timer.stop()
            else:
                QTimer.singleShot(0, lambda: self._check_mouse_timer.disconnect())
                QTimer.singleShot(0, self._check_mouse_timer.stop)
        
        log_print(DEBUG, "インフォメーションバーの全タイマーが停止されました")
        
    def closeEvent(self, event):
        """ウィジェット終了時の処理"""
        # タイマーをすべて停止
        self.stop_timers()
        super().closeEvent(event)
        
    def __del__(self):
        """オブジェクト破棄時の処理"""
        try:
            self.stop_timers()
            log_print(DEBUG, "インフォメーションバーのデストラクタが呼ばれました")
        except:
            pass
