# %%
import sys
import os

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

def synthesize_speech(text: str, output_audio: str = "output.mp3"):
    """
    gTTS를 사용하여 한국어 텍스트를 음성으로 합성하고, 지정된 mp3 파일로 저장합니다.
    
    Parameters:
        text: 합성할 텍스트
        output_audio: 출력 파일 경로
        
    Returns:
        성공 여부를 나타내는 불리언 값
    """
    if not text or not text.strip():
        print("합성할 텍스트가 비어있습니다.")
        return False
    
    try:
        from gtts import gTTS
    except ImportError:
        print("gTTS 패키지가 설치되어 있지 않습니다. 'pip install gTTS' 로 설치하세요.")
        return False
    
    try:
        # 출력 폴더가 존재하는지 확인
        output_dir = os.path.dirname(output_audio)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        # 출력 파일 경로 설정
        output_path = os.path.normpath(os.path.join(os.getcwd(), output_audio))
        
        print("텍스트를 음성으로 합성 중...")
        tts = gTTS(text=text, lang="ko")
        tts.save(output_path)
        print(f"TTS 결과물이 '{output_path}' 파일로 저장되었습니다.")
        return True
    except Exception as e:
        print(f"음성 합성 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    # 현재 작업 디렉토리 출력
    print(f"현재 작업 디렉토리: {os.getcwd()}")

    # 1. STT: Whisper를 사용하여 오디오 파일을 텍스트로 전사합니다.
    print("STT 처리 시작...")
    transcribed_text = transcribe_audio("../uploads/녹음.mp3", "medium")
    print("전사된 텍스트:")
    print(transcribed_text)

    # 2. TTS: 전사된 텍스트를 gTTS를 사용해 음성으로 합성합니다.
    synthesize_speech(transcribed_text, "../responses/대답.mp3")
# %%