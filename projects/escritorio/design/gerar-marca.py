#!/usr/bin/env python3
"""Gera a marca Aeternum (SVGs + PNGs) a partir do glifo Æ do Michroma.

A marca é a ligadura Æ do Michroma (a fonte da palavra-marca "ÆTERNUM"),
extraída da TTF local — o ícone e o começo da palavra-marca são o mesmo glifo.
Monograma em branco (#F4EFE7, o "texto" do tema); na palavra-marca o Æ é bronze
(#DEB878) e o restante branco.

Deps:  pip install pillow fonttools
Uso:   python gerar-marca.py
Saída: aeternum-mark.svg / aeternum-icon.svg / aeternum-wordmark.svg
       aeternum-icon-1024.png / aeternum-mark-1024.png
       aeternum-adaptive-fg-1024.png / aeternum-wordmark-2048.png
"""
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from PIL import Image, ImageDraw, ImageFont

TTF = "Michroma-Regular.ttf"
BRONZE = "#DEB878"
BRONZE_RGB = (222, 184, 120, 255)
CREAM = "#F4EFE7"
CREAM_RGB = (244, 239, 231, 255)
INK = "#181108"
INK_RGB = (24, 17, 8, 255)
BG = (12, 15, 19, 255)          # #0C0F13
AE = "Æ"                 # a marca é o glifo da ligadura
REST = "TERNUM"               # resto da palavra-marca

font = TTFont(TTF)
cmap = font.getBestCmap()
glyf = font["glyf"]
hmtx = font["hmtx"]
glyph_set = font.getGlyphSet()


def glyph_path(ch: str):
    gname = cmap[ord(ch)]
    pen = SVGPathPen(glyph_set)
    glyph_set[gname].draw(pen)
    return pen.getCommands(), hmtx[gname][0]


def ink_bounds(ch: str, dx: float = 0):
    g = glyf[cmap[ord(ch)]]
    g.recalcBounds(glyf)
    return g.xMin + dx, g.yMin, g.xMax + dx, g.yMax


# ---- layout da palavra-marca: avanços naturais, sem tracking extra
layout = []          # (char, path, x_offset)
x = 0
for ch in AE + REST:
    d, adv = glyph_path(ch)
    layout.append((ch, d, x))
    x += adv

bounds = [ink_bounds(ch, dx) for ch, _, dx in layout]
X0 = min(b[0] for b in bounds)
Y0 = min(b[1] for b in bounds)
X1 = max(b[2] for b in bounds)
Y1 = max(b[3] for b in bounds)
WORD_W, WORD_H = X1 - X0, Y1 - Y0

# bounds do Æ sozinho (o monograma)
ae_path, ae_adv = glyph_path(AE)
ax0, ay0, ax1, ay1 = ink_bounds(AE)
AE_W, AE_H = ax1 - ax0, ay1 - ay0


def word_group(indent: str = "  ") -> str:
    """Palavra-marca flipada p/ y-down: Æ bronze + TTERNUM branco."""
    lines = [f'{indent}<g transform="translate({-X0} {Y1}) scale(1 -1)">']
    for ch, d, dx in layout:
        fill = BRONZE if ch == AE else CREAM
        t = f' transform="translate({dx} 0)"' if dx else ""
        lines.append(f'{indent}  <path d="{d}"{t} fill="{fill}"/>')
    lines.append(f"{indent}</g>")
    return "\n".join(lines)


def ae_group(fill: str, indent: str = "  ") -> str:
    return "\n".join([
        f'{indent}<g transform="translate({-ax0} {ay1}) scale(1 -1)" fill="{fill}">',
        f'{indent}  <path d="{ae_path}"/>',
        f"{indent}</g>",
    ])


# ------------------------------------------------------------------ SVGs ----
with open("aeternum-mark.svg", "w", encoding="utf-8") as f:
    f.write(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {AE_W} {AE_H}">\n'
        f"  <!-- Monograma Æ — glifo da ligadura do Michroma, branco sobre midnight. -->\n"
        f"{ae_group(CREAM)}\n"
        f"</svg>\n"
    )
print("ok: aeternum-mark.svg")

S = 512
scale = (S * 0.66) / AE_W
w, h = AE_W * scale, AE_H * scale
ox, oy = (S - w) / 2, (S - h) / 2
with open("aeternum-icon.svg", "w", encoding="utf-8") as f:
    f.write(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}">\n'
        f"  <!-- Ícone do app — inversa: Æ (Michroma) midnight sobre branco. -->\n"
        f'  <rect width="{S}" height="{S}" rx="114" fill="#F4EFE7"/>\n'
        f'  <rect x="1" y="1" width="{S-2}" height="{S-2}" rx="113" fill="none" '
        f'stroke="rgba(24,17,8,0.10)" stroke-width="2"/>\n'
        f'  <g transform="translate({ox:.1f} {oy:.1f}) scale({scale:.5f})">\n'
        f"{ae_group(INK, '    ')}\n"
        f"  </g>\n"
        f"</svg>\n"
    )
print("ok: aeternum-icon.svg")

with open("aeternum-wordmark.svg", "w", encoding="utf-8") as f:
    f.write(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WORD_W} {WORD_H}">\n'
        f"  <!-- Palavra-marca ÆTERNUM — Michroma; Æ bronze + TTERNUM branco. -->\n"
        f"{word_group()}\n"
        f"</svg>\n"
    )
print("ok: aeternum-wordmark.svg")

# ------------------------------------------------------------------ PNGs ----
SS = 4


def render_mark(path: str, canvas: int, frac: float, background=None,
                fg=CREAM_RGB):
    big = canvas * SS
    img = Image.new("RGBA", (big, big), background or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    probe = ImageFont.truetype(TTF, 100)
    w100 = d.textlength(AE, font=probe)
    px = (frac * big) / w100 * 100
    fnt = ImageFont.truetype(TTF, round(px))
    bbox = d.textbbox((0, 0), AE, font=fnt)
    ox = (big - (bbox[2] - bbox[0])) / 2 - bbox[0]
    oy = (big - (bbox[3] - bbox[1])) / 2 - bbox[1]
    d.text((ox, oy), AE, font=fnt, fill=fg)
    img = img.resize((canvas, canvas), Image.LANCZOS)
    img.save(path)
    print("ok:", path)


def render_wordmark(path: str, height: int = 512):
    """Palavra-marca em faixa: glifos a 55% da altura, margens iguais."""
    big = height * SS
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    probe = ImageFont.truetype(TTF, 100)
    h100 = tmp.textbbox((0, 0), AE + REST, font=probe)
    px = (big * 0.55) / (h100[3] - h100[1]) * 100
    fnt = ImageFont.truetype(TTF, round(px))
    bbox = tmp.textbbox((0, 0), AE + REST, font=fnt)
    W, H = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = round((big - H) / 2)
    img = Image.new("RGBA", (W + 2 * pad, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = pad - bbox[0], pad - bbox[1]
    d.text((ox, oy), AE, font=fnt, fill=BRONZE_RGB)
    d.text((ox + d.textlength(AE, font=fnt), oy), REST, font=fnt, fill=CREAM_RGB)
    img = img.resize((round(img.width / SS), height), Image.LANCZOS)
    img.save(path)
    print("ok:", path)


render_mark("aeternum-icon-1024.png", 1024, 0.66, background=CREAM_RGB, fg=INK_RGB)
render_mark("aeternum-mark-1024.png", 1024, 0.74)
render_mark("aeternum-adaptive-fg-1024.png", 1024, 0.50, fg=INK_RGB)
render_wordmark("aeternum-wordmark.png", 512)
