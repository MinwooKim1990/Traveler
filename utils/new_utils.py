import PIL.Image
from google import genai
from config import GEMINI_API_KEY
from duckduckgo_search import DDGS
from datetime import datetime
from timezonefinder import TimezoneFinder
import pytz
import os
import time

def get_search_results(query: str):
    results = []
    pages = 2
    try:
        ddg_results = DDGS().text(query, max_results=pages * 20)
        for item in ddg_results:
            href = item.get("href")
            if not href:
                continue
            parts = href.split("/")
            domain = parts[2] if len(parts) > 2 else ""
            result_item = {
                "kind": "duckduckgo#result",
                "title": item.get("title", "").strip(),
                "link": href.strip(),
                "snippet": item.get("body", "").strip(),
                "displayLink": domain
            }
            # 동일 도메인 결과 제외
            if all(r['displayLink'] != domain for r in results):
                results.append(result_item)
    except Exception as e:
        print(f"DuckDuckGo 검색 오류: {e}")
    return results

def get_local_time_by_gps(lat, lng):
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lng=float(lng), lat=float(lat))
    if not tz_name:
        tz_name = "UTC"  # 기본값: UTC
    local_tz = pytz.timezone(tz_name)
    return datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

def generate_unique_filename(prefix, original_filename):
    """
    고유한 파일 이름을 생성합니다.
    
    Parameters:
        prefix: 파일 이름 접두사 ('image' 또는 'audio')
        original_filename: 원본 파일 이름
        
    Returns:
        생성된 고유 파일 이름
    """
    # 확장자 추출
    _, file_extension = os.path.splitext(original_filename)
    
    # 현재 시간과 UUID를 사용하여 고유한 번호 생성
    unique_id = int(time.time() * 1000) % 100000
    
    # 새 파일 이름 형식: image_12345.jpg 또는 audio_12345.mp3
    return f"{prefix}_{unique_id}{file_extension}"

def generate_content_with_history(system_prompt: str, new_message: str, function_list: list = None, image_path: str = None, k: int = 7, history: list = None):
    
    # 히스토리 초기화: 전달된 히스토리가 없으면 빈 리스트로 생성
    if history is None:
        history = []
    
    # 최신 k 턴의 히스토리만 유지 (시스템 프롬프트는 항상 맨 앞에 유지)
    if len(history) > k:
        history = history[-k:]
    
    # 대화 내용 구성: Gemini API에 맞는 형식으로 구성
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 시스템 프롬프트 구성
    system_message = {"role": "system", "parts": [{"text": system_prompt}]}
    
    try:
        if image_path is None:
            print("No image conversation")
            
            if function_list is not None:
                print("Function list")
                config = {"tools": function_list}
                response = client.models.generate_content(
                    model='gemini-2.0-flash-lite',
                    config=config,
                    contents=[system_prompt, new_message]
                )
            else:
                print("No function list")
                response = client.models.generate_content(
                    model='gemini-2.0-flash-lite',
                    contents=[system_prompt, new_message]
                )
            
        else:
            print("Image conversation")
            image = PIL.Image.open(image_path)
            
            if function_list is not None:
                print("Function list with image")
                config = {"tools": function_list}
                response = client.models.generate_content(
                    model='gemini-2.0-flash-lite',
                    config=config,
                    contents=[system_prompt, new_message, image]
                )
            else:
                print("No function list with image")
                response = client.models.generate_content(
                    model='gemini-2.0-flash-lite',
                    contents=[system_prompt, new_message, image]
                )
        
        # 히스토리 업데이트
        history.append({"role": "user", "content": new_message})
        history.append({"role": "assistant", "content": response.text})
        
        print(response.text)
        return history
    except ValueError as ve:
        print("ValueError가 발생했습니다:", ve)
        return history
    except Exception as e:
        print("예기치 않은 오류가 발생했습니다:", e)
        return history