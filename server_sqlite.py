#!/usr/bin/env python3
"""ホテル管理システム バックエンド (Python標準ライブラリのみ / SQLite)
起動: python3 server.py  →  http://127.0.0.1:8000
"""
import json, os, re, sqlite3
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'hotel.db')
SCHEMA = os.path.join(BASE, 'database.sql')
STATIC = {'/': 'index.html', '/index.html': 'index.html', '/style.css': 'style.css', '/app.js': 'app.js'}
TYPES = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript'}
ACTIVE = "('予約中','宿泊中')"

class Err(Exception):
    def __init__(self, msg, code=400): super().__init__(msg); self.code = code

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON'); return c

def init(reset=False):
    if reset and os.path.exists(DB):
        c = sqlite3.connect(DB)
        c.executescript('DROP VIEW IF EXISTS v_reservation_amount; DROP VIEW IF EXISTS v_monthly_sales;'
                        'DROP TABLE IF EXISTS payments; DROP TABLE IF EXISTS reservations;'
                        'DROP TABLE IF EXISTS rooms; DROP TABLE IF EXISTS customers;')
        c.executescript(open(SCHEMA, encoding='utf-8').read()); c.close()
    elif not os.path.exists(DB):
        c = sqlite3.connect(DB); c.executescript(open(SCHEMA, encoding='utf-8').read()); c.close()

def q(c, sql, *a): return [dict(r) for r in c.execute(sql, a)]

def state(c):
    return {
        'customers': q(c, 'SELECT customer_id id,name,kana,tel,email,address FROM customers ORDER BY id'),
        'rooms': q(c, 'SELECT room_id id,room_no no,room_type type,price,capacity cap FROM rooms ORDER BY no'),
        'reservations': q(c, '''SELECT r.reservation_id id,r.customer_id customerId,r.room_id roomId,r.check_in checkIn,
            r.check_out checkOut,r.guests,r.status,p.amount total,p.method,substr(p.paid_at,1,10) paidAt
            FROM reservations r LEFT JOIN payments p ON p.reservation_id=r.reservation_id ORDER BY r.reservation_id'''),
        'sales': q(c, '''SELECT p.payment_id id,substr(p.paid_at,1,10) date,p.reservation_id resId,c.name,p.method,p.amount
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
    if not r: raise Err('データが見つかりません', 404)
    return r

def check_res(c, room_id, cin, cout, guests, exclude=0):
    if not (cin and cout) or cout <= cin: raise Err('チェックアウト日はチェックイン日より後にしてください')
    cap = one(c, 'SELECT capacity FROM rooms WHERE room_id=?', room_id)[0]
    if guests < 1 or guests > cap: raise Err(f'この客室の定員は{cap}名です')
    if c.execute(f'''SELECT 1 FROM reservations WHERE room_id=? AND reservation_id<>? AND status IN {ACTIVE}
                     AND ?<check_out AND ?>check_in''', (room_id, exclude, cin, cout)).fetchone():
        raise Err('その期間は満室です')

def route(c, m, path, d):
    if m == 'GET' and path == '/state': return state(c)
    if m == 'POST' and path == '/reset': init(reset=True); return {}
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
        except sqlite3.IntegrityError as e:
            s = str(e)
            if 'UNIQUE' in s: raise Err('その部屋番号は登録済みです')
            if 'FOREIGN KEY' in s: raise Err('予約データがあるため削除できません')
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
            c.execute("UPDATE reservations SET status='宿泊中',checked_in_at=datetime('now','localtime') WHERE reservation_id=?", (i,))
        elif act == 'checkout':
            need('宿泊中', 'チェックアウトできません')
            c.execute("UPDATE reservations SET status='精算待ち',checked_out_at=datetime('now','localtime') WHERE reservation_id=?", (i,))
        elif act == 'pay':
            need('精算待ち', '精算できる状態ではありません')
            if d.get('method') not in ('現金', 'クレジットカード', '電子マネー'): raise Err('支払方法が不正です')
            n = one(c, 'SELECT CAST(julianday(?)-julianday(?) AS INTEGER)', r['check_out'], r['check_in'])[0]
            c.execute('INSERT INTO payments(reservation_id,amount,method) VALUES(?,?,?)', (i, max(1, n) * r['price'], d['method']))
            c.execute("UPDATE reservations SET status='精算済' WHERE reservation_id=?", (i,))
        else: raise Err('不正なリクエストです', 404)
        return {}
    raise Err('不正なリクエストです', 404)

class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype='application/json; charset=utf-8'):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
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
        except sqlite3.IntegrityError as e: self.send(400, {'error': str(e)})
        except Exception as e: self.send(500, {'error': 'サーバーエラー: ' + str(e)})

    do_GET = do_POST = do_PUT = do_DELETE = handle_any
    def log_message(self, f, *a): print(self.command, self.path, a[1] if len(a) > 1 else '')

if __name__ == '__main__':
    init()
    port = int(os.environ.get('PORT', 8000))
    print(f'ホテル管理システム起動: http://127.0.0.1:{port}  (Ctrl+C で停止)')
    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
