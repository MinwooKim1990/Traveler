import os
import logging
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

# 기본 설정
API_KEY = os.getenv('API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GMAPS_API_KEY = os.getenv('GMAPS_API_KEY')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SERVER_ID = int(os.getenv('SERVER_ID'))
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
RESPONSE_FOLDER = os.getenv('RESPONSE_FOLDER', 'responses')
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
HISTORY_SIZE = 10

# 업로드 폴더 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESPONSE_FOLDER, exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)-8s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)