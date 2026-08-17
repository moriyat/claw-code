from pathlib import Path
p=Path('fxw_backtest_v1.py')
s=p.read_text()
s=s.replace("raw=pd.read_csv(URL,parse_dates=['time']); raw=raw.set_index('time').sort_index()", "raw=pd.read_csv(URL); raw['time']=pd.to_datetime(raw['time']); raw=raw.set_index('time').sort_index()")
p.write_text(s)
