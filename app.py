import os
import mercadopago
import requests
from flask import Flask, request, render_template, jsonify, redirect

app = Flask(__name__)

# CONFIGURACIÓN (Render leerá esto de las variables secretas)
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
LEGION_API_KEY = os.environ.get("LEGION_API_KEY")
LEGION_URL = "https://legionsmm.com/api/v2"

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# TUS PRECIOS (Puedes editar esto luego)
SERVICES = {
    "likes_1000": {
        "legion_id": 1052,
        "price": 1500,
        "title": "1000 Likes Instagram",
        "quantity": 1000
    },
    "views_5000": {
        "legion_id": 450,
        "price": 2000,
        "title": "5000 Vistas Reels",
        "quantity": 5000
    }
}

@app.route('/')
def home():
    return render_template('index.html', services=SERVICES)

@app.route('/comprar', methods=['POST'])
def comprar():
    data = request.form
    service_code = data.get('service_code')
    insta_link = data.get('link')
    
    selected_service = SERVICES.get(service_code)
    if not selected_service: return "Error", 400

    preference_data = {
        "items": [{
            "title": selected_service['title'],
            "quantity": 1,
            "unit_price": selected_service['price'],
            "currency_id": "ARS"
        }],
        "metadata": {
            "legion_id": selected_service['legion_id'],
            "quantity": selected_service['quantity'],
            "target_link": insta_link
        },
        "back_urls": {
            "success": "https://www.google.com", 
            "failure": "https://www.google.com"
        },
        "auto_return": "approved",
        "notification_url": "https://proyectomkt.onrender.com/webhook"
    }

    preference_response = sdk.preference().create(preference_data)
    return redirect(preference_response["response"]["init_point"])

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
