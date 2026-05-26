"""
AutoDetail Pro — Система управления автомойкой
Роли:
  client   — обычный пользователь: просматривает услуги, создаёт бронирование
  operator — сотрудник: управляет заказами/клиентами/авто, не может удалять и видеть финансы
  admin    — полный доступ: всё включая удаление, финансы, управление пользователями
"""
import sqlite3
import hashlib
import os
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session)

# ── Пути ─────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(BASE_DIR, 'carwash_2026.db')
TMPL_DIR  = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=TMPL_DIR, static_folder=STATIC_DIR)
app.secret_key = 'carwash_autodetail_2026_secret'


def hash_pwd(p):
    return hashlib.sha256(p.encode('utf-8')).hexdigest()


# ── БД ────────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def recalc(order_id):
    db = get_db()
    db.execute("""UPDATE Заказы SET итого=(
        SELECT COALESCE(SUM(количество*цена_на_момент),0)
        FROM Состав_заказа WHERE заказ_id=Заказы.id) WHERE id=?""", (order_id,))
    db.commit()
    db.close()


def init_db():
    db  = get_db()
    cur = db.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS Пользователи (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        логин      TEXT NOT NULL UNIQUE,
        хэш        TEXT NOT NULL,
        имя        TEXT NOT NULL,
        роль       TEXT NOT NULL DEFAULT 'client',
        дата_рег   TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS Услуги (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        название   TEXT NOT NULL UNIQUE,
        цена       REAL NOT NULL,
        категория  TEXT,
        время_мин  INTEGER NOT NULL DEFAULT 30,
        описание   TEXT
    );
    CREATE TABLE IF NOT EXISTS Клиенты (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        телефон         TEXT UNIQUE NOT NULL,
        фио             TEXT NOT NULL,
        скидка_процент  INTEGER DEFAULT 0,
        пользователь_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS Автомобили (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        клиент_id  INTEGER NOT NULL,
        марка      TEXT NOT NULL,
        модель     TEXT,
        госномер   TEXT NOT NULL,
        цвет       TEXT,
        FOREIGN KEY (клиент_id) REFERENCES Клиенты(id),
        UNIQUE (клиент_id, госномер)
    );
    CREATE TABLE IF NOT EXISTS Заказы (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        клиент_id         INTEGER,
        автомобиль_id     INTEGER NOT NULL,
        дата_создания     TEXT NOT NULL,
        планируемая_дата  TEXT,
        статус            TEXT DEFAULT 'Новый',
        итого             REAL DEFAULT 0,
        оплачено          REAL DEFAULT 0,
        способ_оплаты     TEXT,
        комментарий       TEXT,
        FOREIGN KEY (клиент_id)     REFERENCES Клиенты(id),
        FOREIGN KEY (автомобиль_id) REFERENCES Автомобили(id)
    );
    CREATE TABLE IF NOT EXISTS Состав_заказа (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        заказ_id       INTEGER NOT NULL,
        услуга_id      INTEGER NOT NULL,
        количество     INTEGER DEFAULT 1,
        цена_на_момент REAL NOT NULL,
        FOREIGN KEY (заказ_id)  REFERENCES Заказы(id) ON DELETE CASCADE,
        FOREIGN KEY (услуга_id) REFERENCES Услуги(id)
    );
    """)

    # Пользователи по умолчанию
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur.execute("SELECT COUNT(*) FROM Пользователи")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO Пользователи (логин,хэш,имя,роль,дата_рег) VALUES(?,?,?,?,?)",
            [
                ('admin',    hash_pwd('admin123'), 'Администратор',  'admin',    now),
                ('operator', hash_pwd('oper1234'), 'Оператор',       'operator', now),
                ('client',   hash_pwd('client12'), 'Клиент Пример',  'client',   now),
            ])

    # Услуги
    cur.execute("SELECT COUNT(*) FROM Услуги")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO Услуги (название,цена,категория,время_мин,описание) VALUES(?,?,?,?,?)",
            [
                ("Мойка кузова стандарт", 750,  "кузов",    20, "Полная мойка кузова, колёс и стёкол"),
                ("Мойка + воск",         1200,  "кузов",    35, "Мойка кузова с нанесением защитного воска"),
                ("Чернение резины",       500,  "кузов",    15, "Чернение и полировка резины всех колёс"),
                ("Химчистка салона",     4200,  "салон",    90, "Полная химчистка обивки, ковров и панели"),
                ("Комплекс Премиум",     6800,  "комплекс",150, "Мойка кузова + воск + химчистка салона"),
                ("Мойка двигателя",      1500,  "доп",      45, "Мойка моторного отсека с обезжириванием"),
                ("Антидождь (стёкла)",    950,  "доп",      25, "Нанесение гидрофобного покрытия на стёкла"),
            ])

    # Клиенты
    cur.execute("SELECT COUNT(*) FROM Клиенты")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO Клиенты (телефон,фио,скидка_процент) VALUES(?,?,?)",
            [
                ("+79161234567", "Кочанов Александр Викторович", 10),
                ("+79252345678", "Кравцова Ольга Сергеевна",      0),
                ("+79033456789", "Пономарёв Дмитрий Андреевич",   5),
                ("+79264567890", "Соколова Екатерина Михайловна", 0),
            ])

    # Автомобили
    cur.execute("SELECT COUNT(*) FROM Автомобили")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id FROM Клиенты ORDER BY id LIMIT 4")
        cids = [r[0] for r in cur.fetchall()]
        cur.executemany(
            "INSERT INTO Автомобили (клиент_id,марка,модель,госномер,цвет) VALUES(?,?,?,?,?)",
            [
                (cids[0], "Toyota",  "Camry",    "А123ВС 777", "чёрный"),
                (cids[1], "BMW",     "X5",        "О456МР 199", "белый"),
                (cids[2], "Kia",     "Sportage",  "К789АН 777", "серый"),
                (cids[3], "Hyundai", "Tucson",    "Е112КО 777", "синий"),
            ])

    # Демо-заказы
    cur.execute("SELECT COUNT(*) FROM Заказы")
    if cur.fetchone()[0] == 0:
        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur.execute("SELECT id FROM Автомобили ORDER BY id LIMIT 4")
        aids = [r[0] for r in cur.fetchall()]
        cur.executemany(
            """INSERT INTO Заказы
               (клиент_id,автомобиль_id,дата_создания,планируемая_дата,статус,итого,способ_оплаты,комментарий)
               VALUES(?,?,?,?,?,?,?,?)""",
            [
                (1, aids[0], today, today,  "В работе",     1950, "Карта",    "Срочно"),
                (2, aids[1], today, None,   "Новый",        6800, "СБП",      None),
                (3, aids[2], today, None,   "Готов",        4700, "Наличные", None),
                (4, aids[3], today, today,  "Запланировано",1200, None,       "На 14:00 завтра"),
            ])
        db.commit()
        cur.execute("SELECT id FROM Заказы ORDER BY id DESC LIMIT 4")
        oids = [r[0] for r in cur.fetchall()][::-1]
        cur.executemany(
            "INSERT INTO Состав_заказа (заказ_id,услуга_id,количество,цена_на_момент) VALUES(?,?,?,?)",
            [
                (oids[0],1,1, 750),(oids[0],3,1, 500),
                (oids[1],5,1,6800),
                (oids[2],4,1,4200),(oids[2],7,1, 950),
                (oids[3],2,1,1200),
            ])
        for oid in oids:
            cur.execute("""UPDATE Заказы SET итого=(
                SELECT COALESCE(SUM(количество*цена_на_момент),0)
                FROM Состав_заказа WHERE заказ_id=Заказы.id) WHERE id=?""", (oid,))

    db.commit()
    db.close()


# ── Декораторы ────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if 'uid' not in session:
            flash('Войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*a, **kw)
    return w

def role_required(*roles):
    """Доступ только для перечисленных ролей."""
    def decorator(f):
        @wraps(f)
        def w(*a, **kw):
            if 'uid' not in session:
                flash('Войдите в систему', 'warning')
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash('Недостаточно прав для этого действия', 'danger')
                return redirect(url_for('index'))
            return f(*a, **kw)
        return w
    return decorator


@app.context_processor
def inject_user():
    return {
        'cu_name': session.get('name', ''),
        'cu_role': session.get('role', ''),
        'cu_login': session.get('login', ''),
    }

def is_admin():     return session.get('role') == 'admin'
def is_operator():  return session.get('role') in ('admin', 'operator')
def is_client():    return session.get('role') == 'client'

app.jinja_env.globals.update(is_admin=is_admin, is_operator=is_operator, is_client=is_client)


# ── Авторизация ───────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'uid' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        login_ = request.form.get('username', '').strip()
        pwd    = request.form.get('password', '')
        db     = get_db()
        u      = db.execute("SELECT * FROM Пользователи WHERE логин=?", (login_,)).fetchone()
        db.close()
        if u and u['хэш'] == hash_pwd(pwd):
            session['uid']   = u['id']
            session['login'] = u['логин']
            session['role']  = u['роль']
            session['name']  = u['имя']
            flash(f'Добро пожаловать, {u["имя"]}!', 'success')
            # Клиент → страница бронирования, остальные → дашборд
            return redirect(url_for('booking') if u['роль'] == 'client' else url_for('index'))
        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'uid' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        login_ = request.form.get('username', '').strip()
        name   = request.form.get('name', '').strip()
        phone  = request.form.get('phone', '').strip()
        pwd    = request.form.get('password', '')
        pwd2   = request.form.get('password2', '')
        errors = []
        if len(login_) < 3: errors.append('Логин — минимум 3 символа')
        if len(name)  < 2:  errors.append('Введите имя')
        if len(pwd)   < 4:  errors.append('Пароль — минимум 4 символа')
        if pwd != pwd2:      errors.append('Пароли не совпадают')
        if errors:
            for e in errors: flash(e, 'danger')
            return render_template('register.html',
                                   form={'username':login_,'name':name,'phone':phone})
        db = get_db()
        if db.execute("SELECT id FROM Пользователи WHERE логин=?", (login_,)).fetchone():
            flash('Логин уже занят', 'danger')
            db.close()
            return render_template('register.html',
                                   form={'username':login_,'name':name,'phone':phone})
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur = db.cursor()
        cur.execute(
            "INSERT INTO Пользователи (логин,хэш,имя,роль,дата_рег) VALUES(?,?,?,?,?)",
            (login_, hash_pwd(pwd), name, 'client', now))
        uid = cur.lastrowid
        # Автоматически создаём запись клиента если указан телефон
        if phone:
            try:
                cur.execute(
                    "INSERT INTO Клиенты (телефон,фио,скидка_процент,пользователь_id) VALUES(?,?,0,?)",
                    (phone, name, uid))
            except Exception:
                pass
        db.commit()
        db.close()
        flash('Аккаунт создан! Войдите в систему', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form={})


# ── Главная / дашборд ─────────────────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    # Клиент видит только свою страницу бронирования
    if is_client():
        return redirect(url_for('booking'))
    db = get_db()
    stats = {
        'new_orders':    db.execute("SELECT COUNT(*) FROM Заказы WHERE статус='Новый'").fetchone()[0],
        'inwork_orders': db.execute("SELECT COUNT(*) FROM Заказы WHERE статус='В работе'").fetchone()[0],
        'ready_orders':  db.execute("SELECT COUNT(*) FROM Заказы WHERE статус='Готов'").fetchone()[0],
        'clients_cnt':   db.execute("SELECT COUNT(*) FROM Клиенты").fetchone()[0],
        'vehicles_cnt':  db.execute("SELECT COUNT(*) FROM Автомобили").fetchone()[0],
        'services_cnt':  db.execute("SELECT COUNT(*) FROM Услуги").fetchone()[0],
    }
    if is_admin():
        stats['revenue'] = db.execute("SELECT COALESCE(SUM(итого),0) FROM Заказы").fetchone()[0]
    recent = db.execute("""
        SELECT z.id, cl.фио, a.марка||' '||a.модель AS авто,
               z.статус, z.итого, z.дата_создания
        FROM Заказы z
        JOIN Клиенты cl ON z.клиент_id=cl.id
        JOIN Автомобили a ON z.автомобиль_id=a.id
        ORDER BY z.id DESC LIMIT 5""").fetchall()
    db.close()
    return render_template('index.html', **stats, recent=recent)


# ═══════════════════════════════════════════════════════════════════════════════
# КЛИЕНТСКАЯ ЧАСТЬ — бронирование
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/booking')
@login_required
def booking():
    db   = get_db()
    svcs = db.execute("SELECT * FROM Услуги ORDER BY категория, цена").fetchall()
    # Найдём клиента привязанного к этому пользователю
    my_client = db.execute(
        "SELECT * FROM Клиенты WHERE пользователь_id=?", (session['uid'],)).fetchone()
    my_orders = []
    if my_client:
        my_orders = db.execute("""
            SELECT z.id, z.статус, z.итого, z.дата_создания, z.планируемая_дата,
                   z.комментарий, a.марка||' '||a.модель AS авто, a.госномер
            FROM Заказы z
            JOIN Автомобили a ON z.автомобиль_id=a.id
            WHERE z.клиент_id=?
            ORDER BY z.id DESC""", (my_client['id'],)).fetchall()
    db.close()
    return render_template('booking.html', services=svcs,
                           my_client=my_client, my_orders=my_orders)


@app.route('/booking/request', methods=['POST'])
@login_required
def booking_request():
    """Клиент заполняет форму бронирования."""
    db      = get_db()
    cur     = db.cursor()
    name    = request.form.get('name', '').strip()
    phone   = request.form.get('phone', '').strip()
    car     = request.form.get('car', '').strip()
    госномер = request.form.get('госномер', '').strip()
    plan_date = request.form.get('план_дата', '').strip() or None
    comment  = request.form.get('комментарий', '').strip()
    svc_ids  = request.form.getlist('services')

    if not name or not phone or not car or not госномер or not svc_ids:
        flash('Заполните все обязательные поля и выберите хотя бы одну услугу', 'danger')
        db.close()
        return redirect(url_for('booking'))

    # Клиент в БД
    client = cur.execute("SELECT * FROM Клиенты WHERE пользователь_id=?", (session['uid'],)).fetchone()
    if not client:
        # Создаём
        try:
            cur.execute(
                "INSERT INTO Клиенты (телефон,фио,скидка_процент,пользователь_id) VALUES(?,?,0,?)",
                (phone, name, session['uid']))
            db.commit()
            client = cur.execute("SELECT * FROM Клиенты WHERE пользователь_id=?", (session['uid'],)).fetchone()
        except Exception:
            # Телефон уже занят — привязываем существующего
            client = cur.execute("SELECT * FROM Клиенты WHERE телефон=?", (phone,)).fetchone()
            if client:
                cur.execute("UPDATE Клиенты SET пользователь_id=? WHERE id=?", (session['uid'], client['id']))
                db.commit()
            else:
                flash('Ошибка создания профиля клиента. Обратитесь к оператору.', 'danger')
                db.close()
                return redirect(url_for('booking'))

    # Автомобиль
    марка_модель = car.split(' ', 1)
    марка = марка_модель[0]
    модель = марка_модель[1] if len(марка_модель) > 1 else ''
    auto = cur.execute(
        "SELECT id FROM Автомобили WHERE клиент_id=? AND госномер=?",
        (client['id'], госномер)).fetchone()
    if not auto:
        cur.execute(
            "INSERT INTO Автомобили (клиент_id,марка,модель,госномер) VALUES(?,?,?,?)",
            (client['id'], марка, модель, госномер))
        db.commit()
        auto = cur.execute(
            "SELECT id FROM Автомобили WHERE клиент_id=? AND госномер=?",
            (client['id'], госномер)).fetchone()

    # Заказ
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur.execute("""INSERT INTO Заказы
        (клиент_id,автомобиль_id,дата_создания,планируемая_дата,статус,комментарий)
        VALUES(?,?,?,?,'Новый',?)""",
        (client['id'], auto['id'], now, plan_date, comment))
    db.commit()
    oid = cur.lastrowid

    # Услуги
    total = 0
    for sid in svc_ids:
        svc = cur.execute("SELECT цена FROM Услуги WHERE id=?", (sid,)).fetchone()
        if svc:
            cur.execute(
                "INSERT INTO Состав_заказа (заказ_id,услуга_id,количество,цена_на_момент) VALUES(?,?,1,?)",
                (oid, sid, svc['цена']))
            total += svc['цена']
    cur.execute("UPDATE Заказы SET итого=? WHERE id=?", (total, oid))
    db.commit()
    db.close()
    flash(f'✅ Бронирование №{oid} принято! Наш оператор свяжется с вами.', 'success')
    return redirect(url_for('booking'))


# ═══════════════════════════════════════════════════════════════════════════════
# УСЛУГИ
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/services')
@role_required('admin', 'operator')
def services():
    db   = get_db()
    svcs = db.execute("SELECT * FROM Услуги ORDER BY категория, название").fetchall()
    db.close()
    return render_template('services.html', services=svcs)


@app.route('/services/new', methods=['GET', 'POST'])
@role_required('admin')
def service_new():
    if request.method == 'POST':
        db = get_db()
        try:
            db.execute(
                "INSERT INTO Услуги (название,цена,категория,время_мин,описание) VALUES(?,?,?,?,?)",
                (request.form['название'], float(request.form['цена']),
                 request.form.get('категория',''), int(request.form['время_мин']),
                 request.form.get('описание','')))
            db.commit()
            flash('Услуга добавлена', 'success')
        except sqlite3.IntegrityError:
            flash('Услуга с таким названием уже существует', 'danger')
        db.close()
        return redirect(url_for('services'))
    return render_template('service_form.html', title='Новая услуга', s=None)


@app.route('/services/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def service_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute(
            "UPDATE Услуги SET название=?,цена=?,категория=?,время_мин=?,описание=? WHERE id=?",
            (request.form['название'], float(request.form['цена']),
             request.form.get('категория',''), int(request.form['время_мин']),
             request.form.get('описание',''), id))
        db.commit()
        flash('Услуга обновлена', 'success')
        db.close()
        return redirect(url_for('services'))
    s = db.execute("SELECT * FROM Услуги WHERE id=?", (id,)).fetchone()
    db.close()
    return render_template('service_form.html', title='Редактировать услугу', s=s)


@app.route('/services/<int:id>/delete')
@role_required('admin')
def service_delete(id):
    db = get_db()
    db.execute("DELETE FROM Услуги WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Услуга удалена', 'success')
    return redirect(url_for('services'))


# ═══════════════════════════════════════════════════════════════════════════════
# КЛИЕНТЫ
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/clients')
@role_required('admin', 'operator')
def clients():
    db  = get_db()
    cls = db.execute("SELECT * FROM Клиенты ORDER BY фио").fetchall()
    db.close()
    return render_template('clients.html', clients=cls)


@app.route('/clients/new', methods=['GET', 'POST'])
@role_required('admin', 'operator')
def client_new():
    if request.method == 'POST':
        db = get_db()
        try:
            db.execute(
                "INSERT INTO Клиенты (телефон,фио,скидка_процент) VALUES(?,?,?)",
                (request.form['телефон'], request.form['фио'],
                 int(request.form.get('скидка_процент', 0))))
            db.commit()
            flash('Клиент добавлен', 'success')
        except sqlite3.IntegrityError:
            flash('Клиент с таким телефоном уже существует', 'danger')
        db.close()
        return redirect(url_for('clients'))
    return render_template('client_form.html', title='Новый клиент', c=None)


@app.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin', 'operator')
def client_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute(
            "UPDATE Клиенты SET телефон=?,фио=?,скидка_процент=? WHERE id=?",
            (request.form['телефон'], request.form['фио'],
             int(request.form.get('скидка_процент', 0)), id))
        db.commit()
        flash('Клиент обновлён', 'success')
        db.close()
        return redirect(url_for('clients'))
    cl = db.execute("SELECT * FROM Клиенты WHERE id=?", (id,)).fetchone()
    db.close()
    return render_template('client_form.html', title='Редактировать клиента', c=cl)


@app.route('/clients/<int:id>/delete')
@role_required('admin')
def client_delete(id):
    db  = get_db()
    cnt = db.execute("SELECT COUNT(*) FROM Автомобили WHERE клиент_id=?", (id,)).fetchone()[0]
    if cnt:
        flash('Сначала удалите автомобили этого клиента', 'danger')
    else:
        db.execute("DELETE FROM Клиенты WHERE id=?", (id,))
        db.commit()
        flash('Клиент удалён', 'success')
    db.close()
    return redirect(url_for('clients'))


# ═══════════════════════════════════════════════════════════════════════════════
# АВТОМОБИЛИ
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/vehicles')
@role_required('admin', 'operator')
def vehicles():
    db = get_db()
    vs = db.execute("""SELECT a.*, cl.фио AS владелец
        FROM Автомобили a JOIN Клиенты cl ON a.клиент_id=cl.id
        ORDER BY cl.фио, a.марка""").fetchall()
    db.close()
    return render_template('vehicles.html', vehicles=vs)


@app.route('/vehicles/new', methods=['GET', 'POST'])
@role_required('admin', 'operator')
def vehicle_new():
    db  = get_db()
    cls = db.execute("SELECT id,фио FROM Клиенты ORDER BY фио").fetchall()
    if request.method == 'POST':
        try:
            db.execute(
                "INSERT INTO Автомобили (клиент_id,марка,модель,госномер,цвет) VALUES(?,?,?,?,?)",
                (int(request.form['клиент_id']), request.form['марка'],
                 request.form.get('модель',''), request.form['госномер'],
                 request.form.get('цвет','')))
            db.commit()
            flash('Автомобиль добавлен', 'success')
        except sqlite3.IntegrityError:
            flash('Такой госномер уже есть у этого клиента', 'danger')
        db.close()
        return redirect(url_for('vehicles'))
    db.close()
    return render_template('vehicle_form.html', title='Новый автомобиль', v=None, clients=cls)


@app.route('/vehicles/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin', 'operator')
def vehicle_edit(id):
    db  = get_db()
    cls = db.execute("SELECT id,фио FROM Клиенты ORDER BY фио").fetchall()
    if request.method == 'POST':
        try:
            db.execute(
                "UPDATE Автомобили SET клиент_id=?,марка=?,модель=?,госномер=?,цвет=? WHERE id=?",
                (int(request.form['клиент_id']), request.form['марка'],
                 request.form.get('модель',''), request.form['госномер'],
                 request.form.get('цвет',''), id))
            db.commit()
            flash('Автомобиль обновлён', 'success')
        except sqlite3.IntegrityError:
            flash('Конфликт госномера', 'danger')
        db.close()
        return redirect(url_for('vehicles'))
    veh = db.execute("SELECT * FROM Автомобили WHERE id=?", (id,)).fetchone()
    db.close()
    return render_template('vehicle_form.html', title='Редактировать автомобиль', v=veh, clients=cls)


@app.route('/vehicles/<int:id>/delete')
@role_required('admin')
def vehicle_delete(id):
    db  = get_db()
    cnt = db.execute("SELECT COUNT(*) FROM Заказы WHERE автомобиль_id=?", (id,)).fetchone()[0]
    if cnt:
        flash('Нельзя удалить автомобиль с заказами', 'danger')
    else:
        db.execute("DELETE FROM Автомобили WHERE id=?", (id,))
        db.commit()
        flash('Автомобиль удалён', 'success')
    db.close()
    return redirect(url_for('vehicles'))


# ═══════════════════════════════════════════════════════════════════════════════
# ЗАКАЗЫ
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/orders')
@role_required('admin', 'operator')
def orders():
    db = get_db()
    os_ = db.execute("""
        SELECT z.id, cl.фио, a.марка||' '||a.модель AS авто,
               z.статус, z.итого, z.оплачено, z.способ_оплаты, z.дата_создания
        FROM Заказы z
        JOIN Клиенты cl ON z.клиент_id=cl.id
        JOIN Автомобили a ON z.автомобиль_id=a.id
        ORDER BY z.id DESC""").fetchall()
    db.close()
    return render_template('orders.html', orders=os_)


@app.route('/orders/new', methods=['GET', 'POST'])
@role_required('admin', 'operator')
def order_new():
    db  = get_db()
    cls = db.execute("SELECT id,фио FROM Клиенты ORDER BY фио").fetchall()
    vs  = db.execute("""SELECT a.id,a.марка,a.модель,a.госномер,cl.фио,a.клиент_id
        FROM Автомобили a JOIN Клиенты cl ON a.клиент_id=cl.id
        ORDER BY cl.фио""").fetchall()
    if request.method == 'POST':
        vid = request.form.get('автомобиль_id')
        cid = request.form.get('клиент_id')
        if not vid:
            flash('Выберите автомобиль', 'danger')
            db.close()
            return render_template('order_form.html', title='Новый заказ', clients=cls, vehicles=vs)
        now  = datetime.now().strftime("%Y-%m-%d %H:%M")
        plan = request.form.get('планируемая_дата') or None
        cur  = db.cursor()
        cur.execute("""INSERT INTO Заказы
            (клиент_id,автомобиль_id,дата_создания,планируемая_дата,статус,способ_оплаты,комментарий)
            VALUES(?,?,?,?,?,?,?)""",
            (cid, vid, now, plan, request.form.get('статус','Новый'),
             request.form.get('способ_оплаты',''), request.form.get('комментарий','')))
        oid = cur.lastrowid
        db.commit()
        db.close()
        flash('Заказ создан', 'success')
        return redirect(url_for('order_detail', id=oid))
    db.close()
    return render_template('order_form.html', title='Новый заказ', clients=cls, vehicles=vs)


@app.route('/orders/<int:id>')
@role_required('admin', 'operator')
def order_detail(id):
    db    = get_db()
    o     = db.execute("""
        SELECT z.*, cl.фио AS клиент_фио, a.марка, a.модель, a.госномер
        FROM Заказы z
        JOIN Клиенты cl ON z.клиент_id=cl.id
        JOIN Автомобили a ON z.автомобиль_id=a.id
        WHERE z.id=?""", (id,)).fetchone()
    if not o:
        flash('Заказ не найден', 'danger')
        return redirect(url_for('orders'))
    items = db.execute("""
        SELECT sz.id, u.название, sz.количество, sz.цена_на_момент,
               sz.количество*sz.цена_на_момент AS сумма
        FROM Состав_заказа sz JOIN Услуги u ON sz.услуга_id=u.id
        WHERE sz.заказ_id=? ORDER BY sz.id""", (id,)).fetchall()
    svcs  = db.execute("SELECT id,название,цена FROM Услуги ORDER BY название").fetchall()
    db.close()
    return render_template('order_detail.html', order=o, items=items, services=svcs)


@app.route('/orders/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin', 'operator')
def order_edit(id):
    db = get_db()
    if request.method == 'POST':
        # Оператор не может редактировать финансы
        оплачено     = float(request.form.get('оплачено', 0) or 0) if is_admin() else None
        способ       = request.form.get('способ_оплаты','') if is_admin() else None
        if is_admin():
            db.execute("""UPDATE Заказы SET статус=?,оплачено=?,способ_оплаты=?,
                          комментарий=?,планируемая_дата=? WHERE id=?""",
                       (request.form['статус'], оплачено, способ,
                        request.form.get('комментарий',''),
                        request.form.get('планируемая_дата') or None, id))
        else:
            db.execute("""UPDATE Заказы SET статус=?,комментарий=?,планируемая_дата=? WHERE id=?""",
                       (request.form['статус'],
                        request.form.get('комментарий',''),
                        request.form.get('планируемая_дата') or None, id))
        db.commit()
        flash('Заказ обновлён', 'success')
        db.close()
        return redirect(url_for('order_detail', id=id))
    o = db.execute("SELECT * FROM Заказы WHERE id=?", (id,)).fetchone()
    db.close()
    return render_template('order_edit.html', order=o)


@app.route('/orders/<int:id>/add_service', methods=['POST'])
@role_required('admin', 'operator')
def order_add_service(id):
    sid = request.form.get('service_id')
    qty = int(request.form.get('quantity', 1))
    db  = get_db()
    row = db.execute("SELECT цена FROM Услуги WHERE id=?", (sid,)).fetchone()
    if row:
        db.execute(
            "INSERT INTO Состав_заказа (заказ_id,услуга_id,количество,цена_на_момент) VALUES(?,?,?,?)",
            (id, sid, qty, row[0]))
        db.commit()
    db.close()
    recalc(id)
    return redirect(url_for('order_detail', id=id))


@app.route('/orders/remove_item/<int:item_id>')
@role_required('admin', 'operator')
def order_remove_item(item_id):
    db  = get_db()
    row = db.execute("SELECT заказ_id FROM Состав_заказа WHERE id=?", (item_id,)).fetchone()
    if row:
        oid = row[0]
        db.execute("DELETE FROM Состав_заказа WHERE id=?", (item_id,))
        db.commit()
        db.close()
        recalc(oid)
        return redirect(url_for('order_detail', id=oid))
    db.close()
    return redirect(url_for('orders'))


@app.route('/orders/<int:id>/delete')
@role_required('admin')
def order_delete(id):
    db = get_db()
    db.execute("DELETE FROM Заказы WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Заказ удалён', 'success')
    return redirect(url_for('orders'))


# ═══════════════════════════════════════════════════════════════════════════════
# ОТЧЁТЫ
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/reports')
@role_required('admin', 'operator')
def reports():
    db = get_db()
    today_date = datetime.now().strftime("%Y-%m-%d")

    top_client = db.execute("""
        SELECT cl.фио AS Клиент, cl.телефон AS Телефон,
               COUNT(DISTINCT z.id) AS Заказов,
               SUM(sz.количество*sz.цена_на_момент) AS Итого_руб
        FROM Клиенты cl
        JOIN Заказы z ON z.клиент_id=cl.id
        JOIN Состав_заказа sz ON sz.заказ_id=z.id
        GROUP BY cl.id ORDER BY Итого_руб DESC LIMIT 1""").fetchone()

    today_washes = db.execute("""
        SELECT z.id AS №_заказа, cl.фио AS Клиент,
               a.марка||' '||a.модель AS Авто, a.госномер AS Госномер,
               u.название AS Услуга, sz.цена_на_момент AS Цена, z.статус AS Статус
        FROM Заказы z
        JOIN Клиенты cl ON z.клиент_id=cl.id
        JOIN Автомобили a ON z.автомобиль_id=a.id
        JOIN Состав_заказа sz ON sz.заказ_id=z.id
        JOIN Услуги u ON u.id=sz.услуга_id
        WHERE DATE(z.дата_создания)=?
        ORDER BY z.id, sz.id""", (today_date,)).fetchall()
    total_today = sum(r['Цена'] for r in today_washes) if today_washes else 0

    least_washed = db.execute("""
        SELECT a.марка||' '||a.модель AS Авто, a.госномер AS Госномер,
               cl.фио AS Владелец, COUNT(z.id) AS Моек_в_году
        FROM Автомобили a JOIN Клиенты cl ON cl.id=a.клиент_id
        LEFT JOIN Заказы z ON z.автомобиль_id=a.id
            AND strftime('%Y',z.дата_создания)=strftime('%Y','now')
        GROUP BY a.id ORDER BY Моек_в_году ASC, a.id ASC LIMIT 1""").fetchone()

    by_cat = db.execute("""
        SELECT u.категория, SUM(sz.количество*sz.цена_на_момент) AS выручка
        FROM Состав_заказа sz JOIN Услуги u ON u.id=sz.услуга_id
        GROUP BY u.категория ORDER BY выручка DESC""").fetchall()

    db.close()
    return render_template('reports.html',
        top_client=top_client, today_washes=today_washes,
        total_today=total_today, today_date=today_date,
        least_washed=least_washed, by_cat=by_cat)


# ═══════════════════════════════════════════════════════════════════════════════
# ПАНЕЛЬ АДМИНИСТРАТОРА
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/admin')
@role_required('admin')
def admin_panel():
    db            = get_db()
    all_orders    = db.execute("""
        SELECT z.id, cl.фио, a.марка||' '||a.модель AS авто,
               z.статус, z.итого, z.оплачено, z.дата_создания
        FROM Заказы z
        JOIN Клиенты cl ON z.клиент_id=cl.id
        JOIN Автомобили a ON z.автомобиль_id=a.id
        ORDER BY z.id DESC""").fetchall()
    total_revenue = db.execute("SELECT COALESCE(SUM(итого),0) FROM Заказы").fetchone()[0]
    total_paid    = db.execute("SELECT COALESCE(SUM(оплачено),0) FROM Заказы").fetchone()[0]
    users         = db.execute(
        "SELECT id,логин,имя,роль,дата_рег FROM Пользователи ORDER BY роль,id").fetchall()
    db.close()
    return render_template('admin.html', orders=all_orders,
        total_revenue=total_revenue, total_paid=total_paid, users=users)


@app.route('/admin/users/<int:uid>/setrole/<role>')
@role_required('admin')
def user_setrole(uid, role):
    if role not in ('admin','operator','client'):
        flash('Неверная роль', 'danger')
        return redirect(url_for('admin_panel'))
    db     = get_db()
    target = db.execute("SELECT логин FROM Пользователи WHERE id=?", (uid,)).fetchone()
    if target and target['логин'] != session['login']:
        db.execute("UPDATE Пользователи SET роль=? WHERE id=?", (role, uid))
        db.commit()
        flash(f'Роль «{target["логин"]}» → «{role}»', 'success')
    else:
        flash('Нельзя изменить роль самому себе', 'danger')
    db.close()
    return redirect(url_for('admin_panel'))


@app.route('/admin/users/<int:uid>/delete')
@role_required('admin')
def user_delete(uid):
    db     = get_db()
    target = db.execute("SELECT логин FROM Пользователи WHERE id=?", (uid,)).fetchone()
    if target and target['логин'] != session['login']:
        db.execute("DELETE FROM Пользователи WHERE id=?", (uid,))
        db.commit()
        flash(f'Пользователь «{target["логин"]}» удалён', 'success')
    else:
        flash('Нельзя удалить свой аккаунт', 'danger')
    db.close()
    return redirect(url_for('admin_panel'))


# ═══════════════════════════════════════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    init_db()
    # host='0.0.0.0' — доступно по сети (другой компьютер в сети техникума)
    app.run(debug=False, host='0.0.0.0', port=5000)
