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

# --- CONFIGURACIÓN ---
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
LEGION_API_KEY = os.environ.get("LEGION_API_KEY")
LEGION_URL = "https://legionsmm.com/api/v2"

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# --- IDs DE ESTRATEGIA Y MÍNIMOS ---
STRATEGY_CONF = {
    "likes":  {"id": 410,  "min_order": 10,  "batch_min": 15,  "batch_max": 25},
    "views":  {"id": 5559, "min_order": 100, "batch_min": 150, "batch_max": 300},
    "saves":  {"id": 4672, "min_order": 10,  "batch_min": 10,  "batch_max": 20},
    "shares": {"id": 5870, "min_order": 10,  "batch_min": 10,  "batch_max": 15}
}

# --- UTILIDADES ---
def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)

def registrar_log(usuario, link, detalles):
    logs = load_json('logs.json')
    nuevo_log = {
        "fecha": datetime.now().strftime("%d/%m %H:%M"),
        "usuario": usuario,
        "link": link,
        "accion": detalles
    }
    logs.insert(0, nuevo_log)
    save_json('logs.json', logs[:50])

# ==========================================
#  PARTE A: TIENDA PÚBLICA (Sin cambios)
# ==========================================
@app.route('/')
def home():
    services = load_json('services.json')
    return render_template('index.html', services=services)

@app.route('/comprar', methods=['POST'])
def comprar():
    service_id = int(request.form.get('service_id'))
    insta_link = request.form.get('link')
    quantity = int(request.form.get('quantity'))

    services = load_json('services.json')
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
    
    targets = load_json('targets.json')
    logs = load_json('logs.json')
    missions = load_json('missions.json') # Mostrar misiones activas también
    
    return render_template('bot.html', targets=targets, logs=logs, missions=missions)

@app.route('/admin/bot/add', methods=['POST'])
def bot_add():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    username = request.form.get('username').replace('@', '').strip()
    targets = load_json('targets.json')
    for t in targets:
        if t['username'] == username: return "Error: Usuario ya existe", 400
    
    targets.append({ "username": username, "last_shortcode": None })
    save_json('targets.json', targets)
    return redirect(url_for('bot_dashboard'))

@app.route('/admin/bot/delete/<username>')
def bot_delete(username):
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    targets = load_json('targets.json')
    targets = [t for t in targets if t['username'] != username]
    save_json('targets.json', targets)
    return redirect(url_for('bot_dashboard'))


# ==========================================
#  PARTE C: CEREBRO DE MISIONES (NUEVO)
# ==========================================

def crear_misiones_nuevas(link, user):
    """Calcula totales y guarda las tareas pendientes en missions.json"""
    missions = load_json('missions.json')
    
    # 1. LIKES (Total 170-300)
    total_likes = random.randint(170, 300)
    missions.append({
        "type": "likes", "user": user, "link": link,
        "remaining": total_likes, "service_id": STRATEGY_CONF["likes"]["id"]
    })
    
    # 2. VIEWS (Total 2400-3600)
    total_views = random.randint(2400, 3600)
    missions.append({
        "type": "views", "user": user, "link": link,
        "remaining": total_views, "service_id": STRATEGY_CONF["views"]["id"]
    })
    
    # 3. SAVES (Total 10-20) - Se manda todo junto porque es poco para dividir
    total_saves = random.randint(10, 20)
    missions.append({
        "type": "saves", "user": user, "link": link,
        "remaining": total_saves, "service_id": STRATEGY_CONF["saves"]["id"]
    })

    # 4. SHARES (Total 10-15) - Se manda todo junto
    total_shares = random.randint(10, 15)
    missions.append({
        "type": "shares", "user": user, "link": link,
        "remaining": total_shares, "service_id": STRATEGY_CONF["shares"]["id"]
    })

    save_json('missions.json', missions)
    return f"Misiones creadas: {total_likes} Likes, {total_views} Views, {total_saves} Saves."

def procesar_misiones_pendientes():
    """Se ejecuta cada 30 min. Toma un poquito de cada misión y lo manda."""
    missions = load_json('missions.json')
    log_report = []
    
    misiones_activas = []
    
    for m in missions:
        # Configuración según tipo
        conf = STRATEGY_CONF.get(m["type"])
        
        if not conf: continue
        
        # Calcular lote (Batch) aleatorio
        batch_size = random.randint(conf["batch_min"], conf["batch_max"])
        
        # Ajuste final: Si queda menos que el lote, mandar lo que queda
        if m["remaining"] < batch_size:
            batch_size = m["remaining"]
            
        # REGLA DE ORO: Si el lote es menor al mínimo de Legion, mandar el mínimo (o todo si es el final)
        if batch_size < conf["min_order"]:
             # Si lo que queda es menor al mínimo, hay que mandarlo igual PERO Legion puede fallar.
             # Truco: Si falta poco (ej: 5 likes), mejor no mandarlos para no perder plata,
             # O acumularlos (pero eso complica).
             # En este caso, si queda < min_order, intentamos mandar min_order si tenemos saldo, 
             # o cerramos la misión.
             if m["remaining"] > 0:
                 batch_size = m["remaining"] # Intentar mandar resto
        
        # Ejecutar pedido a Legion
        if batch_size > 0:
            try:
                # OJO: Si batch_size < min_order, Legion dará error. 
                # Aseguramos que solo enviamos si cumple MINIMO o si es SAVES/SHARES que configuramos para ir de una.
                if batch_size >= conf["min_order"]:
                    requests.post(LEGION_URL, data={
                        'key': LEGION_API_KEY, 'action': 'add',
                        'service': m["service_id"], 'link': m["link"], 'quantity': batch_size
                    })
                    m["remaining"] -= batch_size
                    log_report.append(f"📦 {m['type'].upper()}: Enviados {batch_size} a {m['user']}")
                else:
                    # Caso borde: Quedan 8 likes, mínimo es 10.
                    # Opción: Mandar 10 para cerrar.
                    requests.post(LEGION_URL, data={
                        'key': LEGION_API_KEY, 'action': 'add',
                        'service': m["service_id"], 'link': m["link"], 'quantity': conf["min_order"]
                    })
                    m["remaining"] = 0 # Forzar cierre
                    log_report.append(f"📦 {m['type'].upper()}: Cierre final ({conf['min_order']}) a {m['user']}")
            except Exception as e:
                log_report.append(f"❌ Error API: {str(e)}")

        # Si todavía queda saldo, mantener la misión viva
        if m["remaining"] > 0:
            misiones_activas.append(m)
        else:
            log_report.append(f"✅ Misión {m['type']} completada para {m['user']}")

    save_json('missions.json', misiones_activas)
    return log_report

# --- CRON JOB UNIFICADO ---
@app.route('/sistema/vigia-automatico')
def cron_vigia():
    targets = load_json('targets.json')
    L = instaloader.Instaloader()
    reporte_general = []
    cambios_targets = False
    
    # 1. EJECUTAR MISIONES PENDIENTES (Goteo)
    logs_misiones = procesar_misiones_pendientes()
    reporte_general.extend(logs_misiones)
    
    # 2. BUSCAR NUEVOS POSTS
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
                print(f"🚨 NUEVO POST DETECTADO: {user}")
                link = f"https://www.instagram.com/p/{shortcode}/"
                
                # EN LUGAR DE DISPARAR, CREAMOS MISIONES
                res_creacion = crear_misiones_nuevas(link, user)
                
                # Guardar log importante
                registrar_log(user, link, "🎯 Post Detectado - Iniciando Campaña")
                
                t['last_shortcode'] = shortcode
                cambios_targets = True
                reporte_general.append(f"🆕 {user}: {res_creacion}")
            else:
                # No llenamos el reporte de "Sin novedad" para no saturar,
                # a menos que no haya misiones corriendo
                pass
                
        except Exception as e:
            reporte_general.append(f"❌ Error escaneo {user}: {str(e)}")
            
    if cambios_targets: save_json('targets.json', targets)
    
    # Guardar logs de ejecución de goteo si hubo actividad
    if logs_misiones:
        registrar_log("SISTEMA", "Auto-Goteo", " | ".join(logs_misiones))
        
    return jsonify({"status": "ok", "actividad": reporte_general})

if __name__ == '__main__':
    app.run(debug=True)
