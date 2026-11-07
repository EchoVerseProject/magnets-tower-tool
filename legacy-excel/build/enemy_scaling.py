"""Enemy wave scaling: Python port of TheTowerSDK src/mechanics/waves/base-empirical-scaling.ts
(MIT, (c) 2026 TmRxJD). Constants from scaling-regression-profile.ts.

Only per-wave *growth rates* are exported to the workbook: the optimizer converts a
% gain in damage or effective HP into extra waves via  waves = ln(1+gain) / growth_rate.
"""
import math
TP=[0,1,20,60,120,240,480,960,1920,5760,40320,2620800,1572480000,786239979520,235870007328768,7.076199997322035e+16,3.538100050200625e+18,1.0614000038903074e+20,2.653599994915152e+21,3.449599940780421e+24,4.139599895572065e+27,4.9675000690814487e+30,5.961000082897738e+33,7.153200099477286e+36,8.583840119372743e+39]
ATT=[0]*10+[2.299999952316284,11.5,115,5750,287500,14375000,86250000,431249984,2156250112,10781249536,53906251776,269531250688,1.34765625344e12,6.7382812672e12,3.3691406336e13]
HPB=dict(a=0.4650000035762787,b=5.840000152587891,c=1.5,baseExp=2.130000114440918,tournamentBaseExp=2.308000087738037,aNT=0.05000000074505806,bNT=0.800000011920929,tbeNoLeague=2.4079999923706055,add=[0.009999999776482582,0.019999999552965164,0.10000000149011612,0.2199999988079071,0.36000001430511475],cap=0.5099999904632568)
HP_POW=[(1.034999966621399,30),(1.0199999809265137,60),(1.024999976158142,72),(1.0299999713897705,83),(1.0299999713897705,94),(1.0199999809265137,100),(1.0199999809265137,107),(1.0299999713897705,200),(1.059999942779541,400),(1.149999976158142,900),(1.149999976158142,'shift10'),(1.1100000143051147,139),(1.1100000143051147,182),(1.1299999952316284,241),(1.1299999952316284,332)]
HP_ERAS=[(0.03999999910593033,5),(0.05000000074505806,10),(0.05999999865889549,25),(0.07999999821186066,50),(0.10000000149011612,60),(0.11999999731779099,100),(0.15000000596046448,200),(0.3499999940395355,900),(0.18000000715255737,72),(0.20000000298023224,83),(0.20999999344348907,94),(0.10000000149011612,107)]
HP_TPB=1.003999948501587; HP_W100=1.649999976158142
DB=dict(a=0.19529999792575836,b=1.1679999828338623,c=1.07,baseExp=2.006999969482422,tournamentBaseExp=2.375,aNT=0.020999999716877937,bNT=0.1599999964237213,tbeNoLeague=2.3550000190734863,add=[0.0020000000949949026,0.004000000189989805,0.019999999552965164,0.04600000008940697,0.0729999989271164],cap=0.10199999809265137)
D_POLY=[(0.019999999552965164,900),(0.02500000037252903,200),(0.019999999552965164,100),(0.017000000923871994,50),(0.012000000104308128,25),(0.019999999552965164,5),(0.02500000037252903,10)]
D_POW=[(1.0049999952316284,30),(1.0099999904632568,72),(1.0099999904632568,83),(1.0099999904632568,94),(1.0099999904632568,'cross'),(1.0199999809265137,200),(1.0199999809265137,400),(1.034999966621399,900),(1.0499999523162842,'shift10')]
D_GT6=[(1.024999976158142,139,None),(1.024999976158142,182,7)]
D_LATE=[(1.0299999713897705,241),(1.0299999713897705,332)]
D_W100=1.059999942779541; TS=0.8600000143051147; TCAP=269531250688; LT4=0.9399999976158142; LT7=0.8999999761581421
def mb(w,d): return max(1,int(w))//d
def cross(w):
    w=max(1,int(w)); r=(w*842937507)//(2**32); return (r+((w-r)>>1))>>6
def shift10(w): return (max(1,int(w))>>10)&0x3fffff
def logpow(w,chain):
    s=0.0
    for base,d in chain:
        e = cross(w) if d=='cross' else shift10(w) if d=='shift10' else mb(w,d)
        if e>0: s+=e*math.log(base)
    return s
def addon(t,tab,cap):
    if t<=9: return 0
    if t<=14: return tab[t-10]
    return cap
def lnHP(w,t,tour):
    w=max(1,int(w)); env=1+sum(c*mb(w,d) for c,d in HP_ERAS)
    a,b=(HPB['a'],HPB['b']) if tour else (HPB['aNT'],HPB['bNT'])
    exp=(HPB['tbeNoLeague'] if tour else HPB['baseExp'])+addon(t,HPB['add'],HPB['cap'])  # tour: league tournament, testMode=true per SDK resolve
    lin=w**exp*a+b*w+HPB['c']
    v=math.log(env)+logpow(w,HP_POW)+math.log(lin)
    if tour:
        n=0; th=100
        while th<w: n+=1; th+=100
        v+=n*math.log(HP_W100)+w*math.log(HP_TPB)
    return v+math.log(TP[t])
def lnDMG(w,t,tour):
    w=max(1,int(w)); env=1+sum(c*mb(w,d) for c,d in D_POLY)
    v=math.log(env)+logpow(w,D_POW)
    if t>6:
        for base,d,skip in D_GT6:
            if skip is not None and t==skip: continue
            e=mb(w,d)
            if e>0: v+=e*math.log(base)
    v+=logpow(w,D_LATE)
    a,b=(DB['a'],DB['b']) if tour else (DB['aNT'],DB['bNT'])
    exp=(DB['tournamentBaseExp'] if tour else DB['baseExp'])+addon(t,DB['add'],DB['cap'])
    v+=math.log(w**exp*a+b*w+DB['c'])
    if tour:
        n=0; th=100
        while th<w: n+=1; th+=100
        v+=n*math.log(D_W100)
    return v
def rate(f,w,t,tour,h=25):
    lo=max(1,w-h); hi=w+h
    return (f(hi,t,tour)-f(lo,t,tour))/(hi-lo)


WAVES = list(range(50, 20001, 50))


def growth_table():
    out = {"waves": WAVES, "hp": {}, "dmg": {}}
    for t in range(1, 25):
        out["hp"][t] = [rate(lnHP, w, t, False) for w in WAVES]
        out["dmg"][t] = [rate(lnDMG, w, t, False) for w in WAVES]
    out["hp_tour"] = [rate(lnHP, w, 1, True) for w in WAVES]
    out["dmg_tour"] = [rate(lnDMG, w, 1, True) for w in WAVES]
    return out


def anchor_check():
    """In-game anchors recorded by the SDK tests (Tier 10)."""
    hp = math.exp(lnHP(8, 10, False))
    dmg = math.exp(lnDMG(10, 10, False)) * TP[10] * TS / ATT[10]
    return {"hp_w8_t10": hp, "hp_expected": [510798, 510800],
            "dmg_w10_t10": dmg, "dmg_expected": [77290, 77295],
            "pass": 510798 <= math.floor(hp) <= 510800 and 77290 <= math.floor(dmg) <= 77295}
