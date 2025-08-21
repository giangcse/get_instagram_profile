# Hướng dẫn sử dụng UptimeRobot để tự động đánh thức bot

## 🤖 UptimeRobot - Giải pháp miễn phí tốt nhất

UptimeRobot là dịch vụ miễn phí giúp monitor và ping website của bạn mỗi 5 phút.

### Bước 1: Đăng ký UptimeRobot
1. Truy cập: https://uptimerobot.com
2. Đăng ký tài khoản miễn phí
3. Xác thực email

### Bước 2: Tạo Monitor
1. Đăng nhập → Click **"+ Add New Monitor"**
2. **Monitor Type**: `HTTP(s)`
3. **Friendly Name**: `Instagram Bot Keep Alive`
4. **URL**: `https://your-service-name.onrender.com/health`
5. **Monitoring Interval**: `5 minutes` (free plan)
6. Click **"Create Monitor"**

### Bước 3: Cấu hình Alert (tùy chọn)
1. Trong monitor vừa tạo → **Alert Contacts**
2. Thêm email để nhận thông báo khi bot down
3. **Alert When**: `Down` và `Up`

## 📱 Các giải pháp khác

### 1. Cron-job.org (Miễn phí)
- Truy cập: https://cron-job.org
- Tạo job ping mỗi 10 phút
- URL: `https://your-service-name.onrender.com/ping`

### 2. Freshping (Miễn phí)
- Truy cập: https://www.freshworks.com/website-monitoring/
- Monitor miễn phí với interval 1 phút
- Có mobile app để theo dõi

### 3. StatusCake (Miễn phí)
- Truy cập: https://www.statuscake.com
- Uptime monitoring miễn phí
- Ping mỗi 5 phút

## 🖥️ Chạy script từ máy tính cá nhân

Nếu bạn có máy tính luôn bật:

```bash
# Cài đặt dependencies
pip install requests schedule

# Chỉnh sửa SERVICE_URL trong external_ping.py
# Rồi chạy:
python external_ping.py
```

## ⚡ VPS/Server khác

Nếu có VPS hoặc server khác:

```bash
# Tạo crontab job
crontab -e

# Thêm dòng này (ping mỗi 10 phút):
*/10 * * * * curl -s https://your-service-name.onrender.com/health > /dev/null
```

## 🎯 Khuyến nghị

**Tốt nhất**: UptimeRobot (miễn phí, ổn định, 5 phút/lần)
**Backup**: Cron-job.org (miễn phí, flexible hơn)
**Professional**: Upgrade Render lên paid plan ($7/tháng)
