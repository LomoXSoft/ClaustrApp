"""Genera icon.png, icon.ico y los fondos de presentación (splash) de cada marca (LomoXSoft).

Uso: make_assets.py            -> icono y splash de la marca activa
     make_assets.py --publica  -> recursos/splash_publico.png con las líneas de marca_publica.json"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import math, os
HERE=os.path.dirname(os.path.abspath(__file__))
BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"; REG="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
RED,GREEN,YELLOW,BLUE=(160,28,32),(28,160,60),(245,200,20),(30,70,200)
EDGE=(70,74,90)

def icon(size=512):
    S=size*2; im=Image.new("RGBA",(S,S),(0,0,0,0))
    def u(v): return int(v*S/512)
    # sombra
    sh=Image.new("RGBA",(S,S),(0,0,0,0)); d=ImageDraw.Draw(sh)
    d.rounded_rectangle([u(56),u(86),u(436),u(446)],u(40),fill=(40,50,80,110))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(u(14))))
    d=ImageDraw.Draw(im)
    # tarjeta calendario
    d.rounded_rectangle([u(46),u(70),u(426),u(430)],u(40),fill=(250,251,253),outline=EDGE,width=u(10))
    d.rounded_rectangle([u(46),u(70),u(426),u(150)],u(40),fill=(118,126,150),outline=EDGE,width=u(10))
    d.rectangle([u(51),u(120),u(421),u(150)],fill=(118,126,150)); d.line([u(46),u(150),u(426),u(150)],fill=EDGE,width=u(10))
    for x in (130,236,342):  # anillas
        d.rounded_rectangle([u(x-12),u(42),u(x+12),u(108)],u(12),fill=(235,238,245),outline=EDGE,width=u(8))
    # rejilla 4x3
    cols,rows=4,3; x0,y0,cw,ch,g=82,178,74,72,14
    colored={(0,0):RED,(2,0):GREEN,(1,1):YELLOW,(0,2):BLUE}
    for r in range(rows):
        for c in range(cols):
            bx,by=x0+c*(cw+g),y0+r*(ch+g)
            col=colored.get((c,r),(222,227,237))
            d.rounded_rectangle([u(bx),u(by),u(bx+cw),u(by+ch)],u(10),fill=col,outline=(EDGE if (c,r) in colored else (190,196,210)),width=u(5))
    # reloj
    cx,cy,R=392,392,96
    sh=Image.new("RGBA",(S,S),(0,0,0,0)); ImageDraw.Draw(sh).ellipse([u(cx-R+8),u(cy-R+12),u(cx+R+8),u(cy+R+12)],fill=(40,50,80,110))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(u(10)))); d=ImageDraw.Draw(im)
    d.ellipse([u(cx-R),u(cy-R),u(cx+R),u(cy+R)],fill=(255,255,255),outline=EDGE,width=u(11))
    for k in range(12):
        a=math.radians(k*30); r1=R-(26 if k%3==0 else 18); r2=R-12
        d.line([u(cx+r1*math.sin(a)),u(cy-r1*math.cos(a)),u(cx+r2*math.sin(a)),u(cy-r2*math.cos(a))],fill=EDGE,width=u(7 if k%3==0 else 4))
    d.line([u(cx),u(cy),u(cx),u(cy-60)],fill=EDGE,width=u(12))
    d.line([u(cx),u(cy),u(cx+44),u(cy+18)],fill=RED,width=u(10))
    d.ellipse([u(cx-11),u(cy-11),u(cx+11),u(cy+11)],fill=EDGE)
    return im.resize((size,size),Image.LANCZOS)

def splash(version="0.0.1", status="Cargando...", W=440, H=440, lineas=("Horarios",)):
    S=2; w,h=W*S,H*S
    # degradado diagonal azul claro (arriba-izq) -> blanco
    base=Image.new("RGB",(w,h)); px=base.load()
    a,b=(196,214,236),(244,246,250)
    for y in range(h):
        for x in range(0,w):
            t=min(1,((x/w)*0.8+(y/h)*0.5)); px[x,y]=tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))
    im=base.convert("RGBA"); d=ImageDraw.Draw(im)
    band=int(h*0.735)
    d.rectangle([0,band,w,h],fill=(201,205,224)); d.line([0,band,w,band],fill=(170,176,200),width=2*S)
    ic=icon(int(176*S)); im.alpha_composite(ic,((w-ic.width)//2,int(18*S)))
    ft=ImageFont.truetype(BOLD,44*S); dark=(58,61,76)
    for i,line in enumerate(lineas):
        tw=d.textlength(line,font=ft); d.text(((w-tw)/2,int((200+i*50)*S)),line,font=ft,fill=dark)
    d.text((int(24*S),band+int(10*S)),version,font=ImageFont.truetype(BOLD,40*S),fill=dark)
    d.text((int(26*S),h-int(30*S)),status,font=ImageFont.truetype(REG,12*S),fill=(95,99,118))
    fl=ImageFont.truetype(BOLD,13*S); tw=d.textlength("LomoXSoft",font=fl)
    d.text((w-tw-int(14*S),h-int(30*S)),"LomoXSoft",font=fl,fill=(72,44,140))
    d.rectangle([0,0,w-1,h-1],outline=(124,131,157),width=2*S)
    return im.resize((W,H),Image.LANCZOS)

if __name__=="__main__":
    import json, sys
    REC=os.path.join(HERE,"horarios","recursos")
    if "--publica" in sys.argv:
        m=json.load(open(os.path.join(REC,"marca_publica.json"),encoding="utf-8"))
        splash(version="",status="",lineas=m["splash_lineas"]).save(os.path.join(REC,m["splash"])); print("ok", m["splash"]); sys.exit()
    from horarios.textos import MARCA
    L=MARCA["splash_lineas"]
    ic=icon(512); ic.save(os.path.join(HERE,"icon.png"))
    ic.save(os.path.join(HERE,"icon.ico"),sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    splash(lineas=L).save(os.path.join(HERE,"splash.png"))
    splash(version="",status="",lineas=L).save(os.path.join(HERE,"splash_base.png"))  # fondo sin estado para Qt
    print("ok")
