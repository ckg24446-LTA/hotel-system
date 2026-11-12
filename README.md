# ホテル管理システム (Hotel Management System)

ホテルの顧客・客室・予約・チェックイン／アウト・会計・売上を管理する Web システムです。
Hệ thống quản lý khách sạn: khách hàng, phòng, đặt phòng, check-in/out, kế toán, doanh thu.

## 機能 (Chức năng)
| 区分 | 内容 |
|---|---|
| 顧客管理 | 登録・表示・更新・削除 |
| 客室管理 | 登録・表示・更新・削除・検索（部屋番号／タイプ） |
| 予約管理 | 登録・表示・変更・キャンセル・空室確認 |
| チェックイン・アウト | チェックイン／チェックアウト登録 |
| 会計管理 | 宿泊料金計算・支払処理・レシート発行 |
| 売上管理 | 総売上・月別売上・売上明細 |

## 構成 (Cấu trúc)
```
index.html / style.css / app.js   フロントエンド (HTML, CSS, JavaScript)
server.py                         バックエンド (Python + PyMySQL / MySQL)
database_mysql.sql                MySQL 用データベース定義
server_sqlite.py / database.sql   SQLite 版（予備・追加ライブラリ不要）
docs/System_Design_Templates_Filled.xlsx   画面設計書・テーブル定義書
```

## 動かし方 (Cách chạy) — MySQL 版
1. Python 3 と MySQL 8.0.16 以上 (または MariaDB 10.2 以上) をインストール
2. `pip install pymysql`
3. データベース作成: `mysql -u root -p < database_mysql.sql`
4. サーバー起動:
   ```
   MYSQL_USER=root MYSQL_PASSWORD=パスワード python3 server.py
   ```
   （Windows PowerShell: `$env:MYSQL_PASSWORD="パスワード"; python server.py`）
5. ブラウザで http://127.0.0.1:8000 を開く

接続設定の環境変数 / Biến môi trường: `MYSQL_HOST` (127.0.0.1), `MYSQL_PORT` (3306), `MYSQL_USER` (root), `MYSQL_PASSWORD` (空), `MYSQL_DB` (hotel_db), `PORT` (8000)

## SQLite 版 (MySQL なしで試す場合)
```
python3 server_sqlite.py
```
`hotel.db` が自動作成されます。ライブラリのインストールは不要です。

## データベース (Cơ sở dữ liệu)
`customers` (顧客) / `rooms` (客室) / `reservations` (予約) / `payments` (会計)
二重予約と定員超過はサーバーとトリガーの両方でチェックします。

## 注意 (Lưu ý)
- ログイン機能はありません。`127.0.0.1` のみで待ち受けるため、インターネット公開には認証の追加が必要です。
- パスワードをコードに書かないでください。環境変数で渡します。
