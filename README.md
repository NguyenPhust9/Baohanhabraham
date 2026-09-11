# Abraham Bike Warranty

Ứng dụng kích hoạt bảo hành điện tử bằng Flask, chạy được trên máy cá nhân và Vercel.

## Chạy dự án

```powershell
python -m pip install -r requirements.txt
python app.py
```

Sau đó mở [http://127.0.0.1:8000](http://127.0.0.1:8000).

Không cần cài đặt thêm thư viện. Nhấn `Ctrl+C` trong terminal để dừng server.

## Trang quản trị

Mở đường dẫn `/admin` trên chính tên miền đang chạy website để vào trang đăng nhập và xem dữ liệu khách hàng. Ví dụ khi chạy thử trên máy là [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin); khi triển khai tại `https://example.com` thì trang quản trị là `https://example.com/admin`.

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

## Triển khai trên Vercel

Vercel tự nhận diện `app.py` là ứng dụng Flask. Trang quản trị nằm tại `/admin` trên domain của dự án.

Để lưu dữ liệu bền vững trên Vercel:

1. Trong Vercel, mở **Storage/Marketplace** và thêm một PostgreSQL database, ví dụ Neon.
2. Kết nối database với dự án để có biến môi trường `DATABASE_URL` (ứng dụng cũng nhận `POSTGRES_URL`).
3. Redeploy dự án.
4. Trong **Settings → Environment Variables**, nên đặt `ADMIN_USERNAME`, `ADMIN_PASSWORD` và `SECRET_KEY`.

Nếu chưa kết nối PostgreSQL, trang đăng nhập vẫn hoạt động nhưng dashboard sẽ hiển thị cảnh báo và form sẽ chưa thể lưu dữ liệu.
