# Abraham Bike Landing Page

Landing page kích hoạt bảo hành điện tử, chạy bằng web server có sẵn của Python.

## Chạy dự án

```powershell
python app.py
```

Sau đó mở [http://127.0.0.1:8000](http://127.0.0.1:8000).

Không cần cài đặt thêm thư viện. Nhấn `Ctrl+C` trong terminal để dừng server.

## Trang quản trị

Mở [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin) để xem dữ liệu khách hàng đã gửi từ form.

- Tên đăng nhập mặc định là `admin`.
- Mật khẩu mặc định là `123456`.
- Có thể đặt thông tin đăng nhập an toàn hơn bằng biến môi trường `ADMIN_USERNAME` và `ADMIN_PASSWORD`.

Ví dụ trong PowerShell:

```powershell
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="mat-khau-an-toan"
python app.py
```

Dữ liệu form được lưu trong SQLite tại `data/warranties.db`. Thư mục `data/` đã được loại khỏi Git để không công khai thông tin khách hàng.

Khi triển khai công khai, hãy dùng HTTPS để bảo vệ thông tin đăng nhập và bảo đảm máy chủ có ổ đĩa lưu trữ lâu dài cho database SQLite.
