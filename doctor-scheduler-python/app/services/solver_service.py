import random
import math
from simanneal import Annealer
import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Any 
from app.models import Doctor, Clinic, Shift, LeaveRequest, SchedulePreference

# =================================================================
# LỚP DÙNG ĐỂ CHỨA DỮ LIỆU NGỮ CẢNH (QUAN TRỌNG)
# =================================================================
class ScheduleContextData:
    """
    Lưu trữ tất cả dữ liệu đầu vào cần thiết cho thuật toán,
    đã được xử lý thành dạng map để truy cập nhanh.
    """
    def __init__(self, 
                 doctors: List[Doctor], 
                 clinics: List[Clinic], 
                 shifts: List[Shift], 
                 leaves_map: Dict[Tuple[int, datetime.date], bool], 
                 preferences_map: Dict[Tuple[int, int, int], int], 
                 date_range: List[datetime.date],
                 doctors_map: Dict[int, Doctor], 
                 clinics_map: Dict[int, Clinic], 
                 shifts_map: Dict[int, Shift]     
                 ):
        self.doctors: List[Doctor] = doctors
        self.clinics: List[Clinic] = clinics
        self.shifts: List[Shift] = shifts
        self.leaves_map: Dict[Tuple[int, datetime.date], bool] = leaves_map
        self.preferences_map: Dict[Tuple[int, int, int], int] = preferences_map
        self.date_range: List[datetime.date] = date_range
        self.doctors_map: Dict[int, Doctor] = doctors_map
        self.clinics_map: Dict[int, Clinic] = clinics_map
        self.shifts_map: Dict[int, Shift] = shifts_map

# =================================================================
# LỚP ĐẠI DIỆN CHO MỘT GIẢI PHÁP (LỊCH TRÌNH HOÀN CHỈNH)
# =================================================================
class ScheduleState:
    """
    Đại diện cho một trạng thái (một lịch trình hoàn chỉnh).
    assignments là một dict lồng nhau: date -> clinic_id -> shift_id -> [doctor_ids]
    """
    def __init__(self, assignments: Dict[datetime.date, Dict[int, Dict[int, List[int]]]]):
        self.assignments: Dict[datetime.date, Dict[int, Dict[int, List[int]]]] = assignments

    def copy(self):
        """Tạo một bản sao sâu (deep copy) của trạng thái."""
        new_assignments = {}
        for date, clinic_data in self.assignments.items():
            new_assignments[date] = {}
            for clinic_id, shift_data in clinic_data.items():
                new_assignments[date][clinic_id] = {}
                for shift_id, doctor_ids in shift_data.items():
                    new_assignments[date][clinic_id][shift_id] = doctor_ids[:] 
        return ScheduleState(new_assignments)
# =================================================================
# LỚP TÍNH CHI PHÍ (HÀM NĂNG LƯỢNG)
# =================================================================
class CostFunction:
    """
    Tính toán chi phí (độ "xấu") của một lịch trình (ScheduleState).
    Chi phí càng thấp, lịch trình càng tốt.
    """
    def __init__(self, context: ScheduleContextData):
        self.context: ScheduleContextData = context
        # Trọng số cho các loại vi phạm (có thể điều chỉnh)
        self.HARD_CONSTRAINT_PENALTY = 10000  
        self.PREFERENCE_WEIGHT = 1           # Điểm cho nguyện vọng (mềm)
        # TODO: Thêm các trọng số khác (ví dụ: cân bằng ca, nghỉ cuối tuần...)

    def calculate_cost(self, state: ScheduleState) -> float:
        """Tính tổng chi phí của lịch trình."""
        total_cost = 0.0

        # 1. Kiểm tra Ràng buộc CỨNG (Hard Constraints)
        total_cost += self._check_leave_requests(state) * self.HARD_CONSTRAINT_PENALTY
        total_cost += self._check_min_doctors(state) * self.HARD_CONSTRAINT_PENALTY
        # TODO: Thêm các kiểm tra ràng buộc cứng khác (ví dụ: không làm 2 ca cùng lúc)
        
        # 2. Tính điểm Ràng buộc MỀM (Soft Constraints)
        total_cost -= self._calculate_preference_score(state) * self.PREFERENCE_WEIGHT
        # TODO: Thêm các tính điểm ràng buộc mềm khác (ví dụ: cân bằng số ca...)

        return total_cost

    def _check_leave_requests(self, state: ScheduleState) -> int:
        """Đếm số lần bác sĩ bị xếp lịch vào ngày nghỉ."""
        violations = 0
        for date, clinic_data in state.assignments.items():
            for clinic_id, shift_data in clinic_data.items():
                for shift_id, doctor_ids in shift_data.items():
                    for doc_id in doctor_ids:
                        if self.context.leaves_map.get((doc_id, date), False):
                            violations += 1
        return violations

    def _check_min_doctors(self, state: ScheduleState) -> int:
        """Đếm số lần một ca bị thiếu bác sĩ so với yêu cầu tối thiểu."""
        violations = 0
        for date, clinic_data in state.assignments.items():
            for clinic_id, shift_data in clinic_data.items():
                clinic = self.context.clinics_map.get(clinic_id)
                if not clinic: continue 
                
                min_required = clinic.min_doctors_required
                
                for shift_id, doctor_ids in shift_data.items():
                    if len(doctor_ids) < min_required:
                        violations += (min_required - len(doctor_ids)) 
        return violations

    def _calculate_preference_score(self, state: ScheduleState) -> int:
        """Tính tổng điểm nguyện vọng của lịch trình."""
        total_score = 0
        for date, clinic_data in state.assignments.items():
            day_of_week = date.weekday() # 0 = Monday, 6 = Sunday
            for clinic_id, shift_data in clinic_data.items():
                for shift_id, doctor_ids in shift_data.items():
                    for doc_id in doctor_ids:
                        # Lấy điểm nguyện vọng từ map, mặc định là 0 nếu không có
                        score = self.context.preferences_map.get((doc_id, shift_id, day_of_week), 0)
                        total_score += score
        return total_score

# =================================================================
# LỚP THUẬT TOÁN LUYỆN KIM MÔ PHỎNG (SIMULATED ANNEALING)
# =================================================================
class ScheduleAnnealer(Annealer):
    """
    Triển khai thuật toán Simulated Annealing để tối ưu lịch trình.
    """
    def __init__(self, initial_state: ScheduleState, cost_function: CostFunction):
        self.cost_function = cost_function
        # Gọi __init__ của lớp cha (Annealer) với trạng thái ban đầu
        super(ScheduleAnnealer, self).__init__(initial_state) 

    def move(self):
        """
        Tạo ra một lịch trình "hàng xóm" bằng cách thay đổi nhỏ lịch trình hiện tại.
        """
        # Chọn ngẫu nhiên một loại thay đổi
        # Kiểm tra xem có đủ bác sĩ để swap không
        can_swap = len(self.cost_function.context.doctors) >= 2
        move_type = random.choice(['move_doctor', 'swap_doctors'] if can_swap else ['move_doctor']) 
        if move_type == 'swap_doctors':
            self._swap_doctors_random_shift()
        elif move_type == 'move_doctor':
             self._move_doctor_random_shift()

    def _swap_doctors_random_shift(self):
        """
        Chọn ngẫu nhiên 2 bác sĩ TRONG CÙNG MỘT CA và hoán đổi vị trí của họ.
        """
        possible_slots = []
        for date, clinic_data in self.state.assignments.items():
            for clinic_id, shift_data in clinic_data.items():
                for shift_id, doctor_ids in shift_data.items():
                    if len(doctor_ids) >= 2:
                        possible_slots.append((date, clinic_id, shift_id))
        
        if not possible_slots:
            return 

        date, clinic_id, shift_id = random.choice(possible_slots)
        doctors_in_shift = self.state.assignments[date][clinic_id][shift_id]
        
        idx1, idx2 = random.sample(range(len(doctors_in_shift)), 2)
        doctors_in_shift[idx1], doctors_in_shift[idx2] = doctors_in_shift[idx2], doctors_in_shift[idx1]


    def _move_doctor_random_shift(self):
        """
        Chọn ngẫu nhiên 1 bác sĩ và di chuyển họ sang một ca NGẪU NHIÊN khác.
        """
        source_slots = []
        for date, clinic_data in self.state.assignments.items():
            for clinic_id, shift_data in clinic_data.items():
                for shift_id, doctor_ids in shift_data.items():
                    if doctor_ids: 
                        source_slots.append((date, clinic_id, shift_id))
        
        if not source_slots:
            return 

        s_date, s_clinic, s_shift = random.choice(source_slots)
        doctors_in_source = self.state.assignments[s_date][s_clinic][s_shift]
        
        doc_to_move = random.choice(doctors_in_source)

       
        all_dates = self.cost_function.context.date_range
        all_clinics = list(self.cost_function.context.clinics_map.keys())
        all_shifts = list(self.cost_function.context.shifts_map.keys())
        
        d_date = random.choice(all_dates)
        d_clinic = random.choice(all_clinics)
        d_shift = random.choice(all_shifts)

        doctors_in_source.remove(doc_to_move)
        
        doctors_in_dest = self.state.assignments[d_date][d_clinic][d_shift]
        if doc_to_move not in doctors_in_dest:
            doctors_in_dest.append(doc_to_move)
        
    def energy(self) -> float:
        """
        Tính toán năng lượng (chi phí) của trạng thái hiện tại.
        """
        cost = self.cost_function.calculate_cost(self.state)
        return cost