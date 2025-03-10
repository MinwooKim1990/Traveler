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
    
def search_and_extract(query: str) -> str:
    max_results = 10
    max_workers = 10
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # 상수 설정
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    TIMEOUT = 30      # 초
    MAX_RETRIES = 3
    RETRY_DELAY = 1   # 초
    
    def fetch_url(url: str, session: requests.Session, retry: int = 0) -> str:
        """단일 URL에서 HTML 콘텐츠를 가져옴 (재시도 로직 포함)."""
        try:
            logger.debug(f"Fetching {url}")
            response = session.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            if response.status_code == 200:
                return response.text
            elif response.status_code in (429, 503) and retry < MAX_RETRIES:
                wait_time = RETRY_DELAY * (2 ** retry)
                logger.warning(f"Rate limited on {url}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                return fetch_url(url, session, retry + 1)
            else:
                logger.error(f"Error fetching {url}: Status code {response.status_code}")
                return ""
        except requests.Timeout:
            if retry < MAX_RETRIES:
                wait_time = RETRY_DELAY * (2 ** retry)
                logger.warning(f"Timeout on {url}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                return fetch_url(url, session, retry + 1)
            logger.error(f"Timeout fetching {url} after {MAX_RETRIES} retries")
            return ""
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return ""
    
    def extract_text_from_html_sync(html_content: str, session: requests.Session = None, visited: set = None, base_url: str = None) -> str:
        """
        HTML 콘텐츠에서 메인 텍스트를 추출합니다.
        readability 라이브러리를 우선 사용하며 실패시 BeautifulSoup을 통해 재시도합니다.
        그리고, 페이지 내 <iframe> 태그의 콘텐츠도 함께 추출합니다.
        """
        if visited is None:
            visited = set()
        main_text = ""
        try:
            from readability import Document
            doc = Document(html_content)
            main_html = doc.summary()
            soup = BeautifulSoup(main_html, "lxml")
            main_text = soup.get_text(separator=" ", strip=True)
            main_text = re.sub(r'\s+', ' ', main_text).strip()
        except Exception as e:
            logger.error(f"Readability 추출 실패: {e}. 기존 방식으로 재시도합니다.")
            if not html_content:
                return ""
            soup = BeautifulSoup(html_content, "lxml")
            for element in soup(['script', 'style', 'meta', 'noscript', 'head', 'footer', 'nav']):
                element.decompose()
            paragraphs = []
            for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span', 'article', 'section', 'li', 'td', 'th']):
                curr_text = tag.get_text(strip=True)
                if curr_text and len(curr_text) > 1:
                    paragraphs.append(curr_text)
            remaining_text = soup.get_text(separator=' ', strip=True)
            if remaining_text:
                for p in paragraphs:
                    remaining_text = remaining_text.replace(p, '')
                remaining_parts = [part for part in remaining_text.split() if len(part) > 1]
                if remaining_parts:
                    paragraphs.append(' '.join(remaining_parts))
            main_text = ' '.join(paragraphs)
            main_text = re.sub(r'\s+', ' ', main_text).strip()
    
        if session is not None:
            original_soup = BeautifulSoup(html_content, "lxml")
            iframe_texts = []
            for iframe in original_soup.find_all("iframe"):
                src = iframe.get("src", "")
                if src:
                    if not bool(urlparse(src).netloc) and base_url:
                        src = urljoin(base_url, src)
                    if src not in visited:
                        visited.add(src)
                        iframe_html = fetch_url(src, session)
                        if iframe_html:
                            iframe_content = extract_text_from_html_sync(iframe_html, session, visited, base_url=src)
                            if iframe_content:
                                iframe_texts.append(iframe_content)
            if iframe_texts:
                main_text += " " + " ".join(iframe_texts)
                main_text = re.sub(r'\s+', ' ', main_text).strip()
    
        return main_text
    
    def process_url(url: str, session: requests.Session) -> dict:
        """URL에서 본문 텍스트를 추출하는 함수."""
        start_time = time.time()
        result = {"url": url, "text": "", "success": False, "time": 0}
        html_content = fetch_url(url, session)
        if not html_content:
            result["time"] = time.time() - start_time
            return result
        text = extract_text_from_html_sync(html_content, session, base_url=url)
        result["text"] = text
        result["success"] = True
        result["time"] = time.time() - start_time
        result["length"] = len(text)
        return result
    
    # DuckDuckGo 검색 수행
    results = []
    try:
        ddg = DDGS()
        ddg_results = ddg.text(query, max_results=max_results)
        for item in ddg_results:
            href = item.get("href", "").strip()
            if not href:
                continue
            result_item = {
                "title": item.get("title", "").strip(),
                "link": href,
                "snippet": item.get("body", "").strip(),
                "main": ""
            }
            if all(r.get('link') != href for r in results):
                results.append(result_item)
    except Exception as e:
        logger.error(f"DuckDuckGo 검색 오류: {e}")
    
    # 검색 결과의 각 링크에 대해 본문 텍스트 추출 (병렬 처리)
    if results:
        links = [item["link"] for item in results]
        session = requests.Session()
        extracted = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(process_url, url, session): url for url in links}
            for future in future_to_url:
                url = future_to_url[future]
                try:
                    resp = future.result()
                    extracted[url] = resp["text"] if resp["success"] else ""
                except Exception as exc:
                    logger.error(f"Error processing {url}: {exc}")
                    extracted[url] = ""
        for item in results:
            item["main"] = extracted.get(item["link"], "")
    result_str = json.dumps(results, ensure_ascii=False)
    return result_str