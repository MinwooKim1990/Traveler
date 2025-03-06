# %%
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
from webdriver_manager.chrome import ChromeDriverManager
import os
import requests
from PIL import Image
from io import BytesIO

def search_similar_images(image_path, num_results=5):
    """
    이미지 파일을 기반으로 구글 이미지 검색을 수행하고 가장 유사한 이미지 결과를 반환합니다.
    
    Args:
        image_path (str): 검색할 이미지 파일의 경로
        num_results (int): 반환할 결과 개수 (기본값: 5)
        
    Returns:
        list: 유사 이미지 URL 목록
    """
    # Chrome Driver 설정
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 브라우저 창 없이 실행
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")  # 화면 크기 설정

    # ChromeDriverManager를 사용하여 자동으로 드라이버 설치 및 경로 설정
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Google 이미지 검색 페이지 열기
        driver.get("https://www.google.com/imghp")
        time.sleep(2)  # 페이지 로딩 대기

        # 이미지 파일 경로 확인
        if not os.path.isabs(image_path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            image_path = os.path.abspath(os.path.join(current_dir, "..", image_path))
        
        print(f"검색할 이미지 경로: {image_path}")

        # 구글 이미지 검색 페이지에서 이미지 검색 버튼 찾기
        try:
            # 카메라 아이콘 찾기 (새로운 UI)
            search_by_image_btn = driver.find_element(By.CSS_SELECTOR, ".nDcEnd")
            search_by_image_btn.click()
            time.sleep(1)
        except:
            try:
                # 다른 가능한 선택자 시도
                search_by_image_btn = driver.find_element(By.XPATH, "//div[@aria-label='이미지로 검색' or @aria-label='Search by image']")
                search_by_image_btn.click()
                time.sleep(1)
            except Exception as e:
                print(f"카메라 아이콘을 찾을 수 없습니다: {e}")

        # 이미지 업로드 입력 필드 찾기
        try:
            upload_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
            upload_input.send_keys(image_path)
            print("이미지 업로드 완료")
            
            # 검색 결과 로딩 대기
            time.sleep(7)
            
            # 검색 결과 이미지 가져오기 (여러 선택자 시도)
            similar_images = []
            
            # 다양한 CSS 선택자 시도
            selectors = [
                "img.Q4LuWd", 
                ".rg_i", 
                "img.rg_i", 
                ".isv-r img", 
                ".PNCib img"
            ]
            
            for selector in selectors:
                image_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if image_elements:
                    print(f"선택자 '{selector}'로 {len(image_elements)}개 이미지 발견")
                    break
            
            # 상위 결과 추출
            for i, img in enumerate(image_elements[:num_results]):
                try:
                    # 이미지 URL 가져오기 (src 또는 data-src 속성)
                    img_url = img.get_attribute("src") or img.get_attribute("data-src")
                    
                    if img_url and not img_url.startswith("data:"):  # base64 인코딩된 이미지 제외
                        similar_images.append(img_url)
                        print(f"유사 이미지 {i+1}: {img_url}")
                except Exception as e:
                    print(f"이미지 URL 추출 중 오류: {e}")
            
            return similar_images[:num_results]
            
        except Exception as e:
            print(f"이미지 업로드 중 오류 발생: {e}")
            return []
            
    finally:
        # 브라우저 종료
        driver.quit()
        print("브라우저 세션 종료")

# 테스트 실행
if __name__ == "__main__":
    # 테스트용 이미지 경로
    test_image_path = "../uploads/gogh.jpg"
    
    # 유사 이미지 검색 실행
    similar_images = search_similar_images(test_image_path, num_results=5)
    
    # 결과 출력
    print("\n=== 검색 결과 요약 ===")
    if similar_images:
        print(f"총 {len(similar_images)}개의 유사 이미지를 찾았습니다:")
        for i, url in enumerate(similar_images):
            print(f"{i+1}. {url}")
    else:
        print("유사 이미지를 찾지 못했습니다.")

# %%
from googleapiclient import discovery
import base64

def search_image_with_google_vision(image_path, api_key="AIzaSyAsX7UxBKEmc3g_NJXzdL9yMebFOOkFOrA"):
    """
    Google Cloud Vision API를 사용하여 입력 이미지와 관련된 정보를 검색합니다.
    이 함수는 서비스 계정 파일 대신 API 키를 직접 사용합니다.
    """
    # 로컬 이미지 파일 읽기 및 base64 인코딩
    with open(image_path, 'rb') as image_file:
        content = image_file.read()
    encoded_image = base64.b64encode(content).decode('utf-8')
    
    # Vision API 서비스 초기화 (API 키 직접 사용)
    service = discovery.build('vision', 'v1', developerKey=api_key)
    
    # 웹 감지 요청 (Web Detection) 본문 구성
    request_body = {
        'requests': [{
            'image': {'content': encoded_image},
            'features': [{'type': 'WEB_DETECTION'}]
        }]
    }
    
    response = service.images().annotate(body=request_body).execute()
    
    if 'error' in response:
        raise Exception(response['error'].get('message', '알 수 없는 오류'))
    
    annotations = response.get('responses', [{}])[0].get('webDetection', {})
    
    if not annotations:
        print("검색 결과가 없습니다.")
        return

    # 관련 엔티티 출력
    web_entities = annotations.get('webEntities', [])
    if web_entities:
        print("\n=== 관련 엔티티 ===")
        for entity in web_entities:
            description = entity.get('description', '')
            score = entity.get('score', 0)
            print("설명: {}, 점수: {:.2f}".format(description, score))
    
    # 관련 페이지 출력
    pages = annotations.get('pagesWithMatchingImages', [])
    if pages:
        print("\n=== 관련 페이지 ===")
        for page in pages:
            print("URL: {}".format(page.get('url', '')))
    
    # 유사 이미지 출력
    similar_images = annotations.get('visuallySimilarImages', [])
    if similar_images:
        print("\n=== 유사 이미지 ===")
        for img in similar_images:
            print("URL: {}".format(img.get('url', '')))

if __name__ == "__main__":
    # API 키는 함수의 기본 인자로 직접 설정되어 있으므로,
    # 별도로 서비스 계정 파일을 지정하지 않습니다.
    pass

    # 검색할 이미지 경로 입력
    image_path = "../uploads/gogh.jpg"  # 로컬 이미지 파일 경로

    # 이미지 검색 실행
    search_image_with_google_vision(image_path)

# %%
import requests
import time
import random
import os
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import base64
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("image_search_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def google_reverse_image_search(image_path, top_k=5, max_retries=3):
    """
    로컬 이미지를 Selenium을 사용하여 Google 이미지 검색에 업로드하고,
    가장 유사한 이미지의 제목들을 추출합니다.
    
    Args:
        image_path (str): 로컬 이미지 파일 경로.
        top_k (int): 추출할 결과 개수.
        max_retries (int): 최대 재시도 횟수.
    
    Returns:
        list: 유사 이미지 제목의 리스트.
    """
    logger.info(f"이미지 검색 시작: {image_path}")
    
    # 크롬 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 헤드리스 모드
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = None
    try:
        # 웹드라이버 초기화
        logger.info("웹드라이버 초기화 중...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Google 이미지 검색 페이지 열기
        driver.get("https://www.google.com/imghp?hl=ko")
        logger.info("Google 이미지 검색 페이지 로드됨")
        
        # 쿠키 동의 처리 (필요한 경우)
        try:
            cookie_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., '동의함') or contains(., 'I agree') or contains(., 'Accept')]"))
            )
            cookie_button.click()
            logger.info("쿠키 동의 버튼 클릭됨")
        except Exception as e:
            logger.info(f"쿠키 동의 버튼 없음 또는 클릭 실패: {e}")
        
        # 이미지 검색 버튼 클릭
        for attempt in range(max_retries):
            try:
                # 이미지 검색 아이콘 클릭
                search_by_image = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[@aria-label='이미지로 검색' or @aria-label='Search by image' or contains(@title, 'Search by image')]"))
                )
                search_by_image.click()
                logger.info("이미지 검색 아이콘 클릭됨")
                
                # 파일 업로드 탭 클릭
                upload_tab = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '파일 업로드') or contains(text(), 'Upload an image')]"))
                )
                upload_tab.click()
                logger.info("파일 업로드 탭 클릭됨")
                
                # 파일 업로드 입력 필드 찾기
                file_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
                )
                
                # 이미지 파일 업로드
                absolute_path = os.path.abspath(image_path)
                file_input.send_keys(absolute_path)
                logger.info(f"이미지 파일 업로드됨: {absolute_path}")
                
                # 검색 결과 로딩 대기
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".g, .rg_bx, .isv-r"))
                )
                logger.info("검색 결과 로드됨")
                
                # 결과 추출
                results = []
                
                # 유사 이미지 제목 추출 시도
                selectors = [
                    ".isv-r .VFACy", # 이미지 결과 제목
                    ".g h3", # 웹 결과 제목
                    ".LC20lb", # 일반 검색 결과 제목
                    ".DKV0Md" # 이미지 결과 설명
                ]
                
                for selector in selectors:
                    try:
                        elements = WebDriverWait(driver, 5).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                        )
                        logger.info(f"선택자 '{selector}'로 {len(elements)}개 요소 발견")
                        
                        for element in elements[:top_k]:
                            title = element.text.strip()
                            if title and title not in results:
                                results.append(title)
                                logger.info(f"제목 추출: {title}")
                        
                        if results:
                            break
                    except Exception as e:
                        logger.warning(f"선택자 '{selector}' 처리 중 오류: {e}")
                
                # 결과가 없으면 페이지 소스에서 추출 시도
                if not results:
                    logger.info("선택자로 결과를 찾지 못함. 페이지 소스에서 추출 시도")
                    page_source = driver.page_source
                    
                    # 디버깅을 위해 페이지 소스 저장
                    with open("page_source_debug.html", "w", encoding="utf-8") as f:
                        f.write(page_source)
                    logger.info("페이지 소스를 'page_source_debug.html'에 저장함")
                    
                    # 스크린샷 저장
                    driver.save_screenshot("search_result_debug.png")
                    logger.info("스크린샷을 'search_result_debug.png'에 저장함")
                    
                    # 페이지 제목 추출 (대안)
                    try:
                        title_element = driver.find_element(By.TAG_NAME, "title")
                        if title_element.text and "이미지" in title_element.text:
                            results.append(title_element.text.replace(" - Google 검색", "").strip())
                            logger.info(f"페이지 제목에서 추출: {results[-1]}")
                    except Exception as e:
                        logger.warning(f"페이지 제목 추출 실패: {e}")
                
                if results:
                    return results[:top_k]
                else:
                    logger.warning(f"검색 결과를 찾을 수 없음, 재시도 중... ({attempt+1}/{max_retries})")
                    time.sleep(3 + random.random() * 2)
            
            except Exception as e:
                logger.error(f"검색 과정 중 오류 발생: {e}, 재시도 중... ({attempt+1}/{max_retries})")
                driver.save_screenshot(f"error_screenshot_{attempt}.png")
                logger.info(f"오류 스크린샷 저장: error_screenshot_{attempt}.png")
                time.sleep(5 + random.random() * 5)
                
                # 드라이버 재시작
                if driver:
                    driver.quit()
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.get("https://www.google.com/imghp?hl=ko")
        
        # 모든 재시도 실패 후
        logger.error("모든 재시도 실패. 대체 결과 반환")
        return ["검색 결과를 가져올 수 없습니다."]
        
    finally:
        # 브라우저 종료
        if driver:
            driver.quit()
            logger.info("웹드라이버 종료됨")

if __name__ == "__main__":
    image_path = "../uploads/gogh.jpg"
    try:
        logger.info("테스트 실행 시작")
        titles = google_reverse_image_search(image_path, top_k=5)
        print("\n=== 유사 이미지 검색 결과 ===")
        if titles and titles[0] != "검색 결과를 가져올 수 없습니다.":
            print(f"총 {len(titles)}개의 유사 이미지 제목을 찾았습니다:")
            for idx, title in enumerate(titles, start=1):
                print(f"{idx}. {title}")
        else:
            print("유사 이미지 제목을 찾지 못했습니다.")
        logger.info("테스트 실행 완료")
    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {e}")
        print(f"오류 발생: {e}")
        print("자세한 내용은 로그 파일을 확인하세요: image_search_debug.log")


# %%
import base64

def convert_image_to_base64(image_path):
    """
    로컬 이미지 파일을 읽어 base64 문자열로 변환하는 함수입니다.
    
    매개변수:
        image_path (str): 변환할 이미지 파일 경로.
        
    반환값:
        str: base64로 인코딩된 이미지 데이터.
    """
    try:
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            return encoded_image
    except Exception as e:
        print(f"이미지 변환 중 오류 발생: {e}")
        return None

if __name__ == "__main__":
    # 테스트용 이미지 파일 경로 (필요에 따라 수정)
    test_image_path = "../uploads/gogh.jpg"
    base64_result = convert_image_to_base64(test_image_path)
    if base64_result:
        print("Base64 인코딩 결과:")
        print(base64_result)
    else:
        print("인코딩에 실패했습니다. 파일 경로나 이미지 파일 내용을 재확인해 주세요.")


# %%
