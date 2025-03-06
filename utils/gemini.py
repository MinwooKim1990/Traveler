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

def gemini_bot(system_prompt: Optional[str] = None, user_input: str = "", image_path: Optional[str] = None, history_turns: int = 7):
    # API 키 설정
    genai.configure(api_key=GEMINI_API_KEY)
    
    # 모델 선택
    model = genai.GenerativeModel('gemini-2.0-flash-lite')
    
    # 히스토리 리스트
    history = []  # 유저 프롬프트와 LLM 응답을 저장하는 리스트
    
    if system_prompt is None:
        system_prompt="당신은 여행자를 돕는 친절한 AI 어시스턴트입니다. 한국어로 상세한 답변을 제공합니다."

    # 이미지 로드 - 이미지 경로가 있고 실제 파일이 존재할 때만 처리
    image = None
    if image_path and os.path.exists(image_path):
        try:
            image = PIL.Image.open(image_path)
            logging.debug(f"이미지 파일 첨부: {image_path}")
        except Exception as e:
            logging.error(f"이미지 로드 실패: {e}")
            # 이미지 로드 실패 시 None으로 설정하여 추가하지 않음
            image = None

    # 히스토리 업데이트 (최근 N턴 유지)
    history.append(f"User: {user_input}")
    
    # `history_turns` 초과 시 가장 오래된 기록 삭제
    if len(history) > history_turns * 2:  # user와 llm 응답 포함하므로 *2
        history = history[-(history_turns * 2):]

    # 프롬프트 구성
    try:
        prompt_parts = []
        prompt_parts.append(system_prompt)
        prompt_parts.append(user_input)
        
        # 이미지가 있는 경우 추가
        if image is not None:
            prompt_parts.append(image)
            
        # LLM 호출
        response = model.generate_content(prompt_parts)

        # LLM 응답 저장 및 출력
        llm_response = response.text
        history.append(f"Assistant: {llm_response}")
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