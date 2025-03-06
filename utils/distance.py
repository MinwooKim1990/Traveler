import math

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    두 지점 간의 거리를 하버사인 공식을 사용하여 계산합니다.
    
    Parameters:
        lat1, lon1: 첫 번째 지점의 위도와 경도
        lat2, lon2: 두 번째 지점의 위도와 경도
        
    Returns:
        두 지점 간의 거리 (km)
    """
    R = 6371  # 지구 반지름 (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c