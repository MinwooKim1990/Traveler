# %%
import os
import re
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
from utils.audio_convert import convert_m4a_to_mp3_moviepy
from utils.whisper_gen import transcribe_audio, synthesize_text
from utils import search_nearby_places as maps_search_nearby
from utils.image_resize import resize_image
from utils.new_utils import get_local_time_by_gps, get_search_results, generate_content_with_history, generate_unique_filename
    
# 응답 저장 폴더 생성
os.makedirs(RESPONSE_FOLDER, exist_ok=True)

app = Flask(__name__)

def System_Prompt(latitude, longitude, city, street, now_time, selection):
    """
    selection: 1 -> GPS only
    selection: 2 -> Image + GPS
    selection: 3 -> Image + Message + GPS
    selection: 4 -> Message + GPS
    """
    user_preference = """너무 매운것은 못먹고, 치즈가 많은 피자를 좋아하며 다이어트를 생각해서 야채를 먼저 먹는걸 좋아함. 
    육류도 좋아하며 해산물 및 회 또한 좋아하는 편이고 너무 야채만 많은 음식은 별로 좋아하지 않고 냄새가 많이 나는 음식도 별로 좋아하지 않음."""

    if selection == 1:
        return f"""
# Restaurant Recommendation Expert System

## Primary Role
You are a specialized assistant that recommends restaurants to travelers based on their current location and time.

## Core Responsibilities
- Analyze user's current location (latitude/longitude) and time
- Write the Reason for the recommendation as detail as possible but not too long.
- Consider user preferences: `{user_preference}`
- Provide detailed restaurant recommendations in Korean language only
- Use a friendly, detailed communication style
- Write distance information in numeric value in km unit. Provide distance information from function is meter unit.

## Recommendation Process (Chain of Thought)
1. **Gather Location Data**: First, Check the user's current location and nearby area from the user's prompt
2. **Search Nearby Options**: Use function call to retrieve 20 nearby restaurants
   ```
   Function parameters:
   - latitude: [Use provided user latitude]
   - longitude: [Use provided user longitude]
   - keyword: "restaurant" (default, adjust based on preferences)
   ```
3. **Filter Results**: From the 20 returned options, select 5 best matches based on:
   - Proximity to user's location
   - Alignment with stated preferences
   - Variety of cuisine types
   - Current operational status (based on time)

4. **Format Recommendations**: For each selected restaurant, provide:
   - Name and cuisine type
   - Key distinguishing features
   - Specific dish recommendations
   - Reason for recommendation
   - Approximate distance from current location

## Output Requirements
- **MUST Respond exclusively in Korean language**
- **MUST Response with only your outputs in Markdown format Not Json style**
- Use polite, friendly tone
- Provide comprehensive details for each recommendation
- Present 5 curated options from the function search results

## Note
The function search results will be listed in order of proximity to the user's current location. Street and city information is provided as user prompt.

"""  
    elif selection == 2:
        return """
### **Objective**
Analyze an image and determine if it is an **artwork, museum artifact, general photo, or text/document in a foreign language**.  
Provide detailed **historical and artistic insights** for artworks, engage in a **friendly conversation** for general photos, and offer **translation and analysis** for foreign language text.

---

### **Step 1: Identify Image Type**
- **Is it an artwork or museum artifact?** → If yes, proceed to `Step 2: Artwork Analysis`
- **Is it a general photo (landscape, people, objects, pets, etc.)?** → If yes, proceed to `Step 3: Friendly Conversation`
- **Does it contain text in a foreign language (signs, menus, documents)?** → If yes, proceed to `Step 4: Foreign Text Analysis`

---

### **Step 2: Artwork or Museum Artifact Analysis**
> Provide an in-depth analysis covering these essential elements:

#### **1. Basic Information**
- **Title:** [Artwork Title]
- **Artist:** [Artist Name]
- **Year Created:** [Creation Year]
- **Location:** [Museum/Gallery Name]
- **Medium & Technique:** [Materials Used]
- **Dimensions:** [Size in cm/inches]

#### **2. Historical Context**
- What was happening during the time this artwork was created?
- How does the artist's life connect to the work?

#### **3. Symbolism & Meaning**
- What are the key themes and hidden messages in the artwork?
- What emotions or ideas is the artist trying to convey?

#### **4. Artistic Techniques & Style**
- Which artistic movement or style does it belong to?
- What unique methods were used in composition, color, and texture?

#### **5. Trivia & Interesting Facts**
- Are there any famous controversies, thefts, or mysteries about this piece?
- Has this artwork been referenced in popular culture?

#### **6. Influence & Legacy**
- How has this artwork influenced other artists or movements?
- How is it perceived in modern times?

---

### **Step 3: Friendly Conversation for General Photos**
> If the image is NOT an artwork or museum artifact, engage with the user in a friendly and interactive manner.
Use the user's current location and time from user prompt to make the conversation more engaging.

#### ** Casual & Conversational Style**
- Identify key elements in the image (e.g., people, pets, objects, nature).
- Make observations in a natural, engaging way.
- Ask open-ended questions to involve the user in a dialogue.

#### ** Example Approaches**
- **Pets:** "Aww, what a cute dog! What's their name? "
- **Food:** "That looks delicious! Did you make it yourself or is it from a restaurant?"
- **Nature:** "Such a peaceful view! Where was this taken?"
- **Selfies:** "Great shot! What was the occasion?"

---

### **Step 4: Foreign Text Analysis**
> If the image contains text in a non-Korean language (signs, menus, documents, etc.), provide a comprehensive analysis:

#### **1. Text Identification & Translation**
- Identify the language of the text
- Transcribe the original text
- Provide a complete Korean translation

#### **2. Content Analysis**
- For menus: Explain dishes, ingredients, pricing, and specialties
- For signs: Explain the meaning, context, and any cultural significance
- For documents: Summarize the key information and purpose

#### **3. Cultural Context**
- Provide relevant cultural background information
- Explain any idioms, references, or cultural nuances
- Connect the text to local customs or traditions

#### **4. Practical Information**
- For menus: Recommend dishes or explain unfamiliar ingredients
- For signs: Explain directions, warnings, or instructions
- For documents: Highlight important details the user should know

---

### **Adaptive Style Guidelines**
- **If it's an artwork:** Be **informative, structured, and insightful**.
- **If it's a general photo:** Be **casual, warm, and conversational**.
- **If it's foreign text:** Be **helpful, detailed, and educational**.

### **Output Requirements**
- **MUST Respond with the same language as the user's input**
- **MUST Response with only your outputs in Markdown format Not Json style**
"""
    elif selection == 3:
        return f"""
# Multimodal Assistant

## Primary Role
You are a specialized multimodal assistant with functions based on user's current location and time.

## Core Responsibilities
- Be aware of user's current location (latitude/longitude) and time Not always use but you can use whenever you needed.
- Use a friendly, detailed communication style
- Analyze an image and determine if it is an **artwork, museum artifact, general photo, or text/document in a foreign language**.  
- Provide detailed **historical and artistic insights** for artworks, engage in a **friendly conversation** for general photos, and offer **translation and analysis** for foreign language text.
- **Following these responsibilities if user does not provide any prompt but if user provide prompt, you must follow user's prompt based on these instructions.**

### **Step 1: Identify Image Type**
- **Is it an artwork or museum artifact?** → If yes, proceed to `Step 2: Artwork Analysis`
- **Is it a general photo (landscape, people, objects, pets, etc.)?** → If yes, proceed to `Step 3: Friendly Conversation`
- **Does it contain text in a foreign language (signs, menus, documents)?** → If yes, proceed to `Step 4: Foreign Text Analysis`
---

### **Step 2: Artwork or Museum Artifact Analysis**
> Provide an in-depth analysis covering these essential elements:

#### **1. Basic Information**
- **Title:** [Artwork Title]
- **Artist:** [Artist Name]
- **Year Created:** [Creation Year]
- **Location:** [Museum/Gallery Name]
- **Medium & Technique:** [Materials Used]
- **Dimensions:** [Size in cm/inches]

#### **2. Historical Context**
- What was happening during the time this artwork was created?
- How does the artist's life connect to the work?

#### **3. Symbolism & Meaning**
- What are the key themes and hidden messages in the artwork?
- What emotions or ideas is the artist trying to convey?

#### **4. Artistic Techniques & Style**
- Which artistic movement or style does it belong to?
- What unique methods were used in composition, color, and texture?

#### **5. Trivia & Interesting Facts**
- Are there any famous controversies, thefts, or mysteries about this piece?
- Has this artwork been referenced in popular culture?

#### **6. Influence & Legacy**
- How has this artwork influenced other artists or movements?
- How is it perceived in modern times?

---

### **Step 3: Friendly Conversation for General Photos**
> If the image is NOT an artwork or museum artifact, engage with the user in a friendly and interactive manner.
Use the user's current location and time from user prompt to make the conversation more engaging.

#### ** Casual & Conversational Style**
- Identify key elements in the image (e.g., people, pets, objects, nature).
- Make observations in a natural, engaging way.
- Ask open-ended questions to involve the user in a dialogue.

#### ** Example Approaches**
- **Pets:** "Aww, what a cute dog! What's their name? "
- **Food:** "That looks delicious! Did you make it yourself or is it from a restaurant?"
- **Nature:** "Such a peaceful view! Where was this taken?"
- **Selfies:** "Great shot! What was the occasion?"

---

### **Step 4: Foreign Text Analysis**
> If the image contains text in a non-user prompt language (signs, menus, documents, etc.), provide a comprehensive analysis:

#### **1. Text Identification & Translation**
- Identify the language of the text
- Transcribe the original text
- Provide a complete translation in user prompt language
- Show original text in parentheses next to translation to understand foreign text in the image well.

#### **2. Content Analysis**
- For menus: Explain dishes, ingredients, pricing, and specialties
- For signs: Explain the meaning, context, and any cultural significance
- For documents: Summarize the key information and purpose

#### **3. Cultural Context**
- Provide relevant cultural background information
- Explain any idioms, references, or cultural nuances
- Connect the text to local customs or traditions

#### **4. Practical Information**
- For menus: Recommend dishes or explain unfamiliar ingredients
- For signs: Explain directions, warnings, or instructions
- For documents: Highlight important details the user should know

---

## Location and Time Parameters
- Use the provided `{latitude}`, `{longitude}`, `{city}`, `{street}`, and `{now_time}` as the basis for recommendations
- These parameters represent the user's current context for providing relevant suggestions

## Response Guidelines
- **MUST Respond to prompts in languages in their respective language from user prompt**
- Provide friendly, appropriately-sized responses based on the user's query
- Adjust detail level based on the nature of the user's request

## Using Internet Search Function
1. **Gather Data**: Determine when you need information you don't know or need to be updated.
2. **Use get_search_results function**: Use function call to retrieve several search results by DuckDuckGo

   Function parameters:
   - query: YOUR QUERY
   ```
3. **Filter Results**: 
   - Process search results by analyzing the returned titles and snippets
   - Summarize the information in the user's input language, even if search results are in different languages
   - Include relevant citations as references at the end of your response
   - Translate if needed - ensure all information is presented in the user's preferred language regardless of the language of search results


## Using Nearby Search Function
1. **Gather Data**: Determine when you need information you don't know or need to be updated.
2. **Use maps_search_nearby function**: Use function call to retrieve several search results by Google Maps
   ```
   Function parameters:
   - latitude: user's current latitude
   - longitude: user's current longitude
   - keyword: Your Keyword (eg. hotel, restaurant, park, etc.)
   ```
3. **Filter Results**: 
   - Process search results by analyzing the returned titles and snippets
   - Summarize the information in the user's input language, even if search results are in different languages
   - Present 5 best matches to the user based on distance, rate, name and explain why you recommend them
   - Translate if needed - ensure all information is presented in the user's preferred language regardless of the language of search results

## Recommendation Format
For each selected restaurant, provide:
- Use Natural language to user whether you use function or not
- If you use function, provide more structured and detailed information about the search results

## Output Requirements
- Match response language to input language
- Use polite, friendly tone
- Write in Markdown format for better readability
- Include references to search results when applicable

"""
    elif selection == 4:
        return f"""
# Multimodal Assistant

## Primary Role
You are a specialized assistant based on user's current location and time.

## Core Responsibilities
- Be aware of user's current location (latitude/longitude) and time
- Use a friendly, detailed communication style

## Location and Time Parameters
- Use the provided `{latitude}`, `{longitude}`, `{city}`, `{street}`, and `{now_time}` as the basis for recommendations
- These parameters represent the user's current context for providing relevant suggestions

## Response Guidelines
- **MUST Respond to prompts in languages in their respective language from user prompt**
- Provide friendly, appropriately-sized responses based on the user's query
- Adjust detail level based on the nature of the user's request

## Using Internet Search Function
1. **Gather Data**: Determine when you need information you don't know or need to be updated.
2. **Use get_search_results function**: Use function call to retrieve several search results by DuckDuckGo

   Function parameters:
   - query: YOUR QUERY
   ```
3. **Filter Results**: 
   - Process search results by analyzing the returned titles and snippets
   - Summarize the information in the user's input language, even if search results are in different languages
   - Include relevant citations as references at the end of your response
   - Translate if needed - ensure all information is presented in the user's preferred language regardless of the language of search results


## Using Nearby Search Function
1. **Gather Data**: Determine when you need information you don't know or need to be updated.
2. **Use maps_search_nearby function**: Use function call to retrieve several search results by Google Maps
   ```
   Function parameters:
   - latitude: user's current latitude
   - longitude: user's current longitude
   - keyword: Your Keyword (eg. hotel, restaurant, park, etc.)
   ```
3. **Filter Results**: 
   - Process search results by analyzing the returned titles and snippets
   - Summarize the information in the user's input language, even if search results are in different languages
   - Present 5 best matches to the user based on distance, rate, name and explain why you recommend them
   - Translate if needed - ensure all information is presented in the user's preferred language regardless of the language of search results

## Recommendation Format
For each selected restaurant, provide:
- Use Natural language to user whether you use function or not
- If you use function, provide more structured and detailed information about the search results

## Output Requirements
- Match response language to input language
- Use polite, friendly tone
- Write in Markdown format for better readability
- Include references to search results when applicable

"""
    else:
        return "You are Helpful Assistant"


@app.route('/upload', methods=['POST'])
def receive_data():
    """위치 정보, 이미지, 음성 등의 데이터를 받아 처리하는 API 엔드포인트
    
    Returns:
        JSON 응답 및 HTTP 상태 코드
    """
    try:
        discord_sent = False  # Discord 메시지 전송 여부 플래그
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
        
        # =====================================================================================
        # 1. GPS만 있는 경우 - 주변 맛집 추천 (function call 사용)
        # =====================================================================================
        if latitude and longitude and not image_filename and not audio_filename and not extra_message:
            logging.info("케이스 1: GPS 정보만 있는 경우 - 주변 맛집 추천")
            executor = concurrent.futures.ThreadPoolExecutor()
            now_time = get_local_time_by_gps(latitude, longitude)
            # 시스템 프롬프트 생성
            system_prompt = System_Prompt(latitude, longitude, city, street, now_time, 1)
            restaurant_history = []
            # LLM 요청 - 실제 검색 결과를 바탕으로 추천 생성
            llm_response = generate_content_with_history(
                system_prompt=system_prompt,
                new_message=f"현재 시간 {now_time}, 현재 위치는 위치(위도 {latitude}, 경도 {longitude}) 부가적인 현재 도시와 거리는 {city}, {street}.",
                function_list=[maps_search_nearby],
                image_path=None,
                k=7,
                history=restaurant_history
            )
            llm_response = dict(list(llm_response)[1])['content']
            print(llm_response)

            # Discord 메시지 전송: 맛집 텍스트(분석 결과)를 포함하여 한 번에 전송
            future_msg = executor.submit(lambda: asyncio.run_coroutine_threadsafe(
                send_location_to_discord(
                    latitude, longitude, street, city,
                    extra_message=llm_response,
                    image_path=None,
                    audio_path=None,
                    show_places=False,
                    message_include=True
                ), bot.loop
            ).result())
            try:
                future_msg.result(timeout=30)
            except Exception as e:
                logging.error(f"디스코드 메시지 전송 실패 (맛집 텍스트): {e}")

            executor.shutdown(wait=True)
            discord_sent = True
            return jsonify({'status': 'success'})
        
        # =====================================================================================
        # 2. 이미지 + GPS - 이미지 리사이즈와 분석 결과를 이용하여 Discord 메시지 전송 후 음성 전송
        # =====================================================================================
        elif latitude and longitude and image_filename and not audio_filename and not extra_message:
            logging.info("케이스 2: 이미지와 GPS 정보가 있는 경우 - 이미지 리사이즈와 분석 결과를 이용하여 Discord 메시지 전송 후 음성 전송")
            now_time = get_local_time_by_gps(latitude, longitude)
            # 시스템 프롬프트 생성
            system_prompt = System_Prompt(latitude, longitude, city, street, now_time, 2)
            
            executor = concurrent.futures.ThreadPoolExecutor()

            # 이미지 용량이 8MB 이상일 때만 리사이즈를 수행합니다.
            if os.path.getsize(image_filename) >= 7.5 * 1024 * 1024:
                future_resize = executor.submit(resize_image, image_filename, 7.5)
                resized_image_filename = future_resize.result()
            else:
                resized_image_filename = image_filename

            # 이미지 먼저 전송
            if resized_image_filename:
                first_image = executor.submit(lambda: asyncio.run_coroutine_threadsafe(
                    send_location_to_discord(
                        latitude, longitude, street, city,
                        extra_message="입력 이미지",
                        image_path=resized_image_filename,
                        audio_path=None,
                        show_places=False,
                        message_include=False
                    ), bot.loop
                ).result())
                try:
                    first_image.result(timeout=30)
                except Exception as e:
                    logging.error(f"디스코드 메시지 전송 실패 (이미지): {e}")
            else:
                logging.error("이미지 전송 실패")

            image_without_message_history = []
            # Gemini 분석 호출
            llm_response = generate_content_with_history(
                system_prompt=system_prompt,
                new_message=f"현재 시간 {now_time}, 현재 위치는 위치(위도 {latitude}, 경도 {longitude}) 부가적인 현재 도시와 거리는 {city}, {street}.",
                image_path=resized_image_filename,
                k=5,
                function_list=None,
                history=image_without_message_history
            )
            llm_response = dict(list(llm_response)[1])['content']

            # Discord 메시지 전송: 텍스트(분석 결과)를 포함하여 한 번에 전송
            future_msg = executor.submit(lambda: asyncio.run_coroutine_threadsafe(
                send_location_to_discord(
                    latitude, longitude, street, city,
                    extra_message=llm_response,
                    image_path=None,
                    audio_path=None,
                    show_places=False,
                    message_include=True
                ), bot.loop
            ).result())
            try:
                future_msg.result(timeout=30)
            except Exception as e:
                logging.error(f"디스코드 메시지 전송 실패 (텍스트): {e}")

            # TTS: 음성 합성
            import re
            audio_text = re.sub(r'[*_`~#]', '', llm_response)
            response_audio_filename = os.path.join(RESPONSE_FOLDER, f"response_{int(time.time())}.mp3")
            tts_success = synthesize_text(audio_text, response_audio_filename, gender="female", speed=1.1)
            if tts_success:
                future_audio = executor.submit(lambda: asyncio.run_coroutine_threadsafe(
                    send_location_to_discord(
                        latitude, longitude, street, city,
                        extra_message="음성 응답",
                        image_path=None,
                        audio_path=response_audio_filename,
                        show_places=False,
                        message_include=False
                    ), bot.loop
                ).result())
                try:
                    future_audio.result(timeout=30)
                except Exception as e:
                    logging.error(f"디스코드 메시지 전송 실패 (음성): {e}")
            else:
                logging.error("TTS 음성 합성 실패")

            executor.shutdown(wait=True)
            discord_sent = True
            return jsonify({'status': 'success'})
        
        # =====================================================================================
        # 3. 이미지 + 메시지 + GPS - 메시지를 프롬프트로 사용
        # =====================================================================================
        elif latitude and longitude and image_filename and not audio_filename and extra_message:
            logging.info("케이스 3: 이미지 + 메시지 + GPS - 메시지를 그대로 프롬프트로 사용")
            now_time = get_local_time_by_gps(latitude, longitude)
            # 기본 시스템 프롬프트
            system_prompt = System_Prompt(latitude, longitude, city, street, now_time, 3)
            executor = concurrent.futures.ThreadPoolExecutor()
            # 이미지 용량이 8MB 이상일 때만 리사이즈를 수행합니다.
            if os.path.getsize(image_filename) >= 7.5 * 1024 * 1024:
                future_resize = executor.submit(resize_image, image_filename, 7.5)
                resized_image_filename = future_resize.result()
            else:
                resized_image_filename = image_filename

            # 이미지 먼저 전송
            if resized_image_filename:
                first_image = executor.submit(lambda: asyncio.run_coroutine_threadsafe(
                    send_location_to_discord(
                        latitude, longitude, street, city,
                        extra_message="입력 이미지",
                        image_path=resized_image_filename,
                        audio_path=None,
                        show_places=False,
                        message_include=False
                    ), bot.loop
                ).result())
                try:
                    first_image.result(timeout=30)
                except Exception as e:
                    logging.error(f"디스코드 메시지 전송 실패 (이미지): {e}")
            else:
                logging.error("이미지 전송 실패")

            image_message_gps_history = []
            # 사용자 메시지를 그대로 프롬프트로 사용
            llm_response = generate_content_with_history(
                system_prompt=system_prompt,
                new_message=extra_message,
                image_path=resized_image_filename,
                function_list=[get_search_results]
            )
            llm_response = dict(list(llm_response)[1])['content']

            # Discord 메시지 전송: 텍스트(분석 결과)를 포함하여 한 번에 전송
            future_msg = executor.submit(lambda: asyncio.run_coroutine_threadsafe(
                send_location_to_discord(
                    latitude, longitude, street, city,
                    extra_message=llm_response,
                    image_path=None,
                    audio_path=None,
                    show_places=False,
                    message_include=True
                ), bot.loop
            ).result())
            try:
                future_msg.result(timeout=30)
            except Exception as e:
                logging.error(f"디스코드 메시지 전송 실패 (텍스트): {e}")

            executor.shutdown(wait=True)
            discord_sent = True
            return jsonify({'status': 'success'})

        # =====================================================================================
        # 4. 이미지 + 오디오 + GPS - 오디오 변환 후 처리
        # =====================================================================================
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
                now_time = get_local_time_by_gps(latitude, longitude)
                
                # 시스템 프롬프트 생성
                system_prompt = System_Prompt(latitude, longitude, city, street, now_time, 3)
                executor = concurrent.futures.ThreadPoolExecutor()
                # 이미지 용량이 8MB 이상일 때만 리사이즈를 수행합니다.
                if os.path.getsize(image_filename) >= 7.5 * 1024 * 1024:
                    future_resize = executor.submit(resize_image, image_filename, 7.5)
                    resized_image_filename = future_resize.result()
                else:
                    resized_image_filename = image_filename
                
                # 이미지 먼저 전송
                if resized_image_filename:
                    first_image = executor.submit(lambda: asyncio.run_coroutine_threadsafe(
                        send_location_to_discord(
                            latitude, longitude, street, city,
                            extra_message="입력 이미지",
                            image_path=resized_image_filename,
                            audio_path=None,
                            show_places=False,
                            message_include=False
                        ), bot.loop
                    ).result())
                    try:
                        first_image.result(timeout=30)
                    except Exception as e:
                        logging.error(f"디스코드 메시지 전송 실패 (이미지): {e}")
                else:
                    logging.error("이미지 전송 실패")

                # LLM 요청 - 사용자 음성 메시지를 그대로 처리
                llm_response = generate_content_with_history(
                    system_prompt=system_prompt,
                    new_message=transcribed_text,
                    image_path=resized_image_filename,
                    function_list=[get_search_results],
                )
                llm_response = dict(list(llm_response)[1])['content']
            else:
                llm_response = "음성 메시지를 처리할 수 없습니다. 텍스트로 변환 중 오류가 발생했습니다."
            
            # Discord 메시지 전송: 텍스트(분석 결과)를 포함하여 한 번에 전송
            future_msg = executor.submit(lambda: asyncio.run_coroutine_threadsafe(
                send_location_to_discord(
                    latitude, longitude, street, city,
                    extra_message=llm_response,
                    image_path=None,
                    audio_path=None,
                    show_places=False,
                    message_include=True
                ), bot.loop
            ).result())
            try:
                future_msg.result(timeout=30)
            except Exception as e:
                logging.error(f"디스코드 메시지 전송 실패 (텍스트): {e}")

            executor.shutdown(wait=True)
            discord_sent = True
            return jsonify({'status': 'success'})

        # =====================================================================================
        # 5-1. 메시지 + GPS - 메시지를 프롬프트로 사용
        # =====================================================================================
        elif latitude and longitude and not image_filename and not audio_filename and extra_message:
            logging.info("케이스 5-1: 메시지 + GPS - 메시지를 그대로 프롬프트로 사용")
            now_time = get_local_time_by_gps(latitude, longitude)
            executor = concurrent.futures.ThreadPoolExecutor()
            # 시스템 프롬프트 생성
            system_prompt = System_Prompt(latitude, longitude, city, street, now_time, 4)
            
            # LLM 요청 - 사용자 메시지를 그대로 처리
            llm_response = generate_content_with_history(
                system_prompt=system_prompt,
                new_message=extra_message,
                function_list=[get_search_results, maps_search_nearby],
                image_path=None
            )
            llm_response = dict(list(llm_response)[1])['content']

            # Discord 메시지 전송: 텍스트(분석 결과)를 포함하여 한 번에 전송
            future_msg = executor.submit(lambda: asyncio.run_coroutine_threadsafe(
                send_location_to_discord(
                    latitude, longitude, street, city,
                    extra_message=llm_response,
                    image_path=None,
                    audio_path=None,
                    show_places=False,
                    message_include=True
                ), bot.loop
            ).result())
            try:
                future_msg.result(timeout=30)
            except Exception as e:
                logging.error(f"디스코드 메시지 전송 실패 (텍스트): {e}")

            executor.shutdown(wait=True)
            discord_sent = True
            return jsonify({'status': 'success'})

        # =====================================================================================
        # 5-2. 오디오 + GPS - 오디오 변환 후 처리
        # =====================================================================================
        elif latitude and longitude and not image_filename and audio_filename and not extra_message:
            logging.info("케이스 5-2: 오디오 + GPS - 오디오 변환 후 처리")
            executor = concurrent.futures.ThreadPoolExecutor()
            
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
                now_time = get_local_time_by_gps(latitude, longitude)
                
                # 시스템 프롬프트 생성
                system_prompt = System_Prompt(latitude, longitude, city, street, now_time, 4)
                
                # LLM 요청 - 사용자 음성 메시지를 그대로 처리
                llm_response = generate_content_with_history(
                    system_prompt=system_prompt,
                    new_message=transcribed_text,
                    function_list=[get_search_results, maps_search_nearby],
                    image_path=None
                )
                llm_response = dict(list(llm_response)[1])['content']

            else:
                llm_response = "음성 메시지를 처리할 수 없습니다. 텍스트로 변환 중 오류가 발생했습니다."

            # Discord 메시지 전송: 텍스트(분석 결과)를 포함하여 한 번에 전송
            future_msg = executor.submit(lambda: asyncio.run_coroutine_threadsafe(
                send_location_to_discord(
                    latitude, longitude, street, city,
                    extra_message=llm_response,
                    image_path=None,
                    audio_path=None,
                    show_places=False,
                    message_include=True
                ), bot.loop
            ).result())
            try:
                future_msg.result(timeout=30)
            except Exception as e:
                logging.error(f"디스코드 메시지 전송 실패 (텍스트): {e}")

            executor.shutdown(wait=True)
            discord_sent = True
            return jsonify({'status': 'success'})

        # =====================================================================================
        # 기타 다른 케이스들 - 기본 처리
        # =====================================================================================
        else:
            logging.info("기타 케이스: 기본 처리")
            executor = concurrent.futures.ThreadPoolExecutor()
            # 디스코드로 전송할 기본 메시지 생성
            extra_message_content = f"GPS: {latitude}, {longitude}"
            if street or city:
                extra_message_content += f", 주소: {street}, {city}"
            
            if extra_message:
                extra_message_content += f"\n\n사용자 메시지: {extra_message}"
            
            # 추가 메시지가 없으면 기본 LLM 응답 생성
            if not llm_response:
                llm_response = "제공된 정보를 처리했습니다."

            # Discord 메시지 전송: 텍스트(분석 결과)를 포함하여 한 번에 전송
            future_msg = executor.submit(lambda: asyncio.run_coroutine_threadsafe(
                send_location_to_discord(
                    latitude, longitude, street, city,
                    extra_message=llm_response,
                    image_path=None,
                    audio_path=None,
                    show_places=False,
                    message_include=True
                ), bot.loop
            ).result())
            try:
                future_msg.result(timeout=30)
            except Exception as e:
                logging.error(f"디스코드 메시지 전송 실패 (텍스트): {e}")

            executor.shutdown(wait=True)
            discord_sent = True
            return jsonify({'status': 'success'})

        # =====================================================================================
        # 처리 결과 및 최종 메시지 정리
        # =====================================================================================
        if not discord_sent:
            response_message = extra_message if extra_message else "처리된 데이터"

            if llm_response:
                response_message = llm_response
            
            executor = concurrent.futures.ThreadPoolExecutor()

            # 이미지 용량이 8MB 이상일 때만 리사이즈를 수행합니다.
            if os.path.getsize(image_filename) >= 7.5 * 1024 * 1024:
                future_resize = executor.submit(resize_image, image_filename, 7.5)
                resized_image_filename = future_resize.result()
            else:
                resized_image_filename = image_filename

            # 디스코드로 전송 (비동기) - 맛집 정보는 표시하지 않음
            future = asyncio.run_coroutine_threadsafe(
                send_location_to_discord(
                    latitude, longitude, street, city,
                    extra_message=response_message,
                    image_path=resized_image_filename,
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
            "filename": resized_image_filename,
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

# %%
