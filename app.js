'use strict';
const $ = s => document.querySelector(s);
const KEY = 'hotelSystem';
const TYPES = ['シングル', 'ダブル', 'ツイン', 'スイート'];
const ST = { '予約中': 's1', '宿泊中': 's2', '精算待ち': 's3', '精算済': '', 'キャンセル': 's4' };
const ACTIVE = ['予約中', '宿泊中'];

const seed = () => ({
  seq: 10,
  customers: [{ id: 1, name: '山田 太郎', kana: 'ヤマダ タロウ', tel: '090-1234-5678', email: 'yamada@example.jp', address: '東京都新宿区1-1-1' }],
  rooms: [
    { id: 2, no: '101', type: 'シングル', price: 8000, cap: 1 },
    { id: 3, no: '102', type: 'ダブル', price: 12000, cap: 2 },
    { id: 4, no: '201', type: 'ツイン', price: 14000, cap: 2 },
    { id: 5, no: '301', type: 'スイート', price: 30000, cap: 4 }
  ],
  reservations: [], sales: []
});
let db = JSON.parse(localStorage.getItem(KEY) || 'null') || seed();
let view = 'customers';
let roomQ = { no: '', type: '' };
let vac = { from: '', to: '' };

const save = () => localStorage.setItem(KEY, JSON.stringify(db));
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const yen = n => '¥' + Number(n).toLocaleString('ja-JP');
const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
const nights = (a, b) => Math.max(1, Math.round((new Date(b) - new Date(a)) / 864e5));
const cust = id => db.customers.find(c => c.id == id);
const room = id => db.rooms.find(r => r.id == id);
const rsv = id => db.reservations.find(r => r.id == id);
const amount = r => nights(r.checkIn, r.checkOut) * (room(r.roomId)?.price || 0);
const nextId = () => ++db.seq;
const badge = s => `<span class="badge ${ST[s]}">${s}</span>`;
function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('show'); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), 2200); }

function isFree(roomId, from, to, exceptId) {
  return !db.reservations.some(r => r.roomId == roomId && r.id != exceptId && ACTIVE.includes(r.status) && from < r.checkOut && to > r.checkIn);
}

/* ---------- ダイアログ ---------- */
function form(title, fields, vals, onOk) {
  const d = $('#dlg');
  d.innerHTML = `<form><h3>${title}</h3>${fields.map(f => `<label>${f.l}${f.t === 'select'
    ? `<select name="${f.k}">${f.o.map(o => `<option value="${esc(o[0])}" ${o[0] == vals[f.k] ? 'selected' : ''}>${esc(o[1])}</option>`).join('')}</select>`
    : `<input name="${f.k}" type="${f.t || 'text'}" value="${esc(vals[f.k])}" ${f.req ? 'required' : ''} ${f.min != null ? `min="${f.min}"` : ''}>`}</label>`).join('')}
    <div class="actions"><button type="button" class="btn ghost" id="cl">キャンセル</button><button class="btn">保存</button></div></form>`;
  $('#cl').onclick = () => d.close();
  d.querySelector('form').onsubmit = e => {
    e.preventDefault();
    if (onOk(Object.fromEntries(new FormData(e.target))) !== false) d.close();
  };
  d.showModal();
}
function info(title, html, extra = '') {
  const d = $('#dlg');
  d.innerHTML = `<div class="box"><h3>${title}</h3>${html}<div class="actions">${extra}<button class="btn ghost" id="cl">閉じる</button></div></div>`;
  $('#cl').onclick = () => d.close();
  d.showModal();
}
const dl = rows => `<dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v) || '－'}</dd>`).join('')}</dl>`;
const table = (heads, rows) => rows.length
  ? `<div class="wrap"><table><thead><tr>${heads.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`
  : '<div class="wrap"><div class="empty">データがありません</div></div>';
const btn = (a, id, label, cls = '') => `<button class="btn sm ${cls}" data-a="${a}" data-id="${id}">${label}</button>`;

/* ---------- 1. 顧客管理 ---------- */
const CF = [
  { k: 'name', l: '氏名', req: 1 }, { k: 'kana', l: 'フリガナ' }, { k: 'tel', l: '電話番号', req: 1 },
  { k: 'email', l: 'メールアドレス', t: 'email' }, { k: 'address', l: '住所' }
];
function vCustomers() {
  return `<h2>顧客管理</h2><p class="sub">顧客情報の登録・表示・更新・削除</p>
  <div class="bar"><button class="btn" data-a="cNew">顧客登録</button></div>
  ${table(['ID', '氏名', 'フリガナ', '電話番号', 'メール', ''], db.customers.map(c => `<tr><td>${c.id}</td><td>${esc(c.name)}</td><td>${esc(c.kana)}</td><td>${esc(c.tel)}</td><td>${esc(c.email)}</td>
  <td class="act">${btn('cShow', c.id, '詳細', 'ghost')}${btn('cEdit', c.id, '更新', 'ghost')}${btn('cDel', c.id, '削除', 'del')}</td></tr>`))}`;
}
/* ---------- 2. 客室管理 ---------- */
const RF = () => [
  { k: 'no', l: '部屋番号', req: 1 },
  { k: 'type', l: '部屋タイプ', t: 'select', o: TYPES.map(t => [t, t]) },
  { k: 'price', l: '1泊料金（円）', t: 'number', req: 1, min: 0 },
  { k: 'cap', l: '定員（人）', t: 'number', req: 1, min: 1 }
];
function vRooms() {
  const list = db.rooms.filter(r => r.no.includes(roomQ.no) && (!roomQ.type || r.type === roomQ.type));
  return `<h2>客室管理</h2><p class="sub">客室情報の登録・表示・更新・削除、検索</p>
  <div class="bar"><button class="btn" data-a="rNew">客室登録</button>
  <label>部屋番号<input id="qNo" value="${esc(roomQ.no)}" placeholder="例：101"></label>
  <label>部屋タイプ<select id="qType"><option value="">すべて</option>${TYPES.map(t => `<option ${t === roomQ.type ? 'selected' : ''}>${t}</option>`).join('')}</select></label></div>
  ${table(['部屋番号', 'タイプ', '料金/泊', '定員', ''], list.map(r => `<tr><td>${esc(r.no)}</td><td>${r.type}</td><td>${yen(r.price)}</td><td>${r.cap}名</td>
  <td class="act">${btn('rShow', r.id, '詳細', 'ghost')}${btn('rEdit', r.id, '更新', 'ghost')}${btn('rDel', r.id, '削除', 'del')}</td></tr>`))}`;
}
/* ---------- 3. 予約管理 ---------- */
function vReservations() {
  const free = vac.from && vac.to && vac.to > vac.from ? db.rooms.filter(r => isFree(r.id, vac.from, vac.to)) : null;
  return `<h2>予約管理</h2><p class="sub">宿泊予約の登録・表示・変更・キャンセル、空室確認</p>
  <div class="bar"><button class="btn" data-a="sNew">予約登録</button></div>
  ${table(['ID', '顧客', '客室', 'チェックイン', 'チェックアウト', '人数', '状態', ''], db.reservations.map(r => `<tr><td>${r.id}</td><td>${esc(cust(r.customerId)?.name)}</td><td>${esc(room(r.roomId)?.no)}</td><td>${r.checkIn}</td><td>${r.checkOut}</td><td>${r.guests}</td><td>${badge(r.status)}</td>
  <td class="act">${btn('sShow', r.id, '詳細', 'ghost')}${r.status === '予約中' ? btn('sEdit', r.id, '変更', 'ghost') + btn('sCancel', r.id, 'キャンセル', 'del') : ''}</td></tr>`))}
  <h3>空室確認</h3>
  <div class="bar"><label>宿泊開始日<input type="date" id="vFrom" value="${vac.from}"></label><label>宿泊終了日<input type="date" id="vTo" value="${vac.to}"></label></div>
  ${free === null ? '<div class="wrap"><div class="empty">日付を選ぶと空室が表示されます</div></div>'
      : table(['部屋番号', 'タイプ', '料金/泊', '定員'], free.map(r => `<tr><td>${esc(r.no)}</td><td>${r.type}</td><td>${yen(r.price)}</td><td>${r.cap}名</td></tr>`))}`;
}
/* ---------- 4. チェックイン・アウト ---------- */
function vCheckin() {
  const a = db.reservations.filter(r => r.status === '予約中'), b = db.reservations.filter(r => r.status === '宿泊中');
  const row = (r, act) => `<tr><td>${r.id}</td><td>${esc(cust(r.customerId)?.name)}</td><td>${esc(room(r.roomId)?.no)}</td><td>${r.checkIn}</td><td>${r.checkOut}</td><td class="act">${act}</td></tr>`;
  const H = ['予約ID', '顧客', '客室', 'チェックイン', 'チェックアウト', ''];
  return `<h2>チェックイン・アウト</h2><p class="sub">宿泊の開始と終了を登録します</p>
  <h3>チェックイン待ち</h3>${table(H, a.map(r => row(r, btn('ci', r.id, 'チェックイン'))))}
  <h3>宿泊中</h3>${table(H, b.map(r => row(r, btn('co', r.id, 'チェックアウト', 'gold'))))}`;
}
/* ---------- 5. 会計管理 ---------- */
function vAccounting() {
  const w = db.reservations.filter(r => r.status === '精算待ち'), p = db.reservations.filter(r => r.status === '精算済');
  const H = ['予約ID', '顧客', '客室', '宿泊数', '宿泊料金', ''];
  const row = (r, act) => `<tr><td>${r.id}</td><td>${esc(cust(r.customerId)?.name)}</td><td>${esc(room(r.roomId)?.no)}</td><td>${nights(r.checkIn, r.checkOut)}泊</td><td>${yen(r.total ?? amount(r))}</td><td class="act">${act}</td></tr>`;
  return `<h2>会計管理</h2><p class="sub">宿泊料金の計算、支払処理、レシート発行</p>
  <h3>精算待ち</h3>${table(H, w.map(r => row(r, btn('calc', r.id, '料金計算', 'ghost') + btn('pay', r.id, '支払処理'))))}
  <h3>精算済み</h3>${table(H, p.map(r => row(r, btn('rcpt', r.id, 'レシート発行', 'ghost'))))}`;
}
/* ---------- 6. 売上管理 ---------- */
function vSales() {
  const sum = a => a.reduce((s, x) => s + x.amount, 0), ym = today().slice(0, 7);
  const byM = {}; db.sales.forEach(s => byM[s.date.slice(0, 7)] = (byM[s.date.slice(0, 7)] || 0) + s.amount);
  return `<h2>売上管理</h2><p class="sub">ホテルの売上情報（支払処理の完了時に自動登録）</p>
  <div class="stats"><div class="stat"><b>${yen(sum(db.sales))}</b><span>総売上</span></div>
  <div class="stat"><b>${yen(sum(db.sales.filter(s => s.date.startsWith(ym))))}</b><span>今月の売上</span></div>
  <div class="stat"><b>${db.sales.length}件</b><span>会計件数</span></div></div>
  <h3>月別売上</h3>${table(['月', '売上'], Object.keys(byM).sort().reverse().map(m => `<tr><td>${m}</td><td>${yen(byM[m])}</td></tr>`))}
  <h3>売上明細</h3>${table(['日付', '予約ID', '顧客', '支払方法', '金額'], [...db.sales].reverse().map(s => `<tr><td>${s.date}</td><td>${s.resId}</td><td>${esc(s.name)}</td><td>${s.method}</td><td>${yen(s.amount)}</td></tr>`))}`;
}

const VIEWS = { customers: vCustomers, rooms: vRooms, reservations: vReservations, checkin: vCheckin, accounting: vAccounting, sales: vSales };
function render() {
  $('#main').innerHTML = VIEWS[view]();
  document.querySelectorAll('#nav button').forEach(b => b.classList.toggle('on', b.dataset.v === view));
}

/* ---------- 予約フォーム ---------- */
function resFields(edit) {
  return [
    ...(edit ? [] : [
      { k: 'customerId', l: '顧客', t: 'select', o: db.customers.map(c => [c.id, c.name]) },
      { k: 'roomId', l: '客室', t: 'select', o: db.rooms.map(r => [r.id, `${r.no}（${r.type}・定員${r.cap}名）`]) }]),
    { k: 'checkIn', l: 'チェックイン日', t: 'date', req: 1 }, { k: 'checkOut', l: 'チェックアウト日', t: 'date', req: 1 },
    { k: 'guests', l: '宿泊人数', t: 'number', req: 1, min: 1 }
  ];
}
function checkRes(d, roomId, exceptId) {
  const r = room(roomId);
  if (d.checkOut <= d.checkIn) { toast('チェックアウト日はチェックイン日より後にしてください'); return false; }
  if (+d.guests > r.cap) { toast(`この客室の定員は${r.cap}名です`); return false; }
  if (!isFree(roomId, d.checkIn, d.checkOut, exceptId)) { toast('その期間は満室です'); return false; }
  return true;
}

/* ---------- 操作 ---------- */
const A = {
  cNew: () => form('顧客登録', CF, {}, d => { db.customers.push({ id: nextId(), ...d }); save(); render(); toast('顧客を登録しました'); }),
  cShow: id => {
    const c = cust(id), h = db.reservations.filter(r => r.customerId == id).length;
    info('顧客情報', dl([['ID', c.id], ['氏名', c.name], ['フリガナ', c.kana], ['電話番号', c.tel], ['メール', c.email], ['住所', c.address], ['予約回数', h + '件']]));
  },
  cEdit: id => form('顧客情報更新', CF, cust(id), d => { Object.assign(cust(id), d); save(); render(); toast('更新しました'); }),
  cDel: id => {
    if (db.reservations.some(r => r.customerId == id && ACTIVE.includes(r.status))) return toast('有効な予約があるため削除できません');
    if (confirm('この顧客情報を削除しますか？')) { db.customers = db.customers.filter(c => c.id != id); save(); render(); toast('削除しました'); }
  },
  rNew: () => form('客室登録', RF(), { type: 'シングル', cap: 1 }, d => {
    if (db.rooms.some(r => r.no === d.no)) { toast('その部屋番号は登録済みです'); return false; }
    db.rooms.push({ id: nextId(), ...d, price: +d.price, cap: +d.cap }); save(); render(); toast('客室を登録しました');
  }),
  rShow: id => { const r = room(id); info('客室情報', dl([['部屋番号', r.no], ['タイプ', r.type], ['1泊料金', yen(r.price)], ['定員', r.cap + '名']])); },
  rEdit: id => form('客室情報更新', RF(), room(id), d => {
    if (db.rooms.some(r => r.no === d.no && r.id != id)) { toast('その部屋番号は登録済みです'); return false; }
    Object.assign(room(id), d, { price: +d.price, cap: +d.cap }); save(); render(); toast('更新しました');
  }),
  rDel: id => {
    if (db.reservations.some(r => r.roomId == id && ACTIVE.includes(r.status))) return toast('有効な予約があるため削除できません');
    if (confirm('この客室情報を削除しますか？')) { db.rooms = db.rooms.filter(r => r.id != id); save(); render(); toast('削除しました'); }
  },
  sNew: () => {
    if (!db.customers.length || !db.rooms.length) return toast('先に顧客と客室を登録してください');
    form('予約登録', resFields(), { checkIn: today(), guests: 1 }, d => {
      if (!checkRes(d, d.roomId)) return false;
      db.reservations.push({ id: nextId(), customerId: +d.customerId, roomId: +d.roomId, checkIn: d.checkIn, checkOut: d.checkOut, guests: +d.guests, status: '予約中' });
      save(); render(); toast('予約を登録しました');
    });
  },
  sShow: id => {
    const r = rsv(id);
    info('予約情報', dl([['予約ID', r.id], ['顧客', cust(r.customerId)?.name], ['客室', `${room(r.roomId)?.no}（${room(r.roomId)?.type}）`], ['チェックイン', r.checkIn], ['チェックアウト', r.checkOut], ['人数', r.guests + '名'], ['宿泊料金', yen(r.total ?? amount(r))], ['状態', r.status]]));
  },
  sEdit: id => { const r = rsv(id); form('予約情報更新（日付・人数）', resFields(true), r, d => {
    if (!checkRes(d, r.roomId, id)) return false;
    Object.assign(r, { checkIn: d.checkIn, checkOut: d.checkOut, guests: +d.guests }); save(); render(); toast('予約を変更しました');
  }); },
  sCancel: id => { if (confirm('この予約をキャンセルしますか？')) { rsv(id).status = 'キャンセル'; save(); render(); toast('予約をキャンセルしました'); } },
  ci: id => { rsv(id).status = '宿泊中'; rsv(id).inAt = today(); save(); render(); toast('チェックインを登録しました'); },
  co: id => { rsv(id).status = '精算待ち'; rsv(id).outAt = today(); save(); render(); toast('チェックアウトを登録しました'); },
  calc: id => {
    const r = rsv(id), rm = room(r.roomId), n = nights(r.checkIn, r.checkOut);
    info('宿泊料金計算', dl([['客室', `${rm.no}（${rm.type}）`], ['1泊料金', yen(rm.price)], ['宿泊日数', n + '泊'], ['合計', yen(n * rm.price)]]));
  },
  pay: id => {
    const r = rsv(id);
    form(`会計処理（${yen(amount(r))}）`, [{ k: 'method', l: '支払方法', t: 'select', o: ['現金', 'クレジットカード', '電子マネー'].map(x => [x, x]) }], {}, d => {
      r.total = amount(r); r.method = d.method; r.paidAt = today(); r.status = '精算済';
      db.sales.push({ id: nextId(), date: today(), resId: r.id, name: cust(r.customerId)?.name || '', method: d.method, amount: r.total });
      save(); render(); toast('支払を処理しました'); A.rcpt(id);
    });
  },
  rcpt: id => {
    const r = rsv(id), rm = room(r.roomId), n = nights(r.checkIn, r.checkOut);
    info('レシート', `<div class="receipt"><h3>ホテル管理システム</h3><hr>
    ${dl([['発行日', r.paidAt], ['お客様', (cust(r.customerId)?.name || '') + ' 様'], ['客室', `${rm.no}（${rm.type}）`], ['宿泊期間', `${r.checkIn} ～ ${r.checkOut}`], ['単価', yen(rm.price)], ['宿泊数', n + '泊'], ['支払方法', r.method]])}
    <hr><div class="tot">合計 ${yen(r.total)}</div></div>`, '<button class="btn" onclick="window.print()">印刷</button>');
  }
};

/* ---------- イベント ---------- */
document.addEventListener('click', e => {
  const b = e.target.closest('[data-a]');
  if (b) A[b.dataset.a](+b.dataset.id || undefined);
});
$('#nav').onclick = e => { const v = e.target.dataset.v; if (v) { view = v; render(); } };
$('#main').addEventListener('input', e => {
  if (e.target.id === 'qNo') { roomQ.no = e.target.value; render(); const i = $('#qNo'); i.focus(); i.setSelectionRange(99, 99); }
});
$('#main').addEventListener('change', e => {
  const t = e.target.id;
  if (t === 'qType') { roomQ.type = e.target.value; render(); }
  if (t === 'vFrom') { vac.from = e.target.value; render(); }
  if (t === 'vTo') { vac.to = e.target.value; render(); }
});
$('#reset').onclick = () => { if (confirm('すべてのデータを初期化しますか？')) { db = seed(); save(); render(); toast('初期化しました'); } };
render();