#!/usr/bin/env python3
"""ホテル管理システム バックエンド (Python + PyMySQL / MySQL)
準備: pip install pymysql && mysql -u root -p < database_mysql.sql
起動: python3 server.py  →  http://127.0.0.1:8000
"""
import json, os, pymysql, pymysql.cursors
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = {'/': 'index.html', '/index.html': 'index.html', '/style.css': 'style.css', '/app.js': 'app.js'}
TYPES = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript'}
ACTIVE = "('予約中','宿泊中')"
CFG = dict(host=os.environ.get('MYSQL_HOST', '127.0.0.1'), port=int(os.environ.get('MYSQL_PORT', 3306)),
           user=os.environ.get('MYSQL_USER', 'root'), password=os.environ.get('MYSQL_PASSWORD', ''),
           database=os.environ.get('MYSQL_DB', 'hotel_db'), charset='utf8mb4')

class Err(Exception):
    def __init__(self, msg, code=400): super().__init__(msg); self.code = code

class Conn:
    """pymysql の薄いラッパー (sqlite3 風に conn.execute(sql, args) で使えるようにする)"""
    def __init__(self): self.c = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **CFG)
    def execute(self, sql, a=()):
        cur = self.c.cursor(); cur.execute(sql.replace('?', '%s'), tuple(a) or None); return cur
    def commit(self): self.c.commit()
    def rollback(self): self.c.rollback()
    def close(self): self.c.close()

def conn(): return Conn()

def reset():
    c = conn()
    try:
        for t in ('payments', 'reservations', 'customers', 'rooms'):
            c.execute('SET FOREIGN_KEY_CHECKS=0'); c.execute(f'TRUNCATE TABLE {t}'); c.execute('SET FOREIGN_KEY_CHECKS=1')
        c.execute("INSERT INTO customers(name,kana,tel,email,address) VALUES('山田 太郎','ヤマダ タロウ','090-1234-5678','yamada@example.jp','東京都新宿区1-1-1')")
        for r in (('101', 'シングル', 8000, 1), ('102', 'ダブル', 12000, 2), ('201', 'ツイン', 14000, 2), ('301', 'スイート', 30000, 4)):
            c.execute('INSERT INTO rooms(room_no,room_type,price,capacity) VALUES(?,?,?,?)', r)
        c.commit()
    finally: c.close()

def q(c, sql, *a): return list(c.execute(sql, a).fetchall())

def state(c):
    return {
        'customers': q(c, 'SELECT customer_id id,name,kana,tel,email,address FROM customers ORDER BY id'),
        'rooms': q(c, 'SELECT room_id id,room_no AS `no`,room_type AS `type`,price,capacity AS cap FROM rooms ORDER BY room_no'),
        'reservations': q(c, '''SELECT r.reservation_id id,r.customer_id customerId,r.room_id roomId,r.check_in AS checkIn,
            r.check_out checkOut,r.guests,r.status,p.amount total,p.method,DATE(p.paid_at) paidAt
            FROM reservations r LEFT JOIN payments p ON p.reservation_id=r.reservation_id ORDER BY r.reservation_id'''),
        'sales': q(c, '''SELECT p.payment_id id,DATE(p.paid_at) `date`,p.reservation_id resId,c.name,p.method,p.amount
            FROM payments p JOIN reservations r ON r.reservation_id=p.reservation_id
            JOIN customers c ON c.customer_id=r.customer_id ORDER BY p.payment_id'''),
    }

# テーブル定義: (テーブル, 主キー, {JSONキー: 列名}, 必須キー, 整数キー)
TBL = {
    'customers': ('customers', 'customer_id', {'name': 'name', 'kana': 'kana', 'tel': 'tel', 'email': 'email', 'address': 'address'}, ['name', 'tel'], []),
    'rooms': ('rooms', 'room_id', {'no': 'room_no', 'type': 'room_type', 'price': 'price', 'cap': 'capacity'}, ['no', 'type', 'price', 'cap'], ['price', 'cap']),
}

def one(c, sql, *a):
    r = c.execute(sql, a).fetchone()
    if r is None: raise Err('データが見つかりません', 404)
    return r

def check_res(c, room_id, cin, cout, guests, exclude=0):
    if not (cin and cout) or cout <= cin: raise Err('チェックアウト日はチェックイン日より後にしてください')
    cap = one(c, 'SELECT capacity FROM rooms WHERE room_id=?', room_id)['capacity']
    if guests < 1 or guests > cap: raise Err(f'この客室の定員は{cap}名です')
    if c.execute(f'''SELECT 1 FROM reservations WHERE room_id=? AND reservation_id<>? AND status IN {ACTIVE}
                     AND ?<check_out AND ?>check_in''', (room_id, exclude, cin, cout)).fetchone():
        raise Err('その期間は満室です')

def route(c, m, path, d):
    if m == 'GET' and path == '/state': return state(c)
    if m == 'POST' and path == '/reset': c.rollback(); reset(); return {}
    p = path.strip('/').split('/')
    t = p[0]; i = int(p[1]) if len(p) > 1 and p[1].isdigit() else None; act = p[2] if len(p) > 2 else None

    if t in TBL:
        tb, pk, cols, req, ints = TBL[t]
        if m in ('POST', 'PUT'):
            if any(str(d.get(k, '')).strip() == '' for k in req): raise Err('必須項目を入力してください')
            try: vals = [int(d[k]) if k in ints else str(d.get(k, '')).strip() for k in cols]
            except (ValueError, KeyError): raise Err('数値を正しく入力してください')
        try:
            if m == 'POST' and i is None:
                c.execute(f'INSERT INTO {tb}({",".join(cols.values())}) VALUES({",".join("?" * len(cols))})', vals)
            elif m == 'PUT' and i:
                c.execute(f'UPDATE {tb} SET {",".join(v + "=?" for v in cols.values())} WHERE {pk}=?', vals + [i])
            elif m == 'DELETE' and i:
                c.execute(f'DELETE FROM {tb} WHERE {pk}=?', (i,))
            else: raise Err('不正なリクエストです', 404)
        except pymysql.err.IntegrityError as e:
            code = e.args[0]
            if code == 1062: raise Err('その部屋番号は登録済みです')
            if code in (1451, 1452): raise Err('予約データがあるため削除できません')
            raise Err('入力内容を確認してください')
        return {}

    if t == 'reservations':
        if m == 'POST' and i is None:
            cid, rid, g = int(d['customerId']), int(d['roomId']), int(d['guests'])
            one(c, 'SELECT 1 FROM customers WHERE customer_id=?', cid)
            check_res(c, rid, d['checkIn'], d['checkOut'], g)
            c.execute('INSERT INTO reservations(customer_id,room_id,check_in,check_out,guests) VALUES(?,?,?,?,?)',
                      (cid, rid, d['checkIn'], d['checkOut'], g))
            return {}
        r = one(c, '''SELECT r.*, m.price FROM reservations r JOIN rooms m ON m.room_id=r.room_id WHERE reservation_id=?''', i)
        st = r['status']
        def need(s, msg):
            if st != s: raise Err(msg)
        if m == 'PUT':
            need('予約中', '変更できるのは予約中のみです')
            g = int(d['guests']); check_res(c, r['room_id'], d['checkIn'], d['checkOut'], g, i)
            c.execute('UPDATE reservations SET check_in=?,check_out=?,guests=? WHERE reservation_id=?', (d['checkIn'], d['checkOut'], g, i))
        elif act == 'cancel':
            need('予約中', 'キャンセルできるのは予約中のみです')
            c.execute("UPDATE reservations SET status='キャンセル' WHERE reservation_id=?", (i,))
        elif act == 'checkin':
            need('予約中', 'チェックインできません')
            c.execute("UPDATE reservations SET status='宿泊中',checked_in_at=NOW() WHERE reservation_id=?", (i,))
        elif act == 'checkout':
            need('宿泊中', 'チェックアウトできません')
            c.execute("UPDATE reservations SET status='精算待ち',checked_out_at=NOW() WHERE reservation_id=?", (i,))
        elif act == 'pay':
            need('精算待ち', '精算できる状態ではありません')
            if d.get('method') not in ('現金', 'クレジットカード', '電子マネー'): raise Err('支払方法が不正です')
            n = one(c, 'SELECT DATEDIFF(?, ?) AS n', r['check_out'], r['check_in'])['n']
            c.execute('INSERT INTO payments(reservation_id,amount,method) VALUES(?,?,?)', (i, max(1, n) * r['price'], d['method']))
            c.execute("UPDATE reservations SET status='精算済' WHERE reservation_id=?", (i,))
        else: raise Err('不正なリクエストです', 404)
        return {}
    raise Err('不正なリクエストです', 404)

class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype='application/json; charset=utf-8'):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(code); self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(b))); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)

    def handle_any(self):
        path = self.path.split('?')[0]
        if not path.startswith('/api/'):
            f = STATIC.get(path)
            if self.command != 'GET' or not f: return self.send(404, {'error': 'Not Found'})
            return self.send(200, open(os.path.join(BASE, f), 'rb').read(), TYPES[os.path.splitext(f)[1]] + '; charset=utf-8')
        try:
            n = int(self.headers.get('Content-Length') or 0)
            d = json.loads(self.rfile.read(n) or b'{}') if n else {}
            c = conn()
            try:
                res = route(c, self.command, path[4:], d); c.commit()
            except Exception: c.rollback(); raise
            finally: c.close()
            self.send(200, res)
        except Err as e: self.send(e.code, {'error': str(e)})
        except (KeyError, ValueError, TypeError, json.JSONDecodeError): self.send(400, {'error': '入力内容が不正です'})
        except pymysql.MySQLError as e: self.send(400 if e.args[0] in (1644, 3819, 4025) else 500, {'error': str(e.args[-1]) if e.args[0] in (1644, 3819, 4025) else 'データベースエラー: ' + str(e.args[-1])})
        except Exception as e: self.send(500, {'error': 'サーバーエラー: ' + str(e)})

    do_GET = do_POST = do_PUT = do_DELETE = handle_any
    def log_message(self, f, *a): print(self.command, self.path, a[1] if len(a) > 1 else '')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f'ホテル管理システム起動: http://127.0.0.1:{port}  (Ctrl+C で停止)')
    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
