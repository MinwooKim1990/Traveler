import google.generativeai as genai
import PIL.Image
import os
import sys
from config import GEMINI_API_KEY
from typing import Optional
import logging

# 로깅 설정
logging.basicConfig(level=logging.DEBUG, 
                    format='[%(asctime)s] [%(levelname)-8s] %(message)s', 
                    datefmt='%Y-%m-%d %H:%M:%S')

# 추가: 전역 변수 HISTORY 선언
HISTORY = []

def gemini_bot(system_prompt: Optional[str] = None, user_input: str = "", image_path: Optional[str] = None, history_turns: int = 7, function_call: Optional[list] = None, config_dict: Optional[dict] = None):
    # API 키 설정
    genai.configure(api_key=GEMINI_API_KEY)
    
    # 모델 선택
    model = genai.GenerativeModel('gemini-2.0-flash-lite')
    
    # 전역 대화 기록 사용
    global HISTORY
    if system_prompt is None:
        system_prompt = "당신은 여행자를 돕는 친절한 AI 어시스턴트입니다. 한국어로 상세한 답변을 제공합니다."
    
    # 시스템 프롬프트는 항상 첫번째에 유지
    if not HISTORY:
        HISTORY = [system_prompt]
    else:
        HISTORY[0] = system_prompt

    # 이미지 로드 - 이미지 경로가 있고 실제 파일이 존재할 때만 처리
    image = None
    if image_path and os.path.exists(image_path):
        try:
            image = PIL.Image.open(image_path)
            logging.debug(f"이미지 파일 첨부: {image_path}")
        except Exception as e:
            logging.error(f"이미지 로드 실패: {e}")
            image = None

    # 대화 기록 업데이트
    HISTORY.append(f"User: {user_input}")

    # 히스토리 유지: 시스템 프롬프트 + 최근 history_turns*2 메시지 유지
    if len(HISTORY) > (history_turns * 2 + 1):
        HISTORY = [HISTORY[0]] + HISTORY[-(history_turns * 2):]

    # 프롬프트 구성 (순서 변경: 시스템 프롬프트, 이미지(존재 시), user_input, 그리고 이전 대화 기록)
    try:
        prompt_parts = []
        # 전체 대화 기록 사용 (시스템 프롬프트 포함)
        prompt_parts.extend(HISTORY)
        
        # 이미지가 있는 경우, prompt에 이미지 객체를 시스템 프롬프트와 유저 입력 사이에 추가
        if image is not None:
            # 이미지 정보를 프롬프트에 추가 (이미지 객체 직접 전달)
            prompt_parts.insert(1, image)
        
        if function_call is not None:
            response = model.generate_content(prompt_parts, config=config_dict)
        else:
            # LLM 호출
            response = model.generate_content(prompt_parts)

        # LLM 응답 저장 및 출력
        llm_response = response.text
        HISTORY.append(f"Assistant: {llm_response}")
        return llm_response
    except Exception as e:
        error_msg = f"LLM 호출 중 오류 발생: {e}"
        logging.error(error_msg)
        return error_msg

if __name__ == "__main__":
    # 텍스트만 있는 경우
    response1 = gemini_bot(
        system_prompt="여행자를 위한 정보를 제공하는 AI 어시스턴트입니다.",
        user_input="서울에서 가볼만한 곳을 추천해줘"
    )
    print("텍스트 응답:", response1)
    
    # 이미지가 있는 경우
    response2 = gemini_bot(
        system_prompt="이 이미지에 대해 자세히 설명해주세요.",
        user_input="이 이미지에 대해 자세한 설명을 자세한 역사와 트리비아 등등을 포함해서 해설해줘",
        image_path="../uploads/gogh.jpg"
    )
    print("이미지 응답:", response2)