import time
import logging
import threading
import discord
import asyncio
from discord.ext import commands, tasks
from config import DISCORD_TOKEN, SERVER_ID, CHANNEL_ID

# 디스코드 봇 설정
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

@tasks.loop(minutes=5)
async def check_connection():
    """5분마다 봇 연결 상태를 확인하고 필요시 재연결"""
    if not bot.is_ready():
        logging.warning("봇 연결이 끊어진 상태, 재연결 시도...")
        try:
            await bot.close()
            await bot.start(DISCORD_TOKEN)
        except Exception as e:
            logging.error(f"재연결 시도 중 오류: {e}")

@bot.event
async def on_ready():
    """봇이 준비되었을 때 호출되는 이벤트 핸들러"""
    logging.info(f'{bot.user.name}이(가) 디스코드에 연결되었습니다!')
    logging.debug(f'Bot 유저 정보: {bot.user}')
    # 연결 유지 작업 시작
    if not check_connection.is_running():
        check_connection.start()

def run_discord_bot():
    """디스코드 봇을 실행합니다. (별도 스레드에서 실행됩니다)"""
    try:
        # 새로운 이벤트 루프 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 봇 실행
        loop.run_until_complete(bot.start(DISCORD_TOKEN))
    except Exception as e:
        logging.error(f"디스코드 봇 실행 중 오류: {e}")
    finally:
        # 정리
        if not loop.is_closed():
            loop.close()

def start_bot():
    """봇을 별도 스레드에서 시작하고 준비될 때까지 기다립니다."""
    bot_thread = threading.Thread(target=run_discord_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # 봇이 준비될 때까지 기다림
    if wait_for_bot_ready():
        logging.info("봇 준비 완료")
    else:
        logging.warning("봇 준비 시간 초과")
    
    return bot

def wait_for_bot_ready(timeout=30):
    """봇이 준비될 때까지 기다립니다.
    
    Parameters:
        timeout: 최대 대기 시간 (초)
        
    Returns:
        성공 여부 (불리언)
    """
    start_time = time.time()
    while not bot.is_ready():
        if time.time() - start_time > timeout:
            logging.warning(f"봇이 {timeout}초 내 준비되지 않음")
            return False
        time.sleep(0.2)
    return True

def get_channel():
    """설정된 채널 ID에 해당하는 디스코드 채널을 반환합니다.
    
    Returns:
        디스코드 채널 객체 또는 None
    """
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        try:
            channel = bot.fetch_channel(CHANNEL_ID)
        except Exception as e:
            logging.error(f"채널 ID {CHANNEL_ID}를 찾을 수 없음: {e}")
            return None
    return channel