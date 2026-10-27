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

def px(wx): return int(wx - cam_x + W//2)
def py(wy): return int(wy - cam_y + H//2)

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

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            mouse_down = True
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            mouse_down = False
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_1: player["weapon"] = 0; msg, msg_t = "Equipped Fists", 1.5
            if e.key == pygame.K_2: player["weapon"] = 1; msg, msg_t = "Equipped Pistol", 1.5
            if e.key == pygame.K_3: player["weapon"] = 2; msg, msg_t = "Equipped Rifle", 1.5
            if e.key == pygame.K_r:
                player["ammo"] += 60; msg, msg_t = "+60 rifle ammo", 1.5
            if e.key == pygame.K_e:
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
                    wave_queue = make_wave(wave); wave_total = len(wave_queue)
                    wave_break_timer = 0; wave_banner_t = 3; plane_timer = 6
                    msg, msg_t = f"Save yüklendi: DALGA {wave}", 3
                else:
                    msg, msg_t = "Save yok! (her 5 dalgada alınır)", 2

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
                en["hp"] -= 300*dt
    else:
        ix = (1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0)
        iy = (1 if keys[pygame.K_s] else 0) - (1 if keys[pygame.K_w] else 0)
        l = math.hypot(ix, iy) or 1
        nx = player["x"] + ix/l*230*dt; ny = player["y"] + iy/l*230*dt
        if not hit_obstacle(nx, ny, 12):
            player["x"], player["y"] = nx, ny
        player["x"] = max(30, min(WORLD-30, player["x"])); player["y"] = max(30, min(WORLD-30, player["y"]))
        cam_x += (player["x"]-cam_x)*0.15; cam_y += (player["y"]-cam_y)*0.15

        w = WEAPONS[player["weapon"]]
        want = mouse_down if w["auto"] else (mouse_down and not prev_click)
        if want and player["cd"] <= 0:
            if player["weapon"] == 0:
                player["cd"] = w["cd"]
                for en in enemies:
                    if math.hypot(en["x"]-player["x"], en["y"]-player["y"]) < 70:
                        en["hp"] -= w["dmg"]
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
            else:
                r = 26 if player["in_car"] else 12
                if math.hypot(tax-b["x"], tay-b["y"]) < r:
                    b["life"] = 0
                    if player["in_car"]:
                        # mermi arabaya işler, sana değil
                        damage_car(player["in_car"], b["dmg"], "taranıyorsun")
                    else:
                        player["hp"] -= b["dmg"]*0.4
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
                if not hit_obstacle(_nx, _ny, 10):
                    en["x"], en["y"] = _nx, _ny
            elif d < 250:  # oyuncudan biraz kaç
                en["x"] -= math.cos(a)*en["speed"]*0.7; en["y"] -= math.sin(a)*en["speed"]*0.7
            elif target is None and d > 220:
                en["x"] += math.cos(a)*en["speed"]*0.6; en["y"] += math.sin(a)*en["speed"]*0.6
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
                if not hit_obstacle(_nx, _ny, 10):
                    en["x"], en["y"] = _nx, _ny
            elif d < 220:
                _nx = en["x"]-math.cos(a)*en["speed"]; _ny = en["y"]-math.sin(a)*en["speed"]
                if not hit_obstacle(_nx, _ny, 10):
                    en["x"], en["y"] = _nx, _ny
            en["cd"] -= dt
            if en["cd"] <= 0 and d < 600:
                en["cd"] = 2.4 + random.random()*1.2  # roket yavaş atar
                spd = 5.2
                bullets.append({"x": en["x"], "y": en["y"],
                                "vx": math.cos(a)*spd, "vy": math.sin(a)*spd,
                                "life": 130, "dmg": 40, "foe": True, "rocket": True})
        elif t == "cop":
            # MAVİLER TARAMALI: tam otomatik, seri atış
            if d > 260:
                _nx = en["x"]+math.cos(a)*en["speed"]; _ny = en["y"]+math.sin(a)*en["speed"]
                if not hit_obstacle(_nx, _ny, 10):
                    en["x"], en["y"] = _nx, _ny
            elif d < 140:
                _nx = en["x"]-math.cos(a)*en["speed"]*0.6; _ny = en["y"]-math.sin(a)*en["speed"]*0.6
                if not hit_obstacle(_nx, _ny, 10):
                    en["x"], en["y"] = _nx, _ny
            else:
                # yan strafing (sağa sola kay)
                strafe = 1 if (pygame.time.get_ticks()//500 + int(en["x"])) % 2 == 0 else -1
                en["x"] += -math.sin(a)*en["speed"]*0.5*strafe
                en["y"] += math.cos(a)*en["speed"]*0.5*strafe
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
                if not hit_obstacle(_nx, _ny, 10):
                    en["x"], en["y"] = _nx, _ny
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

    if player["hp"] <= 0:
        s = load_save()
        enemies.clear(); bullets.clear(); planes.clear(); bombs.clear()
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
        elif t == "cop":
            pygame.draw.circle(screen, (10, 132, 255), (sx, sy), 12)
            # taramalı işareti: çift çizgi namlu
            pygame.draw.line(screen, (20, 20, 20), (sx, sy), (sx+16, sy), 4)
            pygame.draw.line(screen, (20, 20, 20), (sx, sy+4), (sx+14, sy+4), 2)
        else:
            pygame.draw.circle(screen, (255, 69, 58), (sx, sy), 12)
        draw_health_bar(sx, sy-26, 30, en["hp"]/en["maxhp"])

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
        else:
            col = (255, 80, 80) if b["foe"] else (255, 235, 59)
            pygame.draw.circle(screen, col, (px(b["x"]), py(b["y"])), 4)

    for p in particles:
        pygame.draw.circle(screen, p["color"], (px(p["x"]), py(p["y"])), 3)

    for ex in explosions:
        pygame.draw.circle(screen, (255, 150, 0), (px(ex["x"]), py(ex["y"])), int(ex["r"]), 3)
        pygame.draw.circle(screen, (255, 230, 0), (px(ex["x"]), py(ex["y"])), int(ex["r"]//2))

    # HUD
    left = wave_total - len(wave_queue)
    car_txt = f"  🚗:{int(player['in_car']['hp'])}" if player['in_car'] else ""
    hud = font.render(f'DALGA:{wave} ({left}/{wave_total})  HP:{int(max(0, player["hp"]))}{car_txt}  Kills:{kills}  Wanted:{"* "*wanted}  Gun:{WEAPONS[player["weapon"]]["name"]} Ammo:{player["ammo"]}', True, (255, 255, 255))
    screen.blit(hud, (10, 10))
    screen.blit(small.render("WASD | Click ateş | 1/2/3 silah | E bin/in | R mermi  |  Yeşil=healer  Kasklı=roketçi", True, (255, 255, 255)), (10, H-24))
    screen.blit(small.render("Roket/bomba arabayı patlatır, sen -50 yersin | 💚 pickup arabayı tamir eder", True, (255, 150, 100)), (10, H-44))
    screen.blit(small.render(f"✈ Uçak:{len(planes)}  💣 Bomba:{len(bombs)} (kırmızı halkadan kaç!)", True, (150, 220, 255)), (10, H-64))
    # save göstergesi (60 framede bir güncelle)
    save_hud_tick += 1
    if save_hud_tick % 60 == 1:
        _sv = load_save()
        save_hud_txt = f"💾 Save: Dalga {_sv['wave']}" if _sv else "💾 Save yok (5. dalgada alınır) | L: yükle"
    screen.blit(small.render(save_hud_txt + " | 🌳 ağaç + 💡 direk", True, (180, 180, 180)), (10, H-84))
    if wave_break_timer > 0:
        screen.blit(font.render(f'Sonraki dalga: {int(wave_break_timer)+1} sn', True, (0, 255, 150)), (W//2-140, 82))
    if wave_banner_t > 0:
        banner = big.render(f'--- DALGA {wave} ---', True, (255, 204, 0))
        screen.blit(banner, (W//2-110, H//2-60))
        sub = font.render(f'{wave_total} düşman geliyor!', True, (255, 255, 255))
        screen.blit(sub, (W//2-110, H//2-25))
    if msg_t > 0:
        screen.blit(font.render(msg, True, (255, 204, 0)), (W//2-220, 50))

    pygame.display.flip()

pygame.quit()
