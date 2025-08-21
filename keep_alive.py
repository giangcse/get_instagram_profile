"""
Script để giữ bot luôn hoạt động và tự động đánh thức khi bị sleep
"""
import requests
import time
import logging
from threading import Thread
import os
from flask import Flask

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KeepAlive:
    def __init__(self, service_url=None):
        self.service_url = service_url or os.getenv('RENDER_EXTERNAL_URL', 'https://your-service-name.onrender.com')
        self.app = Flask(__name__)
        self.setup_routes()
    
    def setup_routes(self):
        """Tạo một endpoint đơn giản để Render có thể ping"""
        @self.app.route('/')
        def home():
            return "Bot is alive! 🤖"
        
        @self.app.route('/health')
        def health():
            return {"status": "healthy", "timestamp": time.time()}
        
        @self.app.route('/ping')
        def ping():
            return "pong"
    
    def ping_self(self):
        """Ping chính service này để giữ nó luôn hoạt động"""
        while True:
            try:
                response = requests.get(f"{self.service_url}/ping", timeout=30)
                if response.status_code == 200:
                    logger.info(f"✅ Keep-alive ping successful at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    logger.warning(f"⚠️ Keep-alive ping returned status {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Keep-alive ping failed: {e}")
            
            # Ping mỗi 14 phút (trước khi Render sleep sau 15 phút)
            time.sleep(14 * 60)
    
    def start_ping_thread(self):
        """Khởi động thread ping trong background"""
        ping_thread = Thread(target=self.ping_self, daemon=True)
        ping_thread.start()
        logger.info("🚀 Keep-alive ping thread started")
    
    def run_server(self, port=8080):
        """Chạy Flask server"""
        logger.info(f"🌐 Starting Flask server on port {port}")
        self.app.run(host='0.0.0.0', port=port, debug=False)

# Khởi tạo KeepAlive instance
keep_alive = KeepAlive()

def start_keep_alive():
    """Function để import và sử dụng trong tele_bot.py"""
    keep_alive.start_ping_thread()
    return keep_alive.app

if __name__ == "__main__":
    # Nếu chạy trực tiếp file này
    keep_alive.start_ping_thread()
    keep_alive.run_server()
