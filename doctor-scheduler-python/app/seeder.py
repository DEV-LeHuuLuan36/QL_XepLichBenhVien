import traceback
import click
from app import db
from app.models import (
    Doctor, Clinic, Shift, LeaveRequest, SchedulePreference,
    SchedulingJob, Assignment
)
from app.models.scheduling_job import JobStatus 
from sqlalchemy import select
import random
import datetime

# --- Danh sách tên mẫu lớn hơn ---
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
SPECIALTIES = [
    "Tim mạch", "Nhi khoa", "Ngoại tổng quát", "Nội tiết", "Tai Mũi Họng", 
    "Da liễu", "Chấn thương chỉnh hình", "Sản phụ khoa", "Ung bướu", "Thần kinh",
    "Mắt", "Hô hấp"
]
CLINIC_NAMES = [
    "Phòng khám Tim mạch", "Phòng khám Nhi", "Phòng khám Ngoại", "Phòng khám Da liễu",
    "Phòng khám Tai Mũi Họng", "Phòng khám Sản", "Phòng khám Nội tiết", 
    "Phòng khám Chấn thương", "Phòng khám Thần kinh", "Phòng khám Mắt"
]
# --- Kết thúc danh sách tên mẫu ---


def register_seeder(app):
    """Đăng ký các lệnh seed với ứng dụng Flask."""
    
    @app.cli.group(name='seed')
    def seed_cli():
        """Các lệnh để gieo dữ liệu (seed) vào CSDL."""
        pass

    @seed_cli.command(name='all')
    def seed_all():
        """Xóa dữ liệu cũ và gieo toàn bộ dữ liệu mẫu (Doctors, Clinics, Shifts, v.v.)."""
        
        print("--- Bắt đầu quá trình gieo dữ liệu (seeding) ---")
        
        try:
            # === BƯỚC 1: XÓA DỮ LIỆU CŨ ===
            print("1/5: Xóa dữ liệu cũ (Assignments, Preferences, Leaves, Jobs)...")
            db.session.query(Assignment).delete()
            db.session.query(SchedulePreference).delete()
            db.session.query(LeaveRequest).delete()
            db.session.query(SchedulingJob).delete()
            db.session.commit() 
            
            print("2/5: Xóa dữ liệu cũ (Doctors, Clinics, Shifts)...")
            db.session.query(Doctor).delete()
            db.session.query(Clinic).delete()
            db.session.query(Shift).delete()
            db.session.commit() 
            print("...Đã xóa xong dữ liệu cũ.")

            # === BƯỚC 2: TẠO DỮ LIỆU MẪU (CHA) ===
            print("3/5: Tạo 30 Bác sĩ, 10 Phòng khám, 3 Ca trực...")
            
            # Tạo 30 Bác sĩ
            doctors_data = []
            for _ in range(30):
                full_name = f"{random.choice(LAST_NAMES)} {random.choice(FIRST_NAMES)}"
                # Tránh trùng tên
                if not any(d.name == full_name for d in doctors_data):
                    doctors_data.append(Doctor(
                        name=full_name, 
                        specialty=random.choice(SPECIALTIES), 
                        total_shifts_worked=0
                    ))
            db.session.add_all(doctors_data)

            # Tạo 10 Phòng khám
            clinics_data = []
            for name in CLINIC_NAMES:
                clinics_data.append(Clinic(
                    name=name, 
                    min_doctors_required=random.choice([1, 1, 2, 2, 3]) # Hầu hết cần 1-2, 1 phòng cần 3
                ))
            db.session.add_all(clinics_data)

            # Tạo 3 Ca trực
            shifts_data = [
                Shift(name="Ca Sáng", start_time=datetime.time(7, 0, 0), end_time=datetime.time(15, 0, 0)),
                Shift(name="Ca Chiều", start_time=datetime.time(15, 0, 0), end_time=datetime.time(23, 0, 0)),
                Shift(name="Ca Đêm", start_time=datetime.time(23, 0, 0), end_time=datetime.time(7, 0, 0))
            ]
            db.session.add_all(shifts_data)

            # --- QUAN TRỌNG: Commit để lấy ID ---
            db.session.commit()
            print("...Đã tạo xong Bác sĩ, Phòng khám, Ca trực.")

            # === BƯỚC 3: TẠO DỮ LIỆU MẪU (CON) ===
            print("4/5: Tạo 100 Đơn nghỉ ngẫu nhiên và 100 Nguyện vọng ngẫu nhiên...")
            
            all_doctors = db.session.scalars(select(Doctor)).all()
            all_shifts = db.session.scalars(select(Shift)).all()
            
            if not all_doctors or not all_shifts:
                print("Lỗi: Không tìm thấy bác sĩ/ca trực để tạo dữ liệu con.")
                return

            leaves_to_add = []
            prefs_to_add = []
            
            # Tạo 100 đơn nghỉ ngẫu nhiên (cho tháng 12/2025)
            for _ in range(100):
                random_doctor = random.choice(all_doctors)
                random_day = random.randint(1, 31)
                leave_date = datetime.date(2025, 12, random_day)
                
                if not any(l.doctor_id == random_doctor.id and l.date == leave_date for l in leaves_to_add):
                    leaves_to_add.append(LeaveRequest(
                        doctor_id=random_doctor.id,
                        date=leave_date,
                        reason="Nghỉ phép",
                        status="Approved"
                    ))
            db.session.add_all(leaves_to_add)

            # Tạo 100 nguyện vọng ngẫu nhiên
            for _ in range(100):
                random_doctor = random.choice(all_doctors)
                random_shift = random.choice(all_shifts)
                random_day_of_week = random.randint(0, 6) 
                random_score = random.choice([-20, -10, 10, 20]) 
                
                if not any(p.doctor_id == random_doctor.id and p.shift_id == random_shift.id and p.day_of_week == random_day_of_week for p in prefs_to_add):
                    prefs_to_add.append(SchedulePreference(
                        doctor_id=random_doctor.id,
                        shift_id=random_shift.id,
                        day_of_week=random_day_of_week,
                        preference_score=random_score
                    ))
            db.session.add_all(prefs_to_add)

            # Commit lần cuối
            db.session.commit()
            print("...Đã tạo xong Đơn nghỉ và Nguyện vọng.")
            
            print("5/5: HOÀN THÀNH! Dữ liệu mẫu lớn đã được gieo thành công.")
            
        except Exception as e:
            db.session.rollback()
            print(f"!!! LỖI KHI ĐANG GIEO DỮ LIỆU !!!")
            print(f"Lỗi: {str(e)}")
            traceback.print_exc()
        finally:
            db.session.close()