import os
import json
import requests
import instaloader
import mercadopago
import random
from datetime import datetime
from itertools import islice 
from flask import Flask, request, render_template, jsonify, redirect, url_for, session

app = Flask(__name__)

# --- SEGURIDAD ---
app.secret_key = os.urandom(24) 
ADMIN_PASSWORD = "vip2025" 

# --- CREDENCIALES DE ORO (Combinación Ganadora del Diagnóstico) ---
# Usamos .strip() para borrar espacios fantasmas si se copian mal
JSONBIN_API_KEY = "$2a$10$PLVbCTZpFi2EEtkKGOwUO09RFaMx53qA7iNx.sCNZEQ.9bW.leQK6".strip()
JSONBIN_BIN_ID = "69433e3e43b1c97be9f5a86f".strip()

# --- CONFIGURACIÓN DE APIS ---
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
LEGION_API_KEY = os.environ.get("LEGION_API_KEY")
LEGION_URL = "https://legionsmm.com/api/v2"

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# --- IDs DE ESTRATEGIA ---
STRATEGY_CONF = {
    "likes":  {"id": 410,  "min_order": 10,  "batch_min": 15,  "batch_max": 25},
    "views":  {"id": 5559, "min_order": 100, "batch_min": 150, "batch_max": 300},
    "saves":  {"id": 4672, "min_order": 10,  "batch_min": 10,  "batch_max": 20},
    "shares": {"id": 5870, "min_order": 10,  "batch_min": 10,  "batch_max": 15}
}

# --- UTILIDADES DE LA NUBE ---
def get_db():
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    # Usamos X-Master-Key porque estamos usando la llave maestra
    headers = {"X-Master-Key": JSONBIN_API_KEY}
    
    try:
        req = requests.get(url, headers=headers, timeout=10)
        
        if req.status_code == 200:
            return req.json().get("record", {})
        else:
            # Reporte de error detallado
            return {
                "targets": [], "missions": [],
                "logs": [{
                    "fecha": "ERROR", "usuario": "SISTEMA", "link": "#",
                    "accion": f"⚠️ ERROR {req.status_code}: Verifica que Bin ID y Key coincidan."
                }]
            }
    except Exception as e:
        return {
            "targets": [], "missions": [],
            "logs": [{
                "fecha": "ERROR", "usuario": "PYTHON", "link": "#", "accion": f"⚠️ EXCEPCIÓN: {str(e)}"
            }]
        }

def save_db(data):
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": JSONBIN_API_KEY
    }
    requests.put(url, json=data, headers=headers)

def load_json_local(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def registrar_log(usuario, link, detalles):
    db = get_db()
    if "ERROR" in str(db.get('logs', [])): return

    logs = db.get('logs', [])
    nuevo_log = {
        "fecha": datetime.now().strftime("%d/%m %H:%M"),
        "usuario": usuario,
        "link": link,
        "accion": detalles
    }
    logs.insert(0, nuevo_log)
    db['logs'] = logs[:50]
    save_db(db)

# ==========================================
#  PARTE A: TIENDA PÚBLICA
# ==========================================
@app.route('/')
def home():
    services = load_json_local('services.json')
    return render_template('index.html', services=services)

@app.route('/comprar', methods=['POST'])
def comprar():
    service_id = int(request.form.get('service_id'))
    insta_link = request.form.get('link')
    quantity = int(request.form.get('quantity'))

    services = load_json_local('services.json')
    selected_service = next((s for s in services if s['id'] == service_id), None)

    if not selected_service: return "Error", 400

    calculated_price = (quantity / 1000) * selected_service['rate']
    final_price = 500 if calculated_price < 500 else calculated_price

    preference_data = {
        "items": [{
            "title": f"{selected_service['name']} (x{quantity})",
            "quantity": 1,
            "unit_price": float(final_price),
            "currency_id": "ARS"
        }],
        "metadata": { "legion_id": service_id, "quantity": quantity, "target_link": insta_link },
        "back_urls": { "success": "https://proyectomkt.onrender.com/", "failure": "https://proyectomkt.onrender.com/" },
        "auto_return": "approved",
        "notification_url": "https://proyectomkt.onrender.com/webhook"
    }
    try:
        preference_response = sdk.preference().create(preference_data)
        return redirect(preference_response["response"]["init_point"])
    except Exception as e: return f"Error: {str(e)}", 500

@app.route('/webhook', methods=['POST'])
def webhook():
    id = request.args.get('id')
    topic = request.args.get('topic')
    if topic == 'payment':
        payment_info = sdk.payment().get(id)
        if payment_info['response']['status'] == 'approved':
            meta = payment_info['response']['metadata']
            requests.post(LEGION_URL, data={
                'key': LEGION_API_KEY, 'action': 'add',
                'service': meta['legion_id'], 'link': meta['target_link'], 'quantity': meta['quantity']
            })
    return jsonify({"status": "ok"}), 200


# ==========================================
#  PARTE B: PANEL DE CONTROL
# ==========================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('bot_dashboard'))
        else:
            error = "Contraseña Incorrecta"
    return render_template('admin_login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/bot')
def bot_dashboard():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    
    db = get_db()
    targets = db.get('targets', [])
    logs = db.get('logs', [])
    missions = db.get('missions', [])
    
    return render_template('bot.html', targets=targets, logs=logs, missions=missions)

@app.route('/admin/bot/add', methods=['POST'])
def bot_add():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    username = request.form.get('username').replace('@', '').strip()
    
    db = get_db()
    if "ERROR" in str(db.get('logs', [])): return "Error DB", 500

    targets = db.get('targets', [])
    for t in targets:
        if t['username'] == username: return "Error: Usuario ya existe", 400
    
    targets.append({ "username": username, "last_shortcode": None })
    db['targets'] = targets 
    save_db(db)
    
    return redirect(url_for('bot_dashboard'))

@app.route('/admin/bot/delete/<username>')
def bot_delete(username):
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    
    db = get_db()
    if "ERROR" in str(db.get('logs', [])): return "Error DB", 500

    targets = db.get('targets', [])
    targets = [t for t in targets if t['username'] != username]
    db['targets'] = targets
    save_db(db)
    return redirect(url_for('bot_dashboard'))


# ==========================================
#  PARTE C: CEREBRO DE MISIONES
# ==========================================

def crear_misiones_nuevas(link, user):
    db = get_db()
    missions = db.get('missions', [])
    
    total_likes = random.randint(170, 300)
    missions.append({ "type": "likes", "user": user, "link": link, "remaining": total_likes, "service_id": STRATEGY_CONF["likes"]["id"] })
    
    total_views = random.randint(2400, 3600)
    missions.append({ "type": "views", "user": user, "link": link, "remaining": total_views, "service_id": STRATEGY_CONF["views"]["id"] })
    
    total_saves = random.randint(10, 20)
    missions.append({ "type": "saves", "user": user, "link": link, "remaining": total_saves, "service_id": STRATEGY_CONF["saves"]["id"] })

    total_shares = random.randint(10, 15)
    missions.append({ "type": "shares", "user": user, "link": link, "remaining": total_shares, "service_id": STRATEGY_CONF["shares"]["id"] })

    db['missions'] = missions
    save_db(db)
    return f"Misiones creadas: {total_likes} Likes, {total_views} Views."

def procesar_misiones_pendientes():
    db = get_db()
    if "ERROR" in str(db.get('logs', [])): return [] 

    missions = db.get('missions', [])
    if not missions: return []

    log_report = []
    misiones_activas = []
    
    for m in missions:
        conf = STRATEGY_CONF.get(m["type"])
        if not conf: continue
        
        batch_size = random.randint(conf["batch_min"], conf["batch_max"])
        if m["remaining"] < batch_size: batch_size = m["remaining"]
        if m["remaining"] > 0 and batch_size < conf["min_order"]: batch_size = m["remaining"]

        if batch_size > 0:
            try:
                if batch_size >= conf["min_order"]:
                    requests.post(LEGION_URL, data={'key': LEGION_API_KEY, 'action': 'add', 'service': m["service_id"], 'link': m["link"], 'quantity': batch_size})
                    m["remaining"] -= batch_size
                    log_report.append(f"📦 {m['type'].upper()}: Enviados {batch_size} a {m['user']}")
                else:
                    m["remaining"] = 0
            except Exception as e:
                log_report.append(f"❌ Error API: {str(e)}")

        if m["remaining"] > 0: misiones_activas.append(m)
        else: log_report.append(f"✅ Misión {m['type']} completada")

    db['missions'] = misiones_activas
    save_db(db)
    return log_report

# --- CRON JOB UNIFICADO ---
@app.route('/sistema/vigia-automatico')
def cron_vigia():
    db = get_db()
    if "ERROR" in str(db.get('logs', [])): return jsonify({"status": "error_db", "msg": db['logs'][0]['accion']})

    targets = db.get('targets', [])
    L = instaloader.Instaloader()
    reporte_general = []
    cambios_targets = False
    
    logs_misiones = procesar_misiones_pendientes()
    reporte_general.extend(logs_misiones)
    
    for t in targets:
        user = t['username']
        try:
            profile = instaloader.Profile.from_username(L.context, user)
            posts = profile.get_posts()
            candidatos = list(islice(posts, 4))
            
            if not candidatos: continue
            
            latest = max(candidatos, key=lambda p: p.date_utc)
            shortcode = latest.shortcode
            
            if shortcode != t['last_shortcode']:
                print(f"🚨 NUEVO POST: {user}")
                link = f"https://www.instagram.com/p/{shortcode}/"
                res = crear_misiones_nuevas(link, user)
                registrar_log(user, link, "🎯 Post Detectado - Iniciando Campaña")
                t['last_shortcode'] = shortcode
                cambios_targets = True
                reporte_general.append(f"🆕 {user}: {res}")
        except Exception as e:
            reporte_general.append(f"❌ Error {user}: {str(e)}")
            
    if cambios_targets:
        db_final = get_db()
        db_final['targets'] = targets
        save_db(db_final)
    
    if logs_misiones: registrar_log("SISTEMA", "Auto-Goteo", " | ".join(logs_misiones))
        
    return jsonify({"status": "ok", "actividad": reporte_general})

if __name__ == '__main__':
    app.run(debug=True)
