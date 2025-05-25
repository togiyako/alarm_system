from flask import Flask, request, jsonify
from datetime import datetime
import requests
import base64
import json
from Crypto.Cipher import ChaCha20

app = Flask(__name__)

# 🔧 Заміни цими даними свої значення
TELEGRAM_BOT_TOKEN = '8021494403:AAGgznbcZnuxgvhBcMtyOiFmk9w5OLPXwqQ'
TELEGRAM_CHAT_ID = '962377746'

# Ваш 32‑байтовий ключ (той самий, що й на ESP32)
KEY = bytes([
    0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,
    0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,
    0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,
    0x18,0x19,0x1A,0x1B,0x1C,0x1D,0x1E,0x1F
])


def send_telegram_alert(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        print("❌ Не вдалося надіслати повідомлення в Telegram:", r.text)
    else:
        print("✅ Повідомлення надіслано в Telegram")


def decrypt_payload(nonce_b64: str, data_b64: str) -> str:
    # Base64 decode
    raw = base64.b64decode(nonce_b64)
    # Use full 12-byte nonce (8 bytes random + 4 bytes counter)
    nonce = raw
    ciphertext = base64.b64decode(data_b64)

    # Create cipher using full nonce
    cipher = ChaCha20.new(key=KEY, nonce=nonce)
    plaintext = cipher.decrypt(ciphertext)
    return plaintext.decode('utf-8')

@app.route('/notify', methods=['POST'])
def notify():
    payload = request.get_json(silent=True)
    print("Received payload:", payload)
    if not payload or 'nonce' not in payload or 'data' not in payload:
        return jsonify({"status": "invalid request"}), 400

    try:
        decrypted = decrypt_payload(payload['nonce'], payload['data'])
        print("Decrypted JSON:", decrypted)
        data = json.loads(decrypted)
    except Exception as e:
        print("❌ Помилка дешифрування або парсингу:", e)
        return jsonify({"status": "decryption error"}), 400

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if data.get('motion'):
        msg = f"🚨 Рух виявлено!\n🕒 {ts}"
    elif data.get('gas'):
        msg = f"🔥 Виявлено вогонь!\n🕒 {ts}"
    else:
        return jsonify({"status": "unknown payload"}), 400

    print(msg)
    send_telegram_alert(msg)
    return jsonify({"status": "alert sent"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, threaded=True)

