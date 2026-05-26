import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'carwash_secret_key_2026'

DATABASE = 'carwash_2026.db'

def get_db():
    """Возвращает соединение с БД со строковым доступом по ключу."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Создаёт таблицы и заполняет начальными данными, если БД пуста."""
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS Услуги (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        название        TEXT NOT NULL UNIQUE,
        цена            REAL NOT NULL,
        категория       TEXT,
        время_мин       INTEGER NOT NULL DEFAULT 30
    );

    CREATE TABLE IF NOT EXISTS Клиенты (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        телефон         TEXT UNIQUE NOT NULL,
        фио             TEXT NOT NULL,
        скидка_процент  INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS Автомобили (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        клиент_id       INTEGER NOT NULL,
        марка           TEXT NOT NULL,
        модель          TEXT,
        госномер        TEXT NOT NULL,
        цвет            TEXT,
        FOREIGN KEY (клиент_id) REFERENCES Клиенты(id),
        UNIQUE (клиент_id, госномер)
    );

    CREATE TABLE IF NOT EXISTS Заказы (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        клиент_id           INTEGER,
        автомобиль_id       INTEGER NOT NULL,
        дата_создания       TEXT NOT NULL,
        планируемая_дата    TEXT,
        статус              TEXT DEFAULT 'Новый',
        итого               REAL DEFAULT 0,
        оплачено            REAL DEFAULT 0,
        способ_оплаты       TEXT,
        комментарий         TEXT,
        FOREIGN KEY (клиент_id)     REFERENCES Клиенты(id),
        FOREIGN KEY (автомобиль_id) REFERENCES Автомобили(id)
    );

    CREATE TABLE IF NOT EXISTS Состав_заказа (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        заказ_id        INTEGER NOT NULL,
        услуга_id       INTEGER NOT NULL,
        количество      INTEGER DEFAULT 1,
        цена_на_момент  REAL NOT NULL,
        FOREIGN KEY (заказ_id)  REFERENCES Заказы(id) ON DELETE CASCADE,
        FOREIGN KEY (услуга_id) REFERENCES Услуги(id)
    );
    """)

    # Заполнение услуг
    cur.execute("SELECT COUNT(*) FROM Услуги")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO Услуги (название, цена, категория, время_мин) VALUES (?,?,?,?)",
            [
                ("Мойка кузова стандарт",  750,  "кузов",    20),
                ("Мойка + воск",          1200,  "кузов",    35),
                ("Чернение резины",        500,  "кузов",    15),
                ("Химчистка салона",      4200,  "салон",    90),
                ("Комплекс Премиум",      6800,  "комплекс",150),
                ("Мойка двигателя",       1500,  "доп",      45),
                ("Антидождь (стёкла)",     950,  "доп",      25),
            ]
        )

    # Заполнение клиентов
    cur.execute("SELECT COUNT(*) FROM Клиенты")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO Клиенты (телефон, фио, скидка_процент) VALUES (?,?,?)",
            [
                ("+79161234567", "Кочанов Александр Викторович", 10),
                ("+79252345678", "Кравцова Ольга Сергеевна",       0),
                ("+79033456789", "Пономарёв Дмитрий Андреевич",    5),
                ("+79264567890", "Соколова Екатерина Михайловна",  0),
                ("+89120079854", "Шуваллов Андрей Алексеевич",     1),
            ]
        )

    # Заполнение автомобилей
    cur.execute("SELECT COUNT(*) FROM Автомобили")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id FROM Клиенты ORDER BY id LIMIT 4")
        client_ids = [r[0] for r in cur.fetchall()]
        cur.executemany(
            "INSERT INTO Автомобили (клиент_id, марка, модель, госномер, цвет) VALUES (?,?,?,?,?)",
            [
                (client_ids[0], "Toyota",  "Camry",    "А123ВС 777", "чёрный"),
                (client_ids[1], "BMW",     "X5",       "О456МР 199", "белый"),
                (client_ids[2], "Kia",     "Sportage", "К789АН 777", "серый"),
                (client_ids[3], "Hyundai", "Tucson",   "Е112КО 777", "синий"),
            ]
        )

    # Демо-заказы, если их ещё нет
    cur.execute("SELECT COUNT(*) FROM Заказы")
    if cur.fetchone()[0] == 0:
        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur.execute("SELECT id FROM Автомобили ORDER BY id LIMIT 4")
        auto_ids = [r[0] for r in cur.fetchall()]
        cur.executemany(
            """INSERT INTO Заказы
               (клиент_id, автомобиль_id, дата_создания, планируемая_дата,
                статус, итого, способ_оплаты, комментарий)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (1, auto_ids[0], today, today,  "В работе",      1950, "Карта",    "Срочно"),
                (2, auto_ids[1], today, None,   "Новый",         6800, "СБП",      None),
                (3, auto_ids[2], today, None,   "Готов",         4700, "Наличные", None),
                (4, auto_ids[3], today, today,  "Запланировано", 1200, None,       "На 14:00 завтра"),
            ]
        )
        conn.commit()
        cur.execute("SELECT id FROM Заказы ORDER BY id DESC LIMIT 4")
        order_ids = [r[0] for r in cur.fetchall()][::-1]
        cur.executemany(
            "INSERT INTO Состав_заказа (заказ_id, услуга_id, количество, цена_на_момент) VALUES (?,?,?,?)",
            [
                (order_ids[0], 1, 1,  750),
                (order_ids[0], 3, 1,  500),
                (order_ids[1], 5, 1, 6800),
                (order_ids[2], 4, 1, 4200),
                (order_ids[2], 7, 1,  950),
                (order_ids[3], 2, 1, 1200),
            ]
        )
        # Пересчёт итого
        for oid in order_ids:
            cur.execute("""
                UPDATE Заказы
                SET итого = (
                    SELECT SUM(количество * цена_на_момент)
                    FROM Состав_заказа
                    WHERE заказ_id = Заказы.id
                )
                WHERE id = ?
            """, (oid,))
        conn.commit()

    conn.close()

def recalc_order_total(order_id):
    """Пересчитывает сумму заказа на основе Состав_заказа."""
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT SUM(количество * цена_на_момент)
        FROM Состав_заказа
        WHERE заказ_id = ?
    """, (order_id,))
    total = cur.fetchone()[0] or 0
    cur.execute("UPDATE Заказы SET итого = ? WHERE id = ?", (total, order_id))
    db.commit()
    db.close()

# ------------------- Маршруты -------------------
@app.route('/')
def index():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM Заказы WHERE статус = 'Новый'")
    new_orders = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) as cnt FROM Заказы WHERE статус = 'В работе'")
    inwork_orders = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) as cnt FROM Заказы WHERE статус = 'Готов'")
    ready_orders = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) as cnt FROM Клиенты")
    clients_cnt = cur.fetchone()['cnt']
    cur.execute("SELECT IFNULL(SUM(итого),0) as total FROM Заказы")
    revenue = cur.fetchone()['total']
    db.close()
    return render_template('index.html', new_orders=new_orders, inwork_orders=inwork_orders,
                           ready_orders=ready_orders, clients_cnt=clients_cnt, revenue=revenue)

# ---------- Услуги ----------
@app.route('/services')
def services():
    db = get_db()
    services = db.execute("SELECT * FROM Услуги ORDER BY id").fetchall()
    db.close()
    return render_template('services.html', services=services)

@app.route('/services/new', methods=['GET', 'POST'])
def service_new():
    if request.method == 'POST':
        name = request.form['название']
        price = float(request.form['цена'])
        category = request.form.get('категория', '')
        time_min = int(request.form['время_мин'])
        db = get_db()
        try:
            db.execute("INSERT INTO Услуги (название, цена, категория, время_мин) VALUES (?,?,?,?)",
                       (name, price, category, time_min))
            db.commit()
            flash('Услуга добавлена', 'success')
        except sqlite3.IntegrityError:
            flash('Услуга с таким названием уже существует', 'danger')
        db.close()
        return redirect(url_for('services'))
    return render_template('service_form.html', title='Добавить услугу', service=None)

@app.route('/services/<int:id>/edit', methods=['GET', 'POST'])
def service_edit(id):
    db = get_db()
    if request.method == 'POST':
        name = request.form['название']
        price = float(request.form['цена'])
        category = request.form.get('категория', '')
        time_min = int(request.form['время_мин'])
        db.execute("UPDATE Услуги SET название=?, цена=?, категория=?, время_мин=? WHERE id=?", 
                   (name, price, category, time_min, id))
        db.commit()
        flash('Услуга обновлена', 'success')
        db.close()
        return redirect(url_for('services'))
    service = db.execute("SELECT * FROM Услуги WHERE id=?", (id,)).fetchone()
    db.close()
    return render_template('service_form.html', title='Редактировать услугу', service=service)

@app.route('/services/<int:id>/delete')
def service_delete(id):
    db = get_db()
    cnt = db.execute("SELECT COUNT(*) FROM Состав_заказа WHERE услуга_id=?", (id,)).fetchone()[0]
    if cnt > 0:
        flash('Нельзя удалить услугу, которая есть в заказах', 'danger')
    else:
        db.execute("DELETE FROM Услуги WHERE id=?", (id,))
        db.commit()
        flash('Услуга удалена', 'success')
    db.close()
    return redirect(url_for('services'))

# ---------- Клиенты ----------
@app.route('/clients')
def clients():
    db = get_db()
    clients = db.execute("SELECT * FROM Клиенты ORDER BY id").fetchall()
    db.close()
    return render_template('clients.html', clients=clients)

@app.route('/clients/new', methods=['GET', 'POST'])
def client_new():
    if request.method == 'POST':
        phone = request.form['телефон']
        fio = request.form['фио']
        discount = int(request.form.get('скидка_процент', 0))
        db = get_db()
        try:
            db.execute("INSERT INTO Клиенты (телефон, фио, скидка_процент) VALUES (?,?,?)",
                       (phone, fio, discount))
            db.commit()
            flash('Клиент добавлен', 'success')
        except sqlite3.IntegrityError:
            flash('Клиент с таким телефоном уже существует', 'danger')
        db.close()
        return redirect(url_for('clients'))
    return render_template('client_form.html', title='Добавить клиента', client=None)

@app.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
def client_edit(id):
    db = get_db()
    if request.method == 'POST':
        phone = request.form['телефон']
        fio = request.form['фио']
        discount = int(request.form.get('скидка_процент', 0))
        db.execute("UPDATE Клиенты SET телефон=?, фио=?, скидка_процент=? WHERE id=?",
                   (phone, fio, discount, id))
        db.commit()
        flash('Клиент обновлён', 'success')
        db.close()
        return redirect(url_for('clients'))
    client = db.execute("SELECT * FROM Клиенты WHERE id=?", (id,)).fetchone()
    db.close()
    return render_template('client_form.html', title='Редактировать клиента', client=client)

@app.route('/clients/<int:id>/delete')
def client_delete(id):
    db = get_db()
    cnt = db.execute("SELECT COUNT(*) FROM Автомобили WHERE клиент_id=?", (id,)).fetchone()[0]
    if cnt > 0:
        flash('Удалите сначала автомобили клиента', 'danger')
    else:
        db.execute("DELETE FROM Клиенты WHERE id=?", (id,))
        db.commit()
        flash('Клиент удалён', 'success')
    db.close()
    return redirect(url_for('clients'))

# ---------- Автомобили ----------
@app.route('/vehicles')
def vehicles():
    db = get_db()
    vehicles = db.execute("""
        SELECT a.id, a.марка, a.модель, a.госномер, a.цвет, cl.фио as владелец, cl.id as клиент_id
        FROM Автомобили a JOIN Клиенты cl ON a.клиент_id = cl.id
        ORDER BY a.id
    """).fetchall()
    db.close()
    return render_template('vehicles.html', vehicles=vehicles)

@app.route('/vehicles/new', methods=['GET', 'POST'])
def vehicle_new():
    db = get_db()
    clients = db.execute("SELECT id, фио FROM Клиенты ORDER BY фио").fetchall()
    if request.method == 'POST':
        client_id = int(request.form['клиент_id'])
        brand = request.form['марка']
        model = request.form.get('модель', '')
        plate = request.form['госномер']
        color = request.form.get('цвет', '')
        try:
            db.execute("INSERT INTO Автомобили (клиент_id, марка, модель, госномер, цвет) VALUES (?,?,?,?,?)",
                       (client_id, brand, model, plate, color))
            db.commit()
            flash('Автомобиль добавлен', 'success')
        except sqlite3.IntegrityError:
            flash('Такой госномер уже есть у этого клиента', 'danger')
        db.close()
        return redirect(url_for('vehicles'))
    db.close()
    return render_template('vehicle_form.html', title='Добавить автомобиль', vehicle=None, clients=clients)

@app.route('/vehicles/<int:id>/edit', methods=['GET', 'POST'])
def vehicle_edit(id):
    db = get_db()
    clients = db.execute("SELECT id, фио FROM Клиенты ORDER BY фио").fetchall()
    if request.method == 'POST':
        client_id = int(request.form['клиент_id'])
        brand = request.form['марка']
        model = request.form.get('модель', '')
        plate = request.form['госномер']
        color = request.form.get('цвет', '')
        try:
            db.execute("UPDATE Автомобили SET клиент_id=?, марка=?, модель=?, госномер=?, цвет=? WHERE id=?",
                       (client_id, brand, model, plate, color, id))
            db.commit()
            flash('Автомобиль обновлён', 'success')
        except sqlite3.IntegrityError:
            flash('Конфликт: такой госномер уже есть у этого клиента', 'danger')
        db.close()
        return redirect(url_for('vehicles'))
    vehicle = db.execute("SELECT * FROM Автомобили WHERE id=?", (id,)).fetchone()
    db.close()
    return render_template('vehicle_form.html', title='Редактировать автомобиль', vehicle=vehicle, clients=clients)

@app.route('/vehicles/<int:id>/delete')
def vehicle_delete(id):
    db = get_db()
    cnt = db.execute("SELECT COUNT(*) FROM Заказы WHERE автомобиль_id=?", (id,)).fetchone()[0]
    if cnt > 0:
        flash('Нельзя удалить автомобиль, на который есть заказы', 'danger')
    else:
        db.execute("DELETE FROM Автомобили WHERE id=?", (id,))
        db.commit()
        flash('Автомобиль удалён', 'success')
    db.close()
    return redirect(url_for('vehicles'))

# ---------- Заказы ----------
@app.route('/orders')
def orders():
    db = get_db()
    orders = db.execute("""
        SELECT z.id, cl.фио, a.марка || ' ' || a.модель as авто, z.статус, z.итого, z.оплачено, z.способ_оплаты
        FROM Заказы z
        JOIN Клиенты cl ON z.клиент_id = cl.id
        JOIN Автомобили a ON z.автомобиль_id = a.id
        ORDER BY z.id DESC
    """).fetchall()
    db.close()
    return render_template('orders.html', orders=orders)

@app.route('/orders/new', methods=['GET', 'POST'])
def order_new():
    db = get_db()
    clients = db.execute("SELECT id, фио FROM Клиенты ORDER BY фио").fetchall()
    if request.method == 'POST':
        client_id = int(request.form['клиент_id'])
        vehicle_id = int(request.form['автомобиль_id'])
        status = request.form.get('статус', 'Новый')
        plan_date = request.form.get('планируемая_дата') or None
        comment = request.form.get('комментарий')
        payment_method = request.form.get('способ_оплаты')
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur = db.cursor()
        cur.execute("""
            INSERT INTO Заказы (клиент_id, автомобиль_id, дата_создания, планируемая_дата, статус, способ_оплаты, комментарий)
            VALUES (?,?,?,?,?,?,?)
        """, (client_id, vehicle_id, now, plan_date, status, payment_method, comment))
        order_id = cur.lastrowid
        db.commit()
        db.close()
        return redirect(url_for('order_detail', id=order_id))
    # все автомобили с владельцем для выбора
    vehicles = db.execute("""
        SELECT a.id, a.марка, a.модель, a.госномер, cl.фио
        FROM Автомобили a JOIN Клиенты cl ON a.клиент_id = cl.id
    """).fetchall()
    db.close()
    return render_template('order_form.html', title='Новый заказ', order=None, clients=clients, vehicles=vehicles)

@app.route('/orders/<int:id>')
def order_detail(id):
    db = get_db()
    order = db.execute("""
        SELECT z.*, cl.фио as клиент_фио, a.марка, a.модель, a.госномер
        FROM Заказы z
        JOIN Клиенты cl ON z.клиент_id = cl.id
        JOIN Автомобили a ON z.автомобиль_id = a.id
        WHERE z.id = ?
    """, (id,)).fetchone()
    if not order:
        flash('Заказ не найден', 'danger')
        return redirect(url_for('orders'))
    items = db.execute("""
        SELECT sz.id, u.название, sz.количество, sz.цена_на_момент,
               sz.количество * sz.цена_на_момент as сумма
        FROM Состав_заказа sz
        JOIN Услуги u ON sz.услуга_id = u.id
        WHERE sz.заказ_id = ?
    """, (id,)).fetchall()
    services_all = db.execute("SELECT id, название, цена FROM Услуги ORDER BY название").fetchall()
    db.close()
    return render_template('order_detail.html', order=order, items=items, services=services_all)

@app.route('/orders/<int:id>/edit', methods=['GET', 'POST'])
def order_edit(id):
    db = get_db()
    if request.method == 'POST':
        status = request.form['статус']
        paid = float(request.form.get('оплачено', 0))
        payment_method = request.form.get('способ_оплаты')
        comment = request.form.get('комментарий')
        plan_date = request.form.get('планируемая_дата') or None
        db.execute("""
            UPDATE Заказы SET статус=?, оплачено=?, способ_оплаты=?, комментарий=?, планируемая_дата=?
            WHERE id=?
        """, (status, paid, payment_method, comment, plan_date, id))
        db.commit()
        flash('Заказ обновлён', 'success')
        db.close()
        return redirect(url_for('order_detail', id=id))
    order = db.execute("SELECT * FROM Заказы WHERE id=?", (id,)).fetchone()
    db.close()
    return render_template('order_edit.html', order=order)

@app.route('/orders/<int:id>/add_service', methods=['POST'])
def order_add_service(id):
    service_id = int(request.form['service_id'])
    quantity = int(request.form['quantity'])
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT цена FROM Услуги WHERE id=?", (service_id,))
    price = cur.fetchone()[0]
    cur.execute("INSERT INTO Состав_заказа (заказ_id, услуга_id, количество, цена_на_момент) VALUES (?,?,?,?)",
                (id, service_id, quantity, price))
    db.commit()
    recalc_order_total(id)
    db.close()
    flash('Услуга добавлена в заказ', 'success')
    return redirect(url_for('order_detail', id=id))

@app.route('/orders/remove_item/<int:item_id>')
def order_remove_item(item_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT заказ_id FROM Состав_заказа WHERE id=?", (item_id,))
    row = cur.fetchone()
    if row:
        order_id = row[0]
        cur.execute("DELETE FROM Состав_заказа WHERE id=?", (item_id,))
        db.commit()
        recalc_order_total(order_id)
        flash('Позиция удалена', 'success')
        db.close()
        return redirect(url_for('order_detail', id=order_id))
    db.close()
    return redirect(url_for('orders'))

@app.route('/orders/<int:id>/delete')
def order_delete(id):
    db = get_db()
    db.execute("DELETE FROM Заказы WHERE id=?", (id,))
    db.commit()
    flash('Заказ удалён', 'success')
    db.close()
    return redirect(url_for('orders'))

# ---------- Отчёты (исправленные запросы) ----------
@app.route('/reports')
def reports():
    db = get_db()
    
    # Запрос 1: Клиент с наибольшей суммой заказов
    top_client = db.execute("""
        SELECT
            cl.фио                        AS Клиент,
            cl.телефон                    AS Телефон,
            COUNT(DISTINCT z.id)          AS Заказов,
            SUM(sz.количество * sz.цена_на_момент) AS Итого_руб
        FROM Клиенты cl
        JOIN Заказы z ON z.клиент_id = cl.id
        JOIN Состав_заказа sz ON sz.заказ_id = z.id
        GROUP BY cl.id, cl.фио, cl.телефон
        ORDER BY Итого_руб DESC
        LIMIT 1
    """).fetchone()

    # Запрос 2: Все мойки за сегодня
    today_date = datetime.now().strftime("%Y-%m-%d")
    today_washes = db.execute("""
        SELECT
            z.id                                    AS №_заказа,
            cl.фио                                  AS Клиент,
            a.марка || ' ' || a.модель              AS Авто,
            a.госномер                              AS Госномер,
            u.название                              AS Услуга,
            sz.цена_на_момент                       AS Цена,
            z.статус                                AS Статус
        FROM Заказы z
        JOIN Клиенты cl       ON z.клиент_id      = cl.id
        JOIN Автомобили a     ON z.автомобиль_id  = a.id
        JOIN Состав_заказа sz ON sz.заказ_id      = z.id
        JOIN Услуги u         ON u.id             = sz.услуга_id
        WHERE DATE(z.дата_создания) = ?
        ORDER BY z.id, sz.id
    """, (today_date,)).fetchall()
    
    # Считаем итоговую сумму за день
    total_today = 0
    if today_washes:
        total_today = sum(row['Цена'] for row in today_washes)

    # Запрос 3: Автомобиль, реже всего мытый в этом году
    least_washed = db.execute("""
        SELECT
            a.марка || ' ' || a.модель   AS Авто,
            a.госномер                   AS Госномер,
            cl.фио                       AS Владелец,
            COUNT(z.id)                  AS Моек_в_году
        FROM Автомобили a
        JOIN Клиенты cl ON cl.id = a.клиент_id
        LEFT JOIN Заказы z
            ON  z.автомобиль_id = a.id
            AND strftime('%Y', z.дата_создания) = strftime('%Y', 'now')
        GROUP BY a.id, a.марка, a.модель, a.госномер, cl.фио
        ORDER BY Моек_в_году ASC, a.id ASC
        LIMIT 1
    """).fetchone()

    db.close()
    
    return render_template('reports.html',
                           top_client=top_client,
                           today_washes=today_washes,
                           total_today=total_today,
                           today_date=today_date,
                           least_washed=least_washed)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)