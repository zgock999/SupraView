"""
デコーダーテストビューア

Dash フレームワークを使用してデコーダーの動作をテストするGUIアプリケーション
"""

import base64
import io
import os
import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
from PIL import Image
import numpy as np
import sys
import traceback
from typing import Dict, List, Tuple, Optional

# 親ディレクトリをシステムパスに追加して、デコーダーモジュールをインポートできるようにする
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# デコーダーモジュールをインポート
from decoder import ImageDecoder, CV2ImageDecoder, MAGImageDecoder


class DecoderManager:
    """デコーダーの管理と選択を行うクラス"""
    
    def __init__(self):
        """利用可能なすべてのデコーダーをロードする"""
        self.decoders: List[ImageDecoder] = [
            CV2ImageDecoder(),
            MAGImageDecoder(),
            # 他のデコーダーがあれば追加
        ]
        
        # 拡張子ごとにデコーダーをマッピング
        self.extension_map: Dict[str, List[ImageDecoder]] = {}
        for decoder in self.decoders:
            for ext in decoder.supported_extensions:
                if ext not in self.extension_map:
                    self.extension_map[ext] = []
                self.extension_map[ext].append(decoder)
    
    def get_decoders_for_extension(self, filename: str) -> List[ImageDecoder]:
        """
        指定されたファイル名の拡張子に対応するデコーダーのリストを返す
        
        Args:
            filename: デコードするファイルの名前
            
        Returns:
            対応するデコーダーのリスト。対応するデコーダーがない場合は空リスト
        """
        _, ext = os.path.splitext(filename.lower())
        if ext in self.extension_map:
            return self.extension_map[ext]
        return []
    
    def decode_image(self, filename: str, data: bytes) -> Optional[Tuple[np.ndarray, str]]:
        """
        画像データをデコードする
        
        Args:
            filename: ファイル名
            data: デコードするバイトデータ
            
        Returns:
            デコードされた画像の numpy 配列とデコーダー名のタプル、または None
        """
        decoders = self.get_decoders_for_extension(filename)
        
        # 対応するデコーダーがない場合
        if not decoders:
            print(f"対応するデコーダーがありません: {filename}")
            return None
        
        # すべてのデコーダーを試す
        for decoder in decoders:
            try:
                result = decoder.decode(data)
                if result is not None:
                    # 成功したデコーダーの情報と結果を返す
                    return result, decoder.__class__.__name__
            except Exception as e:
                print(f"{decoder.__class__.__name__} デコードエラー: {e}")
                traceback.print_exc()
                continue
        
        # すべてのデコーダーが失敗した場合
        return None


# Dashアプリケーションの作成
def create_app():
    """Dashアプリケーションを作成して返す"""
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="SupraView デコーダーテスト"
    )
    
    # デコーダーマネージャー
    decoder_manager = DecoderManager()
    
    # レイアウトの定義
    app.layout = dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H1("SupraView デコーダーテストビューア", className="text-center my-4"),
                html.Hr(),
            ], width=12)
        ]),
        
        dbc.Row([
            dbc.Col([
                # ファイルドロップエリア
                dcc.Upload(
                    id='upload-image',
                    children=html.Div([
                        'ファイルをドラッグ&ドロップ ',
                        html.A('または選択', className="text-primary")
                    ]),
                    style={
                        'width': '100%',
                        'height': '60px',
                        'lineHeight': '60px',
                        'borderWidth': '1px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                        'margin': '10px'
                    },
                    multiple=False
                ),
            ], width=12)
        ]),
        
        dbc.Row([
            dbc.Col([
                # ファイル情報表示エリア
                html.Div(id='file-info', className="mt-3"),
            ], width=12)
        ]),
        
        dbc.Row([
            dbc.Col([
                # 画像表示エリア
                html.Div(id='output-image-upload', className="mt-3 text-center"),
            ], width=12)
        ]),
        
        dbc.Row([
            dbc.Col([
                # エラーメッセージエリア
                html.Div(id='error-message', className="mt-3 text-danger"),
            ], width=12)
        ]),
    ], fluid=True)
    
    # コールバック - アップロードされた画像を処理して表示する
    @callback(
        Output('output-image-upload', 'children'),
        Output('file-info', 'children'),
        Output('error-message', 'children'),
        Input('upload-image', 'contents'),
        State('upload-image', 'filename')
    )
    def update_output(contents, filename):
        """アップロードされたファイルを処理して表示する"""
        if contents is None:
            return html.Div(), html.Div(), ""
        
        try:
            # Base64エンコードされたデータの先頭部分を削除
            content_type, content_string = contents.split(',')
            
            # Base64デコード
            decoded = base64.b64decode(content_string)
            
            # 画像をデコード
            result = decoder_manager.decode_image(filename, decoded)
            
            if result is None:
                return (
                    html.Div(),
                    html.Div(),
                    f"画像のデコードに失敗しました: {filename}"
                )
            
            # デコード結果と使用したデコーダー
            img_array, decoder_name = result
            
            # PIL Imageに変換
            if len(img_array.shape) == 3 and img_array.shape[2] == 4:  # RGBA
                img = Image.fromarray(img_array, 'RGBA')
            elif len(img_array.shape) == 3 and img_array.shape[2] == 3:  # RGB
                img = Image.fromarray(img_array, 'RGB')
            elif len(img_array.shape) == 2:  # グレースケール
                img = Image.fromarray(img_array, 'L')
            else:
                # その他の形式はRGBに変換を試みる
                img = Image.fromarray(img_array.astype('uint8'))
            
            # メモリストリームにPNG形式で保存
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            # 画像情報
            height, width = img_array.shape[:2]
            channels = 1 if len(img_array.shape) == 2 else img_array.shape[2]
            
            # ファイル情報とデコード情報
            file_info = dbc.Card(
                dbc.CardBody([
                    html.H4(filename, className="card-title"),
                    html.P([
                        html.Strong("使用デコーダー: "), f"{decoder_name}",
                        html.Br(),
                        html.Strong("サイズ: "), f"{width}x{height} ({channels}チャンネル)",
                    ], className="card-text")
                ])
            )
            
            # 画像表示
            return (
                html.Img(
                    src=f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}",
                    style={
                        'max-width': '100%',
                        'max-height': '800px'
                    },
                    className="img-fluid border"
                ),
                file_info,
                ""
            )
            
        except Exception as e:
            print(f"エラー: {e}")
            traceback.print_exc()
            return html.Div(), html.Div(), f"エラーが発生しました: {str(e)}"
    
    return app


def run_viewer(debug=True, port=8050):
    """
    デコーダーテストビューアを起動する
    
    Args:
        debug: デバッグモードを有効にするかどうか
        port: 使用するポート番号
    """
    app = create_app()
    app.run_server(debug=debug, port=port)


if __name__ == "__main__":
    # スクリプトから直接実行された場合はビューアを起動
    print("SupraView デコーダーテストビューアを起動しています...")
    print("Webブラウザで http://127.0.0.1:8050/ にアクセスしてください")
    run_viewer(debug=True, port=8050)
