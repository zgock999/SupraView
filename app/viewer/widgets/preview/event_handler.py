"""
イベント処理モジュール

画像プレビューウィンドウでのキーボードやマウスのイベント処理を担当
"""

from typing import Dict, Callable, Any, Optional
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent, QContextMenuEvent
from logutils import log_print, DEBUG, INFO, WARNING


class EventHandler:
    """イベント処理を一元管理するハンドラクラス"""
    
    def __init__(self, parent):
        """
        イベントハンドラの初期化
        
        Args:
            parent: イベント処理を行う親ウィジェット
        """
        self.parent = parent
        
        # コールバック関数を登録するための辞書
        self.callbacks: Dict[str, Callable] = {}
        
        # キーマッピングの初期化（標準モード）
        self._init_key_mappings()
    
    def _init_key_mappings(self):
        """キーマッピングの初期化"""
        # 標準モードのキーマッピング
        self.key_mapping = {
            # ナビゲーション関連
            Qt.Key_Right: 'next_image',            # 次の画像へ
            Qt.Key_Left: 'prev_image',             # 前の画像へ
            Qt.Key_Up: 'first_folder_image',       # フォルダ先頭へ
            Qt.Key_Down: 'last_folder_image',      # フォルダ末尾へ
            Qt.Key_PageDown: 'next_folder',        # 次のフォルダへ
            Qt.Key_PageUp: 'prev_folder',          # 前のフォルダへ
            Qt.Key_Home: 'first_image',            # 全体先頭へ
            Qt.Key_End: 'last_image',              # 全体末尾へ
            
            # 表示モード関連
            Qt.Key_F11: 'toggle_fullscreen',       # フルスクリーン切替
            Qt.Key_F5: 'toggle_fullscreen',        # フルスクリーン切替（代替キー）
            Qt.Key_Escape: 'exit_fullscreen',      # フルスクリーン終了

            # 代替キー設定
            Qt.Key_N: 'next_image',                # 次の画像へ (代替キー)
            Qt.Key_P: 'prev_image',                # 前の画像へ (代替キー)
            Qt.Key_Space: 'next_image',            # 次の画像へ (代替キー)
            
            # ウィンドウ操作
            Qt.Key_Q: 'close',                     # ウィンドウを閉じる
        }
        
        # 右から左モード（RTL）のキーマッピング
        self.rtl_key_mapping = self.key_mapping.copy()
        # 左右キーの機能を入れ替え
        self.rtl_key_mapping[Qt.Key_Right] = 'prev_image'
        self.rtl_key_mapping[Qt.Key_Left] = 'next_image'
        # その他の代替キーも同様に
        self.rtl_key_mapping[Qt.Key_N] = 'prev_image'
        self.rtl_key_mapping[Qt.Key_P] = 'next_image'
        self.rtl_key_mapping[Qt.Key_Space] = 'prev_image'
    
    def register_callback(self, action: str, callback: Callable) -> bool:
        """
        アクションに対するコールバック関数を登録
        
        Args:
            action: アクション名
            callback: 実行するコールバック関数
            
        Returns:
            bool: 登録に成功したかどうか
        """
        if callable(callback):
            self.callbacks[action] = callback
            return True
        return False
    
    def handle_key_press(self, event: QKeyEvent) -> bool:
        """
        キー押下イベントの処理
        
        Args:
            event: キーイベント
            
        Returns:
            bool: イベントを処理した場合はTrue
        """
        key = event.key()
        
        # 右から左モードの場合は左右反転したキーマッピングを使用
        key_map = self.rtl_key_mapping if hasattr(self.parent, '_right_to_left') and self.parent._right_to_left else self.key_mapping
        
        # キーに対応するアクションを検索
        action = key_map.get(key)
        
        # デバッグログ出力を修正 - アクションにマッピングされなくてもログ出力する
        if action:
            log_print(DEBUG, f"キー {key} は '{action}' アクションにマッピングされています")
            
            # 特別なケース: Escキーのフルスクリーン終了
            if action == 'exit_fullscreen':
                # フルスクリーンモードの場合のみ処理
                if hasattr(self.parent, 'isFullScreen') and self.parent.isFullScreen():
                    if 'toggle_fullscreen' in self.callbacks:
                        log_print(INFO, f"フルスクリーン終了アクション実行: {action}")
                        return self.callbacks['toggle_fullscreen']()
                    else:
                        log_print(WARNING, f"アクション '{action}' に対応するコールバックが見つかりません")
                # フルスクリーンでなければ無視
                log_print(DEBUG, "フルスクリーンモードではないため、exit_fullscreenアクションは無視されます")
                return False
            
            # 通常の処理: 登録されているコールバックを実行
            if action in self.callbacks:
                log_print(INFO, f"キーボードアクション実行: {action}")
                return self.callbacks[action]()
            else:
                log_print(WARNING, f"アクション '{action}' に対応するコールバックが登録されていません。登録済みコールバック: {list(self.callbacks.keys())}")
        else:
            log_print(DEBUG, f"キー {key} にマッピングされたアクションが見つかりません。マッピング: {self.key_mapping}")
        
        # イベントが処理されなかった
        return False
    
    def handle_mouse_move(self, event: QMouseEvent, window_height: int) -> bool:
        """
        マウス移動イベントの処理
        
        Args:
            event: マウスイベント
            window_height: ウィンドウの高さ
            
        Returns:
            bool: イベントを処理した場合はTrue
        """
        # ウィンドウの下部20%にマウスがあればナビゲーションバーを表示
        if event.pos().y() > window_height * 0.8:
            if 'show_navigation' in self.callbacks:
                return self.callbacks['show_navigation']()
        else:
            # それ以外の領域ではナビゲーションバーを非表示
            if 'hide_navigation' in self.callbacks:
                return self.callbacks['hide_navigation']()
        
        # イベント処理なし
        return False
    
    def handle_wheel(self, event: QWheelEvent) -> bool:
        """
        マウスホイールイベントの処理
        
        Args:
            event: ホイールイベント
            
        Returns:
            bool: イベントを処理した場合はTrue
        """
        # 親ウィンドウのイメージモデルが存在し、ウィンドウ合わせモードの時だけ画像移動を行う
        # 原寸大表示モード(fit_to_window=False)のときはスクロール操作を優先
        if hasattr(self.parent, 'image_model') and self.parent.image_model:
            # fit_to_windowモードでない場合は画像スクロールを優先
            if not self.parent.image_model.is_fit_to_window():
                log_print(DEBUG, "原寸大表示モードでホイール操作: スクロール操作を優先")
                return False
                
        # ホイールの回転方向を取得
        delta = event.angleDelta().y()
        
        # 視覚的一貫性を保持: 上スクロールは常に前の画像、下スクロールは常に次の画像
        # RTLモードでも反転させない（視覚的な一貫性を優先）
        if delta > 0:  # 上方向スクロール
            action = 'prev_image'
            if action in self.callbacks:
                log_print(DEBUG, f"ホイール上スクロールで画像移動: {action}")
                return self.callbacks[action]()
        elif delta < 0:  # 下方向スクロール
            action = 'next_image'
            if action in self.callbacks:
                log_print(DEBUG, f"ホイール下スクロールで画像移動: {action}")
                return self.callbacks[action]()
                
        # イベント処理なし
        return False
    
    def handle_resize(self, width: int) -> bool:
        """
        リサイズイベントの処理
        
        Args:
            width: 新しい幅
            
        Returns:
            bool: イベントを処理した場合はTrue
        """
        if 'adjust_navigation_size' in self.callbacks:
            return self.callbacks['adjust_navigation_size'](width)
            
        # イベント処理なし
        return False
    
    def handle_context_menu(self, event: QContextMenuEvent) -> bool:
        """
        コンテキストメニューイベントの処理
        
        Args:
            event: コンテキストメニューイベント
            
        Returns:
            bool: イベントを処理した場合はTrue
        """
        if 'show_context_menu' in self.callbacks:
            return self.callbacks['show_context_menu'](event.globalPos())
            
        # イベント処理なし
        return False
    
    def process_event(self, obj, event):
        """
        イベントフィルタ用の汎用イベント処理メソッド
        
        Args:
            obj: イベントを受信したオブジェクト
            event: 発生したイベント
            
        Returns:
            bool: イベントを処理した場合はTrue
        """
        event_type = event.type()
        
        if event_type == QEvent.FocusIn:
            log_print(DEBUG, f"フォーカスイン: {obj}")
            return False  # イベントを伝搬
        
        elif event_type == QEvent.FocusOut:
            log_print(DEBUG, f"フォーカスアウト: {obj}")
            return False  # イベントを伝搬
        
        elif event_type == QEvent.KeyPress:
            log_print(DEBUG, f"キープレスイベント: {event.key()}, ウィジェット: {obj}")
            # ここではキー処理はせず、親ウィジェットのkeyPressEventが呼ばれるようにする
            return False  # イベントを伝搬
        
        # デフォルトでは処理しない
        return False
    
    def handle_show_event(self, event):
        """
        ウィンドウ表示イベントの処理
        
        Args:
            event: 表示イベント
        """
        # 確実にフォーカスを取得
        if hasattr(self.parent, 'setFocus') and callable(self.parent.setFocus):
            self.parent.setFocus()
        
        if hasattr(self.parent, 'activateWindow') and callable(self.parent.activateWindow):
            self.parent.activateWindow()
        
        # デバッグ出力
        log_print(INFO, "プレビューウィンドウが表示され、フォーカスを取得しました")
