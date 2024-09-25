# run.py

from app import app
import logging

if __name__ == '__main__':
    # Настраиваем логирование в файл
    logging.basicConfig(filename='app.log', level=logging.INFO)
    app.run(debug=True, port=5001)

