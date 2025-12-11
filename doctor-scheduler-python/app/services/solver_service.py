import random
import math
import time
from simanneal import Annealer
import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Any 
from app.models import Doctor, Clinic, Shift, DoctorRole

# =================================================================
# 1. NGỮ CẢNH DỮ LIỆU
# =================================================================
class ScheduleContextData:
    def __init__(self, doctors, clinics, shifts, leaves_map, preferences_map, date_range, 
                 doctors_map, clinics_map, shifts_map):
        self.doctors = doctors
        self.clinics = clinics
        self.shifts = shifts
        self.leaves_map = leaves_map
        self.preferences_map = preferences_map
        self.date_range = date_range
        self.doctors_map = doctors_map
        self.clinics_map = clinics_map
        self.shifts_map = shifts_map
        
        # Indexing danh sách bác sĩ theo Khoa và Vai trò để truy xuất nhanh
        self.doctors_by_clinic = defaultdict(lambda: {'main': [], 'sub': []})
        for doc in doctors:
            if doc.clinic_id:
                role_key = 'main' if doc.role == DoctorRole.MAIN else 'sub'
                self.doctors_by_clinic[doc.clinic_id][role_key].append(doc.id)

# =================================================================
# 2. TRẠNG THÁI (State)
# =================================================================
class ScheduleState:
    def __init__(self, assignments):
        self.assignments = assignments

    def copy(self):
        new_assignments = {}
        for date, c_data in self.assignments.items():
            new_assignments[date] = {}
            for cid, s_data in c_data.items():
                new_assignments[date][cid] = {}
                for sid, doc_ids in s_data.items():
                    new_assignments[date][cid][sid] = list(doc_ids)
        return ScheduleState(new_assignments)

# =================================================================
# 3. HÀM MỤC TIÊU (Cost Function)
# =================================================================
class CostFunction:
    def __init__(self, context: ScheduleContextData):
        self.ctx = context
        self.W_HARD = 10000 
        self.W_SOFT = 10
        
        # Biến đếm lỗi hiển thị Console
        self.current_stats = {
            "missing_staff": 0,
            "over_48h": 0,
            "bad_rest": 0,
            "preference_bad": 0
        }

    # Xác định xem khoa này có cần ca này không
    def _is_shift_required(self, clinic_name, shift_name):
        # Khoa 24/7 -> Cần mọi ca
        if "24/7" in clinic_name: return True
        # Khoa thường -> Không cần ca Đêm
        if "Đêm" in shift_name: return False
        return True

    def calculate_cost(self, state: ScheduleState) -> float:
        total_cost = 0.0
        
        stats = {
            "missing_staff": 0,
            "over_48h": 0,
            "bad_rest": 0,
            "preference_bad": 0
        }

        doc_shift_history = defaultdict(list) 

        # --- GIAI ĐOẠN 1: QUÉT TOÀN BỘ CÁC CA ---
        for date in self.ctx.date_range:
            # Lấy dữ liệu ngày (nếu chưa có thì coi là rỗng)
            date_assignments = state.assignments.get(date, {})
            
            for clinic in self.ctx.clinics:
                clinic_id = clinic.id
                clinic_assignments = date_assignments.get(clinic_id, {})
                
                # Duyệt qua TẤT CẢ các ca có trong hệ thống
                for shift in self.ctx.shifts:
                    # 1. Kiểm tra xem ca này có cần thiết cho khoa này không?
                    if not self._is_shift_required(clinic.name, shift.name):
                        continue 

                    # 2. Lấy danh sách bác sĩ được phân công
                    doc_ids = clinic_assignments.get(shift.id, [])
                    
                    count_main = 0
                    count_sub = 0
                    shift_start_dt = datetime.datetime.combine(date, shift.start_time)
                    
                    # 3. Phân tích nhân sự trong ca
                    for doc_id in doc_ids:
                        doc = self.ctx.doctors_map.get(doc_id)
                        if not doc: continue

                        if doc.role == DoctorRole.MAIN: count_main += 1
                        else: count_sub += 1
                        
                        # Ghi nhận lịch sử làm việc
                        doc_shift_history[doc_id].append(shift_start_dt)
                        
                        # [HARD] Check Đơn nghỉ
                        if self.ctx.leaves_map.get((doc_id, date), False):
                            total_cost += self.W_HARD
                            stats["bad_rest"] += 1 

                        # [SOFT] Check Nguyện vọng
                        pref_score = self.ctx.preferences_map.get((doc_id, shift.id, date.weekday()), 0)
                        if pref_score < 0:
                            total_cost += abs(pref_score) * self.W_SOFT
                            stats["preference_bad"] += 1

                    # 4. TÍNH PHẠT ĐỊNH BIÊN
                    if count_main < clinic.required_main:
                        missing = clinic.required_main - count_main
                        total_cost += missing * self.W_HARD
                        stats["missing_staff"] += missing
                    
                    if count_sub < clinic.required_sub:
                        missing = clinic.required_sub - count_sub
                        total_cost += missing * self.W_HARD
                        stats["missing_staff"] += missing
        
        # --- GIAI ĐOẠN 2: KIỂM TRA LUẬT LAO ĐỘNG ---
        SHIFT_DURATION_HOURS = 8 
        for doc_id, shifts_list in doc_shift_history.items():
            shifts_list.sort()
            
            # [HARD] Quá 48h/tuần
            total_hours = len(shifts_list) * SHIFT_DURATION_HOURS
            if total_hours > 48:
                over = total_hours - 48
                total_cost += over * self.W_HARD 
                stats["over_48h"] += 1 
            
            # [HARD] Nghỉ ngơi & Trùng ca
            for i in range(len(shifts_list) - 1):
                current_start = shifts_list[i]
                next_start = shifts_list[i+1]
                current_end = current_start + datetime.timedelta(hours=SHIFT_DURATION_HOURS)
                
                rest_time_hours = (next_start - current_end).total_seconds() / 3600
                
                if rest_time_hours < 12:
                    total_cost += self.W_HARD
                    stats["bad_rest"] += 1
                
                if current_start.date() == next_start.date():
                     total_cost += self.W_HARD * 2
                     stats["bad_rest"] += 1

        self.current_stats = stats
        return total_cost

    def print_detailed_report(self, state: ScheduleState):
        print("\n" + "="*60)
        print("BÁO CÁO KẾT QUẢ CHI TIẾT SAU KHI CHẠY")
        print("="*60)
        # In chi tiết nếu cần
        pass 

# =================================================================
# 4. ANNEALER (Bộ giải thuật toán)
# =================================================================
class ScheduleAnnealer(Annealer):
    def __init__(self, initial_state, cost_function):
        self.cost_function = cost_function
        super(ScheduleAnnealer, self).__init__(initial_state)
        
        # --- CÁC BIẾN THEO DÕI NÂNG CAO ---
        self.prev_best_energy = float('inf') 
        self.step_of_last_best = 0           
        self.last_move_vars = 0              

    def move(self):
        """Hàm biến đổi trạng thái (Mutation)"""
        ctx = self.cost_function.ctx
        self.last_move_vars = 0 # Reset đếm
        
        # 1. Chọn ngày, khoa, ca ngẫu nhiên
        if not ctx.date_range or not ctx.clinics or not ctx.shifts: return
        date = random.choice(ctx.date_range)
        clinic_id = random.choice(list(ctx.clinics_map.keys()))
        
        existing_shifts = list(self.state.assignments[date][clinic_id].keys())
        if not existing_shifts: return
        shift_id = random.choice(existing_shifts)
        
        current_docs = self.state.assignments[date][clinic_id][shift_id]
        if not current_docs: return
        
        # 2. Chọn người để thay ra (OUT)
        doc_out_id = random.choice(current_docs)
        doc_out = ctx.doctors_map.get(doc_out_id)
        if not doc_out: return

        # 3. Chọn người thay thế (IN)
        role_key = 'main' if doc_out.role == DoctorRole.MAIN else 'sub'
        candidates = ctx.doctors_by_clinic[clinic_id][role_key]
        
        if not candidates: return
        doc_in_id = random.choice(candidates)
        
        if doc_in_id in current_docs: return

        # Hoán đổi
        current_docs.remove(doc_out_id)
        current_docs.append(doc_in_id)
        
        self.last_move_vars = 1 

    def energy(self):
        return self.cost_function.calculate_cost(self.state)
    
    def update(self, step, T, E, acceptance, improvement):
        elapsed = time.time() - self.start
        
        # --- [FIX LỖI] KIỂM TRA NONE ---
        if acceptance is None: acceptance = 0.0
        if improvement is None: improvement = 0.0
        
        # Tính toán chỉ số Dashboard
        accept_rate_pct = acceptance * 100
        good_rate_pct = improvement * 100
        bad_rate_pct = (acceptance - improvement) * 100
        
        current_best = self.best_energy
        if current_best < self.prev_best_energy:
            self.prev_best_energy = current_best
            self.step_of_last_best = step
            
        steps_since_imp = step - self.step_of_last_best
        avg_time_ms = (elapsed / step) * 1000 if step > 0 else 0
        stats = self.cost_function.current_stats
        
        # HIỂN THỊ LOG FORMAT ĐẸP
        print("-" * 100)
        print(f"📊 BƯỚC: {step:6d} / {self.steps}  |  Nhiệt độ (T): {T:10.2f}  |  Thời gian: {elapsed:.1f}s")
        print(f"   ➤ Cost Hiện tại: {E:10.0f}  |  🏆 Best Cost: {current_best:10.0f} (Cập nhật cách đây {steps_since_imp} bước)")
        
        print(f"   ➤ Trạng thái bước đi:")
        print(f"     • Thay đổi: {self.last_move_vars} vị trí (ca trực)")
        print(f"     • Tỷ lệ Chấp nhận: {accept_rate_pct:5.1f}%  (✅ Tốt: {good_rate_pct:4.1f}% | ⚠️ Rủi ro: {bad_rate_pct:4.1f}%)")
        print(f"     • Tốc độ xử lý:    {avg_time_ms:5.2f} ms/bước")
        
        print(f"   ➤ Phân tích Lỗi (Ràng buộc):")
        print(f"     [CỨNG] Thiếu người: {stats['missing_staff']:3d}  |  Quá 48h: {stats['over_48h']:3d}  |  Nghỉ ít/Trùng: {stats['bad_rest']:3d}")
        print(f"     [MỀM ] Nguyện vọng: {stats['preference_bad']:3d}")
        print("-" * 100)