# Bot bán tài khoản Discord

## Chạy bot

Cài Python 3.10+ và `pip install -r requirements.txt`, cấu hình `.env` ở thư mục gốc:

```ini
DISCORD_TOKEN=...
BANK_CODE=MBB
ACCOUNT_NO=...
ACCOUNT_NAME=...
WEB2M_PASSWORD=...
WEB2M_TOKEN=...
PENDING_TTL_SECONDS=1800
```

Chạy `python main.py` tại thư mục dự án. Khởi động lại bot sau khi thay code.

## Cập nhật theo sự kiện

- Tạo kênh `ticket-...` hoặc đổi tên kênh thành ticket: bot tự gửi menu. Khi khởi động/kết nối lại, bot kiểm tra các ticket chưa được ghi nhận một lần.
- Khách chọn mua: kiểm tra tồn kho hiện tại và yêu cầu cập nhật menu. Khi giao acc, menu được cập nhật theo tồn kho mới.
- Admin thêm list qua `/add_account` (text hoặc file): cập nhật menu và đánh thức xử lý đơn đã thanh toán đang chờ hàng.
- Các yêu cầu cập nhật gần nhau được gom lại. Nếu số lượng không đổi, bot bỏ qua sửa menu. `/refresh` vẫn cho phép cập nhật thủ công.
- Nếu thay trực tiếp file kho trên máy chủ, dùng `/refresh` để cập nhật ngay; bot cũng nhận thay đổi vào lần khách mua/tạo ticket tiếp theo. Không có vòng quét file liên tục.
- Không còn quét ticket mỗi giây, sửa menu mỗi phút hoặc tự quét/xóa lịch sử DM và gửi kho mỗi giờ.
- Chỉ kiểm tra Web2M khi có đơn chờ thanh toán, mỗi 60 giây và khi có đơn/list mới. Mỗi lượt lấy lịch sử một lần cho tất cả đơn, chạy ngoài luồng Discord. Khi không có đơn, worker ngủ chờ sự kiện. Đơn đã thanh toán nhưng thiếu hàng chờ lần nạp kho tiếp theo.
- Đếm kho có cache theo thời gian sửa/kích thước file; đọc và lấy acc theo từng dòng để giảm RAM. Tắt cache tin nhắn, thành viên và các gateway intent không cần thiết.

## Kiểm tra cục bộ

```bash
python -m unittest discover -s tests -v
python -m compileall -q core cogs ui utils Modules main.py
```

Các kiểm tra dùng dữ liệu tạm và mô phỏng Discord/Web2M, không tạo đơn hay gửi tin nhắn thật.

## Bộ đếm ở tên kênh

Kênh `1416059603996901427` chỉ hiển thị tổng kho, ví dụ `🟢 CÒN 250 TÀI KHOẢN`. Khi hết kho hiện `🔴 HẾT TÀI KHOẢN`. Không liệt kê từng loại trong tên kênh.

Bot cần quyền **Manage Channels / Quản lý kênh** tại kênh này. Cập nhật khi khởi động/kết nối lại, tạo ticket, mua/giao acc, `/add_account` hoặc `/refresh`. Không quét định kỳ. Các lần đổi tên cách nhau tối thiểu 10 phút; thay đổi trong khoảng chờ được gộp và lấy số lượng mới nhất. Menu mua hàng vẫn cập nhật riêng, không phải chờ đổi tên kênh.

Thời gian chờ đổi tên được lưu trong `data/stock_channel_state.json`, nên khởi động lại không xóa thời gian chờ. Lần đầu chạy bản có cơ chế này, bot chờ 10 phút trước khi đổi tên để tránh trùng với lượt đổi tên từ bản cũ. Trong lúc chờ, mua hàng và menu vẫn hoạt động. Nếu Discord trả 429, thư viện tự chờ theo thời gian Discord yêu cầu; không cần khởi động lại liên tục.

## Bảo hành tự động

Cập nhật thư viện bằng `python -m pip install -U -r requirements.txt` rồi khởi động lại bot. Form tải ảnh/video cần discord.py 2.7.1 trở lên. Nút **🛡️ Bảo hành** được gắn vào bảng giao acc mới, kể cả đơn giao qua file TXT. Nút hoạt động lại sau khi bot khởi động lại mà không phải giữ một view trong RAM cho mỗi đơn.

- Acc thường: **2 giờ**; acc **Chủ Off: 5 giờ**, tính từ lúc gửi acc thành công. Mỗi acc gốc được đổi tối đa một lần. Acc thay thế không tạo thêm lượt đổi.
- Chỉ người mua đơn được mở bảng riêng tư. Bot lấy loại acc từ sổ đơn đã giao, khách không được chọn loại khác.
- Chọn tối đa 10 acc trong mỗi đợt, có phân trang 25 acc để xử lý đơn lớn. Upload bắt buộc đúng một ảnh/video cho mỗi acc đã chọn và mô tả lỗi. Tiếp tục đợt khác cho các acc còn lại.
- Nhận PNG/JPG/GIF/WebP, MP4/MOV/WebM/AVI; tối đa 25 MB/file và 100 MB/đợt, đồng thời tuân theo giới hạn upload của Discord. Bot kiểm tra dấu hiệu định dạng file, đếm file và chặn nội dung file trùng bằng SHA-256. Đây **không phải xác minh bằng AI rằng acc thực sự lỗi**; ảnh bị chỉnh sửa hoặc ảnh khác của cùng lỗi không được nhận diện tự động.
- Khi đủ kho, tự cấp đúng số acc từ đúng loại kho. Khi chưa đủ toàn bộ đợt, giữ yêu cầu và không trừ một phần; khách bấm **Đã gửi / Nhận lại** sau khi shop nạp kho. Yêu cầu được nhận trong hạn vẫn có thể nhận bù sau khi hết hạn.
- Nếu gửi Discord bị lỗi, bấm **Đã gửi / Nhận lại** để xem lại chính các acc đã cấp, không trừ thêm kho. Kết quả bảo hành chỉ gửi riêng cho người mua.
- Sổ đơn, từng acc đã đổi và kết quả nằm trong `data/warranty.sqlite3`; bằng chứng nằm trong `data/warranty_evidence/`. Sao lưu chúng cùng kho. Journal cấp acc bảo hành được phục hồi trước khi bán/thêm kho; nếu kho bị sửa bên ngoài giữa giao dịch và không còn khớp, bot dừng thao tác để admin kiểm tra thay vì đoán và giao nhầm.
- Chỉ chạy một tiến trình bot trên cùng thư mục kho TXT. Không sửa trực tiếp file kho khi đang có giao dịch.
- Đơn đã giao bằng bản cũ không có sổ xác minh, không tự chuyển thành đơn bảo hành. Các đơn mới sau cập nhật có đầy đủ nút và sổ bảo hành.

Kiểm tra bảo hành: `python -m unittest discover -s tests -p test_warranty.py -v`.

