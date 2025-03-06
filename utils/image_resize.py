import os
import logging
from PIL import Image
from PIL import ImageOps

def resize_image(file_path, max_size_mb=7.5, quality=85):
    """
    이미지 파일 크기를 지정된 MB 이하로 줄이는 함수
    
    Parameters:
        file_path: 원본 이미지 파일 경로
        max_size_mb: 최대 파일 크기 (MB)
        quality: 압축 품질 (1-100)
        
    Returns:
        변환된 이미지 파일 경로
    """
    
    if not os.path.exists(file_path):
        logging.error(f"파일이 존재하지 않습니다: {file_path}")
        return None
    
    # 원본 파일 크기 확인
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    
    # 이미 충분히 작으면 원본 반환
    if file_size_mb <= max_size_mb:
        logging.debug(f"이미지 크기가 이미 적절함: {file_size_mb:.2f}MB")
        return file_path
    
    # 출력 파일 경로 생성 - 원본 파일명에 _resized 추가
    filename, ext = os.path.splitext(file_path)
    output_path = f"{filename}_resized{ext}"
    
    # 이미지 불러와서 크기 조정
    try:
        with Image.open(file_path) as img:
            # Adjust image orientation according to EXIF
            img = ImageOps.exif_transpose(img)
            # 이미지 정보 로깅
            logging.debug(f"원본 이미지: {file_path}, 크기: {img.size}, 용량: {file_size_mb:.2f}MB")
            
            # 초기 품질 설정
            current_quality = quality
            img_format = ext.lower().replace('.', '') or 'JPEG'
            
            # 반복적으로 크기와 품질 조정
            while True:
                # 비율 유지하며 크기 조정 (기본: 원본 크기)
                width, height = img.size
                new_size = (width, height)
                
                # 파일이 너무 크면 해상도 줄이기
                if file_size_mb > max_size_mb * 1.5:
                    scale_factor = 0.8
                    new_size = (int(width * scale_factor), int(height * scale_factor))
                    
                # 이미지 리사이즈 및 저장
                resized_img = img.resize(new_size, Image.LANCZOS)
                resized_img.save(output_path, format=img_format, quality=current_quality, optimize=True)
                
                # 새 파일 크기 확인
                new_file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                logging.debug(f"리사이즈 후: {new_size}, 품질: {current_quality}, 용량: {new_file_size_mb:.2f}MB")
                
                # 목표 크기 이하면 완료
                if new_file_size_mb <= max_size_mb:
                    logging.info(f"이미지 리사이즈 완료: {file_size_mb:.2f}MB -> {new_file_size_mb:.2f}MB")
                    return output_path
                
                # 품질 더 낮추기
                current_quality -= 10
                
                # 품질이 너무 낮아지면 해상도 조정
                if current_quality < 40:
                    width, height = new_size
                    new_size = (int(width * 0.8), int(height * 0.8))
                    current_quality = 75
                
                # 최대 10회 시도
                if width < 300 or current_quality < 20:
                    logging.warning(f"최소 크기에 도달: {new_file_size_mb:.2f}MB, 그대로 반환")
                    return output_path
    
    except Exception as e:
        logging.error(f"이미지 리사이즈 중 오류: {e}")
        return file_path
        
    return output_path

def compress_audio(file_path, max_size_mb=7.5):
    """
    오디오 파일 크기를 제한하는 함수 (향후 구현)
    """
    # 오디오 압축 로직 (필요시 구현)
    return file_path 