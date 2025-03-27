"""
プレビューウィンドウ用コンテキストメニュー

ImagePreviewWindowで使用するコンテキストメニューを提供します。
"""

from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QAction, QActionGroup  # QActionGroupをQtGuiからインポート
from logutils import log_print, DEBUG, INFO, WARNING, ERROR


class PreviewContextMenu(QMenu):
    """プレビューウィンドウ用のコンテキストメニュー"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        # クリック位置を保存する変数を追加
        self._click_position = None
        self._last_global_position = None  # 最後に使用されたグローバル位置を保存
        
        self._create_actions()
        self._build_menu()
        
        # コンテキストメニュー表示前のシグナルに接続
        self.aboutToShow.connect(self._on_about_to_show)
    
    def _create_actions(self):
        """メニューアクションの作成"""
        # 表示関連
        self.fit_to_window_action = QAction("ウィンドウに合わせる", self)
        self.fit_to_window_action.setCheckable(True)  # チェック可能に設定
        self.fit_to_window_action.triggered.connect(self._on_fit_to_window)
        
        self.original_size_action = QAction("原寸大表示", self)
        self.original_size_action.setCheckable(True)  # チェック可能に設定
        self.original_size_action.triggered.connect(self._on_original_size)
        
        # 表示モードをグループ化してラジオボタン動作に
        self.display_mode_group = QActionGroup(self)
        self.display_mode_group.addAction(self.fit_to_window_action)
        self.display_mode_group.addAction(self.original_size_action)
        self.display_mode_group.setExclusive(True)
        
        # デフォルトは原寸大表示にチェック
        self.original_size_action.setChecked(True)
        
        # 画像操作関連
        self.rotate_left_action = QAction("左に回転", self)
        self.rotate_left_action.triggered.connect(self._on_rotate_left)
        
        self.rotate_right_action = QAction("右に回転", self)
        self.rotate_right_action.triggered.connect(self._on_rotate_right)
        
        # 超解像処理アクションの追加
        self.superres_action = QAction("超解像処理を実行", self)
        self.superres_action.triggered.connect(self._on_superres)
        
        # 表示モード関連 - 新規追加
        self.mode_single_action = QAction("シングル", self)
        self.mode_single_action.setCheckable(True)
        self.mode_single_action.triggered.connect(lambda: self._on_set_view_mode("single"))
        
        self.mode_dual_rl_action = QAction("デュアル（右左）", self)
        self.mode_dual_rl_action.setCheckable(True)
        self.mode_dual_rl_action.triggered.connect(lambda: self._on_set_view_mode("dual_rl"))
        
        self.mode_dual_lr_action = QAction("デュアル（左右）", self)
        self.mode_dual_lr_action.setCheckable(True)
        self.mode_dual_lr_action.triggered.connect(lambda: self._on_set_view_mode("dual_lr"))
        
        self.mode_dual_rl_shift_action = QAction("デュアル（右左シフト）", self)
        self.mode_dual_rl_shift_action.setCheckable(True)
        self.mode_dual_rl_shift_action.triggered.connect(lambda: self._on_set_view_mode("dual_rl_shift"))
        
        self.mode_dual_lr_shift_action = QAction("デュアル（左右シフト）", self)
        self.mode_dual_lr_shift_action.setCheckable(True)
        self.mode_dual_lr_shift_action.triggered.connect(lambda: self._on_set_view_mode("dual_lr_shift"))
        
        # 表示モードをグループ化してラジオボタン動作に
        self.view_mode_group = QActionGroup(self)
        self.view_mode_group.addAction(self.mode_single_action)
        self.view_mode_group.addAction(self.mode_dual_rl_action)
        self.view_mode_group.addAction(self.mode_dual_lr_action)
        self.view_mode_group.addAction(self.mode_dual_rl_shift_action)
        self.view_mode_group.addAction(self.mode_dual_lr_shift_action)
        self.view_mode_group.setExclusive(True)
        
        # デフォルトはシングルモード
        self.mode_single_action.setChecked(True)
        
        # ファイル操作関連
        self.save_as_action = QAction("名前を付けて保存...", self)
        self.save_as_action.triggered.connect(self._on_save_as)
        
        self.copy_action = QAction("クリップボードにコピー", self)
        self.copy_action.triggered.connect(self._on_copy_to_clipboard)
        
        # ウィンドウ操作
        self.close_action = QAction("閉じる", self)
        self.close_action.triggered.connect(self._on_close)
    
    def _build_menu(self):
        """メニュー構造の構築"""
        # 表示メニュー
        view_menu = self.addMenu("表示")
        view_menu.addAction(self.fit_to_window_action)
        view_menu.addAction(self.original_size_action)
        
        # 表示モードメニュー - 新規追加
        mode_menu = self.addMenu("表示モード")
        mode_menu.addAction(self.mode_single_action)
        mode_menu.addSeparator()
        mode_menu.addAction(self.mode_dual_rl_action)
        mode_menu.addAction(self.mode_dual_lr_action)
        mode_menu.addSeparator()
        mode_menu.addAction(self.mode_dual_rl_shift_action)
        mode_menu.addAction(self.mode_dual_lr_shift_action)
        
        # 画像操作メニュー
        image_menu = self.addMenu("画像")
        image_menu.addAction(self.rotate_left_action)
        image_menu.addAction(self.rotate_right_action)
        image_menu.addSeparator()
        image_menu.addAction(self.superres_action)  # 超解像処理メニュー項目を追加
        
        # ファイル操作
        self.addSeparator()
        self.addAction(self.save_as_action)
        self.addAction(self.copy_action)
        
        # ウィンドウ操作
        self.addSeparator()
        self.addAction(self.close_action)
    
    def popup(self, pos):
        """
        指定された位置にコンテキストメニューを表示（QMenuのpopupをオーバーライド）
        
        Args:
            pos: 表示位置（グローバル座標）
        """
        # クリック位置を保存（pos がQPointオブジェクトであることを確認）
        if isinstance(pos, QPoint):
            self._click_position = QPoint(pos)  # 明示的にコピーを作成
            self._last_global_position = QPoint(pos)  # グローバル位置も保存
            log_print(DEBUG, f"コンテキストメニューpopup: クリック位置を保存: x={pos.x()}, y={pos.y()}")
        else:
            # ポイントオブジェクトでない場合の処理
            log_print(WARNING, f"不正な位置データ型: {type(pos)}")
            # XとYの値を取得してQPointを作成
            try:
                x = pos[0] if isinstance(pos, (list, tuple)) else pos.x if hasattr(pos, 'x') else 0
                y = pos[1] if isinstance(pos, (list, tuple)) else pos.y if hasattr(pos, 'y') else 0
                self._click_position = QPoint(x, y)
                self._last_global_position = QPoint(x, y)
                log_print(DEBUG, f"位置データを変換: x={x}, y={y}")
            except Exception as e:
                log_print(ERROR, f"位置データの変換に失敗: {e}")
                self._click_position = QPoint(0, 0)
                self._last_global_position = QPoint(0, 0)
        
        # 超解像処理メニューの有効/無効を設定
        self._update_superres_action_state()
        
        # 親クラスのpopupメソッドを呼び出し
        super().popup(self._last_global_position)
    
    def _on_about_to_show(self):
        """メニュー表示直前の処理"""
        # カーソル位置を取得
        from PySide6.QtGui import QCursor
        cursor_pos = QCursor.pos()
        
        # クリック位置が未設定の場合はカーソル位置を使用
        if self._click_position is None:
            self._click_position = cursor_pos
            self._last_global_position = cursor_pos
            log_print(DEBUG, f"aboutToShow: カーソル位置を使用: x={cursor_pos.x()}, y={cursor_pos.y()}")
        
        # 超解像処理メニューの有効/無効を更新
        self._update_superres_action_state()
    
    def _update_superres_action_state(self):
        """超解像処理メニューの有効/無効状態を更新"""
        # 親ウィンドウが存在し、超解像処理マネージャが設定されているか確認
        has_sr_manager = hasattr(self.parent, 'sr_manager') and self.parent.sr_manager is not None
        
        # 超解像マネージャが初期化中かどうか確認
        initializing = has_sr_manager and hasattr(self.parent.sr_manager, 'is_initializing') and self.parent.sr_manager.is_initializing
        
        # クリック位置に画像があるかどうか確認
        target_index = self._get_target_image_index()
        has_image = target_index is not None and hasattr(self.parent, 'image_handler') and self.parent.image_handler.is_image_loaded(target_index)
        
        # 条件に基づいてアクションの有効/無効を設定
        enabled = has_sr_manager and not initializing and has_image
        self.superres_action.setEnabled(enabled)
        
        # ログ出力
        log_print(DEBUG, f"超解像メニュー状態更新: 有効={enabled}, マネージャ={has_sr_manager}, 初期化中={initializing if has_sr_manager else False}, 画像={has_image}, ターゲット={target_index}")
    
    def _get_target_image_index(self):
        """クリック位置に基づいて処理対象の画像インデックスを取得"""
        log_print(INFO, f"ターゲットインデックス取得開始 - クリック位置: {self._click_position.x() if self._click_position else 'None'}, "
                     f"最後のグローバル位置: {self._last_global_position.x() if self._last_global_position else 'None'}")
        
        if not self._click_position and not self._last_global_position:
            # クリック位置がない場合、カーソル位置を使用
            from PySide6.QtGui import QCursor
            cursor_pos = QCursor.pos()
            self._click_position = cursor_pos
            self._last_global_position = cursor_pos
            log_print(DEBUG, f"クリック位置がないため現在のカーソル位置を使用: x={cursor_pos.x()}, y={cursor_pos.y()}")
        elif self._last_global_position and not self._click_position:
            # クリック位置がなくグローバル位置のみある場合、それを使用
            self._click_position = QPoint(self._last_global_position)
            log_print(DEBUG, f"グローバル位置からクリック位置を設定: x={self._last_global_position.x()}, y={self._last_global_position.y()}")
        
        # 使用するクリック位置を確認
        actual_click_pos = self._last_global_position or self._click_position
        log_print(DEBUG, f"ヒットテストで使用する位置: x={actual_click_pos.x()}, y={actual_click_pos.y()}")
        
        if not self.parent:
            log_print(DEBUG, "親ウィンドウが未設定です")
            return 0  # デフォルトでインデックス0を返す
        
        # シングルモードの場合は常に0を返す
        if hasattr(self.parent, '_dual_view') and not self.parent._dual_view:
            log_print(DEBUG, "シングルモードなので画像インデックス0を対象とします")
            return 0
        
        # シングルモードの別の確認方法（image_modelを参照）
        if hasattr(self.parent, 'image_model') and hasattr(self.parent.image_model, 'is_dual_view') and not self.parent.image_model.is_dual_view():
            log_print(DEBUG, "image_model参照: シングルモードなので画像インデックス0を対象とします")
            return 0
        
        # デュアルモードの場合、クリック位置によって処理対象の画像を判断
        if hasattr(self.parent, 'image_areas') and len(self.parent.image_areas) >= 2:
            # 各画像エリアの位置とサイズを取得して、どちらの画像エリア内でクリックされたか判定
            for i, area in enumerate(self.parent.image_areas[:2]):  # 最初の2つのエリアのみ確認
                if area:
                    # 画像エリアをグローバル座標系に変換するための情報を取得
                    global_pos = area.mapToGlobal(area.rect().topLeft())
                    area_rect = area.rect()
                    
                    # グローバル座標でのエリアの矩形領域を計算
                    global_rect_x = global_pos.x()
                    global_rect_y = global_pos.y()
                    global_rect_width = area_rect.width()
                    global_rect_height = area_rect.height()
                    
                    # クリック位置が画像エリア内かどうかチェック
                    click_x = actual_click_pos.x()  # 変数名を変更
                    click_y = actual_click_pos.y()  # 変数名を変更
                    
                    # 正確なヒットテストを実行
                    is_in_area = (global_rect_x <= click_x <= global_rect_x + global_rect_width and
                                 global_rect_y <= click_y <= global_rect_y + global_rect_height)
                    
                    # より詳細なデバッグ情報を出力
                    log_print(DEBUG, f"エリア {i} 位置: x={global_rect_x}, y={global_rect_y}, "
                                    f"w={global_rect_width}, h={global_rect_height}, "
                                    f"クリック: x={click_x}, y={click_y}, "
                                    f"クリック位置は内部: {is_in_area}")
                    
                    if is_in_area:
                        log_print(INFO, f"画像エリア {i} 内でクリックされました")
                        return i
            
            # 正確なエリア内ヒットテストが失敗した場合は、親ウィンドウ内での相対位置で判断
            # 親ウィンドウのクライアント領域でのクリック位置を取得
            parent_pos = self.parent.mapFromGlobal(self._click_position)
            parent_width = self.parent.width()
            parent_height = self.parent.height()
            
            # クリック位置が親ウィンドウ内かを確認
            if not (0 <= parent_pos.x() <= parent_width and 0 <= parent_pos.y() <= parent_height):
                log_print(DEBUG, f"クリック位置が親ウィンドウの外です: x={parent_pos.x()}, y={parent_pos.y()}, "
                                 f"parent_size={parent_width}x{parent_height}")
                # ウィンドウ外のクリックの場合、左右どちらに近いかで判断
                if parent_pos.x() < 0:  # ウィンドウの左側
                    return 0 if hasattr(self.parent, '_right_to_left') and self.parent._right_to_left else 0
                else:  # ウィンドウの右側かその他
                    return 1 if hasattr(self.parent, '_right_to_left') and self.parent._right_to_left else 1
                    
            # 右から左モードかどうか確認（複数の方法で確認）
            right_to_left = False
            
            # 方法1: 親ウィンドウの_right_to_left属性
            if hasattr(self.parent, '_right_to_left'):
                right_to_left = self.parent._right_to_left
            # 方法2: image_modelのis_right_to_leftメソッド
            elif hasattr(self.parent, 'image_model') and hasattr(self.parent.image_model, 'is_right_to_left'):
                right_to_left = self.parent.image_model.is_right_to_left()
            
            # スプリッターウィジェットがある場合はその位置を取得
            splitter_pos = 0
            if hasattr(self.parent, 'splitter'):
                try:
                    sizes = self.parent.splitter.sizes()
                    if len(sizes) >= 2 and sizes[0] > 0:
                        splitter_pos = sizes[0]  # 左側の幅
                        log_print(DEBUG, f"スプリッター位置: {splitter_pos}, 全体サイズ: {sizes}")
                except Exception as e:
                    log_print(WARNING, f"スプリッター位置の取得に失敗: {str(e)}")
            
            # 中央位置を計算（スプリッターがなければウィンドウの半分）
            split_point = splitter_pos if splitter_pos > 0 else parent_width / 2
            
            log_print(DEBUG, f"親ウィンドウ内クリック位置: x={parent_pos.x()}, y={parent_pos.y()}, "
                            f"ウィンドウ幅: {parent_width}, 分割位置: {split_point}, 右から左モード: {right_to_left}")
            
            # クリック位置が左右どちらにあるかを判断
            is_left_side = parent_pos.x() < split_point
            
            # 右から左モードと通常モードで左右の解釈を反転
            if right_to_left:
                # 右から左モード: 左側=インデックス1, 右側=インデックス0
                result = 1 if is_left_side else 0
            else:
                # 左から右モード: 左側=インデックス0, 右側=インデックス1
                result = 0 if is_left_side else 1
            
            log_print(DEBUG, f"{'左' if is_left_side else '右'}側がクリックされました: インデックス {result} を対象とします")
            return result
        
        # 表示モードとクリック位置の診断情報を出力
        log_print(INFO, f"表示診断: dual_view={hasattr(self.parent, '_dual_view') and self.parent._dual_view}, "
                        f"image_areas={hasattr(self.parent, 'image_areas') and len(self.parent.image_areas) if hasattr(self.parent, 'image_areas') else 0}")
        
        # フォールバック: 単一画像がある場合は必ずインデックス0を返す
        if hasattr(self.parent, 'image_handler') and hasattr(self.parent.image_handler, 'is_image_loaded') and self.parent.image_handler.is_image_loaded(0):
            log_print(DEBUG, "デフォルトとして画像インデックス0を対象とします")
            return 0
        
        # 判断できない場合はNoneを返す
        log_print(ERROR, "表示モードと画像の配置が不明なため、処理対象の画像インデックスを特定できません")
        return None
    
    def _on_fit_to_window(self):
        """ウィンドウに合わせる処理"""
        if hasattr(self.parent, 'fit_to_window'):
            self.parent.fit_to_window()
            self.fit_to_window_action.setChecked(True)
            self.original_size_action.setChecked(False)
            
            # 重複した画像調整を防ぐため、確認処理のみ実行
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._verify_display_mode)
    
    def _verify_display_mode(self):
        """表示モードが正しく適用されているか確認"""
        # 表示が更新されたことをログに出力
        from logutils import log_print, DEBUG
        log_print(DEBUG, "コンテキストメニューからの表示モード変更確認完了")
    
    def _on_original_size(self):
        """原寸大表示処理"""
        if hasattr(self.parent, 'show_original_size'):
            self.parent.show_original_size()
            self.fit_to_window_action.setChecked(False)
            self.original_size_action.setChecked(True)
            
            # 重複した画像調整を防ぐため、確認処理のみ実行
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._verify_display_mode)
    
    def _on_set_view_mode(self, mode: str):
        """
        表示モードを設定
        
        Args:
            mode: 表示モード
                - "single": シングルモード
                - "dual_rl": デュアルモード（右左）
                - "dual_lr": デュアルモード（左右）
                - "dual_rl_shift": デュアルモード（右左シフト）
                - "dual_lr_shift": デュアルモード（左右シフト）
        """
        if hasattr(self.parent, 'set_view_mode'):
            # モードを設定
            self.parent.set_view_mode(mode)
            
            # コンテキストメニューのチェック状態を更新
            self.update_view_mode(mode)
            
            # 処理後、少し遅延させて画像の読み込みと表示を確実にする
            from PySide6.QtCore import QTimer
            QTimer.singleShot(200, lambda: self._ensure_display_updated(mode))
    
    def _ensure_display_updated(self, mode: str):
        """表示モード変更後に確実に画面が更新されるようにする"""
        if hasattr(self.parent, '_update_images_from_browser'):
            # ブラウザから画像を再取得して表示を更新
            self.parent._update_images_from_browser()
            
            # デュアルモードの場合は明示的にフィット表示を呼び出す
            if mode.startswith("dual_") and hasattr(self.parent, 'fit_to_window'):
                self.parent.fit_to_window()
                
        # ログ出力
        from logutils import log_print, DEBUG
        log_print(DEBUG, f"コンテキストメニューから表示モード変更後の画面更新を実行: {mode}")
    
    def _on_superres(self):
        """超解像処理の実行"""
        # カーソル位置の確認
        from PySide6.QtGui import QCursor
        current_pos = QCursor.pos()
        
        # クリック位置が不明な場合は現在のカーソル位置で更新
        if self._click_position is None:
            self._click_position = current_pos
            log_print(DEBUG, f"超解像処理実行時にクリック位置を更新: x={current_pos.x()}, y={current_pos.y()}")
        
        # クリック位置から対象画像のインデックスを取得（詳細デバッグ情報を出力）
        log_print(INFO, f"超解像処理: クリック位置 {self._click_position.x()}, {self._click_position.y()}")
        
        target_index = self._get_target_image_index()
        
        if target_index is not None:
            log_print(INFO, f"画像インデックス {target_index} に対して超解像処理を実行します")
            
            # 親ウィンドウのプロパティを確認（デバッグ用）
            if hasattr(self.parent, 'image_model'):
                is_dual = self.parent.image_model.is_dual_view() if hasattr(self.parent.image_model, 'is_dual_view') else "不明"
                is_rtl = self.parent.image_model.is_right_to_left() if hasattr(self.parent.image_model, 'is_right_to_left') else "不明"
                log_print(INFO, f"親ウィンドウの状態: dual_view={is_dual}, right_to_left={is_rtl}")
            
            # 親ウィンドウのimage_handlerがあるかどうか確認
            if hasattr(self.parent, 'image_handler') and self.parent.image_handler:
                # この画像が実際に読み込まれているか確認
                if hasattr(self.parent.image_handler, 'is_image_loaded') and self.parent.image_handler.is_image_loaded(target_index):
                    # image_handlerのrun_superresメソッドを呼び出す
                    if hasattr(self.parent.image_handler, 'run_superres'):
                        success = self.parent.image_handler.run_superres(target_index)
                        if success:
                            log_print(INFO, f"超解像処理を開始しました: index={target_index}")
                        else:
                            log_print(ERROR, f"超解像処理の実行に失敗しました: index={target_index}")
                    else:
                        log_print(ERROR, "image_handlerにrun_superresメソッドがありません")
                else:
                    log_print(ERROR, f"インデックス {target_index} の画像は読み込まれていません")
            else:
                # 代替方法: 親ウィンドウに直接run_superresメソッドがある場合
                if hasattr(self.parent, 'run_superres'):
                    self.parent.run_superres(target_index)
                    log_print(INFO, f"親ウィンドウのrun_superresメソッドを呼び出しました: index={target_index}")
                else:
                    log_print(ERROR, "超解像処理を実行する方法がありません")
        else:
            log_print(ERROR, "処理対象の画像インデックスが取得できません")
    
    def _on_rotate_left(self):
        """左回転処理"""
        if hasattr(self.parent, 'rotate_left'):
            self.parent.rotate_left()
    
    def _on_rotate_right(self):
        """右回転処理"""
        if hasattr(self.parent, 'rotate_right'):
            self.parent.rotate_right()
    
    def _on_save_as(self):
        """名前を付けて保存処理"""
        if hasattr(self.parent, 'save_image_as'):
            self.parent.save_image_as()
    
    def _on_copy_to_clipboard(self):
        """クリップボードへコピー処理"""
        if hasattr(self.parent, 'copy_to_clipboard'):
            self.parent.copy_to_clipboard()
    
    def _on_close(self):
        """ウィンドウを閉じる処理"""
        self.parent.close()
    
    def update_view_mode(self, mode: str):
        """
        現在の表示モードに合わせてメニューのチェック状態を更新
        
        Args:
            mode: 現在の表示モード
        """
        if mode == "single":
            self.mode_single_action.setChecked(True)
        elif mode == "dual_rl":
            self.mode_dual_rl_action.setChecked(True)
        elif mode == "dual_lr":
            self.mode_dual_lr_action.setChecked(True)
        elif mode == "dual_rl_shift":
            self.mode_dual_rl_shift_action.setChecked(True)
        elif mode == "dual_lr_shift":
            self.mode_dual_lr_shift_action.setChecked(True)
    
    def update_display_mode(self, fit_to_window: bool):
        """
        現在の表示モード（ウィンドウに合わせる/原寸大）に合わせてチェック状態を更新
        
        Args:
            fit_to_window: ウィンドウに合わせるモードがONの場合はTrue
        """
        # メニューアクションのチェック状態を現在のモードに合わせて更新
        self.fit_to_window_action.setChecked(fit_to_window)
        self.original_size_action.setChecked(not fit_to_window)
        
        # デバッグログでチェック状態を確認
        log_print(DEBUG, f"コンテキストメニューの表示モード更新: fit_to_window={fit_to_window}")
    
    def exec(self, pos):
        """
        PySide6の標準メソッドをオーバーライド
        
        Args:
            pos: メニューを表示する位置
        """
        # クリック位置を保存
        if isinstance(pos, QPoint):
            self._click_position = QPoint(pos)  # 明示的にコピーを作成
            self._last_global_position = QPoint(pos)  # グローバル位置も保存
            log_print(DEBUG, f"exec: クリック位置を保存: x={pos.x()}, y={pos.y()}")
        
        # 超解像処理メニューの有効/無効を設定
        self._update_superres_action_state()
        
        # 親クラスのexecメソッドを呼び出し
        return super().exec(pos)
