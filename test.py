# %%
import requests
from bs4 import BeautifulSoup
from typing import List, Optional, Dict, Any
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import io
import base64
import win32clipboard
from PIL import Image

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 커스텀 헤더 설정 (일부 사이트는 봇 차단)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0'
}

# 세션 타임아웃 및 재시도 설정
TIMEOUT = 30  # 초
MAX_RETRIES = 3
RETRY_DELAY = 1  # 초

def fetch_url(url: str, session: requests.Session, retry: int = 0) -> Optional[str]:
    """단일 URL에서 HTML 콘텐츠를 가져옵니다. 재시도 로직 포함."""
    try:
        domain = urlparse(url).netloc
        logger.debug(f"Fetching {url}")
        
        response = session.get(
            url, 
            headers=HEADERS, 
            timeout=TIMEOUT,
            verify=False  # SSL 인증서 검증 우회 (필요시 활성화)
        )
        
        if response.status_code == 200:
            return response.text
        elif response.status_code in (429, 503) and retry < MAX_RETRIES:  # 속도 제한 또는 서비스 일시 중단
            wait_time = RETRY_DELAY * (2 ** retry)  # 지수 백오프
            logger.warning(f"Rate limited on {url}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            return fetch_url(url, session, retry + 1)
        else:
            logger.error(f"Error fetching {url}: Status code {response.status_code}")
            return None
    except requests.Timeout:
        if retry < MAX_RETRIES:
            wait_time = RETRY_DELAY * (2 ** retry)
            logger.warning(f"Timeout on {url}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            return fetch_url(url, session, retry + 1)
        logger.error(f"Timeout fetching {url} after {MAX_RETRIES} retries")
        return None
    except Exception as e:
        logger.error(f"Error fetching {url}: {str(e)}")
        return None

def extract_text_from_html_sync(html_content: str, session: Optional[requests.Session] = None, visited: Optional[set] = None, base_url: Optional[str] = None) -> str:
    """HTML 콘텐츠에서 메인 기사 및 iframe의 메인 콘텐츠까지 추출하는 함수.
    
    readability를 우선 사용하며, 실패할 경우 기존 방식으로 재시도합니다.
    또한, 페이지 내의 모든 <iframe> 태그의 src에 대해 절대 URL 처리를 포함해 추가 요청을 수행해 
    메인 콘텐츠를 추출하여 병합합니다.
    """
    if visited is None:
        visited = set()

    main_text = ""
    # readability 사용 시도
    try:
        from readability import Document  # readability-lxml 라이브러리 필요
        doc = Document(html_content)
        main_html = doc.summary()
        soup = BeautifulSoup(main_html, 'lxml')
        main_text = soup.get_text(separator=' ', strip=True)
        main_text = re.sub(r'\s+', ' ', main_text).strip()
    except Exception as e:
        logger.error(f"Readability 추출 실패: {e}. 기존 방식으로 재시도합니다.")
        if not html_content:
            return ""
        soup = BeautifulSoup(html_content, 'lxml')
        for element in soup(['script', 'style', 'meta', 'noscript', 'head', 'footer', 'nav']):
            element.decompose()
        
        paragraphs = []
        # 주요 텍스트 컨테이너에서 텍스트 추출
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

    # 만약 세션이 제공되었다면, iframe 내의 콘텐츠도 추가 처리
    if session is not None:
        original_soup = BeautifulSoup(html_content, 'lxml')
        iframe_texts = []
        for iframe in original_soup.find_all("iframe"):
            src = iframe.get("src", "")
            if src:
                # 상대 URL이면 base_url과 조합해서 절대 URL로 변환
                if not bool(urlparse(src).netloc):
                    from urllib.parse import urljoin
                    if base_url:
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

def process_url(url: str, session: requests.Session) -> Dict[str, Any]:
    """URL에서 HTML을 가져와 텍스트를 추출하고 메타데이터와 함께 반환합니다."""
    start_time = time.time()
    result = {"url": url, "text": "", "success": False, "time": 0}
    
    html_content = fetch_url(url, session)
    if not html_content:
        result["time"] = time.time() - start_time
        return result
    
    # base_url로 메인 페이지 URL을 전달하여 상대 URL 처리를 지원합니다.
    text = extract_text_from_html_sync(html_content, session, base_url=url)
    
    result["text"] = text
    result["success"] = True
    result["time"] = time.time() - start_time
    result["length"] = len(text)
    
    return result

def extract_text_from_urls(urls: List[str], max_workers: int = 10) -> str:
    """여러 URL에서 텍스트를 추출하고 결합하는 메인 함수"""
    start_time = time.time()
    
    if not urls:
        logger.warning("Empty URL list provided")
        return ""
    
    # 중복 URL 제거
    unique_urls = list(dict.fromkeys(urls))
    total_urls = len(unique_urls)
    logger.info(f"Starting extraction from {total_urls} unique URLs")
    
    # 세션 생성 (연결 재사용)
    session = requests.Session()
    
    # 스레드 풀을 사용한 병렬 처리
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 작업 제출
        future_to_url = {executor.submit(process_url, url, session): url for url in unique_urls}
        
        # 결과 수집
        for future in future_to_url:
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                url = future_to_url[future]
                logger.error(f"URL {url} generated an exception: {exc}")
    
    # 성공한 결과만 필터링하고 텍스트 결합
    successful_texts = [r["text"] for r in results if r["success"] and r["text"]]
    
    # 통계 출력
    success_count = sum(1 for r in results if r["success"])
    total_chars = sum(len(r["text"]) for r in results if r["success"])
    avg_time = sum(r["time"] for r in results) / len(results) if results else 0
    
    logger.info(f"Extraction completed: {success_count}/{total_urls} URLs successful")
    logger.info(f"Total characters extracted: {total_chars}")
    logger.info(f"Average processing time per URL: {avg_time:.2f}s")
    
    end_time = time.time()
    logger.info(f"Total execution time: {end_time - start_time:.2f} seconds")
    
    return " ".join(successful_texts)

# 사용 예시
if __name__ == "__main__":
    urls = [
        "https://blog.naver.com/baljern/223338612143",
        "https://thenuancedperspective.substack.com/p/this-week-in-ai-18th-jan-2025",
        # 더 많은 URL 추가 가능
    ]
    
    combined_text = extract_text_from_urls(urls)
    print(f"추출된 텍스트 길이: {len(combined_text)} 문자")
    print(combined_text[:200] + "..." if len(combined_text) > 200 else combined_text)

# %%
import requests
from bs4 import BeautifulSoup
import re

def extract_html_structure(url):
    """
    URL에서 HTML을 가져와 LLM이 이해하기 쉬운 구조로 변환하는 함수
    
    Args:
        url (str): 분석할 웹페이지의 URL
        
    Returns:
        str: LLM이 이해하기 쉬운 형태로 정리된 HTML 구조
    """
    try:
        # 사용자 에이전트 설정으로 차단 방지
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # URL에서 HTML 가져오기
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        
        # HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 불필요한 요소 제거
        for script in soup(["script", "style", "meta", "link", "noscript"]):
            script.decompose()
            
        # 주석 제거
        comments = soup.find_all(text=lambda text: isinstance(text, str) and '<!--' in text)
        for comment in comments:
            comment.extract()
        
        # 구조화된 HTML 생성
        structured_html = generate_structured_html(soup)
        
        return structured_html
        
    except requests.exceptions.RequestException as e:
        return f"Error fetching URL: {str(e)}"
    except Exception as e:
        return f"Error processing HTML: {str(e)}"

def generate_structured_html(soup):
    """
    BeautifulSoup 객체에서 구조화된 HTML을 생성
    
    Args:
        soup (BeautifulSoup): 파싱된 HTML
        
    Returns:
        str: 구조화된 HTML 문자열
    """
    # 중요 태그와 속성 추출
    html_structure = []
    
    # HTML 문서의 기본 구조 추가
    html_tag = soup.find('html')
    if html_tag:
        html_attrs = format_attributes(html_tag.attrs)
        html_structure.append(f"<html{html_attrs}>")
    
    # HEAD 섹션 처리
    head_tag = soup.find('head')
    if head_tag:
        html_structure.append("  <head>")
        
        # 제목 추가
        title = head_tag.find('title')
        if title:
            html_structure.append(f"    <title>{title.get_text().strip()}</title>")
        
        html_structure.append("  </head>")
    
    # BODY 섹션 처리
    body_tag = soup.find('body')
    if body_tag:
        body_attrs = format_attributes(body_tag.attrs)
        html_structure.append(f"  <body{body_attrs}>")
        
        # 본문 구조 추출
        extract_content_structure(body_tag, html_structure, indent=4)
        
        html_structure.append("  </body>")
    
    if html_tag:
        html_structure.append("</html>")
    
    return "\n".join(html_structure)

def extract_content_structure(element, structure_list, indent=0):
    """
    HTML 요소의 구조를 재귀적으로 추출
    
    Args:
        element: 현재 처리 중인 HTML 요소
        structure_list: 결과를 저장할 리스트
        indent: 현재 들여쓰기 수준
    """
    # 중요 컨테이너 태그 목록
    important_tags = ['div', 'section', 'article', 'nav', 'header', 'footer', 
                      'main', 'aside', 'form', 'table', 'ul', 'ol']
    
    # 콘텐츠 태그 목록
    content_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'a', 'img', 
                    'button', 'input', 'textarea', 'select']
    
    # 자식 요소 처리
    for child in element.children:
        if child.name in important_tags:
            attrs = format_attributes(child.attrs)
            structure_list.append(" " * indent + f"<{child.name}{attrs}>")
            extract_content_structure(child, structure_list, indent + 2)
            structure_list.append(" " * indent + f"</{child.name}>")
        
        elif child.name in content_tags:
            attrs = format_attributes(child.attrs)
            text = child.get_text().strip()
            text_preview = text[:50] + "..." if len(text) > 50 else text
            text_preview = text_preview.replace("\n", " ").strip()
            
            if text_preview:
                structure_list.append(" " * indent + f"<{child.name}{attrs}>{text_preview}</{child.name}>")
            else:
                structure_list.append(" " * indent + f"<{child.name}{attrs}></{child.name}>")

def format_attributes(attrs):
    """
    HTML 속성을 문자열로 포맷팅
    
    Args:
        attrs: HTML 요소의 속성 딕셔너리
        
    Returns:
        str: 포맷팅된 속성 문자열
    """
    if not attrs:
        return ""
    
    # 중요 속성 필터링
    important_attrs = ['id', 'class', 'name', 'href', 'src', 'alt', 'type', 'role']
    filtered_attrs = {k: v for k, v in attrs.items() if k in important_attrs}
    
    # 클래스 목록 처리
    if 'class' in filtered_attrs and isinstance(filtered_attrs['class'], list):
        filtered_attrs['class'] = ' '.join(filtered_attrs['class'])
    
    # 속성 문자열 생성
    attr_str = ""
    for key, value in filtered_attrs.items():
        attr_str += f' {key}="{value}"'
    
    return attr_str

# 사용 예시
if __name__ == "__main__":
    url = "https://www.bing.com/images/search?view=detailV2&insightstoken=bcid_r72McoQQBjEI1w*ccid_vYxyhBAG&form=SBIIRP&iss=SBIUPLOADGET&sbisrc=ImgPaste&idpbck=1&sbifsz=1200+x+622+%c2%b7+77.22+kB+%c2%b7+png&sbifnm=image.png&thw=1200&thh=622&ptime=75&dlen=105436&expw=833&exph=431&selectedindex=0&id=256804230&ccid=vYxyhBAG&vt=2&sim=11"
    structure = extract_html_structure(url)
    print(structure)

# %%
import time
import logging
import io
import win32clipboard
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options as EdgeOptions

# 로깅 설정
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def copy_image_to_clipboard(image_path: str):
    """
    Pillow와 win32clipboard를 사용하여 로컬 이미지 파일의 BMP(DIB) 데이터를 클립보드에 복사합니다.
    BMP 파일 포맷은 앞의 14 바이트 헤더를 제거한 데이터를 사용해야 함.
    """
    try:
        image = Image.open(image_path)
        output = io.BytesIO()
        # BMP 형식으로 저장 (RGB 변환)
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # BMP 헤더(14 바이트) 제거
        output.close()
        
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        logger.info("이미지를 클립보드에 복사했습니다: %s", image_path)
    except Exception as e:
        logger.error("이미지 클립보드 복사 실패: %s", str(e))

def search_by_image_link_bing(image_path: str, k: int = 5) -> str:
    """
    Bing 이미지 검색에서 "Paste image link" 방식 대신,
    클립보드에 복사된 이미지를 붙여넣어 검색을 시도하는 예제입니다.
    """
    # 로컬 이미지 파일 자체를 클립보드에 복사 (텍스트가 아닌)
    copy_image_to_clipboard(image_path)

    options = EdgeOptions()
    # headless 모드는 캡차 등 이슈로 인해 실제 브라우저 모드로 실행
    #options.add_argument("--headless=new")
    driver = webdriver.Edge(options=options)
    wait = WebDriverWait(driver, 20)
    driver.maximize_window()

    try:
        # Bing 이미지 검색 페이지로 이동
        driver.get("https://www.bing.com/images?FORM=HDRSC2")
        time.sleep(2)
        
        # "이미지를 사용해 검색하기" 버튼 클릭 (해당 div 요소)
        search_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[@id='sb_sbi']"))
        )
        search_button.click()
        logger.info("이미지 검색 버튼 클릭됨")
        
        # "Paste image link" 영역(입력란)으로 전환하기 위한 탭 클릭
        paste_area = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[@id='sb_pastearea']"))
        )
        paste_area.click()
        logger.info("Paste area 탭 클릭됨")
        
        # 이제 이미지 붙여넣기에 사용할 input 요소가 표시됨
        input_field = wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@id='sb_imgpst']"))
        )
        logger.info("Paste 입력란 확인됨")
        
        # 입력란에 클릭 후, Ctrl+V 전송하여 클립보드에 있는 "이미지" 붙여넣기 시도
        input_field.click()
        input_field.send_keys(Keys.CONTROL, "v")
        logger.info("Ctrl+V 전송: 클립보드의 이미지 붙여넣기 시도")
        
        # 붙여넣은 후, Search 버튼 클릭 (입력 영역 내의 Search 버튼)
        search_trigger = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[@id='sb_pastearea']//div[@role='button']"))
        )
        search_trigger.click()
        logger.info("Search 버튼 클릭됨")
        
        # 검색 결과가 로드될 때까지 대기 (필요 시 sleep 시간 조정)
        time.sleep(5)
        
        # 결과 페이지에서 원하는 요소(예: 캡션 텍스트) 추출, 선택자는 필요에 따라 수정
        result_elements = driver.find_elements(By.CSS_SELECTOR, "div.b_caption p")
        results = [elem.text.strip() for elem in result_elements if elem.text.strip()]
        logger.info("추출된 결과 수: %d", len(results))
        combined_results = " ".join(results[:k])
        return combined_results

    except Exception as e:
        logger.error("오류 발생: %s", str(e))
        return ""
    finally:
        driver.quit()

# 사용 예시
if __name__ == "__main__":
    image_path = "uploads/test.webp"  # 실제 이미지 파일 경로로 수정
    result = search_by_image_link_bing(image_path, k=5)
    if result:
        print("추출된 결과:")
        print(result)
    else:
        print("검색 결과 추출에 실패했습니다.")

# %%
from duckduckgo_search import DDGS
def get_search_results(query: str):
    results = []
    pages = 1
    try:
        ddg_results = DDGS().text(query, max_results=pages * 10)
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
get_search_results("apple news")
# %%
import requests
import time
import logging
import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor
from duckduckgo_search import DDGS

import warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0'
}

TIMEOUT = 30  # 초
MAX_RETRIES = 3
RETRY_DELAY = 1  # 초

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
    readability 라이브러리 사용 시도를 하고, 실패하면 기존 방식으로 재시도합니다.
    또한, 페이지 내의 <iframe> 태그 내의 콘텐츠도 추출합니다.
    """
    if visited is None:
        visited = set()
    main_text = ""
    try:
        from readability import Document
        doc = Document(html_content)
        main_html = doc.summary()
        soup = BeautifulSoup(main_html, 'lxml')
        main_text = soup.get_text(separator=' ', strip=True)
        main_text = re.sub(r'\s+', ' ', main_text).strip()
    except Exception as e:
        logger.error(f"Readability 추출 실패: {e}. 기존 방식으로 재시도합니다.")
        if not html_content:
            return ""
        soup = BeautifulSoup(html_content, 'lxml')
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
    
    # iframe 내의 콘텐츠도 추가 추출
    if session is not None:
        original_soup = BeautifulSoup(html_content, 'lxml')
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
    """URL에서 HTML을 가져와 텍스트를 추출 후 결과 딕셔너리로 반환."""
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

class SearchAndExtract:
    """
    이 클래스는 DuckDuckGo를 활용해 검색을 수행하고,
    검색 결과의 링크에서 본문 텍스트를 추출하여 각 결과에 'main' 키에 저장하는 기능을 제공합니다.
    
    반환 형식 예시:
    [
      {
        'title': 'Apple News+ - Apple',
        'link': 'https://www.apple.com/apple-news/',
        'snippet': 'Apple News+ offers access ...',
        'main': '해당 링크에서 추출된 본문 텍스트'
      },
      ...
    ]
    """
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.session = requests.Session()

    def get_search_results(self, query: str) -> list:
        """DuckDuckGo 검색 결과를 받아 title, link, snippet만 반환합니다."""
        results = []
        pages = 1
        try:
            ddg_results = DDGS().text(query, max_results=pages * 10)
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
                # 중복 링크 제거
                if all(r.get('link') != href for r in results):
                    results.append(result_item)
        except Exception as e:
            logger.error(f"DuckDuckGo 검색 오류: {e}")
        return results

    def extract_main_from_url(self, url: str) -> str:
        """단일 URL에서 본문 텍스트 추출."""
        result = process_url(url, self.session)
        return result["text"] if result["success"] else ""
    
    def extract_main_from_urls(self, urls: list) -> dict:
        """
        여러 URL을 병렬 처리하여, 각 URL에 대해 본문 텍스트 추출 결과를
        {url: 추출된 텍스트} 형식의 딕셔너리로 반환합니다.
        """
        extracted = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {executor.submit(self.extract_main_from_url, url): url for url in urls}
            for future in future_to_url:
                url = future_to_url[future]
                try:
                    extracted[url] = future.result()
                except Exception as exc:
                    logger.error(f"Error processing {url}: {exc}")
                    extracted[url] = ""
        return extracted

    def run(self, query: str) -> list:
        """
        주어진 쿼리로 DuckDuckGo 검색 후, 각 결과 링크에서 메인 텍스트를 추출하여
        검색 결과 딕셔너리에 'main' 키에 해당 텍스트를 추가한 후 리스트로 반환합니다.
        """
        search_results = self.get_search_results(query)
        links = [item["link"] for item in search_results if item.get("link")]
        main_mapping = self.extract_main_from_urls(links)
        for item in search_results:
            item["main"] = main_mapping.get(item["link"], "")
        return search_results

if __name__ == "__main__":
    query = "apple news"
    sea = SearchAndExtract(max_workers=10)
    results = sea.run(query)
    for res in results:
        print(res)
# %%
import requests
import time
import logging
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor
from duckduckgo_search import DDGS

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

if __name__ == "__main__":
    query = "한국 뉴스"
    result_list = search_and_extract(query)
    for item in result_list:
        print(item)
# %%
