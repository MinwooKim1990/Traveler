import os
import json
import logging
import asyncio
import discord
from .bot import bot, get_channel
from utils import search_nearby_places, compute_route_matrix
from utils.gemini import gemini_bot

async def send_location_to_discord(latitude, longitude, street, city, extra_message=None, image_path=None, audio_path=None, show_places=False, message_include=True):
    """위치 정보와 추가 데이터를 디스코드로 전송합니다.
    
    Parameters:
        latitude, longitude: 위도와 경도
        street: 도로명 주소
        city: 도시명
        extra_message: 추가 메시지 (선택 사항)
        image_path: 이미지 파일 경로 (선택 사항)
        audio_path: 음성 파일 경로 (선택 사항)
        show_places: 주변 장소 정보 표시 여부 (기본값: False)
    """
    try:
        lat1, lng1 = float(latitude), float(longitude)
    except Exception as e:
        logging.error(f"GPS 좌표 변환 오류: {e}")
        return

    # 디스코드 채널 가져오기 및 타입 확인
    from discord import TextChannel
    channel = get_channel()
    if not channel or not isinstance(channel, TextChannel):
        logging.error("디스코드 채널을 찾을 수 없거나 TextChannel이 아님")
        return

    if message_include == True:
        # 메시지 구성
        message_parts = []
        
        # 추가 메시지가 있다면 맨 위에 추가
        if extra_message:
            message_parts.append(f"💬 **메시지**:\n{extra_message}\n\n")
        
        # 기본 GPS 데이터 정보
        message_parts.append(f"📍 **위치 정보**\n위도: {lat1}\n경도: {lng1}")
        if street or city:
            message_parts.append(f"주소: {street}, {city}")
        
        # show_places가 True인 경우에만 주변 장소 정보 추가
        if show_places:
            # 주변 장소 검색
            filtered_places = search_nearby_places(lat1, lng1, keyword="restaurant")
            message_parts.append(f"\n**총 {len(filtered_places)}개의 장소 정보가 필터링되었습니다.**")
            
            # 각 장소별 정보 추가
            for i, ele in enumerate(filtered_places):
                place_info = f"\n\n**장소 {i+1}: {ele['name']}**\n"
                place_info += f"위치: {ele['location']}\n"
                place_info += f"영업 여부: {ele['open_now']}\n"
                place_info += f"평점: {ele['rating']}\n"
                place_info += f"유형: {ele['types']}\n"
                place_info += f"거리: {ele['distance']:.2f} km\n"
                
                # 첫 두 장소에 대해 경로 정보 추가 (도보, 운전)
                if i in [0, 1]:
                    lat2 = float(ele['location'][0])
                    lng2 = float(ele['location'][1])
                    try:
                        walking_distance = compute_route_matrix((lat1, lng1), [(lat2, lng2)], travel_mode='WALK')
                        driving_distance = compute_route_matrix((lat1, lng1), [(lat2, lng2)], travel_mode='DRIVE')
                        place_info += f"Google Maps 도보 경로: {json.dumps(walking_distance, ensure_ascii=False)}\n"
                        place_info += f"Google Maps 운전 경로: {json.dumps(driving_distance, ensure_ascii=False)}\n"
                    except Exception as route_error:
                        logging.error(f"경로 정보 계산 오류: {route_error}")
                        place_info += "경로 정보 없음\n"
                        
                place_info += f"{'-'*30}\n"
                message_parts.append(place_info)
        
        message = "\n".join(message_parts)
    else:
        message = ""
    files = []
    
    # 이미지 파일이 있고 실제로 존재하는 경우에만 첨부
    if image_path and os.path.exists(image_path):
        try:
            files.append(discord.File(image_path))
            logging.debug(f"이미지 파일 첨부: {image_path}")
        except Exception as e:
            logging.error(f"이미지 파일 전송 실패: {e}")
    
    # 오디오 파일이 있고 실제로 존재하는 경우에만 첨부
    if audio_path and os.path.exists(audio_path):
        try:
            files.append(discord.File(audio_path))
            logging.debug(f"오디오 파일 첨부: {audio_path}")
        except Exception as e:
            logging.error(f"음성 파일 전송 실패: {e}")
    
    try:
        # 메시지 길이가 2000자를 초과하면 분할 전송 (첫 청크에 파일 첨부)
        if len(message) > 2000:
            chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
            for j, chunk in enumerate(chunks):
                if j == 0:
                    await channel.send(content=f"메시지 파트 {j+1}/{len(chunks)}:\n{chunk}", files=files)
                else:
                    await channel.send(content=f"메시지 파트 {j+1}/{len(chunks)}:\n{chunk}")
                await asyncio.sleep(1)
        else:
            await channel.send(content=message, files=files)
        logging.info("디스코드 메시지 전송 성공")
    except Exception as e:
        logging.error(f"메시지 전송 실패: {e}")

@bot.event
async def on_message(message):
    """디스코드 채널에서 수신된 메시지를 처리하는 이벤트 핸들러"""
    # 자신의 메시지는 무시
    if message.author == bot.user:
        return

    # 봇 명령어 처리를 위한 기본 처리
    await bot.process_commands(message)
    
    # 메시지 내용이 있고, 봇이 언급되었거나 DM인 경우에만 처리
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions
    
    if message.content and (is_dm or is_mentioned) and bot.user is not None:
        # 봇 멘션 제거
        clean_content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        
        # 이미지나 오디오 파일이 있는지 확인하고 저장
        image_path = None
        audio_path = None
        
        if message.attachments:
            for attachment in message.attachments:
                # 이미지 파일 처리
                if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    image_path = f"uploads/discord_{attachment.filename}"
                    await attachment.save(image_path)
                    logging.info(f"디스코드로부터 이미지 저장: {image_path}")
                    break
                
                # 오디오 파일 처리
                elif attachment.filename.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a')):
                    audio_path = f"uploads/discord_{attachment.filename}"
                    await attachment.save(audio_path)
                    logging.info(f"디스코드로부터 오디오 저장: {audio_path}")
                    break
        
        # 메시지 처리 - Gemini API 사용
        try:
            from utils.gemini import gemini_bot
            from utils.new_utils import get_local_time_by_gps, generate_content_with_history
            import os
            
            # Gemini 프롬프트 생성
            system_prompt = """
당신은 여행자를 돕는 친절한 AI 어시스턴트입니다. 사용자가 보낸 메시지에 대해 상세하고 유용한 정보를 제공해 주세요.
위치 정보나 여행 계획에 관련된 질문에 특히 잘 대답해주세요.
한국어로 친절하고 도움이 되는 응답을 제공해 주세요.
"""
            # 히스토리 초기화
            history = []
            
            if image_path and os.path.exists(image_path):
                # 이미지가 있는 경우
                response = gemini_bot(
                    system_prompt=system_prompt,
                    user_input=clean_content,
                    image_path=image_path
                )
            else:
                # 텍스트만 있는 경우
                response = generate_content_with_history(
                    system_prompt=system_prompt,
                    new_message=clean_content,
                    function_list=[],
                    image_path="",
                    k=7,
                    history=history
                )
                response = dict(list(response)[1])['content']
            
            # 응답 전송
            await message.channel.send(response)
            
        except Exception as e:
            logging.error(f"메시지 처리 중 오류: {e}")
            await message.channel.send(f"죄송합니다, 응답을 생성하는 중 오류가 발생했습니다: {str(e)}")

    from discord import MessageReference
    if message.reference is not None:
        reference: MessageReference = message.reference
        if reference.message_id is not None:
            try:
                ref_msg = await message.channel.fetch_message(reference.message_id)
                combined_content = f"Reply to: {ref_msg.content}\n" + message.content
                setattr(message, 'content', combined_content)
            except Exception as e:
                logging.error(f"답장 메시지 가져오기 실패: {e}")