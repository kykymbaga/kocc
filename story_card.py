"""Typeset an original Belarusian fable as a Telegram Story photo."""
from io import BytesIO
import os

from PIL import Image, ImageDraw, ImageFont


def render_card(story):
    ink, paper, accent = {
        "friendship": ("#183E3C", "#FAEFDA", "#F6B876"),
        "justice": ("#362950", "#FFF2DC", "#D8B7F3"),
        "leadership": ("#492B29", "#FFEFD7", "#F3A17C"),
        "community": ("#18324A", "#F7EFDD", "#9DD6DA"),
        "faith": ("#393348", "#FFF3DF", "#F3CD7C"),
        "intolerance": ("#293E32", "#F7F3D7", "#B8D6A0"),
    }[story["topic"]]
    image = Image.new("RGB", (1080, 1920), ink)
    draw = ImageDraw.Draw(image)
    serif = "georgia.ttf" if os.name == "nt" else "DejaVuSerif.ttf"
    sans = "arial.ttf" if os.name == "nt" else "DejaVuSans.ttf"
    margin = 92
    width = image.width - 2 * margin

    def lines_of(text, font):
        lines = [""]
        for word in text.split():
            line = (lines[-1] + " " + word).strip()
            if lines[-1] and draw.textlength(line, font=font) > width:
                lines.append(word)
            else:
                lines[-1] = line
        return lines

    title_font = ImageFont.truetype(serif, 92)
    body_font = ImageFont.truetype(serif, 57)
    label_font = ImageFont.truetype(sans, 32)
    title = lines_of(story["title"], title_font)
    body = lines_of(story["text"], body_font)
    y = (image.height - (len(title) * 116 + 60 + len(body) * 81)) // 2
    draw.text((margin, y - 115), "Вячэрняя байка", font=label_font, fill=accent)
    for line in title:
        draw.text((margin, y), line, font=title_font, fill=paper)
        y += 116
    draw.line((margin, y + 15, margin + 98, y + 15), fill=accent, width=5)
    y += 60
    for line in body:
        draw.text((margin, y), line, font=body_font, fill=paper)
        y += 81
    output = BytesIO()
    image.save(output, "JPEG", quality=88, optimize=True)
    return output.getvalue()
