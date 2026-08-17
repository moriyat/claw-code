import csv,io,json,math,statistics,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,timezone
import pandas as pd

URL='https://raw.githubusercontent.com/simom1/XAUUSD-history/main/Forex-Majors/USDJPY/USDJPY_M5.csv'
JST=timezone(timedelta(hours=9)); COSTS=[.2,.5,1.0]; START=1_000_000.; HOLD=72
# Frozen V1 parameters
FAST,SLOW,ATR_N,SLOPE_N=20,50,14,5
SLOPE_T=.08; RANGE_ER=.33; RANGE_CON=.92; PB_ATR=.45; STOP_BUF=.10; BO_BUF=.08; LVL_ATR=.35; MIN_R=1.5

def ema(x,n):
    a=2/(n+1); o=[x[0]]
    for v in x[1:]:o.append(a*v+(1-a)*o[-1])
    return o

def atr(x,n=14):
    if not x:return 0
    tr=[x[0][2]-x[0][3]]
    for p,c in zip(x,x[1:]):tr.append(max(c[2]-c[3],abs(c[2]-p[4]),abs(c[3]-p[4])))
    z=tr[-n:];return sum(z)/len(z)

def er(x,n=20):
    z=x[-n:]
    if len(z)<2:return 0
    path=sum(abs(b[4]-a[4]) for a,b in zip(z,z[1:]));return abs(z[-1][4]-z[0][4])/path if path else 0

def tdir(x):
    if len(x)<SLOW+SLOPE_N:return('N',0)
    cl=[b[4] for b in x]; f=ema(cl,FAST); s=ema(cl,SLOW); a=atr(x)
    if not a:return('N',0)
    sl=(f[-1]-f[-1-SLOPE_N])/a; p=cl[-1]
    if p>f[-1]>s[-1] and sl>SLOPE_T:return('L',sl)
    if p<f[-1]<s[-1] and sl<-SLOPE_T:return('S',-sl)
    return('N',abs(sl))

def regime(h1,m15):
    hd,hs=tdir(h1); md,ms=tdir(m15)
    if hd!='N' and hd==md:return('TREND',hd,hs,ms)
    e=er(m15); an=atr(m15[-20:]); ap=atr(m15[-40:-20]) if len(m15)>=40 else an; con=an/ap if ap else 1
    if e<=RANGE_ER and con<=RANGE_CON:return('RANGE','N',e,con)
    return('TRANSITION','N',e,con)

def trig(m5,d):
    a,b,c=m5[-3:]; rng=max(c[2]-c[3],1e-9); body=abs(c[4]-c[1]); lw=min(c[1],c[4])-c[3]; uw=c[2]-max(c[1],c[4])
    if d=='L':
        rec=c[4]>b[2]; hl=c[3]>min(a[3],b[3]); rej=c[4]>c[1] and lw/rng>=.35 and body/rng>=.25
        return 2 if rec and hl else (1 if rec or rej else 0)
    rec=c[4]<b[3]; lh=c[2]<max(a[2],b[2]); rej=c[4]<c[1] and uw/rng>=.35 and body/rng>=.25
    return 2 if rec and lh else (1 if rec or rej else 0)

def near_score(levels,p,a,d):
    z=(levels['sup']+levels['liq']) if d=='L' else (levels['res']+levels['liq'])
    if not z or not a:return 0
    q=min(abs(p-v) for v in z)/a
    return 2 if q<=LVL_ATR else (1 if q<=2*LVL_ATR else 0)

def target(levels,p,stop,d):
    z=(levels['res']+levels['liq']) if d=='L' else (levels['sup']+levels['liq'])
    z=sorted((v for v in z if (v>p if d=='L' else v<p)),reverse=(d=='S'))
    return z[0] if z else p+(2*abs(p-stop) if d=='L' else -2*abs(p-stop))

def cand(m5,m15,h1,levels,cost):
    rg,bias,*_=regime(h1,m15); out=[]; p=m5[-1][4]; a15=atr(m15); a5=atr(m5)
    if rg=='TREND' and bias!='N':
        cl=[b[4] for b in m15]; f=ema(cl,FAST)[-1]; s=ema(cl,SLOW)[-1]; anc=f if abs(p-f)<=abs(p-s) else s
        if a15 and abs(p-anc)/a15<=PB_ATR:
            d=bias; st=(min(x[3] for x in m5[-6:])-STOP_BUF*a5) if d=='L' else (max(x[2] for x in m5[-6:])+STOP_BUF*a5)
            out.append(mkc('TREND_PULLBACK_CONTINUATION',d,p,st,levels,cost,2,near_score(levels,p,a15,d),2,trig(m5,d)))
    if len(m15)>=25:
        prior=m15[-21:-1]; lo=min(x[3] for x in prior); hi=max(x[2] for x in prior); last=m15[-1]
        if last[4]>hi+BO_BUF*a15 and min(x[3] for x in m5[-4:])<=hi+.25*a15 and p>hi:
            st=min(x[3] for x in m5[-6:])-STOP_BUF*a5; out.append(mkc('BREAKOUT_ACCEPTANCE_RETEST','L',p,st,levels,cost,2,2,2 if rg in ('RANGE','TRANSITION') else 1,trig(m5,'L')))
        elif last[4]<lo-BO_BUF*a15 and max(x[2] for x in m5[-4:])>=lo-.25*a15 and p<lo:
            st=max(x[2] for x in m5[-6:])+STOP_BUF*a5; out.append(mkc('BREAKOUT_ACCEPTANCE_RETEST','S',p,st,levels,cost,2,2,2 if rg in ('RANGE','TRANSITION') else 1,trig(m5,'S')))
        if rg!='TREND':
            if last[2]>hi+BO_BUF*a15 and last[4]<hi:
                st=max(last[2],max(x[2] for x in m5[-6:]))+STOP_BUF*a5; out.append(mkc('FAILED_BREAKOUT_REVERSAL','S',p,st,levels,cost,0,2,2 if rg=='RANGE' else 1,trig(m5,'S')))
            elif last[3]<lo-BO_BUF*a15 and last[4]>lo:
                st=min(last[3],min(x[3] for x in m5[-6:]))-STOP_BUF*a5; out.append(mkc('FAILED_BREAKOUT_REVERSAL','L',p,st,levels,cost,0,2,2 if rg=='RANGE' else 1,trig(m5,'L')))
    return sorted((x for x in out if x),key=lambda x:(x['score'],x['netr']),reverse=True),rg

def mkc(setup,d,p,st,levels,cost,htf,loc,reg,tr):
    if abs(p-st)<1e-9:return None
    tg=target(levels,p,st,d); risk=abs(p-st)/.01; rew=abs(tg-p)/.01; net=max(0,rew-cost)/(risk+cost); rw=2 if net>=2 else (1 if net>=MIN_R else 0)
    sc=htf+loc+reg+tr+rw; grade='A+' if sc>=9 else ('A' if sc==8 else ('B' if sc==7 else 'X'))
    return {'setup':setup,'d':d,'entry':p,'stop':st,'target':tg,'netr':net,'tr':tr,'score':sc,'grade':grade}

def session(ts):
    h=ts.astimezone(JST).hour
    return 'TOKYO' if 7<=h<15 else ('LONDON' if 15<=h<21 else ('NEW_YORK' if h>=21 or h<6 else 'OFF_HOURS'))

def metrics(tr):
    if not tr:return {'n':0,'expR':0,'PF':0,'win%':0,'totalR':0,'maxDDR':0,'ret%':0}
    r=[x['r'] for x in tr]; gp=sum(x for x in r if x>0); gl=-sum(x for x in r if x<0); cum=peak=0; dd=0
    for x in r:cum+=x;peak=max(peak,cum);dd=min(dd,cum-peak)
    return {'n':len(r),'expR':round(sum(r)/len(r),4),'PF':round(gp/gl,3) if gl else 999,'win%':round(100*sum(x>0 for x in r)/len(r),2),'totalR':round(sum(r),2),'maxDDR':round(dd,2),'ret%':round(100*(tr[-1]['eq']/START-1),2)}

def run(df,cost):
    m5=[(t.to_pydatetime().replace(tzinfo=timezone.utc),r.open,r.high,r.low,r.close) for t,r in df.iterrows()]
    d15=df.resample('15min',label='left',closed='left').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna(); d60=df.resample('60min',label='left',closed='left').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
    a15=[(t.to_pydatetime().replace(tzinfo=timezone.utc),r.open,r.high,r.low,r.close) for t,r in d15.iterrows()]; a60=[(t.to_pydatetime().replace(tzinfo=timezone.utc),r.open,r.high,r.low,r.close) for t,r in d60.iterrows()]
    ends15=[x[0]+timedelta(minutes=15) for x in a15]; ends60=[x[0]+timedelta(hours=1) for x in a60]
    tmp=df.copy(); tmp['jday']=[t.to_pydatetime().replace(tzinfo=timezone.utc).astimezone(JST).date() for t in tmp.index]; daily=tmp.groupby('jday').agg({'high':'max','low':'min'}); days=list(daily.index)
    import bisect
    eq=START; tr=[]; i=0; day=week=None; deq=weq=eq; stops=cons=0
    while i<len(m5)-2:
        b=m5[i]; close=b[0]+timedelta(minutes=5); ld=close.astimezone(JST).date(); lw=close.astimezone(JST).isocalendar()[:2]
        if ld!=day:day=ld;deq=eq;stops=cons=0
        if lw!=week:week=lw;weq=eq
        if (eq/deq-1)*100<=-1 or (eq/weq-1)*100<=-2.5 or stops>=3 or cons>=2:i+=1;continue
        j15=bisect.bisect_right(ends15,close);j60=bisect.bisect_right(ends60,close)
        if j15<55 or j60<55 or i<30:i+=1;continue
        x15=a15[max(0,j15-240):j15]; x60=a60[max(0,j60-180):j60]; x5=m5[max(0,i-239):i+1]
        pi=bisect.bisect_left(days,ld)-1; hs=[];ls=[]
        if pi>=0:hs.append(float(daily.loc[days[pi],'high']));ls.append(float(daily.loc[days[pi],'low']))
        rr=x15[-48:];hs.append(max(x[2] for x in rr));ls.append(min(x[3] for x in rr)); levels={'sup':ls,'res':hs,'liq':hs+ls}
        cs,rg=cand(x5,x15,x60,levels,cost)
        if not cs:i+=1;continue
        c=cs[0]
        if c['score']<7 or c['tr']==0 or c['netr']<MIN_R:i+=1;continue
        eidx=i+1; ep=m5[eidx][1]; risk=abs(ep-c['stop'])/.01; rew=((c['target']-ep)/.01 if c['d']=='L' else (ep-c['target'])/.01)
        if risk<=0 or rew<=0 or max(0,rew-cost)/(risk+cost)<MIN_R:i+=1;continue
        jmax=min(len(m5)-1,eidx+HOLD-1); ex=None
        for j in range(eidx,jmax+1):
            z=m5[j]; sh=z[3]<=c['stop'] if c['d']=='L' else z[2]>=c['stop']; th=z[2]>=c['target'] if c['d']=='L' else z[3]<=c['target']
            if sh:ex=(j,c['stop'],'STOP');break
            if th:ex=(j,c['target'],'TARGET');break
        if not ex:ex=(jmax,m5[jmax][4],'TIME')
        j,xp,why=ex; raw=((xp-ep)/.01 if c['d']=='L' else (ep-xp)/.01); R=(raw-cost)/(risk+cost); rp={'A+':.5,'A':.35,'B':.2}[c['grade']]; eq*=1+rp/100*R
        if why=='STOP' and R<=-.95:stops+=1;cons+=1
        else:cons=0
        tr.append({'ts':m5[eidx][0].isoformat(),'setup':c['setup'],'session':session(m5[eidx][0]),'grade':c['grade'],'regime':rg,'r':R,'eq':eq,'why':why})
        i=j+1
    return tr

def main():
    raw=pd.read_csv(URL,parse_dates=['time']); raw=raw.set_index('time').sort_index(); raw=raw[~raw.index.duplicated(keep='last')]
    start,end=raw.index.min().date(),raw.index.max().date(); span=(end-start).days; d1=start+timedelta(days=span//2);d2=start+timedelta(days=3*span//4)
    out={'source':URL,'rows':len(raw),'start':str(raw.index.min()),'end':str(raw.index.max()),'split':[str(d1),str(d2)],'scenarios':{}}
    for cost in COSTS:
        tr=run(raw,cost); parts={'IS':[],'VAL':[],'OOS':[]}
        for x in tr:
            d=datetime.fromisoformat(x['ts']).date(); parts['IS' if d<d1 else ('VAL' if d<d2 else 'OOS')].append(x)
        bys=defaultdict(list);byse=defaultdict(list);byg=defaultdict(list)
        for x in tr:bys[x['setup']].append(x);byse[x['session']].append(x);byg[x['grade']].append(x)
        out['scenarios'][str(cost)]={'all':metrics(tr),'split':{k:metrics(v) for k,v in parts.items()},'setup':{k:metrics(v) for k,v in bys.items()},'session':{k:metrics(v) for k,v in byse.items()},'grade':{k:metrics(v) for k,v in byg.items()}}
    print('FXW_RESULT='+json.dumps(out,separators=(',',':')))
    open('backtest_results.json','w').write(json.dumps(out,indent=2))
main()
