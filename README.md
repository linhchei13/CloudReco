## 1.  Cài đặt thư viện:
   
```pip install -r requirements.txt```

## 2.  Chạy hệ thống (Test tại Local)

Bạn cần mở **3 cửa sổ Terminal** (hoặc 3 tab PowerShell). Cả 3 đều phải ở trong thư mục `backend` và đã kích hoạt `.venv`.

###  Terminal 1: Chạy App Server (API)

1.  **Cài đặt biến môi trường** (làm cho mỗi lần chạy terminal mới):
    ```powershell
    Get-Content .env | Foreach-Object { $name, $value = $_.Split('=', 2); Set-Content "env:\$name" $value }
    ```

2.  **Khởi động App:**
    ```bash
    python app.py
    ```
    *Bạn sẽ thấy server chạy ở `http://127.0.0.1:5000`. Để yên cửa sổ này.*

###  Terminal 2: Chạy Worker

1.  **Cài đặt biến môi trường** (Làm lại giống Terminal 1):
    ```powershell
    # Dùng lệnh này trên PowerShell
    Get-Content .env | Foreach-Object { $name, $value = $_.Split('=', 2); Set-Content "env:\$name" $value }
    ```
2.  **Khởi động Worker:**
    ```bash
    python worker.py
    ```
    *Bạn sẽ thấy worker khởi động và "Polling SQS...". Để yên cửa sổ này.*

###  Terminal 3: Gửi ảnh (Client)

1.  Chuẩn bị một file ảnh (ví dụ `cat.jpg`) trong thư mục `backend`.
2.  Chạy lệnh `curl.exe` để gửi file:
    ```powershell
    # Dùng curl.exe trên Windows PowerShell
    curl.exe -X POST -F "image_file=@cat.jpg" [http://127.0.0.1:5000](http://127.0.0.1:5000)
    ```
    *Thay cat.jpg bằng file ảnh khác.*

---

## 3.  Kết quả 

Nếu mọi thứ thành công:

* **Terminal 3 (Client):** Sẽ in ra một kết quả JSON (sau vài giây) chứa các nhãn mà Rekognition tìm thấy:
    ```json
    {"result":{"analysis_service":"aws_rekognition","filename":"cat.jpg","labels":[{"name":"Cat","confidence":99.1...}, ...],"uid":"..."},"uid":"..."}
    ```
* **Terminal 1 (App):** Sẽ in ra log `... "POST / HTTP/1.1" 200 -`
* **Terminal 2 (Worker):** Sẽ in ra log xử lý: `Bắt đầu gọi Rekognition...`, `Rekognition thành công...`, `Xử lý thành công...`

