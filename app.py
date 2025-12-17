import os
import json
import requests
import instaloader
import mercadopago
from flask import Flask, request, render_template, jsonify, redirect, url_for

app = Flask(__name__)

# CONFIGURACIÓN
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
LEGION_API_KEY = os.environ.get("LEGION_API_KEY")
LEGION_URL = "https://legionsmm.com/api/v2"

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# --- UTILIDADES JSON ---
def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

# --- RUTAS PÚBLICAS (VENTAS) ---
@app.route('/')
def home():
    services = load_json('services.json')
    return render_template('index.html', services=services)

@app.route('/comprar', methods=['POST'])
def comprar():
    # ... (Tu lógica de compra existente se mantiene igual) ...
    # Por brevedad, asumo que mantienes el código de compra aquí.
    # Si lo necesitas completo dímelo, pero es el mismo de antes.
    pass 
    # (NOTA: Copia y pega aquí tu función 'comprar' y 'webhook' del código anterior)

# --- RUTAS PRIVADAS (BOT AUTO-LIKES) ---

@app.route('/admin/bot')
def bot_dashboard():
    # Esta es la nueva sección visual
    targets = load_json('targets.json')
    return render_template('bot.html', targets=targets)

@app.route('/admin/bot/add', methods=['POST'])
def bot_add():
    username = request.form.get('username').replace('@', '').strip()
    service_id = int(request.form.get('service_id'))
    quantity = int(request.form.get('quantity'))
    
    targets = load_json('targets.json')
    
    # Verificar si ya existe
    for t in targets:
        if t['username'] == username:
            return "Error: Usuario ya está en vigilancia", 400
            
    new_target = {
        "username": username,
        "service_id": service_id,
        "quantity": quantity,
        "last_shortcode": None # Aquí guardaremos el ID del último post
    }
    
    targets.append(new_target)
    save_json('targets.json', targets)
    
    return redirect(url_for('bot_dashboard'))

@app.route('/admin/bot/delete/<username>')
def bot_delete(username):
    targets = load_json('targets.json')
    targets = [t for t in targets if t['username'] != username]
    save_json('targets.json', targets)
    return redirect(url_for('bot_dashboard'))

# --- EL MOTOR (CRON JOB) ---
@app.route('/sistema/vigia-automatico')
def cron_vigia():
    # Esta ruta se ejecuta cada 30 min via cron-job.org
    targets = load_json('targets.json')
    L = instaloader.Instaloader()
    reporte = []
    cambios = False
    
    for t in targets:
        user = t['username']
        try:
            profile = instaloader.Profile.from_username(L.context, user)
            posts = profile.get_posts()
            latest = next(posts, None)
            
            if not latest:
                continue
                
            shortcode = latest.shortcode
            
            # Si el post es distinto al último guardado
            if shortcode != t['last_shortcode']:
                print(f"🚨 DETECTADO NUEVO POST DE {user}")
                
                # 1. Enviar orden a Legion
                link = f"https://www.instagram.com/p/{shortcode}/"
                payload = {
                    'key': LEGION_API_KEY,
                    'action': 'add',
                    'service': t['service_id'],
                    'link': link,
                    'quantity': t['quantity']
                }
                
                # Descomentar para producción:
                requests.post(LEGION_URL, data=payload)
                
                # 2. Actualizar registro
                t['last_shortcode'] = shortcode
                cambios = True
                reporte.append(f"✅ {user}: Orden enviada para post {shortcode}")
            else:
                reporte.append(f"💤 {user}: Sin cambios")
                
        except Exception as e:
            reporte.append(f"❌ Error con {user}: {str(e)}")
            
    if cambios:
        save_json('targets.json', targets)
        
    return jsonify({"status": "ok", "log": reporte})

if __name__ == '__main__':
    app.run(debug=True)
