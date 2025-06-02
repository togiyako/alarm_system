import os
import sys
import logging
import base64
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from Crypto.Cipher import ChaCha20
import requests

# 🔧 Негайний вивід логів у stdout (важливо для Render)
sys.stdout.reconfigure(line_buffering=True)

# 🔧 Налаштування логування
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

app = Flask(__name__)

# 🔐 Зчитування токена з середовища (замість захардкоженого токена)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_IDS = ['962377746', '622093459']  # Замінити при потребі

# 🔑 32-байтовий ключ ChaCha20 (той самий, що і на ESP32)
KEY = bytes(range(0x00, 0x20))  # [0x00 до 0x1F включно]


def send_telegram_alert(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chat_id in TELEGRAM_CHAT_IDS:
        payload = {"chat_id": chat_id, "text": message}
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            logging.error(f"❌ Не вдалося надіслати в Telegram (chat_id: {chat_id}): {response.text}")
        else:
            logging.info(f"✅ Надіслано в Telegram (chat_id: {chat_id})")


def decrypt_payload(nonce_b64: str, data_b64: str) -> str:
    nonce = base64.b64decode(nonce_b64)
    ciphertext = base64.b64decode(data_b64)
    cipher = ChaCha20.new(key=KEY, nonce=nonce)
    plaintext = cipher.decrypt(ciphertext)
    return plaintext.decode('utf-8')


@app.route('/notify', methods=['POST'])
def notify():
    payload = request.get_json(silent=True)
    logging.info(f"📦 Отримано payload: {payload}")

    if not payload or 'nonce' not in payload or 'data' not in payload:
        return jsonify({"status": "invalid request"}), 400

    try:
        decrypted = decrypt_payload(payload['nonce'], payload['data'])
        logging.info(f"🔓 Дешифровано JSON: {decrypted}")
        data = json.loads(decrypted)
    except Exception as e:
        logging.error(f"❌ Помилка дешифрування або парсингу: {e}")
        return jsonify({"status": "decryption error"}), 400

    ts = (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
    if data.get('motion'):
        msg = f"🚨 Рух виявлено!\n🕒 {ts}"
    elif data.get('gas'):
        msg = f"🔥 Виявлено вогонь!\n🕒 {ts}"
    else:
        return jsonify({"status": "unknown payload"}), 400

    logging.info(msg)
    send_telegram_alert(msg)
    return jsonify({"status": "alert sent"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, threaded=True)
