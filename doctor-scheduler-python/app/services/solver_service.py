import random
import math
import time
from simanneal import Annealer
import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Any 
from app.models import Doctor, Clinic, Shift, DoctorRole

# =================================================================
# 1. NGỮ CẢNH DỮ LIỆU (Context)
# =================================================================
class ScheduleContextData:
    """
    Chứa toàn bộ dữ liệu readonly cần thiết cho thuật toán.
    Được tối ưu hóa (indexing) để truy xuất nhanh.
    """
    def __init__(self, doctors, clinics, shifts, leaves_map, preferences_map, date_range, 
                 doctors_map, clinics_map, shifts_map):
        self.doctors = doctors
        self.clinics = clinics
        self.shifts = shifts
        self.leaves_map = leaves_map
        self.preferences_map = preferences_map
        self.date_range = date_range
        
        # Maps cơ bản
        self.doctors_map = doctors_map
        self.clinics_map = clinics_map
        self.shifts_map = shifts_map

        # --- TỐI ƯU: Phân nhóm bác sĩ theo Khoa và Vai trò ---
        # Cấu trúc: doctors_by_clinic[clinic_id]['main'] = [list of doctor_ids]
        self.doctors_by_clinic = defaultdict(lambda: {'main': [], 'sub': []})
        
        for doc in doctors:
            if doc.clinic_id: # Chỉ quan tâm bác sĩ có biên chế
                role_key = 'main' if doc.role == DoctorRole.MAIN else 'sub'
                self.doctors_by_clinic[doc.clinic_id][role_key].append(doc.id)

# =================================================================
# 2. TRẠNG THÁI (State)
# =================================================================
class ScheduleState:
    """
    Đại diện cho một phương án xếp lịch.
    """
    def __init__(self, assignments):
        # Cấu trúc assignments: date -> clinic_id -> shift_id -> [doctor_ids]
        self.assignments = assignments

    def copy(self):
        # Deep copy thủ công để tối ưu tốc độ hơn deepcopy mặc định
        new_assignments = {}
        for date, c_data in self.assignments.items():
            new_assignments[date] = {}
            for cid, s_data in c_data.items():
                new_assignments[date][cid] = {}
                for sid, doc_ids in s_data.items():
                    new_assignments[date][cid][sid] = list(doc_ids)
        return ScheduleState(new_assignments)

# =================================================================
# 3. HÀM MỤC TIÊU (Cost Function) - Logic Cốt Lõi
# =================================================================
class CostFunction:
    def __init__(self, context: ScheduleContextData):
        self.ctx = context
        # Trọng số phạt (Penalty Weights)
        self.W_HARD = 10000 # Vi phạm luật (48h, nghỉ 12h, role) -> Phạt cực nặng
        self.W_SOFT = 10    # Nguyện vọng -> Phạt nhẹ

    def calculate_cost(self, state: ScheduleState) -> float:
        total_cost = 0.0
        
        # Dữ liệu tạm để tính toán luật lao động
        # doc_shift_history: doc_id -> danh sách các thời điểm bắt đầu ca trực (datetime)
        doc_shift_history = defaultdict(list) 

        # --- DUYỆT QUA TOÀN BỘ LỊCH ĐỂ TÍNH PHẠT CẤU TRÚC CA ---
        for date, c_data in state.assignments.items():
            for clinic_id, s_data in c_data.items():
                # Lấy thông tin yêu cầu của khoa
                clinic = self.ctx.clinics_map.get(clinic_id)
                if not clinic: continue

                for shift_id, doc_ids in s_data.items():
                    shift = self.ctx.shifts_map.get(shift_id)
                    if not shift: continue

                    # Đếm số lượng Chính/Phụ thực tế trong ca
                    count_main = 0
                    count_sub = 0
                    
                    # Thời điểm bắt đầu ca (để tính nghỉ ngơi)
                    shift_start_dt = datetime.datetime.combine(date, shift.start_time)
                    
                    for doc_id in doc_ids:
                        doc = self.ctx.doctors_map.get(doc_id)
                        if not doc: continue

                        if doc.role == DoctorRole.MAIN: 
                            count_main += 1
                        else: 
                            count_sub += 1
                        
                        # Lưu lịch sử trực của bác sĩ
                        doc_shift_history[doc_id].append(shift_start_dt)
                        
                        # Check đơn nghỉ (Leave Request)
                        if self.ctx.leaves_map.get((doc_id, date), False):
                            total_cost += self.W_HARD # Phạt nếu đi làm ngày xin nghỉ

                        # --- Check Nguyện vọng (SOFT) ---
                        pref_score = self.ctx.preferences_map.get((doc_id, shift_id, date.weekday()), 0)
                        if pref_score < 0:
                            # Nếu phải làm vào ngày ghét (score âm) -> Phạt
                            total_cost += abs(pref_score) * self.W_SOFT

                    # 1. KIỂM TRA ĐỊNH BIÊN (Thiếu người là phạt)
                    if count_main < clinic.required_main:
                        total_cost += (clinic.required_main - count_main) * self.W_HARD
                    if count_sub < clinic.required_sub:
                        total_cost += (clinic.required_sub - count_sub) * self.W_HARD
        
        # --- KIỂM TRA LUẬT LAO ĐỘNG (Theo từng Bác sĩ) ---
        SHIFT_DURATION_HOURS = 8 # Giả định mỗi ca 8 tiếng
        
        for doc_id, shifts_list in doc_shift_history.items():
            # Sắp xếp lịch sử trực theo thời gian tăng dần
            shifts_list.sort()
            
            # 2. KHÔNG QUÁ 48H / TUẦN (Trong phạm vi job này)
            total_hours = len(shifts_list) * SHIFT_DURATION_HOURS
            if total_hours > 48:
                # Phạt dựa trên số giờ vượt
                total_cost += (total_hours - 48) * self.W_HARD
            
            # 3. KIỂM TRA NGHỈ NGƠI & 1 CA/NGÀY
            # Kiểm tra khoảng cách giữa các ca
            for i in range(len(shifts_list) - 1):
                current_start = shifts_list[i]
                next_start = shifts_list[i+1]
                
                # Ca hiện tại kết thúc lúc: Start + 8h
                current_end = current_start + datetime.timedelta(hours=SHIFT_DURATION_HOURS)
                
                # Thời gian nghỉ (giờ)
                rest_time_hours = (next_start - current_end).total_seconds() / 3600
                
                # Luật: Tối thiểu 12h nghỉ
                if rest_time_hours < 12:
                    total_cost += self.W_HARD # Phạt nặng vi phạm nghỉ ngơi
                
                # Luật: Không quá 1 ca/ngày (check ngày)
                if current_start.date() == next_start.date():
                     total_cost += self.W_HARD * 2 # Phạt rất nặng nếu làm 2 ca cùng ngày

        return total_cost

    def print_detailed_report(self, state: ScheduleState):
        """
        Hàm này chỉ gọi 1 lần khi kết thúc để báo cáo chi tiết các lỗi.
        """
        print("\n" + "="*60)
        print("BÁO CÁO CHI TIẾT ĐIỂM PHẠT (COST BREAKDOWN)")
        print("="*60)
        
        total_cost = 0.0
        details = []
        doc_shift_history = defaultdict(list)

        # 1. KIỂM TRA ĐỊNH BIÊN (HARD) VÀ NGUYỆN VỌNG (SOFT)
        for date, c_data in state.assignments.items():
            for clinic_id, s_data in c_data.items():
                clinic = self.ctx.clinics_map.get(clinic_id)
                for shift_id, doc_ids in s_data.items():
                    # Check định biên
                    count_main = sum(1 for d in doc_ids if self.ctx.doctors_map[d].role == DoctorRole.MAIN)
                    count_sub = len(doc_ids) - count_main
                    
                    if count_main < clinic.required_main:
                        missing = clinic.required_main - count_main
                        penalty = missing * self.W_HARD
                        details.append(f"[HARD] Ngày {date} - {clinic.name}: Thiếu {missing} BS Chính -> +{penalty}")
                        total_cost += penalty
                    
                    if count_sub < clinic.required_sub:
                        missing = clinic.required_sub - count_sub
                        penalty = missing * self.W_HARD
                        details.append(f"[HARD] Ngày {date} - {clinic.name}: Thiếu {missing} BS Phụ -> +{penalty}")
                        total_cost += penalty

                    # Check bác sĩ
                    shift = self.ctx.shifts_map[shift_id]
                    shift_start = datetime.datetime.combine(date, shift.start_time)
                    
                    for doc_id in doc_ids:
                        doc = self.ctx.doctors_map[doc_id]
                        doc_shift_history[doc_id].append(shift_start)
                        
                        # Check nghỉ phép
                        if self.ctx.leaves_map.get((doc_id, date), False):
                            penalty = self.W_HARD
                            details.append(f"[HARD] BS {doc.name}: Đi làm ngày xin nghỉ ({date}) -> +{penalty}")
                            total_cost += penalty
                        
                        # Check nguyện vọng
                        pref_score = self.ctx.preferences_map.get((doc_id, shift_id, date.weekday()), 0)
                        if pref_score < 0:
                            penalty = abs(pref_score) * self.W_SOFT
                            details.append(f"[SOFT] BS {doc.name}: Phải trực ca ghét (Score {pref_score}) -> +{penalty}")
                            total_cost += penalty

        # 2. KIỂM TRA LUẬT LAO ĐỘNG (HARD)
        SHIFT_DURATION = 8
        for doc_id, shifts in doc_shift_history.items():
            shifts.sort()
            doc_name = self.ctx.doctors_map[doc_id].name
            
            # Check 48h/tuần
            hours = len(shifts) * SHIFT_DURATION
            if hours > 48:
                penalty = (hours - 48) * self.W_HARD
                details.append(f"[HARD] BS {doc_name}: Làm quá {hours}h -> +{penalty}")
                total_cost += penalty

            # Check nghỉ ngơi 12h
            for i in range(len(shifts) - 1):
                curr = shifts[i]
                next_s = shifts[i+1]
                rest = (next_s - (curr + datetime.timedelta(hours=8))).total_seconds() / 3600
                if rest < 12:
                    penalty = self.W_HARD
                    details.append(f"[HARD] BS {doc_name}: Nghỉ ít ({rest:.1f}h) giữa 2 ca -> +{penalty}")
                    total_cost += penalty

        # IN RA MÀN HÌNH
        if not details:
            print(">> TUYỆT VỜI! KHÔNG CÓ LỖI NÀO (Cost = 0).")
        else:
            for line in details:
                print(line)
            print("-" * 60)
            print(f"TỔNG CỘNG COST TÍNH ĐƯỢC: {total_cost}")
        print("="*60 + "\n")

# =================================================================
# 4. ANNEALER (Bộ giải thuật toán)
# =================================================================
class ScheduleAnnealer(Annealer):
    def __init__(self, initial_state, cost_function):
        self.cost_function = cost_function
        super(ScheduleAnnealer, self).__init__(initial_state)

    def move(self):
        """
        Hàm biến đổi trạng thái (Mutation).
        Chiến lược: Chỉ thay đổi bác sĩ trong cùng 1 Khoa và cùng Vai trò 
        để giữ cấu trúc định biên (Initial Solution đã đúng định biên rồi).
        """
        ctx = self.cost_function.ctx
        
        # 1. Chọn ngẫu nhiên 1 slot (Ngày, Khoa, Ca)
        if not ctx.date_range or not ctx.clinics or not ctx.shifts: return
        
        date = random.choice(ctx.date_range)
        clinic_id = random.choice(list(ctx.clinics_map.keys()))
        shift_id = random.choice(list(ctx.shifts_map.keys()))
        
        current_docs = self.state.assignments[date][clinic_id][shift_id]
        if not current_docs: return
        
        # 2. Chọn 1 bác sĩ đang trực để thay ra (OUT)
        doc_out_id = random.choice(current_docs)
        doc_out = ctx.doctors_map.get(doc_out_id)
        if not doc_out: return

        # 3. Tìm người thay thế (IN) hợp lệ:
        # - Phải CÙNG KHOA (clinic_id)
        # - Phải CÙNG VAI TRÒ (Main đổi Main, Sub đổi Sub)
        role_key = 'main' if doc_out.role == DoctorRole.MAIN else 'sub'
        candidates = ctx.doctors_by_clinic[clinic_id][role_key]
        
        if not candidates: return
        
        doc_in_id = random.choice(candidates)
        
        # Nếu người vào đã có trong ca này rồi thì bỏ qua (tránh trùng lặp)
        if doc_in_id in current_docs:
            return

        # Thực hiện hoán đổi
        current_docs.remove(doc_out_id)
        current_docs.append(doc_in_id)

    def energy(self):
        return self.cost_function.calculate_cost(self.state)
    
    def update(self, step, T, E, acceptance, improvement):
        """
        Hàm này được gọi tự động sau mỗi (steps / updates) vòng lặp.
        """
        elapsed = time.time() - self.start
        print(f"--> [AI Running] Vòng: {step:6d}/{self.steps} | Cost: {E:10.2f} | Nhiệt độ: {T:8.4f} | Giây: {elapsed:.2f}s")