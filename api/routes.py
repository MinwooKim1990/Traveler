import os
import logging
import asyncio
import concurrent.futures
import time
import uuid
import json
from pathlib import Path
from flask import Flask, request, jsonify
from config import API_KEY, UPLOAD_FOLDER, RESPONSE_FOLDER
from discord_bot import bot, send_location_to_discord
from utils.gemini import gemini_bot
from utils.audio_convert import convert_m4a_to_mp3_moviepy
from utils.whisper_gen import transcribe_audio, synthesize_speech
from utils import search_nearby_places as maps_search_nearby

# 응답 저장 폴더 생성
os.makedirs(RESPONSE_FOLDER, exist_ok=True)

app = Flask(__name__)

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

def create_restaurant_system_prompt(latitude, longitude, places):
    """
    주변 식당 정보를 기반으로 시스템 프롬프트를 생성합니다.
    
    Parameters:
        latitude: 현재 위치의 위도
        longitude: 현재 위치의 경도
        places: 주변 장소 정보 리스트
        
    Returns:
        시스템 프롬프트 문자열
    """
    prompt = f"""
당신은 현재 위치(위도: {latitude}, 경도: {longitude})에 있는 여행자에게 맛집을 추천하는 전문가입니다.
다음은 주변에서 찾은 식당 정보입니다:

"""
    
    for i, place in enumerate(places, 1):
        prompt += f"""
식당 {i}: {place['name']}
- 거리: {place['distance']:.2f}km
- 평점: {place.get('rating', '정보 없음')}
- 영업 여부: {'영업 중' if place.get('open_now') else '영업 종료 또는 정보 없음'}
- 유형: {', '.join(place.get('types', ['정보 없음']))}
"""
    
    prompt += """
이 정보를 바탕으로 사용자에게 식당을 추천해주세요. 각 식당의 장점과 특징, 어떤 음식이 맛있을지 설명하고, 
사용자의 위치에서 가까운 순서로 우선 추천해주세요. 한국어로 상세하게 친절한 말투로 대답해주세요.
"""
    return prompt

def process_image_prompt(latitude, longitude, image_path):
    """
    이미지와 GPS 정보를 기반으로 시스템 프롬프트를 생성합니다.
    
    Parameters:
        latitude: 현재 위치의 위도
        longitude: 현재 위치의 경도
        image_path: 이미지 파일 경로
        
    Returns:
        시스템 프롬프트 문자열
    """
    return f"""
당신은 이미지를 분석하고 설명하는 전문가입니다. 
제공된 이미지를 자세하게 분석하고, 이미지의 내용, 특징, 가능한 경우 역사적/문화적 배경을 설명해주세요.

현재 이미지는 GPS 위치(위도: {latitude}, 경도: {longitude})에서 촬영되었습니다.
이 위치 정보를 활용하여 이미지에 나타난 장소, 건물, 명소 등을 더 정확하게 식별해보세요.

만약 이미지의 내용이 불분명하거나 더 자세한 정보가 필요한 경우, 'find_nearby_places' 함수를 사용하여 
현재 위치 주변의 유명한 장소들을 찾아볼 수 있습니다.

예를 들어, "이 지역에 있는 유명한 박물관을 찾아줘"라고 요청하면 해당 지역의 박물관 정보를 얻을 수 있습니다.

한국어로 상세하게 친절한 말투로 대답해주세요.
"""

@app.route('/upload', methods=['POST'])
def receive_data():
    """위치 정보, 이미지, 음성 등의 데이터를 받아 처리하는 API 엔드포인트
    
    Returns:
        JSON 응답 및 HTTP 상태 코드
    """
    try:
        # API Key 검증
        key = request.headers.get("X-API-Key")
        if key != API_KEY:
            return jsonify({"error": "Invalid API Key"}), 403

        # 🌍 GPS 데이터 받기 (form-data의 text 필드에 key=value 형태로 전달)
        gps_data = request.form.get("text", "")
        gps_lines = gps_data.split("\n")
        gps_dict = {}
        
        for line in gps_lines:
            if "=" in line:
                k, v = line.split("=", 1)
                gps_dict[k.strip()] = v.strip()
                
        latitude = gps_dict.get("latitude", "")
        longitude = gps_dict.get("longitude", "")
        street = gps_dict.get("street", "")
        city = gps_dict.get("city", "")

        # 업로드 폴더가 존재하는지 확인
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # 📸 이미지 파일 처리 (없으면 None)
        image = request.files.get("image")
        image_filename = None
        
        if image and image.filename:
            # 고유한 이미지 파일 이름 생성
            new_image_filename = generate_unique_filename("image", image.filename)
            image_filename = os.path.join(UPLOAD_FOLDER, new_image_filename)
            image.save(image_filename)
            logging.debug(f"이미지 저장: {image_filename} (원본: {image.filename})")

        # 🎤 음성 파일 처리 (없으면 None)
        audio = request.files.get("voice")
        audio_filename = None
        
        if audio and audio.filename:
            # 고유한 오디오 파일 이름 생성
            new_audio_filename = generate_unique_filename("audio", audio.filename)
            audio_filename = os.path.join(UPLOAD_FOLDER, new_audio_filename)
            audio.save(audio_filename)
            logging.debug(f"음성 저장: {audio_filename} (원본: {audio.filename})")

        # 💬 추가 메시지 처리
        extra_message = request.form.get("message", "")
        
        # LLM 및 처리 결과를 저장할 변수
        llm_response = None
        response_audio = None
        
        # 1. GPS만 있는 경우 - 주변 맛집 추천 (function call 사용)
        if latitude and longitude and not image_filename and not audio_filename and not extra_message:
            logging.info("케이스 1: GPS 정보만 있는 경우 - 주변 맛집 추천")
            
            # 주변 맛집 검색
            lat1, lng1 = float(latitude), float(longitude)
            nearby_places = maps_search_nearby(lat1, lng1, radius=500, k=5, keyword='restaurant')
            
            # 시스템 프롬프트 생성
            system_prompt = f"""
당신은 현재 위치(위도: {latitude}, 경도: {longitude})에 있는 여행자에게 맛집을 추천하는 전문가입니다.
주변에서 찾은 맛집 정보를 바탕으로 상세한 설명과 추천을 제공해주세요.
식당의 특징, 음식 종류, 그리고 왜 추천하는지 자세하게 설명해주세요.
한국어로 상세하게 친절한 말투로 대답해주세요.

주변 맛집 정보:
"""
            
            # 주변 맛집 정보를 프롬프트에 추가
            for i, place in enumerate(nearby_places, 1):
                system_prompt += f"""
맛집 {i}: {place['name']}
- 거리: {place['distance']:.2f}km
- 평점: {place.get('rating', '정보 없음')}
- 영업 여부: {'영업 중' if place.get('open_now') else '영업 종료 또는 정보 없음'}
- 유형: {', '.join(place.get('types', ['정보 없음']))}
"""
            
            # LLM 요청 - 실제 검색 결과를 바탕으로 추천 생성
            llm_response = gemini_bot(
                system_prompt=system_prompt,
                user_input=f"현재 위치(위도 {latitude}, 경도 {longitude})에서 가까운 맛집을 추천해주세요. 각 식당의 특징과 추천 이유를 상세히 설명해주세요."
            )
        
        # 2. 이미지 + GPS - 이미지 분석 (더 상세한 설명 추가)
        elif latitude and longitude and image_filename and not audio_filename and not extra_message:
            logging.info("케이스 2: 이미지와 GPS 정보만 있는 경우 - 상세한 이미지 분석")
            
            # 시스템 프롬프트 생성 - 더 상세한 설명 요청
            system_prompt = f"""
당신은 이미지를 분석하고 풍부하게 설명하는 전문가입니다. 
제공된 이미지를 자세하게 분석하고:

1. 이미지의 주요 내용과 특징을 상세히 설명해주세요.
2. 이미지에 있는 역사적/문화적 장소나 물체라면, 그 역사와 배경 정보를 최대한 풍부하게 설명해주세요.
3. 관련된 흥미로운 사실이나 트리비아, 역사적 이야기를 포함해주세요.
4. 여행자에게 도움이 될 만한 추가 정보를 제공해주세요.

현재 이미지는 GPS 위치(위도: {latitude}, 경도: {longitude})에서 촬영되었습니다.
이 위치 정보를 활용하여 더 정확한 정보를 제공해보세요.

한국어로 여행 가이드처럼 상세하고 재미있게 설명해주세요.
"""
            
            # LLM 요청 - 상세 분석 요청
            llm_response = gemini_bot(
                system_prompt=system_prompt,
                user_input="이 이미지에 대해 최대한 상세히 설명해주세요. 역사적 배경, 문화적 의미, 재미있는 이야기 등을 모두 포함해서 여행 가이드처럼 설명해주세요.",
                image_path=image_filename
            )
            
            # 설명이 부족하다고 판단되면 주변 장소 정보 추가
            if "정보가 부족" in llm_response or "확실하지 않" in llm_response or "알 수 없" in llm_response:
                try:
                    lat1, lng1 = float(latitude), float(longitude)
                    nearby_places = maps_search_nearby(lat1, lng1, radius=1000, k=3)
                    
                    additional_info = "\n\n주변에 다음과 같은 유명한 장소들이 있습니다:\n"
                    for i, place in enumerate(nearby_places, 1):
                        additional_info += f"{i}. {place['name']} (거리: {place['distance']:.2f}km)\n"
                    
                    llm_response += additional_info
                except Exception as e:
                    logging.error(f"주변 장소 정보 추가 중 오류: {e}")
        
        # 3. 이미지 + 메시지 + GPS - 메시지를 프롬프트로 사용
        elif latitude and longitude and image_filename and not audio_filename and extra_message:
            logging.info("케이스 3: 이미지 + 메시지 + GPS - 메시지를 그대로 프롬프트로 사용")
            
            # 기본 시스템 프롬프트
            system_prompt = f"""
당신은 여행자를 위한 AI 어시스턴트입니다. 이미지와 함께 전달된 질문이나 요청에 상세하게 답변해주세요.
현재 위치 정보(위도: {latitude}, 경도: {longitude})를 참고하여 더 정확한 응답을 제공할 수 있습니다.
사용자의 요청을 정확히 이해하고 충실하게 수행해주세요.
한국어로 상세하게 친절한 말투로 대답해주세요.
"""
            
            # 사용자 메시지를 그대로 프롬프트로 사용
            llm_response = gemini_bot(
                system_prompt=system_prompt,
                user_input=extra_message,
                image_path=image_filename
            )
        
        # 4. 이미지 + 오디오 + GPS - 오디오 변환 후 처리
        elif latitude and longitude and image_filename and audio_filename and not extra_message:
            logging.info("케이스 4: 이미지 + 오디오 + GPS - 오디오 변환 후 처리")
            
            # 오디오 파일 확장자 확인 및 변환
            audio_ext = os.path.splitext(audio_filename)[1].lower()
            mp3_audio_path = audio_filename
            
            # m4a 파일이면 mp3로 변환
            if audio_ext == '.m4a':
                mp3_audio_path = convert_m4a_to_mp3_moviepy(audio_filename)
            
            # 음성을 텍스트로 변환 (medium 모델 사용)
            transcribed_text = transcribe_audio(mp3_audio_path, "medium")
            
            if transcribed_text and isinstance(transcribed_text, str):
                logging.info(f"오디오 텍스트 변환 결과: {transcribed_text}")
                
                # 시스템 프롬프트 생성
                system_prompt = f"""
당신은 여행자를 위한 AI 어시스턴트입니다. 이미지와 음성 메시지를 함께 받았습니다.
현재 위치 정보(위도: {latitude}, 경도: {longitude})를 참고할 수 있습니다.
음성 메시지의 요청을 정확히 이해하고 충실하게 수행해주세요.
한국어로 상세하게 친절한 말투로 대답해주세요.
"""
                
                # LLM 요청 - 사용자 음성 메시지를 그대로 처리
                llm_response = gemini_bot(
                    system_prompt=system_prompt,
                    user_input=transcribed_text,
                    image_path=image_filename
                )
                
                # 응답을 음성으로 변환
                response_audio_filename = os.path.join(RESPONSE_FOLDER, f"response_{int(time.time())}.mp3")
                synthesize_speech(llm_response, response_audio_filename)
                response_audio = response_audio_filename
            else:
                llm_response = "음성 메시지를 처리할 수 없습니다. 텍스트로 변환 중 오류가 발생했습니다."
        
        # 5-1. 메시지 + GPS - 메시지를 프롬프트로 사용
        elif latitude and longitude and not image_filename and not audio_filename and extra_message:
            logging.info("케이스 5-1: 메시지 + GPS - 메시지를 그대로 프롬프트로 사용")
            
            # 시스템 프롬프트 생성
            system_prompt = f"""
당신은 여행자를 위한 AI 어시스턴트입니다.
현재 위치 정보(위도: {latitude}, 경도: {longitude})를 참고할 수 있습니다.
사용자의 메시지를 정확히 이해하고 요청대로 충실하게 수행해주세요.
한국어로 상세하게 친절한 말투로 대답해주세요.
"""
            
            # LLM 요청 - 사용자 메시지를 그대로 처리
            llm_response = gemini_bot(
                system_prompt=system_prompt,
                user_input=extra_message
            )
        
        # 5-2. 오디오 + GPS - 오디오 변환 후 처리
        elif latitude and longitude and not image_filename and audio_filename and not extra_message:
            logging.info("케이스 5-2: 오디오 + GPS - 오디오 변환 후 처리")
            
            # 오디오 파일 확장자 확인 및 변환
            audio_ext = os.path.splitext(audio_filename)[1].lower()
            mp3_audio_path = audio_filename
            
            # m4a 파일이면 mp3로 변환
            if audio_ext == '.m4a':
                mp3_audio_path = convert_m4a_to_mp3_moviepy(audio_filename)
            
            # 음성을 텍스트로 변환
            transcribed_text = transcribe_audio(mp3_audio_path, "medium")
            
            if transcribed_text and isinstance(transcribed_text, str):
                logging.info(f"오디오 텍스트 변환 결과: {transcribed_text}")
                
                # 시스템 프롬프트 생성
                system_prompt = f"""
당신은 여행자를 위한 AI 어시스턴트입니다.
현재 위치 정보(위도: {latitude}, 경도: {longitude})를 참고할 수 있습니다.
사용자의 음성 메시지를 정확히 이해하고 요청대로 충실하게 수행해주세요.
한국어로 상세하게 친절한 말투로 대답해주세요.
"""
                
                # LLM 요청 - 사용자 음성 메시지를 그대로 처리
                llm_response = gemini_bot(
                    system_prompt=system_prompt,
                    user_input=transcribed_text
                )
                
                # 응답을 음성으로 변환
                response_audio_filename = os.path.join(RESPONSE_FOLDER, f"response_{int(time.time())}.mp3")
                synthesize_speech(llm_response, response_audio_filename)
                response_audio = response_audio_filename
            else:
                llm_response = "음성 메시지를 처리할 수 없습니다. 텍스트로 변환 중 오류가 발생했습니다."
                
        # 기타 다른 케이스들 - 기본 처리
        else:
            logging.info("기타 케이스: 기본 처리")
            # 디스코드로 전송할 기본 메시지 생성
            extra_message_content = f"GPS: {latitude}, {longitude}"
            if street or city:
                extra_message_content += f", 주소: {street}, {city}"
            
            if extra_message:
                extra_message_content += f"\n\n사용자 메시지: {extra_message}"
            
            # 추가 메시지가 없으면 기본 LLM 응답 생성
            if not llm_response:
                llm_response = "제공된 정보를 처리했습니다."

        # 처리 결과 및 최종 메시지 정리
        response_message = extra_message if extra_message else "처리된 데이터"
        
        if llm_response:
            response_message = llm_response
            
        # 디스코드로 전송 (비동기) - 맛집 정보는 표시하지 않음
        future = asyncio.run_coroutine_threadsafe(
            send_location_to_discord(
                latitude, longitude, street, city,
                extra_message=response_message,
                image_path=image_filename,
                audio_path=response_audio if response_audio else audio_filename,
                show_places=False  # 주변 장소 정보 표시하지 않음
            ),
            bot.loop
        )
        
        try:
            future.result(timeout=30)
        except concurrent.futures.TimeoutError:
            logging.error("디스코드 메시지 전송 시간 초과")
        except Exception as e:
            logging.error(f"디스코드 전송 중 오류: {e}")

        return jsonify({
            "status": "success",
            "filename": image_filename,
            "audio_filename": audio_filename,
            "response_audio": response_audio,
            "message": extra_message,
            "llm_response": llm_response,
            "latitude": latitude,
            "longitude": longitude,
            "street": street,
            "city": city
        }), 200

    except Exception as e:
        logging.exception("데이터 처리 중 에러:")
        return jsonify({"error": str(e)}), 500