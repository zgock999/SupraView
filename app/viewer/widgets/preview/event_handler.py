"""
イベント処理モジュール

画像プレビューウィンドウでのキーボードやマウスのイベント処理を担当
"""

from typing import Dict, Callable, Any, Optional
import time  # 時間計測用に追加
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent, QContextMenuEvent
from logutils import log_print, DEBUG, INFO, WARNING, ERROR


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
        
        # 前回のアクション記録用（間引き処理は削除するが、デバッグ用に残す）
        self._last_key_action = None
        
        # 移動系アクション（ナビゲーションロック対象）
        self._navigation_actions = [
            'next_image', 'prev_image',
            'first_folder_image', 'last_folder_image',
            'next_folder', 'prev_folder', 
            'first_image', 'last_image'
        ]
        
        # キーイベントロック状態
        self._key_event_locked = False
        
        # ナビゲーション処理中フラグ
        self._navigation_in_progress = False  # ナビゲーション処理中フラグ
        
        # ナビゲーションバーのシグナル接続状態を管理
        self._navigation_signals_connected = True
        
        # ナビゲーションバーのシグナル情報を保持
        self._navigation_signals = []
    
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
            Qt.Key_Space: 'apply_superres',        # 超解像処理を適用 (スペースキー)
            
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
        # スペースキーは超解像処理のままで変更しない
        self.rtl_key_mapping[Qt.Key_Space] = 'apply_superres'
    
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
    
    def register_navigation_bar_signals(self, navigation_bar):
        """
        ナビゲーションバーのシグナル情報を登録
        
        Args:
            navigation_bar: ナビゲーションバーのインスタンス
        """
        # シグナル情報を保存
        self._navigation_signals = [
            (navigation_bar.first_image_requested, navigation_bar._on_first_image_clicked),
            (navigation_bar.prev_image_requested, navigation_bar._on_prev_image_clicked),
            (navigation_bar.next_image_requested, navigation_bar._on_next_image_clicked),
            (navigation_bar.last_image_requested, navigation_bar._on_last_image_clicked),
            (navigation_bar.prev_folder_requested, navigation_bar._on_prev_folder_clicked),
            (navigation_bar.next_folder_requested, navigation_bar._on_next_folder_clicked),
            (navigation_bar.first_folder_requested, navigation_bar._on_first_folder_clicked),
            (navigation_bar.last_folder_requested, navigation_bar._on_last_folder_clicked)
        ]
        
        log_print(DEBUG, "ナビゲーションバーのシグナル情報を登録しました")
    
    def disconnect_navigation_signals(self):
        """ナビゲーションバーのシグナルを一時的に解除"""
        if not self._navigation_signals_connected:
            return
            
        # ナビゲーションバーとの接続を解除
        if hasattr(self.parent, 'navigation_bar'):
            nav_bar = self.parent.navigation_bar
            
            # ボタンとシグナルの接続を解除
            try:
                nav_bar.first_image_button.clicked.disconnect()
                nav_bar.first_folder_button.clicked.disconnect()
                nav_bar.prev_folder_button.clicked.disconnect()
                nav_bar.prev_image_button.clicked.disconnect()
                nav_bar.next_image_button.clicked.disconnect()
                nav_bar.last_folder_button.clicked.disconnect()
                nav_bar.next_folder_button.clicked.disconnect()
                nav_bar.last_image_button.clicked.disconnect()
                
                self._navigation_signals_connected = False
                log_print(INFO, "ナビゲーションバーのシグナルを解除しました")
            except Exception as e:
                log_print(ERROR, f"ナビゲーションシグナルの解除中にエラーが発生: {e}")
    
    def reconnect_navigation_signals(self):
        """ナビゲーションバーのシグナルを再接続"""
        if self._navigation_signals_connected:
            return
            
        # ナビゲーションバーとの接続を再確立
        if hasattr(self.parent, 'navigation_bar'):
            nav_bar = self.parent.navigation_bar
            
            # ボタンとシグナルを再接続
            try:
                if hasattr(nav_bar, 'set_right_to_left_mode'):
                    # RTLモードに応じた接続を再確立
                    rtl_mode = nav_bar._right_to_left
                    nav_bar.set_right_to_left_mode(rtl_mode)
                    self._navigation_signals_connected = True
                    log_print(INFO, f"ナビゲーションバーのシグナルを再接続しました (RTL: {rtl_mode})")
                else:
                    log_print(WARNING, "ナビゲーションバーにset_right_to_left_modeメソッドが見つかりません")
            except Exception as e:
                log_print(ERROR, f"ナビゲーションシグナルの再接続中にエラーが発生: {e}")
    
    def lock_navigation_events(self):
        """
        移動系キーイベントをロック（画像更新中にキー入力を防止）
        """
        self._key_event_locked = True
        self.disconnect_navigation_signals()  # シグナルも解除
        
        # ApplicationレベルでQtのイベントキューをクリア
        self.clear_pending_events()
        
        log_print(INFO, "キーイベントとナビゲーションシグナルをロックしました（画像更新中）")
    
    def unlock_navigation_events(self):
        """
        移動系キーイベントのロックを解除（画像更新完了後に呼び出される）
        """
        # 両方のロックを解除
        self._key_event_locked = False
        self._navigation_in_progress = False
        self.clear_pending_events()
        self.reconnect_navigation_signals()  # シグナルを再接続
        log_print(INFO, "キーイベントとナビゲーションシグナルのロックを解除しました（画像更新完了）")
    
    def is_navigation_locked(self):
        """
        キーイベントがロックされているか確認
        
        Returns:
            bool: ロックされている場合はTrue
        """
        # 親ウィンドウの画像更新状態も確認
        is_updating = False
        if hasattr(self.parent, '_is_updating_images'):
            is_updating = self.parent._is_updating_images
        
        # 明示的なロックか、画像更新中の場合はロック状態と判断
        return self._key_event_locked or is_updating
    
    def handle_key_press(self, event: QKeyEvent) -> bool:
        """
        キー押下イベントの処理
        
        Args:
            event: キーイベント
            
        Returns:
            bool: イベントを処理した場合はTrue
        """
        key = event.key()
        
        # デバッグログ - 最初にキー入力をログ出力
        log_print(DEBUG, f"キー入力を検出: キーコード {key}")
        
        # ナビゲーション処理中やロック中の場合は即座に廃棄
        if self._navigation_in_progress or self.is_navigation_locked():
            log_print(DEBUG, f"ナビゲーション処理中またはロック中のため、キー入力 {key} を廃棄")
            return True  # イベントを消費
        
        # 右から左モードの場合は左右反転したキーマッピングを使用
        key_map = self.rtl_key_mapping if hasattr(self.parent, '_right_to_left') and self.parent._right_to_left else self.key_mapping
        
        # キーに対応するアクションを検索
        action = key_map.get(key)
        
        # ナビゲーションキーかどうかを確認
        if action in self._navigation_actions:
            # 既にナビゲーション処理中か更新中なら処理しない
            if self._navigation_in_progress or self.is_navigation_locked():
                log_print(INFO, f"ナビゲーション処理中または画像更新中のため、キー入力をスキップします: キーコード {key}, アクション {action}")
                event.accept()  # イベントを消費
                return True
                
            # *** 新しい方法: 多重実行防止のために即座にシグナル接続を解除 ***
            log_print(DEBUG, f"ナビゲーションキー検出: シグナルを即座に解除 ({key}, {action})")
            self._navigation_in_progress = True
            
            # シグナルが接続されている場合のみ解除（二重解除を防止）
            if self._navigation_signals_connected:
                self.disconnect_navigation_signals()  # シグナルを解除
            
            # Page Up/Down キーを特別に処理
            if key == Qt.Key_PageUp or key == Qt.Key_PageDown:
                page_action = "prev_folder" if key == Qt.Key_PageUp else "next_folder"
                log_print(INFO, f"Page {'Up' if key == Qt.Key_PageUp else 'Down'} キーを検出")
                
                # 最後に処理したアクションを記録（デバッグ用）
                self._last_key_action = page_action
                
                # ナビゲーションイベントをロック（永続的なロックを設定）
                self.lock_navigation_events()
                
                # コールバック実行
                if page_action in self.callbacks:
                    log_print(INFO, f"フォルダナビゲーション実行: {page_action}")
                    
                    # イベントを消費
                    event.accept()
                    
                    try:
                        # コールバックを実行
                        result = self.callbacks[page_action]()
                        return result
                    except Exception as e:
                        log_print(ERROR, f"コールバック実行中にエラー発生: {e}")
                        # エラーが発生した場合でも必ずロック解除
                        self.unlock_navigation_events()
                        return False
            
            # 通常のナビゲーションアクション
            log_print(INFO, f"キーボードナビゲーションアクション実行: {action}")
            
            # キーイベントをロック
            self.lock_navigation_events()
            
            # イベントを消費して実行 
            event.accept()
            
            try:
                if action in self.callbacks:
                    return self.callbacks[action]()
                else:
                    log_print(WARNING, f"アクション '{action}' に対応するコールバックが登録されていません")
                    return False
            except Exception as e:
                log_print(ERROR, f"コールバック実行中にエラー発生: {e}")
                # エラーが発生した場合でも必ずロック解除
                self.unlock_navigation_events()
                return False
        
        # 非ナビゲーションキーの処理
        if action:
            log_print(DEBUG, f"キー {key} は '{action}' アクションにマッピングされています")
            
            # 最後に処理したアクションを記録（デバッグ用）
            self._last_key_action = action
            
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
            
            # 特別なケース: 超解像処理（スペースキー）
            if action == 'apply_superres':
                # 自動処理モードがオンになっている場合はスキップ
                auto_process = False
                
                # 親ウィンドウが存在し、超解像処理マネージャが設定されているか確認
                if hasattr(self.parent, 'sr_manager') and self.parent.sr_manager is not None:
                    # 直接sr_managerプロパティがある場合
                    if hasattr(self.parent.sr_manager, 'auto_process'):
                        auto_process = self.parent.sr_manager.auto_process
                # image_handler経由でsr_managerが設定されている場合
                elif hasattr(self.parent, 'image_handler') and hasattr(self.parent.image_handler, 'sr_manager'):
                    if hasattr(self.parent.image_handler.sr_manager, 'auto_process'):
                        auto_process = self.parent.image_handler.sr_manager.auto_process
                
                if auto_process:
                    log_print(INFO, "自動超解像処理モードが有効なため、手動での超解像実行はスキップされます")
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
        # ウィンドウの上部20%にマウスがあればインフォメーションバーを表示
        if event.pos().y() < window_height * 0.2:
            if 'show_information' in self.callbacks:
                self.callbacks['show_information']()
        else:
            # それ以外の領域ではインフォメーションバーを非表示
            if 'hide_information' in self.callbacks:
                self.callbacks['hide_information']()
        
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
            # width引数を確実に渡すように修正
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
    
    def install_global_event_filter(self, app):
        """
        アプリケーション全体のイベントフィルタを設定
        
        Args:
            app: QApplicationインスタンス
        """
        # QApplicationレベルのイベントフィルタを設定
        app.installEventFilter(self)
        log_print(INFO, "グローバルイベントフィルタを設定しました")
    
    def eventFilter(self, obj, event):
        """
        QObjectのイベントをフィルタリング
        
        Args:
            obj: イベントを受信したオブジェクト
            event: イベント
            
        Returns:
            イベントを処理した場合はTrue
        """
        # キープレスイベントを処理
        if event.type() == QEvent.KeyPress:
            key = event.key()
            
            # Page Up/Downキーを特別に処理 - ナビゲーション処理中/ロック中は全て廃棄
            if key == Qt.Key_PageUp or key == Qt.Key_PageDown:
                if self._navigation_in_progress or self.is_navigation_locked():
                    log_print(INFO, f"Page{'Up' if key == Qt.Key_PageUp else 'Down'}キーをイベントフィルタで廃棄: ナビゲーションロック中")
                    return True  # イベントを消費(廃棄)
            
            # その他のナビゲーションキーもチェック
            action = None
            if hasattr(self.parent, '_right_to_left') and self.parent._right_to_left:
                action = self.rtl_key_mapping.get(key)
            else:
                action = self.key_mapping.get(key)
            
            if action in self._navigation_actions:
                if self._navigation_in_progress or self.is_navigation_locked():
                    log_print(INFO, f"ナビゲーションキー ({key}:{action}) をイベントフィルタで廃棄: ロック中")
                    return True  # イベントを消費(廃棄)
        
        # デフォルト処理 (イベントを通過させる)
        return False
    
    def clear_pending_events(self):
        """Qtのイベントキューから保留中のキーイベントをクリア"""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QEvent
        
        # 仮のイベント処理でキューをフラッシュ
        QApplication.processEvents()
        
        log_print(DEBUG, "ペンディング中のイベントをクリアしました")
    
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
