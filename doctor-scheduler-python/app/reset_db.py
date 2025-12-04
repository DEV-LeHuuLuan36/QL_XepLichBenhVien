from app import create_app, db
from app.models import * # Import tất cả models để SQLAlchemy biết cấu trúc

app = create_app()

with app.app_context():
    print("Đang xóa toàn bộ bảng cũ...")
    db.drop_all()
    print("Đã xóa xong.")
    
    print("Đang tạo bảng mới theo schema mới...")
    db.create_all()
    print("Đã tạo bảng thành công!")
    print("Bây giờ hãy chạy lệnh: flask seed all")