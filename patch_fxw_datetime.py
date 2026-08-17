from pathlib import Path
p=Path('fxw_backtest_v1.py')
s=p.read_text()
s=s.replace("raw=pd.read_csv(URL,parse_dates=['time']); raw=raw.set_index('time').sort_index()", "raw=pd.read_csv(URL); raw['time']=pd.to_datetime(raw['time'], format='mixed'); raw=raw.set_index('time').sort_index()")
old="out['scenarios'][str(cost)]={'all':metrics(tr),'split':{k:metrics(v) for k,v in parts.items()},'setup':{k:metrics(v) for k,v in bys.items()},'session':{k:metrics(v) for k,v in byse.items()},'grade':{k:metrics(v) for k,v in byg.items()}}"
new="""split_setup={}; split_session={}; split_grade={}
        for pn,pv in parts.items():
            ss=defaultdict(list); se=defaultdict(list); sg=defaultdict(list)
            for x in pv:
                ss[x['setup']].append(x); se[x['session']].append(x); sg[x['grade']].append(x)
            split_setup[pn]={k:metrics(v) for k,v in ss.items()}
            split_session[pn]={k:metrics(v) for k,v in se.items()}
            split_grade[pn]={k:metrics(v) for k,v in sg.items()}
        out['scenarios'][str(cost)]={'all':metrics(tr),'split':{k:metrics(v) for k,v in parts.items()},'setup':{k:metrics(v) for k,v in bys.items()},'session':{k:metrics(v) for k,v in byse.items()},'grade':{k:metrics(v) for k,v in byg.items()},'split_setup':split_setup,'split_session':split_session,'split_grade':split_grade}"""
s=s.replace(old,new)
p.write_text(s)
