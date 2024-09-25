# config.py

class Config:
    SECRET_KEY = 'VKR' 
    REDIS_URL = 'redis://localhost:6379/0'  # URL для подключения к Redis
    WTF_CSRF_ENABLED = True  # Включаем CSRF-защиту для форм

