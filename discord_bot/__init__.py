# discord_bot 패키지
from .bot import start_bot, bot

# message.py가 api.routes에 의존하므로 여기서 import할 수 없음
# 대신 이 함수를 만들어서 필요할 때 임포트하도록 함

# 모든 코드에서 기존과 동일하게 작동하도록 패키지 레벨 변수로 함수 구현
def send_location_to_discord(latitude, longitude, street, city, extra_message=None, image_path=None, audio_path=None, show_places=False, message_include=True):
    """원형 참조 문제를 해결하기 위한 래퍼 함수"""
    # 필요할 때만 임포트
    from .message import send_location_to_discord as _send_location
    return _send_location(latitude, longitude, street, city, extra_message, image_path, audio_path, show_places, message_include)

__all__ = [
    'start_bot',
    'bot',
    'send_location_to_discord'
]