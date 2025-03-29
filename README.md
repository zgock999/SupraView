# SupraView

複数の画像フォーマットに対応した画像ビューワーアプリケーション。

## 機能

- 様々な画像フォーマットのサポート
  - 一般的な画像フォーマット（JPEG, PNG, BMP, GIFなど）
  - レトロコンピューター向け画像フォーマット（MAGなど）
- プラグイン形式のデコーダーシステム
- シンプルなビューワーインターフェース

## インストール

### 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

または、必要最小限のパッケージを直接インストールする場合:

```bash
pip install numpy opencv-python pillow dash dash-bootstrap-components
```

## 使い方

### デコーダーテストビューアの起動

```bash
python -m decoder.viewer
```

ブラウザで http://127.0.0.1:8050/ にアクセスし、画像ファイルをドラッグ&ドロップしてデコードをテストできます。

### カスタムデコーダーの追加

1. `decoder/decoder.py` の `ImageDecoder` クラスを継承したデコーダークラスを実装
2. `decoder/__init__.py` にデコーダークラスをインポートして `__all__` リストに追加

## 対応フォーマット

- OpenCV対応フォーマット: JPEG, PNG, BMP, TIFF など
- MAG形式（X68000, PC-98 の画像フォーマット）

## 開発

### テスト実行

```bash
pytest
```