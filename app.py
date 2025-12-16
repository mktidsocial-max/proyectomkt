import os
import json
import mercadopago
import requests
from flask import Flask, request, render_template, jsonify, redirect

app = Flask(__name__)

# CONFIGURACIÓN
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
LEGION_API_KEY = os.environ.get("LEGION_API_KEY")
LEGION_URL = "https://legionsmm.com/api/v2"

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# FUNCIÓN PARA CARGAR SERVICIOS DESDE JSON
def load_services():
    try:
        with open('services.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando services.json: {e}")
        return []

@app.route('/')
def home():
    # Cargar servicios y enviarlos al HTML
    services = load_services()
    return render_template('index.html', services=services)

@app.route('/comprar', methods=['POST'])
def comprar():
    service_id = int(request.form.get('service_id')) # ID viene como string, convertir a int
    insta_link = request.form.get('link')
    quantity = int(request.form.get('quantity'))

    # Buscar el servicio en el JSON
    services = load_services()
    selected_service = next((s for s in services if s['id'] == service_id), None)

    if not selected_service:
        return "Error: Servicio no encontrado", 400

    # 1. CÁLCULO DEL PRECIO
    calculated_price = (quantity / 1000) * selected_service['rate']
    
    # 2. REGLA DEL MÍNIMO ($500 ARS)
    final_price = calculated_price
    if final_price < 500:
        final_price = 500

    # Crear Preferencia
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
    id = request.args.get('id')
    topic = request.args.get('topic')
    
    if topic == 'payment':
        payment_info = sdk.payment().get(id)
        if payment_info['response']['status'] == 'approved':
            meta = payment_info['response']['metadata']
            
            payload = {
                'key': LEGION_API_KEY,
                'action': 'add',
                'service': meta['legion_id'],
                'link': meta['target_link'],
                'quantity': meta['quantity']
            }
            requests.post(LEGION_URL, data=payload)
            
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(debug=True)
