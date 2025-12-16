import os
import mercadopago
import requests
from flask import Flask, request, render_template, jsonify, redirect

app = Flask(__name__)

# CONFIGURACIÓN (Render lee esto de las Environment Variables)
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
LEGION_API_KEY = os.environ.get("LEGION_API_KEY")
LEGION_URL = "https://legionsmm.com/api/v2"

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# BASE DE DATOS DE SERVICIOS
# (Títulos originales restaurados)
SERVICES_RATES = {
    "410":  {"rate": 2700, "name": "Me gusta USA - Mixto -"},
    "3878": {"rate": 2900, "name": "Me gusta USA - Mayormente femeninos"},
    "417":  {"rate": 14000,"name": "Me gusta USA + Alcance + Impresiones + Visitas al perfil."},
    "2326": {"rate": 2300, "name": "Me gusta + Alcance + Impresiones."},
    "390":  {"rate": 4200, "name": "Me gusta Brasil"},
    "2055": {"rate": 397,  "name": "IMPRESIONES PUBLICACIONES (Foto y Reel)"},
    "2704": {"rate": 17000,"name": "Comentarios - Emoji positivos mixtos [😘💞💐🏵️😍🤩]"},
    "5924": {"rate": 10000,"name": "Comentarios - Emoji NEGATIVOS mixtos [💩👎🏼🤢😡🤬]"},
    "5923": {"rate": 10000,"name": "Comentarios - Emoji NEGATIVOS mixtos [😔🤮💔😈🥵]"}
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/comprar', methods=['POST'])
def comprar():
    service_id = request.form.get('service_id')
    insta_link = request.form.get('link')
    quantity = int(request.form.get('quantity'))

    service_info = SERVICES_RATES.get(service_id)
    if not service_info:
        return "Error: Servicio no encontrado", 400

    # 1. CÁLCULO DEL PRECIO
    calculated_price = (quantity / 1000) * service_info['rate']
    
    # 2. REGLA DEL MÍNIMO ($500 ARS)
    final_price = calculated_price
    if final_price < 500:
        final_price = 500

    # Crear Preferencia de MercadoPago
    preference_data = {
        "items": [{
            "title": f"{service_info['name']} (x{quantity})",
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
