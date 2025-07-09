import random
import uuid
import os
import re
from datetime import datetime
from io import BytesIO
import json
import csv
import asyncio

import logging
from logging.handlers import RotatingFileHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)


import qrcode
from PIL import Image

import zipfile
import requests
import time
from telegram.ext import ApplicationBuilder
from aiohttp import web

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'bot.log',
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
    ]
)

TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN не установлен в переменных окружения!")

WEBHOOK_URL = os.getenv('WEBHOOK_URL')
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL не установлен в переменных окружения!")

application = None

user_data = {}

MAX_MESSAGE_LENGTH = 4096

SUPPORTED_ZIP_FORMATS = ['.zip', '.mcpack', '.mcworld', '.mctemplate', '.mcaddon']

MAX_FILE_SIZE_MB = 50
MAX_ITEMS = 500
MAX_RETRIES = 3

ZALGO_UP = ['̍', '̎', '̄', '̅', '̿', '̑', '̆', '̐', '͒', '͗', '͑', '̇', '̈', '̊', '͂', '̓', '̈́', '͊', '͋', '͌', '̃', '̂', '̌']
ZALGO_DOWN = ['̖', '̗', '̘', '̙', '̜', '̝', '̞', '̟', '̠', '̤', '̥', '̦', '̩', '̪', '̫', '̬', '̭', '̮', '̯', '̰', '̱', '̲', '̳']
ZALGO_MID = ['̕', '̛', '̀', '́', '͘', '̡', '̢', '̧', '̹', '̺', '̻', '̼', 'ͅ', '͇', '͈', '͉', '͍', '͎', '͓', '͔', '͕', '͖']

SLAVIC_COMBINING = ['ⷠ', 'ⷡ', 'ⷢ', 'ⷣ', 'ⷤ', 'ⷥ', 'ⷦ', 'ⷧ', 'ⷨ', 'ⷩ', 'ⷪ', 'ⷫ', 'ⷬ', 'ⷭ', 'ⷮ', 'ⷯ', 'ⷰ', 'ⷱ', 'ⷲ', 'ⷳ', 'ⷴ', 'ⷵ', 'ⷶ', 'ⷷ', 'ⷸ', 'ⷹ', 'ⷺ', 'ⷻ', 'ⷼ', 'ⷽ', 'ⷾ', 'ⷿ', 'ꙵ', 'ꙷ', 'ꙸ', 'ꙹ', 'ꙺ']

CYRILLIC_TO_SLAVIC = {
    'а': 'ⷶ', 'б': 'ⷠ', 'в': 'ⷡ', 'г': 'ⷢ', 'д': 'ⷣ', 'е': 'ⷷ', 'ё': 'ⷷ', 'ж': 'ⷤ', 'з': 'ⷥ', 'и': 'ꙵ',
    'й': 'ꙵ', 'к': 'ⷦ', 'л': 'ⷧ', 'м': 'ⷨ', 'н': 'ⷩ', 'о': 'ⷪ', 'п': 'ⷫ', 'р': 'ⷬ', 'с': 'ⷭ', 'т': 'ⷮ',
    'у': 'ꙷ', 'ф': 'ⷴ', 'х': 'ⷯ', 'ц': 'ⷰ', 'ч': 'ⷱ', 'ш': 'ⷲ', 'щ': 'ⷳ', 'ъ': 'ꙸ', 'ы': 'ꙹ', 'ь': 'ꙺ',
    'э': 'ⷷ', 'ю': 'ⷻ', 'я': 'ⷶ'
}

ARROWS = ['↗️', '↖️', '↘️', '↙️', '➡️', '⬅️', '⬆️', '⬇️', '→', '←', '↑', '↓', '⇐', '⇒', '⇑', '⇓', '↔️', '↕️', '⟶', '⟵', '⟷', '⟴']
HIEROGLYPHS = ['漢', '字', '愛', '美', '龍', '風', '天', '地', '山', '川', '日', '月', '星', '花', '木', '水']
UNUSUAL_SYMBOLS = [
    ('¬', 'U+00AC', 'Not Sign'), ('¶', 'U+00B6', 'Pilcrow Sign'), ('§', 'U+00A7', 'Section Sign'),
    ('†', 'U+2020', 'Dagger'), ('‡', 'U+2021', 'Double Dagger'), ('ℵ', 'U+2135', 'Alef Symbol'),
    ('∞', 'U+221E', 'Infinity'), ('∅', 'U+2205', 'Empty Set'), ('∆', 'U+2206', 'Increment'),
    ('∫', 'U+222B', 'Integral'), ('∮', 'U+222E', 'Contour Integral'), ('√', 'U+221A', 'Square Root'),
    ('∝', 'U+221D', 'Proportional To'), ('≠', 'U+2260', 'Not Equal To'), ('≈', 'U+2248', 'Almost Equal To'),
    ('∑', 'U+2211', 'Summation'), ('∏', 'U+220F', 'Product'), ('⊥', 'U+22A5', 'Perpendicular'),
    ('⊗', 'U+2297', 'Circled Times'), ('◊', 'U+25CA', 'Lozenge'), ('⁂', 'U+2042', 'Asterism'),
    ('⌈', 'U+2308', 'Left Ceiling'), ('⌋', 'U+230B', 'Right Floor'), ('⁗', 'U+2057', 'Quadruple Prime'),
    ('Ꝟ', 'U+A75E', 'Latin Capital Letter Vend'), ('ꟻ', 'U+A7FB', 'Latin Epigraphic Letter Reversed F'),
    ('Ꚙ', 'U+A698', 'Cyrillic Capital Letter Double O'), ('Ꜣ', 'U+A722', 'Egyptological Alef')
]
ALL_SYMBOLS = ARROWS + HIEROGLYPHS + [s[0] for s in UNUSUAL_SYMBOLS]

custom_alphabet = {
    "А": ["А", "А҆", "А҇", "Ꙙ", "ꙙ", "А̄", "Ӑ", "А̇", "А̋", "А̌", "А̑", "А̒", "А̕", "А̖", "Ꙛ", "ꙛ"],
    "Б": ["Б", "Б҆", "Б҇", "Ꙋ", "ꙋ", "Б̄", "Б̆", "Б̇", "Б̋", "Б̌", "Б̑", "Б̒", "Б̕", "Б̖"],
    "В": ["В", "В҆", "В҇", "В̄", "В̆", "В̇", "В̋", "В̌", "В̑", "В̒", "В̕", "В̖"],
    "Г": ["Г", "Г҆", "Г҇", "Ґ", "Г̄", "Г̆", "Г̇", "Г̋", "Г̌", "Г̑", "Г̒", "Г̕", "Г̖"],
    "Д": ["Д", "Д҆", "Д҇", "Д̄", "Д̆", "Д̇", "Д̋", "Д̌", "Д̑", "Д̒", "Д̕", "Д̖"],
    "Е": ["Е", "Е҆", "Е҇", "Є", "Ё", "Е̄", "Ӗ", "Е̇", "Е̋", "Е̌", "Е̑", "Е̒", "Е̕", "Е̖"],
    "Ж": ["Ж", "Ж҆", "Ж҇", "Ꙗ", "ꙗ", "Ж̄", "Ӂ", "Ж̇", "Ж̋", "Ж̌", "Ж̑", "Ж̒", "Ж̕", "Ж̖"],
    "З": ["З", "З҆", "З҇", "Ꙁ", "ꙁ", "Ꙃ", "ꙃ", "З̇", "З̋", "З̌", "З̑", "З̒", "З̕", "З̖"],
    "И": ["И", "И҆", "И҇", "І", "Ї", "Ӣ", "Й", "И̇", "И̋", "И̌", "И̑", "И̒", "И̕", "И̖"],
    "Й": ["Й", "Й҆", "Й҇", "Й̄", "Й̆", "Й̇", "Й̋", "Й̌", "Й̑", "Й̒", "Й̕", "Й̖"],
    "К": ["К", "К҆", "К҇", "Ꙉ", "ꙉ", "К̄", "К̆", "К̇", "К̋", "К̌", "К̑", "К̒", "К̕", "К̖"],
    "Л": ["Л", "Л҆", "Л҇", "Ꙋ", "ꙋ", "Л̄", "Л̆", "Л̇", "Л̋", "Л̌", "Л̑", "Л̒", "Л̕", "Л̖"],
    "М": ["М", "М҆", "М҇", "Ꙍ", "ꙍ", "М̄", "М̆", "М̇", "М̋", "М̌", "М̑", "М̒", "М̕", "М̖"],
    "Н": ["Н", "Н҆", "Н҇", "Ꙏ", "ꙏ", "Н̄", "Н̆", "Н̇", "Н̋", "Н̌", "Н̑", "Н̒", "Н̕", "Н̖"],
    "О": ["О", "О҆", "О҇", "Ꙋ", "ꙋ", "О̄", "О̆", "О̇", "О̋", "О̌", "О̑", "О̒", "О̕", "О̖"],
    "П": ["П", "П҆", "П҇", "Ꙍ", "ꙍ", "П̄", "П̆", "П̇", "П̋", "П̌", "П̑", "П̒", "П̕", "П̖"],
    "Р": ["Р", "Р҆", "Р҇", "Ꙑ", "ꙑ", "Р̄", "Р̆", "Р̇", "Р̋", "Р̌", "Р̑", "Р̒", "Р̕", "Р̖"],
    "С": ["С", "С҆", "С҇", "Ꙓ", "ꙓ", "С̄", "С̆", "С̇", "С̋", "С̌", "С̑", "С̒", "С̕", "С̖"],
    "Т": ["Т", "Т҆", "Т҇", "Ꙕ", "ꙕ", "Т̄", "Т̆", "Т̇", "Т̋", "Т̌", "Т̑", "Т̒", "Т̕", "Т̖"],
    "У": ["У", "У҆", "У҇", "Ў", "Ꙗ", "Ӯ", "Ў", "У̇", "Ӳ", "У̌", "У̑", "У̒", "У̕", "У̖"],
    "Ф": ["Ф", "Ф҆", "Ф҇", "Ꙙ", "ꙙ", "Ф̄", "Ф̆", "Ф̇", "Ф̋", "Ф̌", "Ф̑", "Ф̒", "Ф̕", "Ф̖"],
    "Х": ["Х", "Х҆", "Х҇", "Ꙛ", "ꙛ", "Х̄", "Х̆", "Х̇", "Х̋", "Х̌", "Х̑", "Х̒", "Х̕", "Х̖"],
    "Ц": ["Ц", "Ц҆", "Ц҇", "Ꙝ", "ꙝ", "Ц̄", "Ц̆", "Ц̇", "Ц̋", "Ц̌", "Ц̑", "Ц̒", "Ц̕", "Ц̖", "Ꚅ", "ꚅ"],
    "Ч": ["Ч", "Ч҆", "Ч҇", "Ч̄", "Ч̆", "Ч̇", "Ч̋", "Ч̌", "Ч̑", "Ч̒", "Ч̕", "Ч̖", "Ꚇ", "ꚇ"],
    "Ш": ["Ш", "Ш҆", "Ш҇", "Ꙡ", "ꙡ", "Ш̄", "Ш̆", "Ш̇", "Ш̋", "Ш̌", "Ш̑", "Ш̒", "Ш̕", "Ш̖", "Ꚉ", "ꚉ"],
    "Щ": ["Щ", "Щ҆", "Щ҇", "Ꙣ", "ꙣ", "Щ̄", "Щ̆", "Щ̇", "Щ̋", "Щ̌", "Щ̑", "Щ̒", "Щ̕", "Щ̖", "Ꚗ", "ꚗ"],
    "Ъ": ["Ъ", "Ъ҆", "Ъ҇", "Ꙥ", "ꙥ", "Ъ̄", "Ъ̆", "Ъ̇", "Ъ̋", "Ъ̌", "Ъ̑", "Ъ̒", "Ъ̕", "Ъ̖"],
    "Ы": ["Ы", "Ы҆", "Ы҇", "Ꙧ", "ꙧ", "Ы̄", "Ы̆", "Ы̇", "Ы̋", "Ы̌", "Ы̑", "Ы̒", "Ы̕", "Ы̖"],
    "Ь": ["Ь", "Ь҆", "Ь҇", "Ꙩ", "ꙩ", "Ь̄", "Ь̆", "Ь̇", "Ь̋", "Ь̌", "Ь̑", "Ь̒", "Ь̕", "Ь̖"],
    "Э": ["Э", "Э҆", "Э҇", "Ꙫ", "ꙫ", "Э̄", "Э̆", "Э̇", "Э̋", "Э̌", "Э̑", "Э̒", "Э̕", "Э̖"],
    "Ю": ["Ю", "Ю҆", "Ю҇", "Ю̄", "Ю̆", "Ю̇", "Ю̋", "Ю̌", "Ю̑", "Ю̒", "Ю̕", "Ю̖", "Ꙕ", "ꙕ", "Ꙝ", "ꙝ"],
    "Я": ["Я", "Я҆", "Я҇", "Я̄", "Я̆", "Я̇", "Я̋", "Я̌", "Я̑", "Я̒", "Я̕", "Я̖"]
}

PHONE_PREFIXES = ['+7 (999)', '+7 (926)', '+7 (495)', '+7 (812)', '+7 (903)']

EMAIL_DOMAINS = ['@test.com', '@fake.com']

PASSWORD_CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

SUPPORTED_FILE_TYPES = {
    'text/plain': ['.txt', '.md'],
    'application/json': ['.json'],
    'text/x-python': ['.py'],
    'text/csv': ['.csv'],
    'text/html': ['.html'],
    'text/css': ['.css'],
    'text/javascript': ['.js']
}

async def clear_user_data(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data
    await asyncio.sleep(600)
    if user_id in user_data and 'last_activity' in user_data[user_id]:
        if (datetime.now() - user_data[user_id]['last_activity']).total_seconds() >= 600:
            user_data.pop(user_id, None)
            logging.info(f"Очищено состояние пользователя {user_id} по таймауту")

def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list:
    if len(text) <= max_length:
        return [text.rstrip('\n')]
    parts = []
    current_part = ""
    lines = text.split('\n')
    for line in lines:
        line = line.rstrip()
        if len(current_part) + len(line) + 1 <= max_length - 20:
            current_part += line + "\n"
        else:
            if current_part:
                parts.append(current_part.rstrip('\n'))
            current_part = line + "\n"
    if current_part:
        parts.append(current_part.rstrip('\n'))
    return parts

def is_cyrillic(text: str) -> bool:
    return all(char in CYRILLIC_TO_SLAVIC or char.isspace() or char.upper() in custom_alphabet for char in text.lower())

# Генерация Zalgo-текста (обычногоо)
def generate_zalgo(text: str, intensity: str = 'medium', direction: str = 'both', mode: str = 'normal', overlay_text: str = None) -> str:
    result = ""
    intensity_map = {'light': 2, 'medium': 5, 'heavy': 10, 'absolute': 15, 'destroyer': 22}
    num_chars = intensity_map.get(intensity, 5)
    max_zalgo = 22
    if any(ord(char) > 0xFFFF for char in text + (overlay_text or '')):
        return "😅 Ты, конечно, офигел с этими смайликами! Введи текст на русском без эмодзи."
    estimated_length = len(text) * (1 + num_chars * (3 if mode == 'normal' else 1))
    if estimated_length > MAX_MESSAGE_LENGTH:
        return f"❌ Текст слишком длинный! Максимум {MAX_MESSAGE_LENGTH // (1 + num_chars * 3)} символов."
    if mode == 'custom':
        if not overlay_text or not is_cyrillic(text) or not is_cyrillic(overlay_text):
            return "❌ Слово снизу и сверху должны быть на русском языке (кириллица)!"
        min_length = min(len(text), len(overlay_text))
        for i in range(min_length):
            char = text[i]
            if char.isspace():
                result += " "
            else:
                overlay_char = overlay_text[i].lower()
                result += char + (CYRILLIC_TO_SLAVIC.get(overlay_char, char))
        if len(text) > min_length:
            result += text[min_length:]
        return result
    else:
        for char in text:
            result += char
            if direction in ['up', 'both']:
                for _ in range(random.randint(1, min(num_chars, max_zalgo))):
                    result += random.choice(ZALGO_UP)
            if direction == 'both':
                for _ in range(random.randint(1, min(num_chars, max_zalgo))):
                    result += random.choice(ZALGO_MID)
            if direction in ['down', 'both']:
                for _ in range(random.randint(1, min(num_chars, max_zalgo))):
                    result += random.choice(ZALGO_DOWN)
        return result

# Генерация случайного алфавита на основе кириллицы
def generate_random_alphabet(text: str) -> str:
    if not is_cyrillic(text.upper()):
        return "❌ Текст должен быть на русском языке (кириллица)!"
    if len(text) * 2 > MAX_MESSAGE_LENGTH:
        return f"❌ Текст слишком длинный! Максимум {MAX_MESSAGE_LENGTH // 2} символов."
    result = ""
    for char in text.upper():
        if char in custom_alphabet:
            result += random.choice(custom_alphabet[char])
        else:
            result += char
    return result

def encrypt_to_unicode(text: str) -> str:
    return ''.join(f'\\u{ord(char):04x}' if char.isalpha() else char for char in text)

def decrypt_from_unicode(text: str) -> str:
    try:
        parts = re.split(r'(\\u[0-9a-fA-F]{4})', text)
        result = ''
        for part in parts:
            if re.match(r'\\u[0-9a-fA-F]{4}', part):
                result += chr(int(part[2:], 16))
            else:
                result += part
        return result
    except ValueError:
        return "❌ Ошибка: коды должны быть в формате \\uXXXX (4 hex-цифры, например, \\u0048)!"

def remove_newlines(text: str) -> str:
    return text.replace('\r\n', '').replace('\n', '').replace('\r', '')

def generate_phone_number() -> str:
    prefix = random.choice(PHONE_PREFIXES)
    number = ''.join([str(random.randint(0, 9)) for _ in range(7)])
    return f"{prefix} {number[:3]}-{number[3:5]}-{number[5:]}"

def generate_temp_email() -> str:
    username = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))
    domain = random.choice(EMAIL_DOMAINS)
    return f"{username}{domain}"

def generate_password() -> str:
    return ''.join(random.choices(PASSWORD_CHARS, k=12))

def get_exchange_rates() -> dict:
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/RUB", timeout=5)
        response.raise_for_status()
        data = response.json()
        rates = data['rates']
        return {
            'EUR': 1 / rates['EUR'],
            'USD': 1 / rates['USD'],
            'GBP': 1 / rates['GBP'],
            'date': data['date']
        }
    except requests.RequestException:
        return None

# Извлечение текста из загруженного файла
def extract_text_from_file(file_content: bytes, file_name: str, mime_type: str = None) -> tuple[str, str]:
    extension = '.' + file_name.split('.')[-1].lower()
    logging.info(f"Processing file: {file_name}, extension: {extension}, mime_type: {mime_type}")

    try:
        if not file_content:
            logging.warning(f"File {file_name} is empty")
            return None, "❌ Файл пустой!"

        supported_extensions = []
        for mime, exts in SUPPORTED_FILE_TYPES.items():
            supported_extensions.extend(exts)
        if extension not in supported_extensions:
            logging.warning(f"Unsupported extension {extension} for file {file_name}")
            return None, f"❌ Неподдерживаемый формат файла! Поддерживаются: {', '.join(supported_extensions)}"
        try:
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            logging.error(f"Failed to decode {file_name} as UTF-8")
            return None, "❌ Ошибка: файл не в кодировке UTF-8!"

        if (extension in SUPPORTED_FILE_TYPES['text/plain'] or
                extension in SUPPORTED_FILE_TYPES['text/x-python'] or
                extension in SUPPORTED_FILE_TYPES['text/html'] or
                extension in SUPPORTED_FILE_TYPES['text/css'] or
                extension in SUPPORTED_FILE_TYPES['text/javascript'] or
                extension in SUPPORTED_FILE_TYPES['application/json']):
            return text, None
        elif extension == '.csv':
            lines = text.splitlines()
            reader = csv.reader(lines)
            return '\n'.join([','.join(row) for row in reader]), None
        else:
            logging.warning(f"Unexpected extension {extension} for file {file_name}")
            return None, f"❌ Неподдерживаемый формат файла! Поддерживаются: {', '.join(supported_extensions)}"

    except Exception as e:
        logging.error(f"Unexpected error processing {file_name}: {e}")
        return None, f"❌ Неожиданная ошибка при обработке файла: {str(e)}"

# Создание текстового файла в памяти
def create_txt_file(content: str, file_name: str) -> BytesIO:
    bio = BytesIO()
    bio.write(content.encode('utf-8'))
    bio.seek(0)
    bio.name = f"{file_name}.txt"
    return bio

# Анализ структуры ZIP-архива с прогрессом очень сложна ток для гениев, а еще именно на этом моменте хочу пожаловаться что я задолбался расставлять смайлики
async def analyze_zip(file_content: bytes, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    structure = []
    file_size_mb = len(file_content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return f"❌ Архив слишком большой ({file_size_mb:.2f} МБ > {MAX_FILE_SIZE_MB} МБ)!"
    try:
        with zipfile.ZipFile(BytesIO(file_content)) as z:
            file_list = z.infolist()
            total_items = len(file_list)
            if total_items > MAX_ITEMS:
                return f"❌ Слишком много элементов ({total_items} > {MAX_ITEMS})!"
            progress_message = await update.message.reply_text("⏳ Анализ архива: 0%", parse_mode='HTML')
            for i, file_info in enumerate(file_list):
                name = file_info.filename
                if not file_info.is_dir():
                    structure.append(f"📄 <code>{name}</code>")
                else:
                    structure.append(f"📁 <code>{name}</code>")
                progress = (i + 1) * 100 // total_items
                if (i + 1) % max(1, total_items // 10) == 0 or i == total_items - 1:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=progress_message.message_id,
                        text=f"⏳ Анализ архива: {progress}%",
                        parse_mode='HTML'
                    )
                    await asyncio.sleep(0.1)
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=progress_message.message_id
            )
        return "\n".join(structure) if structure else "❌ Архив пуст!"
    except zipfile.BadZipFile:
        return "❌ Это не валидный ZIP-архив!"
    except Exception as e:
        logging.error(f"Ошибка анализа ZIP: {e}")
        return "❌ Произошла ошибка при анализе архива!"

# Создание ZIP из папки
def create_zip_from_folder(zip_data: bytes, folder_path: str) -> BytesIO:
    input_zip = zipfile.ZipFile(BytesIO(zip_data))
    output_zip = BytesIO()
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        for file_info in input_zip.infolist():
            if file_info.filename.startswith(folder_path) and not file_info.is_dir():
                file_content = input_zip.read(file_info.filename)
                if file_content:
                    relative_path = file_info.filename[len(folder_path):]
                    z.writestr(relative_path, file_content)
    output_zip.seek(0)
    return output_zip

def zip_action_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Дамп файлов", callback_data='zip_dump_files'),
         InlineKeyboardButton("📋 Дамп структуры", callback_data='zip_dump_structure')],
        [InlineKeyboardButton("🏠 В меню", callback_data='back')]
    ])

# Главное меню бота
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Генератор UUID", callback_data='uuid'),
         InlineKeyboardButton("🔒 Шифратор Unicode", callback_data='unicode_encrypt')],
        [InlineKeyboardButton("🔓 Дешифратор Unicode", callback_data='unicode_decrypt'),
         InlineKeyboardButton("👻 Генератор Zalgo", callback_data='zalgo')],
        [InlineKeyboardButton("🌟 Прочие символы", callback_data='unicode_symbols'),
         InlineKeyboardButton("🆔 Прочие ID", callback_data='other_ids')],
        [InlineKeyboardButton("🎲 Случайные числа", callback_data='random_numbers'),
         InlineKeyboardButton("📝 Генератор QR", callback_data='qr_generate')],
        [InlineKeyboardButton("💱 Конвертер валют", callback_data='currency'),
         InlineKeyboardButton("🧹 Удалить переносы", callback_data='remove_newlines')],
        [InlineKeyboardButton("📦 Анализатор ZIP", callback_data='zip_analyzer'),
         InlineKeyboardButton("🧼 GPT Deobfuscator", callback_data='deobfuscator')],
        [InlineKeyboardButton("🔧 Обработать текстурпак", callback_data="process_texturepack"),
         InlineKeyboardButton("👨‍💻 Авторы", callback_data='authors')]
    ])

def texturepack_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 Обфускация", callback_data='texturepack_obfuscate'),
         InlineKeyboardButton("🔓 Деобфускация", callback_data='texturepack_deobfuscate')],
        [InlineKeyboardButton("🏠 В меню", callback_data='back')]
    ])
def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='back')]])

def copy_menu(text):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Скопировать", switch_inline_query=text)],
        [InlineKeyboardButton("🏠 В меню", callback_data='back')]
    ])

def zalgo_type_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👻 Обычный", callback_data='zalgo_normal'),
         InlineKeyboardButton("🎨 Кастомный", callback_data='zalgo_custom')],
        [InlineKeyboardButton("🎲 Случайный алфавит", callback_data='zalgo_random')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back')]
    ])

def zalgo_normal_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👁‍🗨 Лёгкий хаос", callback_data='zalgo_light'),
         InlineKeyboardButton("👁 Средний хаос", callback_data='zalgo_medium'),
         InlineKeyboardButton("💀 Жуткий хаос", callback_data='zalgo_heavy')],
        [InlineKeyboardButton("💥 Абсолютный Хаос", callback_data='zalgo_absolute'),
         InlineKeyboardButton("🌌 Разрушитель текста", callback_data='zalgo_destroyer')],
        [InlineKeyboardButton("⬆️ Только вверх", callback_data='zalgo_up'),
         InlineKeyboardButton("⬇️ Только вниз", callback_data='zalgo_down'),
         InlineKeyboardButton("↕️ Оба направления", callback_data='zalgo_both')],
        [InlineKeyboardButton("🔄 Сгенерировать", callback_data='zalgo_generate'),
         InlineKeyboardButton("🗑️ Сбросить", callback_data='zalgo_normal_reset'),
         InlineKeyboardButton("🏠 В меню", callback_data='back')]
    ])

def zalgo_custom_menu(base_text=None, overlay_text=None):
    message = (
        f"🎨 <b>Кастомный Zalgo</b>\n"
        f"<b>Слово снизу:</b> <code>{base_text if base_text else 'не задано'}</code>\n"
        f"<b>Слово сверху:</b> <code>{overlay_text if overlay_text else 'не задано'}</code>\n"
    )
    keyboard = [
        [InlineKeyboardButton("📝 Слово снизу", callback_data='zalgo_custom_base'),
         InlineKeyboardButton("ⷭ Слово сверху 😎", callback_data='zalgo_custom_overlay')],
        [InlineKeyboardButton("🔄 Сгенерировать", callback_data='zalgo_custom_generate'),
         InlineKeyboardButton("🗑️ Сбросить", callback_data='zalgo_custom_reset')],
        [InlineKeyboardButton("🏠 В меню", callback_data='back')]
    ]
    return message, InlineKeyboardMarkup(keyboard)

def unicode_symbols_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ Все стрелки", callback_data='symbols_arrows'),
         InlineKeyboardButton("🎲 Случайный символ", callback_data='symbols_random_all')],
        [InlineKeyboardButton("漢 Генерация иероглифов", callback_data='symbols_hieroglyphs'),
         InlineKeyboardButton("✨ Необычный символ", callback_data='symbols_random')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back')]
    ])

def other_ids_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Телефон", callback_data='phone_number'),
         InlineKeyboardButton("✉️ Email", callback_data='temp_email')],
        [InlineKeyboardButton("🔑 Пароль", callback_data='password')],
        [InlineKeyboardButton("🏠 В меню", callback_data='back')]
    ])

def random_number_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Ещё число", callback_data='generate_again'),
         InlineKeyboardButton("🎲 Новый диапазон", callback_data='random_numbers')],
        [InlineKeyboardButton("🏠 В меню", callback_data='back')]
    ])

def qr_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Сгенерировать ещё", callback_data='qr_generate')],
        [InlineKeyboardButton("🏠 В меню", callback_data='back')]
    ])

def currency_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💱 Конвертировать", callback_data='currency_select'),
         InlineKeyboardButton("📊 Обновить курс", callback_data='currency')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back')]
    ])

def currency_after_conversion_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💱 Ещё конвертировать", callback_data='currency_select'),
         InlineKeyboardButton("📊 Обновить курс", callback_data='currency_update')],
        [InlineKeyboardButton("🔙 Вернуться к валютам", callback_data='currency')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back')]
    ])

def currency_select_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇪🇺 EUR", callback_data='currency_from_EUR'),
         InlineKeyboardButton("🇺🇸 USD", callback_data='currency_from_USD'),
         InlineKeyboardButton("🇷🇺 RUB", callback_data='currency_from_RUB')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back')]
    ])

def currency_to_menu(from_currency):
    options = {'EUR': ['USD', 'RUB'], 'USD': ['EUR', 'RUB'], 'RUB': ['EUR', 'USD']}
    to_options = options[from_currency]
    flag_map = {'EUR': '🇪🇺', 'USD': '🇺🇸', 'RUB': '🇷🇺'}
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{flag_map[to_options[0]]} {to_options[0]}", callback_data=f'currency_to_{to_options[0]}'),
         InlineKeyboardButton(f"{flag_map[to_options[1]]} {to_options[1]}", callback_data=f'currency_to_{to_options[1]}')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back')]
    ])

def result_choice_menu(processed_text: str, original_callback: str):
    label_map = {
        'unicode_encrypt': 'Зашифровано',
        'unicode_decrypt': 'Расшифровано',
        'remove_all_spaces': 'Без пробелов',
        'remove_all_newlines': 'Без переносов',
        'remove_all_spaces_newlines': 'Без пробелов и переносов',
        'remove_extra_spaces': 'Без лишних пробелов',
        'remove_extra_newlines': 'Без лишних переносов',
        'remove_extra_spaces_newlines': 'Без лишних пробелов и переносов',
        'format_code': 'Отформатированный код',
        'deobfuscator': 'Символы \\u202F удалены'
    }
    label_map.get(original_callback, 'Результат')
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📋 Вывести текст", callback_data=f'result_text_{original_callback}')],
        [InlineKeyboardButton(f"📥 Скачать в .txt", callback_data=f'result_file_{original_callback}')],
        [InlineKeyboardButton("🏠 В меню", callback_data='back')]
    ])

def zip_options_menu(path: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Как ZIP", callback_data='send_as_zip'),
         InlineKeyboardButton("📄 Просто файлы", callback_data='send_files')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back')]
    ])

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_message = (
        "🎉 <b>Привет, друг!</b> 🎉\n"
        "Добро пожаловать в мой <b><i>супер-бот</i></b> с утилитами! 🚀\n"
        "Выбирай, что нужно, и давай повеселимся! 😎\n\n"
        "✨ <b>О боте</b> ✨\n"
        "Этот бот — твой верный помощник для генерации всего на свете: от UUID и QR-кодов "
        "до Zalgo-текста и случайных паролей! 🎲 Шифруй сообщения в Unicode, убирай лишние "
        "пробелы, конвертируй валюты и анализируй ZIP-архивы! 💻 Всё это с щепоткой магии и "
        "кучей веселья! 🌟"
    )
    await update.message.reply_text(welcome_message, reply_markup=main_menu(), parse_mode='HTML')

def deobfuscate_text_gpt(text: str, filename: str = None) -> tuple[str, bool]:
    log_filename = filename if filename else "текст из ввода"
    logging.debug(f"Исходный текст для деобфускации ({log_filename}): {text[:1000]}...")
    if '\u202F' not in text:
        return "❌ В тексте нет символов \\u202F!", False
    cleaned_text = text.replace('\u202F', ' ')
    logging.info(f"Деобфусцированный текст ({log_filename}): {cleaned_text[:1000]}...")
    return cleaned_text, True

# Функция загрузки файла с повторными попытками
async def download_file_with_retries(file, update: Update) -> bytes:
    for attempt in range(MAX_RETRIES):
        try:
            file_obj = await file.get_file()
            byte_array = await file_obj.download_as_bytearray()
            return bytes(byte_array)  # Преобразуем Bytearray в bytes
        except NetworkError as e:
            logging.warning(f"Попытка {attempt + 1}/{MAX_RETRIES} загрузки файла не удалась: {e}")
            if attempt < MAX_RETRIES - 1:
                await update.message.reply_text(
                    f"⚠️ Ошибка сети, повторная попытка ({attempt + 1}/{MAX_RETRIES})...",
                    parse_mode='HTML'
                )
                await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
            else:
                raise NetworkError(f"Не удалось загрузить файл после {MAX_RETRIES} попыток: {e}")

# Обработка текстурпаков

def is_valid_json(text):
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка валидации JSON: {e}")
        return False

def obfuscate_text(text, filename):
    logging.debug(f"Исходный текст для обфускации ({filename}): {text[:1000]}...")

    def to_unicode(match):
        return ''.join(f'\\u{ord(c):04x}' for c in match.group(1))

    key_pattern = r'"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:'
    comment_pattern = r'(//.*?\n|/\*.*?\*/)'

    obfuscated_text = text
    obfuscated_text = re.sub(key_pattern, lambda m: f'"{to_unicode(m)}":', obfuscated_text)
    obfuscated_text = re.sub(comment_pattern, to_unicode, obfuscated_text, flags=re.DOTALL)

    logging.debug(f"Обфусцированный текст ({filename}): {obfuscated_text[:1000]}...")
    logging.info(f"Обфусцированный JSON в файле {filename} обработан")
    return obfuscated_text

def deobfuscate_text(text, filename, remove_comments=False):
    logging.debug(f"Исходный текст для деобфускации ({filename}): {text[:1000]}...")

    def from_unicode(match):
        return chr(int(match.group(1), 16))

    deobfuscated_text = re.sub(r'\\u([0-9a-fA-F]{4})', from_unicode, text)

    if remove_comments:
        deobfuscated_text = re.sub(r'//.*?\n|/\*.*?\*/', '', deobfuscated_text, flags=re.DOTALL)
        logging.info(f"Комментарии удалены из файла {filename}")

    logging.debug(f"Деобфусцированный текст ({filename}): {deobfuscated_text[:1000]}...")
    logging.info(f"Деобфусцированный JSON в файле {filename} обработан")
    return deobfuscated_text

async def process_archive(file_content, mode, remove_comments=False):
    output_zip = BytesIO()
    invalid_json_detected = False
    invalid_json_files = []
    processed_files = 0
    total_json_files = 0

    with zipfile.ZipFile(BytesIO(file_content), "r") as zip_in:
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for item in zip_in.infolist():
                data = zip_in.read(item.filename)
                if item.filename.endswith(".json"):
                    total_json_files += 1
                    logging.info(f"Обработка файла {item.filename} для {mode}")
                    try:
                        json_text = data.decode("utf-8")
                        if mode == "obfuscate":
                            processed_text = obfuscate_text(json_text, item.filename)
                        else:
                            processed_text = deobfuscate_text(json_text, item.filename, remove_comments)
                        zip_out.writestr(item.filename, processed_text.encode("utf-8"))
                        processed_files += 1
                    except Exception as e:
                        logging.error(f"Ошибка обработки JSON {item.filename}: {e}")
                        zip_out.writestr(item.filename, data)
                else:
                    zip_out.writestr(item.filename, data)

    return output_zip.getvalue(), invalid_json_detected, invalid_json_files, processed_files, total_json_files


async def process_texturepack_file(update, context, file_id: str, file_name: str, file_size: int):
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        chat_id = update.callback_query.message.chat_id
        message_id = update.callback_query.message.message_id
    else:
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id
        message_id = update.message.message_id

    mode = user_data[user_id].get('texturepack_mode', 'obfuscate')

    logging.info(
        f"Начало обработки файла {file_name}, размер: {file_size} байт, режим: {mode}, chat_id: {chat_id}, message_id: {message_id}")

    try:
        file = await context.bot.get_file(file_id)
        file_content = await file.download_as_bytearray()

        animation_states = ["🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚", "🕛"]
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="⏳ Обработка файла... 🕑",
                parse_mode='HTML'
            )
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение {message_id}: {e}, отправляем новое")
            animation_message = await context.bot.send_message(
                chat_id=chat_id,
                text="⏳ Обработка файла... 🕑",
                parse_mode='HTML'
            )
            message_id = animation_message.message_id

        start_time = time.time()
        remove_comments = user_data[user_id].get('remove_comments', False)
        output_file, invalid_json_detected, invalid_json_files, processed_files, total_json_files = await process_archive(
            file_content, mode, remove_comments)

        elapsed_time = time.time() - start_time
        for i, state in enumerate(animation_states[1:], 1):
            if elapsed_time < i * 0.5:
                await asyncio.sleep(i * 0.5 - elapsed_time)
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"⏳ Обработка файла... {state}",
                        parse_mode='HTML'
                    )
                    logging.info(f"Обновление анимации: ⏳ Обработка файла... {state}, message_id: {message_id}")
                except Exception as e:
                    logging.warning(f"Ошибка анимации: {e}")
                    continue

        output_name = file_name.replace('.mcpack', f'_{mode}.mcpack')
        processing_time = time.time() - start_time

        logging.info(
            f"Файл обработан, выходное имя: {output_name}, размер: {len(output_file)} байт, время обработки: {processing_time:.2f} сек")

        await context.bot.send_document(
            chat_id=chat_id,
            document=BytesIO(output_file),
            filename=output_name
        )
        logging.info(f"Файл {output_name} успешно отправлен")

        json_status_text = ""
        if mode == "obfuscate":
            if invalid_json_files:
                invalid_files_formatted = [f"- {file}" for file in [f.replace('\\', '/') for f in invalid_json_files]]
                json_status_text = (
                    f"⚠️ Внимание: Следующие JSON-файлы ({len(invalid_json_files)}/{total_json_files}) не были обфусцированы из-за ошибок:\n"
                    + "\n".join(invalid_files_formatted)
                    + "\nТекстурпак может не работать."
                )
            else:
                json_status_text = f"✅ Все JSON-файлы ({processed_files}/{total_json_files}) успешно обфусцированы."
        else:
            if invalid_json_files:
                invalid_files_formatted = [f"- {file}" for file in [f.replace('\\', '/') for f in invalid_json_files]]
                json_status_text = (
                f"⚠️ Внимание: Следующие JSON-файлы ({len(invalid_json_files)}/{total_json_files}) не были деобфусцированы из-за ошибок:\n"
                + "\n".join(invalid_files_formatted)
                + "\nТекстурпак может не работать."
                )
            else:
                json_status_text = f"✅ Все JSON-файлы ({processed_files}/{total_json_files}) успешно деобфусцированы."
                if remove_comments:
                    json_status_text += "\n🗑️ Комментарии удалены из JSON-файлов."
                else:
                    json_status_text += "\n💾 Комментарии сохранены в JSON-файлах."

        keyboard = [[InlineKeyboardButton("🏠 В меню", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        final_message = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ Файл отправлен! 🎉\n"
                f"⚠️ Обратите внимание: Текстурпак может сломаться после {mode}.\n"
                f"{json_status_text}"
            ),
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение анимации {message_id}: {e}")

        logging.info(f"Обработка файла завершена для чата {chat_id}, final_message_id: {final_message.message_id}")

        user_data[user_id].clear()
        user_data[user_id]['last_activity'] = datetime.now()

    except Exception as e:
        logging.error(f"Ошибка обработки файла {file_name}: {e}")
        keyboard = [[InlineKeyboardButton("🏠 В меню", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ Произошла ошибка при обработке файла. Попробуйте еще раз.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение {message_id}: {e}, отправляем новое")
            error_message = await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при обработке файла. Попробуйте еще раз.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        user_data[user_id].clear()
        user_data[user_id]['last_activity'] = datetime.now()

def remove_newlines_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Все пробелы", callback_data='remove_all_spaces'),
         InlineKeyboardButton("📜 Все переносы", callback_data='remove_all_newlines')],
        [InlineKeyboardButton("🗑️ Пробелы и переносы", callback_data='remove_all_spaces_newlines')],
        [InlineKeyboardButton("✂️ Лишние пробелы", callback_data='remove_extra_spaces'),
         InlineKeyboardButton("📏 Лишние переносы", callback_data='remove_extra_newlines')],
        [InlineKeyboardButton("🧼 Лишние пробелы и переносы", callback_data='remove_extra_spaces_newlines')],
        [InlineKeyboardButton("💻 Форматирование кода", callback_data='format_code')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back')]
    ])

# Дальше идет дохрена всяких режимов - не пытайтесь в них разобраться я сам еле понял
def remove_all_spaces(text: str) -> str:
    return re.sub(r'\s+', '', text)

def remove_all_newlines(text: str) -> str:
    return text.replace('\r\n', '').replace('\n', '').replace('\r', '')

def remove_all_spaces_newlines(text: str) -> str:
    return re.sub(r'\s+', '', text.replace('\r\n', '').replace('\n', '').replace('\r', ''))

def remove_extra_spaces(text: str) -> str:
    lines = text.split('\n')
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in lines]
    return '\n'.join(lines)

def remove_extra_newlines(text: str) -> str:
    text = re.sub(r'(\r?\n|\r){3,}', '\n\n', text)
    text = re.sub(r'(\r?\n|\r){3,}$', '\n\n', text)
    return text

def remove_extra_spaces_newlines(text: str) -> str:
    text = re.sub(r'(\r?\n|\r){3,}', '\n\n', text)
    text = re.sub(r'(\r?\n|\r){3,}$', '\n\n', text)
    lines = text.split('\n')
    lines = [re.sub(r'[ \t]+', ' ', line.rstrip()) for line in lines]
    result = '\n'.join(lines)
    return result


def format_code(text: str, language: str = 'auto') -> str:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]

    if language == 'python':
        formatted_lines = []
        for line in lines:
            indent = len(line) - len(line.lstrip())
            indent_level = indent // 4
            formatted_line = '    ' * indent_level + line.lstrip()
            formatted_lines.append(formatted_line)
        return '\n'.join(formatted_lines)
    elif language == 'javascript':
        text = '\n'.join(lines)
        text = re.sub(r'\s*([{}()[\];,])\s*', r'\1', text)
        return re.sub(r'\s+', ' ', text.strip())
    elif language == 'css':
        text = '\n'.join(lines)
        text = re.sub(r'\s*([{}:;])\s*', r'\1', text)
        return re.sub(r'\s+', ' ', text.strip())
    elif language == 'html':
        text = '\n'.join(lines)
        text = re.sub(r'\s*(<[^>]+>)\s*', r'\1', text)
        return re.sub(r'\s+', ' ', text.strip())
    elif language == 'json':
            try:
                cleaned_text = text.strip().encode('utf-8').decode('utf-8-sig')
                parsed_json = json.loads(cleaned_text)
                formatted_text = json.dumps(parsed_json, ensure_ascii=False, separators=(',', ':'))
                return formatted_text
            except json.JSONDecodeError as e:
                logging.error(f"Ошибка парсинга JSON: {e}, входной текст: {text[:1000]}...")
                return f"❌ Ошибка: JSON невалиден ({str(e)}). Исправьте и попробуйте снова!"
    else:
        text = '\n'.join(lines)
        text = re.sub(r'(\r?\n|\r){2,}', '\n', text.strip())
        return re.sub(r'\s+', ' ', text)

def format_code_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🐍 Python", callback_data='format_code_python'),
         InlineKeyboardButton("🌐 JavaScript", callback_data='format_code_javascript')],
        [InlineKeyboardButton("🎨 CSS", callback_data='format_code_css'),
         InlineKeyboardButton("🏷️ HTML", callback_data='format_code_html')],
        [InlineKeyboardButton("📋 JSON", callback_data='format_code_json'),  # Новая кнопка
         InlineKeyboardButton("🤖 Auto", callback_data='format_code_auto')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back')]
    ])

# Экранируем гребанные символы которые не хотят это делать
def escape_html(text: str, for_code: bool = False) -> list:
    if for_code:
        parts = split_message(text, MAX_MESSAGE_LENGTH - 20)
        return parts
    else:
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        parts = split_message(text, MAX_MESSAGE_LENGTH - 20)
        return parts


def escape_html_for_code(text: str) -> list:
    html_escape_table = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&apos;'
    }
    escaped_text = ''.join(html_escape_table.get(char, char) for char in text)
    return split_message(escaped_text, MAX_MESSAGE_LENGTH)


# Обработчик нажатий кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['last_activity'] = datetime.now()
    context.job_queue.run_once(clear_user_data, 600, data=user_id)
    logging.info(f"Button pressed by {user_id}: {query.data}")
    supported_formats = "📎 <i>Можно загрузить файл: .txt, .json, .py, .csv, .md, .html, .css, .js</i>" # Ахаха вы посмотрите на скрепку в питоне

    if query.data == 'uuid':
        new_uuid = str(uuid.uuid4())
        escaped_parts = escape_html_for_code(new_uuid)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Скопировать", switch_inline_query=new_uuid),
             InlineKeyboardButton("🔄 Ещё", callback_data='uuid')],
            [InlineKeyboardButton("🏠 В меню", callback_data='back')]
        ])
        for i, part in enumerate(escaped_parts, 1):
            message = f"✨ <b>Твой UUID:</b> 🎉\n<code>{part}</code>"
            if len(escaped_parts) > 1:
                message += f"\nЧасть {i}/{len(escaped_parts)}"
            if i == 1:
                await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')
            else:
                await query.message.reply_text(message, reply_markup=None, parse_mode='HTML')
                if i < len(escaped_parts):
                    await asyncio.sleep(0.5)

    elif query.data == 'unicode_encrypt':
        message = f"🔒 <b>Введи текст для шифровки!</b> ✨\n{supported_formats}"
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = 'waiting_for_encrypt_input'

    elif query.data == 'unicode_decrypt':
        message = (
            f"🔓 <b>Введи Unicode-код для расшифровки!</b> 😎\n"
            f"(Пример: <code>\\u0048\\u0065\\u006c\\u006c\\u006f</code>)\n"
            f"{supported_formats}"
        )
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = 'waiting_for_decrypt_input'

    elif query.data == 'zalgo':
        message = "👻 <b>Выберите тип Zalgo!</b> 🕸️"
        await query.edit_message_text(message, reply_markup=zalgo_type_menu(), parse_mode='HTML')

    elif query.data == 'zalgo_normal':
        message = "👻 <b>Введи текст для обычного Zalgo-хаоса!</b> 🕸️"
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = 'waiting_for_zalgo_normal_text'

    elif query.data == 'zalgo_custom':
        message, markup = zalgo_custom_menu()
        await query.edit_message_text(message, reply_markup=markup, parse_mode='HTML')
        user_data[user_id]['state'] = 'zalgo_custom_menu'

    elif query.data == 'zalgo_random':
        message = "🎲 <b>Введи текст для случайного алфавита!</b> ✨"
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = 'waiting_for_zalgo_random_text'


    elif (query.data.startswith('zalgo_') and not query.data.startswith('zalgo_custom') and
          query.data not in ['zalgo_random', 'zalgo_random_generate']):
        if 'zalgo_text' not in user_data[user_id]:
            message = "👻 <b>Сначала введи текст для Zalgo!</b>"
            await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
            user_data[user_id]['state'] = 'waiting_for_zalgo_normal_text'
            return
        text = user_data[user_id]['zalgo_text']
        if query.data == 'zalgo_light':
            user_data[user_id]['zalgo_intensity'] = 'light'
        elif query.data == 'zalgo_medium':
            user_data[user_id]['zalgo_intensity'] = 'medium'
        elif query.data == 'zalgo_heavy':
            user_data[user_id]['zalgo_intensity'] = 'heavy'
        elif query.data == 'zalgo_absolute':
            user_data[user_id]['zalgo_intensity'] = 'absolute'
        elif query.data == 'zalgo_destroyer':
            user_data[user_id]['zalgo_intensity'] = 'destroyer'
        elif query.data == 'zalgo_up':
            user_data[user_id]['zalgo_direction'] = 'up'
        elif query.data == 'zalgo_down':
            user_data[user_id]['zalgo_direction'] = 'down'
        elif query.data == 'zalgo_both':
            user_data[user_id]['zalgo_direction'] = 'both'
        elif query.data == 'zalgo_normal_reset':
            user_data[user_id] = {'last_activity': datetime.now()}
            message = "👻 <b>Введи текст для обычного Zalgo-хаоса!</b> 🕸️"
            await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
            user_data[user_id]['state'] = 'waiting_for_zalgo_normal_text'
            return

        elif query.data == 'zalgo_generate':
            intensity = user_data[user_id].get('zalgo_intensity', 'medium')
            direction = user_data[user_id].get('zalgo_direction', 'both')
            zalgo_text = generate_zalgo(text, intensity, direction)
            if zalgo_text.startswith("❌"):
                await query.edit_message_text(zalgo_text, reply_markup=zalgo_normal_menu(), parse_mode='HTML')
                return
            escaped_parts = escape_html_for_code(zalgo_text)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Скопировать", switch_inline_query=zalgo_text),
                 InlineKeyboardButton("🔄 Ещё", callback_data='zalgo_normal')],
                [InlineKeyboardButton("🏠 В меню", callback_data='back')]
            ])
            for i, part in enumerate(escaped_parts, 1):
                message = f"👻 Твой Zalgo: 🕸️\n<code>{part}</code>"
                if len(escaped_parts) > 1:
                    message += f"\nЧасть {i}/{len(escaped_parts)}"
                if i == 1:
                    await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')
                else:
                    await query.message.reply_text(message, reply_markup=None, parse_mode='HTML')
                    if i < len(escaped_parts):
                        await asyncio.sleep(0.5)
            return
        intensity = user_data[user_id].get('zalgo_intensity', 'medium')
        direction = user_data[user_id].get('zalgo_direction', 'both')
        escaped_text = escape_html_for_code(text)[0]
        message = (
            f"👻 <b>Текст:</b> <code>{escaped_text}</code>\n"
            f"<b>Уровень хаоса:</b> <b>{intensity}</b>\n"
            f"<b>Направление:</b> <b>{direction}</b>\n"
            f"<i>Выбери и жми 'Сгенерировать'!</i> 🚀"
        )
        await query.edit_message_text(message, reply_markup=zalgo_normal_menu(), parse_mode='HTML')

    elif query.data.startswith('zalgo_custom_'):
        base_text = user_data[user_id].get('zalgo_base_text')
        overlay_text = user_data[user_id].get('zalgo_overlay_text')
        if query.data == 'zalgo_custom_base':
            message = "📝 <b>Введи слово снизу для кастомного Zalgo!</b>"
            await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
            user_data[user_id]['state'] = 'waiting_for_zalgo_custom_base'
        elif query.data == 'zalgo_custom_overlay':
            message = "ⷭ <b>Введи слово сверху для кастомного Zalgo!</b>"
            await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
            user_data[user_id]['state'] = 'waiting_for_zalgo_custom_overlay'
        elif query.data == 'zalgo_custom_reset':
            user_data[user_id] = {'last_activity': datetime.now()}
            message, markup = zalgo_custom_menu()
            await query.edit_message_text(message, reply_markup=markup, parse_mode='HTML')
            user_data[user_id]['state'] = 'zalgo_custom_menu'
        elif query.data == 'zalgo_custom_generate':
            if not base_text or not overlay_text:
                missing = "слово снизу" if not base_text else "слово сверху"
                message = f"🎨 <b>Сначала введи {missing}!</b>"
                await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
                user_data[user_id]['state'] = (
                    'waiting_for_zalgo_custom_base' if not base_text else 'waiting_for_zalgo_custom_overlay'
                )
                return
            result = generate_zalgo(base_text, mode='custom', overlay_text=overlay_text)
            if result.startswith("❌"):
                message, markup = zalgo_custom_menu(base_text, overlay_text)
                await query.edit_message_text(result, reply_markup=markup, parse_mode='HTML')
                return
            escaped_parts = escape_html_for_code(result)

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Скопировать", switch_inline_query=result),
                 InlineKeyboardButton("🔄 Ещё", callback_data='zalgo_custom')],
                [InlineKeyboardButton("🏠 В меню", callback_data='back')]
            ])

            for i, part in enumerate(escaped_parts, 1):
                message = f"🎨 Твой кастомный Zalgo: \n<code>{part}</code>"
                if len(escaped_parts) > 1:
                    message += f"\nЧасть {i}/{len(escaped_parts)}"
                if i == 1:
                    await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')
                else:
                    await query.message.reply_text(message, reply_markup=None, parse_mode='HTML')
                    if i < len(escaped_parts):
                        await asyncio.sleep(0.5)

        else:
            message, markup = zalgo_custom_menu(base_text, overlay_text)
            await query.edit_message_text(message, reply_markup=markup, parse_mode='HTML')


    elif query.data == 'zalgo_random_generate':
        text = user_data[user_id].get('random_alphabet_text')
        if not text:
            message = "🎲 <b>Сначала введи текст для случайного алфавита!</b> ✨"
            await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
            user_data[user_id]['state'] = 'waiting_for_zalgo_random_text'
            return
        result = generate_random_alphabet(text)
        if result.startswith("❌"):
            await query.edit_message_text(result, reply_markup=back_button(), parse_mode='HTML')
            return
        escaped_parts = escape_html_for_code(result)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Скопировать", switch_inline_query=result),
             InlineKeyboardButton("🔄 Ещё", callback_data='zalgo_random_generate')],
            [InlineKeyboardButton("🏠 В меню", callback_data='back')]
        ])
        for i, part in enumerate(escaped_parts, 1):
            message = f"🎲 Твой случайный алфавит: ✨\n<code>{part}</code>"
            if len(escaped_parts) > 1:
                message += f"\nЧасть {i}/{len(escaped_parts)}"
            if i == 1:
                await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')
            else:
                await query.message.reply_text(message, reply_markup=None, parse_mode='HTML')
                if i < len(escaped_parts):
                    await asyncio.sleep(0.5)

    elif query.data == 'unicode_symbols':
        message = "🌟 <b>Выбери символы для генерации!</b> 😍"
        await query.edit_message_text(message, reply_markup=unicode_symbols_menu(), parse_mode='HTML')

    elif query.data == 'symbols_arrows':
        escaped_arrows = [escape_html_for_code(s)[0] for s in ARROWS]
        arrows_str = '\n'.join(f"<code>{s}</code>" for s in escaped_arrows)
        message = f"🌟 <b>Все стрелки:</b> 🎯\n{arrows_str}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Скопировать", switch_inline_query='\n'.join(ARROWS)),
             InlineKeyboardButton("🎲 Случайная стрелка", callback_data='symbols_random_arrow')],
            [InlineKeyboardButton("🏠 В меню", callback_data='back')]
        ])
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    elif query.data == 'symbols_random_arrow':
        arrow = random.choice(ARROWS)
        escaped_arrow = escape_html_for_code(arrow)[0]
        message = f"🌟 <b>Случайная стрелка:</b> 🎯\n<code>{escaped_arrow}</code>"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Скопировать", switch_inline_query=arrow),
             InlineKeyboardButton("🎲 Ещё", callback_data='symbols_random_arrow')],
            [InlineKeyboardButton("🏠 В меню", callback_data='back')]
        ])
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    elif query.data == 'symbols_random_all':
        symbol = random.choice(ALL_SYMBOLS)
        escaped_symbol = escape_html_for_code(symbol)[0]
        message = f"🌟 <b>Случайный символ:</b> 🎲\n<code>{escaped_symbol}</code>"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Скопировать", switch_inline_query=symbol),
             InlineKeyboardButton("🔄 Ещё", callback_data='symbols_random_all')],
            [InlineKeyboardButton("🏠 В меню", callback_data='back')]
        ])
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    elif query.data == 'symbols_hieroglyphs':
        hieroglyphs = random.sample(HIEROGLYPHS, min(8, len(HIEROGLYPHS)))
        escaped_hieroglyphs = escape_html_for_code(' '.join(hieroglyphs))[0]
        message = f"🌟 <b>Твои иероглифы:</b> 🈲\n<code>{escaped_hieroglyphs}</code>"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Скопировать", switch_inline_query=' '.join(hieroglyphs)),
             InlineKeyboardButton("🔄 Ещё", callback_data='symbols_hieroglyphs')],
            [InlineKeyboardButton("🏠 В меню", callback_data='back')]
        ])
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    elif query.data == 'symbols_random':
        symbol, code, name = random.choice(UNUSUAL_SYMBOLS)
        escaped_symbol = escape_html_for_code(symbol)[0]
        message = (
            f"🌟 <b>Необычный символ:</b> ✨\n"
            f"Символ: <code>{escaped_symbol}</code>\n"
            f"Код: {code}\n"
            f"Название: {name}"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Скопировать", switch_inline_query=symbol),
             InlineKeyboardButton("🔄 Ещё", callback_data='symbols_random')],
            [InlineKeyboardButton("🏠 В меню", callback_data='back')]
        ])
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    elif query.data == 'other_ids':
        message = "🆔 <b>Выбери ID для генерации!</b> 🚀"
        await query.edit_message_text(message, reply_markup=other_ids_menu(), parse_mode='HTML')

    elif query.data == 'phone_number':
        phone = generate_phone_number()
        escaped_phone = escape_html_for_code(phone)[0]
        message = f"📞 <b>Твой номер:</b> 🎉\n<code>{escaped_phone}</code>"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Скопировать", switch_inline_query=phone),
             InlineKeyboardButton("🔄 Ещё", callback_data='phone_number')],
            [InlineKeyboardButton("🏠 В меню", callback_data='back')]
        ])
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    elif query.data == 'temp_email':
        email = generate_temp_email()
        escaped_email = escape_html_for_code(email)[0]
        message = f"✉️ <b>Твой email:</b> 🌟\n<code>{escaped_email}</code>"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Скопировать", switch_inline_query=email),
             InlineKeyboardButton("🔄 Ещё", callback_data='temp_email')],
            [InlineKeyboardButton("🏠 В меню", callback_data='back')]
        ])
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    elif query.data == 'password':
        password = generate_password()
        escaped_password = escape_html_for_code(password)[0]
        message = f"🔑 <b>Твой пароль:</b> 💪\n<code>{escaped_password}</code>"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Скопировать", switch_inline_query=password),
             InlineKeyboardButton("🔄 Ещё", callback_data='password')],
            [InlineKeyboardButton("🏠 В меню", callback_data='back')]
        ])
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='HTML')

    elif query.data == 'random_numbers':
        message = "🎲 <b>Введи диапазон (например, 1-100 или 1-1e6)!</b> 🎯"
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = 'waiting_for_random_range'

    elif query.data == 'generate_again':
        if 'last_range' not in user_data[user_id]:
            message = "🎲 <b>Сначала введи диапазон!</b> 😊"
            await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
            user_data[user_id]['state'] = 'waiting_for_random_range'
            return
        start, end = user_data[user_id]['last_range']
        number = random.randint(start, end)
        escaped_number = escape_html_for_code(str(number))[0]
        message = f"🎲 <b>Твоё число:</b> <code>{escaped_number}</code> 🎉"
        await query.edit_message_text(message, reply_markup=random_number_menu(), parse_mode='HTML')

    elif query.data == 'qr_generate':
        message = "📝 <b>Введи текст для QR-кода!</b> 🌐"
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = 'waiting_for_qr_text'

    elif query.data == 'currency':
        await query.edit_message_text("⏳ Подождите...", parse_mode='HTML')
        rates = get_exchange_rates()
        if not rates:
            message = "❌ Не удалось загрузить курсы валют! Попробуй позже."
            await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
            return
        message = (
            f"💱 <b>Конвертер валют!</b> 💸\n"
            f"Курсы к RUB (на {rates['date']}):\n"
            f"🇪🇺 1 EUR = {rates['EUR']:.2f} RUB\n"
            f"🇺🇸 1 USD = {rates['USD']:.2f} RUB\n"
            f"🇬🇧 1 GBP = {rates['GBP']:.2f} RUB"
        )
        await query.edit_message_text(message, reply_markup=currency_menu(), parse_mode='HTML')

    elif query.data == 'currency_select':
        message = "💱 <b>Выбери валюту для конвертации!</b> 💰"
        await query.edit_message_text(message, reply_markup=currency_select_menu(), parse_mode='HTML')

    elif query.data.startswith('currency_from_'):
        from_currency = query.data.split('_')[-1]
        user_data[user_id]['from_currency'] = from_currency
        message = f"💱 <b>Выбрано:</b> <b>{from_currency}</b>\n<i>В какую валюту?</i>"
        await query.edit_message_text(message, reply_markup=currency_to_menu(from_currency), parse_mode='HTML')

    elif query.data.startswith('currency_to_'):
        user_data[user_id]['to_currency'] = query.data.split('_')[-1]
        message = (
            f"💱 <b>Из {user_data[user_id]['from_currency']} в {user_data[user_id]['to_currency']}</b>\n"
            f"<i>Введи сумму!</i> 💸"
        )
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = 'waiting_for_currency_amount'

    elif query.data == 'currency_update':
        if 'last_conversion' not in user_data[user_id]:
            message = "❌ Сначала выполни конвертацию!"
            await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
            return
        await query.edit_message_text("⏳ Подождите...", parse_mode='HTML')
        amount, from_currency, to_currency = user_data[user_id]['last_conversion']
        try:
            response = requests.get(f"https://api.exchangerate-api.com/v4/latest/{from_currency}", timeout=5)
            rate = response.json()['rates'][to_currency]
            result = amount * rate
            date = response.json()['date']
            escaped_result = escape_html_for_code(f"{result:.2f}")[0]
            message = (
                f"💱 <b>{amount} {from_currency} = <code>{escaped_result}</code> {to_currency}</b> 💸\n"
                f"Обновлено на {date}"
            )
            await query.edit_message_text(message, reply_markup=currency_after_conversion_menu(), parse_mode='HTML')
        except requests.RequestException:
            message = "❌ Не удалось обновить курс! Попробуй позже."
            await query.edit_message_text(message, reply_markup=currency_after_conversion_menu(), parse_mode='HTML')

    elif query.data == 'remove_newlines':
        message = "🧹 <b>Выбери режим обработки текста!</b> ✨"
        await query.edit_message_text(message, reply_markup=remove_newlines_menu(), parse_mode='HTML')

    elif query.data == 'zip_analyzer':
        message = (
            "📦 <b>Загрузи ZIP-архив!</b>\n"
            "Поддерживаемые форматы: .zip, .mcpack, .mcworld, .mctemplate, .mcaddon\n"
            f"Лимит: {MAX_FILE_SIZE_MB} МБ, {MAX_ITEMS} элементов"
        )
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = 'waiting_for_zip'

    elif query.data == 'send_as_zip':
        folder_path = user_data[user_id].get('selected_path')
        zip_data = user_data[user_id].get('zip_data')
        if not folder_path or not zip_data:
            await query.edit_message_text("❌ Ошибка: данные потеряны!", reply_markup=back_button(), parse_mode='HTML')
            return
        await query.edit_message_text("⏳ Подождите...", parse_mode='HTML')
        zip_file = create_zip_from_folder(zip_data, folder_path)
        if zip_file.getvalue():
            zip_file.name = f"{folder_path.rstrip('/').split('/')[-1]}.zip"
            await query.message.reply_document(document=zip_file, filename=zip_file.name)
            await query.edit_message_text("📦 Архив отправлен!", parse_mode='HTML')
            await query.message.reply_text("✅ Готово! Что дальше?", reply_markup=back_button(), parse_mode='HTML')
        else:
            await query.edit_message_text("❌ В папке нет файлов или они пустые!", reply_markup=back_button(), parse_mode='HTML')

    elif query.data == 'send_files':
        folder_path = user_data[user_id].get('selected_path')
        zip_data = user_data[user_id].get('zip_data')
        if not folder_path or not zip_data:
            await query.edit_message_text("❌ Ошибка: данные потеряны!", reply_markup=back_button(), parse_mode='HTML')
            return
        await query.edit_message_text("⏳ Подождите...", parse_mode='HTML')
        sent = False
        with zipfile.ZipFile(BytesIO(zip_data)) as z:
            for file_info in z.infolist():
                if file_info.filename.startswith(folder_path) and not file_info.is_dir():
                    file_content = z.read(file_info.filename)
                    if file_content:
                        bio = BytesIO(file_content)
                        bio.name = os.path.basename(file_info.filename)
                        await query.message.reply_document(document=bio, filename=bio.name)
                        sent = True
        if sent:
            await query.edit_message_text("📦 Файлы отправлены!", parse_mode='HTML')
            await query.message.reply_text("✅ Готово! Что дальше?", reply_markup=back_button(), parse_mode='HTML')
        else:
            await query.edit_message_text("❌ В папке нет файлов или они пустые!", reply_markup=back_button(), parse_mode='HTML')

    elif query.data == 'zip_dump_files':
        if 'zip_data' not in user_data[user_id]:
            await query.edit_message_text("❌ Ошибка: данные архива потеряны!", reply_markup=back_button(),
                                          parse_mode='HTML')
            return
        message = (
            f"📦 <b>Структура архива:</b>\n"
            f"{user_data[user_id]['zip_structure']}\n\n"
            f"📋 Отправь название файла или папки из списка выше!"
        )
        parts = split_message(message, MAX_MESSAGE_LENGTH)
        for i, part in enumerate(parts, 1):
            part_message = f"{part}\nЧасть {i}/{len(parts)}" if len(parts) > 1 else part
            if i == len(parts):
                await query.message.reply_text(part_message, reply_markup=back_button(), parse_mode='HTML')
            else:
                await query.message.reply_text(part_message, parse_mode='HTML')
            if i < len(parts):
                await asyncio.sleep(0.5)
        await query.delete_message()
        user_data[user_id]['state'] = 'waiting_for_path'

    elif query.data == 'zip_dump_structure':
        if 'zip_structure' not in user_data[user_id]:
            await query.edit_message_text("❌ Ошибка: структура архива потеряна!", reply_markup=back_button(),
                                          parse_mode='HTML')
            return
        await query.edit_message_text("⏳ Подождите...", parse_mode='HTML')
        structure_text = user_data[user_id]['zip_structure'].replace('<code>', '').replace('</code>', '')
        file = create_txt_file(structure_text, "zip_structure")
        await query.message.reply_document(document=file, filename=file.name)
        await query.edit_message_text("📋 Файл со структурой отправлен!", parse_mode='HTML')
        await query.message.reply_text("✅ Готово! Что дальше?", reply_markup=back_button(), parse_mode='HTML')

    elif query.data == 'authors':
        message = (
            "👨‍💻 <b>Авторы</b> 👨‍💻\n\n"
            "✨ <b>Создатель:</b> @minetextureshub — гений, который вдохнул жизнь в этого бота! 🚀\n"
            "🤖 <b>ИИ Ассистент:</b> Grok 3 — умный помощник, который делает всё ещё круче! 🌟\n\n"
            "💡 Этот бот — настоящая находка для тех, кто любит творить и экспериментировать. "
            "Генерируй, шифруй, форматируй и веселись! 😎"
        )
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')

    elif query.data == 'deobfuscator':
        message = (
            f"🧼 <b>Введи текст для удаления \\u202F!</b> ✨\n"
            f"📎 <i>Можно загрузить файл: .txt, .json, .py, .csv, .md, .html, .css, .js</i>"
        )
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = 'waiting_for_deobfuscator_input'



    elif query.data.startswith('result_text_'):
        callback = query.data.split('_')[-1]
        processed_text = user_data[user_id].get('processed_text', 'Ошибка: текст не найден')
        label_map = {
            'unicode_encrypt': ('🔒', 'Зашифровано'),
            'unicode_decrypt': ('🔓', 'Расшифровано'),
            'remove_all_spaces': ('🧹', 'Без пробелов'),
            'remove_all_newlines': ('🧹', 'Без переносов'),
            'remove_all_spaces_newlines': ('🧹', 'Без пробелов и переносов'),
            'remove_extra_spaces': ('🧹', 'Без лишних пробелов'),
            'remove_extra_newlines': ('🧹', 'Без лишних переносов'),
            'remove_extra_spaces_newlines': ('🧹', 'Без лишних пробелов и переносов'),
            'format_code': ('💻', 'Отформатированный код'),
            'deobfuscator': ('🧼', 'Символы \\u202F удалены')
        }
        prefix, text_label = label_map.get(callback, ('✨', 'Результат'))
        escaped_parts = escape_html_for_code(processed_text)
        for i, part in enumerate(escaped_parts, 1):
            message = f"{prefix} <b>{text_label}</b>: ✨\n<code>{part}</code>"
            if len(escaped_parts) > 1:
                message += f"\nЧасть {i}/{len(escaped_parts)}"
            reply_markup = copy_menu(processed_text)
            await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')
            if i < len(escaped_parts):
                await asyncio.sleep(0.5)
        user_data[user_id]['state'] = None
        user_data[user_id]['last_activity'] = datetime.now()

    elif query.data.startswith('result_file_'):
        callback = query.data.split('_')[-1]
        processed_text = user_data[user_id].get('processed_text', 'Ошибка: текст не найден')
        await query.edit_message_text("⏳ Подождите...", parse_mode='HTML')
        file = create_txt_file(processed_text, f"result_{callback}")
        await query.message.reply_document(document=file, filename=file.name)
        await query.edit_message_text("📥 Файл отправлен!", parse_mode='HTML')
        await query.message.reply_text("📥 Твой файл готов! 🎉", reply_markup=back_button(), parse_mode='HTML')

    elif query.data == 'back':
        user_data[user_id].clear()
        user_data[user_id]['last_activity'] = datetime.now()
        message = (
            "🎉 <b>Привет, друг!</b> 🎉\n"
            "Добро пожаловать в мой <b><i>супер-бот</i></b> с утилитами! 🚀\n"
            "Выбирай, что нужно, и давай повеселимся! 😎\n\n"
            "✨ <b>О боте</b> ✨\n"
            "Этот бот — твой верный помощник для генерации всего на свете: от UUID и QR-кодов "
            "до Zalgo-текста и случайных паролей! 🎲 Шифруй сообщения в Unicode, убирай лишние "
            "пробелы, конвертируй валюты и анализируй ZIP-архивы! 💻 Всё это с щепоткой магии и "
            "кучей веселья! 🌟"
        )
        try:
            await query.edit_message_text(message, reply_markup=main_menu(), parse_mode='HTML')
        except Exception as e:
            logging.warning(f"ОПЯТЬ не удалось отредактировать сообщение для {user_id}: {e}")
            await query.message.reply_text(message, reply_markup=main_menu(), parse_mode='HTML')
            await query.delete_message()

    elif query.data == 'process_texturepack':
        message = "🔧 <b>Выбери режим обработки текстурпака!</b> 🎨"
        await query.edit_message_text(message, reply_markup=texturepack_menu(), parse_mode='HTML')
        logging.info(f"Пользователь {user_id} выбрал process_texturepack")

    elif query.data in ['texturepack_obfuscate', 'texturepack_deobfuscate']:
        mode = 'obfuscate' if query.data == 'texturepack_obfuscate' else 'deobfuscate'
        user_data[user_id]['texturepack_mode'] = mode
        message = (
            f"{'🔒' if mode == 'obfuscate' else '🔓'} <b>{'Обфускация' if mode == 'obfuscate' else 'Деобфускация'}</b>\n"
            f"📦 Загрузи файл текстурпака (.mcpack)!"
        )
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = 'waiting_for_texturepack'
        logging.info(f"Пользователь {user_id} выбрал режим {mode}")

    elif query.data in ['texturepack_remove_comments', 'texturepack_keep_comments']:
        user_data[user_id]['remove_comments'] = query.data == 'texturepack_remove_comments'
        logging.info(
            f"Пользователь {user_id} выбрал {'удаление' if user_data[user_id]['remove_comments'] else 'сохранение'} комментариев")
        if 'texturepack_data' not in user_data[user_id]:
            await query.edit_message_text(
                "❌ Ошибка: данные о файле потеряны! Загрузите файл снова.",
                reply_markup=back_button(),
                parse_mode='HTML'
            )
            user_data[user_id]['state'] = 'waiting_for_texturepack'
            return
        file_data = user_data[user_id]['texturepack_data']
        file_id = file_data['file_id']
        file_name = file_data['file_name']
        file_size = file_data['file_size']
        await query.edit_message_text(
            "⏳ Подождите, файл обрабатывается...", # Но это не точно
            parse_mode='HTML'
        )
        await process_texturepack_file(
            update=update,
            context=context,
            file_id=file_id,
            file_name=file_name,
            file_size=file_size
        )

    elif query.data in ['remove_all_spaces', 'remove_all_newlines', 'remove_all_spaces_newlines',
                        'remove_extra_spaces', 'remove_extra_newlines', 'remove_extra_spaces_newlines']:
        mode = query.data
        message = f"🧹 <b>Введи текст для обработки!</b> ✨\n{supported_formats}"
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = f'waiting_for_{mode}_input'

    elif query.data == 'format_code':
        message = "💻 <b>Выбери язык программирования!</b> 🖥️"
        await query.edit_message_text(message, reply_markup=format_code_menu(), parse_mode='HTML')

    elif query.data.startswith('format_code_'):
        language = query.data.split('_')[-1]
        user_data[user_id]['format_language'] = language
        message = f"💻 <b>Введи код для форматирования ({language})!</b> 🖥️\n{supported_formats}"
        await query.edit_message_text(message, reply_markup=back_button(), parse_mode='HTML')
        user_data[user_id]['state'] = 'waiting_for_format_code_input'

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['last_activity'] = datetime.now()
    context.job_queue.run_once(clear_user_data, 600, data=user_id)
    text = update.message.text
    if not text and not update.message.document:
        message = "❌ Введи непустой текст!"
        await update.message.reply_text(message, reply_markup=back_button(), parse_mode='HTML')
        return
    state = user_data[user_id].get('state')
    logging.info(f"Message from {user_id} in state {state}: {text}")
    if text:
        if state == 'waiting_for_encrypt_input':
            processed_text = encrypt_to_unicode(text)
            user_data[user_id]['processed_text'] = processed_text
            message = "🔒 <b>Зашифровано</b>: ✨\n<i>Теперь выбирай: вывести или скачать!</i>"
            await update.message.reply_text(message, reply_markup=result_choice_menu(processed_text, 'unicode_encrypt'), parse_mode='HTML')
        elif state == 'waiting_for_decrypt_input':
            processed_text = decrypt_from_unicode(text)
            if processed_text.startswith("❌"):
                await update.message.reply_text(processed_text, reply_markup=back_button(), parse_mode='HTML')
                return
            user_data[user_id]['processed_text'] = processed_text
            message = "🔓 <b>Расшифровано</b>: 😎\n<i>Теперь выбирай: вывести или скачать!</i>"
            await update.message.reply_text(message, reply_markup=result_choice_menu(processed_text, 'unicode_decrypt'), parse_mode='HTML')
        elif state == 'waiting_for_zalgo_normal_text':
            user_data[user_id]['zalgo_text'] = text
            user_data[user_id]['zalgo_intensity'] = user_data[user_id].get('zalgo_intensity', 'medium')
            user_data[user_id]['zalgo_direction'] = user_data[user_id].get('zalgo_direction', 'both')
            escaped_text = escape_html_for_code(text)[0]
            message = (
                f"👻 <b>Текст:</b> <code>{escaped_text}</code>\n"
                f"<b>Уровень хаоса:</b> <b>{user_data[user_id]['zalgo_intensity']}</b>\n"
                f"<b>Направление:</b> <b>{user_data[user_id]['zalgo_direction']}</b>\n"
                f"<i>Выбери и жми 'Сгенерировать'!</i> 🚀"
            )
            await update.message.reply_text(message, reply_markup=zalgo_normal_menu(), parse_mode='HTML')
        elif state == 'waiting_for_zalgo_custom_base':
            if not is_cyrillic(text):
                message = "❌ Слово снизу должно быть на русском языке (кириллица)!"
                await update.message.reply_text(message, reply_markup=back_button(), parse_mode='HTML')
                return
            user_data[user_id]['zalgo_base_text'] = text
            message, markup = zalgo_custom_menu(base_text=text, overlay_text=user_data[user_id].get('zalgo_overlay_text'))
            await update.message.reply_text(message, reply_markup=markup, parse_mode='HTML')
            user_data[user_id]['state'] = 'zalgo_custom_menu'
        elif state == 'waiting_for_zalgo_custom_overlay':
            if not is_cyrillic(text):
                message = "❌ Слово сверху должно быть на русском языке (кириллица)!"
                await update.message.reply_text(message, reply_markup=back_button(), parse_mode='HTML')
                return
            user_data[user_id]['zalgo_overlay_text'] = text
            message, markup = zalgo_custom_menu(base_text=user_data[user_id].get('zalgo_base_text'), overlay_text=text)
            await update.message.reply_text(message, reply_markup=markup, parse_mode='HTML')
            user_data[user_id]['state'] = 'zalgo_custom_menu'
        elif state == 'waiting_for_zalgo_random_text':
            user_data[user_id]['random_alphabet_text'] = text
            result = generate_random_alphabet(text)
            if result.startswith("❌"):
                await update.message.reply_text(result, reply_markup=back_button(), parse_mode='HTML')
                return
            escaped_parts = escape_html_for_code(result)
            for i, part in enumerate(escaped_parts, 1):
                message = f"🎲 Твой случайный алфавит: ✨\n<code>{part}</code>"
                if len(escaped_parts) > 1:
                    message += f"\nЧасть {i}/{len(escaped_parts)}"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Скопировать", switch_inline_query=result),
                     InlineKeyboardButton("🔄 Ещё", callback_data='zalgo_random_generate')],
                    [InlineKeyboardButton("🏠 В меню", callback_data='back')]
                ]) if i == len(escaped_parts) else None
                await update.message.reply_text(message, reply_markup=keyboard, parse_mode='HTML')
                if i < len(escaped_parts):
                    await asyncio.sleep(0.5)
            user_data[user_id]['state'] = None
        elif state == 'waiting_for_random_range':
            try:
                start_str, end_str = text.split('-')
                start = float(start_str.replace(',', '.'))
                end = float(end_str.replace(',', '.'))
                if start > end:
                    start, end = end, start
                if start == end:
                    number = int(start)
                else:
                    number = random.randint(int(start), int(end))
                user_data[user_id]['last_range'] = (int(start), int(end))
                escaped_number = escape_html_for_code(str(number))[0]
                message = f"🎲 <b>Твоё число:</b> <code>{escaped_number}</code> 🎉"
                await update.message.reply_text(message, reply_markup=random_number_menu(), parse_mode='HTML')
            except ValueError:
                message = "❌ Введи два числа через дефис (например, 1-100 или 1-1e6)!"
                await update.message.reply_text(message, reply_markup=back_button(), parse_mode='HTML')
        elif state == 'waiting_for_qr_text':
            escaped_text = escape_html_for_code(text)[0]
            qr = qrcode.make(text)
            bio = BytesIO()
            qr.save(bio, 'PNG')
            bio.seek(0)
            await update.message.reply_photo(photo=bio)
            message = f"📝 Твой QR-код для: <code>{escaped_text}</code>"
            await update.message.reply_text(message, reply_markup=qr_menu(), parse_mode='HTML')
            user_data.pop(user_id)
        elif state == 'waiting_for_path':
            zip_data = user_data[user_id].get('zip_data')
            if not zip_data:
                await update.message.reply_text("❌ Ошибка: архив потерян!", reply_markup=back_button(), parse_mode='HTML')
                return
            requested_path = text.strip()
            with zipfile.ZipFile(BytesIO(zip_data)) as z:
                file_list = [f.filename for f in z.infolist()]
                logging.info(f"Requested path: {requested_path}, Available files: {file_list}")
                if requested_path in file_list and not requested_path.endswith('/'):
                    file_content = z.read(requested_path)
                    if file_content:
                        bio = BytesIO(file_content)
                        bio.name = os.path.basename(requested_path)
                        await update.message.reply_document(document=bio, filename=bio.name)
                        await update.message.reply_text("📄 Файл отправлен!", reply_markup=back_button(), parse_mode='HTML')
                    else:
                        await update.message.reply_text("❌ Файл пустой!", reply_markup=back_button(), parse_mode='HTML')
                    return
                elif any(f.startswith(requested_path) for f in file_list):
                    if not requested_path.endswith('/'):
                        requested_path += '/'
                    user_data[user_id]['selected_path'] = requested_path
                    escaped_path = escape_html_for_code(requested_path)[0]
                    message = (
                        f"📁 <b>Папка:</b> <code>{escaped_path}</code>\n"
                        f"Как отправить содержимое?"
                    )
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("📦 Как ZIP", callback_data='send_as_zip'),
                            InlineKeyboardButton("📄 Просто файлы", callback_data='send_files')
                        ],
                        [InlineKeyboardButton("⬅️ Назад", callback_data='back')]
                    ])
                    await update.message.reply_text(message, reply_markup=keyboard, parse_mode='HTML')
                else:
                    await update.message.reply_text("❌ Такого файла или папки нет в архиве!", reply_markup=back_button(),
                                                    parse_mode='HTML')
        elif state == 'waiting_for_currency_amount':
            try:
                amount = float(text.replace(',', '.'))
                if amount <= 0:
                    raise ValueError
                from_currency = user_data[user_id]['from_currency']
                to_currency = user_data[user_id]['to_currency']
                response = requests.get(f"https://api.exchangerate-api.com/v4/latest/{from_currency}", timeout=5)
                rate = response.json()['rates'][to_currency]
                result = amount * rate
                date = response.json()['date']
                user_data[user_id]['last_conversion'] = (amount, from_currency, to_currency)
                escaped_result = escape_html_for_code(f"{result:.2f}")[0]
                message = (
                    f"💱 <b>{amount} {from_currency} = <code>{escaped_result}</code> {to_currency}</b> 💸\n"
                    f"Обновлено на {date}"
                )
                await update.message.reply_text(message, reply_markup=currency_after_conversion_menu(), parse_mode='HTML')
                user_data[user_id]['state'] = None
            except ValueError:
                message = "❌ Введи положительное число (например, 100 или 15.5)!"
                await update.message.reply_text(message, reply_markup=back_button(), parse_mode='HTML')
            except requests.RequestException:
                message = "❌ Ошибка загрузки курса! Попробуй позже."
                await update.message.reply_text(message, reply_markup=back_button(), parse_mode='HTML')
        elif state == 'waiting_for_newlines_input':
            processed_text = remove_newlines(text)
            user_data[user_id]['processed_text'] = processed_text
            message = "🧹 <b>Без переносов</b>: ✨\n<i>Теперь выбирай: вывести или скачать!</i>"
            await update.message.reply_text(message, reply_markup=result_choice_menu(processed_text, 'remove_newlines'), parse_mode='HTML')
        elif state == 'waiting_for_deobfuscator_input':
            if not text.strip():
                await update.message.reply_text("❌ Введи непустой текст!", reply_markup=back_button(),
                                                parse_mode='HTML')
                return
            logging.info(f"Обработка текста для GPT Deobfuscator: '{text}'")
            processed_text, success = deobfuscate_text_gpt(text, filename="введенный_текст")
            if not success:
                logging.info(f"Текст не содержит \\u202F: '{text}'")
                await update.message.reply_text(processed_text, reply_markup=back_button(), parse_mode='HTML')
                return
            user_data[user_id]['processed_text'] = processed_text
            message = "🧼 <b>Символы \\u202F удалены</b>: ✨\n<i>Теперь выбирай: вывести или скачать!</i>"
            logging.info(f"Успешная деобфускация: '{processed_text}'")
            await update.message.reply_text(message, reply_markup=result_choice_menu(processed_text, 'deobfuscator'),
                                            parse_mode='HTML')
            user_data[user_id]['state'] = None
            user_data[user_id]['last_activity'] = datetime.now()
        elif state in ['waiting_for_remove_all_spaces_input', 'waiting_for_remove_all_newlines_input',
                       'waiting_for_remove_all_spaces_newlines_input', 'waiting_for_remove_extra_spaces_input',
                       'waiting_for_remove_extra_newlines_input', 'waiting_for_remove_extra_spaces_newlines_input']:
            mode = state.replace('waiting_for_', '').replace('_input', '')
            if mode == 'remove_all_spaces':
                processed_text = remove_all_spaces(text)
            elif mode == 'remove_all_newlines':
                processed_text = remove_all_newlines(text)
            elif mode == 'remove_all_spaces_newlines':
                processed_text = remove_all_spaces_newlines(text)
            elif mode == 'remove_extra_spaces':
                processed_text = remove_extra_spaces(text)
            elif mode == 'remove_extra_newlines':
                processed_text = remove_extra_newlines(text)
            elif mode == 'remove_extra_spaces_newlines':
                processed_text = remove_extra_spaces_newlines(text)
            user_data[user_id]['processed_text'] = processed_text
            message = f"🧹 <b>Обработано ({mode.replace('_', ' ')})</b>: ✨\n<i>Теперь выбирай: вывести или скачать!</i>"
            await update.message.reply_text(message, reply_markup=result_choice_menu(processed_text, mode),
                                            parse_mode='HTML')
        elif state == 'waiting_for_format_code_input':
            language = user_data[user_id].get('format_language', 'auto')
            logging.info(f"Форматирование кода, язык: {language}, текст: {text[:100]}...")
            processed_text = format_code(text, language)
            user_data[user_id]['processed_text'] = processed_text
            message = f"💻 <b>Отформатировано ({language})</b>: 🖥️\n<i>Теперь выбирай: вывести или скачать!</i>"
            await update.message.reply_text(message, reply_markup=result_choice_menu(processed_text, 'format_code'),
                                            parse_mode='HTML')
            user_data[user_id]['state'] = None
            user_data[user_id]['last_activity'] = datetime.now()
        else:
            message = "❌ Сначала выбери действие в меню!"
            await update.message.reply_text(message, reply_markup=main_menu(), parse_mode='HTML')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['last_activity'] = datetime.now()
    context.job_queue.run_once(clear_user_data, 600, data=user_id)
    document = update.message.document
    state = user_data[user_id].get('state')
    file_name = document.file_name
    file_size_mb = document.file_size / (1024 * 1024)
    mime_type = document.mime_type

    if file_size_mb > MAX_FILE_SIZE_MB:
        message = f"❌ Файл слишком большой ({file_size_mb:.2f} МБ > {MAX_FILE_SIZE_MB} МБ)!"
        await update.message.reply_text(message, reply_markup=back_button(), parse_mode='HTML')
        return

    file_content = await download_file_with_retries(document, update)
    logging.info(f"Received document: {file_name}, mime_type: {mime_type}, size: {file_size_mb:.2f} MB")

    if state in ['waiting_for_encrypt_input', 'waiting_for_decrypt_input', 'waiting_for_newlines_input',
                 'waiting_for_deobfuscator_input', 'waiting_for_remove_all_spaces_input',
                 'waiting_for_remove_all_newlines_input', 'waiting_for_remove_all_spaces_newlines_input',
                 'waiting_for_remove_extra_spaces_input', 'waiting_for_remove_extra_newlines_input',
                 'waiting_for_remove_extra_spaces_newlines_input', 'waiting_for_format_code_input']:
        text, error_message = extract_text_from_file(file_content, file_name, mime_type)
        if error_message:
            await update.message.reply_text(error_message, reply_markup=back_button(), parse_mode='HTML')
            return

        if state == 'waiting_for_encrypt_input':
            processed_text = encrypt_to_unicode(text)
            user_data[user_id]['processed_text'] = processed_text
            message = "🔒 <b>Зашифровано</b>: ✨\n<i>Теперь выбирай: вывести или скачать!</i>"
            await update.message.reply_text(message, reply_markup=result_choice_menu(processed_text, 'unicode_encrypt'),
                                            parse_mode='HTML')
        elif state == 'waiting_for_decrypt_input':
            processed_text = decrypt_from_unicode(text)
            if processed_text.startswith("❌"):
                await update.message.reply_text(processed_text, reply_markup=back_button(), parse_mode='HTML')
                return
            user_data[user_id]['processed_text'] = processed_text
            message = "🔓 <b>Расшифровано</b>: 😎\n<i>Теперь выбирай: вывести или скачать!</i>"
            await update.message.reply_text(message, reply_markup=result_choice_menu(processed_text, 'unicode_decrypt'),
                                            parse_mode='HTML')
        elif state in ['waiting_for_remove_all_spaces_input', 'waiting_for_remove_all_newlines_input',
                       'waiting_for_remove_all_spaces_newlines_input', 'waiting_for_remove_extra_spaces_input',
                       'waiting_for_remove_extra_newlines_input', 'waiting_for_remove_extra_spaces_newlines_input']:
            mode = state.replace('waiting_for_', '').replace('_input', '')
            logging.info(f"Processing document in mode {mode}")
            if not text.strip():
                logging.warning(f"Empty text extracted from {file_name}")
                message = "❌ Файл пустой или не содержит текста!"
                await update.message.reply_text(message, reply_markup=back_button(), parse_mode='HTML')
                return
            if mode == 'remove_all_spaces':
                processed_text = remove_all_spaces(text)
            elif mode == 'remove_all_newlines':
                processed_text = remove_all_newlines(text)
            elif mode == 'remove_all_spaces_newlines':
                processed_text = remove_all_spaces_newlines(text)
            elif mode == 'remove_extra_spaces':
                processed_text = remove_extra_spaces(text)
            elif mode == 'remove_extra_newlines':
                processed_text = remove_extra_newlines(text)
            elif mode == 'remove_extra_spaces_newlines':
                processed_text = remove_extra_spaces_newlines(text)
            user_data[user_id]['processed_text'] = processed_text
            message = f"🧹 <b>Обработано ({mode.replace('_', ' ')})</b>: ✨\n<i>Теперь выбирай: вывести или скачать!</i>"
            logging.info(f"Processed text: {processed_text[:100]}...")
            await update.message.reply_text(message, reply_markup=result_choice_menu(processed_text, mode),
                                            parse_mode='HTML')
            user_data[user_id]['state'] = None
        elif state == 'waiting_for_format_code_input':
            language = user_data[user_id].get('format_language', 'auto')
            processed_text = format_code(text, language)
            user_data[user_id]['processed_text'] = processed_text
            message = f"💻 <b>Отформатировано ({language})</b>: 🖥️\n<i>Теперь выбирай: вывести или скачать!</i>"
            await update.message.reply_text(message, reply_markup=result_choice_menu(processed_text, 'format_code'),
                                            parse_mode='HTML')
            user_data[user_id]['state'] = None
        elif state == 'waiting_for_deobfuscator_input':
            processed_text, success = deobfuscate_text_gpt(text, file_name)
            if not success:
                await update.message.reply_text(processed_text, reply_markup=back_button(), parse_mode='HTML')
                return
            user_data[user_id]['processed_text'] = processed_text
            message = "🧼 <b>Символы \\u202F удалены</b>: ✨\n<i>Теперь выбирай: вывести или скачать!</i>"
            await update.message.reply_text(message, reply_markup=result_choice_menu(processed_text, 'deobfuscator'),
                                            parse_mode='HTML')
            user_data[user_id]['state'] = None

    elif state == 'waiting_for_zip':
        extension = '.' + file_name.split('.')[-1].lower()
        if extension not in SUPPORTED_ZIP_FORMATS:
            message = f"❌ Неподдерживаемый формат! Используй: {', '.join(SUPPORTED_ZIP_FORMATS)}"
            await update.message.reply_text(message, reply_markup=back_button(), parse_mode='HTML')
            return
        result = await analyze_zip(file_content, update, context)
        if result.startswith("❌"):
            await update.message.reply_text(result, reply_markup=back_button(), parse_mode='HTML')
        else:
            user_data[user_id]['zip_data'] = file_content
            user_data[user_id]['zip_structure'] = result
            message = "📋 Выбери действие:"
            await update.message.reply_text(message, reply_markup=zip_action_menu(), parse_mode='HTML')

    elif state == 'waiting_for_texturepack':
        extension = '.' + file_name.split('.')[-1].lower()
        if extension != '.mcpack':
            message = "❌ Загрузи файл в формате .mcpack!"
            await update.message.reply_text(message, reply_markup=back_button(), parse_mode='HTML')
            return

        user_data[user_id]['texturepack_data'] = {
            'file_id': document.file_id,
            'file_name': file_name,
            'file_size': document.file_size
        }

        mode = user_data[user_id].get('texturepack_mode', 'obfuscate')
        if mode == 'deobfuscate' and 'remove_comments' not in user_data[user_id]:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Удалить комментарии", callback_data='texturepack_remove_comments'),
                 InlineKeyboardButton("💾 Сохранить комментарии", callback_data='texturepack_keep_comments')],
                [InlineKeyboardButton("🏠 В меню", callback_data='back')]
            ])
            await update.message.reply_text(
                "🔓 <b>Удалить комментарии из JSON-файлов при деобфускации?</b>",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            logging.info(f"Запрошен выбор удаления комментариев для пользователя {user_id}")
            return

        await process_texturepack_file(
            update=update,
            context=context,
            file_id=document.file_id,
            file_name=file_name,
            file_size=document.file_size
        )

    else:
        message = "❌ Сначала выбери действие в меню!"
        await update.message.reply_text(message, reply_markup=main_menu(), parse_mode='HTML')

# Основная функция для запуска бота
async def webhook(request):
    try:
        update = Update.de_json(json.loads(await request.text()), application.bot)
        await application.process_update(update)
        return web.Response(status=200)
    except Exception as e:
        logging.error(f"Ошибка в вебхуке: {e}")
        return web.Response(status=500)

# Главная страница для проверки
async def index(request):
    return web.Response(text="Бот работает!")

# Настройка приложения с webhook
async def init_app(app):
    await application.initialize()
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logging.info(f"Вебхук установлен: {WEBHOOK_URL}")
    return app

# Основная функция
def main() -> None:
    global application
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Настройка веб-сервера
    app = web.Application()
    app.router.add_post('/webhook', webhook)
    app.router.add_get('/', index)

    # Запуск веб-сервера
    port = int(os.getenv('PORT', 8000))
    web.run_app(init_app(app), host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()