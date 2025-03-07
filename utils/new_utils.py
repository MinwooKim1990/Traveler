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
    if len(history) > k * 2:  # 쌍으로 계산하므로 k*2
        history = history[-(k*2):]
    
    # 대화 내용 구성: Gemini API에 맞는 형식으로 구성
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 히스토리를 Gemini 포맷으로 변환
    gemini_messages = []
    
    # 시스템 메시지 추가
    gemini_messages.append(system_prompt)
    
    # 기존 대화 히스토리 추가
    for i in range(0, len(history), 2):
        if i+1 < len(history):  # 쌍이 완성된 경우만
            user_msg = history[i]['content']
            assistant_msg = history[i+1]['content']
            gemini_messages.append(user_msg)
            gemini_messages.append(assistant_msg)
    
    # 새 사용자 메시지 추가
    gemini_messages.append(new_message)
    
    print("히스토리 길이:", len(history))
    print("API에 보내는 메시지 수:", len(gemini_messages))
    
    try:
        if image_path is None or image_path == "":
            print("No image conversation")
            
            if function_list is not None:
                print("Function list")
                config = {"tools": function_list}
                response = client.models.generate_content(
                    model='gemini-2.0-flash-lite',
                    config=config,
                    contents=gemini_messages  # 전체 대화 히스토리 포함
                )
            else:
                print("No function list")
                response = client.models.generate_content(
                    model='gemini-2.0-flash-lite',
                    contents=gemini_messages  # 전체 대화 히스토리 포함
                )
            
        else:
            print("Image conversation")
            # 이미지 파일이 존재하는지 확인
            if os.path.exists(image_path):
                image = PIL.Image.open(image_path)
                
                # 이미지가 포함된 메시지는 히스토리의 마지막 메시지와 병합해야 함
                # 마지막 메시지를 제외한 히스토리 구성
                image_messages = gemini_messages[:-1]
                
                # 이미지와 마지막 텍스트 메시지를 함께 추가
                final_message = [new_message, image]
                
                if function_list is not None:
                    print("Function list with image")
                    config = {"tools": function_list}
                    response = client.models.generate_content(
                        model='gemini-2.0-flash-lite',
                        config=config,
                        contents=image_messages + [final_message]  # 히스토리 + 이미지 메시지
                    )
                else:
                    print("No function list with image")
                    response = client.models.generate_content(
                        model='gemini-2.0-flash-lite',
                        contents=image_messages + [final_message]  # 히스토리 + 이미지 메시지
                    )
            else:
                # 이미지 파일이 존재하지 않으면 텍스트만 처리
                print("Image file not found, fallback to text only")
                if function_list is not None:
                    config = {"tools": function_list}
                    response = client.models.generate_content(
                        model='gemini-2.0-flash-lite',
                        config=config,
                        contents=gemini_messages  # 전체 대화 히스토리 포함
                    )
                else:
                    response = client.models.generate_content(
                        model='gemini-2.0-flash-lite',
                        contents=gemini_messages  # 전체 대화 히스토리 포함
                    )
        
        # 히스토리 업데이트
        try:
            history.append({"role": "user", "content": new_message})
            history.append({"role": "assistant", "content": response.text})
            
            print(response.text)
            return history
        except AttributeError:
            # response.text가 없는 경우
            print("응답에 text 속성이 없습니다.")
            history.append({"role": "user", "content": new_message})
            history.append({"role": "assistant", "content": "응답을 생성할 수 없습니다."})
            return history
    except ValueError as ve:
        print("ValueError가 발생했습니다:", ve)
        history.append({"role": "user", "content": new_message})
        history.append({"role": "assistant", "content": f"오류: {str(ve)}"})
        return history
    except Exception as e:
        print("예기치 않은 오류가 발생했습니다:", e)
        history.append({"role": "user", "content": new_message})
        history.append({"role": "assistant", "content": f"오류: {str(e)}"})
        return history