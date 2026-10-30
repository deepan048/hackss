"""
Brand Shield Guardian - Automated Logo Detection & Color/Aspect Ratio Checker
Performs OpenCV / Perceptual feature matching, aspect ratio distortion checking,
and dominant HEX color verification against approved master logo assets.
"""

import os
import io
import re
import math
import base64
import logging
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageOps, ImageChops

import numpy as np

logger = logging.getLogger("brand_shield_guardian.logo_checker")

# Check if OpenCV is available
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.info("OpenCV not installed. Using pure Pillow/NumPy perceptual vision matcher.")

# ----------------- Helper Functions -----------------
def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_clean = hex_str.strip().lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    if len(hex_clean) != 6:
        return (0, 0, 0)
    return (int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16))

def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"

def color_distance_rgb(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    """Euclidean distance in RGB color space."""
    return math.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2 + (c1[2] - c2[2])**2)

def extract_dominant_colors(pil_img: Image.Image, num_colors: int = 4) -> List[str]:
    """Extracts top non-background dominant HEX colors from an image."""
    img_rgb = pil_img.convert("RGB")
    # Resize for fast processing
    img_thumb = img_rgb.resize((100, 100), Image.Resampling.BILINEAR)

    # Quantize to 16 colors
    quantized = img_thumb.quantize(colors=16)
    palette = quantized.getpalette()[:48]  # 16 * 3
    counts = {}
    for pixel in list(quantized.getdata()):
        counts[pixel] = counts.get(pixel, 0) + 1

    sorted_palette = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    extracted_hex = []
    for idx, count in sorted_palette:
        r, g, b = palette[idx * 3 : idx * 3 + 3]
        # Ignore extreme whites / near-blacks that are typical background margins
        is_near_white = (r > 245 and g > 245 and b > 245)
        is_near_black = (r < 15 and g < 15 and b < 15)

        hex_code = rgb_to_hex(r, g, b)
        if not is_near_white and not is_near_black and hex_code not in extracted_hex:
            extracted_hex.append(hex_code)
        if len(extracted_hex) >= num_colors:
            break

    # If all were filtered out, fallback to most frequent color
    if not extracted_hex and sorted_palette:
        idx = sorted_palette[0][0]
        extracted_hex.append(rgb_to_hex(*palette[idx * 3 : idx * 3 + 3]))

    return extracted_hex

# ----------------- Logo Detection -----------------
def find_logo_in_image(
    ad_img: Image.Image,
    master_logo_img: Image.Image
) -> Tuple[Optional[Image.Image], float, Tuple[int, int, int, int]]:
    """
    Locates the master logo inside the ad creative.
    Returns (cropped_detected_logo, confidence_score, (x, y, w, h)).
    """
    ad_rgb = ad_img.convert("RGB")
    master_rgb = master_logo_img.convert("RGB")

    ad_w, ad_h = ad_rgb.size
    master_w, master_h = master_rgb.size

    # 1. OpenCV Multi-scale Template Matching if available
    if OPENCV_AVAILABLE:
        ad_cv = np.array(ad_rgb)
        ad_cv = cv2.cvtColor(ad_cv, cv2.COLOR_RGB2BGR)
        ad_gray = cv2.cvtColor(ad_cv, cv2.COLOR_BGR2GRAY)

        master_cv = np.array(master_rgb)
        master_cv = cv2.cvtColor(master_cv, cv2.COLOR_RGB2BGR)
        master_gray = cv2.cvtColor(master_cv, cv2.COLOR_BGR2GRAY)

        best_val = -1.0
        best_loc = (0, 0)
        best_w, best_h = master_w, master_h

        # Multi-scale search from 20% to 120% of original master logo size
        for scale in np.linspace(0.2, 1.2, 15):
            new_w = int(master_w * scale)
            new_h = int(master_h * scale)
            if new_w >= ad_w or new_h >= ad_h or new_w < 20 or new_h < 15:
                continue

            resized = cv2.resize(master_gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(ad_gray, resized, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_w, best_h = new_w, new_h

        if best_val >= 0.40:
            x, y = best_loc
            cropped = ad_rgb.crop((x, y, x + best_w, y + best_h))
            return cropped, float(best_val), (x, y, best_w, best_h)

    # 2. Pure Pillow & NumPy Fallback (Corner/Header/Footer Region Scoring)
    # Search common strategic brand logo regions: Top-Left, Top-Right, Top-Center, Bottom-Left, Bottom-Right
    target_regions = [
        ("top_left", (0, 0, int(ad_w * 0.45), int(ad_h * 0.35))),
        ("top_right", (int(ad_w * 0.55), 0, ad_w, int(ad_h * 0.35))),
        ("top_center", (int(ad_w * 0.25), 0, int(ad_w * 0.75), int(ad_h * 0.25))),
        ("bottom_left", (0, int(ad_h * 0.65), int(ad_w * 0.45), ad_h)),
        ("bottom_right", (int(ad_w * 0.55), int(ad_h * 0.65), ad_w, ad_h)),
        ("full_canvas", (0, 0, ad_w, ad_h))
    ]

    master_aspect = master_w / max(1, master_h)
    master_thumb = master_rgb.resize((64, int(64 / master_aspect) if master_aspect > 0 else 64))
    master_arr = np.array(master_thumb.convert("L"), dtype=np.float32)
    master_arr = (master_arr - np.mean(master_arr)) / (np.std(master_arr) + 1e-5)

    best_score = 0.0
    best_crop = None
    best_box = (0, 0, master_w, master_h)

    for region_name, box in target_regions:
        rx1, ry1, rx2, ry2 = box
        if rx2 <= rx1 or ry2 <= ry1:
            continue
        sub_img = ad_rgb.crop((rx1, ry1, rx2, ry2))
        sub_w, sub_h = sub_img.size
        if sub_w < 20 or sub_h < 20:
            continue

        sub_thumb = sub_img.resize((64, int(64 / master_aspect) if master_aspect > 0 else 64))
        sub_arr = np.array(sub_thumb.convert("L"), dtype=np.float32)
        sub_arr = (sub_arr - np.mean(sub_arr)) / (np.std(sub_arr) + 1e-5)

        # Normalized cross correlation on downscaled feature map
        corr = float(np.mean(master_arr * sub_arr))
        # Normalize into a 0-1 confidence proxy
        norm_score = max(0.0, min(1.0, (corr + 1.0) / 2.0))

        if norm_score > best_score:
            best_score = norm_score
            # Trim background margins to isolate exact logo bounding box
            bg = Image.new(sub_img.mode, sub_img.size, sub_img.getpixel((0, 0)))
            diff = ImageChops.difference(sub_img, bg)
            bbox = diff.getbbox()
            if bbox and (bbox[2] - bbox[0] > 15) and (bbox[3] - bbox[1] > 10):
                best_crop = sub_img.crop(bbox)
                best_box = (rx1 + bbox[0], ry1 + bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
            else:
                best_crop = sub_img
                best_box = (rx1, ry1, sub_w, sub_h)

    return best_crop, best_score, best_box

# ----------------- Core Logo Audit Function -----------------
def verify_ad_logo(
    ad_image_bytes: bytes,
    master_logo_path: str,
    approved_hex_colors: List[str],
    aspect_ratio_tolerance: float = 0.08
) -> Dict[str, Any]:
    """
    Complete Logo Verification Engine:
    1. Detects logo presence and bounding box.
    2. Checks aspect ratio distortion against master logo.
    3. Analyzes dominant colors and validates against approved brand palette.
    4. Generates structured audit results and violation objects.
    """
    violations = []

    if not os.path.exists(master_logo_path):
        return {
            "logo_checked": False,
            "message": f"Master logo file not found at '{master_logo_path}'.",
            "violations": []
        }

    try:
        ad_img = Image.open(io.BytesIO(ad_image_bytes))
        master_img = Image.open(master_logo_path)
    except Exception as e:
        logger.error(f"Error loading images for logo check: {e}")
        return {"logo_checked": False, "message": str(e), "violations": []}

    master_w, master_h = master_img.size
    master_aspect = master_w / max(1, master_h)

    cropped_logo, confidence, (bx, by, bw, bh) = find_logo_in_image(ad_img, master_img)

    # Check 1: Logo Presence Detection
    logo_detected = (confidence >= 0.42)
    if not logo_detected:
        violations.append({
            "issue_type": "visual_mismatch",
            "severity": "high",
            "detected_text": "Missing Brand Logo",
            "rule_violated": "Visual Identity Policy: Approved master logo must be clearly displayed.",
            "explanation": f"The official brand logo was not recognized in the submitted creative (match confidence: {int(confidence * 100)}%).",
            "evidence": "Brand guidelines mandate official brand logo presence on all published advertising.",
            "suggested_fix": "Add the official approved master logo prominently to the header or footer.",
            "confidence": 0.95
        })

    # Check 2: Aspect Ratio Distortion Check
    detected_aspect = bw / max(1, bh) if bh > 0 else master_aspect
    aspect_diff = abs(detected_aspect - master_aspect) / master_aspect
    aspect_valid = (aspect_diff <= aspect_ratio_tolerance)

    if logo_detected and not aspect_valid:
        pct_change = aspect_diff * 100
        direction = "stretched horizontally" if detected_aspect > master_aspect else "compressed / squashed vertically"
        violations.append({
            "issue_type": "visual_mismatch",
            "severity": "high",
            "detected_text": f"Logo Aspect Ratio {detected_aspect:.2f}:1 (Distorted by {pct_change:.1f}%)",
            "rule_violated": "Logo Integrity & Proportions: Never stretch, squash, or alter logo aspect ratio.",
            "explanation": f"The detected logo is {direction}. It deviates by {pct_change:.1f}% from the approved master ratio ({master_aspect:.2f}:1).",
            "evidence": f"Official master logo aspect ratio is {master_aspect:.2f}:1. Max allowable tolerance is {int(aspect_ratio_tolerance * 100)}%.",
            "suggested_fix": f"Maintain locked aspect ratio ({master_aspect:.2f}:1) when resizing the brand logo.",
            "confidence": 0.96
        })

    # Check 3: Dominant HEX Color Checker
    target_img_for_color = cropped_logo if cropped_logo else master_img
    detected_hex_colors = extract_dominant_colors(target_img_for_color, num_colors=3)

    approved_hex_clean = [c.strip().upper() for c in approved_hex_colors if c.strip()]
    if not approved_hex_clean:
        approved_hex_clean = ["#1E3A8A", "#FFFFFF"]  # default fallback

    color_valid = True
    unapproved_detected = []

    # Check if detected primary color is within acceptable RGB distance of any approved color
    approved_rgbs = [hex_to_rgb(h) for h in approved_hex_clean]

    for det_hex in detected_hex_colors:
        det_rgb = hex_to_rgb(det_hex)
        min_dist = min([color_distance_rgb(det_rgb, app_rgb) for app_rgb in approved_rgbs])
        if min_dist > 55.0:  # Distance threshold
            unapproved_detected.append(det_hex)

    if logo_detected and unapproved_detected:
        color_valid = False
        violations.append({
            "issue_type": "visual_mismatch",
            "severity": "high",
            "detected_text": f"Unapproved Logo Colors: {', '.join(unapproved_detected)}",
            "rule_violated": f"Brand Color Compliance: Logo must strictly use approved brand palette ({', '.join(approved_hex_clean)}).",
            "explanation": f"The logo contains colors ({', '.join(unapproved_detected)}) that deviate from the approved brand color specifications.",
            "evidence": f"Approved brand palette allows only: {', '.join(approved_hex_clean)}.",
            "suggested_fix": f"Recolor the logo using authorized brand HEX codes: {approved_hex_clean[0]}.",
            "confidence": 0.94
        })

    # Convert cropped detected logo to base64 for Streamlit preview
    cropped_b64 = ""
    if cropped_logo:
        buf = io.BytesIO()
        cropped_logo.save(buf, format="PNG")
        cropped_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {
        "logo_checked": True,
        "logo_detected": logo_detected,
        "match_confidence": round(confidence, 3),
        "bounding_box": [bx, by, bw, bh],
        "master_aspect_ratio": round(master_aspect, 2),
        "detected_aspect_ratio": round(detected_aspect, 2),
        "aspect_ratio_valid": aspect_valid,
        "aspect_ratio_deviation_pct": round(aspect_diff * 100, 1),
        "detected_hex_colors": detected_hex_colors,
        "approved_hex_colors": approved_hex_clean,
        "color_valid": color_valid,
        "cropped_logo_b64": cropped_b64,
        "violations": violations
    }
