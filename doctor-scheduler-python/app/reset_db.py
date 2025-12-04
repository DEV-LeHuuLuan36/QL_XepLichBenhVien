import os
import sys
from dotenv import load_dotenv

# --- CẤU HÌNH ĐƯỜNG DẪN & MÔI TRƯỜNG ---
# Xác định thư mục gốc của dự án (project_root) từ vị trí file này (app/reset_db.py)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) # Lên 1 cấp: từ app/ ra doctor-scheduler-python/

# Thêm project root vào sys.path để Python tìm được package 'app'
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Tải biến môi trường từ file .env ở thư mục gốc
load_dotenv(os.path.join(project_root, '.env'))

# --- BÂY GIỜ MỚI IMPORT APP ---
from app import create_app, db
# Import tất cả models để SQLAlchemy biết cấu trúc bảng cần tạo
from app.models import Doctor, Clinic, Shift, LeaveRequest, SchedulePreference, SchedulingJob, Assignment

app = create_app()

with app.app_context():
    print(f"--> Kết nối CSDL: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    print("\n[1/3] Đang XÓA toàn bộ bảng cũ...")
    # drop_all() sẽ xóa các bảng dựa trên metadata của models đã import
    db.drop_all()
    print("... Đã xóa xong.")
    
    print("\n[2/3] Đang TẠO bảng mới theo schema mới...")
    # Tạo lại bảng với đầy đủ cột (role, clinic_id, required_main, v.v.)
    db.create_all()
    print("... Đã tạo bảng thành công!")
    
    print("\n[3/3] HOÀN TẤT.")
    print(">>> Bước tiếp theo: Hãy chạy lệnh 'flask seed all' để tạo dữ liệu mẫu.")