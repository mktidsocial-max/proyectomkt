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

# --- IDs DE ESTRATEGIA ---
STRATEGY_IDS = {
    "likes": 410,    
    "views": 5559,   
    "saves": 4672,   
    "shares": 5870   
}

# --- UTILIDADES ---
def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)

# --- SISTEMA DE LOGS ---
def registrar_log(usuario, link, detalles):
    logs = load_json('logs.json')
    nuevo_log = {
        "fecha": datetime.now().strftime("%d/%m %H:%M"),
        "usuario": usuario,
        "link": link,
        "accion": detalles
    }
    # Guardamos el más nuevo arriba
    logs.insert(0, nuevo_log)
    # Mantenemos solo los últimos 50 eventos para no llenar memoria
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
#  PARTE B: CEREBRO ESTRATEGA (PROTEGIDO)
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
    
    # CARGAMOS OBJETIVOS E HISTORIAL
    targets = load_json('targets.json')
    logs = load_json('logs.json')
    
    return render_template('bot.html', targets=targets, logs=logs)

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

# --- EL MOTOR MATEMÁTICO ---
def ejecutar_estrategia_vip(link, user):
    log_acciones = []
    
    # 1. LIKES
    total_likes = random.randint(170, 300)
    max_tandas_posibles = total_likes // 10 
    if max_tandas_posibles >= 24: runs = 24; interval = 60 
    elif max_tandas_posibles >= 12: runs = 12; interval = 120 
    else: runs = max_tandas_posibles; interval = 1440 // runs 

    payload_likes = {
        'key': LEGION_API_KEY, 'action': 'add', 'service': STRATEGY_IDS['likes'],
        'link': link, 'quantity': total_likes, 'runs': runs, 'interval': interval
    }
    requests.post(LEGION_URL, data=payload_likes)
    log_acciones.append(f"❤️ {total_likes} Likes")

    # 2. VIEWS
    total_views = random.randint(2400, 3600)
    payload_views = {
        'key': LEGION_API_KEY, 'action': 'add', 'service': STRATEGY_IDS['views'],
        'link': link, 'quantity': total_views, 'runs': 24, 'interval': 60
    }
    requests.post(LEGION_URL, data=payload_views)
    log_acciones.append(f"👀 {total_views} Views")

    # 3. SAVES
    total_saves = random.randint(10, 20)
    requests.post(LEGION_URL, data={
        'key': LEGION_API_KEY, 'action': 'add', 'service': STRATEGY_IDS['saves'],
        'link': link, 'quantity': total_saves
    })
    log_acciones.append(f"💾 {total_saves} Saves")

    # 4. SHARES
    total_shares = random.randint(10, 15)
    requests.post(LEGION_URL, data={
        'key': LEGION_API_KEY, 'action': 'add', 'service': STRATEGY_IDS['shares'],
        'link': link, 'quantity': total_shares
    })
    log_acciones.append(f"🚀 {total_shares} Shares")
    
    # REGISTRAR
    resumen = " | ".join(log_acciones)
    registrar_log(user, link, resumen)
    
    return resumen

@app.route('/sistema/vigia-automatico')
def cron_vigia():
    targets = load_json('targets.json')
    L = instaloader.Instaloader()
    reporte = []
    cambios = False
    
    for t in targets:
        user = t['username']
        try:
            profile = instaloader.Profile.from_username(L.context, user)
            posts = profile.get_posts()
            
            # ANTI-FIJADOS: Tomamos 4 y buscamos el más nuevo por fecha
            candidatos = list(islice(posts, 4))
            
            if not candidatos: continue
            
            latest = max(candidatos, key=lambda p: p.date_utc)
            shortcode = latest.shortcode
            
            if shortcode != t['last_shortcode']:
                print(f"🚨 ESTRATEGIA ACTIVADA PARA {user}")
                link = f"https://www.instagram.com/p/{shortcode}/"
                
                res = ejecutar_estrategia_vip(link, user)
                
                t['last_shortcode'] = shortcode
                cambios = True
                reporte.append(f"✅ {user}: {res}")
            else:
                reporte.append(f"💤 {user}: Sin novedad")
        except Exception as e:
            reporte.append(f"❌ Error {user}: {str(e)}")
            
    if cambios: save_json('targets.json', targets)
    return jsonify({"status": "ok", "log": reporte})

if __name__ == '__main__':
    app.run(debug=True)
