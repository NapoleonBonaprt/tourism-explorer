"""Compact destination-specific PDF cover art, independent of external image hosts."""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1] / "assets" / "cities"
SIZE = (900, 560)
# Madrid and Barcelona intentionally share the current local photograph.
REQUIRED_PHOTOS = {"cairo", "lisbon", "paris", "rome", "tokyo", "madrid", "barcelona"}

class RequiredPhotoUnavailable(OSError):
    """A required local destination photo could not be loaded."""

def slug(city):
    return re.sub(r"[^a-z0-9]+", "-", city.strip().lower()).strip("-")

def illustrate(key):
    """Stylized landmark art, not a documentary view of a real location."""
    w,h = SIZE
    im=Image.new("RGB",SIZE)
    d=ImageDraw.Draw(im)
    for y in range(h):
        a=y/h
        d.line((0,y,w,y),fill=tuple(round(x+(z-x)*a) for x,z in zip((224,236,216),(250,226,176))))
    d.ellipse((650,45,790,185),fill="#F3BF64")
    d.polygon([(0,335),(180,180),(360,340),(550,220),(900,350),(900,560),(0,560)],fill="#A1BBA2")
    d.polygon([(0,390),(170,310),(430,385),(680,290),(900,375),(900,560),(0,560)],fill="#6C9A85")
    d.rectangle((0,410,900,560),fill="#315C4D")
    cream="#F6E5BC"; dark="#244B43"; gold="#DDA856"; stone="#D1AE76"; pale="#F3D39A"
    def poly(points, fill): d.polygon(points,fill=fill)
    def box(x0,y0,x1,y1,fill): d.rectangle((x0,y0,x1,y1),fill=fill)
    if key=="cairo":
        for x,y,a,b in [(60,425,320,260),(335,430,370,310),(630,430,230,190)]:
            poly([(x,y),(x+a/2,y-b),(x+a,y)],pale)
            poly([(x+a/2,y-b),(x+a,y),(x+a/2,y)],stone)
        d.line((0,450,900,450),fill=gold,width=5)
    elif key=="paris":
        # Eiffel Tower silhouette and low Parisian roofline.
        for x,ht in [(35,80),(125,105),(205,65),(645,94),(740,118),(820,74)]:
            box(x,430-ht,x+62,430,cream);poly([(x-5,430-ht),(x+31,410-ht),(x+67,430-ht)],dark)
            for xx in range(x+10,x+55,20): box(xx,445-ht,xx+7,462-ht,"#769D88")
        poly([(286,435),(420,200),(447,65),(461,65),(488,200),(620,435),(550,435),(483,278),(425,278),(355,435)],dark)
        for yy,ww in [(195,82),(267,132),(351,233)]:
            box(454-ww/2,yy,454+ww/2,yy+10,gold)
        box(447,42,461,75,dark)
    elif key=="tokyo":
        poly([(30,408),(340,93),(650,408)],"#8DAFA7")
        poly([(227,208),(340,93),(454,208),(383,187),(340,231),(300,185)],cream)
        for x,ht in [(40,100),(110,150),(190,80),(705,160),(782,115)]:
            box(x,425-ht,x+55,425,dark)
            for yy in range(435-ht,415,20):box(x+12,yy,x+20,yy+7,pale)
        for y,ww in [(205,158),(268,210),(333,265)]:
            box(660-ww*.34,y,660+ww*.34,y+68,"#C26B4D")
            poly([(660-ww/2,y),(660-ww*.34,y-20),(660+ww*.34,y-20),(660+ww/2,y)],dark)
            box(650,y+13,670,y+49,cream)
        box(575,399,745,428,dark)
    elif key=="rome":
        d.rounded_rectangle((112,190,785,439),radius=64,fill=stone)
        box(112,274,785,439,pale)
        for y in [230,305,380]:
            for x in range(155,750,88):
                d.rounded_rectangle((x,y,x+48,y+58),radius=20,fill=dark)
        box(103,287,795,298,cream);box(103,361,795,372,cream)
    elif key=="lisbon":
        for i,x in enumerate(range(25,880,120)):
            top=240+(i%3)*24
            box(x,top,x+100,425,["#F5D59C","#EBC58F","#D9E4C9"][i%3])
            poly([(x-8,top),(x+50,top-40),(x+108,top)],"#B46C4C")
            for xx in (x+20,x+60):
                box(xx,top+27,xx+15,top+54,dark);box(xx,top+72,xx+15,top+99,dark)
        d.rounded_rectangle((270,310,625,481),radius=22,fill=gold)
        box(282,330,613,400,cream)
        for xx in [298,390,482,574]:box(xx,343,xx+20,389,dark)
        for xx in (335,560):d.ellipse((xx-23,457,xx+23,503),fill=dark)
        d.line((395,310,490,270,550,310),fill=dark,width=5)
    elif key=="madrid":
        box(110,235,790,435,cream)
        box(340,180,560,435,pale)
        poly([(320,180),(450,122),(580,180)],stone)
        for x in range(144,765,68):
            for y in (260,331):d.rounded_rectangle((x,y,x+30,y+48),radius=13,fill=dark)
        for x in (120,317,570,765):box(x,220,x+18,437,stone)
        box(420,345,480,435,dark)
    else:
        for i,x in enumerate(range(35,870,100)):
            ht=80+(i*37)%160;box(x,440-ht,x+65,440,dark)
            for yy in range(455-ht,430,25):box(x+15,yy,x+25,yy+10,cream)
    poly([(0,560),(260,482),(440,472),(650,510),(900,464),(900,560)],"#547E68")
    d.line([(0,540),(240,505),(440,505),(600,531),(900,497)],fill="#E8D1A0",width=5)
    return im

@lru_cache(maxsize=16)
def city_cover(city):
    key=slug(city)
    photo=ROOT / (key+".jpg")
    if key and photo.is_file():
        try:
            with Image.open(photo) as img:
                im=ImageOps.fit(ImageOps.exif_transpose(img).convert("RGB"),SIZE,Image.Resampling.LANCZOS,centering=(.5,.46))
            kind="photo"
        except (OSError,ValueError) as exc:
            if key in REQUIRED_PHOTOS:
                raise RequiredPhotoUnavailable(f"Destination photo unavailable: {city}") from exc
            im=illustrate(key);kind="illustration"
    else:
        if key in REQUIRED_PHOTOS:
            raise RequiredPhotoUnavailable(f"Destination photo unavailable: {city}")
        im=illustrate(key);kind="illustration"
    out=BytesIO()
    im.save(out,format="JPEG",quality=86,optimize=True)
    return out.getvalue(),kind
