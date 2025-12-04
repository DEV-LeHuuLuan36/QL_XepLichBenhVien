from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)
from sqlalchemy import select
from app import db # Import đối tượng db từ app/__init__.py
import datetime
from sqlalchemy.orm import joinedload
from sqlalchemy import select, func
from app import create_app
import multiprocessing
from collections import defaultdict
import calendar
# Import TẤT CẢ các model 
from app.models import (
    Doctor, Clinic, Shift, LeaveRequest, SchedulePreference, SchedulingJob,
    Assignment 
)
# Import JobStatus từ file của nó
from app.models.scheduling_job import JobStatus 

from app.models.base import Base

# IMPORT BỘ NÃO AI
from app.services.scheduling_service import SchedulingService

# --- triển khai: Tạo một Blueprint ---
main_bp = Blueprint('main', __name__)

# --- triển khai: Route cho Trang chủ ---
@main_bp.route('/')
def index():
    """
    Route (URL) cho trang chủ.
    Hiển thị thông tin tổng quan.
    """
    try:    
        # Đếm số lượng
        doctor_count = db.session.scalar(select(func.count(Doctor.id)))
        clinic_count = db.session.scalar(select(func.count(Clinic.id)))
        shift_count = db.session.scalar(select(func.count(Shift.id)))
        
        # Lấy 5 bác sĩ mới nhất
        recent_doctors_stmt = (
            select(Doctor)
            .order_by(Doctor.id.desc())
            .limit(5)
        )
        recent_doctors = db.session.scalars(recent_doctors_stmt).all()
        
    except Exception as e:
        # Nếu có lỗi CSDL, hiển thị giá trị mặc định
        print(f"Lỗi khi tải dữ liệu trang chủ: {e}")
        doctor_count = clinic_count = shift_count = 0
        recent_doctors = []
        flash("Không thể tải dữ liệu tổng quan từ CSDL.", "warning")

    # Trả về file 'index.html' với dữ liệu đã lấy
    return render_template(
        "index.html", 
        title="Trang chủ",
        doctor_count=doctor_count,
        clinic_count=clinic_count,
        shift_count=shift_count,
        recent_doctors=recent_doctors
        )
# =================================================================
# QUẢN LÝ BÁC SĨ (Doctors)
# =================================================================
@main_bp.route('/doctors', methods=['GET', 'POST'])
def manage_doctors():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            specialty = request.form.get('specialty')
            if not name or not specialty:
                flash("Tên và chuyên khoa là bắt buộc.", "danger")
            else:
                new_doctor = Doctor(
                    name=name,
                    specialty=specialty,
                    total_shifts_worked=0
                )
                db.session.add(new_doctor)
                db.session.commit()
                flash(f"Đã thêm bác sĩ '{name}' thành công!", "success")
            return redirect(url_for('main.manage_doctors'))
        except Exception as e:
            db.session.rollback()
            flash(f"Có lỗi xảy ra: {e}", "danger")

    stmt = select(Doctor).order_by(Doctor.id)
    doctors_list = db.session.scalars(stmt).all()
    return render_template(
        "doctors.html",
        doctors=doctors_list,
        title="Quản lý Bác sĩ"
    )

# =================================================================
# QUẢN LÝ PHÒNG KHÁM (Clinics)
# =================================================================
@main_bp.route('/clinics', methods=['GET', 'POST'])
def manage_clinics():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            min_doctors_str = request.form.get('min_doctors_required', '1') 
            
            if not name:
                flash("Tên phòng khám là bắt buộc.", "danger")
            else:
                try:
                    min_doctors = int(min_doctors_str)
                    if min_doctors < 0:
                         flash("Số bác sĩ tối thiểu phải là số dương.", "danger")
                         raise ValueError("Negative min doctors") 
                    
                    new_clinic = Clinic(name=name, min_doctors_required=min_doctors) 
                    db.session.add(new_clinic)
                    db.session.commit()
                    flash(f"Đã thêm phòng khám '{name}' thành công!", "success")
                    
                except ValueError:
                     flash("Số bác sĩ tối thiểu phải là một số nguyên dương.", "danger")

            return redirect(url_for('main.manage_clinics'))
        except Exception as e:
            db.session.rollback()
            flash(f"Có lỗi xảy ra khi thêm phòng khám: {e}", "danger")

    stmt = select(Clinic).order_by(Clinic.id)
    clinics_list = db.session.scalars(stmt).all()
    return render_template(
        "clinics.html",
        clinics=clinics_list,
        title="Quản lý Phòng khám"
    )

# =================================================================
# QUẢN LÝ CA TRỰC (Shifts)
# =================================================================
@main_bp.route('/shifts', methods=['GET', 'POST'])
def manage_shifts():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            start_time_str = request.form.get('start_time')
            end_time_str = request.form.get('end_time')

            if not name or not start_time_str or not end_time_str:
                flash("Vui lòng điền đầy đủ thông tin.", "danger")
            else:
                try:
                    start_time = datetime.datetime.strptime(start_time_str, '%H:%M').time()
                    end_time = datetime.datetime.strptime(end_time_str, '%H:%M').time()
                except ValueError:
                    flash("Định dạng giờ không hợp lệ. Vui lòng nhập HH:MM.", "danger")
                    return redirect(url_for('main.manage_shifts'))

                new_shift = Shift(
                    name=name,
                    start_time=start_time,
                    end_time=end_time
                )
                db.session.add(new_shift)
                db.session.commit()
                flash(f"Đã thêm ca trực '{name}' thành công!", "success")
            return redirect(url_for('main.manage_shifts'))
        except Exception as e:
            db.session.rollback()
            flash(f"Có lỗi xảy ra khi thêm ca trực: {e}", "danger")

    stmt = select(Shift).order_by(Shift.start_time)
    shifts_list = db.session.scalars(stmt).all()
    return render_template(
        "shifts.html",
        shifts=shifts_list,
        title="Quản lý Ca trực"
    )

# =================================================================
# QUẢN LÝ ĐƠN XIN NGHỈ (Leave Requests)
# =================================================================
@main_bp.route('/leave_requests', methods=['GET', 'POST'])
def manage_leave_requests():
    if request.method == 'POST':
        try:
            doctor_id = request.form.get('doctor_id')
            leave_date_str = request.form.get('leave_date')
            reason = request.form.get('reason', '') 

            if not doctor_id or not leave_date_str:
                flash("Vui lòng chọn bác sĩ và ngày nghỉ.", "danger")
            else:
                try:
                    leave_date = datetime.datetime.strptime(leave_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash("Định dạng ngày không hợp lệ.", "danger")
                    return redirect(url_for('main.manage_leave_requests'))
                
                new_leave = LeaveRequest(
                    doctor_id=int(doctor_id),
                    date=leave_date, 
                    reason=reason,
                    status="Approved" 
                )
                db.session.add(new_leave)
                db.session.commit()
                flash(f"Đã thêm đơn nghỉ thành công!", "success")
            return redirect(url_for('main.manage_leave_requests'))
        except Exception as e:
            db.session.rollback()
            flash(f"Có lỗi xảy ra khi thêm đơn nghỉ: {e}", "danger")

    stmt_leaves = (
        select(LeaveRequest)
        .options(joinedload(LeaveRequest.doctor))
        .order_by(LeaveRequest.date.desc()) 
    )
    leaves_list = db.session.scalars(stmt_leaves).all()
    
    stmt_doctors = select(Doctor).order_by(Doctor.name)
    doctors_list = db.session.scalars(stmt_doctors).all()
    
    return render_template(
        "leave_requests.html",
        leaves=leaves_list,
        doctors=doctors_list,
        title="Quản lý Đơn xin nghỉ"
    )

# =================================================================
# QUẢN LÝ NGUYỆN VỌNG (Preferences)
# =================================================================
@main_bp.route('/preferences', methods=['GET', 'POST'])
def manage_preferences():
    if request.method == 'POST':
        try:
            doctor_id = request.form.get('doctor_id')
            shift_id = request.form.get('shift_id')
            day_of_week = request.form.get('day_of_week')
            preference_score = request.form.get('preference_score')

            if not doctor_id or not shift_id or not day_of_week or not preference_score:
                flash("Vui lòng điền đầy đủ thông tin.", "danger")
            else:
                try:
                    score = int(preference_score)
                    day = int(day_of_week)
                except ValueError:
                     flash("Điểm nguyện vọng và ngày trong tuần phải là số nguyên.", "danger")
                     return redirect(url_for('main.manage_preferences'))

                new_pref = SchedulePreference(
                    doctor_id=int(doctor_id),
                    shift_id=int(shift_id),
                    day_of_week=day, 
                    preference_score=score 
                )
                db.session.add(new_pref)
                db.session.commit()
                flash("Đã thêm nguyện vọng thành công!", "success")
            return redirect(url_for('main.manage_preferences'))
        except Exception as e:
            db.session.rollback()
            flash(f"Có lỗi xảy ra khi thêm nguyện vọng: {e}", "danger")

    stmt_prefs = (
        select(SchedulePreference)
        .options(joinedload(SchedulePreference.doctor), joinedload(SchedulePreference.shift))
        .order_by(SchedulePreference.id.desc())
    )
    preferences_list = db.session.scalars(stmt_prefs).all()
    
    doctors_list = db.session.scalars(select(Doctor).order_by(Doctor.name)).all()
    shifts_list = db.session.scalars(select(Shift).order_by(Shift.name)).all()
    
    return render_template(
        "preferences.html",
        preferences=preferences_list,
        doctors=doctors_list,
        shifts=shifts_list,
        title="Quản lý Nguyện vọng"
    )

# =================================================================
# TRANG BẢNG ĐIỀU KHIỂN XẾP LỊCH (SCHEDULING DASHBOARD)
# =================================================================

@main_bp.route('/scheduling', methods=['GET'])
def schedule_dashboard():
    stmt = (
        select(SchedulingJob)
        .order_by(SchedulingJob.created_at.desc())
    )
    jobs_list = db.session.scalars(stmt).all()
    
    return render_template('schedule_dashboard.html', jobs=jobs_list)


@main_bp.route('/scheduling/create', methods=['POST'])
def create_scheduling_job():
    try:
        job_name = request.form.get('job_name')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')

        if not job_name or not start_date_str or not end_date_str:
            flash('Vui lòng điền đầy đủ thông tin.', 'danger')
            return redirect(url_for('main.schedule_dashboard'))

        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            if start_date > end_date:
                flash('Ngày bắt đầu không được sau ngày kết thúc.', 'danger')
                return redirect(url_for('main.schedule_dashboard'))
        except ValueError:
            flash("Định dạng ngày không hợp lệ.", "danger")
            return redirect(url_for('main.schedule_dashboard'))

        new_job = SchedulingJob(
            name=job_name,
            start_date=start_date,
            end_date=end_date
        )
        
        db.session.add(new_job)
        db.session.commit()
        
        flash(f'Tạo tác vụ "{job_name}" thành công!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi tạo tác vụ: {str(e)}', 'danger')
        
    return redirect(url_for('main.schedule_dashboard'))

def run_ai_in_background_process(app_config, job_id_to_run):
    """Hàm này sẽ được chạy trong một tiến trình riêng biệt."""
    # Tạo app mới và context MỚI bên trong tiến trình 
    # Dùng config được truyền vào
    temp_app = create_app() # create_app đã đọc .env và config 
    
    with temp_app.app_context(): # Kích hoạt app context mới
        print(f"--- [Process] Bắt đầu xử lý AI cho Job ID: {job_id_to_run} ---")
        
        # Lấy db session từ context mới 
        local_session = db.session() 
        
        try:
            # Khởi tạo service VỚI SESSION MỚI
            scheduler_service = SchedulingService(local_session) 
            
            # Gọi hàm chạy AI
            scheduler_service.run_scheduling_job(job_id_to_run) 
            
            print(f"--- [Process] Xử lý AI hoàn tất cho Job ID: {job_id_to_run} ---")

        except Exception as proc_e:
            print(f"!!! [Process] Lỗi nghiêm trọng khi chạy AI cho Job {job_id_to_run}: {proc_e} !!!")
            # Cập nhật trạng thái Job thành FAILED trong CSDL
            try:
                job = local_session.get(SchedulingJob, job_id_to_run)
                if job and job.status != JobStatus.FAILED: 
                    job.status = JobStatus.FAILED
                    error_msg = f"Lỗi tiến trình nền: {str(proc_e)}"
                    job.status_message = error_msg[:1000] 
                    local_session.commit()
            except Exception as update_e:
                 print(f"!!! [Process] Lỗi khi cập nhật trạng thái Failed cho Job {job_id_to_run}: {update_e} !!!")
                 local_session.rollback()
        finally:
            # Đóng session của tiến trình 
            db.session.remove() 
            print(f"--- [Process] Đã đóng session cho Job ID: {job_id_to_run} ---")


@main_bp.route('/scheduling/run/<int:job_id>', methods=['POST'])
def run_scheduling_job(job_id):
    """
    Khởi động TIẾN TRÌNH NỀN (Process) để chạy AI.
    (PHIÊN BẢN SỬA LỖI SIGNAL BẰNG MULTIPROCESSING)
    """
    job = db.session.get(SchedulingJob, job_id)
    if not job:
        flash('Không tìm thấy tác vụ!', 'danger')
        return redirect(url_for('main.schedule_dashboard'))

    if job.status != JobStatus.PENDING:
         flash(f'Tác vụ "{job.name}" không ở trạng thái "Chờ xử lý".', 'warning')
         return redirect(url_for('main.schedule_dashboard'))

    try:
        # 1. Chỉ hiển thị flash và khởi động process
        flash(f'Đã gửi yêu cầu chạy tác vụ "{job.name}" (ID: {job_id}) vào nền. Tải lại trang sau giây lát để xem trạng thái.', 'info')

        # 2. Chuẩn bị config (nếu cần)
        app_config = {} # Hiện tại chưa dùng, nhưng có thể mở rộng sau này

        # 3. Khởi động Tiến trình Nền (Process)
        process = multiprocessing.Process(target=run_ai_in_background_process, args=(app_config, job_id))
        process.daemon = True 
        process.start() # Bắt đầu chạy tiến trình mới

        print(f"--- [Route] Đã khởi động tiến trình nền cho Job ID: {job_id} ---")

    except Exception as e:
        flash(f'Lỗi nghiêm trọng khi khởi động tiến trình chạy AI: {str(e)}', 'danger')

    return redirect(url_for('main.schedule_dashboard'))
# =================================================================
# TRANG HIỂN THỊ KẾT QUẢ XẾP LỊCH (Schedule Results)
# =================================================================

@main_bp.route('/scheduling/results/<int:job_id>', methods=['GET'])
def view_schedule_results(job_id):
    job = db.session.get(SchedulingJob, job_id)
    if not job:
        flash('Không tìm thấy tác vụ!', 'danger')
        return redirect(url_for('main.schedule_dashboard'))

    if job.status != JobStatus.COMPLETED:
        flash(f'Tác vụ "{job.name}" chưa hoàn thành.', 'warning')
        return redirect(url_for('main.schedule_dashboard'))

    stmt = (
        select(Assignment)
        .where(Assignment.job_id == job_id)
        .options(
            joinedload(Assignment.doctor),
            joinedload(Assignment.clinic),
            joinedload(Assignment.shift)
        )
        .order_by(Assignment.assignment_date, Shift.start_time) 
        # Cần join với Shift để có start_time
        .join(Assignment.shift) 
    )
    assignments_list = db.session.scalars(stmt).all()

    print("--- DEBUG: Danh sách bác sĩ lấy từ CSDL ---")

    return render_template(
        "schedule_results.html",
        job=job,
        assignments=assignments_list,
        title=f"Kết quả: {job.name}"
    )
# =================================================================
# TRANG HIỂN THỊ LỊCH (CALENDAR VIEW) - SỬA LẠI ĐỂ NHẬN JOB_ID
# =================================================================

# Route này sẽ xử lý cả 2 trường hợp:
# 1. /calendar (mặc định job_id=None)
# 2. /calendar/5 (job_id=5)
@main_bp.route('/calendar', defaults={'job_id': None})
@main_bp.route('/calendar/<int:job_id>')
def view_calendar(job_id):
    """
    Hiển thị kết quả của Tác vụ (Job) hoàn thành GẦN NHẤT
    HOẶC một Job ID cụ thể, dưới dạng bảng ma trận.
    """
    
    current_job = None
    
    if job_id:
        # 1. Nếu có Job ID, tìm Job đó
        current_job = db.session.get(SchedulingJob, job_id)
        if not current_job or current_job.status != JobStatus.COMPLETED:
            flash(f'Tác vụ (ID: {job_id}) không tìm thấy hoặc chưa hoàn thành.', 'danger')
            return redirect(url_for('main.schedule_dashboard'))
    else:
        # 2. Nếu không có Job ID (vào /calendar), tìm Job hoàn thành mới nhất
        current_job = db.session.scalar(
            select(SchedulingJob)
            .where(SchedulingJob.status == JobStatus.COMPLETED)
            .order_by(SchedulingJob.created_at.desc())
            .limit(1)
        )

    if not current_job:
        # Không có job nào hoàn thành (kể cả 2 trường hợp)
        today = datetime.date.today()
        year, month = today.year, today.month
        calendar_weeks = calendar.monthcalendar(year, month)
        
        return render_template(
            "calendar_view.html", 
            job=None, 
            year=year, month=month,
            date_range=[], doctors_list=[], assignments_map={}
        )

    # 3. Lấy thông tin tháng/năm từ Job đã tìm thấy
    year = current_job.start_date.year
    month = current_job.start_date.month
    
    # 4. Lấy tất cả Assignments của Job này
    stmt = (
        select(Assignment)
        .where(Assignment.job_id == current_job.id)
        .options(
            joinedload(Assignment.doctor),
            joinedload(Assignment.clinic),
            joinedload(Assignment.shift) 
        )
    )
    all_assignments = db.session.scalars(stmt).all()

    # 5. Tạo danh sách các ngày (cột)
    date_range = []
    current_date = current_job.start_date
    while current_date <= current_job.end_date:
        date_range.append(current_date)
        current_date += datetime.timedelta(days=1)
        
    # 6. Tạo Map kết quả và Danh sách bác sĩ (hàng)
    assignments_map = defaultdict(lambda: defaultdict(dict))
    doctors_in_schedule = {} 

    for assign in all_assignments:
        color = ['primary', 'success', 'danger', 'secondary'][assign.shift_id % 4]
        assignments_map[assign.doctor_id][assign.assignment_date] = {
            "shift_name": assign.shift.name,
            "clinic_name": assign.clinic.name,
            "color": color
        }
        if assign.doctor_id not in doctors_in_schedule:
            doctors_in_schedule[assign.doctor_id] = assign.doctor

    doctors_list = sorted(doctors_in_schedule.values(), key=lambda doc: doc.name)
    
    # 7. Render template
    return render_template(
        "calendar_view.html",
        job=current_job, # Truyền job đã tìm thấy
        date_range=date_range,
        doctors_list=doctors_list,
        assignments_map=assignments_map
    )