# app/__init__.py

from flask import Flask
from config import Config
from redis import Redis
from rq import Queue
from flask_wtf import CSRFProtect

app = Flask(__name__)  # Создаем экземпляр приложения
app.config.from_object(Config)  # Загружаем настройки из config.py

# Инициализируем подключение к Redis и очередь задач RQ
redis_conn = Redis.from_url(app.config['REDIS_URL'])
task_queue = Queue(connection=redis_conn)

# Включаем CSRF-защиту
csrf = CSRFProtect(app)

from app import routes  # Импортируем маршруты

