"""Render Folio's original route-map animation. Development-only Pillow dependency."""
import argparse
import math
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H, SCALE = 1280, 420, 2
INK, PAPER, BRASS, MUTED = "#102e2a", "#f2ecdc", "#b9a071", "#80918a"


def font(size, serif=False):
    names = ([Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/georgia.ttf",
              Path("/System/Library/Fonts/Supplemental/Georgia.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")]
             if serif else [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf",
                            Path("/System/Library/Fonts/Supplemental/Arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")])
    for path in names:
        if path.exists(): return ImageFont.truetype(str(path), round(size * SCALE))
    return ImageFont.load_default()


def bezier(t, a, b, c, d):
    return tuple((1-t)**3*a[i] + 3*(1-t)**2*t*b[i] + 3*(1-t)*t*t*c[i] + t**3*d[i] for i in (0,1))


def frame(phase):
    im = Image.new("RGB", (W*SCALE, H*SCALE), INK); draw = ImageDraw.Draw(im)
    def line(points, fill, width=1): draw.line([(round(x*SCALE),round(y*SCALE)) for x,y in points], fill=fill, width=max(1,round(width*SCALE)))
    def text(x,y,value,size=14,fill=PAPER,serif=False): draw.text((x*SCALE,y*SCALE),value,font=font(size,serif),fill=fill)
    def ellipse(x,y,r,fill=None,outline=None,width=1): draw.ellipse(((x-r)*SCALE,(y-r)*SCALE,(x+r)*SCALE,(y+r)*SCALE),fill=fill,outline=outline,width=round(width*SCALE))
    for x in range(600,W,32): line([(x,45),(x,360)],"#173832")
    for y in range(45,365,32): line([(600,y),(1235,y)],"#173832")
    for n in range(5):
        ellipse(965,210,70+n*38,outline="#1b3b34")
    line([(60,43),(90,43)],BRASS,2)
    text(105,34,"A LIBRARY OF YOUR WORK",12,MUTED)
    text(55,80,"Folio",88,PAPER,True)
    text(53,174,"Atlas",88,PAPER,True)
    text(60,288,"A place for every file.",22,PAPER)
    text(60,321,"A map of what you're working on.",17,MUTED)
    text(60,382,"LOCAL FIRST   /   LEARN · SORT · FIND",11,BRASS)
    line([(535,80),(535,340)],"#355047")
    a=(650,210)
    targets=[(1050,95,"PROJECTS","01"),(1130,210,"DOCUMENTS","02"),(1040,325,"RECORDINGS","03")]
    ellipse(*a,23,INK,"#4a5e50"); text(614,245,"INCOMING",10,MUTED)
    line([(642,202),(658,202),(658,218),(642,218),(642,202)],PAPER)
    for i,(x,y,label,index) in enumerate(targets):
        controls=(a,(825,210),(835,y),(x,y))
        points=[bezier(k/80,*controls) for k in range(81)]
        line(points,"#4e6150",1.2)
        pulse=8+5*(0.5+0.5*math.sin(phase*math.tau+i))
        ellipse(x,y,pulse,outline="#485746")
        ellipse(x,y,4,BRASS)
        text(x+18,y-17,index,10,BRASS); text(x+18,y+1,label,11,PAPER)
        for j in range(2):
            u=(phase+j/2+i/7)%1
            # Continuous slow packets make the GIF seamlessly loop.
            px,py=bezier(u,*controls)
            draw.rounded_rectangle(((px-10)*SCALE,(py-13)*SCALE,(px+10)*SCALE,(py+13)*SCALE),radius=3*SCALE,fill=PAPER)
            line([(px-5,py-4),(px+5,py-4)],INK)
            line([(px-5,py+1),(px+3,py+1)],"#a3977b")
            line([(px-5,py+6),(px+1,py+6)],"#a3977b")
    text(604,382,"SCATTERED FILES",10,MUTED)
    text(1030,382,"A LIVING ATLAS",10,BRASS)
    return im.resize((W,H),Image.Resampling.LANCZOS)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--out",default=str(ROOT/"assets")); args=parser.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    frames=[frame(i/72) for i in range(72)]
    frames[19].save(out/"folio-atlas-banner.png")
    palette=frames[19].quantize(colors=128)
    gif=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in frames]
    gif[0].save(out/"folio-atlas-banner.gif",save_all=True,append_images=gif[1:],duration=83,loop=0,optimize=True,disposal=1)
    svg='''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="420" viewBox="0 0 1280 420"><rect width="1280" height="420" fill="#102e2a"/><g fill="#f2ecdc" font-family="Georgia,serif" font-size="100"><text x="56" y="170">Folio</text><text x="56" y="270">Atlas</text></g><g font-family="Arial,sans-serif"><text x="60" y="45" fill="#b9a071" font-size="13">A LIBRARY OF YOUR WORK</text><text x="60" y="320" fill="#f2ecdc" font-size="22">A place for every file.</text><text x="60" y="350" fill="#80918a" font-size="17">A map of what you're working on.</text></g><g fill="none" stroke="#4e6150"><path d="M650 210 C825 210 835 95 1050 95"/><path d="M650 210 C825 210 835 210 1130 210"/><path d="M650 210 C825 210 835 325 1040 325"/></g><g fill="#b9a071" font-family="Arial,sans-serif" font-size="12"><text x="1068" y="100">PROJECTS</text><text x="1148" y="215">DOCUMENTS</text><text x="1058" y="330">RECORDINGS</text></g>'''
    for i,path in enumerate(["M650 210 C825 210 835 95 1050 95","M650 210 C825 210 835 210 1130 210","M650 210 C825 210 835 325 1040 325"]):
        svg+=f'<rect x="-9" y="-12" width="18" height="24" rx="3" fill="#f2ecdc"><animateMotion dur="6s" begin="-{i*1.4}s" repeatCount="indefinite" path="{path}"/></rect>'
    svg+='</svg>'; (out/"folio-atlas-banner.svg").write_text(svg,encoding="utf-8")
    print("Rendered original GIF, PNG, and animated SVG banner.")


if __name__=="__main__": main()
