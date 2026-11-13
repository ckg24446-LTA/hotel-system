-- ホテル管理システム データベース (SQLite)
PRAGMA foreign_keys = ON;

-- 1. 顧客
CREATE TABLE customers (
  customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,                -- 氏名
  kana        TEXT,                         -- フリガナ
  tel         TEXT NOT NULL,                -- 電話番号
  email       TEXT,
  address     TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 2. 客室
CREATE TABLE rooms (
  room_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  room_no   TEXT NOT NULL UNIQUE,           -- 部屋番号
  room_type TEXT NOT NULL CHECK (room_type IN ('シングル','ダブル','ツイン','スイート')),
  price     INTEGER NOT NULL CHECK (price >= 0),     -- 1泊料金
  capacity  INTEGER NOT NULL CHECK (capacity >= 1)   -- 定員
);

-- 3. 予約 (チェックイン・アウトの状態もここで管理)
CREATE TABLE reservations (
  reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id    INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,
  room_id        INTEGER NOT NULL REFERENCES rooms(room_id)         ON DELETE RESTRICT,
  check_in       TEXT NOT NULL,             -- 宿泊開始日 YYYY-MM-DD
  check_out      TEXT NOT NULL,             -- 宿泊終了日
  guests         INTEGER NOT NULL CHECK (guests >= 1),
  status         TEXT NOT NULL DEFAULT '予約中'
                 CHECK (status IN ('予約中','宿泊中','精算待ち','精算済','キャンセル')),
  checked_in_at  TEXT,                      -- 実チェックイン日時
  checked_out_at TEXT,                      -- 実チェックアウト日時
  created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  CHECK (check_out > check_in)
);
CREATE INDEX idx_res_room_date ON reservations(room_id, check_in, check_out);
CREATE INDEX idx_res_customer  ON reservations(customer_id);

-- 4. 会計・売上 (1予約につき1支払い)
CREATE TABLE payments (
  payment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  reservation_id INTEGER NOT NULL UNIQUE REFERENCES reservations(reservation_id),
  amount         INTEGER NOT NULL CHECK (amount >= 0),
  method         TEXT NOT NULL CHECK (method IN ('現金','クレジットカード','電子マネー')),
  paid_at        TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 二重予約・定員超過の防止
CREATE TRIGGER trg_res_check BEFORE INSERT ON reservations
BEGIN
  SELECT RAISE(ABORT,'定員を超えています')
   WHERE NEW.guests > (SELECT capacity FROM rooms WHERE room_id = NEW.room_id);
  SELECT RAISE(ABORT,'その期間は満室です')
   WHERE NEW.status IN ('予約中','宿泊中') AND EXISTS (
     SELECT 1 FROM reservations r
      WHERE r.room_id = NEW.room_id AND r.status IN ('予約中','宿泊中')
        AND NEW.check_in < r.check_out AND NEW.check_out > r.check_in);
END;

-- 宿泊料金 = 宿泊数 × 1泊料金
CREATE VIEW v_reservation_amount AS
SELECT r.reservation_id, c.name AS customer, m.room_no, r.check_in, r.check_out, r.status,
       CAST(julianday(r.check_out) - julianday(r.check_in) AS INTEGER) AS nights,
       CAST(julianday(r.check_out) - julianday(r.check_in) AS INTEGER) * m.price AS amount
FROM reservations r
JOIN customers c ON c.customer_id = r.customer_id
JOIN rooms m     ON m.room_id = r.room_id;

-- 売上管理 (月別)
CREATE VIEW v_monthly_sales AS
SELECT substr(paid_at,1,7) AS month, COUNT(*) AS cnt, SUM(amount) AS total
FROM payments GROUP BY substr(paid_at,1,7);

-- サンプルデータ
INSERT INTO customers(name,kana,tel,email,address) VALUES
 ('山田 太郎','ヤマダ タロウ','090-1234-5678','yamada@example.jp','東京都新宿区1-1-1');
INSERT INTO rooms(room_no,room_type,price,capacity) VALUES
 ('101','シングル',8000,1),('102','ダブル',12000,2),('201','ツイン',14000,2),('301','スイート',30000,4);

-- ===== よく使うクエリ =====
-- 空室確認 (:from, :to を指定)
--   SELECT * FROM rooms WHERE room_id NOT IN (
--     SELECT room_id FROM reservations WHERE status IN ('予約中','宿泊中')
--       AND :from < check_out AND :to > check_in);
-- 客室検索
--   SELECT * FROM rooms WHERE room_no LIKE '1%' AND room_type = 'ダブル';
-- チェックイン / チェックアウト
--   UPDATE reservations SET status='宿泊中',   checked_in_at=datetime('now','localtime')  WHERE reservation_id=?;
--   UPDATE reservations SET status='精算待ち', checked_out_at=datetime('now','localtime') WHERE reservation_id=?;
-- 支払処理
--   INSERT INTO payments(reservation_id,amount,method) SELECT reservation_id,amount,'現金' FROM v_reservation_amount WHERE reservation_id=?;
--   UPDATE reservations SET status='精算済' WHERE reservation_id=?;
