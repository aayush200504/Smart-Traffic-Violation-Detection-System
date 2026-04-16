"""
High-Speed, High-Accuracy ANPR Module  (Blur Recovery + Plate Border)
======================================================================
Primary  : EasyOCR  (deep-learning, handles real-world plates well)
Fallback : Tesseract (multiple PSM configs)

Key Improvements
-----------------
* Returns (plate_text, accuracy, bbox) via extract_plate_text_full()
* Draws glowing neon bounding-box around the detected plate region
* Aggressive multi-strategy region detection
* Relaxed regex + smart character correction to avoid UNKNOWN
* Blur / unsharp-mask / CLAHE enhancement pipeline for degraded images
"""

import cv2
import re
import numpy as np
import pytesseract
import os
import threading
from collections import Counter

# ── Tesseract path (Windows) ──────────────────────────────────────────────────
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ── Indian number-plate regex  (strict → used for scoring) ───────────────────
PLATE_RE = re.compile(
    r'([A-Z]{2})\s*(\d{1,2})\s*([A-Z]{1,3})\s*(\d{4})'
)

# Relaxed regex – looser on separators / character positions (fallback)
PLATE_RE_LOOSE = re.compile(
    r'([A-Z]{2})\s*(\d{1,2})\s*([A-Z]{0,3})\s*(\d{3,4})'
)

INDIAN_STATE_CODES = {
    'AN','AP','AR','AS','BR','CH','CG','DD','DL','DN','GA','GJ','HP','HR',
    'JH','JK','KA','KL','LA','LD','MH','ML','MN','MP','MZ','NL','OD','PB',
    'PY','RJ','SK','TN','TR','TS','UK','UP','WB'
}

# OCR confusion fixers  (position-aware)
OCR_FIX_STATE  = str.maketrans('01BSGOIQD8', 'OIBSG0OID8')
OCR_FIX_DIGITS = str.maketrans('OIQBSDGZ',   '01085060')

# ── EasyOCR singleton ─────────────────────────────────────────────────────────
_easyocr_reader  = None
_easyocr_lock    = threading.Lock()
_easyocr_ready   = threading.Event()
EASYOCR_AVAILABLE = False

try:
    import easyocr as _easyocr_module
    EASYOCR_AVAILABLE = True
    print("[ANPR] EasyOCR found – will initialise on first use (or via prewarm)")
except ImportError:
    print("[ANPR] EasyOCR not installed – falling back to Tesseract only")


def _init_easyocr():
    global _easyocr_reader
    models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    os.makedirs(models_dir, exist_ok=True)
    print("[ANPR] Initialising EasyOCR reader …")
    _easyocr_reader = _easyocr_module.Reader(
        ['en'],
        gpu=False,
        verbose=False,
        model_storage_directory=models_dir,
        download_enabled=True,
    )
    _easyocr_ready.set()
    print("[ANPR] EasyOCR ready ✓")


def _get_easyocr():
    if not EASYOCR_AVAILABLE:
        return None
    global _easyocr_reader
    if _easyocr_reader is not None:
        return _easyocr_reader
    with _easyocr_lock:
        if _easyocr_reader is None:
            _init_easyocr()
    return _easyocr_reader


def prewarm():
    if EASYOCR_AVAILABLE and _easyocr_reader is None:
        t = threading.Thread(target=_init_easyocr, daemon=True, name="easyocr-prewarm")
        t.start()
        return t


# ── Blur / Quality Detection ──────────────────────────────────────────────────
def _laplacian_variance(gray):
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def _is_blurry(gray, threshold=80.0):
    return _laplacian_variance(gray) < threshold


def _blur_score_to_pct(var):
    return int(min(100, max(0, (var - 10) / (500 - 10) * 100)))


# ── Image Enhancement ─────────────────────────────────────────────────────────
def _enhance_blurry(gray):
    h, w = gray.shape[:2]
    up = cv2.resize(gray, (w * 3, h * 3), interpolation=cv2.INTER_LANCZOS4)
    denoised = cv2.fastNlMeansDenoising(up, h=10, templateWindowSize=7, searchWindowSize=21)
    blur_layer = cv2.GaussianBlur(denoised, (0, 0), 3)
    sharpened = cv2.addWeighted(denoised, 1.8, blur_layer, -0.8, 0)
    kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]], dtype=np.float32)
    return cv2.filter2D(sharpened, -1, kernel)


def _enhance_scratchy(gray):
    h, w = gray.shape[:2]
    up  = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_LANCZOS4)
    med = cv2.medianBlur(up, 5)
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    closed = cv2.morphologyEx(med, cv2.MORPH_CLOSE, kern)
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    return clahe.apply(closed)


# ── Preprocessing ─────────────────────────────────────────────────────────────
def _preprocess_roi(roi_gray, is_degraded=False):
    h, w = roi_gray.shape[:2]
    if h == 0 or w == 0:
        return []
    if h < 60:
        scale = 60 / h
        roi_gray = cv2.resize(roi_gray, (int(w * scale), int(h * scale)),
                              interpolation=cv2.INTER_LANCZOS4)

    variants = []

    if is_degraded:
        enh_blur = _enhance_blurry(roi_gray)
        clahe2 = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        cl_enh = clahe2.apply(enh_blur)
        _, v_enh = cv2.threshold(cl_enh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(v_enh)
        variants.append(cv2.bitwise_not(v_enh))

        enh_scr = _enhance_scratchy(roi_gray)
        _, v_scr = cv2.threshold(enh_scr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(v_scr)

        v_adp = cv2.adaptiveThreshold(
            enh_blur, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        variants.append(v_adp)

    # Standard: CLAHE + Otsu
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(roi_gray)
    _, v1 = cv2.threshold(cl, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(v1)
    variants.append(cv2.bitwise_not(v1))

    # Bilateral + Adaptive
    bilat = cv2.bilateralFilter(roi_gray, 9, 75, 75)
    v2 = cv2.adaptiveThreshold(
        bilat, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    variants.append(v2)

    # Extra: simple Otsu on raw
    _, v3 = cv2.threshold(roi_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(v3)
    variants.append(cv2.bitwise_not(v3))

    return variants


# ── Plate Region Detection ────────────────────────────────────────────────────
def _find_plate_regions(img):
    """
    Multi-strategy region detection – returns deduplicated (x,y,w,h) list.
    Strategy 1: HSV colour segmentation (white/yellow/green plates)
    Strategy 2: Morphological blackhat (dark chars on light bg)
    Strategy 3: Canny edge + rectangle
    Strategy 4: MSER text regions (catches hard cases)
    """
    h_img, w_img = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    candidates = []

    # ── Strategy 1: colour segmentation ──────────────────────────────────────
    white_mask  = cv2.inRange(hsv, (0,   0, 160), (180,  60, 255))
    yellow_mask = cv2.inRange(hsv, (15, 100,  80), (35, 255, 255))
    green_mask  = cv2.inRange(hsv, (40,  50,  80), (80, 255, 255))
    combined = cv2.bitwise_or(white_mask, cv2.bitwise_or(yellow_mask, green_mask))

    kern_close = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 6))
    kern_open  = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kern_close)
    combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN,  kern_open)

    cnts, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(cnts, key=cv2.contourArea, reverse=True)[:15]:
        x, y, w, h = cv2.boundingRect(c)
        ar   = w / float(h) if h else 0
        area = w * h
        if 1.8 <= ar <= 8.0 and 800 <= area <= h_img * w_img * 0.35:
            pad = max(4, int(h * 0.12))
            x1, y1 = max(0, x-pad), max(0, y-pad)
            x2, y2 = min(w_img, x+w+pad), min(h_img, y+h+pad)
            candidates.append((x1, y1, x2-x1, y2-y1))

    # ── Strategy 2: morphological blackhat ───────────────────────────────────
    for kw in [14, 17, 27, 40]:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, 5))
        bh     = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
        _, thr = cv2.threshold(bh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thr    = cv2.dilate(thr, None, iterations=2)
        cnts2, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in sorted(cnts2, key=cv2.contourArea, reverse=True)[:10]:
            x, y, w, h = cv2.boundingRect(c)
            ar = w / float(h) if h else 0
            if 1.5 <= ar <= 9.5 and w * h > 600:
                pad = max(3, int(h * 0.08))
                x1, y1 = max(0, x-pad), max(0, y-pad)
                x2, y2 = min(w_img, x+w+pad), min(h_img, y+h+pad)
                candidates.append((x1, y1, x2-x1, y2-y1))

    # ── Strategy 3: Canny + rectangular contours ──────────────────────────────
    blur  = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 180)
    edges = cv2.dilate(edges, None, iterations=1)
    cnts3, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(cnts3, key=cv2.contourArea, reverse=True)[:25]:
        peri   = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.022 * peri, True)
        if len(approx) in (4, 5, 6):
            x, y, w, h = cv2.boundingRect(approx)
            ar = w / float(h) if h else 0
            if 1.8 <= ar <= 8.0 and 800 <= w * h <= h_img * w_img * 0.35:
                candidates.append((x, y, w, h))

    # ── Strategy 4: Scan the lower half systematically (plates are usually low) ─
    # Divide lower 60% of image into horizontal strips and score them
    y_start = int(h_img * 0.25)
    strip_h = max(20, h_img // 12)
    for sy in range(y_start, h_img - strip_h, strip_h // 2):
        strip = gray[sy:sy+strip_h, :]
        var   = _laplacian_variance(strip)
        if var > 50:                          # only sharpish strips
            _, thr = cv2.threshold(strip, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            cntsS, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in sorted(cntsS, key=cv2.contourArea, reverse=True)[:5]:
                x, y, w, h = cv2.boundingRect(c)
                ar = w / float(h) if h else 0
                if 2.0 <= ar <= 7.5 and w * h > 600:
                    candidates.append((x, sy + y, w, h))

    # ── Deduplicate overlapping regions ───────────────────────────────────────
    seen, unique = [], []
    for (x, y, w, h) in candidates:
        cx, cy = x + w // 2, y + h // 2
        duplicate = False
        for sx, sy, sw, sh in seen:
            if (abs(cx - (sx + sw // 2)) < sw * 0.55 and
                    abs(cy - (sy + sh // 2)) < sh * 0.55):
                duplicate = True
                break
        if not duplicate:
            seen.append((x, y, w, h))
            unique.append((x, y, w, h))

    return unique


# ── OCR helpers ───────────────────────────────────────────────────────────────
_TESS_CONFIGS = [
    '--oem 3 --psm 8  -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
    '--oem 3 --psm 7  -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
    '--oem 3 --psm 13 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
    '--oem 3 --psm 6  -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
    '--oem 1 --psm 8  -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
]


def _tesseract_ocr(img_gray, extra_psm=False):
    configs = _TESS_CONFIGS if extra_psm else _TESS_CONFIGS[:2]
    results = []
    for cfg in configs:
        try:
            raw = pytesseract.image_to_string(img_gray, config=cfg)
            results.append(re.sub(r'[^A-Z0-9\s]', '', raw.upper().strip()))
        except Exception:
            pass
    return ' '.join(results)


def _easyocr_on(img_bgr):
    reader = _get_easyocr()
    if reader is None:
        return []
    try:
        results = reader.readtext(
            img_bgr,
            detail=1,
            paragraph=False,
            allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ',
            batch_size=4,
        )
        return [(text.upper().strip(), conf) for (_, text, conf) in results if conf > 0.05]
    except Exception as ex:
        print(f"[ANPR] EasyOCR error: {ex}")
        return []


# ── Candidate scoring & correction ───────────────────────────────────────────
def _score_and_fix(raw_text):
    """
    Clean raw OCR text, apply correction, score against Indian plate format.
    Returns (score, corrected_plate_string).
    score == 0 means no valid plate found.
    Tries strict regex first, then loose regex.
    """
    text = re.sub(r'[^A-Z0-9]', '', raw_text.upper())
    if len(text) < 6:
        return 0, text

    # ── Strict match ──────────────────────────────────────────────────────────
    for pattern in (PLATE_RE, PLATE_RE_LOOSE):
        m = pattern.search(text)
        if m:
            groups = m.groups()
            state   = groups[0].translate(OCR_FIX_STATE)
            d1      = ''.join(c.translate(OCR_FIX_DIGITS) if c.isalpha() else c for c in groups[1])
            letters = ''.join(c.translate(OCR_FIX_STATE)  if c.isdigit() else c for c in groups[2])
            d2      = ''.join(c.translate(OCR_FIX_DIGITS) if c.isalpha() else c for c in groups[3])

            corrected = state + d1 + letters + d2

            score = 0
            if state in INDIAN_STATE_CODES:
                score += 60
            if len(d2) == 4:
                score += 20
            if 1 <= len(letters) <= 3:
                score += 10
            if len(d1) in (1, 2):
                score += 5
            score += len(corrected)
            return score, corrected

    # ── No regex match – try aggressive single-block correction ───────────────
    # If text looks like a plate (8-10 alphanums) attempt position-based fix
    if 7 <= len(text) <= 12:
        fixed = []
        for i, ch in enumerate(text):
            if i < 2:        # state code position – should be alpha
                fixed.append(ch.translate(OCR_FIX_STATE) if ch.isdigit() else ch)
            elif i < 4:      # district number – should be digit
                fixed.append(ch.translate(OCR_FIX_DIGITS) if ch.isalpha() else ch)
            elif i < 6:      # series letters – should be alpha
                fixed.append(ch.translate(OCR_FIX_STATE) if ch.isdigit() else ch)
            else:            # registration number – should be digit
                fixed.append(ch.translate(OCR_FIX_DIGITS) if ch.isalpha() else ch)
        corrected = ''.join(fixed)
        m2 = PLATE_RE.search(corrected)
        if m2:
            score = 30 + len(corrected)
            if corrected[:2] in INDIAN_STATE_CODES:
                score += 30
            return score, corrected

    return 0, text


# ── Accuracy score ────────────────────────────────────────────────────────────
def _compute_accuracy(winner_score, max_possible_score, blur_var,
                      easyocr_conf, is_degraded, candidates):
    pattern_pct   = min(100, int(winner_score / max(max_possible_score, 1) * 100))
    conf_pct      = int(easyocr_conf * 100) if easyocr_conf is not None else 50
    quality_pct   = _blur_score_to_pct(blur_var)

    if candidates:
        plates = [p for _, p in candidates]
        freq   = Counter(plates)
        top    = max(plates, key=lambda p: freq[p])
        agreement_pct = int(freq[top] / max(len(plates), 1) * 100)
    else:
        agreement_pct = 0

    raw = (pattern_pct  * 0.40 +
           conf_pct     * 0.30 +
           quality_pct  * 0.15 +
           agreement_pct * 0.15)

    if is_degraded:
        raw *= 0.92

    return max(0, min(100, int(round(raw))))


# ── Full extraction (returns plate, accuracy, best_bbox) ─────────────────────
def extract_plate_text_full(image_path):
    """
    Returns (plate_str | None, accuracy_int, best_bbox | None)
    best_bbox = (x, y, w, h) in the ORIGINAL (possibly downscaled) image coords.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            print(f"[ANPR] Could not load image: {image_path}")
            return None, 0, None

        orig_h, orig_w = img.shape[:2]

        # Resize to ≤900 px
        if max(orig_h, orig_w) > 900:
            scale = 900 / max(orig_h, orig_w)
            img = cv2.resize(img, (int(orig_w * scale), int(orig_h * scale)),
                             interpolation=cv2.INTER_AREA)
        proc_h, proc_w = img.shape[:2]
        scale_back_x = orig_w / proc_w
        scale_back_y = orig_h / proc_h

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        blur_var    = _laplacian_variance(gray)
        is_degraded = _is_blurry(gray)
        print(f"[ANPR] Laplacian variance={blur_var:.1f}, degraded={is_degraded}")

        if is_degraded:
            enhanced_full = _enhance_blurry(gray)
            img_for_ocr   = cv2.cvtColor(enhanced_full, cv2.COLOR_GRAY2BGR)
        else:
            img_for_ocr = img

        all_candidates = []      # (score, plate_str)
        bbox_map       = {}      # plate_str → (x,y,w,h)  first occurrence bbox
        best_easyocr_conf = None

        # ══════════════════════════════════════════════════════════════════════
        # PASS 1 – EasyOCR on full image
        # ══════════════════════════════════════════════════════════════════════
        if EASYOCR_AVAILABLE:
            for text, conf in _easyocr_on(img_for_ocr):
                score, fixed = _score_and_fix(text)
                if score > 0:
                    weighted = score + int(conf * 35)
                    all_candidates.append((weighted, fixed))
                    if best_easyocr_conf is None or conf > best_easyocr_conf:
                        best_easyocr_conf = conf
                    print(f"[ANPR-P1] EasyOCR full: '{fixed}'  score={weighted}")

        # ══════════════════════════════════════════════════════════════════════
        # PASS 2 – ROI-based detection
        # ══════════════════════════════════════════════════════════════════════
        regions = _find_plate_regions(img)
        print(f"[ANPR] {len(regions)} plate region(s) detected")

        for (x, y, rw, rh) in regions[:8]:
            if rw <= 0 or rh <= 0:
                continue
            roi_bgr  = img[y:y+rh, x:x+rw]
            roi_gray = gray[y:y+rh, x:x+rw]

            roi_is_degraded = _is_blurry(roi_gray, threshold=60.0)

            bgr_variants_for_easy = [roi_bgr]
            if roi_is_degraded:
                enh_roi = _enhance_blurry(roi_gray)
                bgr_variants_for_easy.append(cv2.cvtColor(enh_roi, cv2.COLOR_GRAY2BGR))

            if EASYOCR_AVAILABLE:
                for bgr_var in bgr_variants_for_easy:
                    for text, conf in _easyocr_on(bgr_var):
                        score, fixed = _score_and_fix(text)
                        if score > 0:
                            weighted = score + int(conf * 50)
                            all_candidates.append((weighted, fixed))
                            if fixed not in bbox_map:
                                bbox_map[fixed] = (x, y, rw, rh)
                            if best_easyocr_conf is None or conf > best_easyocr_conf:
                                best_easyocr_conf = conf
                            print(f"[ANPR-P2] EasyOCR ROI: '{fixed}'  score={weighted} conf={conf:.2f}")

            for variant in _preprocess_roi(roi_gray, is_degraded=roi_is_degraded):
                raw = _tesseract_ocr(variant, extra_psm=roi_is_degraded)
                for m in PLATE_RE.finditer(raw):
                    cand = re.sub(r'\s+', '', m.group(0).upper())
                    score, fixed = _score_and_fix(cand)
                    if score > 0:
                        all_candidates.append((score, fixed))
                        if fixed not in bbox_map:
                            bbox_map[fixed] = (x, y, rw, rh)
                        print(f"[ANPR-P2] Tesseract ROI: '{fixed}'  score={score}")

            # Also try Tesseract on the loose pattern
            for variant in _preprocess_roi(roi_gray, is_degraded=roi_is_degraded):
                raw = _tesseract_ocr(variant, extra_psm=True)
                for m in PLATE_RE_LOOSE.finditer(raw):
                    cand = re.sub(r'\s+', '', m.group(0).upper())
                    score, fixed = _score_and_fix(cand)
                    if score > 0:
                        all_candidates.append((score, fixed))
                        if fixed not in bbox_map:
                            bbox_map[fixed] = (x, y, rw, rh)

            if all_candidates and max(s for s, _ in all_candidates) >= 90:
                break

        # ══════════════════════════════════════════════════════════════════════
        # PASS 3 – Tesseract on full image (pure fallback)
        # ══════════════════════════════════════════════════════════════════════
        if not all_candidates:
            for variant in _preprocess_roi(gray, is_degraded=is_degraded):
                raw = _tesseract_ocr(variant, extra_psm=is_degraded)
                for pattern in (PLATE_RE, PLATE_RE_LOOSE):
                    for m in pattern.finditer(raw):
                        cand = re.sub(r'\s+', '', m.group(0).upper())
                        score, fixed = _score_and_fix(cand)
                        if score > 0:
                            all_candidates.append((score, fixed))
                            print(f"[ANPR-P3] Tesseract full: '{fixed}'  score={score}")

        # ══════════════════════════════════════════════════════════════════════
        # PASS 4 – EasyOCR raw text concat fallback
        #   Sometimes EasyOCR splits the plate into multiple tokens.
        #   Concatenate all tokens and try to extract a plate.
        # ══════════════════════════════════════════════════════════════════════
        if not all_candidates and EASYOCR_AVAILABLE:
            all_tokens = _easyocr_on(img_for_ocr)
            concat = ''.join(t for t, _ in all_tokens)
            score, fixed = _score_and_fix(concat)
            if score > 0:
                best_conf = max((c for _, c in all_tokens), default=0.5)
                weighted  = score + int(best_conf * 35)
                all_candidates.append((weighted, fixed))
                print(f"[ANPR-P4] EasyOCR concat: '{fixed}'  score={weighted}")

            # Also try per-region token concat
            for (x, y, rw, rh) in regions[:5]:
                roi_bgr  = img[y:y+rh, x:x+rw]
                tokens   = _easyocr_on(roi_bgr)
                concat   = ''.join(t for t, _ in tokens)
                score, fixed = _score_and_fix(concat)
                if score > 0:
                    best_conf = max((c for _, c in tokens), default=0.5)
                    weighted  = score + int(best_conf * 50)
                    all_candidates.append((weighted, fixed))
                    if fixed not in bbox_map:
                        bbox_map[fixed] = (x, y, rw, rh)
                    print(f"[ANPR-P4] EasyOCR ROI concat: '{fixed}'  score={weighted}")

        # ── Pick the winner ───────────────────────────────────────────────────
        if not all_candidates:
            print("[ANPR] No plate detected.")
            return None, 0, None

        freq   = Counter(plate for _, plate in all_candidates)
        winner = max(all_candidates, key=lambda x: x[0] + freq[x[1]] * 12)
        print(f"[ANPR] Best result: '{winner[1]}'  raw_score={winner[0]}")

        # ── Compute accuracy ──────────────────────────────────────────────────
        max_possible = 60 + 20 + 10 + 5 + 10 + 50
        accuracy = _compute_accuracy(
            winner_score=winner[0],
            max_possible_score=max_possible,
            blur_var=blur_var,
            easyocr_conf=best_easyocr_conf,
            is_degraded=is_degraded,
            candidates=all_candidates,
        )
        print(f"[ANPR] Accuracy score: {accuracy}%")

        # ── Retrieve bbox in ORIGINAL image coordinates ───────────────────────
        raw_bbox = bbox_map.get(winner[1])
        if raw_bbox:
            rx, ry, rw, rh = raw_bbox
            # scale back to original image size
            raw_bbox = (
                int(rx * scale_back_x),
                int(ry * scale_back_y),
                int(rw * scale_back_x),
                int(rh * scale_back_y),
            )

        return winner[1], accuracy, raw_bbox

    except Exception as ex:
        import traceback
        print(f"[ANPR] Unhandled error: {ex}")
        traceback.print_exc()
        return None, 0, None


# ── Backward-compat wrappers ──────────────────────────────────────────────────
def extract_plate_text(image_path, full_result=False):
    plate, accuracy, _ = extract_plate_text_full(image_path)
    if full_result:
        return plate, accuracy
    return plate


# ── Annotation: draw glowing plate border on the image ────────────────────────
def draw_plate_annotation(image_path, plate_text, output_path,
                          accuracy=None, bbox=None):
    """
    Draws:
      - A glowing neon-green bounding box around the detected plate (if bbox given)
      - A semi-transparent dark bar at bottom with plate text + accuracy
    Saves result to output_path.
    """
    img = cv2.imread(image_path)
    if img is None:
        return
    h, w = img.shape[:2]

    # ── Glowing plate border ──────────────────────────────────────────────────
    if bbox:
        bx, by, bw, bh = bbox
        # Clamp to image bounds
        bx = max(0, bx); by = max(0, by)
        bx2 = min(w, bx + bw); by2 = min(h, by + bh)
        if bx2 > bx and by2 > by:
            # Glow effect: draw thick blurred neon rect then sharp rect on top
            glow_color = (0, 255, 100)   # neon green
            # Layer 1 – thick blurred glow
            glow = img.copy()
            cv2.rectangle(glow, (bx - 4, by - 4), (bx2 + 4, by2 + 4), glow_color, 12)
            img = cv2.addWeighted(cv2.GaussianBlur(glow, (21, 21), 0), 0.55, img, 0.45, 0)
            # Layer 2 – medium glow
            cv2.rectangle(img, (bx - 2, by - 2), (bx2 + 2, by2 + 2), glow_color, 4)
            # Layer 3 – crisp border
            cv2.rectangle(img, (bx, by), (bx2, by2), (0, 255, 80), 2)
            # Corner accents
            corner_len = max(10, min(bw, bh) // 4)
            thick = 3
            for cx, cy, dx, dy in [
                (bx, by, 1, 1), (bx2, by, -1, 1),
                (bx, by2, 1, -1), (bx2, by2, -1, -1)
            ]:
                cv2.line(img, (cx, cy), (cx + dx*corner_len, cy), (0, 255, 80), thick)
                cv2.line(img, (cx, cy), (cx, cy + dy*corner_len), (0, 255, 80), thick)

            # Small label above the box
            label = f"DETECTED: {plate_text}"
            lx = max(0, bx)
            ly = max(0, by - 10)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1)
            cv2.rectangle(img, (lx, ly - th - 4), (lx + tw + 6, ly + 2), (0, 0, 0), -1)
            cv2.putText(img, label, (lx + 3, ly - 2),
                        cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 255, 80), 1)

    # ── Bottom info bar ───────────────────────────────────────────────────────
    overlay = img.copy()
    cv2.rectangle(overlay, (0, h - 60), (w, h), (10, 15, 35), -1)
    cv2.addWeighted(overlay, 0.82, img, 0.18, 0, img)
    font = cv2.FONT_HERSHEY_DUPLEX
    cv2.putText(img, f"PLATE: {plate_text}", (10, h - 20), font, 0.7, (0, 220, 150), 2)
    cv2.putText(img, "VIOLATION DETECTED", (10, 30), font, 0.7, (0, 80, 255), 2)
    if accuracy is not None:
        acc_color = (0, 220, 80) if accuracy >= 75 else (0, 200, 255) if accuracy >= 50 else (0, 80, 255)
        cv2.putText(img, f"OCR Accuracy: {accuracy}%", (10, 60), font, 0.55, acc_color, 2)

    cv2.imwrite(output_path, img)
    print(f"[ANPR] Annotated image saved → {output_path}")
"""
Module-level __all__ for clean imports
"""
__all__ = [
    'extract_plate_text',
    'extract_plate_text_full',
    'draw_plate_annotation',
    'prewarm',
]