import sys, os, io, json, traceback
from flask import Flask, request, send_file, abort
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config

app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = None
app.config['MAX_FORM_MEMORY_SIZE'] = None
Image.MAX_IMAGE_PIXELS = None 

app.config.from_object(Config)

def create_collage(image_list, layout='grid'):
    count = len(image_list)
    if count == 0: return None
    
    images = []
    for f in image_list:
        try:
            img = Image.open(f).convert('RGB')
            images.append(img)
        except: pass
        
    if not images: return None
    count = len(images)

    W, H = 1920, 1920
    canvas = Image.new('RGB', (W, H), (255, 255, 255))
    slots = []
  
    if layout == 'horizontal':
        
        width_per_img = W // count
        for i in range(count):
            slots.append((i * width_per_img, 0, width_per_img, H))
            
    elif layout == 'vertical':
        height_per_img = H // count
        for i in range(count):
            slots.append((0, i * height_per_img, W, height_per_img))
            
    else:
        if count == 1: slots = [(0, 0, W, H)]
        elif count == 2: slots = [(0, 0, W//2, H), (W//2, 0, W//2, H)]
        elif count == 3: slots = [(0, 0, W, H//2), (0, H//2, W//2, H//2), (W//2, H//2, W//2, H//2)]
        elif count == 4: slots = [(0, 0, W//2, H//2), (W//2, 0, W//2, H//2), (0, H//2, W//2, H//2), (W//2, H//2, W//2, H//2)]
        elif count == 5: h3 = H // 3; slots = [(0, 0, W//2, h3*2), (W//2, 0, W//2, h3*2), (0, h3*2, W//3, h3), (W//3, h3*2, W//3, h3), (2*W//3, h3*2, W//3, h3)]
        else: w3 = W // 3; h2 = H // 2; slots = [(0,0,w3,h2), (w3,0,w3,h2), (2*w3,0,w3,h2), (0,h2,w3,h2), (w3,h2,w3,h2), (2*w3,h2,w3,h2)]

    for i, img in enumerate(images):
        if i >= len(slots): break
        x, y, sw, sh = slots[i]
        
        target_ratio = sw / sh
        img_ratio = img.width / img.height
        
        if img_ratio > target_ratio:
            new_h = sh
            new_w = int(sh * img_ratio)
        else:
            new_w = sw
            new_h = int(sw / img_ratio)
        
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - sw) // 2
        top = (new_h - sh) // 2
        img = img.crop((left, top, left + sw, top + sh))
        
        canvas.paste(img, (x, y))

    return canvas

def apply_filter(img, name, intensity):
    intensity = float(intensity)
    if name == 'emerald':
        img = ImageEnhance.Contrast(img).enhance(1.0 + (0.3 * intensity))
        r, g, b = img.split()
        g = ImageEnhance.Brightness(g).enhance(1.0 + (0.2 * intensity))
        img = Image.merge("RGB", (r, g, b))
    elif name == 'warm':
        r, g, b = img.split()
        r = ImageEnhance.Brightness(r).enhance(1.0 + (0.2 * intensity))
        b = ImageEnhance.Brightness(b).enhance(1.0 - (0.1 * intensity))
        img = Image.merge("RGB", (r, g, b))
    elif name == 'cool':
        r, g, b = img.split()
        r = ImageEnhance.Brightness(r).enhance(1.0 - (0.1 * intensity))
        b = ImageEnhance.Brightness(b).enhance(1.0 + (0.2 * intensity))
        img = Image.merge("RGB", (r, g, b))
    elif name == 'vivid':
        img = ImageEnhance.Color(img).enhance(1.0 + (0.5 * intensity))
        img = ImageEnhance.Contrast(img).enhance(1.0 + (0.2 * intensity))
    elif name == 'bw':
        img = img.convert('L').convert('RGB')
    return img

@app.route('/process', methods=['POST'])
def process():
    if request.headers.get('X-Auth-Token') != Config.INTERNAL_API_TOKEN:
        abort(403)

    try:
        mode = request.form.get('mode')
        
        if mode == 'collage':
            files = request.files.getlist('files')
           
            layout = request.form.get('layout', 'grid') 
            
            result = create_collage(files, layout=layout)
            if not result: return "Error creating collage", 500
            
            img_io = io.BytesIO()
            result.save(img_io, 'JPEG', quality=95)
            img_io.seek(0)
            return send_file(img_io, mimetype='image/jpeg')

        else:
            if 'file' not in request.files: return "No file", 400
            file = request.files['file']
            edits = json.loads(request.form.get('edits', '{}'))
            
            img = Image.open(file.stream).convert("RGB")
            
            if edits.get('crop') and edits['crop'].get('w', 0) > 0:
                c = edits['crop']
                img = img.crop((c['x'], c['y'], c['x'] + c['w'], c['y'] + c['h']))

            rot = edits.get('rotate', 0)
            if rot: img = img.rotate(-1 * int(rot), expand=True)

            flt = edits.get('filter')
            if flt and flt != 'original':
                img = apply_filter(img, flt, edits.get('intensity', 1))

            if 'brightness' in edits:
                img = ImageEnhance.Brightness(img).enhance(float(edits['brightness']))
            if 'contrast' in edits:
                img = ImageEnhance.Contrast(img).enhance(float(edits['contrast']))
            
            if edits.get('portrait'):
                mask = Image.new('L', img.size, 255)
                draw = ImageDraw.Draw(mask)
                w, h = img.size
                draw.ellipse((w*0.1, h*0.1, w*0.9, h*0.9), fill=0)
                mask = mask.filter(ImageFilter.GaussianBlur(50))
                dark = ImageEnhance.Brightness(img).enhance(0.5)
                img = Image.composite(img, dark, mask)

            wm = edits.get('watermark_text')
            if wm:
                draw = ImageDraw.Draw(img)
                w, h = img.size
                x, y = w - (len(wm)*10) - 20, h - 30
                draw.text((x, y), wm, fill=(255, 255, 255))

            quality_val = int(edits.get('quality', 95))
            
            img_io = io.BytesIO()
            img.save(img_io, 'JPEG', quality=quality_val)
            img_io.seek(0)
            return send_file(img_io, mimetype='image/jpeg')

    except Exception as e:
        traceback.print_exc()
        return str(e), 500

if __name__ == '__main__':
    app.run(port=5001, threaded=True)