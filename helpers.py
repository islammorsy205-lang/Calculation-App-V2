# helpers.py

import io
import fitz
from PIL import Image
import numpy as np

def get_val(key, i, default):
    import streamlit as st
    full_key = f"{key}_{i}"
    if full_key in st.session_state:
        return st.session_state[full_key]
    return default

def get_idx(key, i, options, default_idx):
    import streamlit as st
    full_key = f"{key}_{i}"
    if full_key in st.session_state:
        try:
            return options.index(st.session_state[full_key])
        except ValueError:
            return default_idx
    return default_idx

def convert_transparent_to_pdf_stream(img_bytes):
    from PIL import Image
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.paste(img, mask=img)
    pdf_bytes = io.BytesIO()
    bg.convert("RGB").save(pdf_bytes, format="PDF")
    pdf_bytes.seek(0)
    return pdf_bytes.getvalue()

def crop_white_margins(img, tolerance=240):
    img_data = np.array(img)
    if img_data.shape[2] == 4:
        alpha = img_data[:, :, 3]
        rgb = img_data[:, :, :3]
        mask = (alpha > 0) & (np.min(rgb, axis=2) < tolerance)
    else:
        mask = np.min(img_data, axis=2) < tolerance
    coords = np.argwhere(mask)
    if coords.size == 0:
        return img
    y0, x0 = coords.min(axis=0)
    y1, x1 = coords.max(axis=0) + 1
    return img.crop((x0, y0, x1, y1))

# =========================================================
# دوال استخراج الصور (تم استرجاعها ليعمل ملف ui_project.py بكفاءة)
# =========================================================
def extract_images_from_pdf(pdf_file):
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

def get_best_image_match(images, keyword=None):
    if not images: return None
    best_img = None
    max_size = 0
    for img_bytes in images:
        try:
            img = Image.open(io.BytesIO(img_bytes))
            size = img.width * img.height
            if size > max_size:
                max_size = size
                best_img = img_bytes
        except:
            pass
    return best_img

# =========================================================
# دالة فلترة النهايز (محدثة بالترتيب الذكي الجديد المطابق لطلبك)
# =========================================================
def get_valid_struts(L_req, mode="wind"):
    from config import STRUTS_DB
    valid = []
    for k, v in STRUTS_DB.items():
        if v['min'] <= L_req <= v['max']:
            valid.append(k)
            
    if not valid:
        return [f"No strut fits ({L_req:.2f}m)"]
    
    # الترتيب في حالة الـ Strongback (PPH ثم PPS)
    if mode == "strongback":
        def sort_key_sb(name):
            n_up = name.upper()
            if "PPH" in n_up: return 0
            if "PPS" in n_up: return 1
            return 2
        valid.sort(key=sort_key_sb)
        
    # الترتيب في حالة الـ Wind Load (TILT UP/MPP ثم PPS ثم PPH)
    else:
        def sort_key_wind(name):
            n_up = name.upper()
            if "MPP" in n_up or "TILT" in n_up: return 0
            if "PPS" in n_up: return 1
            if "PPH" in n_up: return 2
            return 3
        valid.sort(key=sort_key_wind)
        
    return valid
