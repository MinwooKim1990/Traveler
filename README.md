# 여행 위치 정보 공유 애플리케이션

이 애플리케이션은 위치 정보, 이미지, 음성 등을 받아 디스코드 채널로 전송하고 주변 장소 정보를 함께 제공합니다. 또한 Google Gemini AI를 활용하여 이미지 분석, 텍스트 생성, 음성 처리 등의 기능을 제공합니다.

## 주요 기능

- 위도, 경도, 주소 정보를 포함한 위치 데이터 수신
- 이미지 및 음성 파일 업로드 지원
- Google Maps API를 활용한 주변 장소 검색 및 정보 제공
- Google Gemini AI를 활용한 이미지 분석 및 텍스트 생성
- Whisper를 활용한 음성 텍스트 변환 (STT)
- gTTS를 활용한 텍스트 음성 변환 (TTS)
- 디스코드 봇을 통한 정보 전송

## 지원하는 요청 형태

1. **GPS 정보만 있는 경우**: 주변 맛집 추천 (반경 500m 내)
2. **이미지 + GPS**: 이미지 분석 및 위치 정보 활용 설명
3. **이미지 + 메시지 + GPS**: 메시지를 프롬프트로 사용해 이미지 분석
4. **이미지 + 오디오 + GPS**: 오디오 변환 후 내용 분석 및 음성 응답 생성
5. **메시지/오디오 + GPS**: 메시지/음성 내용에 대한 응답 생성

## 프로젝트 구조

```
Travel/
├── .env                  # 환경 변수 설정
├── config.py             # 설정 파일
├── main.py               # 애플리케이션 시작점
├── requirements.txt      # 필요한 패키지 목록
├── README.md             # 프로젝트 설명
├── api/                  # Flask API 관련 모듈
│   ├── __init__.py
│   └── routes.py         # API 라우트 정의
├── discord_bot/          # 디스코드 봇 관련 모듈
│   ├── __init__.py
│   ├── bot.py            # 디스코드 봇 설정 및 실행
│   └── message.py        # 디스코드 메시지 전송 함수
├── utils/                # 유틸리티 함수들
│   ├── __init__.py
│   ├── distance.py       # 거리 계산 관련 함수
│   ├── maps.py           # Google Maps API 관련 함수
│   ├── gemini.py         # Google Gemini AI 관련 함수
│   ├── whisper_gen.py    # 음성 인식 및 합성 관련 함수
│   └── audio_convert.py  # 오디오 파일 변환 관련 함수
├── uploads/              # 업로드된 파일 저장 폴더
└── responses/            # 생성된 응답 파일 저장 폴더
```

## 설치 및 실행 방법

1. 필요한 패키지 설치:
   ```
   pip install -r requirements.txt
   ```

2. `.env` 파일을 수정하여 API 키와 토큰 설정:
   ```
   API_KEY=your_api_key
   GMAPS_API_KEY=your_google_maps_api_key
   DISCORD_TOKEN=your_discord_bot_token
   SERVER_ID=your_server_id
   CHANNEL_ID=your_channel_id
   GEMINI_API_KEY=your_gemini_api_key
   ```

3. 애플리케이션 실행:
   ```
   python main.py
   ```

## API 사용법

### 위치 데이터 업로드 (POST /upload)

**헤더:**
- `X-API-Key`: API 키

**폼 데이터:**
- `text`: 위치 정보 (key=value 형식, 줄바꿈으로 구분)
  ```
  latitude=37.5665
  longitude=126.9780
  street=세종대로
  city=서울
  ```
- `image`: 이미지 파일 (선택 사항)
- `voice`: 음성 파일 (선택 사항)
- `message`: 추가 메시지 (선택 사항)

**응답 예시:**
```json
{
  "status": "success",
  "filename": "uploads/image_12345.jpg",
  "audio_filename": "uploads/audio_67890.mp3",
  "response_audio": "responses/response_12345.mp3",
  "message": "여행 중입니다",
  "llm_response": "AI가 생성한 응답 내용",
  "latitude": "37.5665",
  "longitude": "126.9780",
  "street": "세종대로",
  "city": "서울"
}
``` 