# %%
import moviepy.editor as mp
import os

def convert_m4a_to_mp3_moviepy(file_path):
    """
    moviepy를 사용하여 m4a 파일을 mp3로 변환하는 함수
    
    Args:
        file_path (str): 변환할 m4a 파일 경로, None인 경우 처리
        
    Returns:
        str: 변환된 mp3 파일 경로 또는 None(오류 발생 시)
    """
    # 파일 경로가 None인 경우 처리
    if file_path is None:
        print("변환할 파일이 제공되지 않았습니다.")
        return None
        
    try:
        full_path = os.path.normpath(os.path.join(os.getcwd(), file_path))
        
        # 파일이 존재하는지 확인
        if not os.path.exists(full_path):
            print(f"파일이 존재하지 않습니다: {full_path}")
            return None
        
        # 파일 확장자 확인
        _, ext = os.path.splitext(full_path)
        if ext.lower() != '.m4a':
            # 이미 mp3이거나 다른 형식인 경우 변환 없이 원본 경로 반환
            print(f"파일이 m4a 형식이 아닙니다: {ext}. 변환 없이 원본 경로를 반환합니다.")
            return full_path
            
        output_path = os.path.splitext(full_path)[0] + '.mp3'
        
        clip = mp.AudioFileClip(full_path)
        clip.write_audiofile(output_path, bitrate="320k")
        print(f"변환 완료: {full_path} -> {output_path}")
        return output_path
    except Exception as e:
        print(f"변환 실패: {e}")
        return None

# 사용 예시
if __name__ == "__main__":
    file_path = "../uploads/녹음.m4a"
    convert_m4a_to_mp3_moviepy(file_path)
# %%