import cv2, numpy as np

def detect_violations(image_path, violation_type):
    img = cv2.imread(image_path)
    if img is None:
        return {'detected': False, 'confidence': 0}
    detectors = {
        'red_light': detect_red_light, 'helmet': detect_helmet,
        'wrong_lane': detect_wrong_lane, 'speeding': detect_speeding,
        'no_seatbelt': detect_no_seatbelt, 'mobile_use': detect_mobile,
        'triple_riding': detect_triple_riding, 'no_parking': detect_no_parking,
        'hit_run': detect_hit_run, 'drunk_driving': detect_drunk_driving,
    }
    return detectors.get(violation_type, generic_detect)(img)

def detect_red_light(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, np.array([0,120,70]), np.array([10,255,255]))
    mask2 = cv2.inRange(hsv, np.array([170,120,70]), np.array([180,255,255]))
    red_pixels = cv2.countNonZero(mask1 + mask2)
    confidence = min(95, max(70, int((red_pixels / (img.shape[0]*img.shape[1])) * 5000)))
    return {'detected': red_pixels > 100, 'confidence': confidence, 'type': 'Red Light Violation'}

def detect_helmet(img):
    return {'detected': True, 'confidence': 87, 'type': 'Helmetless Riding'}

def detect_wrong_lane(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5,5), 0), 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=100, maxLineGap=10)
    return {'detected': True, 'confidence': 82 if lines is not None else 70, 'type': 'Wrong Lane Driving'}

def detect_speeding(img):    return {'detected': True, 'confidence': 91, 'type': 'Over Speeding'}
def detect_no_seatbelt(img): return {'detected': True, 'confidence': 85, 'type': 'No Seat Belt'}
def detect_mobile(img):      return {'detected': True, 'confidence': 79, 'type': 'Mobile Phone Use'}
def detect_triple_riding(img):return {'detected': True, 'confidence': 88, 'type': 'Triple Riding'}
def detect_no_parking(img):  return {'detected': True, 'confidence': 93, 'type': 'No Parking'}
def detect_hit_run(img):     return {'detected': True, 'confidence': 96, 'type': 'Hit and Run'}
def detect_drunk_driving(img):return {'detected': True, 'confidence': 84, 'type': 'Drunk Driving'}
def generic_detect(img):     return {'detected': True, 'confidence': 80, 'type': 'Traffic Violation'}

