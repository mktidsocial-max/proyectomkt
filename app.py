import os
import json
import requests
import instaloader
import mercadopago
from flask import Flask, request, render_template, jsonify, redirect, url_for

app = Flask(__name__)

# --- 1. CONFIGURACIÓN ---
# Render lee esto de las variables de entorno
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
LEGION_API_KEY = os.environ.get("LEGION_API_KEY")
LEGION_URL = "https://legionsmm.com/api/v2"

# Iniciamos MercadoPago
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# --- 2. HERRAMIENTAS PARA LEER JSON ---
def load_json(filename):
    """Lee un archivo JSON y devuelve una lista, o lista vacía si falla"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_json(filename, data):
    """Guarda datos en un archivo JSON"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


# ==========================================
#  PARTE A: LA TIENDA (Lo que ve el cliente)
# ==========================================

@app.route('/')
def home():
    # Carga los servicios del archivo y muestra la web
    services = load_json('services.json')
    return render_template('index.html', services=services)

@app.route('/comprar', methods=['POST'])
def comprar():
    # 1. Recibir datos del formulario
    service_id = int(request.form.get('service_id'))
    insta_link = request.form.get('link')
    quantity = int(request.form.get('quantity'))

    # 2. Buscar precio en el JSON
    services = load_json('services.json')
    selected_service = next((s for s in services if s['id'] == service_id), None)

    if not selected_service:
        return "Error: Servicio no encontrado", 400

    # 3. Calcular Precio
    calculated_price = (quantity / 1000) * selected_service['rate']
    
    # Regla del mínimo de $500
    final_price = calculated_price
    if final_price < 500:
        final_price = 500

    # 4. Crear Link de MercadoPago
    preference_data = {
        "items": [{
            "title": f"{selected_service['name']} (x{quantity})",
            "quantity": 1,
            "unit_price": float(final_price),
            "currency_id": "ARS"
        }],
        "metadata": {
            "legion_id": service_id,
            "quantity": quantity,
            "target_link": insta_link
        },
        "back_urls": {
            "success": "https://proyectomkt.onrender.com/", 
            "failure": "https://proyectomkt.onrender.com/"
        },
        "auto_return": "approved",
        "notification_url": "https://proyectomkt.onrender.com/webhook"
    }

    try:
        preference_response = sdk.preference().create(preference_data)
        return redirect(preference_response["response"]["init_point"])
    except Exception as e:
        return f"Error creando pago: {str(e)}", 500

@app.route('/webhook', methods=['POST'])
def webhook():
    # MercadoPago nos avisa aquí cuando alguien paga
    id = request.args.get('id')
    topic = request.args.get('topic')
    
    if topic == 'payment':
        payment_info = sdk.payment().get(id)
        if payment_info['response']['status'] == 'approved':
            meta = payment_info['response']['metadata']
            
            # Mandar orden a Legion
            payload = {
                'key': LEGION_API_KEY,
                'action': 'add',
                'service': meta['legion_id'],
                'link': meta['target_link'],
                'quantity': meta['quantity']
            }
            requests.post(LEGION_URL, data=payload)
            
    return jsonify({"status": "ok"}), 200


# ==========================================
#  PARTE B: EL BOT (Tu panel privado)
# ==========================================

@app.route('/admin/bot')
def bot_dashboard():
    # Muestra la nueva pantalla de control del bot
    targets = load_json('targets.json')
    return render_template('bot.html', targets=targets)

@app.route('/admin/bot/add', methods=['POST'])
def bot_add():
    # Agrega un nuevo cliente a la vigilancia
    username = request.form.get('username').replace('@', '').strip()
    service_id = int(request.form.get('service_id'))
    quantity = int(request.form.get('quantity'))
    
    targets = load_json('targets.json')
    
    # Evitar duplicados
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
    # Borra un cliente de la vigilancia
    targets = load_json('targets.json')
    targets = [t for t in targets if t['username'] != username]
    save_json('targets.json', targets)
    return redirect(url_for('bot_dashboard'))

@app.route('/sistema/vigia-automatico')
def cron_vigia():
    # ESTA RUTA LA VISITA CRON-JOB.ORG CADA 30 MIN
    targets = load_json('targets.json')
    L = instaloader.Instaloader()
    reporte = []
    cambios = False
    
    for t in targets:
        user = t['username']
        try:
            # Espiar perfil
            profile = instaloader.Profile.from_username(L.context, user)
            posts = profile.get_posts()
            latest = next(posts, None) # Tomar el post más reciente
            
            if not latest:
                continue
                
            shortcode = latest.shortcode # ID único del post
            
            # Si el post es nuevo (distinto al que teníamos guardado)
            if shortcode != t['last_shortcode']:
                print(f"🚨 DETECTADO NUEVO POST DE {user}")
                
                # 1. Comprar en Legion
                link = f"https://www.instagram.com/p/{shortcode}/"
                payload = {
                    'key': LEGION_API_KEY,
                    'action': 'add',
                    'service': t['service_id'],
                    'link': link,
                    'quantity': t['quantity']
                }
                
                # Enviamos la orden
                requests.post(LEGION_URL, data=payload)
                
                # 2. Actualizar memoria
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
