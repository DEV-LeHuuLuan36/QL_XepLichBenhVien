from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from app import db, create_app
import datetime
import multiprocessing
from collections import defaultdict
import calendar

# Import Models
from app.models import (
    Doctor, Clinic, Shift, LeaveRequest, SchedulePreference, SchedulingJob,
    Assignment, DoctorRole
)
from app.models.scheduling_job import JobStatus 
from app.models.base import Base
from app.services.scheduling_service import SchedulingService

# Tạo Blueprint
main_bp = Blueprint('main', __name__)

# --- Trang chủ ---
@main_bp.route('/')
def index():
    try:    
        doctor_count = db.session.scalar(select(func.count(Doctor.id)))
        clinic_count = db.session.scalar(select(func.count(Clinic.id)))
        shift_count = db.session.scalar(select(func.count(Shift.id)))
        
        recent_doctors = db.session.scalars(
            select(Doctor).order_by(Doctor.id.desc()).limit(5)
        ).all()
        
    except Exception as e:
        print(f"Lỗi trang chủ: {e}")
        doctor_count = clinic_count = shift_count = 0
        recent_doctors = []
        flash("Không thể tải dữ liệu tổng quan.", "warning")

    return render_template(
        "index.html", 
        title="Trang chủ",
        doctor_count=doctor_count,
        clinic_count=clinic_count,
        shift_count=shift_count,
        recent_doctors=recent_doctors
    )

# --- Quản lý Bác sĩ ---
@main_bp.route('/doctors', methods=['GET', 'POST'])
def manage_doctors():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            specialty = request.form.get('specialty')
            if not name:
                flash("Tên là bắt buộc.", "danger")
            else:
                new_doctor = Doctor(name=name, specialty=specialty)
                db.session.add(new_doctor)
                db.session.commit()
                flash(f"Đã thêm bác sĩ '{name}'!", "success")
            return redirect(url_for('main.manage_doctors'))
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi: {e}", "danger")

    doctors_list = db.session.scalars(select(Doctor).order_by(Doctor.id)).all()
    return render_template("doctors.html", doctors=doctors_list, title="Quản lý Bác sĩ")

# --- Quản lý Phòng khám ---
@main_bp.route('/clinics', methods=['GET', 'POST'])
def manage_clinics():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            # Mặc định tạo cấu hình 2 Chính 1 Phụ
            new_clinic = Clinic(name=name, required_main=2, required_sub=1)
            db.session.add(new_clinic)
            db.session.commit()
            flash(f"Đã thêm khoa '{name}'!", "success")
            return redirect(url_for('main.manage_clinics'))
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi: {e}", "danger")

    clinics_list = db.session.scalars(select(Clinic).order_by(Clinic.id)).all()
    return render_template("clinics.html", clinics=clinics_list, title="Quản lý Phòng khám")

# --- Quản lý Ca trực ---
@main_bp.route('/shifts', methods=['GET', 'POST'])
def manage_shifts():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            start = request.form.get('start_time')
            end = request.form.get('end_time')
            
            s_time = datetime.datetime.strptime(start, '%H:%M').time()
            e_time = datetime.datetime.strptime(end, '%H:%M').time()
            
            new_shift = Shift(name=name, start_time=s_time, end_time=e_time)
            db.session.add(new_shift)
            db.session.commit()
            flash("Đã thêm ca trực!", "success")
            return redirect(url_for('main.manage_shifts'))
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi: {e}", "danger")

    shifts_list = db.session.scalars(select(Shift).order_by(Shift.start_time)).all()
    return render_template("shifts.html", shifts=shifts_list, title="Quản lý Ca trực")

# --- Quản lý Đơn nghỉ ---
@main_bp.route('/leave_requests', methods=['GET', 'POST'])
def manage_leave_requests():
    if request.method == 'POST':
        try:
            doc_id = request.form.get('doctor_id')
            date_str = request.form.get('leave_date')
            reason = request.form.get('reason')
            
            l_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            new_leave = LeaveRequest(doctor_id=doc_id, date=l_date, reason=reason, status="Approved")
            db.session.add(new_leave)
            db.session.commit()
            flash("Đã thêm đơn nghỉ!", "success")
            return redirect(url_for('main.manage_leave_requests'))
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi: {e}", "danger")

    leaves = db.session.scalars(select(LeaveRequest).options(joinedload(LeaveRequest.doctor)).order_by(LeaveRequest.date.desc())).all()
    doctors = db.session.scalars(select(Doctor).order_by(Doctor.name)).all()
    return render_template("leave_requests.html", leaves=leaves, doctors=doctors, title="Quản lý Đơn nghỉ")

# --- Quản lý Nguyện vọng ---
@main_bp.route('/preferences', methods=['GET', 'POST'])
def manage_preferences():
    if request.method == 'POST':
        try:
            doc_id = request.form.get('doctor_id')
            shift_id = request.form.get('shift_id')
            day = request.form.get('day_of_week')
            score = request.form.get('preference_score')
            
            new_pref = SchedulePreference(doctor_id=doc_id, shift_id=shift_id, day_of_week=day, preference_score=score)
            db.session.add(new_pref)
            db.session.commit()
            flash("Đã thêm nguyện vọng!", "success")
            return redirect(url_for('main.manage_preferences'))
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi: {e}", "danger")

    prefs = db.session.scalars(select(SchedulePreference).options(joinedload(SchedulePreference.doctor), joinedload(SchedulePreference.shift))).all()
    doctors = db.session.scalars(select(Doctor).order_by(Doctor.name)).all()
    shifts = db.session.scalars(select(Shift).order_by(Shift.name)).all()
    return render_template("preferences.html", preferences=prefs, doctors=doctors, shifts=shifts, title="Nguyện vọng")

# --- Dashboard Xếp lịch ---
@main_bp.route('/scheduling', methods=['GET'])
def schedule_dashboard():
    jobs = db.session.scalars(select(SchedulingJob).order_by(SchedulingJob.created_at.desc())).all()
    return render_template('schedule_dashboard.html', jobs=jobs)

@main_bp.route('/scheduling/create', methods=['POST'])
def create_scheduling_job():
    try:
        name = request.form.get('job_name')
        start = datetime.datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end = datetime.datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        
        if start > end: raise ValueError("Ngày bắt đầu phải trước ngày kết thúc")
        
        job = SchedulingJob(name=name, start_date=start, end_date=end)
        db.session.add(job)
        db.session.commit()
        flash(f"Đã tạo tác vụ '{name}'", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Lỗi: {e}", "danger")
    return redirect(url_for('main.schedule_dashboard'))

# --- Chạy AI (Background Process) ---
def run_ai_in_background_process(app_config, job_id):
    app = create_app()
    with app.app_context():
        try:
            print(f"--- [AI] Bắt đầu chạy Job {job_id} ---")
            service = SchedulingService(db.session)
            service.run_scheduling_job(job_id)
            print(f"--- [AI] Hoàn tất Job {job_id} ---")
        except Exception as e:
            print(f"--- [AI] Lỗi Job {job_id}: {e} ---")
            # Cập nhật trạng thái lỗi
            try:
                job = db.session.get(SchedulingJob, job_id)
                if job: 
                    job.status = JobStatus.FAILED
                    job.status_message = str(e)[:500]
                    db.session.commit()
            except: pass
        finally:
            db.session.remove()

@main_bp.route('/scheduling/run/<int:job_id>', methods=['POST'])
def run_scheduling_job(job_id):
    job = db.session.get(SchedulingJob, job_id)
    if not job or job.status != JobStatus.PENDING:
        flash("Tác vụ không hợp lệ để chạy.", "warning")
        return redirect(url_for('main.schedule_dashboard'))
    
    # Chạy process
    p = multiprocessing.Process(target=run_ai_in_background_process, args=(None, job_id))
    p.daemon = True
    p.start()
    
    flash(f"Đã gửi yêu cầu chạy tác vụ ID {job_id}. Vui lòng chờ...", "info")
    return redirect(url_for('main.schedule_dashboard'))

@main_bp.route('/scheduling/results/<int:job_id>')
def view_schedule_results(job_id):
    job = db.session.get(SchedulingJob, job_id)
    if not job or job.status != JobStatus.COMPLETED:
        flash("Tác vụ chưa hoàn thành.", "warning")
        return redirect(url_for('main.schedule_dashboard'))
    
    assignments = db.session.scalars(
        select(Assignment).where(Assignment.job_id==job_id)
        .options(joinedload(Assignment.doctor), joinedload(Assignment.clinic), joinedload(Assignment.shift))
        .join(Assignment.shift).order_by(Assignment.assignment_date, Shift.start_time)
    ).all()
    
    return render_template("schedule_results.html", job=job, assignments=assignments, title="Kết quả chi tiết")

# =================================================================
# TRANG HIỂN THỊ LỊCH (CALENDAR VIEW) - LỌC THEO KHOA
# =================================================================
@main_bp.route('/calendar', defaults={'job_id': None})
@main_bp.route('/calendar/<int:job_id>')
def view_calendar(job_id):
    """
    Hiển thị lịch trực dạng bảng ma trận.
    Hỗ trợ lọc theo Khoa và lọc theo thời gian (Tuần/Ngày).
    """
    current_job = None
    
    # 1. Xác định Job cần xem
    if job_id:
        current_job = db.session.get(SchedulingJob, job_id)
        if not current_job or current_job.status != JobStatus.COMPLETED:
            flash(f'Tác vụ (ID: {job_id}) chưa hoàn thành hoặc không tồn tại.', 'danger')
            return redirect(url_for('main.schedule_dashboard'))
    else:
        # Lấy job mới nhất đã hoàn thành
        current_job = db.session.scalar(
            select(SchedulingJob)
            .where(SchedulingJob.status == JobStatus.COMPLETED)
            .order_by(SchedulingJob.created_at.desc())
            .limit(1)
        )

    # Lấy danh sách khoa để tạo bộ lọc
    all_clinics = db.session.scalars(select(Clinic).order_by(Clinic.name)).all()

    if not current_job:
        today = datetime.date.today()
        return render_template(
            "calendar_view.html", 
            job=None, year=today.year, month=today.month,
            date_range=[], doctors_list=[], assignments_map={}, clinics=all_clinics
        )

    # --- XỬ LÝ LỌC THỜI GIAN (View Mode) ---
    view_mode = request.args.get('view_mode', 'all') # 'all', 'week', 'day'
    date_str = request.args.get('date')
    
    job_start = current_job.start_date
    job_end = current_job.end_date
    
    # Ngày mốc để lọc (mặc định là ngày bắt đầu job nếu không chọn)
    try:
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else job_start
    except:
        target_date = job_start

    final_start = job_start
    final_end = job_end

    if view_mode == 'day':
        final_start = target_date
        final_end = target_date
    elif view_mode == 'week':
        # Tính thứ 2 đầu tuần
        start_of_week = target_date - datetime.timedelta(days=target_date.weekday())
        end_of_week = start_of_week + datetime.timedelta(days=6)
        final_start = max(job_start, start_of_week)
        final_end = min(job_end, end_of_week)
    
    # Đảm bảo không vượt quá phạm vi job
    if final_start < job_start: final_start = job_start
    if final_end > job_end: final_end = job_end

    # Tạo danh sách ngày hiển thị
    date_range = []
    curr = final_start
    while curr <= final_end:
        date_range.append(curr)
        curr += datetime.timedelta(days=1)

    # 3. Lấy dữ liệu phân công
    stmt = (
        select(Assignment)
        .where(Assignment.job_id == current_job.id)
        .options(
            joinedload(Assignment.doctor).joinedload(Doctor.clinic),
            joinedload(Assignment.clinic),
            joinedload(Assignment.shift) 
        )
    )
    all_assignments = db.session.scalars(stmt).all()

    # --- [SỬA ĐỔI] Dùng list để chứa nhiều ca trong 1 ngày ---
    assignments_map = defaultdict(lambda: defaultdict(list)) 
    doctors_in_schedule = {} 

    for assign in all_assignments:
        color = ['primary', 'success', 'danger', 'secondary'][assign.shift_id % 4]
        
        # --- [SỬA ĐỔI] Append vào list thay vì gán đè ---
        assignments_map[assign.doctor_id][assign.assignment_date].append({
            "shift_name": assign.shift.name,
            "clinic_name": assign.clinic.name,
            "color": color
        })
        
        if assign.doctor_id not in doctors_in_schedule:
            doctors_in_schedule[assign.doctor_id] = assign.doctor

    # --- SẮP XẾP DANH SÁCH BÁC SĨ (Logic Mới) ---
    doctors_list = sorted(
        doctors_in_schedule.values(), 
        key=lambda doc: (
            doc.clinic.name if doc.clinic else "zz_Khac", # Gom theo Khoa
            0 if doc.role == DoctorRole.MAIN else 1,      # Chính lên trước
            doc.name                                      # Tên A-Z
        )
    )
    
    return render_template(
        "calendar_view.html",
        job=current_job, 
        date_range=date_range,
        doctors_list=doctors_list,
        assignments_map=assignments_map,
        clinics=all_clinics,
        current_view=view_mode,
        current_date=target_date.strftime('%Y-%m-%d')
    )