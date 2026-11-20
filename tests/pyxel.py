# テスト用の偽Pyxel（描画は呼ばれた回数だけ数える）
import itertools
_names = ["KEY_LEFT","KEY_RIGHT","KEY_UP","KEY_DOWN","KEY_A","KEY_D","KEY_W","KEY_S","KEY_Z","KEY_X",
 "KEY_SPACE","KEY_RETURN","KEY_LSHIFT","GAMEPAD1_BUTTON_DPAD_LEFT","GAMEPAD1_BUTTON_DPAD_RIGHT",
 "GAMEPAD1_BUTTON_DPAD_UP","GAMEPAD1_BUTTON_DPAD_DOWN","GAMEPAD1_BUTTON_A","GAMEPAD1_BUTTON_B"]
for i,n in enumerate(_names): globals()[n]=i+1
held=set(); pressed=set(); calls={}
def btn(k): return k in held
def btnp(k): return k in pressed
class _S:
    def set(self, notes, tones, vols, effs, speed):
        assert isinstance(speed,int) and notes and tones and vols and effs
sounds=[_S() for _ in range(64)]
def _rec(name):
    def f(*a, **k):
        calls[name]=calls.get(name,0)+1
        for v in a:
            if isinstance(v,float) and v!=v: raise ValueError("NaN passed to "+name)
    return f
for n in ["cls","circ","circb","line","rect","rectb","pset","tri","text","camera","play","init","run"]:
    globals()[n]=_rec(n)
class Font:
    def __init__(self,p): raise FileNotFoundError(p)
