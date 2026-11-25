"""Concise, traveller-facing itinerary PDF. No model diagnostics or raw coordinates."""
from datetime import date
from io import BytesIO
import math
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import simpleSplit

INK = '#203B35'
GREEN = '#315C4D'
MUTED = '#53665D'
PAPER = '#F8F6EF'
WHITE = '#FFFFFF'
GOLD = '#E7B96B'
SOFT = '#E8EFE6'


def friendly_date(value, fmt='%d %b %Y'):
    try:
        return date.fromisoformat(value).strftime(fmt).lstrip('0')
    except (ValueError, TypeError):
        return str(value)


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def approx(value):
    return f'{math.floor(value + .5)}°C' if finite(value) else ''


def preference(kind):
    return {'indoor': 'Indoor escapes', 'outdoor': 'Outdoor discoveries',
            'mixed': 'Flexible sightseeing'}.get(kind, 'Explore at your pace')


def monthly_summary(forecast):
    values = {v['label']: v['prediction'] for v in forecast['monthly_weather']['variables']}
    t = values.get('Mean temperature')
    score = forecast['predicted_tci']
    mood = 'Great for sightseeing' if score >= 70 else 'A good time to explore' if score >= 50 else 'Plan for indoor breaks'
    clothing = 'Pack light layers.' if not finite(t) or t >= 15 else 'Bring warm layers.'
    if finite(t) and t >= 28:
        clothing = 'Pack light clothes and sun protection.'
    rain = values.get('Monthly rainfall')
    if finite(rain) and rain >= 60:
        clothing += ' Consider a compact umbrella.'
    return mood + (f' | Around {approx(t)} on average' if finite(t) else ''), clothing


def daily_summary(weather):
    t = weather.get('temperature_2m_max')
    rain = weather.get('precipitation_sum')
    wind = weather.get('wind_speed_10m_max')
    parts = [f'High near {approx(t)}'] if finite(t) else []
    if finite(rain):
        parts.append('Rain expected' if rain >= 3 else 'Possible light rain' if rain >= .5 else 'Little rain expected')
    if finite(wind) and wind >= 30:
        parts.append('Windy')
    return ' | '.join(parts) or 'Check local weather before heading out'


def make_guide(plan):
    out = BytesIO()
    pdf = canvas.Canvas(out, pagesize=A4, pageCompression=1)
    pdf.setTitle(f"WanderClimate | {plan['city']} travel guide")
    pdf.setAuthor('WanderClimate')
    W, H = A4
    M = 38
    CW = W - 2*M
    bottom = H - 54
    days = plan['days']
    monthly = plan.get('monthly_forecasts') or []
    changed = {str(c.get('date')) for c in (plan.get('changes') or [])}
    page = 0
    y = 0

    def rect(x, top, w, h, color, radius=0):
        pdf.setFillColor(HexColor(color))
        if radius:
            pdf.roundRect(x, H-top-h, w, h, radius, stroke=0, fill=1)
        else:
            pdf.rect(x, H-top-h, w, h, stroke=0, fill=1)

    def text(value, x, top, size=11, color=INK, bold=False):
        pdf.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
        pdf.setFillColor(HexColor(color))
        pdf.drawString(x, H-top-size, str(value))

    def wrap(value, width, size=11, bold=False):
        font = 'Helvetica-Bold' if bold else 'Helvetica'
        result = []
        for line in simpleSplit(str(value), font, size, width) or ['']:
            # Handle exceptionally long, unbroken attraction names safely.
            while pdf.stringWidth(line, font, size) > width and len(line)>1:
                cut = len(line)
                while cut>1 and pdf.stringWidth(line[:cut],font,size)>width:
                    cut -= 1
                result.append(line[:cut])
                line=line[cut:]
            result.append(line)
        return result

    def lines(value, x, top, width, size=11, color=INK, bold=False, leading=15):
        rows = wrap(value, width, size, bold)
        for i, line in enumerate(rows):
            text(line, x, top+i*leading, size, color, bold)
        return len(rows)*leading

    def circle(x, top, r, color):
        pdf.setFillColor(HexColor(color)); pdf.circle(x, H-top, r, stroke=0, fill=1)

    def footer():
        text('Check opening hours, local weather and travel times before you go.', M, H-39, 8.5, MUTED)
        pdf.setFont('Helvetica', 8.5); pdf.setFillColor(HexColor(MUTED))
        pdf.drawRightString(W-M, 29, f'{page:02d}')

    def new_page():
        nonlocal page, y
        if page:
            footer(); pdf.showPage()
        page += 1
        rect(0, 0, W, H, PAPER)
        rect(0, 0, W, 145 if page == 1 else 87, INK)
        circle(W-77, 50, 27, GOLD)
        # A destination-neutral landscape motif, not an image of the city.
        if page == 1:
            pdf.setFillColor(HexColor(GREEN))
            p = pdf.beginPath(); p.moveTo(W-205, H-145); p.lineTo(W-110, H-78); p.lineTo(W-38, H-145); p.close()
            pdf.drawPath(p, stroke=0, fill=1)
        text('WANDERCLIMATE  /  YOUR TRAVEL GUIDE', M, 23, 9, '#DCE8D8', True)
        city = str(plan['city'])
        title = 'Discover ' + city if page == 1 else city + ' | Your itinerary'
        title_size = 32 if page == 1 else 19
        while pdf.stringWidth(title, 'Helvetica-Bold', title_size) > CW-88 and title_size > 10:
            title_size -= 1
        if page == 1:
            text(title, M, 43, title_size, WHITE, True)
            text(f"{friendly_date(days[0]['date'])} - {friendly_date(days[-1]['date'])}", M, 89, 12, WHITE)
            count = sum(len(d['stops']) for d in days)
            text(f"{len(days)} {'day' if len(days)==1 else 'days'}  /  {count} places to discover", M, 111, 10, '#DCE8D8')
            y = 159
        else:
            text(title, M, 43, title_size, WHITE, True)
            y = 103

    def room(h):
        if y+h > bottom: new_page()

    new_page()
    if monthly:
        for f in monthly:
            headline, tip = monthly_summary(f)
            month = friendly_date(f['target_month']+'-01', '%B %Y')
            height = 66 + max(0,len(wrap(headline,CW-28,13,True))-1)*16 + max(0,len(wrap(tip,CW-28,10))-1)*14
            room(height+12)
            rect(M,y,CW,height,SOFT,10)
            text('WHAT TO EXPECT  /  '+month.upper(),M+14,y+10,8.5,GREEN,True)
            n=lines(headline,M+14,y+25,CW-28,13,INK,True,16)
            lines(tip,M+14,y+30+n,CW-28,10,MUTED,False,14)
            y += height+10
        msg='Early trip plan: monthly estimates, not daily weather. Rebuild within seven days of travel.'
    else:
        msg='Weather-aware plan: check the latest forecast before each day out.'
    y += lines(msg,M,y,CW,9.5,MUTED,False,13)+9
    if changed:
        y += lines('Your itinerary was adjusted after a weather re-check.',M,y,CW,10,GREEN,True,14)+8

    for d in days:
        stops=d['stops']
        groups=[(slot,[s for s in stops if s.get('slot')==slot]) for slot in ('morning','afternoon')]
        extra=[s for s in stops if s.get('slot') not in ('morning','afternoon')]
        if extra: groups.append(('explore',extra))
        weather = '' if monthly else daily_summary(d.get('weather') or {})
        subtitle=preference(d['day_type']) + (' | Updated' if d['date'] in changed else '')
        if weather: subtitle += ' | ' + weather
        sub_h=len(wrap(subtitle,CW-28,10))*13
        rows_h=sum(14+sum(max(1,len(wrap(s['name'],CW-69,11,True)))*14+2 for s in ss) for _,ss in groups if ss)
        height=40+sub_h+rows_h+(22 if not stops else 0)+10
        room(height+11)
        start=y
        rect(M,start,CW,height,WHITE,10)
        rect(M+12,start+12,35,25,GREEN,6)
        text(f"DAY {d['number']}",M+17,start+18,9,WHITE,True)
        text(friendly_date(d['date'],'%a, %d %b %Y'),M+58,start+12,15,INK,True)
        y=start+38
        y+=lines(subtitle,M+14,y,CW-28,10,MUTED,False,13)+3
        for slot, ss in groups:
            if not ss: continue
            text(slot.upper(),M+14,y,8.5,GREEN,True); y+=14
            for s in ss:
                name=str(s['name'])
                circle(M+19,y+7,3,GOLD)
                h=lines(name,M+30,y,CW-69,11,INK,True,14)
                if finite(s.get('lat')) and finite(s.get('lon')):
                    pdf.linkURL(f"https://www.google.com/maps/search/?api=1&query={s['lat']},{s['lon']}",(M+28,H-y-h,W-M-12,H-y+2),relative=0)
                y+=h+2
        if not stops: y+=lines('Free time to explore at your own pace.',M+14,y,CW-28,11,MUTED,False,15)
        y=start+height+11
    room(29)
    link_note = 'Tap a place name to open it on the map. ' if any(finite(s.get('lat')) and finite(s.get('lon')) for d in days for s in d['stops']) else ''
    lines(link_note + 'Visit order is a guide, not turn-by-turn directions.',M,y,CW,9,MUTED,False,13)
    footer(); pdf.save()
    return out.getvalue()
