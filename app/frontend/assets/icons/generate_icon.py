from PIL import Image, ImageDraw, ImageFont
import math, os

def draw_icon(size):
    img = Image.new('RGBA', (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    s = size
    r_bg = int(s * 0.20)
    draw.rounded_rectangle([0,0,s,s], radius=r_bg, fill=(22,24,30,255))
    silver = (180,185,195,255)
    silver_dim = (110,118,132,255)
    silver_hi = (220,225,235,255)
    n_bars=4; bar_vals=[0.35,0.55,0.75,1.0]
    chart_l=int(s*0.44); chart_r=int(s*0.88)
    chart_b=int(s*0.80); chart_h=int(s*0.48)
    bar_w=int((chart_r-chart_l)/n_bars*0.56)
    gap=int((chart_r-chart_l-bar_w*n_bars)/(n_bars+1))
    trend_pts=[]
    for i,v in enumerate(bar_vals):
        bx=chart_l+gap+i*(bar_w+gap); bh=int(chart_h*v); by=chart_b-bh
        shade=int(80+90*v)
        draw.rectangle([bx,by,bx+bar_w,chart_b], fill=(shade,shade+8,shade+18,255))
        trend_pts.append((bx+bar_w//2, by-int(s*0.025)))
    lw=max(1,int(s*0.018))
    for k in range(len(trend_pts)-1):
        draw.line([trend_pts[k],trend_pts[k+1]], fill=silver_hi, width=lw)
    dr=max(2,int(s*0.030))
    for p in trend_pts:
        draw.ellipse([p[0]-dr,p[1]-dr,p[0]+dr,p[1]+dr], fill=silver_hi)
    cx_net=int(s*0.295); cy_net=int(s*0.345); r_net=int(s*0.195)
    hex_pts=[(cx_net+int(r_net*math.cos(math.radians(i*60-30))),
              cy_net+int(r_net*math.sin(math.radians(i*60-30)))) for i in range(6)]
    elw=max(1,int(s*0.010))
    for a,b in [(0,2),(1,3),(2,4),(3,5),(4,0),(5,1)]:
        draw.line([hex_pts[a],hex_pts[b]], fill=(*silver_dim[:3],160), width=elw)
    for i in range(6):
        draw.line([hex_pts[i],hex_pts[(i+1)%6]], fill=(*silver_dim[:3],200), width=elw)
    vr=max(2,int(s*0.028))
    for p in hex_pts:
        draw.ellipse([p[0]-vr,p[1]-vr,p[0]+vr,p[1]+vr], fill=silver)
    cr=max(2,int(s*0.036))
    draw.ellipse([cx_net-cr,cy_net-cr,cx_net+cr,cy_net+cr], fill=silver_hi)
    try:
        font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', int(s*0.185))
    except:
        font = ImageFont.load_default()
    label='SDISG'; bbox=draw.textbbox((0,0),label,font=font)
    tw=bbox[2]-bbox[0]; th=bbox[3]-bbox[1]
    tx=(s-tw)//2-bbox[0]; ty=int(s*0.72)-bbox[1]
    sp=int(s*0.03)
    draw.rectangle([tx-sp,ty-sp//2,tx+tw+sp,ty+th+sp//2], fill=(22,24,30,220))
    draw.text((tx,ty), label, font=font, fill=silver_hi)
    bw=max(1,int(s*0.012))
    draw.rounded_rectangle([bw//2,bw//2,s-bw//2,s-bw//2],
                            radius=r_bg, outline=(*silver_dim[:3],80), width=bw)
    return img

out = 'app/frontend/assets/icons/sdisg_icon.ico'
os.makedirs(os.path.dirname(out), exist_ok=True)

# Generar tamaño base grande y reducir con alta calidad
base = draw_icon(512)
imgs = []
for s in [16, 32, 48, 64, 128, 256]:
    resized = base.resize((s, s), Image.LANCZOS)
    imgs.append(resized)

imgs[0].save(out, format='ICO',
             sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)],
             append_images=imgs[1:])
print('ICO generado en:', out)