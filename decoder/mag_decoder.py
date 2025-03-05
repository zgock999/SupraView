"""
MAG形式デコーダー

X68000の画像フォーマットMAG（MAG形式）をデコードするImageDecoderの実装
参考: https://emk.name/2015/03/magjs.html のJavaScript実装および
https://www.vector.co.jp/soft/dl/pc/art/se004903.html のMAGBIBLE.txtの仕様書
"""

import numpy as np
from typing import List, Optional, Tuple

from .decoder import ImageDecoder


class MAGImageDecoder(ImageDecoder):
    """
    MAGフォーマット画像デコーダー
    
    X68000およびPC-98等で使用された画像フォーマットのデコーダー
    """
    
    @property
    def supported_extensions(self) -> List[str]:
        """
        サポートする拡張子のリスト
        
        Returns:
            List[str]: サポートされている拡張子のリスト
        """
        return ['.mag']
    
    def decode(self, data: bytes) -> Optional[np.ndarray]:
        """
        MAG形式のバイナリデータをデコードする
        
        Args:
            data (bytes): デコードする画像のバイトデータ
            
        Returns:
            Optional[np.ndarray]: デコードされた画像の numpy 配列、失敗した場合は None
                                  形状は (height, width, channels) の順
        """
        try:
            width, height, pixels = self._decode_mag(data)
            return pixels  # すでに正しい形式 (height, width, 3) の numpy 配列
        except Exception as e:
            print(f"MAG画像デコードエラー: {e}")
            return None
    
    def get_image_info(self, data: bytes) -> Optional[Tuple[int, int, int]]:
        """
        MAG画像の基本情報を取得する
        
        Args:
            data (bytes): 情報を取得する画像のバイトデータ
            
        Returns:
            Optional[Tuple[int, int, int]]: (幅, 高さ, チャンネル数) の形式の情報、
                                           取得できない場合は None
        """
        try:
            # ヘッダーチェック
            if not data or len(data) < 16:
                return None

            # 先頭8バイトがヘッダー
            header = data[0:8]
            if header != b'MAKI02  ' and header != b'MAKI03  ':
                return None
            
            # コメント部分の読み飛ばし
            offset = 8
            while offset < len(data) and data[offset] != 0x1A and data[offset] != 0:
                offset += 1
            
            # 終端マークも読み飛ばす
            if offset < len(data):
                offset += 1
            
            # ヘッダ領域の解析
            if offset + 32 > len(data):
                return None
            
            # 表示範囲から画像サイズを計算
            x1 = int.from_bytes(data[offset+4:offset+6], byteorder='little')
            y1 = int.from_bytes(data[offset+6:offset+8], byteorder='little')
            x2 = int.from_bytes(data[offset+8:offset+10], byteorder='little')
            y2 = int.from_bytes(data[offset+10:offset+12], byteorder='little')
            
            # 画像サイズの計算
            width = x2 - x1 + 1
            height = y2 - y1 + 1
            
            # 200ラインモードのチェック
            screen_mode = data[offset+3]
            is_200line = (screen_mode & 0x01) != 0
            
            if is_200line:
                height *= 2  # 200ラインモードなら高さを2倍
                
            # MAG画像はRGB形式で3チャンネル
            channels = 3
            
            return (width, height, channels)
        except Exception as e:
            print(f"MAG画像情報取得エラー: {e}")
            return None

    def _decode_mag(self, data: bytes) -> Tuple[int, int, np.ndarray]:
        """
        MAG形式のバイナリデータを内部でデコードする
        
        Args:
            data (bytes): MAG形式のバイナリデータ
        
        Returns:
            Tuple[int, int, np.ndarray]: 幅、高さ、RGBピクセル配列
        """
        if not data or len(data) < 16:
            raise ValueError("無効なMAGデータです: データが短すぎます")

        # 先頭8バイトがヘッダー
        header = data[0:8]
        if header != b'MAKI02  ' and header != b'MAKI03  ':
            raise ValueError(f"無効なMAGヘッダー: {header}")
        
        # コメント部分の読み飛ばし
        # EOFマーク(0x1A)またはNUL(0x00)までがコメント
        offset = 8
        while offset < len(data) and data[offset] != 0x1A and data[offset] != 0:
            offset += 1
        
        # 終端マークも読み飛ばす
        if offset < len(data):
            offset += 1
        
        # ヘッダ領域の解析 (32バイト)
        if offset + 32 > len(data):
            raise ValueError("無効なMAGデータです: ヘッダ領域が存在しません")
        
        # 機種コード
        machine_code = data[offset+1]
        # 機種依存フラグ
        dependent_flag = data[offset+2]
        # スクリーンモード
        screen_mode = data[offset+3]
        
        # 表示範囲
        x1 = int.from_bytes(data[offset+4:offset+6], byteorder='little')
        y1 = int.from_bytes(data[offset+6:offset+8], byteorder='little')
        x2 = int.from_bytes(data[offset+8:offset+10], byteorder='little')
        y2 = int.from_bytes(data[offset+10:offset+12], byteorder='little')
        
        # 画像サイズの計算
        width = x2 - x1 + 1
        height = y2 - y1 + 1
        
        # 各セクションのオフセット情報
        flag_a_offset = int.from_bytes(data[offset+12:offset+16], byteorder='little')
        flag_b_offset = int.from_bytes(data[offset+16:offset+20], byteorder='little')
        flag_b_size = int.from_bytes(data[offset+20:offset+24], byteorder='little')
        pixel_offset = int.from_bytes(data[offset+24:offset+28], byteorder='little')
        pixel_size = int.from_bytes(data[offset+28:offset+32], byteorder='little')
        
        # オフセットはヘッダ先頭からの相対位置
        flag_a_offset += offset
        flag_b_offset += offset
        pixel_offset += offset
        
        # スクリーンモードの解析
        is_256color = (screen_mode & 0x80) != 0
        is_200line = (screen_mode & 0x01) != 0
        is_8color = (screen_mode & 0x02) != 0
        is_digital = (screen_mode & 0x04) != 0
        
        # ピクセルの単位サイズを計算（16色=4ドット、256色=2ドット）
        pixel_unit = 2 if is_256color else 4
        # 水平ピクセル数（仮想座標系の幅）
        h_pixels = (width + pixel_unit - 1) // pixel_unit
        
        if width <= 0 or height <= 0 or width > 10000 or height > 10000:
            raise ValueError(f"無効な画像サイズ: {width}x{height}")
        
        # パレットの読み込み
        palette_offset = offset + 32
        color_count = 256 if is_256color else 16
        palette_size = color_count * 3  # RGB各1バイト
        
        if palette_offset + palette_size > len(data):
            raise ValueError("無効なMAGデータです: パレットデータが存在しません")
        
        # パレットを読み込む
        palette = []
        for i in range(color_count):
            # GRBの順でパレットが格納されている
            g = data[palette_offset + i * 3]
            r = data[palette_offset + i * 3 + 1]
            b = data[palette_offset + i * 3 + 2]
            
            # 値をそのまま使用する（スケール化なし）
            palette.append((r, g, b))
        
        # フラグの展開
        flag_a_size = flag_b_offset - flag_a_offset
        flag_a_bits = flag_a_size * 8  # ビット数
        
        # フラグデータ用の配列を作成
        flags = np.zeros(h_pixels * height, dtype=np.uint8)
        flag_index = 0
        
        # フラグAとフラグBからフラグデータを構築
        bit_pos = 0  # フラグAのビット位置
        flag_b_index = 0  # フラグBのインデックス
        
        for i in range(h_pixels * height // 2):  # フラグAのビット数分処理
            if bit_pos >= flag_a_bits:
                break
            
            byte_pos = bit_pos // 8
            bit_in_byte = 7 - (bit_pos % 8)  # MSBから処理
            
            # インデックス範囲チェック
            if flag_a_offset + byte_pos >= len(data):
                break
            
            flag_a_byte = data[flag_a_offset + byte_pos]
            flag_a_bit = (flag_a_byte >> bit_in_byte) & 1
            
            bit_pos += 1
            
            if flag_a_bit == 0:
                # フラグが0の場合は2つのフラグデータに0を設定
                if flag_index + 1 < len(flags):
                    flags[flag_index] = 0
                    flags[flag_index + 1] = 0
                    flag_index += 2
                else:
                    break
            else:
                # フラグBからフラグデータを取得
                if flag_b_offset + flag_b_index < len(data):
                    flag_b_byte = data[flag_b_offset + flag_b_index]
                    if flag_index + 1 < len(flags):
                        flags[flag_index] = (flag_b_byte >> 4) & 0x0F  # 上位4ビット
                        flags[flag_index + 1] = flag_b_byte & 0x0F     # 下位4ビット
                        flag_index += 2
                    else:
                        break
                    flag_b_index += 1  # フラグBのインデックスを正しくインクリメント
                else:
                    # 残りのフラグはゼロで埋める
                    while flag_index < len(flags):
                        flags[flag_index] = 0
                        flag_index += 1
                    break
        
        # フラグのXOR差分を元に戻す（上から一行ずつ処理）
        for y in range(1, height):
            line_start = y * h_pixels
            prev_line_start = (y - 1) * h_pixels
            for x in range(h_pixels):
                flags[line_start + x] ^= flags[prev_line_start + x]
        
        # デコード結果の配列を準備
        pixels = np.zeros((height, width, 3), dtype=np.uint8)
        
        # ピクセルデータのデコード
        pixel_index = 0  # ピクセルデータのインデックス
        
        for y in range(height):
            for px in range(h_pixels):
                # インデックスの範囲チェック
                if y * h_pixels + px >= len(flags):
                    continue
                    
                # フラグの取得
                flag = flags[y * h_pixels + px]
                
                # フラグに応じて処理
                if flag == 0:
                    # 新しいピクセルデータ
                    if pixel_offset + pixel_index + 1 < len(data):
                        # ピクセルデータを単純に2バイト読み込む
                        pixel_byte_low = data[pixel_offset + pixel_index]
                        pixel_byte_high = data[pixel_offset + pixel_index + 1]
                        pixel_index += 2
                        
                        # 16色モードの場合
                        if not is_256color:
                            # 4ドット分展開（16色画像）
                            # バイトデータを4ビットずつに分解
                            color_index3 = (pixel_byte_high >> 4) & 0x0F  # 上位バイトの上位4ビット
                            color_index4 = pixel_byte_high & 0x0F         # 上位バイトの下位4ビット
                            color_index1 = (pixel_byte_low >> 4) & 0x0F   # 下位バイトの上位4ビット
                            color_index2 = pixel_byte_low & 0x0F          # 下位バイトの下位4ビット
                            
                            # 各ドットを配置（範囲チェック付き）
                            if px * 4 < width:
                                pixels[y, px * 4] = palette[color_index1]
                            if px * 4 + 1 < width:
                                pixels[y, px * 4 + 1] = palette[color_index2]
                            if px * 4 + 2 < width:
                                pixels[y, px * 4 + 2] = palette[color_index3]
                            if px * 4 + 3 < width:
                                pixels[y, px * 4 + 3] = palette[color_index4]
                        else:
                            # 256色モードの場合は2ドット分展開
                            if px * 2 < width:
                                pixels[y, px * 2] = palette[pixel_byte_low]
                            if px * 2 + 1 < width:
                                pixels[y, px * 2 + 1] = palette[pixel_byte_high]
                    else:
                        # データが不足している場合、残りを黒で埋める
                        if not is_256color:
                            for i in range(4):
                                x_pos = px * 4 + i
                                if 0 <= x_pos < width:
                                    pixels[y, x_pos] = (0, 0, 0)
                        else:
                            for i in range(2):
                                x_pos = px * 2 + i
                                if 0 <= x_pos < width:
                                    pixels[y, x_pos] = (0, 0, 0)
                else:
                    # 相対位置からピクセルをコピー
                    copy_x, copy_y = 0, 0
                    
                    # フラグは4ビットのみなので値の範囲を確保
                    flag = flag & 0x0F
                    
                    # 仕様書に基づいて参照先を特定
                    if flag == 1:
                        copy_x, copy_y = px - 1, y
                    elif flag == 2:
                        copy_x, copy_y = px - 2, y
                    elif flag == 3:
                        copy_x, copy_y = px - 4, y
                    elif flag == 4:
                        copy_x, copy_y = px - 0, y - 1
                    elif flag == 5:
                        copy_x, copy_y = px - 1, y - 1
                    elif flag == 6:
                        copy_x, copy_y = px - 0, y - 2
                    elif flag == 7:
                        copy_x, copy_y = px - 1, y - 2
                    elif flag == 8:
                        copy_x, copy_y = px - 2, y - 2
                    elif flag == 9:
                        copy_x, copy_y = px - 0, y - 4
                    elif flag == 10:
                        copy_x, copy_y = px - 1, y - 4
                    elif flag == 11:
                        copy_x, copy_y = px - 2, y - 4
                    elif flag == 12:
                        copy_x, copy_y = px - 0, y - 8
                    elif flag == 13:
                        copy_x, copy_y = px - 1, y - 8
                    elif flag == 14:
                        copy_x, copy_y = px - 2, y - 8
                    elif flag == 15:
                        copy_x, copy_y = px - 0, y - 16
                    else:
                        # 万が一フラグ値が範囲外の場合
                        copy_x, copy_y = -1, -1  # 無効な値
                    
                    # コピー元の範囲チェック - 負の値や範囲外を防ぐ
                    if 0 <= copy_x < h_pixels and 0 <= copy_y < height:
                        if not is_256color:
                            # 16色の場合は1ピクセル=4ドット分コピー
                            for i in range(4):
                                src_x = copy_x * 4 + i
                                dest_x = px * 4 + i
                                if 0 <= src_x < width and 0 <= dest_x < width:
                                    pixels[y, dest_x] = pixels[copy_y, src_x]
                        else:
                            # 256色の場合は1ピクセル=2ドット分コピー
                            for i in range(2):
                                src_x = copy_x * 2 + i
                                dest_x = px * 2 + i
                                if 0 <= src_x < width and 0 <= dest_x < width:
                                    pixels[y, dest_x] = pixels[copy_y, src_x]
        
        # 200ラインモードの場合、縦を2倍に拡大
        if is_200line:
            double_height = height * 2
            double_pixels = np.zeros((double_height, width, 3), dtype=np.uint8)
            for y in range(height):
                double_pixels[y * 2] = pixels[y]
                double_pixels[y * 2 + 1] = pixels[y]
            return width, double_height, double_pixels

        # RGB配列を返す
        return width, height, pixels
