from flask import Flask, request, redirect, session, render_template
import sqlite3
from datetime import datetime
import requests
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask import url_for
from flask import flash
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")

app = Flask(__name__)
app.secret_key = "dev-key"

DB = "database.db"
ADMINS = [u.lower() for u in ["gsignorele"]]
PAYMENTS_ENABLED = False
import smtplib
import uuid
from email.mime.text import MIMEText
from datetime import datetime, timedelta

UPLOAD_FOLDER = "static/avatars"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
def get_country_codes():
    return {
        "Argentina": "ar",
        "Brasil": "br",
        "Uruguay": "uy",
        "Paraguay": "py",
        "Chile": "cl",
        "Bolivia": "bo",
        "Perú": "pe",
        "Ecuador": "ec",
        "Colombia": "co",
        "Venezuela": "ve",
        "Bosnia y Herzegovina": "ba",
        "Catar": "qa",
        "México": "mx",
        "Estados Unidos": "us",
        "Canadá": "ca",
        "Costa Rica": "cr",
        "Panamá": "pa",
        "Honduras": "hn",
        "El Salvador": "sv",
        "Jamaica": "jm",

        "Francia": "fr",
        "España": "es",
        "Alemania": "de",
        "Italia": "it",
        "Portugal": "pt",
        "Inglaterra": "gb-eng",
        "Países Bajos": "nl",
        "Bélgica": "be",
        "Suiza": "ch",
        "Croacia": "hr",
        "Dinamarca": "dk",
        "Suecia": "se",
        "Noruega": "no",
        "Polonia": "pl",
        "Austria": "at",
        "Serbia": "rs",
        "Ucrania": "ua",
        "Grecia": "gr",
        "Turquía": "tr",
        "República Checa": "cz",
        "Escocia": "sc",
        "Gales": "wa",
        "Japón": "jp",
        "Corea del Sur": "kr",
        "Australia": "au",
        "Nueva Zelanda": "nz",
        "China": "cn",
        "Arabia Saudita": "sa",
        "Irán": "ir",
        "Qatar": "qa",
        "Emiratos Árabes Unidos": "ae",
        "India": "in",

        "Senegal": "sn",
        "Marruecos": "ma",
        "Egipto": "eg",
        "Nigeria": "ng",
        "Ghana": "gh",
        "Camerún": "cm",
        "Costa de Marfil": "ci",
        "Túnez": "tn",
        "Argelia": "dz",
        "Sudáfrica": "za",
        "Chequia": "cz",
        "Haití": "ht",
        "Curaçao": "cw",
        "Curacao": "cw",  # 🔥 por si viene sin ç
        "Irak": "iq",
        "Jordania": "jo",
        "RD Congo": "cd",
        "Cabo Verde": "cv",
        "Uzbekistán": "uz"
    }

# =========================
# DB
# =========================
def get_db():
    return sqlite3.connect(DB)


def init_db():
    conn = get_db()
    c = conn.cursor()

    # USERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        telefono TEXT,
        paid INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,

        reset_token TEXT,
        reset_expiry TEXT,

        avatar TEXT   -- 🔥 AGREGAR ESTO
    )
    """)

    # MATCHES
    c.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        home TEXT,
        away TEXT,
        match_datetime TEXT,
        stage TEXT,
        home_goals INTEGER,
        away_goals INTEGER
    )
    """)

    # PREDICTIONS
    c.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        match_id INTEGER,
        pred_home INTEGER,
        pred_away INTEGER,
        UNIQUE(user, match_id)
    )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================
# HELPERS
# =========================
def is_admin():
    user = session.get("user")
    if not user:
        return False
    return user.lower() in ADMINS

def send_email(to, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

from flask import flash, redirect, url_for

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form["email"]

        conn = get_db()
        c = conn.cursor()

        c.execute("SELECT username FROM users WHERE email=?", (email,))
        row = c.fetchone()

        if row:
            token = str(uuid.uuid4())
            expiry = (datetime.now() + timedelta(hours=1)).isoformat()

            c.execute("""
                UPDATE users
                SET reset_token=?, reset_expiry=?
                WHERE email=?
            """, (token, expiry, email))

            conn.commit()

            link = url_for("reset_password", token=token, _external=True)

            send_email(
                email,
                "Recuperar contraseña",
                f"Hacé click para resetear:\n{link}"
            )

        conn.close()

        flash("Si el email existe, te enviamos un link para recuperar la contraseña", "success")

        return redirect(url_for("forgot"))  # 🔥 IMPORTANTE

    return render_template("forgot.html")


from flask import flash, redirect, url_for

@app.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT username, reset_expiry
        FROM users
        WHERE reset_token=?
    """, (token,))
    row = c.fetchone()

    # ❌ token inválido
    if not row:
        conn.close()
        flash("Link inválido o ya usado", "error")
        return redirect("/forgot_password")

    username, expiry = row

    # ❌ expirado
    if datetime.now() > datetime.fromisoformat(expiry):
        conn.close()
        flash("El link expiró. Pedí uno nuevo", "error")
        return redirect("/forgot_password")

    # ✅ POST (guardar nueva password)
    if request.method == "POST":
        new_password = request.form["password"]

        if not new_password or len(new_password) < 4:
            flash("La contraseña es muy corta", "error")
            return redirect(request.url)

        hashed = generate_password_hash(new_password)

        c.execute("""
            UPDATE users
            SET password=?, reset_token=NULL, reset_expiry=NULL
            WHERE username=?
        """, (hashed, username))

        conn.commit()
        conn.close()

        flash("Contraseña actualizada. Ya podés ingresar", "success")
        return redirect("/")

    conn.close()
    return render_template("reset.html")
# =========================
# LOGIN / REGISTER
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        c = conn.cursor()

        c.execute("SELECT password FROM users WHERE username=?", (username,))
        row = c.fetchone()
        conn.close()

        if row and check_password_hash(row[0], password):
            session["user"] = username
            session["is_admin"] = is_admin()  # ✔ correcto acá
            return redirect("/matches")

        flash("Usuario o contraseña incorrectos", "error")
        return redirect("/")

    return render_template("login.html", full_screen=True)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        email = request.form["email"]
        telefono = request.form["telefono"]

        if len(password) < 4:
            flash("La contraseña es muy corta", "error")
            return redirect("/register")

        if not email:
            flash("Email requerido", "error")
            return redirect("/register")

        avatar_tipo = request.form.get("avatar_tipo")
        file = request.files.get("avatar_file")

        avatar_map = {
            "m": "/static/img/default_m.png",
            "f": "/static/img/default_f.png",
            "f2": "/static/img/default_f_dark.png",
            "m_old": "/static/img/default_m_old.png",
            "f_old": "/static/img/default_f_old.png",
            "nb": "/static/img/default_nb.png"
        }

        avatar = avatar_map.get(avatar_tipo, "/static/img/default_m.png")

        # 🔥 upload
        if file and file.filename:
            filename = f"{username}.jpg"
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

            from PIL import Image

            try:
                img = Image.open(file).convert("RGB")

                w, h = img.size
                min_side = min(w, h)

                img = img.crop((
                    (w - min_side)//2,
                    (h - min_side)//2,
                    (w + min_side)//2,
                    (h + min_side)//2
                ))

                img = img.resize((200, 200))
                img.save(path, "JPEG", quality=75)

                avatar = f"/static/avatars/{filename}"

            except:
                flash("Imagen inválida", "error")
                return redirect("/register")

        hashed = generate_password_hash(password)

        # 🔥 ADMIN SIN UPDATE
        is_admin = 1 if username == "gsignorele" else 0

        conn = get_db()
        c = conn.cursor()

        try:
            c.execute("""
                INSERT INTO users (username, password, email, telefono, avatar, is_admin)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, hashed, email, telefono, avatar, is_admin))
            conn.commit()
        except:
            conn.close()
            flash("Usuario ya existe", "error")
            return redirect("/register")

        conn.close()

        session["user"] = username
        session["is_admin"] = is_admin  # 🔥 CLAVE

        return redirect("/matches")

    return render_template("register.html")


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user" not in session:
        return redirect("/")

    username = session["user"]

    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        email = request.form["email"]
        telefono = request.form["telefono"]
        file = request.files.get("avatar_file")

        avatar = None

        # 🔥 subir imagen
        if file and file.filename:
            filename = f"{username}.jpg"
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

            from PIL import Image

            try:
                img = Image.open(file).convert("RGB")

                w, h = img.size
                min_side = min(w, h)

                img = img.crop((
                    (w - min_side)//2,
                    (h - min_side)//2,
                    (w + min_side)//2,
                    (h + min_side)//2
                ))

                img = img.resize((200, 200))
                img.save(path, "JPEG", quality=75)

                avatar = f"/static/avatars/{filename}"

            except:
                flash("Imagen inválida", "error")
                return redirect("/profile")

        # 🔥 update
        if avatar:
            c.execute("""
                UPDATE users SET email=?, telefono=?, avatar=?
                WHERE username=?
            """, (email, telefono, avatar, username))
        else:
            c.execute("""
                UPDATE users SET email=?, telefono=?
                WHERE username=?
            """, (email, telefono, username))

        conn.commit()
        flash("Perfil actualizado", "success")
        return redirect("/profile")

    # GET
    c.execute("SELECT email, telefono, avatar FROM users WHERE username=?", (username,))
    row = c.fetchone()

    conn.close()

    return render_template("profile.html",
        email=row[0],
        telefono=row[1],
        avatar=row[2]
    )
# =========================
# PAGO
# =========================
@app.route("/crear_pago")
def crear_pago():
    if not PAYMENTS_ENABLED:
        return redirect("/matches")

    if "user" not in session:
        return redirect("/")

    user = session["user"]

    payload = {
        "items": [{
            "title": "Penca Mundial",
            "quantity": 1,
            "unit_price": 150
        }],
        "metadata": {"user": user},
        "notification_url": "https://TU-APP.onrender.com/webhook",
        "back_urls": {
            "success": "/matches",
            "failure": "/matches",
            "pending": "/matches"
        },
        "auto_return": "approved"
    }

    headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}

    r = requests.post(
        "https://api.mercadopago.com/checkout/preferences",
        json=payload,
        headers=headers
    )

    data = r.json()

    if "init_point" not in data:
        return f"Error MercadoPago: {data}"

    return redirect(data["init_point"])
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if data.get("type") == "payment":
        payment_id = data["data"]["id"]

        r = requests.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
        )

        payment = r.json()

        if payment["status"] == "approved":
            user = payment["metadata"]["user"]

            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET paid=1 WHERE username=?", (user,))
            conn.commit()
            conn.close()

    return "OK"



@app.route("/admin/matches", methods=["GET", "POST"])
def admin_matches():
    if not is_admin():
        return redirect("/")

    conn = get_db()
    c = conn.cursor()

    from datetime import datetime
    if request.method == "POST":

        match_ids = []

        for key in request.form.keys():
            if key.startswith("match_"):
                match_ids.append(key.replace("match_", ""))

        for match_id in match_ids:

            home = request.form.get(f"home_{match_id}")
            away = request.form.get(f"away_{match_id}")

            date = request.form.get(f"date_{match_id}")
            time = request.form.get(f"time_{match_id}")

            home_goals = request.form.get(f"gl_{match_id}")
            away_goals = request.form.get(f"gv_{match_id}")

            home_goals = int(home_goals) if home_goals else None
            away_goals = int(away_goals) if away_goals else None

            # fecha/hora
            if not date or not time:
                continue

            new_dt = f"{date}T{time}:00"

            # validaciones
            valid_teams = get_country_codes().keys()

            if home == away:
                flash("No puede ser el mismo equipo")
                return redirect("/admin/matches")

            if home not in valid_teams or away not in valid_teams:
                flash("Equipo inválido")
                return redirect("/admin/matches")

            # update
            c.execute("""
                UPDATE matches
                SET home=?, away=?, match_datetime=?,
                    home_goals=?, away_goals=?
                WHERE id=?
            """, (
                home,
                away,
                new_dt,
                home_goals,
                away_goals,
                match_id
            ))

        conn.commit()

    # 🔥 cargar
    c.execute("""
        SELECT id, home, away, match_datetime,
               home_goals, away_goals, stage
        FROM matches
        ORDER BY match_datetime
    """)

    matches = c.fetchall()
    teams = list(get_country_codes().keys())

    conn.close()

    return render_template(
        "admin_matches.html",
        matches=matches,
        teams=teams,
        country_codes=get_country_codes()
    )
@app.route("/admin/save_all", methods=["POST"])
def admin_save_all():
    if not is_admin():
        return redirect("/")

    conn = get_db()
    c = conn.cursor()

    for key in request.form:
        if key.startswith("match_"):
            match_id = int(key.split("_")[1])

            home = request.form.get(f"home_{match_id}")
            away = request.form.get(f"away_{match_id}")
            date = request.form.get(f"date_{match_id}")
            time = request.form.get(f"time_{match_id}")
            gl = request.form.get(f"gl_{match_id}")
            gv = request.form.get(f"gv_{match_id}")

            if not date or not time:
                continue

            gl = int(gl) if gl else None
            gv = int(gv) if gv else None

            new_dt = f"{date}T{time}:00"

            c.execute("""
                UPDATE matches
                SET home=?, away=?, match_datetime=?,
                    home_goals=?, away_goals=?
                WHERE id=?
            """, (home, away, new_dt, gl, gv, match_id))

    conn.commit()
    conn.close()

    return redirect("/admin/matches")


@app.route("/admin/toggle_pay/<username>")
def toggle_pay(username):
    if not is_admin():
        return redirect("/")

    conn = get_db()
    c = conn.cursor()

    c.execute("UPDATE users SET paid = NOT paid WHERE username=?", (username,))
    conn.commit()
    conn.close()

    return redirect("/admin/users")




@app.route("/matches")
def matches():
    if "user" not in session:
        return redirect("/")

    user = session["user"]

    conn = get_db()
    c = conn.cursor()

    # pago
    c.execute("SELECT paid FROM users WHERE username=?", (user,))
    row = c.fetchone()
    paid = row[0] if row else 0

    show_pay_banner = not paid

    # partidos + predicciones
    c.execute("""
        SELECT m.id, m.home, m.away, m.match_datetime,
               m.stage,
               m.home_goals, m.away_goals,
               p.pred_home, p.pred_away
        FROM matches m
        LEFT JOIN predictions p
            ON m.id = p.match_id AND p.user = ?
    """, (user,))
    rows = c.fetchall()

    # líder
    c.execute("""
    SELECT p.user,
    SUM(
        CASE
            WHEN m.home_goals = p.pred_home AND m.away_goals = p.pred_away THEN 3
            WHEN (m.home_goals > m.away_goals AND p.pred_home > p.pred_away)
              OR (m.home_goals < m.away_goals AND p.pred_home < p.pred_away)
              OR (m.home_goals = m.away_goals AND p.pred_home = p.pred_away)
            THEN 1
            ELSE 0
        END
    ) as pts
    FROM predictions p
    JOIN matches m ON p.match_id = m.id
    WHERE m.home_goals IS NOT NULL
    GROUP BY p.user
    ORDER BY pts DESC
    LIMIT 1
    """)

    leader_row = c.fetchone()
    leader = leader_row[0] if leader_row else None

    # aciertos
    aciertos = {}

    c.execute("""
    SELECT m.id, p.user, p.pred_home, p.pred_away,
           m.home_goals, m.away_goals
    FROM matches m
    JOIN predictions p ON m.id = p.match_id
    WHERE m.home_goals IS NOT NULL
    """)

    for match_id, user_p, ph, pa, gl, gv in c.fetchall():
        if gl == ph and gv == pa:
            aciertos.setdefault(match_id, []).append(user_p)

    conn.close()

    # 🔧 FIX
    now = datetime.now()

    matches = []

    for r in rows:
        match_id, home, away, dt, stage, gl, gv, pl, pv = r
        match_time = datetime.fromisoformat(dt).replace(tzinfo=None)

        matches.append({
            "id": match_id,
            "home": home,
            "away": away,
            "stage": str(stage),
            "match_datetime": dt,
            "home_goals": gl,
            "away_goals": gv,
            "pred_home": pl,
            "pred_away": pv,
            "started": now >= match_time,
            "user_pred": pl is not None and pv is not None,
            "finished": gl is not None and gv is not None
        })

    pending_matches = []
    predicted_matches = []
    closed_matches = []

    order_map = {"16": 1, "8": 2, "4": 3, "2": 4, "1": 5}

    matches.sort(
        key=lambda x: (
            order_map.get(x["stage"], 0),
            x["match_datetime"]
        )
    )

    for m in matches:

        if m["started"]:
            closed_matches.append(m)

        elif m["user_pred"]:
            predicted_matches.append(m)

        else:
            pending_matches.append(m)

    return render_template(
        "matches.html",
        pending_matches=pending_matches,
        predicted_matches=predicted_matches,
        closed_matches=closed_matches,
        user=user,
        leader=leader,
        aciertos=aciertos,
        show_pay_banner=show_pay_banner,
        country_codes=get_country_codes(),
        special_flags={
            "Escocia": url_for('static', filename='flags/scotland.png'),
            "Inglaterra": url_for('static', filename='flags/england.png'),
            "Gales": url_for('static', filename='flags/wales.png'),
        }
    )
# =========================
# PREDICT
# =========================
from flask import flash, redirect, request, session

@app.route("/predict", methods=["POST"])
def predict():
    if "user" not in session:
        return redirect("/")

    user = session["user"]
    match_id = request.form.get("match_id")

    conn = get_db()
    c = conn.cursor()

    # 🔒 verificar pago
    if PAYMENTS_ENABLED and not is_admin():
        c.execute("SELECT paid FROM users WHERE username=?", (user,))
        row = c.fetchone()

        if not row or not row[0]:
            conn.close()
            flash("Tenés que pagar para participar", "error")
            return redirect("/matches")

    # 🔎 obtener partido
    c.execute("SELECT home, away, match_datetime FROM matches WHERE id=?", (match_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        flash("Partido inexistente", "error")
        return redirect("/matches")

    home, away, dt_str = row

    if not home or not away:
        conn.close()
        flash("Partido no definido todavía", "error")
        return redirect("/matches")

    from datetime import datetime

    now = datetime.now()

    # 🔧 FIX REAL
    match_time = datetime.fromisoformat(dt_str)
    if match_time.tzinfo:
        match_time = match_time.replace(tzinfo=None)

    if now >= match_time:
        conn.close()
        flash("El partido ya comenzó", "error")
        return redirect("/matches")

    # 🎯 predicción
    try:
        ph = int(request.form.get("pred_local"))
        pa = int(request.form.get("pred_visitante"))
    except (TypeError, ValueError):
        conn.close()
        flash("Ingresá un resultado válido", "error")
        return redirect("/matches")

    # 💾 guardar
    c.execute("""
        INSERT OR REPLACE INTO predictions (user, match_id, pred_home, pred_away)
        VALUES (?, ?, ?, ?)
    """, (user, match_id, ph, pa))

    conn.commit()
    conn.close()

    flash("Predicción guardada", "success")
    return redirect("/matches")


@app.route("/admin/clear_result/<int:match_id>")
def clear_result(match_id):
    if not is_admin():
        return redirect("/")

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        UPDATE matches
        SET home_goals=NULL, away_goals=NULL
        WHERE id=?
    """, (match_id,))

    conn.commit()
    conn.close()

    return ("", 204)



# =========================
# ADMIN RESULTADOS
# =========================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not is_admin():
        return "No autorizado"

    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        match_id = request.form["match_id"]
        gl = request.form["gl"]
        gv = request.form["gv"]

        c.execute("""
            UPDATE matches
            SET home_goals=?, away_goals=?
            WHERE id=?
        """, (gl, gv, match_id))
        conn.commit()

    c.execute("SELECT * FROM matches ORDER BY match_datetime DESC")
    matches = c.fetchall()

    conn.close()

    return render_template("admin.html", matches=matches)


@app.route("/ranking")
def ranking():
    if "user" not in session:
        return redirect("/")

    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT u.username, u.avatar,
        SUM(
            CASE
                WHEN m.home_goals = p.pred_home AND m.away_goals = p.pred_away THEN 3
                WHEN (m.home_goals > m.away_goals AND p.pred_home > p.pred_away)
                  OR (m.home_goals < m.away_goals AND p.pred_home < p.pred_away)
                  OR (m.home_goals = m.away_goals AND p.pred_home = p.pred_away)
                THEN 1
                ELSE 0
            END
        ) as pts,
        SUM(
            CASE
                WHEN m.home_goals = p.pred_home AND m.away_goals = p.pred_away THEN 1
                ELSE 0
            END
        ) as exactos
    FROM users u
    LEFT JOIN predictions p ON u.username = p.user
    LEFT JOIN matches m ON p.match_id = m.id AND m.home_goals IS NOT NULL
    GROUP BY u.username
    ORDER BY pts DESC, exactos DESC
    """)

    rows = c.fetchall()  # 🔥 ESTO VA ACÁ

    ranking = []
    pos = 1

    for r in rows:
        ranking.append({
            "pos": pos,
            "user": r[0],
            "avatar": r[1],
            "pts": r[2] or 0,
            "exactos": r[3] or 0
        })
        pos += 1

    # 🔥 saber si terminó todo
    c.execute("SELECT MAX(match_datetime) FROM matches")
    ultima = c.fetchone()[0]

    fecha_jugada = False

    if ultima:
        try:
            fecha_jugada = datetime.now() > datetime.fromisoformat(ultima)
        except:
            pass

    conn.close()

    return render_template(
        "ranking.html",
        ranking=ranking,
        user=session["user"],
        fecha_jugada=fecha_jugada
    )

@app.route("/user/<username>")
def user_detail(username):
    if "user" not in session:
        return redirect("/")

    current_user = session["user"]

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT m.id, m.home, m.away, m.match_datetime,
               m.home_goals, m.away_goals,
               p.pred_home, p.pred_away,
               m.stage
        FROM matches m
        LEFT JOIN predictions p
            ON m.id = p.match_id AND p.user = ?
        ORDER BY 
            CASE m.stage
                WHEN 'A' THEN 1
                WHEN 'B' THEN 2
                WHEN 'C' THEN 3
                WHEN 'D' THEN 4
                WHEN 'E' THEN 5
                WHEN 'F' THEN 6
                WHEN 'G' THEN 7
                WHEN 'H' THEN 8
                WHEN '16' THEN 9
                WHEN '8' THEN 10
                WHEN '4' THEN 11
                WHEN '2' THEN 12
                WHEN '1' THEN 13
                ELSE 99
            END,
            m.match_datetime
    """, (username,))
    rows = c.fetchall()
    conn.close()

    from datetime import datetime

    now = datetime.now()

    matches = []

    for r in rows:
        match_id, home, away, dt, gl, gv, ph, pv, stage = r

        # 🔧 FIX datetime (clave)
        match_time = None
        if dt:
            try:
                match_time = datetime.fromisoformat(dt)
                if match_time.tzinfo:
                    match_time = match_time.replace(tzinfo=None)
            except:
                match_time = None

        finished = gl is not None and gv is not None
        pts = None

        if finished and ph is not None and pv is not None:
            if gl == ph and gv == pv:
                pts = 3
            elif (
                    (gl > gv and ph > pv) or
                    (gl < gv and ph < pv) or
                    (gl == gv and ph == pv)
            ):
                pts = 1
            else:
                pts = 0
        # 🔒 ocultar predicción si no empezó
        if username != current_user and not finished:
            ph = None
            pv = None

        matches.append({
            "home": home,
            "away": away,
            "datetime": dt,
            "started": (now >= match_time) if match_time else False,
            "finished": finished,
            "pred_home": ph,
            "pred_away": pv,
            "real_home": gl,
            "real_away": gv,
            "stage": stage,
            "pts": pts
        })

    return render_template(
        "user_detail.html",
        matches=matches,
        username=username,
        country_codes=get_country_codes(),
        special_flags={
            "Escocia": url_for('static', filename='flags/scotland.png'),
            "Inglaterra": url_for('static', filename='flags/england.png'),
            "Gales": url_for('static', filename='flags/wales.png'),
        }
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/admin/reset", methods=["POST"])
def admin_reset():
    if not is_admin():
        return redirect("/")

    conn = get_db()
    c = conn.cursor()

    # borrar predicciones
    c.execute("DELETE FROM predictions")

    # borrar resultados pero NO partidos
    c.execute("""
        UPDATE matches
        SET home_goals=NULL, away_goals=NULL
    """)

    conn.commit()
    conn.close()

    return redirect("/admin/matches")


@app.route("/admin/users")
def admin_users():
    if not is_admin():
        return redirect("/")

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT username, email, telefono, paid
        FROM users
        ORDER BY username
    """)
    users = c.fetchall()

    # 🔥 contadores
    total = len(users)
    pagaron = sum(1 for u in users if u[3])
    deben = total - pagaron

    conn.close()

    return render_template(
        "admin_users.html",
        users=users,
        total=total,
        pagaron=pagaron,
        deben=deben
    )


@app.context_processor
def inject_user():
    return {
        "is_admin": is_admin(),
        "user": session.get("user")
    }
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)