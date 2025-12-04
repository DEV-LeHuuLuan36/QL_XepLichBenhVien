import os
import sys
from dotenv import load_dotenv
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
load_dotenv()
print(f"DEBUG: DB URI từ .env = {os.environ.get('SQLALCHEMY_DATABASE_URI')}")


# Import các thành phần cần thiết TỪ app
from app import create_app, db
from app.services.scheduling_service import SchedulingService
from app.models import SchedulingJob # Import SchedulingJob

JOB_ID_TO_RUN = 5 # <<< Giữ nguyên số 3 (hoặc đổi thành 1, 2, 4)

# Tạo ứng dụng Flask để có app context
app = create_app()

print(f"DEBUG: DB URI trong app.config = {app.config.get('SQLALCHEMY_DATABASE_URI')}")



# Chạy code bên trong app context
with app.app_context():
    print(f"--- Bắt đầu chạy thử Solver cho Job ID: {JOB_ID_TO_RUN} ---")
    
    # Lấy Job từ CSDL
    job_to_run = db.session.get(SchedulingJob, JOB_ID_TO_RUN)
    if not job_to_run:
        print(f"Lỗi: Không tìm thấy Job với ID {JOB_ID_TO_RUN} trong CSDL.")
        try:
             # truy vấn tất cả các Job ID xem có lấy được không
             all_job_ids = db.session.scalars(db.select(SchedulingJob.id)).all()
             print(f"DEBUG: Các Job ID tìm thấy trong session hiện tại: {all_job_ids}")
        except Exception as e:
             print(f"DEBUG: Lỗi khi thử truy vấn tất cả Job ID: {e}")
    elif job_to_run.status.value != 'Pending':
         print(f"Lỗi: Job {JOB_ID_TO_RUN} không ở trạng thái 'Pending' (hiện tại: {job_to_run.status.value}). Không thể chạy.")
    else:
        try:
            scheduler_service = SchedulingService(db.session)
            scheduler_service.run_scheduling_job(JOB_ID_TO_RUN)
            job_after_run = db.session.get(SchedulingJob, JOB_ID_TO_RUN)
            print(f"--- Chạy thử hoàn tất ---")
            print(f"Trạng thái cuối cùng của Job {JOB_ID_TO_RUN}: {job_after_run.status.value}")
            if job_after_run.status.value == 'Failed':
                print(f"Lý do thất bại: {job_after_run.status_message}")
        except Exception as e:
            print(f"\n!!! LỖI NGHIÊM TRỌNG KHI CHẠY TRỰC TIẾP !!!")
            import traceback
            traceback.print_exc() 

print(f"--- Kết thúc chạy thử ---")