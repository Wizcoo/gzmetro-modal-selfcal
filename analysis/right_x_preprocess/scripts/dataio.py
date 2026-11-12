from common import *

def load(p):
 with p.open('rb') as f:
  def u():return struct.unpack('<I',f.read(4))[0]
  def s():return f.read(u()).decode()
  n=u();names=[s() for _ in range(n)];nm=u();methods=[s() for _ in range(nm)];nd=u();fields=[s() for _ in range(nd)];nf=u();offset=f.tell()
 inner=np.dtype([('pre','<f8',(n,)),('cal','<f8',(n,)),('diag','<f8',(nd,))]);dt=np.dtype([('ts','<i8'),('raw','<f8',(n,)),('yinput','<f8',(n,)),('field','<f8',(n,)),('youtput','<f8',(n,)),('methods',inner,(nm,))]);assert p.stat().st_size==offset+nf*dt.itemsize,(p,p.stat().st_size,offset+nf*dt.itemsize)
 return names,methods,fields,np.memmap(p,dtype=dt,mode='r',offset=offset,shape=(nf,))

def windows(t,stage):
 out=[]
 for day in pd.date_range('2026-11-05','2026-11-12'):
  date=day.strftime('%Y-%m-%d');ns=epoch(date+' 23:20');ne=ns+460*60000;ds=epoch(date+' 07:20');de=epoch(date+' 22:00')
  for phase,st,en in [('night',ns,ne),('day',ds,de)]:
   if t[0]>=en or t[-1]<st:continue
   if stage=='old' and day>=pd.Timestamp('2026-11-07') and phase=='night':continue
   out.append((date,phase,st,en))
 return out
