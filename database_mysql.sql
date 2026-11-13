-- ホテル管理システム データベース (MySQL 8.0.16+ / MariaDB 10.2+)
-- 実行: mysql -u root -p < database_mysql.sql
CREATE DATABASE IF NOT EXISTS hotel_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE hotel_db;

DROP VIEW  IF EXISTS v_monthly_sales;
DROP VIEW  IF EXISTS v_reservation_amount;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS reservations;
DROP TABLE IF EXISTS rooms;
DROP TABLE IF EXISTS customers;

-- 顧客
CREATE TABLE customers (
  customer_id INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(100) NOT NULL,
  kana        VARCHAR(100),
  tel         VARCHAR(30)  NOT NULL,
  email       VARCHAR(255),
  address     VARCHAR(255),
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 客室
CREATE TABLE rooms (
  room_id   INT AUTO_INCREMENT PRIMARY KEY,
  room_no   VARCHAR(10) NOT NULL UNIQUE,
  room_type ENUM('シングル','ダブル','ツイン','スイート') NOT NULL,
  price     INT NOT NULL,
  capacity  INT NOT NULL,
  CONSTRAINT chk_room_price CHECK (price >= 0),
  CONSTRAINT chk_room_cap   CHECK (capacity >= 1)
) ENGINE=InnoDB;

-- 予約
CREATE TABLE reservations (
  reservation_id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id    INT  NOT NULL,
  room_id        INT  NOT NULL,
  check_in       DATE NOT NULL,
  check_out      DATE NOT NULL,
  guests         INT  NOT NULL,
  status         ENUM('予約中','宿泊中','精算待ち','精算済','キャンセル') NOT NULL DEFAULT '予約中',
  checked_in_at  DATETIME NULL,
  checked_out_at DATETIME NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_res_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT,
  CONSTRAINT fk_res_room     FOREIGN KEY (room_id)     REFERENCES rooms(room_id)         ON DELETE RESTRICT,
  CONSTRAINT chk_res_dates   CHECK (check_out > check_in),
  CONSTRAINT chk_res_guests  CHECK (guests >= 1),
  KEY idx_res_room_date (room_id, check_in, check_out),
  KEY idx_res_customer (customer_id)
) ENGINE=InnoDB;

-- 会計・売上
CREATE TABLE payments (
  payment_id     INT AUTO_INCREMENT PRIMARY KEY,
  reservation_id INT NOT NULL UNIQUE,
  amount         INT NOT NULL,
  method         ENUM('現金','クレジットカード','電子マネー') NOT NULL,
  paid_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_pay_res FOREIGN KEY (reservation_id) REFERENCES reservations(reservation_id),
  CONSTRAINT chk_pay_amount CHECK (amount >= 0)
) ENGINE=InnoDB;

-- 二重予約・定員超過の防止
DELIMITER $$
CREATE TRIGGER trg_res_check BEFORE INSERT ON reservations FOR EACH ROW
BEGIN
  IF NEW.guests > (SELECT capacity FROM rooms WHERE room_id = NEW.room_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '定員を超えています';
  END IF;
  IF NEW.status IN ('予約中','宿泊中') AND EXISTS (
       SELECT 1 FROM reservations r
        WHERE r.room_id = NEW.room_id AND r.status IN ('予約中','宿泊中')
          AND NEW.check_in < r.check_out AND NEW.check_out > r.check_in) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'その期間は満室です';
  END IF;
END$$
DELIMITER ;

-- 宿泊料金 = 宿泊数 × 1泊料金
CREATE VIEW v_reservation_amount AS
SELECT r.reservation_id, c.name AS customer, m.room_no, r.check_in, r.check_out, r.status,
       DATEDIFF(r.check_out, r.check_in) AS nights,
       DATEDIFF(r.check_out, r.check_in) * m.price AS amount
FROM reservations r
JOIN customers c ON c.customer_id = r.customer_id
JOIN rooms m     ON m.room_id = r.room_id;

-- 月別売上
CREATE VIEW v_monthly_sales AS
SELECT DATE_FORMAT(paid_at, '%Y-%m') AS month, COUNT(*) AS cnt, SUM(amount) AS total
FROM payments GROUP BY DATE_FORMAT(paid_at, '%Y-%m');

-- サンプルデータ
INSERT INTO customers(name,kana,tel,email,address) VALUES
 ('山田 太郎','ヤマダ タロウ','090-1234-5678','yamada@example.jp','東京都新宿区1-1-1');
INSERT INTO rooms(room_no,room_type,price,capacity) VALUES
 ('101','シングル',8000,1),('102','ダブル',12000,2),('201','ツイン',14000,2),('301','スイート',30000,4);
