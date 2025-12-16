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

# BASE DE DATOS DE SERVICIOS (ID Legion: Precio x 1000)
# Esto coincide con la tabla de tu HTML
SERVICES_RATES = {
    "410":  {"rate": 2700, "name": "Likes USA - Mixto"},
    "3878": {"rate": 2900, "name": "Likes USA - Femeninos"},
    "417":  {"rate": 14000,"name": "Likes USA + Alcance + Visitas"},
    "2326": {"rate": 2300, "name": "Likes + Alcance + Impresiones"},
    "390":  {"rate": 4200, "name": "Likes Brasil"},
    "2055": {"rate": 397,  "name": "Impresiones (Foto/Reel)"},
    "2704": {"rate": 17000,"name": "Comentarios Positivos"},
    "5924": {"rate": 10000,"name": "Comentarios Negativos 1"},
    "5923": {"rate": 10000,"name": "Comentarios Negativos 2"}
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/comprar', methods=['POST'])
def comprar():
    # 1. Recibir datos del formulario HTML
    service_id = request.form.get('service_id')
    insta_link = request.form.get('link')
    quantity = int(request.form.get('quantity'))

    # 2. Buscar datos del servicio
    service_info = SERVICES_RATES.get(service_id)
    if not service_info:
        return "Error: Servicio no encontrado", 400

    # 3. Calcular Precio Total (Matemática: (Cantidad / 1000) * Precio_x_1000)
    unit_price = (quantity / 1000) * service_info['rate']
    
    # Asegurar que el precio tenga formato correcto (mínimo 1 peso para evitar errores)
    if unit_price < 1: unit_price = 1

    # 4. Crear Preferencia de MercadoPago
    preference_data = {
        "items": [{
            "title": f"{service_info['name']} (x{quantity})",
            "quantity": 1,
            "unit_price": float(unit_price),
            "currency_id": "ARS"
        }],
        "metadata": {
            "legion_id": service_id,
            "quantity": quantity,
            "target_link": insta_link
        },
        "back_urls": {
            "success": "https://tusitio.onrender.com/", # OJO: Cambia esto si quieres una pag de gracias
            "failure": "https://tusitio.onrender.com/"
        },
        "auto_return": "approved",
        "notification_url": "https://proyectomkt.onrender.com/webhook" # Tu URL de Webhook real
    }

    try:
        preference_response = sdk.preference().create(preference_data)
        # Redirigir al usuario a pagar a MercadoPago
        return redirect(preference_response["response"]["init_point"])
    except Exception as e:
        return f"Error creando pago: {str(e)}", 500

@app.route('/webhook', methods=['POST'])
def webhook():
    # Tu lógica original intacta, solo asegura procesar bien la metadata
    id = request.args.get('id')
    topic = request.args.get('topic')
    
    if topic == 'payment':
        payment_info = sdk.payment().get(id)
        if payment_info['response']['status'] == 'approved':
            meta = payment_info['response']['metadata']
            
            # EJECUTAR ORDEN EN LEGION
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
    # Gunicorn maneja esto en producción, esto es solo para local
    app.run(debug=True)
