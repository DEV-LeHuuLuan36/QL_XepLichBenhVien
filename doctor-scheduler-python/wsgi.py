# /doctor-scheduler-python/wsgi.py

from dotenv import load_dotenv
import os

# Tải các biến môi trường từ file .env 
load_dotenv() 

from app import create_app
app = create_app()
if __name__ == "__main__":
    # Lấy debug mode từ biến môi trường để an toàn
    DEBUG_MODE = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(debug=DEBUG_MODE)

