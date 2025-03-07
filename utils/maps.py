import json
import requests
import logging
import googlemaps
from .distance import haversine_distance
from config import GMAPS_API_KEY
import numpy as np

def search_nearby_places(latitude: float, longitude: float, keyword: str) -> list:
    """
    주어진 위치 주변의 장소들을 검색합니다.
    
    Parameters:
        latitude, longitude: 중심 위치의 위도와 경도
        keyword: 검색 키워드
        
    Returns:
        가까운 순서대로 정렬된 장소 목록
    """
    radius=1000
    k=20
    language='ko'

    try:
        gmaps = googlemaps.Client(key=GMAPS_API_KEY)
        location = (latitude, longitude)
        places_result = gmaps.places_nearby(location=location, radius=radius, language=language, keyword=keyword)
        temp_places = []
        
        for place in places_result.get('results', []):
            loc_data = place.get("geometry", {}).get("location", {})
            lat2 = loc_data.get('lat')
            lng2 = loc_data.get('lng')
            
            if lat2 is None or lng2 is None:
                continue
                
            filtered_place = {
                "name": place.get("name", ""),
                "location": (lat2, lng2),
                "open_now": place.get("opening_hours", {}).get("open_now", None),
                "rating": place.get("rating", None),
                "types": place.get("types", []),
                "distance": haversine_distance(latitude, longitude, lat2, lng2)
            }
            temp_places.append(filtered_place)
            
        temp_places.sort(key=lambda x: x["distance"])
        return temp_places[:min(k, 20)]
    except Exception as e:
        logging.error(f"주변 장소 검색 오류: {e}")
        return []

def compute_route_matrix(origin, destinations, travel_mode="DRIVE", waypoints=None):
    """
    출발지에서 목적지들까지의 경로 정보를 계산합니다.
    
    Parameters:
        origin: 출발지 좌표 (위도, 경도)
        destinations: 목적지 좌표 목록 [(위도1, 경도1), (위도2, 경도2), ...]
        travel_mode: 이동 방식 ("DRIVE", "WALK" 등)
        waypoints: 경유지 좌표 목록 (선택 사항)
        
    Returns:
        경로 정보 목록
    """
    try:
        url = 'https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix'
        headers = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': GMAPS_API_KEY,
            'X-Goog-FieldMask': 'originIndex,destinationIndex,duration,distanceMeters,status,condition'
        }
        
        formatted_origins = [{
            "waypoint": {
                "location": {
                    "latLng": {
                        "latitude": origin[0],
                        "longitude": origin[1]
                    }
                }
            }
        }]
        
        if waypoints:
            for waypoint in waypoints:
                formatted_origins.append({
                    "waypoint": {
                        "location": {
                            "latLng": {
                                "latitude": waypoint[0],
                                "longitude": waypoint[1]
                            }
                        }
                    }
                })
                
        formatted_destinations = []
        for dest in destinations:
            formatted_destinations.append({
                "waypoint": {
                    "location": {
                        "latLng": {
                            "latitude": dest[0],
                            "longitude": dest[1]
                        }
                    }
                }
            })
            
        payload = {
            "origins": formatted_origins,
            "destinations": formatted_destinations,
            "travelMode": travel_mode
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response_data = response.json()
        
        filtered_list = []
        if 'originDestinationPairs' in response_data and response_data['originDestinationPairs']:
            routes = response_data['originDestinationPairs'][0]['routeInfo']
            valid_routes = [route for route in routes if route.get('condition') == 'ROUTE_EXISTS']
            if valid_routes:
                sorted_routes = sorted(valid_routes, key=lambda x: x.get('distanceMeters', float('inf')))
                filtered_list = [{"DistanceMeters": i['distanceMeters'], "Duration": i['duration']} for i in sorted_routes]
                return filtered_list
                
        filtered_list = [{"DistanceMeters": i.get('distanceMeters'), "Duration": i.get('duration')} for i in response_data]
        return filtered_list
    except Exception as e:
        logging.error(f"경로 계산 오류: {e}")
        return []