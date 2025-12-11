# QL_XepLichBenhVien
Dùng thuật toán luyện kim để quản lý xếp lịch theo tiêu chí ràng buộc cứng và ràng buộc mềm dựa trên môi trường framwork flask dùng sql server,python,html kết hợp
Cách chạy thuật toán bao gồm các bước 

Bước 1: Tạo db trong sql 

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'HospitalSchedulerDB')
BEGIN
    CREATE DATABASE [HospitalSchedulerDB]
    COLLATE Vietnamese_CI_AS; 

    PRINT 'Da tao thanh cong CSDL [HospitalSchedulerDB] voi Collation Vietnamese_CI_AS.';
END
ELSE
BEGIN
    PRINT 'CSDL [HospitalSchedulerDB] da ton tai.';
END
GO

Bước 2 : đổi đường link dẫn trong file .env
SQLALCHEMY_DATABASE_URI="mssql+pyodbc://LAPTOP-LIJG7TF4\SQLLUAN/HospitalSchedulerDB?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"

Bước 3:
chạy lệnh: cd vô GitHub\QL_XepLichBenhVien\doctor-scheduler-python\app> 
và chạy lệnh : flask python reset_db.py

Bước 4: 
xong rồi chạy lệnh: cd..
để ra GitHub\QL_XepLichBenhVien\doctor-scheduler-python
chạy lệnh: flask seed all

Bước 5:
Chạy lệnh: flask run
Muốn debug: flask run --debug
hoặc chạy không reload: flask run --debug --no-reload
