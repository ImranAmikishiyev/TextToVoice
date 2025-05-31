import telebot
import os
import time
import jwt
import requests
import json
import speech_recognition as sr
from pydub import AudioSegment

# === CONFIG ===
TELEGRAM_BOT_TOKEN = '7943310439:AAGlZ_pFE1VO9homhP_IP0dkYrKBoRuZS_I'
YANDEX_SERVICE_ACCOUNT_KEY_FILE = os.path.join(os.path.dirname(__file__), 'key.json')
FOLDER_ID = 'b1gi5iqh0sbq4ka4k35b'

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
user_texts = {}

# === Get Yandex IAM Token ===
def get_iam_token():
    with open(YANDEX_SERVICE_ACCOUNT_KEY_FILE, 'r') as f:
        data = json.load(f)

    now = int(time.time())
    payload = {
        'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
        'iss': data['service_account_id'],
        'iat': now,
        'exp': now + 360,
    }

    encoded_jwt = jwt.encode(
        payload,
        data['private_key'],
        algorithm='PS256',
        headers={'kid': data['id']}
    )

    response = requests.post(
        'https://iam.api.cloud.yandex.net/iam/v1/tokens',
        json={'jwt': encoded_jwt}
    )

    return response.json()['iamToken']

# === Handle text messages ===
@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    user_texts[chat_id] = message.text
    bot.send_message(chat_id, "Озвучиваю текст...")

    try:
        bot.send_chat_action(chat_id, 'record_voice')
        iam_token = get_iam_token()
        headers = {
            'Authorization': f'Bearer {iam_token}',
        }
        data = {
            'text': message.text,
            'lang': 'ru-RU',
            'voice': 'alena',
            'folderId': FOLDER_ID,
            'format': 'oggopus',
        }

        response = requests.post('https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize', headers=headers, data=data)
        if response.status_code == 200:
            with open("alice.ogg", "wb") as f:
                f.write(response.content)
            with open("alice.ogg", "rb") as voice:
                bot.send_voice(chat_id, voice)
            os.remove("alice.ogg")
        else:
            bot.send_message(chat_id, f"Ошибка от Алисы: {response.text}")

    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {e}")

# === Handle voice messages ===
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    chat_id = message.chat.id
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    ogg_path = 'voice.ogg'
    wav_path = 'voice.wav'

    with open(ogg_path, 'wb') as f:
        f.write(downloaded_file)

    # Convert OGG to WAV
    AudioSegment.from_file(ogg_path).export(wav_path, format='wav')

    # Speech recognition
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_path) as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data, language='ru-RU')
            bot.send_message(chat_id, f"Распознанный текст: {text}")
        except sr.UnknownValueError:
            bot.send_message(chat_id, "Не удалось распознать речь")
        except sr.RequestError as e:
            bot.send_message(chat_id, f"Ошибка распознавания: {e}")

    os.remove(ogg_path)
    os.remove(wav_path)

bot.polling(none_stop=True)
