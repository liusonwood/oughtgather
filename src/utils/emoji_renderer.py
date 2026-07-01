import os
from PIL import Image, ImageDraw, ImageFont

def render_emoji_to_png(emoji_char, font_path, output_dir, size=128):
    """
    将单个 Emoji 字符渲染为指定目录下的透明背景 PNG。
    返回生成的图片文件名，例如 'emoji_1f60a.png'
    """
    # 使用 Unicode 码点作为唯一文件名
    codepoint = "-".join(f"{ord(c):x}" for c in emoji_char)
    filename = f"emoji_{codepoint}.png"
    output_path = os.path.join(output_dir, filename)
    
    # 如果已存在，直接返回文件名
    if os.path.exists(output_path):
        return filename
        
    os.makedirs(output_dir, exist_ok=True)
    
    # 建立透明底画布
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    font_size = int(size * 0.85)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        raise FileNotFoundError(f"未找到指定的 Emoji 字体文件: {font_path}")
        
    # 计算文本边框并居中
    bbox = draw.textbbox((0, 0), emoji_char, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) / 2 - bbox[0]
    y = (size - text_h) / 2 - bbox[1]
    
    # 绘制纯黑色 Emoji 确保在电子墨水屏上的高对比度
    draw.text((x, y), emoji_char, font=font, fill=(0, 0, 0, 255))
    img.save(output_path, "PNG")
    
    return filename
