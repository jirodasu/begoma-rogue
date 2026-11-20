# ベゴマ・ローグ（仮） - Pyxel試作
# モンスターをコマ型の乗り物「ベゴマ」に乗せて戦う、3対3勝ち抜きのローグライク
# 操作: 方向キー/WASD/十字=加速  X/Shift/B=ブレーキ  Z/Space/A=必殺(ゲージMAX時)  Z/Enter/A=決定
import math
import os
import random

import pyxel

VERSION = "0.1.0"
W, H = 256, 192
CX, CY, R = 128, 108, 78
FPS = 60
ROUND_SEC = 45
MATCHES = 3

# ---------------------------------------------------------------- 文字
FONT = None


def L(ja, en):
    return ja if FONT else en


def txt(x, y, s, col):
    if FONT:
        pyxel.text(int(x), int(y), s, col, FONT)
    else:
        pyxel.text(int(x), int(y), s, col)


def txt_w(s):
    if FONT:
        try:
            return FONT.text_width(s)
        except Exception:
            return len(s) * 10
    return len(s) * 4


def txt_c(y, s, col, cx=W // 2):
    txt(cx - txt_w(s) // 2, y, s, col)


def load_font():
    global FONT
    base = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
    for p in ("umplus_j10r.bdf", os.path.join("assets", "umplus_j10r.bdf")):
        path = os.path.join(base, p)
        if os.path.exists(path):
            try:
                FONT = pyxel.Font(path)
                return
            except Exception:
                FONT = None


# ---------------------------------------------------------------- データ
ROSTER = [
    dict(ja="ボルカ", en="VOLCA", col=8, sub=9, mass=1.2, acc=0.15, vmax=2.5, hp=100, atk="dash"),
    dict(ja="ゴロン", en="GORON", col=4, sub=15, mass=1.9, acc=0.10, vmax=1.9, hp=130, atk="shock"),
    dict(ja="ピリカ", en="PIRIKA", col=10, sub=9, mass=0.85, acc=0.19, vmax=2.9, hp=98, atk="bolt"),
    dict(ja="ミズチ", en="MIZUCHI", col=12, sub=6, mass=1.0, acc=0.14, vmax=2.4, hp=105, atk="bolt"),
    dict(ja="カブト", en="KABUTO", col=3, sub=11, mass=1.4, acc=0.12, vmax=2.1, hp=100, atk="dash"),
    dict(ja="フワリ", en="FUWARI", col=14, sub=7, mass=0.9, acc=0.17, vmax=2.6, hp=95, atk="shock"),
]

ATK = {
    "dash": dict(ja="突進", en="DASH", dmg=28, jd="向いた方へ一気に突っ込む", ed="charge forward"),
    "shock": dict(ja="衝撃波", en="SHOCK", dmg=24, jd="周りをはね飛ばす。近いほど強い", ed="blast around you"),
    "bolt": dict(ja="雷弾", en="BOLT", dmg=27, jd="相手を追う弾を撃つ", ed="homing shot"),
}

# (id, 日本語名, 英語名, 日本語説明, 英語説明, 効果)
RELICS = [
    ("spike", "スパイクリング", "SPIKE RING", "ぶつかりのゲージ+35%", "clash gauge +35%", {"gauge_mul": 0.35}),
    ("heavy", "ヘビーコア", "HEAVY CORE", "重さ+30%。押し負けない", "mass +30%", {"mass": 0.30}),
    ("turbo", "ターボモーター", "TURBO MOTOR", "加速+20% 最高速+12%", "accel+20% speed+12%", {"acc": 0.20, "vmax": 0.12}),
    ("shell", "ガードシェル", "GUARD SHELL", "受けるダメージ-20%", "damage taken -20%", {"dmg_taken": -0.20}),
    ("chip", "チャージチップ", "CHARGE CHIP", "ゲージ50で戦い始める", "start with 50 gauge", {"start_gauge": 50}),
    ("edge", "キラーエッジ", "KILLER EDGE", "必殺の威力+25%", "special damage +25%", {"dmg_mul": 0.25}),
    ("repair", "リペアキット", "REPAIR KIT", "最大HP+25", "max HP +25", {"hp": 25}),
]
ADDITIVE = {"hp", "start_gauge"}


class Mods:
    def __init__(self, effects=()):
        self.mass = self.acc = self.vmax = self.gauge_mul = self.dmg_taken = self.dmg_mul = 1.0
        self.hp = 0
        self.start_gauge = 0
        for eff in effects:
            for k, v in eff.items():
                if k in ADDITIVE:
                    setattr(self, k, getattr(self, k) + v)
                else:
                    setattr(self, k, getattr(self, k) * (1 + v))


ENEMY_EFFECTS = [
    [],
    [{"hp": 10, "dmg_mul": 0.05}],
    [{"hp": 20, "dmg_mul": 0.12, "gauge_mul": 0.10}],
]
AI_LEVEL = [0.55, 0.75, 0.95]


# ---------------------------------------------------------------- 戦い（描画から独立）
class Fighter:
    def __init__(self, d, x, y, mods):
        self.d = d
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.mass = d["mass"] * mods.mass
        self.acc = d["acc"] * mods.acc
        self.vmax = d["vmax"] * mods.vmax
        self.maxhp = d["hp"] + mods.hp
        self.hp = float(self.maxhp)
        self.gauge = float(min(100, mods.start_gauge))
        self.gauge_mul = mods.gauge_mul
        self.dmg_taken = mods.dmg_taken
        self.dmg_mul = mods.dmg_mul
        self.r = 7 + round(self.mass * 2)
        self.spin = 0.0
        self.flash = 0
        self.dash_t = 0
        self.dash_hit = False
        self.braking = False
        self.trail = []
        self.face = (1.0, 0.0)

    @property
    def speed(self):
        return math.hypot(self.vx, self.vy)


class Battle:
    def __init__(self, pdef, edef, pmods, emods, ai_level, rng):
        self.rng = rng
        self.p = Fighter(pdef, CX - 42, CY, pmods)
        self.e = Fighter(edef, CX + 42, CY, emods)
        self.p.vy, self.e.vy = -1.0, 1.0
        self.ai = AI(ai_level, rng)
        self.t = 0
        self.limit = ROUND_SEC * FPS
        self.count = 150
        self.state = "count"  # count -> fight -> end
        self.end_t = 0
        self.winner = None  # "p" / "e"
        self.reason = ""
        self.projs, self.waves, self.parts, self.pops = [], [], [], []
        self.shake = 0.0
        self.events = []

    # ---- 1フレーム進める
    def step(self, pin):
        self.events.clear()
        for f in (self.p, self.e):
            f.spin += 0.25 + f.speed * 0.12
            f.flash = max(0, f.flash - 1)
        self._update_fx()
        if self.state == "count":
            self.count -= 1
            if self.count in (150 - 1, 100, 50):
                self.events.append("tick")
            if self.count <= 0:
                self.state = "fight"
                self.events.append("go")
            return
        if self.state == "end":
            self.end_t += 1
            self._physics(None, None)
            return
        self.t += 1
        ein = self.ai.think(self.e, self.p, self)
        self._physics(pin, ein)
        self._attacks(pin, ein)
        self._check_end()

    def done(self):
        return self.state == "end" and self.end_t > 100

    # ---- 動き
    def _move(self, f, inp):
        dx = dy = 0.0
        mag = 1.0
        f.braking = False
        if inp:
            dx, dy = inp.get("dx", 0), inp.get("dy", 0)
            mag = inp.get("mag", 1.0)
            f.braking = inp.get("brake", False)
        n = math.hypot(dx, dy)
        if n > 0 and f.dash_t <= 0:
            f.vx += dx / n * f.acc * mag
            f.vy += dy / n * f.acc * mag
            f.face = (dx / n, dy / n)
        # すり鉢の傾き（中心へ引かれる）
        f.vx -= (f.x - CX) * 0.0011
        f.vy -= (f.y - CY) * 0.0011
        fr = 0.93 if f.braking else (0.995 if f.dash_t > 0 else 0.988)
        f.vx *= fr
        f.vy *= fr
        s = f.speed
        if f.dash_t > 0:
            f.dash_t -= 1
        elif s > f.vmax:
            k = max(f.vmax / s, 0.95)
            f.vx *= k
            f.vy *= k
        f.x += f.vx
        f.y += f.vy
        self._wall(f)
        if f.speed > 0.3:
            f.trail.append((f.x, f.y))
        if len(f.trail) > (8 if f.dash_t > 0 else 3) or (f.trail and f.speed <= 0.3):
            f.trail.pop(0)

    def _wall(self, f):
        # 外周の壁：はみ出したら内側へ戻して跳ね返す
        dx, dy = f.x - CX, f.y - CY
        d = math.hypot(dx, dy)
        lim = R - f.r
        if d <= lim:
            return
        nx, ny = dx / d, dy / d
        f.x, f.y = CX + nx * lim, CY + ny * lim
        vn = f.vx * nx + f.vy * ny
        if vn > 0:
            f.vx -= 1.75 * vn * nx
            f.vy -= 1.75 * vn * ny
            if vn > 1.2:
                self.events.append("wall")
                self._sparks(f.x + nx * f.r, f.y + ny * f.r, 4, 13)

    def _physics(self, pin, ein):
        self._move(self.p, pin)
        self._move(self.e, ein)
        p, e = self.p, self.e
        dx, dy = e.x - p.x, e.y - p.y
        d = math.hypot(dx, dy)
        if d <= 0.001 or d >= p.r + e.r:
            return
        nx, ny = dx / d, dy / d
        # めり込みを質量の逆比で押し戻す
        ov = p.r + e.r - d
        ip, ie = 1 / p.mass, 1 / e.mass
        p.x -= nx * ov * ip / (ip + ie)
        p.y -= ny * ov * ip / (ip + ie)
        e.x += nx * ov * ie / (ip + ie)
        e.y += ny * ov * ie / (ip + ie)
        self._wall(p)
        self._wall(e)
        ap = max(0.0, p.vx * nx + p.vy * ny)
        ae = max(0.0, -(e.vx * nx + e.vy * ny))
        rel = (p.vx - e.vx) * nx + (p.vy - e.vy) * ny
        if rel <= 0:
            return
        j = 1.9 * rel / (ip + ie)
        p.vx -= j * ip * nx
        p.vy -= j * ip * ny
        e.vx += j * ie * nx
        e.vy += j * ie * ny
        if self.state != "fight":
            return
        tot = ap + ae + 1e-6
        sp = 0.3 + 0.7 * ap / tot
        se = 0.3 + 0.7 * ae / tot
        g = rel * 12
        self._gain(p, g * sp)
        self._gain(e, g * se)
        # かすりダメージ（ぶつけた側が有利）
        self._damage(e, rel * 0.45 * sp, chip=True)
        self._damage(p, rel * 0.45 * se, chip=True)
        mx, my = (p.x + e.x) / 2, (p.y + e.y) / 2
        self._sparks(mx, my, int(4 + rel * 3), 10)
        self.shake = max(self.shake, min(5.0, rel * 1.6))
        self.events.append("clash")
        for a, b, s in ((p, e, 1), (e, p, -1)):
            if a.dash_t > 0 and not a.dash_hit:
                a.dash_hit = True
                self._damage(b, ATK["dash"]["dmg"] * a.dmg_mul)
                b.vx += nx * s * 2.5 / b.mass
                b.vy += ny * s * 2.5 / b.mass

    def _gain(self, f, amount):
        before = f.gauge
        f.gauge = min(100.0, f.gauge + amount * f.gauge_mul)
        if before < 100 <= f.gauge:
            self.events.append("full")

    def _damage(self, f, amount, chip=False):
        amount *= f.dmg_taken
        f.hp = max(0.0, f.hp - amount)
        if not chip:
            f.flash = 14
            self.shake = max(self.shake, 5.0)
            self.pops.append([f.x, f.y - f.r - 4, str(int(round(amount))), 40])
            self._sparks(f.x, f.y, 14, 7)
            self.events.append("hit")

    # ---- 必殺
    def _attacks(self, pin, ein):
        for f, foe, inp in ((self.p, self.e, pin), (self.e, self.p, ein)):
            if inp and inp.get("atk") and f.gauge >= 100:
                self._fire(f, foe, inp)
        for pr in self.projs:
            tgt = pr["tgt"]
            ang = math.atan2(pr["vy"], pr["vx"])
            want = math.atan2(tgt.y - pr["y"], tgt.x - pr["x"])
            da = (want - ang + math.pi) % (2 * math.pi) - math.pi
            ang += max(-0.065, min(0.065, da))
            sp = 3.4
            pr["vx"], pr["vy"] = math.cos(ang) * sp, math.sin(ang) * sp
            pr["x"] += pr["vx"]
            pr["y"] += pr["vy"]
            pr["life"] -= 1
            if math.hypot(tgt.x - pr["x"], tgt.y - pr["y"]) < tgt.r + 3:
                self._damage(tgt, ATK["bolt"]["dmg"] * pr["mul"])
                tgt.vx += pr["vx"] * 0.5 / tgt.mass
                tgt.vy += pr["vy"] * 0.5 / tgt.mass
                pr["life"] = 0
            elif math.hypot(pr["x"] - CX, pr["y"] - CY) > R:
                pr["life"] = 0
                self._sparks(pr["x"], pr["y"], 5, 10)
        self.projs = [p for p in self.projs if p["life"] > 0]
        for w in self.waves:
            w["r"] += 3.2
            src, tgt = w["src"], w["tgt"]
            w["x"], w["y"] = src.x, src.y
            dist = math.hypot(tgt.x - w["x"], tgt.y - w["y"])
            if not w["hit"] and dist <= w["r"] + tgt.r:
                w["hit"] = True
                closeness = 1.0 - 0.4 * min(1.0, dist / w["max"])
                self._damage(tgt, ATK["shock"]["dmg"] * w["mul"] * closeness / 0.8)
                if dist > 0:
                    tgt.vx += (tgt.x - w["x"]) / dist * 3.6 / tgt.mass
                    tgt.vy += (tgt.y - w["y"]) / dist * 3.6 / tgt.mass
        self.waves = [w for w in self.waves if w["r"] < w["max"]]

    def _fire(self, f, foe, inp):
        f.gauge = 0
        kind = f.d["atk"]
        if kind == "dash":
            dx, dy = inp.get("dx", 0), inp.get("dy", 0)
            if dx == 0 and dy == 0:
                dx, dy = foe.x - f.x, foe.y - f.y
            n = math.hypot(dx, dy) or 1
            f.vx, f.vy = dx / n * 5.4, dy / n * 5.4
            f.dash_t = 28
            f.dash_hit = False
            self.events.append("dash")
        elif kind == "shock":
            self.waves.append(dict(x=f.x, y=f.y, r=f.r, max=50, src=f, tgt=foe, hit=False, mul=f.dmg_mul))
            self.events.append("shock")
        else:
            a = math.atan2(foe.y - f.y, foe.x - f.x)
            self.projs.append(dict(x=f.x, y=f.y, vx=math.cos(a) * 3.4, vy=math.sin(a) * 3.4,
                                   tgt=foe, life=110, col=f.d["col"], mul=f.dmg_mul))
            self.events.append("bolt")

    def _check_end(self):
        if self.p.hp <= 0 or self.e.hp <= 0:
            self.winner = "e" if self.p.hp <= 0 else "p"
            self.reason = "ko"
        elif self.t >= self.limit:
            rp, re_ = self.p.hp / self.p.maxhp, self.e.hp / self.e.maxhp
            self.winner = "p" if rp >= re_ else "e"
            self.reason = "time"
        else:
            return
        self.state = "end"
        self.events.append("ko" if self.reason == "ko" else "time")
        loser = self.e if self.winner == "p" else self.p
        self._sparks(loser.x, loser.y, 30, 8)

    # ---- 演出用
    def _sparks(self, x, y, n, col):
        for _ in range(n):
            a = self.rng.random() * math.tau
            s = 0.6 + self.rng.random() * 2.2
            self.parts.append([x, y, math.cos(a) * s, math.sin(a) * s, 10 + self.rng.randint(0, 12), col])

    def _update_fx(self):
        for pt in self.parts:
            pt[0] += pt[2]
            pt[1] += pt[3]
            pt[2] *= 0.9
            pt[3] *= 0.9
            pt[4] -= 1
        self.parts = [pt for pt in self.parts if pt[4] > 0]
        for po in self.pops:
            po[1] -= 0.4
            po[3] -= 1
        self.pops = [po for po in self.pops if po[3] > 0]
        self.shake *= 0.85


class AI:
    def __init__(self, level, rng):
        self.l = level
        self.rng = rng
        self.timer = 0
        self.plan = "chase"
        self.side = 1

    def think(self, me, foe, battle):
        self.timer -= 1
        dx, dy = foe.x - me.x, foe.y - me.y
        d = math.hypot(dx, dy) or 1
        if self.timer <= 0:
            self.timer = int(26 - 16 * self.l) + self.rng.randint(0, 8)
            if foe.gauge >= 100 and d < 70 and self.rng.random() < self.l * 0.6:
                self.plan = "evade"
                self.side = self.rng.choice((-1, 1))
            elif d < 30 and me.speed < 1.0 and self.rng.random() < 0.6:
                self.plan = "backoff"
            else:
                self.plan = "chase"
        if self.plan == "evade":
            mx, my = -dy / d * self.side, dx / d * self.side
        elif self.plan == "backoff":
            mx, my = -dx / d, -dy / d
        else:
            lead = 6 + 10 * self.l
            tx, ty = foe.x + foe.vx * lead, foe.y + foe.vy * lead
            mx, my = tx - me.x, ty - me.y
        atk = False
        if me.gauge >= 100 and self.rng.random() < 0.03 + 0.07 * self.l:
            kind = me.d["atk"]
            atk = (kind == "dash" and 18 < d < 85) or (kind == "shock" and d < 46) or (kind == "bolt" and d > 22)
        return dict(dx=mx, dy=my, mag=0.55 + 0.45 * self.l, brake=False, atk=atk)


# ---------------------------------------------------------------- 入力
def btn_any(keys):
    return any(pyxel.btn(k) for k in keys)


def btnp_any(keys):
    return any(pyxel.btnp(k) for k in keys)


K_LEFT = (pyxel.KEY_LEFT, pyxel.KEY_A, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT)
K_RIGHT = (pyxel.KEY_RIGHT, pyxel.KEY_D, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
K_UP = (pyxel.KEY_UP, pyxel.KEY_W, pyxel.GAMEPAD1_BUTTON_DPAD_UP)
K_DOWN = (pyxel.KEY_DOWN, pyxel.KEY_S, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
K_OK = (pyxel.KEY_Z, pyxel.KEY_SPACE, pyxel.KEY_RETURN, pyxel.GAMEPAD1_BUTTON_A)
K_ATK = (pyxel.KEY_Z, pyxel.KEY_SPACE, pyxel.GAMEPAD1_BUTTON_A)
K_BRAKE = (pyxel.KEY_X, pyxel.KEY_LSHIFT, pyxel.GAMEPAD1_BUTTON_B)


def read_battle_input():
    return dict(
        dx=btn_any(K_RIGHT) - btn_any(K_LEFT),
        dy=btn_any(K_DOWN) - btn_any(K_UP),
        brake=btn_any(K_BRAKE),
        atk=btnp_any(K_ATK),
        mag=1.0,
    )


# ---------------------------------------------------------------- 音
# ゲーム音楽30年のプロの方針：コマの金属感とモンスターのにぎやかさを、内蔵音源だけで最短に作る
def setup_sounds():
    s = pyxel.sounds
    s[0].set("a3c3", "n", "64", "nf", 2)          # ぶつかり（ガチッ）
    s[1].set("c3e3g3c4", "p", "5", "n", 4)        # ゲージMAX
    s[2].set("c2g2c3g3c4", "s", "6", "n", 2)      # 突進
    s[3].set("c1c1", "n", "76", "nf", 9)          # 衝撃波
    s[4].set("g4c4g3", "s", "5", "f", 3)          # 雷弾
    s[5].set("e2c1", "n", "77", "nf", 6)          # 必殺命中
    s[6].set("g3e3c3g2c2", "s", "6", "f", 9)      # KO
    s[7].set("c3e3g3c4e4g4c4", "p", "6", "n", 7)  # 勝ち
    s[8].set("c4", "p", "3", "n", 3)              # カーソル
    s[9].set("e3a3", "p", "4", "n", 3)            # 決定
    s[10].set("c3", "p", "4", "n", 6)             # カウント
    s[11].set("c4", "p", "5", "n", 12)            # GO
    s[12].set("c2r", "n", "3", "f", 3)            # 壁
    s[13].set("e3c3a2", "t", "5", "f", 12)        # 負け


SE = dict(clash=(0, 0), full=(1, 1), dash=(2, 2), shock=(2, 3), bolt=(2, 4), hit=(3, 5), ko=(3, 6),
          time=(3, 6), win=(0, 7), cursor=(3, 8), ok=(3, 9), tick=(3, 10), go=(3, 11), wall=(1, 12),
          lose=(0, 13))


def se(name):
    ch, snd = SE[name]
    pyxel.play(ch, snd)


# ---------------------------------------------------------------- ゲーム全体
def name(d):
    return L(d["ja"], d["en"])


class Game:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.state = "title"
        self.cursor = 0
        self.frame = 0
        self.battle = None

    # ---- 挑戦の始まり
    def new_run(self):
        self.team = self.rng.sample(ROSTER, 3)
        self.relics = []
        self.match = 0
        self.start_match()
        self.state = "map"

    def start_match(self):
        self.enemy_team = self.rng.sample(ROSTER, 3)
        self.p_wins = self.e_wins = 0
        self.round = 0
        self.used = set()
        self.last_win = None

    def pmods(self):
        return Mods([r[5] for r in self.relics])

    def remaining(self):
        return [d for d in self.team if d["ja"] not in self.used]

    # ---- 更新
    def update(self):
        self.frame += 1
        getattr(self, "u_" + self.state)()

    def ok(self):
        if btnp_any(K_OK):
            se("ok")
            return True
        return False

    def move_cursor(self, n):
        if btnp_any(K_UP):
            self.cursor = (self.cursor - 1) % n
            se("cursor")
        if btnp_any(K_DOWN):
            self.cursor = (self.cursor + 1) % n
            se("cursor")

    def u_title(self):
        if self.ok():
            self.new_run()

    def u_map(self):
        if self.ok():
            self.cursor = 0
            self.state = "pick"

    def u_pick(self):
        rem = self.remaining()
        self.move_cursor(len(rem))
        if self.ok():
            mine = rem[self.cursor]
            self.used.add(mine["ja"])
            foe = self.enemy_team[self.round]
            emods = Mods(ENEMY_EFFECTS[self.match])
            self.battle = Battle(mine, foe, self.pmods(), emods, AI_LEVEL[self.match], self.rng)
            self.state = "battle"

    def u_battle(self):
        b = self.battle
        b.step(read_battle_input() if b.state == "fight" else None)
        for ev in b.events:
            se(ev)
        if b.done():
            self.last_win = b.winner
            if b.winner == "p":
                self.p_wins += 1
                se("win")
            else:
                self.e_wins += 1
                se("lose")
            self.round += 1
            self.state = "round_result"

    def u_round_result(self):
        if self.ok():
            if self.p_wins >= 2 or self.e_wins >= 2:
                self.state = "match_result"
            else:
                self.cursor = 0
                self.state = "pick"

    def u_match_result(self):
        if self.ok():
            if self.e_wins >= 2:
                self.state = "over"
            elif self.match + 1 >= MATCHES:
                self.state = "clear"
            else:
                owned = {r[0] for r in self.relics}
                pool = [r for r in RELICS if r[0] not in owned]
                self.offer = self.rng.sample(pool, min(3, len(pool)))
                self.cursor = 0
                self.state = "reward"

    def u_reward(self):
        self.move_cursor(len(self.offer))
        if self.ok():
            self.relics.append(self.offer[self.cursor])
            self.match += 1
            self.start_match()
            self.state = "map"

    def u_over(self):
        if self.ok():
            self.state = "title"

    u_clear = u_over

    # ---- 描画
    def draw(self):
        pyxel.cls(0)
        getattr(self, "d_" + self.state)()

    def d_title(self):
        self.draw_bowl()
        a = self.frame * 0.15
        draw_top(ROSTER[0], CX, CY - 4, 12, a)
        txt_c(26, L("ベゴマ・ローグ（仮）", "BEGOMA ROGUE"), 10)
        txt_c(42, L("3体で勝ち抜け！ ベゴマバトル", "3-ON-3 SPINNING TOP BATTLES"), 7)
        if self.frame // 20 % 2 == 0:
            txt_c(150, L("Zで はじめる", "PRESS Z"), 7)
        txt(4, H - 10, "v" + VERSION, 5)

    def d_map(self):
        txt_c(12, L("大会 %d / %d" % (self.match + 1, MATCHES), "MATCH %d / %d" % (self.match + 1, MATCHES)), 10)
        for i in range(MATCHES):
            x = 64 + i * 64
            col = 11 if i < self.match else (10 if i == self.match else 5)
            pyxel.circ(x, 40, 9 if i == self.match else 6, col)
            if i < MATCHES - 1:
                pyxel.line(x + 10, 40, x + 54, 40, 5)
        txt_c(58, L("あいてのチーム", "RIVAL TEAM"), 13)
        for i, d in enumerate(self.enemy_team):
            draw_top(d, 64 + i * 64, 86, 9, self.frame * 0.1)
            txt_c(100, name(d), 7, 64 + i * 64)
        txt_c(120, L("きみのチーム", "YOUR TEAM"), 13)
        for i, d in enumerate(self.team):
            draw_top(d, 64 + i * 64, 146, 9, self.frame * 0.1)
            txt_c(160, name(d), 7, 64 + i * 64)
        if self.relics:
            txt(4, H - 10, L("パーツ: ", "PARTS: ") + " ".join(L(r[1], r[2]) for r in self.relics)[:60], 6)
        if self.frame // 20 % 2 == 0:
            txt_c(176, L("Zで すすむ", "PRESS Z"), 7)

    def score_line(self, y):
        s = L("きみ %d - %d あいて", "YOU %d - %d RIVAL") % (self.p_wins, self.e_wins)
        txt_c(y, s, 7)

    def d_pick(self):
        foe = self.enemy_team[self.round]
        self.score_line(6)
        txt_c(20, L("つぎの相手", "NEXT RIVAL"), 13)
        draw_top(foe, W // 2, 44, 10, self.frame * 0.1)
        txt_c(58, "%s  %s" % (name(foe), L(ATK[foe["atk"]]["ja"], ATK[foe["atk"]]["en"])), 8)
        txt_c(76, L("だれを出す？", "WHO GOES?"), 10)
        rem = self.remaining()
        for i, d in enumerate(rem):
            y = 92 + i * 16
            sel = i == self.cursor
            if sel:
                pyxel.rect(60, y - 3, 136, 14, 1)
                txt(64, y, ">", 10)
            draw_top(d, 80, y + 3, 5, self.frame * 0.1 if sel else 0)
            txt(92, y, name(d), 7 if sel else 13)
            txt(150, y, L(ATK[d["atk"]]["ja"], ATK[d["atk"]]["en"]), d["col"])
        d = rem[self.cursor]
        a = ATK[d["atk"]]
        txt_c(150, L(a["jd"], a["ed"]), 6)
        txt_c(164, "HP %d  %s %.1f  %s %.1f" % (d["hp"], L("重さ", "MASS"), d["mass"], L("速さ", "SPD"), d["vmax"]), 13)

    def d_battle(self):
        b = self.battle
        sx = (b.rng.random() - 0.5) * b.shake * 2 if b.shake > 0.3 else 0
        sy = (b.rng.random() - 0.5) * b.shake * 2 if b.shake > 0.3 else 0
        pyxel.camera(sx, sy)
        self.draw_bowl()
        for w in b.waves:
            pyxel.circb(w["x"], w["y"], w["r"], 7 if self.frame % 4 < 2 else w["src"].d["col"])
        for f in (b.p, b.e):
            for i, (tx, ty) in enumerate(f.trail):
                pyxel.circ(tx, ty, max(1, f.r - 4 + i // 2), f.d["sub"] if f.dash_t > 0 else 1)
        for f in sorted((b.p, b.e), key=lambda f: f.y):
            draw_fighter(f, self.frame, f is b.p)
        for pr in b.projs:
            pyxel.circ(pr["x"], pr["y"], 3, pr["col"])
            pyxel.circ(pr["x"], pr["y"], 1, 7)
        for pt in b.parts:
            pyxel.pset(pt[0], pt[1], pt[5] if pt[4] > 4 else 9)
        for po in b.pops:
            txt(po[0] - 6, po[1], po[2], 7 if po[3] % 6 < 3 else 10)
        pyxel.camera()
        self.draw_hud(b)
        if b.state == "count":
            n = b.count // 50 + 1
            txt_c(CY - 4, str(n), 10)
            txt_c(H - 12, L("移動:方向キー  ブレーキ:X  必殺:Z", "MOVE:ARROWS BRAKE:X SPECIAL:Z"), 13)
        elif b.state == "fight" and b.t < 40:
            txt_c(CY - 4, "GO!", 10)
        elif b.state == "end":
            if b.reason == "ko":
                txt_c(CY - 20, "K.O.!", 8 if self.frame % 6 < 3 else 10)
            else:
                txt_c(CY - 20, L("タイムアップ", "TIME UP"), 10)

    def draw_hud(self, b):
        pyxel.rect(0, 0, W, 24, 0)
        for f, left in ((b.p, True), (b.e, False)):
            x = 4 if left else W - 104
            txt(x, 2, name(f.d), f.d["col"])
            pyxel.rect(x, 11, 100, 5, 1)
            hw = int(100 * f.hp / f.maxhp)
            pyxel.rect(x if left else x + 100 - hw, 11, hw, 5, 11 if f.hp / f.maxhp > 0.3 else 8)
            pyxel.rect(x, 18, 100, 3, 1)
            gw = int(100 * f.gauge / 100)
            full = f.gauge >= 100
            pyxel.rect(x if left else x + 100 - gw, 18, gw, 3, (10 if self.frame % 8 < 4 else 7) if full else 9)
        remain = max(0, (b.limit - b.t) // FPS)
        txt_c(6, str(remain), 7 if remain > 10 else 8)

    def d_round_result(self):
        self.draw_bowl()
        win = self.last_win == "p"
        txt_c(60, L("勝ち！", "YOU WIN!") if win else L("負け…", "YOU LOSE..."), 10 if win else 8)
        self.score_line(80)
        if self.frame // 20 % 2 == 0:
            txt_c(150, L("Zで つぎへ", "PRESS Z"), 7)

    def d_match_result(self):
        win = self.p_wins >= 2
        txt_c(60, L("大会に勝った！", "MATCH WON!") if win else L("大会に負けた…", "MATCH LOST..."), 10 if win else 8)
        self.score_line(80)
        if win and self.match + 1 < MATCHES:
            txt_c(100, L("賞品のパーツを1つ選べる", "CHOOSE A PART"), 7)
        if self.frame // 20 % 2 == 0:
            txt_c(150, L("Zで つぎへ", "PRESS Z"), 7)

    def d_reward(self):
        txt_c(14, L("賞品のパーツを1つえらぶ", "CHOOSE ONE PART"), 10)
        txt_c(28, L("チーム全員のベゴマに付く", "APPLIES TO WHOLE TEAM"), 13)
        for i, r in enumerate(self.offer):
            y = 50 + i * 34
            sel = i == self.cursor
            pyxel.rectb(28, y, 200, 28, 10 if sel else 5)
            if sel:
                pyxel.rect(29, y + 1, 198, 26, 1)
            txt(36, y + 4, L(r[1], r[2]), 10 if sel else 7)
            txt(36, y + 16, L(r[3], r[4]), 6 if sel else 13)

    def d_over(self):
        txt_c(70, L("挑戦おわり", "RUN OVER"), 8)
        txt_c(90, L("大会 %d で敗退" % (self.match + 1), "LOST AT MATCH %d" % (self.match + 1)), 7)
        if self.frame // 20 % 2 == 0:
            txt_c(150, L("Zで タイトルへ", "PRESS Z"), 7)

    def d_clear(self):
        txt_c(60, L("優勝！", "CHAMPION!"), 10)
        txt_c(80, L("全大会を勝ち抜いた", "ALL MATCHES CLEARED"), 7)
        for i, d in enumerate(self.team):
            draw_top(d, 64 + i * 64, 116, 10, self.frame * 0.2)
        if self.frame // 20 % 2 == 0:
            txt_c(150, L("Zで タイトルへ", "PRESS Z"), 7)

    def draw_bowl(self):
        pyxel.circ(CX, CY, R + 4, 13)
        pyxel.circ(CX, CY, R, 5)
        pyxel.circ(CX, CY, int(R * 0.68), 1)
        pyxel.circb(CX, CY, int(R * 0.36), 5)
        pyxel.circb(CX, CY, R, 6)


# ---------------------------------------------------------------- 絵（コードで描く）
def draw_top(d, x, y, r, spin, flash=False):
    col, sub = (7, 7) if flash else (d["col"], d["sub"])
    pyxel.circ(x + 2, y + 3, r, 0)                  # 影
    pyxel.circ(x, y, r, sub)                        # 胴
    for k in range(3):                              # 回る羽根
        a = spin + k * math.tau / 3
        pyxel.line(x, y, x + math.cos(a) * r, y + math.sin(a) * r, col)
    pyxel.circb(x, y, r, 0)
    br = max(2, int(r * 0.55))                      # 上に乗るモンスター
    pyxel.circ(x, y - 2, br, col)
    pyxel.circb(x, y - 2, br, 0)
    if r >= 5:
        pyxel.pset(x - 2, y - 3, 7)
        pyxel.pset(x + 1, y - 3, 7)
        pyxel.pset(x - 2, y - 2, 0)
        pyxel.pset(x + 1, y - 2, 0)


def draw_fighter(f, frame, is_player):
    draw_top(f.d, f.x, f.y, f.r, f.spin, flash=f.flash > 0 and f.flash % 4 < 2)
    # 自分のコマには足元の目印
    pyxel.tri(f.x, f.y - f.r - 9, f.x - 3, f.y - f.r - 13, f.x + 3, f.y - f.r - 13, 11 if is_player else 8)
    if f.gauge >= 100:                              # 必殺を撃てる合図（相手も見える＝予告）
        pyxel.circb(f.x, f.y, f.r + 2 + (frame // 4) % 2, 10)
    if f.braking:
        pyxel.circb(f.x, f.y, f.r + 1, 6)


# ---------------------------------------------------------------- 起動
def main():
    pyxel.init(W, H, title="BEGOMA ROGUE v" + VERSION, fps=FPS, display_scale=3)
    load_font()
    setup_sounds()
    game = Game()
    pyxel.run(game.update, game.draw)


if __name__ == "__main__":
    main()
