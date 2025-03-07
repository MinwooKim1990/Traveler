# %%
"""
여행 위치 정보 공유 애플리케이션

이 애플리케이션은 위치 정보, 이미지, 음성 등을 받아 디스코드 채널로 전송하고
주변 장소 정보를 함께 제공합니다.
"""
import logging
from config import HOST, PORT, DEBUG
from discord_bot import start_bot
from api import app

def main():
    """애플리케이션 메인 함수"""
    # 디스코드 봇 시작
    bot = start_bot()
    
    # Flask 서버 실행
    logging.info(f"Flask 서버 시작 - {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG, use_reloader=False)

if __name__ == '__main__':
    main()

# %%
