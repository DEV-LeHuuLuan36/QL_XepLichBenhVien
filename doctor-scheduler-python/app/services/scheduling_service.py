import datetime
import random
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select 
from app import db 
from app.models import (
    Doctor, Clinic, Shift, LeaveRequest, SchedulePreference, 
    SchedulingJob, Assignment
)
from app.models.doctor import DoctorRole
from app.models.scheduling_job import JobStatus 
from .solver_service import ScheduleState, CostFunction, ScheduleAnnealer, ScheduleContextData
from collections import defaultdict
import math 
import traceback 

class SchedulingService:
    """
    Lớp dịch vụ cấp cao để xử lý logic xếp lịch.
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def run_scheduling_job(self, job_id: int):
        print(f"--- Service: Bắt đầu xử lý Tác vụ Xếp lịch ID: {job_id} ---")
        job = self.db.get(SchedulingJob, job_id)

        if not job:
            print(f"Service Error: Không tìm thấy Job ID {job_id}.")
            return 
        
        if job.status != JobStatus.PENDING:
            print(f"Service Info: Tác vụ {job_id} không ở trạng thái 'Pending'. Bỏ qua.")
            return

        try:
            print(f"Service: Cập nhật Job {job_id} sang 'Running'.")
            job.status = JobStatus.RUNNING
            job.status_message = None 
            self.db.commit() 

            print(f"Service: Chuẩn bị dữ liệu ngữ cảnh cho Job {job_id}...")
            context_data: ScheduleContextData = self._build_context(job.start_date, job.end_date)
            
            if not context_data.doctors or not context_data.clinics or not context_data.shifts:
                 raise ValueError("Dữ liệu đầu vào (Bác sĩ/Phòng khám/Ca trực) không đủ.")
            
            print(f"Service: Tạo giải pháp ban đầu THÔNG MINH (Đúng định biên)...")
            initial_assignments = self._create_smart_initial_solution(context_data)
            
            initial_state = ScheduleState(initial_assignments) 

            print(f"Service: Khởi tạo Annealer...")
            cost_function = CostFunction(context_data)
            annealer = ScheduleAnnealer(initial_state, cost_function) 

            # ============================================================
            # CẤU HÌNH THAM SỐ CHO THUẬT TOÁN SIMULATED ANNEALING (AI)
            # ============================================================
            
            # 1. Tmax (Nhiệt độ đầu): Độ "nóng" ban đầu.
            # - Ý nghĩa: Nhiệt độ càng cao, thuật toán càng dễ chấp nhận các phương án xấu hơn tạm thời.
            # - Tác dụng: Giúp thuật toán "nhảy" ra khỏi các hố sâu cục bộ (local minima) để tìm vùng đất mới tốt hơn.
            annealer.Tmax = 25000.0  

            # 2. Tmin (Nhiệt độ cuối): Độ "lạnh" kết thúc.
            # - Ý nghĩa: Khi nhiệt độ giảm dần về Tmin, thuật toán trở nên khắt khe.
            # - Tác dụng: Giai đoạn này giúp thuật toán "tinh chỉnh" (fine-tune) để hội tụ về kết quả tốt nhất có thể.
            annealer.Tmin = 2.5      

            # 3. Steps (Tổng số bước lặp):
            # - Ý nghĩa: Tổng số lần thuật toán thử thay đổi lịch để tìm phương án tốt hơn.
            # - Tác dụng: Số bước càng lớn -> khả năng tìm ra lịch tối ưu càng cao, nhưng thời gian chạy càng lâu.
            annealer.steps = 50000   

            # 4. Updates (Tần suất báo cáo):
            # - Ý nghĩa: Chia tổng số bước (steps) cho số này để quyết định bao lâu in log ra console một lần.
            # - Ví dụ: steps=100.000, updates=10 => Cứ mỗi 10.000 bước sẽ in ra 1 dòng log.
            # - Tác dụng: Giúp theo dõi "sức khỏe" thuật toán chạy theo thời gian thực mà không làm tràn màn hình console.
            annealer.updates = 10   
            
            # ============================================================

            print(f"Service: Bắt đầu chạy Annealer cho Job {job_id}...")
            best_state, best_cost = annealer.anneal() 
            print(f"Service: Hoàn thành. Chi phí tốt nhất: {best_cost}")

            print(f"Service: Đang phân tích chi tiết kết quả...")
            cost_function.print_detailed_report(best_state) 

            print(f"Service: Lưu kết quả cho Job {job_id}...")
            self._save_results(job, best_state, context_data) 

            job.status = JobStatus.COMPLETED
            job.status_message = f"Hoàn thành với chi phí: {best_cost:.2f}"
            self.db.commit() 

        except Exception as e:
            print(f"!!! Service Error: Lỗi khi xử lý Job {job_id}: {str(e)} !!!") 
            traceback.print_exc() 
            self.db.rollback() 
            
            job = self.db.get(SchedulingJob, job_id) 
            if job:
                job.status = JobStatus.FAILED
                error_message = str(e)[:900]
                job.status_message = f"Lỗi: {error_message}" 
                self.db.commit() 

    def _build_context(self, start_date: datetime.date, end_date: datetime.date) -> ScheduleContextData:
        # Load dữ liệu kèm quan hệ nếu cần thiết
        doctors = self.db.scalars(select(Doctor)).all()
        clinics = self.db.scalars(select(Clinic)).all()
        shifts = self.db.scalars(select(Shift)).all()
        
        leaves_stmt = select(LeaveRequest).where(
            LeaveRequest.date.between(start_date, end_date)
        )
        leaves = self.db.scalars(leaves_stmt).all()
        
        preferences = self.db.scalars(select(SchedulePreference)).all()

        doctors_map = {d.id: d for d in doctors}
        clinics_map = {c.id: c for c in clinics}
        shifts_map = {s.id: s for s in shifts}
        
        leaves_map = defaultdict(bool) 
        for l in leaves:
            leaves_map[(l.doctor_id, l.date)] = True 

        preferences_map = defaultdict(int) 
        for p in preferences:
            preferences_map[(p.doctor_id, p.shift_id, p.day_of_week)] = p.preference_score

        date_range = list(self._daterange(start_date, end_date)) 

        context = ScheduleContextData(
            doctors=doctors, clinics=clinics, shifts=shifts,
            leaves_map=leaves_map, preferences_map=preferences_map,
            date_range=date_range,
            doctors_map=doctors_map, clinics_map=clinics_map, shifts_map=shifts_map
        )
        return context

    def _create_smart_initial_solution(self, ctx: ScheduleContextData) -> dict:
        """
        Tạo lịch ban đầu ĐÚNG ĐỊNH BIÊN (Correct by Construction):
        - Duyệt từng ngày, từng ca, từng khoa.
        - Lấy đủ số lượng bác sĩ Chính và Phụ từ danh sách biên chế của khoa đó.
        - Chưa quan tâm đến luật 48h hay nghỉ ngơi (để Annealer tối ưu sau).
        """
        assignments = {} 

        for date in ctx.date_range:
            assignments[date] = {}
            
            for clinic in ctx.clinics:
                clinic_id = clinic.id
                assignments[date][clinic_id] = {}
                
                # Danh sách bác sĩ của khoa này
                # (Sử dụng list đã phân loại trong Context)
                main_candidates = ctx.doctors_by_clinic[clinic_id]['main']
                sub_candidates = ctx.doctors_by_clinic[clinic_id]['sub']
                
                for shift in ctx.shifts:
                    shift_id = shift.id
                    assigned_docs = []

                    # 1. Chọn Bác sĩ CHÍNH
                    req_main = clinic.required_main
                    if len(main_candidates) >= req_main:
                        # Chọn ngẫu nhiên đủ số lượng
                        # Lưu ý: Ở bước này có thể chọn người đang xin nghỉ, 
                        # Annealer sẽ tính đó là lỗi (cost cao) và tìm cách đổi người khác sau.
                        assigned_docs.extend(random.sample(main_candidates, k=req_main))
                    else:
                        # Nếu thiếu người (ít gặp nếu seed data tốt), lấy hết
                        assigned_docs.extend(main_candidates)
                        print(f"Warn: Khoa {clinic.name} thiếu bác sĩ Chính (Cần {req_main}, có {len(main_candidates)})")

                    # 2. Chọn Bác sĩ PHỤ
                    req_sub = clinic.required_sub
                    if len(sub_candidates) >= req_sub:
                        assigned_docs.extend(random.sample(sub_candidates, k=req_sub))
                    else:
                        assigned_docs.extend(sub_candidates)
                        print(f"Warn: Khoa {clinic.name} thiếu bác sĩ Phụ")
                    
                    assignments[date][clinic_id][shift_id] = assigned_docs
        
        return assignments 

    def _save_results(self, job: SchedulingJob, state: ScheduleState, context: ScheduleContextData):
        # Xóa cũ
        self.db.query(Assignment).filter(Assignment.job_id == job.id).delete(synchronize_session=False)
        
        new_assignments = []
        for date, clinic_data in state.assignments.items():
            for clinic_id, shift_data in clinic_data.items():
                for shift_id, doctor_ids in shift_data.items():
                    for doc_id in doctor_ids:
                        assign = Assignment(
                            assignment_date=date, 
                            doctor_id=doc_id,
                            clinic_id=clinic_id,
                            shift_id=shift_id,
                            job_id=job.id
                        )
                        new_assignments.append(assign)
        
        if new_assignments:
            self.db.add_all(new_assignments)

    def _daterange(self, start_date, end_date):
        for n in range(int((end_date - start_date).days) + 1):
            yield start_date + datetime.timedelta(n)

    # FILE: app/services/scheduling_service.py

    # Thêm hàm phụ trợ này vào trong class SchedulingService
    def _is_shift_needed(self, clinic_name, shift_name):
        # Nếu khoa có chữ "24/7" -> Cần mọi ca
        if "24/7" in clinic_name:
            return True
        # Nếu khoa thường -> Chỉ nhận ca Sáng và Chiều (Bỏ ca Đêm)
        if "Đêm" in shift_name:
            return False
        return True

    def _create_smart_initial_solution(self, ctx: ScheduleContextData) -> dict:
        assignments = {} 

        for date in ctx.date_range:
            assignments[date] = {}
            
            for clinic in ctx.clinics:
                clinic_id = clinic.id
                assignments[date][clinic_id] = {}
                
                main_candidates = ctx.doctors_by_clinic[clinic_id]['main']
                sub_candidates = ctx.doctors_by_clinic[clinic_id]['sub']
                
                for shift in ctx.shifts:
                    # [QUAN TRỌNG] Kiểm tra xem khoa này có cần trực ca này không
                    if not self._is_shift_needed(clinic.name, shift.name):
                        continue # Bỏ qua, không xếp người

                    shift_id = shift.id
                    assigned_docs = []

                    # Logic chọn người như cũ
                    req_main = clinic.required_main
                    if len(main_candidates) >= req_main:
                        assigned_docs.extend(random.sample(main_candidates, k=req_main))
                    else:
                        assigned_docs.extend(main_candidates)

                    req_sub = clinic.required_sub
                    if len(sub_candidates) >= req_sub:
                        assigned_docs.extend(random.sample(sub_candidates, k=req_sub))
                    else:
                        assigned_docs.extend(sub_candidates)
                    
                    assignments[date][clinic_id][shift_id] = assigned_docs
        
        return assignments