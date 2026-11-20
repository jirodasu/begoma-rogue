import sys, random, statistics, math
import os; _h=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, _h); sys.path.insert(1, os.path.dirname(_h))
import pyxel, begoma_rogue as g

def ai_input(ai, me, foe, b):
    return ai.think(me, foe, b)

def sim(pdef, edef, lvl_p=0.75, lvl_e=0.75, seed=0, pm=None, em=None):
    rng = random.Random(seed)
    b = g.Battle(pdef, edef, pm or g.Mods(), em or g.Mods(), lvl_e, rng)
    pai = g.AI(lvl_p, random.Random(seed+999))
    n=0
    while not b.done():
        b.step(pai.think(b.p, b.e, b) if b.state=="fight" else None)
        for f in (b.p,b.e):
            assert all(map(math.isfinite,(f.x,f.y,f.vx,f.vy,f.hp,f.gauge)))
            assert math.hypot(f.x-g.CX,f.y-g.CY) <= g.R - f.r + 0.01
        n+=1; assert n < 60*60
    return b

# 1) 同じレベルのAI同士で総当たり：決着の仕方・長さ・勝率の偏り
rows=[]; ko=0; tot=0; lens=[]
wins={d["en"]:0 for d in g.ROSTER}; games={d["en"]:0 for d in g.ROSTER}
for i,a in enumerate(g.ROSTER):
    for j,b_ in enumerate(g.ROSTER):
        for s in range(10):
            b=sim(a,b_,seed=i*100+j*10+s)
            tot+=1; ko+= b.reason=="ko"; lens.append(b.t/60)
            w = a if b.winner=="p" else b_
            wins[w["en"]]+=1; games[a["en"]]+=1; games[b_["en"]]+=1
print("KO率 %.0f%%  1戦の長さ 平均%.1f秒 中央%.1f秒 最短%.1f 最長%.1f" % (100*ko/tot, statistics.mean(lens), statistics.median(lens), min(lens), max(lens)))
for k in wins: print("  %-8s 勝率 %.0f%%" % (k, 100*wins[k]/games[k]))

# 2) 上手なプレイヤー役(0.95) vs 各大会の敵
for m in range(3):
    w=0
    for s in range(60):
        r=random.Random(s); a,b_=r.choice(g.ROSTER), r.choice(g.ROSTER)
        b=sim(a,b_,lvl_p=0.95,lvl_e=g.AI_LEVEL[m],seed=s,em=g.Mods(g.ENEMY_EFFECTS[m]))
        w+= b.winner=="p"
    print("上手な役 vs 大会%d の敵: 勝率 %.0f%%" % (m+1, 100*w/60))

# 3) 画面の流れを通しで（タイトル→3大会→優勝/敗退）、必殺ボタンを押し続ける操作
def run_flow(seed, strategy):
    game=g.Game(seed=seed); steps=0; seen=set(); fired=0
    pai=g.AI(0.95, random.Random(seed))
    orig=g.read_battle_input
    def scripted():
        b=game.battle; inp=pai.think(b.p,b.e,b) if strategy=="ai" else dict(dx=1,dy=0,brake=False,atk=True,mag=1)
        return inp
    g.read_battle_input=scripted
    try:
        while steps < 60*60*30:
            pyxel.pressed.clear()
            if game.state!="battle" and steps%3==0: pyxel.pressed.add(pyxel.KEY_Z)
            if game.state in("pick","reward") and steps%7==0: pyxel.pressed.add(pyxel.KEY_DOWN)
            game.update(); game.draw(); seen.add(game.state); steps+=1
            if game.state in ("over","clear") and len(seen)>3:
                return game.state, seen, steps
    finally:
        g.read_battle_input=orig
    raise AssertionError("終わらない")
results=[]
for s in range(12):
    st,seen,steps=run_flow(s, "ai" if s%2 else "mash")
    results.append(st)
print("通しプレイ12回:", {k:results.count(k) for k in set(results)})
print("通った画面:", sorted(seen))
print("描画呼び出し:", {k:v for k,v in pyxel.calls.items() if k in("text","circ","play")})

# 4) 必ず勝つ設定で、報酬の画面→次の大会→優勝まで通るか
game=g.Game(seed=5); seen=[]; steps=0
orig=g.read_battle_input
g.read_battle_input=lambda: dict(dx=0,dy=0,brake=False,atk=False,mag=1)
while game.state!="clear" and steps<60*60*20:
    pyxel.pressed.clear()
    if game.state=="battle" and game.battle.state=="fight": game.battle.e.hp=0
    if game.state!="battle" and steps%3==0: pyxel.pressed.add(pyxel.KEY_Z)
    if game.state=="reward" and steps%5==0: pyxel.pressed.add(pyxel.KEY_DOWN)
    game.update(); game.draw()
    if not seen or seen[-1]!=game.state: seen.append(game.state)
    steps+=1
g.read_battle_input=orig
assert game.state=="clear", seen
assert len(game.relics)==2, game.relics
print("優勝ルートOK  画面の順:", " > ".join(seen[:12]), "...")
print("付いたパーツ:", [r[1] for r in game.relics], " 補正:", vars(game.pmods()))
