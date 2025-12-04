import datetime
import random
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select 
from app import db 
from app.models import (
    Doctor, Clinic, Shift, LeaveRequest, SchedulePreference, 
    SchedulingJob, Assignment
)
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
            print(f"Service Info: Tác vụ {job_id} không ở trạng thái 'Pending' (hiện tại: {job.status.value}). Bỏ qua.")
            return

        try:
            print(f"Service: Cập nhật Job {job_id} sang 'Running'.")
            job.status = JobStatus.RUNNING
            job.status_message = None 
            self.db.commit() 

            print(f"Service: Chuẩn bị dữ liệu ngữ cảnh cho Job {job_id} (Từ {job.start_date} đến {job.end_date})...")
            context_data: ScheduleContextData = self._build_context(job.start_date, job.end_date)
            
            if not context_data.doctors or not context_data.clinics or not context_data.shifts:
                 raise ValueError("Dữ liệu đầu vào (Bác sĩ/Phòng khám/Ca trực) không đủ để xếp lịch.")
            
            print(f"Service: Tạo giải pháp ban đầu THÔNG MINH cho Job {job_id}...")
            # Hàm này giờ sẽ cố gắng đáp ứng MinDocs và Đơn nghỉ
            initial_assignments = self._create_smart_initial_solution(context_data)
            
            initial_state = ScheduleState(initial_assignments) 

            print(f"Service: Khởi tạo Annealer cho Job {job_id}...")
            cost_function = CostFunction(context_data)
            annealer = ScheduleAnnealer(initial_state, cost_function) 

            # Cấu hình AI (có thể tăng 'steps' nếu muốn chạy kỹ hơn)
            annealer.Tmax = 25000.0  
            annealer.Tmin = 2.5      
            annealer.steps = 100000   # Tăng số bước
            annealer.updates = 200   
            
            print(f"Service: Bắt đầu chạy Annealer (Simulated Annealing) cho Job {job_id}...")
            best_state, best_cost = annealer.anneal() 
            print(f"Service: Annealer hoàn thành cho Job {job_id}. Chi phí tốt nhất: {best_cost}")

            print(f"Service: Lưu kết quả cho Job {job_id}...")
            self._save_results(job, best_state, context_data) 

            print(f"Service: Cập nhật Job {job_id} sang 'Completed'.")
            job.status = JobStatus.COMPLETED
            job.status_message = f"Hoàn thành với chi phí: {best_cost:.2f}"
            self.db.commit() 

        except Exception as e:
            print(f"!!! Service Error: Lỗi ({type(e).__name__}) khi xử lý Job {job_id}: {str(e)} !!!") 
            traceback.print_exc() 
            self.db.rollback() 
            
            job = self.db.get(SchedulingJob, job_id) 
            if job:
                job.status = JobStatus.FAILED
                error_message = str(e)
                if len(error_message) > 950:
                    error_message = error_message[:950] + "... (lỗi đầy đủ trong log)"
                job.status_message = f"Lỗi ({type(e).__name__}): {error_message}" 
                self.db.commit() 
            print(f"Service: Cập nhật Job {job_id} sang 'Failed'.")

    def _build_context(self, start_date: datetime.date, end_date: datetime.date) -> ScheduleContextData:
        doctors = self.db.scalars(select(Doctor)).all()
        clinics = self.db.scalars(select(Clinic)).all()
        shifts = self.db.scalars(select(Shift)).all()
        
        leaves_stmt = select(LeaveRequest).where(
            LeaveRequest.date.between(start_date, end_date)
        )
        leaves = self.db.scalars(leaves_stmt).all()
        
        prefs_stmt = select(SchedulePreference) 
        preferences = self.db.scalars(prefs_stmt).all()

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

    def _create_smart_initial_solution(self, context_data: ScheduleContextData) -> dict:
        """
        Tạo ra một lịch trình ban đầu "thông minh":
        1. Đảm bảo đáp ứng số bác sĩ tối thiểu (MinDocs).
        2. Đảm bảo tôn trọng Đơn xin nghỉ (Leave).
        3. Một bác sĩ không làm 2 ca/2 phòng khám CÙNG LÚC.
        """
        assignments = {} 
        all_doctor_ids = list(context_data.doctors_map.keys())
        all_clinic_ids = list(context_data.clinics_map.keys())
        all_shift_ids = list(context_data.shifts_map.keys())

        if not all_doctor_ids or not all_clinic_ids or not all_shift_ids:
            raise ValueError("Không có đủ Bác sĩ, Phòng khám hoặc Ca trực.")

        for date in context_data.date_range:
            assignments[date] = {}
            
            # 1. Tìm các bác sĩ "có sẵn" trong ngày hôm đó (không nghỉ phép)
            available_doctors_today = [
                doc_id for doc_id in all_doctor_ids 
                if not context_data.leaves_map.get((doc_id, date), False)
            ]
            
            # Nếu không có ai đi làm, báo lỗi
            if not available_doctors_today:
                print(f"Cảnh báo: Không có bác sĩ nào đi làm ngày {date} (do nghỉ phép).")
                # Vẫn tạo dict rỗng để AI xử lý
                for clinic_id in all_clinic_ids:
                    assignments[date][clinic_id] = {}
                    for shift_id in all_shift_ids:
                         assignments[date][clinic_id][shift_id] = []
                continue # Bỏ qua ngày này

            # 2. Lặp qua từng CA TRỰC
            for shift_id in all_shift_ids:
                # Bác sĩ có sẵn cho ca này (ban đầu là tất cả bác sĩ có sẵn trong ngày)
                available_doctors_for_shift = available_doctors_today.copy() 
                
                # 3. Lặp qua từng PHÒNG KHÁM (ưu tiên phòng cần nhiều người trước)
                sorted_clinics = sorted(context_data.clinics, key=lambda c: c.min_doctors_required, reverse=True)
                
                for clinic in sorted_clinics:
                    clinic_id = clinic.id
                    if clinic_id not in assignments[date]:
                        assignments[date][clinic_id] = {}
                        
                    min_required = clinic.min_doctors_required

                    # Kiểm tra xem có đủ người không
                    if len(available_doctors_for_shift) < min_required:
                        # Không đủ bác sĩ cho ca này!
                        print(f"Cảnh báo KHÔNG THỂ GIẢI: Ngày {date}, Ca {shift_id}, P.Khám {clinic_id} cần {min_required} BS, nhưng chỉ còn {len(available_doctors_for_shift)} BS có sẵn.")
                        # Gán TẤT CẢ những người còn lại
                        assigned_doctors = available_doctors_for_shift.copy()
                        available_doctors_for_shift = [] # Hết bác sĩ cho ca này
                    else:
                        # Lấy ngẫu nhiên đủ số bác sĩ
                        assigned_doctors = random.sample(available_doctors_for_shift, k=min_required)
                        # Xóa những bác sĩ đã được gán khỏi danh sách "có sẵn"
                        for doc_id in assigned_doctors:
                            available_doctors_for_shift.remove(doc_id)

                    assignments[date][clinic_id][shift_id] = assigned_doctors
        
        return assignments 

    def _save_results(self, job: SchedulingJob, state: ScheduleState, context: ScheduleContextData):
        print(f"Service: Xóa assignments cũ của Job {job.id}...")
        try:
            num_deleted = self.db.query(Assignment).filter(Assignment.job_id == job.id).delete(synchronize_session=False)
            print(f"Service: Đã xóa {num_deleted} assignments cũ (nếu có) của Job {job.id}.")
        except Exception as del_e:
             print(f"!!! Service Error: Lỗi ({type(del_e).__name__}) khi xóa assignments cũ của Job {job.id}: {str(del_e)} !!!")
             traceback.print_exc() 
             self.db.rollback() 
             raise 

        print(f"Service: Tạo assignments mới cho Job {job.id}...")
        new_assignments = []
        if not state.assignments: 
             print(f"Cảnh báo: ScheduleState trả về từ Annealer bị rỗng cho Job {job.id}.")
        else:
            for date, clinic_data in state.assignments.items():
                if not isinstance(date, datetime.date):
                    print(f"Cảnh báo: Bỏ qua key 'date' không hợp lệ: {date} (kiểu: {type(date)})")
                    continue 
                for clinic_id, shift_data in clinic_data.items():
                    for shift_id, doctor_ids in shift_data.items():
                        if not isinstance(doctor_ids, list):
                            print(f"Cảnh báo: doctor_ids không phải list cho {date}/{clinic_id}/{shift_id}: {doctor_ids}")
                            try: 
                                doctor_ids = list(doctor_ids)
                            except TypeError:
                                print(f"Lỗi: Không thể chuyển đổi doctor_ids thành list. Bỏ qua.")
                                continue 

                        for doc_id in doctor_ids:
                            if doc_id not in context.doctors_map:
                                print(f"Cảnh báo: Bỏ qua doctor_id không tồn tại: {doc_id} cho ca {date}/{clinic_id}/{shift_id}")
                                continue

                            assign = Assignment(
                                assignment_date=date, 
                                doctor_id=doc_id,
                                clinic_id=clinic_id,
                                shift_id=shift_id,
                                job_id=job.id
                            )
                            new_assignments.append(assign)
        
        if new_assignments:
            print(f"Service: Thêm {len(new_assignments)} assignments mới vào session...")
            self.db.add_all(new_assignments)
        else:
             print(f"Service: Không có assignments hợp lệ nào để thêm cho Job {job.id}.")

    def _daterange(self, start_date, end_date):
        if not isinstance(start_date, datetime.date) or not isinstance(end_date, datetime.date):
             raise TypeError("start_date và end_date phải là kiểu datetime.date") 
        if start_date > end_date:
             return 
        for n in range(int((end_date - start_date).days) + 1):
            yield start_date + datetime.timedelta(n)