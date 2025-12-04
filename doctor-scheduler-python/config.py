# /doctor-scheduler-python/config.py

import os
from dotenv import load_dotenv
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    """
    Lớp cấu hình chung cho ứng dụng Flask.
    """
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'một-chuỗi-bí-mật-khó-đoán'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # TODO: Cấu hình cho Celery (Redis broker)
    # CELERY_BROKER_URL = 'redis://localhost:6379/0'
    # CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

