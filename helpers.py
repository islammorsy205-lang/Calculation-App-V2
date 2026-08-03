# helpers.py

import io
import re
from PIL import Image, ImageChops
import streamlit as st
import numpy as np
from config import STRUTS_DB

def crop_white_margins(img):
    if img.mode != "RGB":
        img = img.convert("RGB")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    if bbox:
        pad = 20
        bbox = (max(0, bbox[0]-pad), max(0, bbox[1]-pad), min(img.width, bbox[2]+pad), min(img.height, bbox[3]+pad))
        return img.crop(bbox)
    return img

def convert_transparent_to_pdf_stream(img_bytes):
    img_stream = io.BytesIO(img_bytes)
    img = Image.open(img_stream)
    bg = Image.new("RGB", img.size, (255, 255, 255))
    if img.mode in ('RGBA', 'LA'):
        bg.paste(img, mask=img.split()[3])
    else:
        bg.paste(img)
    pdf_stream = io.BytesIO()
    bg.save(pdf_stream, format='PDF')
    pdf_stream.seek(0)
    return pdf_stream

def get_val(key_base, i, default_val):
    if i == 0: 
        return default_val
    return st.session_state.get(f"{key_base}_0", default_val)

def get_idx(key_base, i, options_list, default_idx):
    if i == 0: 
        return default_idx
    val_0 = st.session_state.get(f"{key_base}_0")
    if val_0 in options_list: 
        return options_list.index(val_0)
    return default_idx

def extract_images_from_pdf(pdf_file):
    import fitz
    images = []
    try:
        pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
        for page_num in range(min(3, len(pdf_document))): 
            page = pdf_document.load_page(page_num)
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                images.append(base_image["image"])
        pdf_file.seek(0)
    except Exception:
        pass
    return images

def get_best_image_match(subject, system, image_list):
    if not image_list: 
        return 0
    best_idx, max_score = 0, -1
    stopwords = {"calculation", "sheet", "for", "system", "&", "and", "panel"}
    subj_words = [w.lower() for w in re.split(r'\W+', subject) if w and w.lower() not in stopwords]
    sys_words = [w.lower() for w in re.split(r'\W+', system) if w and w.lower() not in stopwords]
    keywords = set(subj_words + sys_words)

    for idx, img in enumerate(image_list):
        score = sum(1 for kw in keywords if kw in img.lower())
        if score > max_score: 
            max_score, best_idx = score, idx
    return best_idx

def get_valid_struts(req_len, mode="wind"):
    valid = []
    for k, v in STRUTS_DB.items():
        if v['min'] <= req_len <= v['max']:
            if mode == "strongback":
                if "PPH" in k or "PPS" in k: 
                    valid.append(k)
            else:
                valid.append(k)
                
    if not valid: 
        return [f"No strut fits ({req_len:.2f}m)"]
    
    def sort_key(name):
        n_up = name.upper()
        score = 10
        
        if mode == "strongback":
            if "PPH" in n_up: score = 0
            elif "PPS" in n_up: score = 1
        else:
            if "TILT" in n_up or "MPP" in n_up: score = 0
            elif "PPS" in n_up: score = 1
            elif "PPH" in n_up: score = 2
        
        match = re.search(r'\d+', name.split()[0])
        if match and int(match.group()[-1]) in [1, 3, 5]:
            score += 20
        if "X1" in n_up or "X3" in n_up or "X5" in n_up:
            score += 20
        if "X4" in n_up:
            score += 20
            
        return (score, name)
    
    valid.sort(key=sort_key)
    return valid
