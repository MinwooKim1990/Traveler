# %%
import sys
import os
from google.cloud import texttospeech
import os
import re
from collections import Counter
import langid

def transcribe_audio(audio_file, model_name: str = "base"):
    """
    Whisper 모델을 이용하여 입력된 오디오 파일을 텍스트로 전사합니다.
    한국어 인식을 위해 language="ko" 옵션을 사용합니다.
    
    Parameters:
        audio_file: 오디오 파일 경로 (None인 경우 예외 처리)
        model_name: 사용할 Whisper 모델 이름
        
    Returns:
        전사된 텍스트 또는 오류 메시지
    """
    # 파일이 None인 경우 처리
    if audio_file is None:
        return "오디오 파일이 제공되지 않았습니다."
    
    try:
        import whisper
    except ImportError:
        error_msg = "openai-whisper 패키지가 설치되어 있지 않습니다. 'pip install openai-whisper' 로 설치하세요."
        print(error_msg)
        return error_msg
    
    # 파일 경로 확인
    full_path = os.path.normpath(os.path.join(os.getcwd(), audio_file))
    if not os.path.exists(full_path):
        error_msg = f"오류: 파일을 찾을 수 없습니다. 경로: {full_path}"
        print(error_msg)
        return error_msg
    
    try:
        print(f"Whisper 모델 '{model_name}'를 로드하는 중...")
        model = whisper.load_model(model_name)
        
        print(f"오디오 파일 전사 중... (파일 경로: {full_path})")
        # language="ko" 옵션을 사용해 한국어에 최적화된 전사를 수행합니다.
        result = model.transcribe(full_path, language="ko")
        return result["text"]
    except Exception as e:
        error_msg = f"전사 중 오류 발생: {e}"
        print(error_msg)
        return error_msg

def detect_language(text: str) -> str:
    """
    입력된 문자열의 언어를 감지합니다.
    
    Parameters:
        text: 언어를 감지할 문자열
        
    Returns:
        감지된 언어 코드 (예: 'ko', 'en', 'ja' 등)
    """
    # 텍스트가 너무 짧으면 정확도가 떨어질 수 있음
    if len(text) < 10:
        # 한글 문자 패턴
        korean_pattern = re.compile('[ㄱ-ㅎㅏ-ㅣ가-힣]')
        # 영어 문자 패턴
        english_pattern = re.compile('[a-zA-Z]')
        # 일본어 문자 패턴 (히라가나, 가타카나)
        japanese_pattern = re.compile('[ぁ-んァ-ン]')
        # 중국어 문자 패턴
        chinese_pattern = re.compile('[\u4e00-\u9fff]')
        
        # 각 언어 패턴에 맞는 문자 수 계산
        korean_count = len(korean_pattern.findall(text))
        english_count = len(english_pattern.findall(text))
        japanese_count = len(japanese_pattern.findall(text))
        chinese_count = len(chinese_pattern.findall(text))
        
        # 가장 많이 나타난 언어 반환
        counts = {
            'ko': korean_count,
            'en': english_count,
            'ja': japanese_count,
            'zh': chinese_count
        }
        
        return max(counts, key=counts.get)
    else:
        # 텍스트가 충분히 길면 langid 라이브러리 사용
        lang, _ = langid.classify(text)
        return lang

def synthesize_text(text: str, output_audio: str = "output.mp3", gender: str = "female", speed: float = 1.1):
    """
    Synthesizes speech from the input string of text.
    
    Parameters:
        text (str): 음성으로 변환할 텍스트
        output_audio (str): 출력 오디오 파일 경로
        gender (str): 성별 선택 ('male' 또는 'female')
        speed (float): 읽기 속도 (1.0이 기본 속도)
    """
    # 서비스 계정 키 JSON 파일 경로 설정
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "TTS.json"

    # 음성 선택 매핑
    voice_mapping = {
        "ko": {
            "female": "ko-KR-Chirp3-HD-Leda",  # 한국어 여성
            "male": "ko-KR-Chirp3-HD-Charon"     # 한국어 남성
        },
        "en": {
            "female": "en-GB-Chirp3-HD-Aoede",   # 영국 영어 여성
            "male": "en-GB-Chirp3-HD-Charon"      # 영국 영어 남성 (가정)
        },
        "ja": {
            "female": "ja-JP-Chirp3-HD-Leda",  # 일본어 여성
            "male": "ja-JP-Chirp3-HD-Fenrir"     # 일본어 남성
        }
    }
    
    # 언어 코드 매핑
    language_code_mapping = {
        "ko": "ko-KR",
        "en": "en-GB",
        "ja": "ja-JP"
    }
    
    # SSML 성별 매핑
    gender_mapping = {
        "male": texttospeech.SsmlVoiceGender.MALE,
        "female": texttospeech.SsmlVoiceGender.FEMALE
    }
    language = detect_language(text)
    print(f"감지된 언어: {language}")
    # 입력 매개변수 검증
    if language not in language_code_mapping:
        raise ValueError(f"지원되지 않는 언어입니다: {language}. 지원되는 언어: ko, en, ja")
    
    if gender not in gender_mapping:
        raise ValueError(f"지원되지 않는 성별입니다: {gender}. 지원되는 성별: male, female")
    
    # TTS 클라이언트 초기화
    client = texttospeech.TextToSpeechClient()
    
    # 입력 텍스트 설정
    input_text = texttospeech.SynthesisInput(text=text)
    
    # 음성 매개변수 설정
    voice_name = voice_mapping[language][gender]
    language_code = language_code_mapping[language]
    
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,
        ssml_gender=gender_mapping[gender]
    )
    
    # 오디오 구성 설정 (속도 포함)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speed  # 읽기 속도 설정
    )
    
    # 음성 합성 수행
    response = client.synthesize_speech(
        input=input_text, voice=voice, audio_config=audio_config
    )
    
    # 결과 오디오 저장
    with open(output_audio, "wb") as out:
        out.write(response.audio_content)
        print(f'Audio content written to file "{output_audio}"')
    
    return output_audio
# %%