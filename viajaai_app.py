from flask import Flask, request, jsonify, render_template
import sqlite3
import requests
from twilio.rest import Client
import schedule
import time
import threading
import os
from datetime import datetime
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)

# Configurações do Twilio
TWILIO_SID = os.getenv('TWILIO_SID', 'SEU_TWILIO_SID')
TWILIO_TOKEN = os.getenv('TWILIO_TOKEN', 'SEU_TWILIO_TOKEN')
TWILIO_NUMBER = 'whatsapp:+14155238886'
client = Client(TWILIO_SID, TWILIO_TOKEN)

# Configuração do marcador (affiliate marker) da Travelpayouts
AFFILIATE_MARKER = os.getenv('AFFILIATE_MARKER', 'SEU_MARKER_AQUI')

# Banco de dados SQLite
conn = sqlite3.connect('viajaai.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    telefone TEXT,
    origem TEXT,
    destino TEXT,
    data TEXT,
    preco_max REAL
)''')
conn.commit()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/cadastro', methods=['POST'])
def cadastrar():
    dados = request.form
    cursor.execute('''INSERT INTO usuarios (nome, telefone, origem, destino, data, preco_max)
                      VALUES (?, ?, ?, ?, ?, ?)''',
                   (dados['nome'], dados['telefone'], dados['origem'],
                    dados['destino'], dados['data'], dados['preco_max']))
    conn.commit()
    return render_template('index.html', sucesso=True)

def buscar_promocao(origem, destino, data):
    try:
        url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
        headers = {
            "x-access-token": os.getenv('TRAVELPAYOUTS_TOKEN', 'SEU_TOKEN_AQUI')
        }
        params = {
            "origin": origem.upper(),
            "destination": destino.upper(),
            "departure_at": data,
            "currency": "BRL",
            "unique": False,
            "sorting": "price",
            "limit": 1
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("data"):
            preco = float(data["data"][0]["price"])
            return preco
    except Exception as e:
        print("Erro ao buscar promoção:", e)
    return 9999.0

def gerar_link_afiliado(origem, destino, data):
    return f"https://www.aviasales.com/search/{origem.upper()}{data[5:7]}{data[8:]}{destino.upper()}1?marker={AFFILIATE_MARKER}"

def enviar_alerta(telefone, mensagem):
    message = client.messages.create(
        body=mensagem,
        from_=TWILIO_NUMBER,
        to=f'whatsapp:{telefone}'
    )
    return message.sid

def verificar_promocoes():
    cursor.execute('SELECT * FROM usuarios')
    usuarios = cursor.fetchall()
    for usuario in usuarios:
        id, nome, telefone, origem, destino, data, preco_max = usuario
        preco = buscar_promocao(origem, destino, data)
        if preco <= preco_max:
            link = gerar_link_afiliado(origem, destino, data)
            msg = f"Olá {nome}, encontramos uma promoção de {origem} para {destino} por R$ {preco:.2f}!\nGaranta agora: {link}"
            enviar_alerta(telefone, msg)

# Inicia o agendador assim que o app carrega
t = threading.Thread(target=lambda: (schedule.every(6).hours.do(verificar_promocoes),
                                     [schedule.run_pending() or time.sleep(1) for _ in iter(int, 1)]))
t.daemon = True
t.start()
