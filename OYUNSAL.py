# Street Outlaw - Pygame version v2
# pip install pygame | python game.py
# WASD hareket/sür, Mouse nişan, Click ateş, 1/2/3 silah, E bin/in, R mermi

import pygame
import math
import random
import json
import os

SAVE_FILE = "savegame.json"

pygame.init()
W, H = 960, 640
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Street Outlaw Pygame - Healer + Roketçi")
clock = pygame.time.Clock()
font = pygame.font.SysFont("arial", 18, bold=True)
small = pygame.font.SysFont("arial", 14)
big = pygame.font.SysFont("arial", 22, bold=True)

WORLD = 2400

WEAPONS = [
    {"name": "Fists",  "dmg": 25, "cd": 0.35, "auto": False},
    {"name": "Pistol", "dmg": 34, "cd": 0.28, "auto": False},
    {"name": "Rifle",  "dmg": 26, "cd": 0.11, "auto": True},
]

player = {"x": 1200, "y": 1200, "angle": 0, "hp": 100, "maxhp": 100,
          "weapon": 0, "ammo": 120, "cd": 0, "in_car": None}

# --- DİREK + AĞAÇ (engel) ---
# yollara ve binalara gelmeyecek şekilde rastgele yerleştir
def is_on_road(x, y):
    for i in range(200, WORLD, 400):
        if abs(x - i) < 70 or abs(y - i) < 70:
            return True
    return False

def is_in_building(x, y):
    for bx in range(6):
        for by in range(6):
            bx0, by0 = 80 + bx * 400, 80 + by * 400
            if bx0 - 20 < x < bx0 + 220 and by0 - 20 < y < by0 + 220:
                return True
    return False

obstacles = []  # {x,y,r,kind: tree/pole}
for _ in range(35):  # ağaçlar
    for _try in range(20):
        x, y = random.randint(60, WORLD-60), random.randint(60, WORLD-60)
        if is_on_road(x, y) or is_in_building(x, y):
            continue
        if math.hypot(x-1200, y-1200) < 150:
            continue
        obstacles.append({"x": x, "y": y, "r": 14, "kind": "tree",
                          "seed": random.random()})
        break
for _ in range(55):  # direkler SADECE gri yol üstünde
    for _try in range(20):
        i = random.choice(range(200, WORLD, 400))
        along = random.randint(60, WORLD-60)
        # yolun gri şeridi: merkezden ±40 (yol yarı genişliği 60, gri alan)
        off = random.choice([-45, 45])
        if random.random() < 0.5:
            x, y = i + off, along
        else:
            x, y = along, i + off
        # gri kontrolü: gerçekten yol üstünde mi?
        on_gray_x = any(abs(x - j) < 60 for j in range(200, WORLD, 400))
        on_gray_y = any(abs(y - j) < 60 for j in range(200, WORLD, 400))
        if not (on_gray_x or on_gray_y):
            continue
        if is_in_building(x, y):
            continue
        obstacles.append({"x": x, "y": y, "r": 6, "kind": "pole",
                          "phase": random.random() * 6.28})  # ışık titremesi için
        break

def hit_obstacle(x, y, r=10):
    for o in obstacles:
        if math.hypot(x-o["x"], y-o["y"]) < r + o["r"]:
            return o
    return None


def try_move(en, nx, ny, r=10):
    # engele takılmadan ilerle: önce düz, sonra eksen boyunca kay, sonra engelin etrafından dolan
    if not hit_obstacle(nx, ny, r):
        en["x"], en["y"] = nx, ny
        return True
    if not hit_obstacle(nx, en["y"], r):
        en["x"] = nx
        return True
    if not hit_obstacle(en["x"], ny, r):
        en["y"] = ny
        return True
    o = hit_obstacle(nx, ny, r)
    if o:
        ox, oy = en["x"] - o["x"], en["y"] - o["y"]
        dd = math.hypot(ox, oy) or 1
        tx_, ty_ = -oy / dd, ox / dd
        step = max(1.5, math.hypot(nx - en["x"], ny - en["y"]))
        side = en.get("side", 1)
        for sgn in (side, -side):
            cx = en["x"] + tx_ * step * sgn + ox / dd * step * 0.4
            cy = en["y"] + ty_ * step * sgn + oy / dd * step * 0.4
            if not hit_obstacle(cx, cy, r):
                en["x"], en["y"] = cx, cy
                en["side"] = sgn
                return True
    return False

def unstick(en, r=8):
    # engelin içinde sıkışmışsa dışarı it
    o = hit_obstacle(en["x"], en["y"], r)
    if o:
        ox, oy = en["x"] - o["x"], en["y"] - o["y"]
        dd = math.hypot(ox, oy) or 1
        push = (r + o["r"]) - dd + 1
        en["x"] += ox / dd * push
        en["y"] += oy / dd * push

# --- ARABA REWORK: her arabanın canı var, patlayınca -50 ---
CAR_MAXHP = 150
cars = [
    {"x": 1250, "y": 1150, "angle": 0,   "speed": 0, "color": (255, 59, 48),  "w": 52, "h": 26, "hp": CAR_MAXHP, "maxhp": CAR_MAXHP, "wreck": False},
    {"x": 1050, "y": 1300, "angle": 1.5, "speed": 0, "color": (10, 132, 255), "w": 52, "h": 26, "hp": CAR_MAXHP, "maxhp": CAR_MAXHP, "wreck": False},
    {"x": 1400, "y": 1350, "angle": 0.5, "speed": 0, "color": (255, 204, 0),  "w": 56, "h": 28, "hp": 180, "maxhp": 180, "wreck": False},
    {"x": 950,  "y": 1050, "angle": 2.2, "speed": 0, "color": (48, 209, 88),  "w": 52, "h": 26, "hp": CAR_MAXHP, "maxhp": CAR_MAXHP, "wreck": False},
    {"x": 1500, "y": 1100, "angle": 0,   "speed": 0, "color": (191, 90, 242), "w": 52, "h": 26, "hp": CAR_MAXHP, "maxhp": CAR_MAXHP, "wreck": False},
    {"x": 1200, "y": 1500, "angle": 0,   "speed": 0, "color": (240, 240, 240),"w": 52, "h": 26, "hp": CAR_MAXHP, "maxhp": CAR_MAXHP, "wreck": False},
]

def damage_car(c, amount, cause=""):
    if c.get("wreck"):
        return
    if god and player.get("in_car") is c:
        return  # god mod: araban patlamaz
    c["hp"] -= amount
    if c["hp"] <= 0:
        blow_up_car(c, cause)

def blow_up_car(c, cause=""):
    # araba patlar, içindeki oyuncu dışarı fırlar ve -50 yer
    global msg, msg_t
    c["hp"] = 0; c["wreck"] = True; c["speed"] = 0
    explode(c["x"], c["y"], 110)
    explode(c["x"], c["y"], 60)
    if player.get("in_car") is c:
        player["in_car"] = None
        player["x"], player["y"] = c["x"] + 60, c["y"]
        player["hp"] -= 50  # orijinal canımızdan -50
        msg, msg_t = f"💥 ARABA PATLADI! ({cause}) -50 yedin!", 2.5
    else:
        msg, msg_t = f"💥 Araba patladı! ({cause})", 2

bullets, enemies, pickups, particles, explosions = [], [], [], [], []
planes, bombs = [], []
# --- NÜKLEER HELİKOPTER ---
helis, nukes, nuke_fx = [], [], []
NUKE_R = 1050       # patlama yarıçapı (BUFF: 650 -> 1050)
NUKE_LETHAL = 0.75  # bu orandaki iç bölge = anında ölüm
NUKE_FUSE = 7.0     # bomba düştükten sonra patlamaya kadar saniye
nuke_zones = []     # patlamadan sonra kalan radyasyon bölgeleri
nuke_shake = 0
shake_x, shake_y = 0, 0
freeze_t, freeze_immune = 0.0, 0.0  # donma süresi / donma sonrası dokunulmazlık
god = False         # god mod: 1,2,3,4,5,6,7,8,9 sırayla basınca açılır/kapanır
cheat_idx = 0
# konsol: c,o,n,s,o,l,e yazınca açılır
console_open = False
console_buf = ""
console_log = []
console_idx = 0
shades = []          # kara gölgeler (7. dalgadan itibaren): SALDIRMA!
shade_timer = 6.0
shade_attacked = False
CONSOLE_SEQ = [pygame.K_c, pygame.K_o, pygame.K_n, pygame.K_s, pygame.K_o, pygame.K_l, pygame.K_e]
CHEAT_SEQ = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
             pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9]
heli_timer = 40     # ilk helikopter (2. dalgadan itibaren) ~40 sn sonra
nuke_flash = 0
kills, wanted = 0, 0
# --- DALGA SİSTEMİ ---
wave = 1
wave_queue = []  # çıkmayı bekleyen tipler
wave_spawn_timer = 0
wave_break_timer = 0  # dalga arası mola
wave_total = 0
wave_banner_t = 0
cam_x, cam_y = player["x"], player["y"]
plane_timer = 6  # ilk uçak 6 sn sonra
prev_tax, prev_tay = player["x"], player["y"]
player_vx, player_vy = 0, 0

def make_wave(n):
    # dalga n: toplam = 4 + n*2, içerik dalgayla zorlaşır
    q = []
    total = 4 + n * 2
    for _ in range(total):
        r = random.random()
        # kılıçlı manyaklar 2. dalgadan itibaren, dalga ilerledikçe artar
        if n >= 2 and random.random() < min(0.30, 0.12 + n * 0.02):
            q.append("sword")
            continue
        # donduranlar 5. dalgadan itibaren
        if n >= 5 and random.random() < min(0.28, 0.10 + (n - 4) * 0.03):
            q.append("freezer")
            continue
        if n >= 3 and r < 0.12 + n * 0.01:
            q.append("rocket")
        elif n >= 2 and r < 0.30:
            q.append("healer")
        elif n >= 2 and r < 0.55:
            q.append("cop")  # maviler 2. dalgadan itibaren
        elif r < 0.70:
            q.append("cop" if n >= 4 and random.random() < 0.5 else "normal")
        else:
            q.append("normal")
    random.shuffle(q)
    if n % 5 == 0:
        # her 5. dalgada BOSS en önde, yanında 2 dondurucu
        q.insert(0, "boss")
        q += ["freezer", "freezer"]
    return q

def spawn_enemy(force_type=None, ignore_cap=False):
    if not ignore_cap and len(enemies) > 7 + wanted * 2:
        return
    a = random.random() * math.pi * 2
    d = 500 + random.random() * 400
    x = max(50, min(WORLD-50, player["x"] + math.cos(a)*d))
    y = max(50, min(WORLD-50, player["y"] + math.sin(a)*d))

    # tip seç: normal / cop / healer(yeşil) / rocket(kasklı kırmızı)
    if force_type is None:
        r = random.random()
        if kills >= 2 and r < 0.18:
            typ = "rocket"
        elif r < 0.36:
            typ = "healer"
        elif wanted >= 2 and r < 0.6:
            typ = "cop"
        else:
            typ = "normal"
    else:
        typ = force_type

    if typ == "healer":
        enemies.append({"x": x, "y": y, "type": "healer", "hp": 60, "maxhp": 60,
                        "speed": 2.0, "cd": 0, "heal_cd": 0, "cop": False})
    elif typ == "rocket":
        enemies.append({"x": x, "y": y, "type": "rocket", "hp": 90, "maxhp": 90,
                        "speed": 1.5, "cd": 1.5 + random.random(), "cop": False})
    elif typ == "cop":
        enemies.append({"x": x, "y": y, "type": "cop", "hp": 70, "maxhp": 70,
                        "speed": 2.4, "cd": 1 + random.random(), "cop": True})
    elif typ == "freezer":
        enemies.append({"x": x, "y": y, "type": "freezer", "hp": 70, "maxhp": 70,
                        "speed": 2.0, "cd": 1.5 + random.random(), "cop": False})
    elif typ == "boss":
        bhp = 900 + (wave // 5 - 1) * 500
        enemies.append({"x": x, "y": y, "type": "boss", "hp": bhp, "maxhp": bhp,
                        "speed": 1.6, "cd": 2.0, "cop": False, "nova_cd": 4.0,
                        "nova_t": 0.0, "summoned": 0})
    elif typ == "sword":
        # kılıçlı manyak: yaklaşır, işaret verir, sonra DASH atıp kılıçla keser
        enemies.append({"x": x, "y": y, "type": "sword", "hp": 105, "maxhp": 105,
                        "speed": 2.6, "cd": 1.0 + random.random(), "cop": False,
                        "state": "walk", "st": 0.0, "dir": 0.0, "hit": False,
                        "tcd": 1.5 + random.random()*1.5, "combo": 0})
    else:
        enemies.append({"x": x, "y": y, "type": "normal", "hp": 50, "maxhp": 50,
                        "speed": 1.7, "cd": 1 + random.random(), "cop": False})

def do_save():
    try:
        data = {"wave": wave, "kills": kills, "wanted": wanted,
                "ammo": player["ammo"], "weapon": player["weapon"],
                "hp": 100, "px": 1200, "py": 1200}
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f)
        return True
    except Exception as e:
        print("save hatası:", e)
        return False

def load_save():
    try:
        if not os.path.exists(SAVE_FILE):
            return None
        with open(SAVE_FILE) as f:
            return json.load(f)
    except Exception:
        return None

def spawn_pickup(x=None, y=None):
    pickups.append({"x": x or random.randint(100, WORLD-100),
                    "y": y or random.randint(100, WORLD-100),
                    "type": random.choice(["ammo", "health"])})

for _ in range(8):
    spawn_pickup()
# dalga 1'i başlat
wave_queue = make_wave(1)
wave_total = len(wave_queue)
wave_banner_t = 3
msg, msg_t = "DALGA 1 başlıyor!", 3

msg, msg_t = "Yeşil heal basar! Kasklı kırmızı roket atar! Dikkat!", 5
mouse_down = False
prev_click = False

def px(wx): return int(wx - cam_x + W//2 + shake_x)
def py(wy): return int(wy - cam_y + H//2 + shake_y)

def draw_health_bar(sx, sy, w, ratio, big_bar=False):
    h = 8 if big_bar else 5
    pygame.draw.rect(screen, (0, 0, 0), (sx - w//2 - 1, sy - 1, w + 2, h + 2))
    pygame.draw.rect(screen, (200, 0, 0), (sx - w//2, sy, w, h))
    col = (0, 220, 0) if ratio > 0.5 else (255, 200, 0) if ratio > 0.25 else (255, 50, 50)
    pygame.draw.rect(screen, col, (sx - w//2, sy, int(w * max(0, ratio)), h))

def spawn_plane(cx, cy, vx, vy):
    # ekranın rastgele bir kenarından doğ, gittiğin yöne (tahmini konuma) uç
    side = random.choice(["left", "right", "top", "bottom"])
    if side == "left": sx, sy = cx - 900, cy + random.uniform(-500, 500)
    elif side == "right": sx, sy = cx + 900, cy + random.uniform(-500, 500)
    elif side == "top": sx, sy = cx + random.uniform(-500, 500), cy - 700
    else: sx, sy = cx + random.uniform(-500, 500), cy + 700
    # gittiğin yeri hedefle: konum + hız * 1.2 sn (önüne atar)
    lead = 1.3
    tx = max(50, min(WORLD-50, cx + vx * lead))
    ty = max(50, min(WORLD-50, cy + vy * lead))
    ang = math.atan2(ty - sy, tx - sx)
    planes.append({"x": sx, "y": sy, "angle": ang, "speed": 270,
                   "bomb_cd": 1.0, "hp": 60, "maxhp": 60})
    return tx, ty

def spawn_heli():
    # hedef: haritanın ortası YA DA bir kenarı
    if random.random() < 0.5:
        tx, ty, where = WORLD / 2, WORLD / 2, "HARİTANIN ORTASINA"
    else:
        m = 250
        side = random.choice(["left", "right", "top", "bottom"])
        if side == "left": tx, ty = m, random.uniform(m, WORLD - m)
        elif side == "right": tx, ty = WORLD - m, random.uniform(m, WORLD - m)
        elif side == "top": tx, ty = random.uniform(m, WORLD - m), m
        else: tx, ty = random.uniform(m, WORLD - m), WORLD - m
        where = "HARİTANIN KENARINA"
    while True:
        a = random.random() * math.pi * 2
        sx = max(-300, min(WORLD + 300, tx + math.cos(a) * 1600))
        sy = max(-300, min(WORLD + 300, ty + math.sin(a) * 1600))
        if math.hypot(tx - sx, ty - sy) > 900:
            break
    helis.append({"x": sx, "y": sy, "angle": math.atan2(ty - sy, tx - sx),
                  "speed": 170, "hp": 700, "maxhp": 700, "tx": tx, "ty": ty,
                  "dropped": False, "rot": 0.0})
    return where

def draw_offscreen_arrow(wx, wy, color, label):
    # hedef ekran dışındaysa kenarda yön oku göster
    sx, sy = px(wx), py(wy)
    if 30 < sx < W - 30 and 30 < sy < H - 30:
        return
    ang = math.atan2(sy - H / 2, sx - W / 2)
    c, s = math.cos(ang), math.sin(ang)
    t = min((W / 2 - 40) / abs(c) if abs(c) > 1e-6 else 1e9,
            (H / 2 - 40) / abs(s) if abs(s) > 1e-6 else 1e9)
    ex, ey = W / 2 + c * t, H / 2 + s * t
    pts = []
    for dx, dy in [(14, 0), (-10, 9), (-10, -9)]:
        pts.append((ex + dx * c - dy * s, ey + dx * s + dy * c))
    pygame.draw.polygon(screen, color, pts)
    pygame.draw.polygon(screen, (0, 0, 0), pts, 2)
    screen.blit(small.render(label, True, color), (ex - 22, ey - 28 if ey > 60 else ey + 14))

def freeze_player(sec):
    # oyuncuyu (arabadaysa arabayı) dondurur; arka arkaya kilitlememek için kısa dokunulmazlık var
    global freeze_t, freeze_immune, msg, msg_t
    if god or freeze_t > 0 or freeze_immune > 0:
        return
    freeze_t = sec
    freeze_immune = sec + 2.5
    msg, msg_t = "❄ DONDUN! Hareket edemezsin (ateş edebilirsin)!", 1.8

def drop_bomb(x, y):
    # bombanın düştüğü yerde 1.1 sn uyarı halkası, sonra patlama
    bombs.append({"x": x, "y": y, "timer": 1.1, "max": 1.1})

def explode(x, y, radius=70):
    explosions.append({"x": x, "y": y, "r": 10, "max": radius, "life": 0.35})
    for _ in range(18):
        ang = random.random() * math.pi * 2
        sp = random.uniform(30, 220)
        particles.append({"x": x, "y": y, "vx": math.cos(ang)*sp,
                          "vy": math.sin(ang)*sp, "life": random.uniform(0.2, 0.6),
                          "color": random.choice([(255, 150, 0), (255, 50, 50), (255, 230, 0), (120, 120, 120)])})

def hurt_shade(sh, dmg):
    # kara gölgeye saldırmak lanetlenmek demek: her isabette -10 can
    global shade_attacked, msg, msg_t
    sh["hp"] -= dmg
    sh["flash"] = 0.5
    shade_attacked = True
    player["hp"] -= 10
    msg, msg_t = "☠ KARA GÖLGEYE SALDIRDIN! Lanet: -10", 1.5

def spawn_shade():
    a = random.random() * math.pi * 2
    d = 450 + random.random() * 300
    shades.append({"x": max(60, min(WORLD - 60, player["x"] + math.cos(a) * d)),
                   "y": max(60, min(WORLD - 60, player["y"] + math.sin(a) * d)),
                   "hp": 80, "maxhp": 80, "dir": random.random() * math.pi * 2,
                   "turn": random.uniform(2, 4), "flash": 0.0, "age": 0.0, "life": 50.0,
                   "ram_cd": 0.0})
def jump_to_wave(n):
    # istenen dalgaya direkt atla: sahayı temizle, o dalgayı baştan başlat
    global wave, wave_queue, wave_total, wave_break_timer, wave_banner_t, wave_spawn_timer
    global wanted, msg, msg_t, plane_timer, heli_timer, freeze_t, shade_attacked
    enemies.clear(); planes.clear(); bombs.clear(); shades.clear(); helis.clear(); nukes.clear(); nuke_zones.clear()
    shade_attacked = False
    bullets[:] = [b for b in bullets if not b.get("foe")]
    wave = n
    wanted = min(5, wave // 2)
    wave_queue = make_wave(wave)
    wave_total = len(wave_queue)
    wave_break_timer = 0
    wave_spawn_timer = 0
    wave_banner_t = 3
    plane_timer = 6
    heli_timer = 45
    freeze_t = 0.0
    msg, msg_t = f"DALGA {wave} başlıyor! ({wave_total} düşman)", 3

def run_console(cmd):
    global god
    parts = cmd.strip().lower().split()
    if not parts:
        return ""
    if parts[0] == "god" and (len(parts) == 1 or parts[1] == "mode"):
        god = not god
        return "god mode: " + ("AÇIK" if god else "KAPALI")
    if parts[0] in ("wave", "dalga"):
        arg = parts[1].strip("[]") if len(parts) > 1 else ""
        if not arg.isdigit():
            return "kullanım: wave [dalga no]   örn: wave 10"
        n = int(arg)
        if n < 1 or n > 200:
            return "dalga no 1-200 arası olmalı"
        jump_to_wave(n)
        return f"dalga {n}'e atlandı"
    if parts[0] == "help":
        return "komutlar: god mode | wave [dalga no]"
    return "bilinmeyen komut. komutlar: god mode | wave [dalga no]"

save_info = load_save()
if save_info:
    print(f"Save bulundu: dalga {save_info.get('wave')}")
save_hud_txt = f"💾 Save: Dalga {save_info['wave']}" if save_info else "💾 Save yok (5. dalgada alınır) | L: yükle"
save_hud_tick = 0
running = True
while running:
    dt = min(0.033, clock.tick(60) / 1000.0)
    player["cd"] -= dt
    msg_t -= dt
    freeze_t = max(0.0, freeze_t - dt)
    freeze_immune = max(0.0, freeze_immune - dt)

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            mouse_down = True
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            mouse_down = False
        if e.type == pygame.KEYDOWN:
            # --- KONSOL ---
            if console_open:
                if e.key == pygame.K_ESCAPE:
                    console_open = False
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    out = run_console(console_buf)
                    if console_buf.strip():
                        console_log.append("> " + console_buf)
                        if out:
                            console_log.append(out)
                        console_log = console_log[-6:]
                    console_buf = ""
                elif e.key == pygame.K_BACKSPACE:
                    console_buf = console_buf[:-1]
                else:
                    ch = getattr(e, "unicode", "")
                    if ch and ch.isprintable() and len(console_buf) < 40:
                        console_buf += ch
                continue  # konsol açıkken oyun tuşları çalışmaz
            # konsolu açma kodu: c,o,n,s,o,l,e  (l ve e'nin normal işlevi bu sırada çalışmaz)
            if pygame.K_a <= e.key <= pygame.K_z:
                if e.key == CONSOLE_SEQ[console_idx]:
                    console_idx += 1
                    if console_idx == len(CONSOLE_SEQ):
                        console_open = True
                        console_idx = 0
                        console_buf = ""
                        console_log = ["konsol açıldı. komutlar: god mode | wave [dalga no]  (ESC: kapat)"]
                        continue
                    if console_idx == 6:
                        continue  # 'l' tuşu: save yüklemesin
                else:
                    console_idx = 1 if e.key == CONSOLE_SEQ[0] else 0
            # GOD MOD kodu: 1 2 3 4 5 6 7 8 9 (sırayla, arada yanlış rakam olmadan)
            if e.key in CHEAT_SEQ:
                if e.key == CHEAT_SEQ[cheat_idx]:
                    cheat_idx += 1
                    if cheat_idx == len(CHEAT_SEQ):
                        god = not god
                        cheat_idx = 0
                        msg, msg_t = ("⚡ GOD MOD AÇIK! Ölümsüzsün" if god else "GOD MOD kapandı"), 3
                else:
                    cheat_idx = 1 if e.key == CHEAT_SEQ[0] else 0
            if e.key == pygame.K_1: player["weapon"] = 0; msg, msg_t = "Equipped Fists", 1.5
            if e.key == pygame.K_2: player["weapon"] = 1; msg, msg_t = "Equipped Pistol", 1.5
            if e.key == pygame.K_3: player["weapon"] = 2; msg, msg_t = "Equipped Rifle", 1.5
            if e.key == pygame.K_r:
                player["ammo"] += 60; msg, msg_t = "+60 rifle ammo", 1.5
            if e.key == pygame.K_e and freeze_t <= 0:
                if player["in_car"]:
                    c = player["in_car"]; c["speed"] = 0
                    player["in_car"] = None
                    player["x"], player["y"] = c["x"] + 60, c["y"]
                    msg, msg_t = f"Arabadan indin (araba %{int(100*c['hp']/c['maxhp'])})", 1.5
                else:
                    best, bd = None, 90
                    for c in cars:
                        if c.get("wreck"):
                            continue
                        d = math.hypot(c["x"]-player["x"], c["y"]-player["y"])
                        if d < bd: bd, best = d, c
                    if best:
                        player["in_car"] = best; msg, msg_t = f"Sürüyorsun! Can %{int(100*best['hp']/best['maxhp'])} | E ile in", 2
                    else:
                        # hurda mı yakınında?
                        wreck_near = any(math.hypot(c["x"]-player["x"], c["y"]-player["y"]) < 90 and c.get("wreck") for c in cars)
                        msg, msg_t = ("Bu araba patlamış! 💥" if wreck_near else "Yakında araba yok!"), 1.5
            if e.key == pygame.K_ESCAPE:
                running = False
            # manuel save yükleme: L tuşu
            if e.key == pygame.K_l:
                s = load_save()
                if s:
                    wave = s["wave"]; kills = s["kills"]; wanted = s["wanted"]
                    player.update(hp=100, x=1200, y=1200, in_car=None,
                                  ammo=s.get("ammo", 120), weapon=s.get("weapon", 0))
                    enemies.clear(); bullets.clear(); planes.clear(); bombs.clear()
                    freeze_t = 0; freeze_immune = 0; shades.clear(); helis.clear(); nukes.clear(); nuke_fx.clear(); nuke_zones.clear(); nuke_flash = 0; heli_timer = 45
                    wave_queue = make_wave(wave); wave_total = len(wave_queue)
                    wave_break_timer = 0; wave_banner_t = 3; plane_timer = 6
                    msg, msg_t = f"Save yüklendi: DALGA {wave}", 3
                else:
                    msg, msg_t = "Save yok! (her 5 dalgada alınır)", 2

    if not console_open:
        keys = pygame.key.get_pressed()
        mx, my = pygame.mouse.get_pos()
        tax = player["in_car"]["x"] if player["in_car"] else player["x"]
        tay = player["in_car"]["y"] if player["in_car"] else player["y"]
        # oyuncu hızı (uçağın önüne bomba atması için)
        player_vx = (tax - prev_tax) / max(dt, 0.001)
        player_vy = (tay - prev_tay) / max(dt, 0.001)
        prev_tax, prev_tay = tax, tay
        mwx, mwy = mx - W//2 + cam_x, my - H//2 + cam_y
        player["angle"] = math.atan2(mwy - tay, mwx - tax)

        # --- hareket ---
        if player["in_car"]:
            c = player["in_car"]
            acc = (320 if keys[pygame.K_w] else 0) + (-200 if keys[pygame.K_s] else 0)
            turn = (-2.6 if keys[pygame.K_a] else 0) + (2.6 if keys[pygame.K_d] else 0)
            if freeze_t > 0:
                acc = 0; turn = 0; c["speed"] *= 0.85  # araba buz tuttu
            c["speed"] += (acc - c["speed"]*1.2) * dt
            c["speed"] = max(-140, min(380, c["speed"]))
            if abs(c["speed"]) > 10:
                c["angle"] += turn * dt * (c["speed"]/200)
            nx = c["x"] + math.cos(c["angle"])*c["speed"]*dt
            ny = c["y"] + math.sin(c["angle"])*c["speed"]*dt
            # direk/ağaç çarpması: hızı kes + sertse araba hasar alır
            if hit_obstacle(nx, ny, 20):
                if abs(c["speed"]) > 200:
                    damage_car(c, 15, "duvara çarptın")
                c["speed"] *= 0.3
            else:
                c["x"], c["y"] = nx, ny
            c["x"] = max(30, min(WORLD-30, c["x"])); c["y"] = max(30, min(WORLD-30, c["y"]))
            player["x"], player["y"] = c["x"], c["y"]
            cam_x += (c["x"]-cam_x)*0.12; cam_y += (c["y"]-cam_y)*0.12
            # arabadayken sen iyileşmezsin, araba da kendiliğinden iyileşmez
            pass
            for en in enemies:
                if math.hypot(en["x"]-c["x"], en["y"]-c["y"]) < 42 and abs(c["speed"]) > 80:
                    en["hp"] -= (80 if en["type"] == "boss" else 300)*dt
            for sh in shades:
                if sh["ram_cd"] <= 0 and math.hypot(sh["x"]-c["x"], sh["y"]-c["y"]) < 44 and abs(c["speed"]) > 80:
                    sh["ram_cd"] = 0.4
                    hurt_shade(sh, 60)
        else:
            ix = (1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0)
            iy = (1 if keys[pygame.K_s] else 0) - (1 if keys[pygame.K_w] else 0)
            if freeze_t > 0:
                ix = iy = 0  # donmuş
            l = math.hypot(ix, iy) or 1
            nx = player["x"] + ix/l*230*dt; ny = player["y"] + iy/l*230*dt
            if not hit_obstacle(nx, ny, 12):
                player["x"], player["y"] = nx, ny
            player["x"] = max(30, min(WORLD-30, player["x"])); player["y"] = max(30, min(WORLD-30, player["y"]))
            cam_x += (player["x"]-cam_x)*0.15; cam_y += (player["y"]-cam_y)*0.15

            w = WEAPONS[player["weapon"]]
            want = (mouse_down if w["auto"] else (mouse_down and not prev_click)) and not console_open
            if want and player["cd"] <= 0 and freeze_t <= 0:
                if player["weapon"] == 0:
                    player["cd"] = w["cd"]
                    for en in enemies:
                        if math.hypot(en["x"]-player["x"], en["y"]-player["y"]) < 70:
                            en["hp"] -= w["dmg"]
                    for sh in shades:
                        if math.hypot(sh["x"]-player["x"], sh["y"]-player["y"]) < 70:
                            hurt_shade(sh, w["dmg"])
                else:
                    if player["weapon"] == 2 and player["ammo"] <= 0:
                        msg, msg_t = "Mermi yok! R'ye bas", 1.5
                    else:
                        if player["weapon"] == 2: player["ammo"] -= 1
                        player["cd"] = w["cd"]
                        a = player["angle"] + random.uniform(-0.06, 0.06)
                        sx = player["x"]+math.cos(a)*22; sy = player["y"]+math.sin(a)*22
                        bullets.append({"x": sx, "y": sy, "vx": math.cos(a)*11,
                                        "vy": math.sin(a)*11, "life": 50, "dmg": w["dmg"],
                                        "foe": False, "rocket": False})
        prev_click = mouse_down

        # --- mermiler + roketler (direk/ağaçlara çarpar) ---
        for b in bullets:
            b["x"] += b["vx"]; b["y"] += b["vy"]; b["life"] -= 1
            if hit_obstacle(b["x"], b["y"], 3):
                b["life"] = 0
                if not b.get("foe"):
                    particles.append({"x": b["x"], "y": b["y"], "vx": 0, "vy": 0,
                                      "life": 0.15, "color": (200, 200, 200)})
            if b.get("ice") and random.random() < 0.5:
                particles.append({"x": b["x"], "y": b["y"], "vx": random.uniform(-15, 15),
                                  "vy": random.uniform(-15, 15), "life": 0.3, "color": (170, 225, 255)})
            if b.get("rocket"):
                particles.append({"x": b["x"], "y": b["y"], "vx": random.uniform(-20, 20),
                                  "vy": random.uniform(-20, 20), "life": 0.25, "color": (255, 150, 0)})
        bullets = [b for b in bullets if b["life"] > 0]

        for b in bullets[:]:
            if not b["foe"]:
                for en in enemies:
                    if math.hypot(en["x"]-b["x"], en["y"]-b["y"]) < 14:
                        en["hp"] -= b["dmg"]; b["life"] = 0; break
                # uçakları da vurabilirsin!
                if b["life"] > 0:
                    for pl in planes:
                        if math.hypot(pl["x"]-b["x"], pl["y"]-b["y"]) < 22:
                            pl["hp"] -= b["dmg"]; b["life"] = 0
                            particles.append({"x": b["x"], "y": b["y"], "vx": 0, "vy": -30,
                                              "life": 0.3, "color": (255, 255, 0)})
                            break
                # kara gölgeye ateş etme!
                if b["life"] > 0:
                    for sh in shades:
                        if math.hypot(sh["x"]-b["x"], sh["y"]-b["y"]) < 20:
                            hurt_shade(sh, b["dmg"]); b["life"] = 0
                            break
                # nükleer helikopteri de vurabilirsin!
                if b["life"] > 0:
                    for hl in helis:
                        if math.hypot(hl["x"]-b["x"], hl["y"]-b["y"]) < 30:
                            hl["hp"] -= b["dmg"]; b["life"] = 0
                            particles.append({"x": b["x"], "y": b["y"], "vx": 0, "vy": -30,
                                              "life": 0.3, "color": (255, 255, 0)})
                            break
            else:
                if b.get("rocket"):
                    d = math.hypot(tax-b["x"], tay-b["y"])
                    hit_r = 30 if player["in_car"] else 16
                    if d < hit_r or b["life"] <= 0:
                        b["life"] = 0
                        explode(b["x"], b["y"], 75)
                        if math.hypot(tax-b["x"], tay-b["y"]) < 90:
                            if player["in_car"]:
                                # REWORK: arabadaysan araba patlar, sen -50 yersin
                                damage_car(player["in_car"], 200, "roket yedin")
                            else:
                                player["hp"] -= 40
                                msg, msg_t = "-40! Roket yedin!", 1.2
                elif b.get("ice"):
                    r = 32 if player["in_car"] else 15
                    if math.hypot(tax-b["x"], tay-b["y"]) < r:
                        b["life"] = 0
                        freeze_player(b.get("freeze", 1.4))
                        if player["in_car"]:
                            damage_car(player["in_car"], b["dmg"], "buz mermisi")
                        else:
                            player["hp"] -= b["dmg"]
                else:
                    r = 26 if player["in_car"] else 12
                    if math.hypot(tax-b["x"], tay-b["y"]) < r:
                        b["life"] = 0
                        if player["in_car"]:
                            # mermi arabaya işler, sana değil
                            damage_car(player["in_car"], b["dmg"], "taranıyorsun")
                        else:
                            player["hp"] -= b["dmg"]*(1.0 if b.get("dagger") else 0.4)
        bullets = [b for b in bullets if b["life"] > 0]

        # --- uçaklar: gittiğin yeri bombalar ---
        plane_timer -= dt
        # wanted arttıkça daha sık gelir
        interval = max(3.5, 11 - wanted * 1.2 - wave * 0.5)
        if plane_timer <= 0:
            tx_, ty_ = spawn_plane(tax, tay, player_vx, player_vy)
            plane_timer = interval + random.uniform(0, 3)
            msg, msg_t = "✈ UÇAK GELİYOR! Kaç! Bombalar düşecek!", 2.5
        for pl in planes:
            pl["x"] += math.cos(pl["angle"]) * pl["speed"] * dt
            pl["y"] += math.sin(pl["angle"]) * pl["speed"] * dt
            pl["bomb_cd"] -= dt
            if pl["bomb_cd"] <= 0:
                pl["bomb_cd"] = 0.9
                # bombayı uçağın altına değil, oyuncunun GİTTİĞİ YERE at
                lead = 0.9
                bx = max(50, min(WORLD-50, tax + player_vx * lead + random.uniform(-30, 30)))
                by = max(50, min(WORLD-50, tay + player_vy * lead + random.uniform(-30, 30)))
                drop_bomb(bx, by)
        # haritadan çok uzaklaşan / ölen uçaklar
        for pl in [p for p in planes if p["hp"] <= 0]:
            explode(pl["x"], pl["y"], 90)
            kills += 1; wanted = min(5, max(wave // 2, kills // 3))
            msg, msg_t = "Uçak düşürdün! +1 kill", 2
        planes = [p for p in planes if p["hp"] > 0
                  and abs(p["x"]-tax) < 1400 and abs(p["y"]-tay) < 1100]
        # --- bombalar ---
        for bm in bombs:
            bm["timer"] -= dt
        for bm in [b for b in bombs if b["timer"] <= 0]:
            explode(bm["x"], bm["y"], 85)
            d = math.hypot(tax - bm["x"], tay - bm["y"])
            if d < 85:
                if player["in_car"]:
                    # bomba arabayı haşatlar
                    damage_car(player["in_car"], 85 if d < 45 else 45, "bomba yedin")
                else:
                    player["hp"] -= 65 if d < 40 else 30
                    msg, msg_t = "💣 Bomba yedin!", 1.2
        bombs = [b for b in bombs if b["timer"] > 0]

        # --- NÜKLEER HELİKOPTER ---
        heli_timer -= dt
        if heli_timer <= 0:
            if wave >= 2 and not helis and not nukes:
                where = spawn_heli()
                heli_timer = random.uniform(55, 80)
                msg, msg_t = f"🚁 NÜKLEER HELİKOPTER {where} GELİYOR! Vur onu!", 4
            else:
                heli_timer = 5  # uygun değilse biraz sonra tekrar dene
        for hl in helis:
            hl["rot"] += dt * 40
            if not hl["dropped"]:
                hl["angle"] = math.atan2(hl["ty"] - hl["y"], hl["tx"] - hl["x"])
            hl["x"] += math.cos(hl["angle"]) * hl["speed"] * dt
            hl["y"] += math.sin(hl["angle"]) * hl["speed"] * dt
            if not hl["dropped"] and math.hypot(hl["tx"] - hl["x"], hl["ty"] - hl["y"]) < 25:
                hl["dropped"] = True
                nukes.append({"x": hl["tx"], "y": hl["ty"], "timer": NUKE_FUSE, "max": NUKE_FUSE})
                msg, msg_t = f"☢ NÜKLEER BOMBA BIRAKILDI! {int(NUKE_FUSE)} sn! Kırmızı halkadan ÇIK!", 4
        for hl in [h for h in helis if h["hp"] <= 0]:
            explode(hl["x"], hl["y"], 110)
            kills += 1; wanted = min(5, max(wave // 2, kills // 3))
            if hl["dropped"]:
                msg, msg_t = "Helikopteri düşürdün ama bomba zaten düştü! KAÇ!", 3
            else:
                msg, msg_t = "🚁 Helikopteri düşürdün! Nükleer bomba İPTAL! +1 kill", 3
        helis = [h for h in helis if h["hp"] > 0
                 and -400 < h["x"] < WORLD + 400 and -400 < h["y"] < WORLD + 400]

        # --- NÜKLEER BOMBA: geri sayım + patlama ---
        for nk in nukes:
            nk["timer"] -= dt
        for nk in [n for n in nukes if n["timer"] <= 0]:
            nxp, nyp = nk["x"], nk["y"]
            nuke_flash = 3.0
            nuke_shake = 3.0
            nuke_fx.append({"x": nxp, "y": nyp, "t": 0.0})
            nuke_zones.append({"x": nxp, "y": nyp, "life": 45.0})
            explode(nxp, nyp, NUKE_R)
            for _ in range(500):
                ang = random.random() * math.pi * 2
                sp = random.uniform(80, 1100)
                particles.append({"x": nxp, "y": nyp, "vx": math.cos(ang)*sp, "vy": math.sin(ang)*sp,
                                  "life": random.uniform(0.8, 2.4),
                                  "color": random.choice([(255, 255, 255), (255, 230, 0), (255, 120, 0), (90, 90, 90)])})
            # oyuncu
            dpl = math.hypot(tax - nxp, tay - nyp)
            if dpl < NUKE_R:
                if player["in_car"]:
                    damage_car(player["in_car"], 99999, "NÜKLEER")
                if dpl < NUKE_R * NUKE_LETHAL:
                    player["hp"] = 0
                    msg, msg_t = "☢ NÜKLEER PATLAMA! Yok oldun!", 3
                elif not player["in_car"]:
                    player["hp"] -= 90
                    msg, msg_t = "☢ Nükleer şok dalgası! -90", 3
            # düşmanlar, uçaklar, helikopterler
            for en in enemies:
                if math.hypot(en["x"] - nxp, en["y"] - nyp) < NUKE_R:
                    if en["type"] == "boss":
                        en["hp"] -= en["maxhp"] * 0.4  # boss tek atmada ölmez
                    else:
                        en["hp"] = 0
            for pl in planes:
                if math.hypot(pl["x"] - nxp, pl["y"] - nyp) < NUKE_R:
                    pl["hp"] = 0
            for hl in helis:
                if math.hypot(hl["x"] - nxp, hl["y"] - nyp) < NUKE_R:
                    hl["hp"] = 0
            # arabalar (oyuncunun arabası yukarıda halledildi)
            for c in cars:
                if c is not player.get("in_car") and not c.get("wreck") \
                        and math.hypot(c["x"] - nxp, c["y"] - nyp) < NUKE_R:
                    damage_car(c, 99999, "NÜKLEER")
            # ağaç, direk, pickup, mermi yok olur
            obstacles[:] = [o for o in obstacles if math.hypot(o["x"] - nxp, o["y"] - nyp) > NUKE_R]
            pickups[:] = [p for p in pickups if math.hypot(p["x"] - nxp, p["y"] - nyp) > NUKE_R]
            bullets[:] = [b for b in bullets if math.hypot(b["x"] - nxp, b["y"] - nyp) > NUKE_R]
            shades[:] = [x for x in shades if math.hypot(x["x"] - nxp, x["y"] - nyp) > NUKE_R]
        nukes = [n for n in nukes if n["timer"] > 0]

        # --- RADYASYON BÖLGESİ: patlamadan sonra 45 sn boyunca zarar verir ---
        for nz in nuke_zones:
            nz["life"] -= dt
            zr = NUKE_R * 0.6
            if math.hypot(tax - nz["x"], tay - nz["y"]) < zr:
                player["hp"] -= 12 * dt
                if random.random() < 0.02:
                    msg, msg_t = "☢ RADYASYON! Bölgeden çık!", 1.0
            for en in enemies:
                if math.hypot(en["x"] - nz["x"], en["y"] - nz["y"]) < zr:
                    en["hp"] -= 25 * dt
        nuke_zones = [z for z in nuke_zones if z["life"] > 0]
        # ekran sarsıntısı
        if nuke_shake > 0:
            nuke_shake -= dt
            amp = min(1.0, nuke_shake) * 20
            shake_x, shake_y = random.uniform(-amp, amp), random.uniform(-amp, amp)
        else:
            shake_x, shake_y = 0, 0

        # --- KARA GÖLGELER: 7. dalgadan itibaren; barışçıl ama SALDIRMA! ---
        shade_timer -= dt
        if wave >= 7 and shade_timer <= 0 and len(shades) < min(4, 1 + (wave - 7) // 2):
            spawn_shade()
            shade_timer = 9.0
            msg, msg_t = "☠ KARA GÖLGELER belirdi! Yarı saydam siyahlara SALDIRMA!", 3.5
        for sh in shades:
            sh["age"] += dt
            sh["flash"] = max(0.0, sh["flash"] - dt)
            sh["ram_cd"] = max(0.0, sh["ram_cd"] - dt)
            sh["turn"] -= dt
            if sh["turn"] <= 0:
                sh["dir"] = random.random() * math.pi * 2
                sh["turn"] = random.uniform(2, 4)
            dsp = math.hypot(tax - sh["x"], tay - sh["y"])
            if dsp < 170:  # oyuncudan uzaklaşır
                fa = math.atan2(sh["y"] - tay, sh["x"] - tax)
                try_move(sh, sh["x"] + math.cos(fa) * 1.5, sh["y"] + math.sin(fa) * 1.5)
            else:
                try_move(sh, sh["x"] + math.cos(sh["dir"]) * 0.9, sh["y"] + math.sin(sh["dir"]) * 0.9)
            sh["x"] = max(40, min(WORLD - 40, sh["x"])); sh["y"] = max(40, min(WORLD - 40, sh["y"]))
            if random.random() < 0.08:
                particles.append({"x": sh["x"] + random.uniform(-10, 10), "y": sh["y"] + 10, "vx": 0, "vy": -30,
                                  "life": 0.6, "color": (40, 40, 50)})
        for sh in [x for x in shades if x["hp"] <= 0]:
            # gölgeyi öldürürsen patlama yok: lanet seni vurur (-30) + kill cezası
            for _ in range(14):
                particles.append({"x": sh["x"] + random.uniform(-12, 12), "y": sh["y"] + random.uniform(-12, 12),
                                  "vx": random.uniform(-40, 40), "vy": random.uniform(-80, -20),
                                  "life": random.uniform(0.4, 0.9), "color": random.choice([(20, 20, 25), (60, 60, 70), (110, 110, 130)])})
            if player["in_car"]:
                damage_car(player["in_car"], 30, "gölge laneti")
            else:
                player["hp"] -= 30
            kills = max(0, kills - 2)
            msg, msg_t = "☠ GÖLGE ÖLDÜ! Lanet seni vurdu: -30 (ve -2 kill)", 3
        shades = [x for x in shades if x["hp"] > 0 and x["age"] < x["life"]]
        # --- DALGA YÖNETİMİ ---
        if wave_banner_t > 0:
            wave_banner_t -= dt
        if wave_break_timer > 0:
            wave_break_timer -= dt
            if wave_break_timer <= 0:
                wave += 1
                wanted = min(5, wave // 2)
                wave_queue = make_wave(wave)
                wave_total = len(wave_queue)
                wave_banner_t = 3
                # HER 5 DALGADA SAVE
                if wave % 5 == 0:
                    do_save()
                    msg, msg_t = f"DALGA {wave} + 💾 SAVE ALINDI!", 3
                else:
                    msg, msg_t = f"DALGA {wave} başlıyor! ({wave_total} düşman)", 3
                # dalga ödülü
                player["ammo"] += 40
                player["hp"] = min(100, player["hp"] + 25)
                spawn_pickup(tax + random.uniform(-150, 150), tay + random.uniform(-150, 150))
        else:
            # sıradaki düşmanı sahaya sür (0.7 sn arayla, aynı anda max 10)
            wave_spawn_timer -= dt
            if wave_queue and wave_spawn_timer <= 0 and len(enemies) < 10:
                wave_spawn_timer = 0.7
                typ = wave_queue.pop(0)
                spawn_enemy(typ, ignore_cap=True)
            # dalga bitti mi? (kuyruk boş + sahada düşman yok)
            if not wave_queue and len(enemies) == 0:
                msg, msg_t = f"DALGA {wave} TEMİZLENDİ! +ödül", 3
                if shades and not shade_attacked:
                    player["hp"] = min(100, player["hp"] + 30); player["ammo"] += 40
                    msg, msg_t = f"DALGA {wave} TEMİZLENDİ! Gölgelere dokunmadın: +30 can +40 mermi", 3.5
                shade_attacked = False
                wave_break_timer = 5  # 5 sn mola
                kills += 2  # bonus
                for c in cars:
                    if c.get("wreck"):
                        c.update(hp=c["maxhp"], wreck=False, speed=0,
                                 x=tax+random.uniform(-300, 300), y=tay+random.uniform(-300, 300))
                    else:
                        c["hp"] = min(c["maxhp"], c["hp"]+50)
                player["ammo"] += 30
                spawn_pickup(tax + 100, tay)
                spawn_pickup(tax - 100, tay)
        for en in enemies:
            unstick(en)
            d = math.hypot(tax-en["x"], tay-en["y"])
            a = math.atan2(tay-en["y"], tax-en["x"])
            t = en["type"]

            if t == "healer":
                # en yaralı dosta git, alan heal bas
                target = None; best = 1e9
                for o in enemies:
                    if o is not en and o["hp"] < o["maxhp"]:
                        dd = math.hypot(o["x"]-en["x"], o["y"]-en["y"])
                        if dd < best: best, target = dd, o
                if target and best > 90:
                    ta = math.atan2(target["y"]-en["y"], target["x"]-en["x"])
                    _nx = en["x"]+math.cos(ta)*en["speed"]; _ny = en["y"]+math.sin(ta)*en["speed"]
                    try_move(en, _nx, _ny)
                elif d < 250:  # oyuncudan biraz kaç
                    try_move(en, en["x"]-math.cos(a)*en["speed"]*0.7, en["y"]-math.sin(a)*en["speed"]*0.7)
                elif target is None and d > 220:
                    try_move(en, en["x"]+math.cos(a)*en["speed"]*0.6, en["y"]+math.sin(a)*en["speed"]*0.6)
                # heal aura
                en["heal_cd"] -= dt
                if en["heal_cd"] <= 0:
                    en["heal_cd"] = 0.6
                    healed = False
                    for o in enemies:
                        if o is not en and math.hypot(o["x"]-en["x"], o["y"]-en["y"]) < 160:
                            if o["hp"] < o["maxhp"]:
                                o["hp"] = min(o["maxhp"], o["hp"] + 9)
                                healed = True
                                particles.append({"x": o["x"]+random.uniform(-10, 10),
                                                  "y": o["y"]-14, "vx": 0, "vy": -40,
                                                  "life": 0.5, "color": (0, 255, 120)})
                    if healed:
                        particles.append({"x": en["x"], "y": en["y"], "vx": 0, "vy": -20,
                                          "life": 0.4, "color": (0, 255, 120)})

            elif t == "rocket":
                # mesafeyi koru, roket at
                if d > 420:
                    _nx = en["x"]+math.cos(a)*en["speed"]; _ny = en["y"]+math.sin(a)*en["speed"]
                    try_move(en, _nx, _ny)
                elif d < 220:
                    _nx = en["x"]-math.cos(a)*en["speed"]; _ny = en["y"]-math.sin(a)*en["speed"]
                    try_move(en, _nx, _ny)
                en["cd"] -= dt
                if en["cd"] <= 0 and d < 600:
                    en["cd"] = 2.4 + random.random()*1.2  # roket yavaş atar
                    spd = 5.2
                    bullets.append({"x": en["x"], "y": en["y"],
                                    "vx": math.cos(a)*spd, "vy": math.sin(a)*spd,
                                    "life": 130, "dmg": 40, "foe": True, "rocket": True})
            elif t == "sword":
                # BUFF'lı kılıçlı manyak: hançer fırlatır + hızlı, çift dash
                en["st"] -= dt
                if en["state"] == "walk":
                    if d > 70:
                        _nx = en["x"]+math.cos(a)*en["speed"]; _ny = en["y"]+math.sin(a)*en["speed"]
                        try_move(en, _nx, _ny)
                    en["cd"] -= dt
                    en["tcd"] -= dt
                    # orta mesafede 3'lü hançer yelpazesi fırlat
                    if en["tcd"] <= 0 and 170 < d < 580:
                        en["tcd"] = 2.6 + random.random()*1.3
                        for off in (-0.16, 0.0, 0.16):
                            aa = a + off + random.uniform(-0.03, 0.03)
                            bullets.append({"x": en["x"], "y": en["y"], "vx": math.cos(aa)*9.5,
                                            "vy": math.sin(aa)*9.5, "life": 75, "dmg": 16,
                                            "foe": True, "rocket": False, "dagger": True})
                        particles.append({"x": en["x"], "y": en["y"], "vx": 0, "vy": -20,
                                          "life": 0.2, "color": (220, 220, 255)})
                    if en["cd"] <= 0 and d < 460:
                        en["state"] = "windup"; en["st"] = 0.55; en["dir"] = a; en["combo"] = 0
                elif en["state"] == "windup":
                    # son 0.22 sn'de yön kilitlenir -> yana kaçmak için zaman var
                    if en["st"] > 0.22:
                        en["dir"] = a
                    if en["st"] <= 0:
                        en["state"] = "dash"; en["st"] = 0.42; en["hit"] = False
                elif en["state"] == "dash":
                    _nx = en["x"]+math.cos(en["dir"])*1200*dt; _ny = en["y"]+math.sin(en["dir"])*1200*dt
                    if try_move(en, _nx, _ny):
                        if random.random() < 0.9:
                            particles.append({"x": en["x"], "y": en["y"], "vx": 0, "vy": 0,
                                              "life": 0.25, "color": (200, 150, 255)})
                    else:
                        en["state"] = "rest"; en["st"] = 0.7
                    dd = math.hypot(tax-en["x"], tay-en["y"])
                    if not en["hit"] and dd < (50 if player["in_car"] else 36):
                        en["hit"] = True
                        if player["in_car"]:
                            damage_car(player["in_car"], 50, "kılıçlı manyak")
                        else:
                            player["hp"] -= 45
                            msg, msg_t = "🗡 Kılıç yedin! -45", 1.2
                        particles.append({"x": tax, "y": tay, "vx": 0, "vy": -30,
                                          "life": 0.3, "color": (255, 255, 255)})
                    if en["st"] <= 0 and en["state"] == "dash":
                        # %45 ihtimalle hemen ikinci bir dash (kısa işaretle)
                        if en["combo"] == 0 and random.random() < 0.30:
                            en["combo"] = 1; en["state"] = "windup"; en["st"] = 0.4; en["dir"] = a
                        else:
                            en["state"] = "rest"; en["st"] = 0.7
                else:  # rest: nefes alır, bu sırada vurulabilir
                    if en["st"] <= 0:
                        en["state"] = "walk"; en["cd"] = 1.4 + random.random()*1.2
                if not player["in_car"] and d < 22:
                    player["hp"] -= 25*dt
            elif t == "freezer":
                # dondurucu: mesafeyi korur, yavaş buz mermisi atar (isabet = donma)
                if d > 380:
                    try_move(en, en["x"]+math.cos(a)*en["speed"], en["y"]+math.sin(a)*en["speed"])
                elif d < 220:
                    try_move(en, en["x"]-math.cos(a)*en["speed"]*0.8, en["y"]-math.sin(a)*en["speed"]*0.8)
                en["cd"] -= dt
                if en["cd"] <= 0 and d < 560:
                    en["cd"] = 2.4 + random.random()*1.0
                    bullets.append({"x": en["x"], "y": en["y"], "vx": math.cos(a)*5.5, "vy": math.sin(a)*5.5,
                                    "life": 100, "dmg": 10, "foe": True, "rocket": False,
                                    "ice": True, "freeze": 1.4})
                if not player["in_car"] and d < 22:
                    player["hp"] -= 25*dt
            elif t == "boss":
                # DONDURAN BOSS: buz yelpazesi + telgraflı buz patlaması (nova) + %66/%33'te dondurucu çağırır
                if d > 460:
                    try_move(en, en["x"]+math.cos(a)*en["speed"], en["y"]+math.sin(a)*en["speed"], 24)
                elif d < 280:
                    try_move(en, en["x"]-math.cos(a)*en["speed"]*0.8, en["y"]-math.sin(a)*en["speed"]*0.8, 24)
                en["cd"] -= dt
                if en["cd"] <= 0 and d < 680 and en["nova_t"] <= 0:
                    en["cd"] = 2.3
                    for off in (-0.3, -0.15, 0.0, 0.15, 0.3):
                        aa = a + off
                        bullets.append({"x": en["x"], "y": en["y"], "vx": math.cos(aa)*6.5, "vy": math.sin(aa)*6.5,
                                        "life": 110, "dmg": 12, "foe": True, "rocket": False,
                                        "ice": True, "freeze": 1.2})
                en["nova_cd"] -= dt
                if en["nova_t"] > 0:
                    en["nova_t"] -= dt
                    if en["nova_t"] <= 0:
                        # buz patlaması: 280 px içindeyse donarsın
                        for _ in range(70):
                            ang = random.random() * math.pi * 2
                            sp = random.uniform(200, 520)
                            particles.append({"x": en["x"], "y": en["y"], "vx": math.cos(ang)*sp, "vy": math.sin(ang)*sp,
                                              "life": random.uniform(0.3, 0.7), "color": random.choice([(170, 225, 255), (255, 255, 255), (90, 170, 255)])})
                        if d < 280:
                            freeze_player(2.5)
                            if player["in_car"]:
                                damage_car(player["in_car"], 40, "buz patlaması")
                            else:
                                player["hp"] -= 25
                elif en["nova_cd"] <= 0 and d < 460:
                    en["nova_t"] = 1.1
                    en["nova_cd"] = 6.5
                    msg, msg_t = "❄ BUZ PATLAMASI geliyor! Mavi halkadan uzaklaş!", 1.5
                # kalan cana göre yardım çağır
                ratio_ = en["hp"] / en["maxhp"]
                phases = (1 if ratio_ < 0.66 else 0) + (1 if ratio_ < 0.33 else 0)
                if phases > en["summoned"]:
                    en["summoned"] = phases
                    for _ in range(2):
                        spawn_enemy("freezer", ignore_cap=True)
                    msg, msg_t = "❄ Boss dondurucuları çağırdı!", 2
                if not player["in_car"] and d < 45:
                    player["hp"] -= 30*dt
            elif t == "cop":
                # MAVİLER TARAMALI: tam otomatik, seri atış
                if d > 260:
                    _nx = en["x"]+math.cos(a)*en["speed"]; _ny = en["y"]+math.sin(a)*en["speed"]
                    try_move(en, _nx, _ny)
                elif d < 140:
                    _nx = en["x"]-math.cos(a)*en["speed"]*0.6; _ny = en["y"]-math.sin(a)*en["speed"]*0.6
                    try_move(en, _nx, _ny)
                else:
                    # yan strafing (sağa sola kay)
                    strafe = 1 if (pygame.time.get_ticks()//500 + int(en["x"])) % 2 == 0 else -1
                    try_move(en, en["x"]-math.sin(a)*en["speed"]*0.5*strafe, en["y"]+math.cos(a)*en["speed"]*0.5*strafe)
                en["cd"] -= dt
                if en["cd"] <= 0 and d < 520:
                    en["cd"] = 0.22  # taramalı hız
                    spread = random.uniform(-0.12, 0.12)
                    aa = a + spread
                    spd = 8.5
                    bullets.append({"x": en["x"], "y": en["y"], "vx": math.cos(aa)*spd,
                                    "vy": math.sin(aa)*spd, "life": 45, "dmg": 8,
                                    "foe": True, "rocket": False})
                    particles.append({"x": en["x"], "y": en["y"], "vx": 0, "vy": 0,
                                      "life": 0.08, "color": (150, 200, 255)})
                if not player["in_car"] and d < 22:
                    player["hp"] -= 25*dt
            else:
                # normal
                if d > 180:
                    _nx = en["x"]+math.cos(a)*en["speed"]; _ny = en["y"]+math.sin(a)*en["speed"]
                    try_move(en, _nx, _ny)
                else:
                    en["cd"] -= dt
                    if en["cd"] <= 0:
                        en["cd"] = 1.2 + random.random()
                        bullets.append({"x": en["x"], "y": en["y"], "vx": math.cos(a)*7,
                                        "vy": math.sin(a)*7, "life": 60, "dmg": 12,
                                        "foe": True, "rocket": False})
                if not player["in_car"] and d < 22:
                    player["hp"] -= 25*dt

        for en in [x for x in enemies if x["hp"] <= 0]:
            kills += 1; wanted = min(5, max(wave // 2, kills // 3))
            explode(en["x"], en["y"], 40)
            if en["type"] == "boss":
                explode(en["x"], en["y"], 150)
                kills += 4
                for _k in range(4):
                    spawn_pickup(en["x"] + random.uniform(-80, 80), en["y"] + random.uniform(-80, 80))
                player["hp"] = min(100, player["hp"] + 40); player["ammo"] += 60
                msg, msg_t = "❄ DONDURAN BOSS ÖLDÜ! +5 kill, +40 can, +60 mermi", 4
            if random.random() < 0.4: spawn_pickup(en["x"], en["y"])
        enemies = [x for x in enemies if x["hp"] > 0]

        for p in pickups:
            if math.hypot(p["x"]-tax, p["y"]-tay) < 30:
                p["taken"] = True
                if p["type"] == "ammo": player["ammo"] += 60; msg, msg_t = "+60 mermi", 1.5
                else:
                    if player["in_car"]:
                        c = player["in_car"]
                        c["hp"] = min(c["maxhp"], c["hp"]+60)
                        msg, msg_t = "+60 araba tamiri 🔧", 1.5
                    else:
                        player["hp"] = min(100, player["hp"]+40); msg, msg_t = "+40 can", 1.5
        pickups = [p for p in pickups if not p.get("taken")]
        if len(pickups) < 5 and random.random() < 0.01: spawn_pickup()

        # partikül + patlama güncelle
        for p in particles:
            p["x"] += p["vx"]*dt; p["y"] += p["vy"]*dt; p["life"] -= dt
        particles = [p for p in particles if p["life"] > 0]
        for ex in explosions:
            ex["r"] += (ex["max"]-ex["r"])*8*dt; ex["life"] -= dt
        explosions = [x for x in explosions if x["life"] > 0]

        if god:
            player["hp"] = player["maxhp"]
            freeze_t = 0.0
            player["ammo"] = max(player["ammo"], 999)
            if player["in_car"]:
                player["in_car"]["hp"] = player["in_car"]["maxhp"]

        if player["hp"] <= 0:
            s = load_save()
            enemies.clear(); bullets.clear(); planes.clear(); bombs.clear()
            freeze_t = 0; freeze_immune = 0; shades.clear(); helis.clear(); nukes.clear(); nuke_zones.clear(); heli_timer = 45  # flaş/şok dalgası ölümde de oynasın
            plane_timer = 6
            if s and s.get("wave", 1) >= 5:
                wave = s["wave"]; kills = s["kills"]; wanted = s["wanted"]
                player.update(hp=100, x=1200, y=1200, in_car=None,
                              ammo=s.get("ammo", 120), weapon=s.get("weapon", 0))
                wave_queue = make_wave(wave); wave_total = len(wave_queue)
                wave_break_timer = 0; wave_spawn_timer = 0; wave_banner_t = 3
                msg, msg_t = f"Öldün! 💾 Save'den devam: DALGA {wave}", 3
            else:
                player.update(hp=100, x=1200, y=1200, in_car=None)
                kills, wanted = 0, 0
                wave = 1; wave_break_timer = 0; wave_spawn_timer = 0
                wave_queue = make_wave(1); wave_total = len(wave_queue)
                wave_banner_t = 3
                msg, msg_t = "Öldün! DALGA 1'e döndün (5. dalgada save alınır)", 2

    # --- çizim ---
    screen.fill((58, 74, 58))
    for i in range(200, WORLD, 400):
        pygame.draw.rect(screen, (61, 61, 63), (px(i-60), py(0), 120, WORLD))
        pygame.draw.rect(screen, (61, 61, 63), (px(0), py(i-60), WORLD, 120))
    for bx in range(6):
        for by in range(6):
            x, y = 80+bx*400, 80+by*400
            pygame.draw.rect(screen, (90, 98, 112), (px(x), py(y), 200, 200))
            pygame.draw.rect(screen, (67, 73, 86), (px(x+15), py(y+15), 170, 170))

    # bombalar: kırmızı uyarı halkası (kaçman için)
    for bm in bombs:
        bx, by = px(bm["x"]), py(bm["y"])
        ratio = 1 - bm["timer"] / bm["max"]
        # dış halka: patlama alanı
        pygame.draw.circle(screen, (255, 0, 0), (bx, by), 85, 2)
        # iç dolan halka: zaman daralıyor
        blink = (math.sin(pygame.time.get_ticks() * 0.02) + 1) / 2
        col = (255, int(100 + blink*100), 0)
        pygame.draw.circle(screen, col, (bx, by), int(10 + ratio * 75), 2)
        pygame.draw.circle(screen, (255, 0, 0), (bx, by), 8)
        screen.blit(small.render("!", True, (255, 0, 0)), (bx-3, by-22))

    # radyasyon bölgesi (yeşil, titreşen)
    tnow = pygame.time.get_ticks()
    if nuke_zones:
        zo = pygame.Surface((W, H), pygame.SRCALPHA)
        for nz in nuke_zones:
            fadez = min(1.0, nz["life"] / 3.0)
            pz = 0.5 + 0.5 * math.sin(tnow * 0.005)
            pygame.draw.circle(zo, (80, 255, 60, int((30 + 25 * pz) * fadez)), (px(nz["x"]), py(nz["y"])), int(NUKE_R * 0.6))
            pygame.draw.circle(zo, (140, 255, 80, int(200 * fadez)), (px(nz["x"]), py(nz["y"])), int(NUKE_R * 0.6), 3)
        screen.blit(zo, (0, 0))

    # nükleer hedef işareti (helikopter henüz bırakmadıysa) + aktif nükleer bomba uyarısı
    for hl in helis:
        if not hl["dropped"]:
            pulse = 0.5 + 0.5 * math.sin(tnow * 0.006)
            pygame.draw.circle(screen, (255, int(180 + 60 * pulse), 0), (px(hl["tx"]), py(hl["ty"])), NUKE_R, 2)
            screen.blit(small.render("NÜKLEER HEDEF", True, (255, 220, 0)), (px(hl["tx"]) - 45, py(hl["ty"]) - 8))
    if nukes:
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        for nk in nukes:
            cx_, cy_ = px(nk["x"]), py(nk["y"])
            ratio = 1 - nk["timer"] / nk["max"]
            blink = 0.5 + 0.5 * math.sin(tnow * (0.01 + ratio * 0.03))
            pygame.draw.circle(ov, (255, 0, 0, int(35 + 45 * blink)), (cx_, cy_), NUKE_R)
            pygame.draw.circle(ov, (255, 0, 0, int(55 + 60 * blink)), (cx_, cy_), int(NUKE_R * NUKE_LETHAL))
            pygame.draw.circle(ov, (255, 220, 0, 255), (cx_, cy_), NUKE_R, 4)
            pygame.draw.circle(ov, (255, 0, 0, 255), (cx_, cy_), int(NUKE_R * NUKE_LETHAL), 4)
            pygame.draw.circle(ov, (255, 255, 255, 255), (cx_, cy_), int(10 + ratio * NUKE_R * NUKE_LETHAL), 2)
        screen.blit(ov, (0, 0))
        for nk in nukes:
            screen.blit(big.render(f"NUKE {nk['timer']:.1f}", True, (255, 255, 255)),
                        (px(nk["x"]) - 45, py(nk["y"]) - 12))

    # direkler + ağaçlar
    # lamba ışıkları: direklerin altına yumuşak ışık havuzu (additive glow)
    glow = pygame.Surface((W, H), pygame.SRCALPHA)
    for o in obstacles:
        if o["kind"] != "pole":
            continue
        sx, sy = px(o["x"]), py(o["y"])
        if -150 < sx < W+150 and -150 < sy < H+150:
            flick = 0.9 + 0.1 * math.sin(pygame.time.get_ticks() * 0.003 + o.get("phase", 0))
            for r, a in [(110, 18), (80, 28), (50, 45), (28, 70)]:
                pygame.draw.circle(glow, (255, 220, 130, int(a * flick)), (sx, sy), r)
    screen.blit(glow, (0, 0))
    for o in obstacles:
        sx, sy = px(o["x"]), py(o["y"])
        if -50 < sx < W+50 and -50 < sy < H+50:
            if o["kind"] == "tree":
                pygame.draw.circle(screen, (20, 90, 40), (sx+2, sy+3), o["r"]+2)  # gölge
                pygame.draw.circle(screen, (25, 130, 55), (sx, sy), o["r"])
                pygame.draw.circle(screen, (35, 170, 70), (sx-3, sy-3), o["r"]-6)
                pygame.draw.circle(screen, (110, 70, 30), (sx, sy), 4)  # gövde
            else:
                # direk gövdesi + ışık saçan lamba kafası
                pygame.draw.circle(screen, (0, 0, 0), (sx+2, sy+2), 7)
                pygame.draw.circle(screen, (70, 70, 80), (sx, sy), 6)  # direk
                lamp = 230 + int(25 * math.sin(pygame.time.get_ticks() * 0.003 + o.get("phase", 0)))
                pygame.draw.circle(screen, (lamp, lamp, 180), (sx, sy), 4)  # ampul
                pygame.draw.circle(screen, (255, 240, 180), (sx, sy), 9, 2)  # halka

    for p in pickups:
        c = (255, 204, 0) if p["type"] == "ammo" else (48, 209, 88)
        pygame.draw.circle(screen, c, (px(p["x"]), py(p["y"])), 10)
        screen.blit(small.render("M" if p["type"] == "ammo" else "+", True, (0, 0, 0)), (px(p["x"])-5, py(p["y"])-9))

    for c in cars:
        col = (30, 30, 30) if c.get("wreck") else c["color"]
        surf = pygame.Surface((c["w"], c["h"]), pygame.SRCALPHA)
        surf.fill(col)
        if not c.get("wreck"):
            pygame.draw.rect(surf, (255, 255, 255), (c["w"]-14, 4, 10, c["h"]-8))
        else:
            pygame.draw.line(surf, (255, 100, 0), (0, 0), (c["w"], c["h"]), 3)
        rs = pygame.transform.rotate(surf, -math.degrees(c["angle"]))
        screen.blit(rs, rs.get_rect(center=(px(c["x"]), py(c["y"]))))
        # araba can barı
        if not c.get("wreck"):
            draw_health_bar(px(c["x"]), py(c["y"])-30, 48, c["hp"]/c["maxhp"])
        else:
            screen.blit(small.render("💥 HURDA", True, (255, 100, 0)), (px(c["x"])-28, py(c["y"])-42))
        # duman: canı azalan araba duman çıkarır
        if not c.get("wreck") and c["hp"] < c["maxhp"]*0.35 and random.random() < 0.2:
            particles.append({"x": c["x"]+random.uniform(-10, 10), "y": c["y"]+random.uniform(-8, 8),
                              "vx": 0, "vy": -50, "life": 0.5, "color": (120, 120, 120)})

    if not player["in_car"]:
        best, bd = None, 90
        for c in cars:
            if c.get("wreck"):
                continue
            d = math.hypot(c["x"]-player["x"], c["y"]-player["y"])
            if d < bd: bd, best = d, c
        if best:
            pygame.draw.circle(screen, (255, 204, 0), (px(best["x"]), py(best["y"])), 42, 3)
            screen.blit(small.render("E: bin", True, (255, 204, 0)), (px(best["x"])-18, py(best["y"])-52))

    # uçaklar (gölge + gövde + can barı)
    for pl in planes:
        sx, sy = px(pl["x"]), py(pl["y"])
        # gölge (hafif kayık)
        pygame.draw.ellipse(screen, (0, 0, 0), (sx-24, sy-8, 48, 16))
        # gövde: uçağın yönüne dönmüş üçgen
        ang = pl["angle"]
        pts = []
        for dx, dy in [(26, 0), (-14, 16), (-6, 0), (-14, -16)]:
            rx = dx*math.cos(ang) - dy*math.sin(ang)
            ry = dx*math.sin(ang) + dy*math.cos(ang)
            pts.append((sx+rx, sy+ry))
        pygame.draw.polygon(screen, (200, 200, 210), pts)
        pygame.draw.polygon(screen, (40, 40, 40), pts, 2)
        pygame.draw.circle(screen, (255, 0, 0), (sx, sy), 4)
        draw_health_bar(sx, sy-28, 36, pl["hp"]/pl["maxhp"])
        screen.blit(small.render("✈", True, (255, 255, 255)), (sx-8, sy-12))

    # nükleer helikopterler (gölge + gövde + dönen pervane + can barı)
    for hl in helis:
        sx, sy = px(hl["x"]), py(hl["y"])
        if not (-100 < sx < W + 100 and -100 < sy < H + 100):
            continue
        ang = hl["angle"]
        ca, sa = math.cos(ang), math.sin(ang)
        def rot(dx, dy):
            return (sx + dx * ca - dy * sa, sy + dx * sa + dy * ca)
        pygame.draw.ellipse(screen, (0, 0, 0), (sx - 26 + 10, sy - 10 + 14, 52, 20))  # gölge
        pygame.draw.line(screen, (60, 70, 60), rot(-8, 0), rot(-46, 0), 5)             # kuyruk
        pygame.draw.line(screen, (60, 70, 60), rot(-46, -8), rot(-46, 8), 3)           # kuyruk rotoru
        pygame.draw.ellipse(screen, (70, 90, 70), (sx - 22, sy - 14, 44, 28))           # gövde (yönsüz)
        pygame.draw.circle(screen, (110, 190, 220), rot(14, 0), 8)                      # kokpit
        pygame.draw.circle(screen, (255, 220, 0), rot(-2, 0), 6)                        # nükleer işareti
        pygame.draw.circle(screen, (0, 0, 0), rot(-2, 0), 6, 2)
        for k in range(2):  # dönen ana pervane
            ra = hl["rot"] + k * math.pi / 2
            pygame.draw.line(screen, (200, 200, 200), (sx + math.cos(ra) * 40, sy + math.sin(ra) * 40),
                             (sx - math.cos(ra) * 40, sy - math.sin(ra) * 40), 3)
        pygame.draw.circle(screen, (30, 30, 30), (sx, sy), 4)
        draw_health_bar(sx, sy - 40, 50, hl["hp"] / hl["maxhp"])
        screen.blit(small.render("NUKE HELİ" if not hl["dropped"] else "BOŞ HELİ", True, (255, 220, 0)), (sx - 30, sy - 58))

    # düşmanlar
    for en in enemies:
        sx, sy = px(en["x"]), py(en["y"])
        t = en["type"]
        if t == "healer":
            # yeşil birim + beyaz haç
            pygame.draw.circle(screen, (0, 200, 80), (sx, sy), 13)
            pygame.draw.rect(screen, (255, 255, 255), (sx-2, sy-7, 4, 14))
            pygame.draw.rect(screen, (255, 255, 255), (sx-7, sy-2, 14, 4))
            # heal alanı
            pygame.draw.circle(screen, (0, 255, 120), (sx, sy), 30, 1)
        elif t == "rocket":
            # kasklı kırmızı birim
            pygame.draw.circle(screen, (200, 20, 20), (sx, sy), 13)
            pygame.draw.arc(screen, (80, 80, 80), (sx-12, sy-14, 24, 16), 0, math.pi, 5)  # kask
            pygame.draw.rect(screen, (60, 60, 60), (sx-12, sy-10, 24, 4))  # kask bandı
            screen.blit(small.render("R", True, (255, 255, 255)), (sx-5, sy-7))
        elif t == "freezer":
            pygame.draw.circle(screen, (120, 200, 255), (sx, sy), 13)
            pygame.draw.circle(screen, (225, 245, 255), (sx, sy), 13, 2)
            for k in range(3):  # kar tanesi
                ka = k * math.pi / 3
                pygame.draw.line(screen, (255, 255, 255), (sx - math.cos(ka)*9, sy - math.sin(ka)*9),
                                 (sx + math.cos(ka)*9, sy + math.sin(ka)*9), 2)
        elif t == "boss":
            pulse_ = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.006)
            pygame.draw.circle(screen, (60, 120, 190), (sx, sy), 34)
            pygame.draw.circle(screen, (130, 200, 255), (sx, sy), 28)
            pygame.draw.circle(screen, (230, 248, 255), (sx, sy), 34, 3)
            for k in range(6):  # buz dikenleri
                ka = k * math.pi / 3 + pygame.time.get_ticks() * 0.001
                pygame.draw.line(screen, (230, 248, 255), (sx + math.cos(ka)*30, sy + math.sin(ka)*30),
                                 (sx + math.cos(ka)*(44 + 4*pulse_), sy + math.sin(ka)*(44 + 4*pulse_)), 4)
            pygame.draw.circle(screen, (255, 60, 60), (sx - 8, sy - 4), 4)
            pygame.draw.circle(screen, (255, 60, 60), (sx + 8, sy - 4), 4)
            if en["nova_t"] > 0:
                # buz patlaması uyarısı: dış halka sabit, iç halka dolar
                kk = 1 - en["nova_t"] / 1.1
                pygame.draw.circle(screen, (90, 170, 255), (sx, sy), 280, 3)
                pygame.draw.circle(screen, (200, 240, 255), (sx, sy), int(20 + kk * 260), 4)
                nv = pygame.Surface((W, H), pygame.SRCALPHA)
                pygame.draw.circle(nv, (120, 200, 255, int(30 + 50 * kk)), (sx, sy), 280)
                screen.blit(nv, (0, 0))
        elif t == "sword":
            sa_ = en["dir"] if en["state"] in ("windup", "dash") else math.atan2(tay-en["y"], tax-en["x"])
            if en["state"] == "windup":
                # kırmızı işaret çizgisi: dash yönünü gösterir (yanıp söner)
                if (pygame.time.get_ticks() // 70) % 2 == 0:
                    pygame.draw.line(screen, (255, 40, 40), (sx, sy),
                                     (sx + math.cos(sa_)*420, sy + math.sin(sa_)*420), 3)
                screen.blit(small.render("!!", True, (255, 40, 40)), (sx-6, sy-44))
            pygame.draw.circle(screen, (150, 50, 210), (sx, sy), 13)
            pygame.draw.circle(screen, (30, 10, 40), (sx, sy-4), 7)  # kapüşon
            # kılıç: dash'te öne uzanır, yürürken yanda durur
            ln = 40 if en["state"] == "dash" else 30
            ca_ = sa_ if en["state"] != "walk" else sa_ + 0.5
            ex_, ey_ = sx + math.cos(ca_)*ln, sy + math.sin(ca_)*ln
            pygame.draw.line(screen, (220, 225, 235), (sx, sy), (ex_, ey_), 4)
            pygame.draw.line(screen, (120, 80, 30), (sx + math.cos(ca_)*8 - math.sin(ca_)*5, sy + math.sin(ca_)*8 + math.cos(ca_)*5),
                             (sx + math.cos(ca_)*8 + math.sin(ca_)*5, sy + math.sin(ca_)*8 - math.cos(ca_)*5), 3)  # siper
            if en["state"] == "dash":
                pygame.draw.arc(screen, (255, 255, 255), (sx-28, sy-28, 56, 56), -sa_-0.8, -sa_+0.8, 3)  # kesik izi
        elif t == "cop":
            pygame.draw.circle(screen, (10, 132, 255), (sx, sy), 12)
            # taramalı işareti: çift çizgi namlu
            pygame.draw.line(screen, (20, 20, 20), (sx, sy), (sx+16, sy), 4)
            pygame.draw.line(screen, (20, 20, 20), (sx, sy+4), (sx+14, sy+4), 2)
        else:
            pygame.draw.circle(screen, (255, 69, 58), (sx, sy), 12)
        draw_health_bar(sx, sy-(50 if t == "boss" else 26), 70 if t == "boss" else 30, en["hp"]/en["maxhp"])

    # kara gölgeler: yarı saydam siyah hayaletler
    for sh in shades:
        sx, sy = px(sh["x"]), py(sh["y"])
        if not (-60 < sx < W + 60 and -60 < sy < H + 60):
            continue
        fade = max(0.0, min(1.0, sh["age"] / 1.5, (sh["life"] - sh["age"]) / 2.0))
        wob = math.sin(pygame.time.get_ticks() * 0.004 + sh["x"] * 0.01)
        gs = pygame.Surface((70, 84), pygame.SRCALPHA)
        a_ = int((62 + 16 * wob) * fade)
        pygame.draw.circle(gs, (0, 0, 0, a_), (35, 28), 18)
        pygame.draw.rect(gs, (0, 0, 0, a_), (17, 28, 36, 26))
        for k in range(4):  # dalgalı etek
            pygame.draw.circle(gs, (0, 0, 0, a_), (22 + k * 9, 54 + int(3 * math.sin(pygame.time.get_ticks() * 0.008 + k))), 6)
        pygame.draw.circle(gs, (90, 90, 115, int(a_ * 0.8)), (35, 28), 18, 2)
        ecol = (255, 40, 40) if sh["flash"] > 0 else (230, 230, 255)
        ea = int(150 * fade)
        pygame.draw.ellipse(gs, ecol + (ea,), (24, 22, 7, 10))
        pygame.draw.ellipse(gs, ecol + (ea,), (39, 22, 7, 10))
        screen.blit(gs, (sx - 35, sy - 40 + int(3 * wob)))
        lab = small.render("DOKUNMA", True, (150, 150, 165))
        lab.set_alpha(int(150 * fade))
        screen.blit(lab, (sx - 28, sy - 62))
    # oyuncu + KAFAMIZDA CAN BARI
    if not player["in_car"]:
        sx, sy = px(player["x"]), py(player["y"])
        pygame.draw.circle(screen, (74, 222, 128), (sx, sy), 12)
        gx = sx+math.cos(player["angle"])*28
        gy = sy+math.sin(player["angle"])*28
        if player["weapon"] > 0:
            pygame.draw.line(screen, (30, 30, 30), (sx, sy), (gx, gy), 6)
        # kafa üstü can barı
        draw_health_bar(sx, sy-30, 44, player["hp"]/player["maxhp"], big_bar=True)
        screen.blit(small.render(f'{int(max(0, player["hp"]))}', True, (255, 255, 255)), (sx-10, sy-46))
    else:
        c = player["in_car"]
        sx, sy = px(c["x"]), py(c["y"])
        # üstte senin canın, altta arabanın canı
        draw_health_bar(sx, sy-48, 56, player["hp"]/player["maxhp"], big_bar=True)
        screen.blit(small.render(f'{int(max(0, player["hp"]))}', True, (255, 255, 255)), (sx-10, sy-64))
        draw_health_bar(sx, sy-36, 56, max(0, c["hp"])/c["maxhp"], big_bar=True)
        screen.blit(small.render(f'🚗{int(max(0, c["hp"]))}', True, (255, 255, 0)), (sx-16, sy-52))

    for b in bullets:
        if b.get("rocket"):
            pygame.draw.circle(screen, (255, 60, 0), (px(b["x"]), py(b["y"])), 7)
            pygame.draw.circle(screen, (255, 230, 0), (px(b["x"]), py(b["y"])), 4)
        elif b.get("ice"):
            pygame.draw.circle(screen, (120, 200, 255), (px(b["x"]), py(b["y"])), 7)
            pygame.draw.circle(screen, (255, 255, 255), (px(b["x"]), py(b["y"])), 3)
        elif b.get("dagger"):
            ba = math.atan2(b["vy"], b["vx"]); bx_, by_ = px(b["x"]), py(b["y"])
            pygame.draw.line(screen, (225, 230, 245), (bx_, by_),
                             (bx_ + math.cos(ba)*16, by_ + math.sin(ba)*16), 3)       # bıçak
            pygame.draw.line(screen, (120, 80, 30), (bx_, by_),
                             (bx_ - math.cos(ba)*7, by_ - math.sin(ba)*7), 4)         # sap
        else:
            col = (255, 80, 80) if b["foe"] else (255, 235, 59)
            pygame.draw.circle(screen, col, (px(b["x"]), py(b["y"])), 4)

    for p in particles:
        pygame.draw.circle(screen, p["color"], (px(p["x"]), py(p["y"])), 3)

    for ex in explosions:
        pygame.draw.circle(screen, (255, 150, 0), (px(ex["x"]), py(ex["y"])), int(ex["r"]), 3)
        pygame.draw.circle(screen, (255, 230, 0), (px(ex["x"]), py(ex["y"])), int(ex["r"]//2))

    # nükleer şok dalgası + ekran flaşı
    for fx in nuke_fx:
        fx["t"] += dt
        cx_, cy_ = px(fx["x"]), py(fx["y"])
        if fx["t"] < 2.4:  # şok dalgası
            k = fx["t"] / 2.4
            rr = int(NUKE_R * 1.3 * k)
            pygame.draw.circle(screen, (255, 200, 80), (cx_, cy_), rr, max(2, int(22 * (1 - k))))
            pygame.draw.circle(screen, (255, 255, 255), (cx_, cy_), int(rr * 0.7), 5)
            pygame.draw.circle(screen, (255, 140, 0), (cx_, cy_), int(rr * 0.45))
        # mantar bulutu: gövde yükselir, başlık büyür, sonra söner
        mk = min(1.0, fx["t"] / 2.0)
        fade = 1.0 if fx["t"] < 3.0 else max(0.0, (4.0 - fx["t"]))
        if fade > 0:
            mo = pygame.Surface((W, H), pygame.SRCALPHA)
            stem_h = int(260 * mk)
            a_ = int(200 * fade)
            pygame.draw.rect(mo, (110, 100, 95, a_), (cx_ - 28, cy_ - stem_h, 56, stem_h))
            capr = int(30 + 110 * mk)
            capy = cy_ - stem_h
            pygame.draw.circle(mo, (255, 120, 20, a_), (cx_, capy), capr)
            pygame.draw.circle(mo, (255, 200, 60, a_), (cx_, capy - capr // 4), int(capr * 0.7))
            pygame.draw.circle(mo, (70, 65, 62, a_), (cx_ - capr // 2, capy + capr // 3), int(capr * 0.5))
            pygame.draw.circle(mo, (70, 65, 62, a_), (cx_ + capr // 2, capy + capr // 3), int(capr * 0.5))
            screen.blit(mo, (0, 0))
    nuke_fx = [f for f in nuke_fx if f["t"] < 4.0]
    if nuke_flash > 0:
        nuke_flash -= dt
        fl = pygame.Surface((W, H), pygame.SRCALPHA)
        fl.fill((255, 255, 255, max(0, min(255, int(255 * nuke_flash / 2.0)))))
        screen.blit(fl, (0, 0))

    # yön okları: helikopter + nükleer hedef ekran dışındaysa
    for hl in helis:
        draw_offscreen_arrow(hl["x"], hl["y"], (255, 220, 0), "HELİ")
        if not hl["dropped"]:
            draw_offscreen_arrow(hl["tx"], hl["ty"], (255, 120, 0), "HEDEF")
    for nk in nukes:
        draw_offscreen_arrow(nk["x"], nk["y"], (255, 40, 40), "NUKE")

    # donma efekti: buz bloğu + mavi ekran tonu
    if freeze_t > 0:
        fz = pygame.Surface((W, H), pygame.SRCALPHA)
        fz.fill((140, 200, 255, 70))
        pygame.draw.circle(fz, (200, 235, 255, 150), (px(tax), py(tay)), 30)
        pygame.draw.circle(fz, (255, 255, 255, 220), (px(tax), py(tay)), 30, 3)
        screen.blit(fz, (0, 0))
        screen.blit(big.render(f"❄ DONDUN {freeze_t:.1f}", True, (200, 235, 255)), (W//2-60, H//2-90))

    # boss can barı (ekranın üstünde)
    for en in enemies:
        if en["type"] == "boss":
            bw = 440
            bx0 = W//2 - bw//2
            pygame.draw.rect(screen, (0, 0, 0), (bx0-2, 138, bw+4, 20))
            pygame.draw.rect(screen, (40, 60, 100), (bx0, 140, bw, 16))
            pygame.draw.rect(screen, (110, 200, 255), (bx0, 140, int(bw*max(0, en["hp"])/en["maxhp"]), 16))
            screen.blit(small.render(f"❄ DONDURAN BOSS  {int(max(0,en['hp']))}/{en['maxhp']}", True, (255, 255, 255)), (bx0+6, 141))

    # HUD
    if nukes:
        n0 = min(nukes, key=lambda n: n["timer"])
        dn = math.hypot(tax - n0["x"], tay - n0["y"])
        status = "ÖLDÜRÜCÜ BÖLGEDESİN!" if dn < NUKE_R * NUKE_LETHAL else ("TEHLİKELİ BÖLGE!" if dn < NUKE_R else "güvendesin")
        screen.blit(big.render(f"☢ NÜKLEER BOMBA: {n0['timer']:.1f} sn - {status}", True, (255, 60, 60)), (W//2-230, 110))
    elif helis:
        screen.blit(big.render("🚁 Nükleer helikopter yolda! VUR ONU!", True, (255, 220, 0)), (W//2-190, 110))
    left = wave_total - len(wave_queue)
    car_txt = f"  🚗:{int(player['in_car']['hp'])}" if player['in_car'] else ""
    hud = font.render(f'DALGA:{wave} ({left}/{wave_total})  HP:{int(max(0, player["hp"]))}{car_txt}  Kills:{kills}  Wanted:{"* "*wanted}  Gun:{WEAPONS[player["weapon"]]["name"]} Ammo:{player["ammo"]}', True, (255, 255, 255))
    screen.blit(hud, (10, 10))
    if god:
        screen.blit(big.render("⚡ GOD MOD", True, (255, 215, 0)), (W-150, 36))
    screen.blit(small.render("WASD | Click ateş | 1/2/3 silah | E bin/in | R mermi  |  Yeşil=healer  Kasklı=roketçi  Mor=kılıçlı (dash!)  |  Nükleer helikopteri vur!", True, (255, 255, 255)), (10, H-24))
    screen.blit(small.render("Roket/bomba arabayı patlatır, sen -50 yersin | 💚 pickup arabayı tamir eder", True, (255, 150, 100)), (10, H-44))
    screen.blit(small.render(f"✈ Uçak:{len(planes)}  💣 Bomba:{len(bombs)} (kırmızı halkadan kaç!)", True, (150, 220, 255)), (10, H-64))
    # save göstergesi (60 framede bir güncelle)
    save_hud_tick += 1
    if save_hud_tick % 60 == 1:
        _sv = load_save()
        save_hud_txt = f"💾 Save: Dalga {_sv['wave']}" if _sv else "💾 Save yok (5. dalgada alınır) | L: yükle"
    screen.blit(small.render(save_hud_txt + " | 🌳 ağaç + 💡 direk", True, (180, 180, 180)), (10, H-84))
    screen.blit(small.render("☠ 7. dalgadan sonra gelen yarı saydam siyah gölgelere SALDIRMA! (dokunmazsan dalga bonusu)", True, (170, 170, 190)), (10, H-104))
    if wave_break_timer > 0:
        screen.blit(font.render(f'Sonraki dalga: {int(wave_break_timer)+1} sn', True, (0, 255, 150)), (W//2-140, 82))
    if wave_banner_t > 0:
        banner = big.render(f'--- DALGA {wave} ---', True, (255, 204, 0))
        screen.blit(banner, (W//2-110, H//2-60))
        sub = font.render(('❄ DONDURAN BOSS geliyor! ' if wave % 5 == 0 else '') + f'{wave_total} düşman geliyor!', True, (255, 255, 255))
        screen.blit(sub, (W//2-110, H//2-25))
    if msg_t > 0:
        screen.blit(font.render(msg, True, (255, 204, 0)), (W//2-220, 50))

    if console_open:
        cs = pygame.Surface((W, 150), pygame.SRCALPHA)
        cs.fill((0, 0, 0, 215))
        screen.blit(cs, (0, 0))
        pygame.draw.line(screen, (0, 255, 150), (0, 150), (W, 150), 2)
        for i, ln in enumerate(console_log[-6:]):
            screen.blit(small.render(ln, True, (180, 255, 200) if ln.startswith(">") else (255, 220, 120)), (12, 8 + i * 18))
        cur = "_" if (pygame.time.get_ticks() // 400) % 2 == 0 else " "
        screen.blit(font.render("> " + console_buf + cur, True, (0, 255, 150)), (12, 122))
        screen.blit(small.render("ENTER: çalıştır | ESC: kapat | oyun duraklatıldı", True, (150, 150, 150)), (W - 330, 128))

    pygame.display.flip()

pygame.quit()
