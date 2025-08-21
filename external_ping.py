"""
Script để chạy từ máy tính cá nhân hoặc VPS khác
để ping và đánh thức bot trên Render
"""
import requests
import time
import schedule
import logging
from datetime import datetime

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ExternalPinger:
    def __init__(self, service_url):
        self.service_url = service_url.rstrip('/')
        
    def ping_service(self):
        """Ping service để đánh thức"""
        try:
            response = requests.get(f"{self.service_url}/health", timeout=30)
            if response.status_code == 200:
                logger.info(f"✅ Service is awake - Response: {response.status_code}")
                return True
            else:
                logger.warning(f"⚠️ Service responded with status: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to ping service: {e}")
            return False
    
    def wake_up_service(self):
        """Đánh thức service và thử nhiều lần nếu cần"""
        logger.info("🚀 Attempting to wake up service...")
        
        for attempt in range(3):
            if self.ping_service():
                logger.info(f"✅ Service is awake after {attempt + 1} attempt(s)")
                return True
            
            if attempt < 2:
                logger.info(f"⏳ Retrying in 30 seconds... (Attempt {attempt + 2}/3)")
                time.sleep(30)
        
        logger.error("❌ Failed to wake up service after 3 attempts")
        return False

def main():
    """Script chính"""
    # THAY ĐỔI URL này thành URL của service Render của bạn
    SERVICE_URL = "https://your-service-name.onrender.com"
    
    if "your-service-name" in SERVICE_URL:
        print("⚠️ Hãy thay đổi SERVICE_URL thành URL thực của service Render!")
        print("Ví dụ: https://instagram-telegram-bot.onrender.com")
        return
    
    pinger = ExternalPinger(SERVICE_URL)
    
    # Lên lịch ping mỗi 10 phút
    schedule.every(10).minutes.do(pinger.wake_up_service)
    
    logger.info(f"🎯 External pinger started for: {SERVICE_URL}")
    logger.info("📅 Scheduled to ping every 10 minutes")
    
    # Ping ngay lần đầu
    pinger.wake_up_service()
    
    # Chạy vòng lặp
    while True:
        schedule.run_pending()
        time.sleep(60)  # Kiểm tra mỗi phút

if __name__ == "__main__":
    main()
