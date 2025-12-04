import traceback
import click
from app import db
from app.models import (
    Doctor, Clinic, Shift, LeaveRequest, SchedulePreference,
    SchedulingJob, Assignment
)
from app.models.doctor import DoctorRole
from sqlalchemy import select
import random
import datetime

# --- Danh sách tên mẫu ---
FIRST_NAMES = [
    "An", "Anh", "Bảo", "Bình", "Cẩm", "Châu", "Chi", "Cường", "Dũng", "Dương",
    "Đại", "Đức", "Giang", "Hà", "Hải", "Hằng", "Hạnh", "Hiếu", "Hoa", "Hòa",
    "Hoàng", "Hùng", "Huy", "Huyền", "Khánh", "Kiên", "Lan", "Linh", "Long", "Mai",
    "Mạnh", "Minh", "Nam", "Nga", "Ngọc", "Nguyên", "Nhật", "Nhung", "Phong", "Phúc",
    "Phú", "Phượng", "Quân", "Quang", "Quỳnh", "Sơn", "Tâm", "Thắng", "Thanh", "Thảo",
    "Thi", "Thịnh", "Thu", "Thủy", "Tiến", "Trang", "Trí", "Trung", "Tuấn", "Tú",
    "Tùng", "Vân", "Vi", "Việt", "Vinh", "Vũ"
]
LAST_NAMES = [
    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng",
    "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"
]

def register_seeder(app):
    """Đăng ký các lệnh seed với ứng dụng Flask."""
    
    @app.cli.group(name='seed')
    def seed_cli():
        """Các lệnh để gieo dữ liệu (seed) vào CSDL."""
        pass

    @seed_cli.command(name='all')
    def seed_all():
        print("--- Bắt đầu tạo dữ liệu chuẩn nghiệp vụ Bệnh viện (24/7, Phân vai trò) ---")
        
        try:
            # === BƯỚC 1: XÓA DỮ LIỆU CŨ ===
            print("1/5: Xóa dữ liệu cũ...")
            db.session.query(Assignment).delete()
            db.session.query(SchedulePreference).delete()
            db.session.query(LeaveRequest).delete()
            db.session.query(SchedulingJob).delete()
            db.session.query(Doctor).delete()
            db.session.query(Clinic).delete()
            db.session.query(Shift).delete()
            db.session.commit() 
            print("...Đã xóa xong dữ liệu cũ.")

            # === BƯỚC 2: TẠO 3 CA TRỰC CHUẨN (24h) ===
            print("2/5: Tạo 3 Ca trực (Sáng/Chiều/Đêm)...")
            # Ca 1: 6h - 14h (8 tiếng)
            # Ca 2: 14h - 22h (8 tiếng)
            # Ca 3: 22h - 6h hôm sau (8 tiếng)
            shifts_data = [
                Shift(name="Ca Sáng (6h-14h)", start_time=datetime.time(6, 0), end_time=datetime.time(14, 0)),
                Shift(name="Ca Chiều (14h-22h)", start_time=datetime.time(14, 0), end_time=datetime.time(22, 0)),
                Shift(name="Ca Đêm (22h-6h)", start_time=datetime.time(22, 0), end_time=datetime.time(6, 0))
            ]
            db.session.add_all(shifts_data)
            db.session.commit()
            
            # Lấy lại danh sách ca để dùng ID sau này
            all_shifts = db.session.scalars(select(Shift)).all()

            # === BƯỚC 3: TẠO KHOA VÀ BÁC SĨ ===
            print("3/5: Tạo Khoa và Bác sĩ biên chế (Khoảng 20 người/khoa)...")
            
            clinic_names = [
                "Khoa Cấp Cứu", 
                "Khoa Hồi Sức Tích Cực (ICU)", 
                "Khoa Nội Tổng Quát", 
                "Khoa Ngoại", 
                "Khoa Nhi"
            ]
            
            for c_name in clinic_names:
                # Tạo Khoa: Cấu hình mặc định 2 Chính, 1 Phụ
                clinic = Clinic(
                    name=c_name, 
                    required_main=2, 
                    required_sub=1
                )
                db.session.add(clinic)
                db.session.commit() # Commit để lấy ID
                
                # Tạo 20 Bác sĩ cho khoa này
                # Tỷ lệ: 12 Chính (để đủ xoay tua 3 ca * 2 người = 6 slot/ngày), 8 Phụ
                doctors_for_clinic = []
                for i in range(20):
                    is_main = i < 12 # 12 người đầu là Chính
                    role = DoctorRole.MAIN if is_main else DoctorRole.SUB
                    
                    full_name = f"{random.choice(LAST_NAMES)} {random.choice(FIRST_NAMES)}"
                    
                    doc = Doctor(
                        name=full_name,
                        specialty=c_name, # Chuyên khoa theo tên Khoa
                        role=role,
                        clinic_id=clinic.id, # Gán biên chế về khoa này
                        total_shifts_worked=0
                    )
                    doctors_for_clinic.append(doc)
                
                db.session.add_all(doctors_for_clinic)
            
            db.session.commit()
            print("...Đã tạo xong Khoa và Bác sĩ.")

            # === BƯỚC 4: TẠO DỮ LIỆU CON (Đơn nghỉ, Nguyện vọng) ===
            print("4/5: Tạo Đơn nghỉ và Nguyện vọng ngẫu nhiên...")
            
            all_doctors = db.session.scalars(select(Doctor)).all()
            
            leaves_to_add = []
            prefs_to_add = []
            
            # Tạo một số đơn nghỉ cho tháng 12/2025
            for _ in range(50):
                random_doctor = random.choice(all_doctors)
                random_day = random.randint(1, 31)
                leave_date = datetime.date(2025, 12, random_day)
                
                # Kiểm tra trùng lặp đơn giản
                if not any(l.doctor_id == random_doctor.id and l.date == leave_date for l in leaves_to_add):
                    leaves_to_add.append(LeaveRequest(
                        doctor_id=random_doctor.id,
                        date=leave_date,
                        reason="Việc riêng",
                        status="Approved"
                    ))
            db.session.add_all(leaves_to_add)

            # Tạo nguyện vọng
            for _ in range(100):
                random_doctor = random.choice(all_doctors)
                random_shift = random.choice(all_shifts)
                random_day_of_week = random.randint(0, 6) 
                random_score = random.choice([-10, 10]) # Thích hoặc Ghét nhẹ
                
                prefs_to_add.append(SchedulePreference(
                    doctor_id=random_doctor.id,
                    shift_id=random_shift.id,
                    day_of_week=random_day_of_week,
                    preference_score=random_score
                ))
            db.session.add_all(prefs_to_add)

            db.session.commit()
            print("...Đã tạo xong dữ liệu con.")
            
            print("5/5: HOÀN THÀNH! Dữ liệu mẫu đã sẵn sàng.")
            
        except Exception as e:
            db.session.rollback()
            print(f"!!! LỖI KHI ĐANG GIEO DỮ LIỆU !!!")
            print(f"Lỗi: {str(e)}")
            traceback.print_exc()
        finally:
            db.session.close()