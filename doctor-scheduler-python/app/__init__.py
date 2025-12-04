from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from app.models.base import Base

# ---  Khởi tạo extensions ---
db = SQLAlchemy(model_class=Base)
migrate = Migrate()

def create_app():
    """
    Hàm factory để tạo và cấu hình ứng dụng Flask.
    (Phiên bản đã thêm Seeder CLI)
    """
    app = Flask(__name__)

    # --- Tải cấu hình (DB_URI) ---
    DB_URI = os.environ.get('SQLALCHEMY_DATABASE_URI')
    if not DB_URI:
        raise RuntimeError("SQLALCHEMY_DATABASE_URI is not set. Check your .env file.")
    
    app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
    app.config['SECRET_KEY'] = 'day-la-khoa-bi-mat-cua-ban-12345'
    db.init_app(app)
    migrate.init_app(app, db) 
    from app import models
    from app.routes.main_routes import main_bp
    app.register_blueprint(main_bp)
    from app import seeder
    seeder.register_seeder(app)


    @app.route('/health')
    def health_check():
        return jsonify({"status": "ok"})

    return app