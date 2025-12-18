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

# --- CREDENCIALES MAESTRAS (Verificadas) ---
# Usamos la MASTER KEY porque es la única que tiene acceso total garantizado
JSONBIN_API_KEY = "$2a$10$PLVbCTZpFi2EEtkKGOwUO09RFaMx53qA7iNx.sCNZEQ.9bW.leQK6".strip()

# Usamos el BIN ID que tiene los datos (el terminado en ...86f)
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

# --- UTILIDADES DE LA NUBE (Con Diagnóstico Avanzado) ---
def get_db():
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    # IMPORTANTE: Header para Master Key
    headers = {"X-Master-Key": JSONBIN_API_KEY}
    
    try:
        req = requests.get(url, headers=headers, timeout=10)
        
        if req.status_code == 200:
            return req.json().get("record", {})
        else:
            # SI FALLA: Mostramos la respuesta exacta de JsonBin para entender por qué
            error_msg = req.text # Esto nos dirá si es "Invalid Key" o "Bin not found"
            return {
                "targets": [], "missions": [],
                "logs": [{
                    "fecha": "ERROR", "usuario": "SISTEMA", "link": "#",
                    "accion": f"⚠️ FALLO {req.status_code}: {error_msg}"
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
    # IMPORTANTE: Header para Master Key también aquí
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
    # Si la DB falló al bajar, no intentamos subir nada
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
    selected_service = next((s for s in services if s['id
