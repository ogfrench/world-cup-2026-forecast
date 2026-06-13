#!/usr/bin/env python3
"""Generate og.png, the 1200x630 social-share card, in the app's visual style.

Not part of the build. Run by hand to refresh the card:
    python3 source/make_og.py

Fonts (Anton, DM Mono) are pulled from the public google/fonts repo into a temp
dir if not already present, so nothing heavy is committed. Output: og.png at the
repo root, served by Netlify and referenced by the og:image / twitter:image meta.
"""
import os, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTDIR = os.path.join(HERE, ".ogfonts")
FONTS = {
    "Anton-Regular.ttf": "ofl/anton/Anton-Regular.ttf",
    "DMMono-Medium.ttf": "ofl/dmmono/DMMono-Medium.ttf",
    "DMMono-Regular.ttf": "ofl/dmmono/DMMono-Regular.ttf",
}
def fetch_fonts():
    os.makedirs(FONTDIR, exist_ok=True)
    for name, path in FONTS.items():
        dst = os.path.join(FONTDIR, name)
        if not os.path.exists(dst):
            urllib.request.urlretrieve("https://raw.githubusercontent.com/google/fonts/main/" + path, dst)

# palette, straight from the app
BG=(10,11,13); SURF=(21,24,30); SURF2=(27,31,39); LINE=(38,43,52); LINE2=(50,56,69)
TXT=(236,238,241); MUT=(150,156,166); FAINT=(139,145,157)
LIME=(200,255,77); GOLD=(255,209,102); BLUE=(95,179,255)

S = 2                         # supersample, downscaled at the end for crisp text
W, H = 1200*S, 630*S
def f(name, size): return ImageFont.truetype(os.path.join(FONTDIR, name), size*S)

def tracked(d, xy, text, font, fill, track=0):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + track*S
    return x

def main():
    fetch_fonts()
    anton = lambda s: f("Anton-Regular.ttf", s)
    mono  = lambda s: f("DMMono-Medium.ttf", s)
    monor = lambda s: f("DMMono-Regular.ttf", s)

    img = Image.new("RGB", (W, H), BG)
    # soft brand glows, like the app background
    glow = Image.new("RGBA", (W, H), (0,0,0,0)); gd = ImageDraw.Draw(glow)
    gd.ellipse([W*0.55, -H*0.5, W*1.25, H*0.6], fill=LIME+(34,))
    gd.ellipse([-W*0.3, H*0.55, W*0.4, H*1.4], fill=BLUE+(28,))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(120*S))).convert("RGB")
    d = ImageDraw.Draw(img)

    P = 64*S
    # kicker
    ky = 58*S
    d.line([P, ky+11*S, P+30*S, ky+11*S], fill=LIME, width=2*S)
    tracked(d, (P+44*S, ky), "104 MATCHES  ·  FIVE MODELS  ·  50,000 SIMULATIONS", mono(15), LIME, track=2)

    # title, two lines, "2026" in lime
    ty = 120*S
    tf = anton(100)
    x = tracked(d, (P, ty), "WORLD CUP ", tf, TXT, track=1)
    tracked(d, (x, ty), "2026", tf, LIME, track=1)
    tracked(d, (P, ty+108*S), "FORECAST", tf, TXT, track=1)

    # podium: three favorites, like the app
    pods = [("1ST", "SPAIN", "16.6", LIME), ("2ND", "FRANCE", "15.8", BLUE), ("3RD", "ENGLAND", "11.5", GOLD)]
    cw, gap = 330*S, 24*S
    px0, ch = P, 180*S
    py = H - P - ch
    for i,(rk,team,pct,col) in enumerate(pods):
        x0 = px0 + i*(cw+gap)
        d.rounded_rectangle([x0, py, x0+cw, py+ch], radius=16*S, fill=SURF, outline=LINE, width=1*S)
        d.rectangle([x0, py, x0+cw, py+4*S], fill=col)
        tracked(d, (x0+22*S, py+22*S), rk+" FAVORITE", monor(13), FAINT, track=2)
        d.text((x0+20*S, py+44*S), team, font=anton(42), fill=TXT)
        d.text((x0+20*S, py+100*S), pct, font=mono(40), fill=col)
        pw = d.textlength(pct, font=mono(40))
        d.text((x0+20*S+pw+6*S, py+112*S), "%", font=mono(20), fill=col)
        d.text((x0+22*S, py+150*S), "to win the World Cup", font=monor(13), fill=MUT)

    # url, bottom-right of the header
    url = "wc2026forecast.xyz"
    uf = mono(20)
    uw = d.textlength(url, font=uf)
    d.text((W-P-uw, 66*S), url, font=uf, fill=LIME)

    out = img.resize((1200, 630), Image.LANCZOS)
    dst = os.path.join(ROOT, "og.png")
    out.save(dst, "PNG", optimize=True)
    print("wrote", dst, os.path.getsize(dst), "bytes")

if __name__ == "__main__":
    main()
