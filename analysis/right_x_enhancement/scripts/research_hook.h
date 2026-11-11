#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>
#include <numeric>
#include <map>
namespace rx {
using Vec=std::vector<double>;
inline double med(Vec v){if(v.empty())return NAN;std::sort(v.begin(),v.end());return (v.size()%2)?v[v.size()/2]:.5*(v[v.size()/2]+v[v.size()/2-1]);}
inline bool solve(Vec G,Vec r,int k,Vec& x){double scale=0;for(int i=0;i<k;i++)scale=std::max(scale,std::abs(G[i*k+i]));for(int c=0;c<k;c++){int piv=c;for(int j=c+1;j<k;j++)if(std::abs(G[j*k+c])>std::abs(G[piv*k+c]))piv=j;if(std::abs(G[piv*k+c])<1e-10*std::max(scale,1e-20))return false;for(int j=0;j<k;j++)std::swap(G[piv*k+j],G[c*k+j]);std::swap(r[piv],r[c]);double d=G[c*k+c];for(int j=c;j<k;j++)G[c*k+j]/=d;r[c]/=d;for(int i=0;i<k;i++)if(i!=c){double a=G[i*k+c];for(int j=c;j<k;j++)G[i*k+j]-=a*G[c*k+j];r[i]-=a*r[c];}}x=r;return true;}
inline bool inverse(const Vec& g,int k,Vec& inv){inv.assign(k*k,0);for(int j=0;j<k;j++){Vec r(k,0),x;r[j]=1;if(!solve(g,r,k,x))return false;for(int i=0;i<k;i++)inv[i*k+j]=x[i];}return true;}
inline double dot(const double* a,const Vec& b,int k){double v=0;for(int j=0;j<k;j++)v+=a[j]*b[j];return v;}
inline bool isref(const std::string& n){return n.rfind("YJ",0)==0;}
inline bool key(const std::string& n){return isref(n)||n.rfind("YXJ",0)==0;}
struct Diag {Vec v0=Vec(3,0),v=Vec(3,0);double neff=0,down=0,maxh=0,refs=0,refreject=0,dv=0,rms0=0,rms1=0,reset=0,bscore=NAN,bcond=NAN;int fallback=0,active=0;};
struct Context {
 std::string mode;std::vector<std::string> names;std::map<int64_t,Vec> coords;int64_t night=-999999,lastts=0;int p=0,k=3;Vec C,R,H,sigma,precision,lev,quality,noise,deltaBar,extraBar,Q;std::vector<int> refs;std::map<int,Vec> looBar;Vec filter,P;bool qualified=false,bqual=false;int bd=0;double bscore=NAN,bcond=NAN;Diag diag;Vec loo,extra;std::vector<Vec> birth;
 explicit Context(std::string m={},std::vector<std::string> n={}):mode(m),names(n){}
 template<class S> Vec gram(const S&s,const std::vector<char>& valid,const Vec* w=nullptr)const{Vec g(k*k,0);for(int i=0;i<p;i++)if(valid[i]&&s.learn[i])for(int a=0;a<k;a++)for(int b=0;b<k;b++)g[a*k+b]+=(w?(*w)[i]:1)*s.A[i*k+a]*s.A[i*k+b];return g;}
 template<class S> void init(S&s){
  night=s.night_id;p=int(s.p);k=s.K();C.assign(p*p,0);Vec N(p*p,0);double nf=0;
  for(const auto& st:s.history){std::map<std::string,int> pos;for(int j=0;j<int(st.names.size());j++)pos[st.names[j]]=j;for(int i=0;i<p;i++)if(pos.count(names[i]))for(int j=0;j<p;j++)if(pos.count(names[j])){int a=pos[names[i]],b=pos[names[j]],q=int(st.names.size());C[i*p+j]+=st.S[a*q+b];N[i*p+j]+=st.N[a*q+b];}nf+=st.n_frames;}
  for(int i=0;i<p*p;i++)C[i]=N[i]>1?C[i]/N[i]:0;
  std::vector<char> mask=s.learn;Vec G=gram(s,mask),I;if(!inverse(G,k,I)){qualified=false;return;}
  H.assign(k*p,0);for(int a=0;a<k;a++)for(int i=0;i<p;i++)if(mask[i])for(int b=0;b<k;b++)H[a*p+i]+=I[a*k+b]*s.A[i*k+b];
  Vec HC(k*p,0),V(k*k,0);for(int a=0;a<k;a++)for(int j=0;j<p;j++)for(int i=0;i<p;i++)HC[a*p+j]+=H[a*p+i]*C[i*p+j];
  for(int a=0;a<k;a++)for(int b=0;b<k;b++)for(int j=0;j<p;j++)V[a*k+b]+=HC[a*p+j]*H[b*p+j];
  R=C;sigma.assign(p,.02);quality.assign(p,0);lev.assign(p,0);precision.assign(p,1);refs.clear();Vec scales;
  for(int i=0;i<p;i++)for(int j=0;j<p;j++)if(s.use[i]&&s.use[j]){for(int a=0;a<k;a++){R[i*p+j]-=s.A[i*k+a]*HC[a*p+j]+s.A[j*k+a]*HC[a*p+i];for(int b=0;b<k;b++)R[i*p+j]+=s.A[i*k+a]*V[a*k+b]*s.A[j*k+b];}}
  for(int i=0;i<p;i++)if(s.use[i]){sigma[i]=std::sqrt(std::max(.0004,R[i*p+i]));quality[i]=C[i*p+i]>1e-8?1-std::max(0.,R[i*p+i])/C[i*p+i]:0;for(int a=0;a<k;a++)for(int b=0;b<k;b++)lev[i]+=s.A[i*k+a]*I[a*k+b]*s.A[i*k+b];if(mask[i])scales.push_back(sigma[i]);if(isref(names[i])&&quality[i]>=.8)refs.push_back(i);}
  double sc=med(scales);if(!std::isfinite(sc))sc=.02;noise.resize(k);for(int a=0;a<k;a++)noise[a]=std::max(1e-6,sc*sc*I[a*k+a]);
  for(int i=0;i<p;i++)precision[i]=std::clamp(sc*sc/(sigma[i]*sigma[i]),.25,4.);
  Vec corr;for(size_t a=0;a<refs.size();a++)for(size_t b=a+1;b<refs.size();b++){int i=refs[a],j=refs[b];corr.push_back(std::abs(C[i*p+j])/std::sqrt(std::max(1e-20,C[i*p+i]*C[j*p+j])));}
  qualified=refs.size()>=3&&!corr.empty()&&med(corr)>=.7;filter.clear();P.clear();lastts=0;deltaBar.assign(k,0);extraBar.assign(p,0);looBar.clear();
  if(mode.rfind("B",0)==0)buildSpatial(s);
  // Re-evaluate cached baseline frames with this night's fixed A. This is
  // available at model birth, never uses a later correction sample.
  int cnt=0;std::map<int,int> lc;for(int j:refs)looBar[j]=Vec(k,0);
  for(const auto& f:s.ref_buf){Vec z(p),v0;std::vector<char> valid(p);for(int i=0;i<p;i++){valid[i]=std::isfinite(f.y[i]-s.b[i]);z[i]=valid[i]?f.y[i]-s.b[i]:0;}if(!s.SolveV(z,valid,&v0,nullptr))continue;Diag tmp;Vec vv=estimate(s,z,valid,v0,-1,tmp);for(int a=0;a<k;a++)deltaBar[a]+=vv[a]-v0[a];if(mode.rfind("B",0)==0){Vec ee=spatial(s,z,valid,v0,-1);for(int i=0;i<p;i++)extraBar[i]+=ee[i];}for(int j:refs){Vec lv=estimate(s,z,valid,v0,j,tmp);for(int a=0;a<k;a++)looBar[j][a]+=lv[a]-v0[a];lc[j]++;}cnt++;}
  if(cnt){for(double&v:deltaBar)v/=cnt;for(double&v:extraBar)v/=cnt;for(auto&kv:looBar)if(lc[kv.first])for(double&v:kv.second)v/=lc[kv.first];}
  for(int i=0;i<p;i++)birth.push_back({double(night),double(i),double(mask[i]),double(s.use[i]),quality[i],sigma[i],lev[i],double(qualified),double(bqual),bscore,bcond,double(s.history.size()),nf,s.A[i*k],s.A[i*k+1],s.A[i*k+2],s.b[i],s.cbar[i]});
 }
 template<class S> Vec estimate(S&s,const Vec&z,const std::vector<char>&valid,const Vec&v0,int exclude,Diag&d){
  if(mode=="identity"||mode.rfind("D",0)==0||mode.rfind("B",0)==0)return v0;
  bool e=mode=="E_Huber"||mode=="E_full"||mode=="EA";bool a=mode=="A"||mode=="EA";
  std::vector<char> active=s.research_active;if(active.size()!=size_t(p))return v0;
  int n=0;for(int i=0;i<p;i++)if(active[i]&&s.learn[i])n++;if(n<std::max(5,k+2)){d.fallback=1;return v0;}
  Vec rr;std::vector<int> refok;if(a&&qualified){for(int j:refs)if(valid[j]&&j!=exclude){double sign=s.A[j*k]>=0?1:-1;rr.push_back(sign*(z[j]-dot(&s.A[j*k],v0,k))/sigma[j]);refok.push_back(j);}if(refok.size()>=2){double center=med(rr);Vec dev;for(double x:rr)dev.push_back(std::abs(x-center));double scale=std::max(1.,1.4826*med(dev));std::vector<int> keep;for(size_t t=0;t<rr.size();t++)if(std::abs(rr[t]-center)<=3*scale)keep.push_back(refok[t]);else d.refreject++;refok=keep;}else refok.clear();}
  if(a&&refok.size()<2){d.fallback=1;return v0;}d.refs=refok.size();
  Vec weights(p,0),cur=v0,G0=gram(s,active);double global=0;Vec sx;for(int i=0;i<p;i++)if(active[i]&&s.learn[i])sx.push_back(sigma[i]);global=med(sx);
  for(int iter=0;iter<5;iter++){
   double sw=0,sw2=0;int down=0;for(int i=0;i<p;i++)if(active[i]&&s.learn[i]){double r=std::abs(z[i]-dot(&s.A[i*k],cur,k));double cut=e?1.345*(mode=="E_Huber"?global:sigma[i]):2.5;double w=r>cut?cut/std::max(r,1e-12):1.;if(mode=="E_full"||mode=="EA"){w*=precision[i];w*=std::min(1.,(2.*k/n)/std::max(1e-12,lev[i]));}w=std::max(.05,w);weights[i]=w;sw+=w;sw2+=w*w;down+=w<.5;}
   d.neff=sw*sw/std::max(sw2,1e-20);d.down=down;d.maxh=0;for(int i=0;i<p;i++)if(active[i]&&s.learn[i])d.maxh=std::max(d.maxh,lev[i]);
   if(d.neff<std::max(5,k+2)){d.fallback=2;return v0;}
   Vec G=gram(s,active,&weights),rhs(k,0);for(int i=0;i<p;i++)if(active[i]&&s.learn[i])for(int j=0;j<k;j++)rhs[j]+=weights[i]*s.A[i*k+j]*z[i];
   if(a){double tr=0,trref=0;for(int j=0;j<k;j++)tr+=G0[j*k+j];for(int i:refok)for(int j=0;j<k;j++)trref+=s.A[i*k+j]*s.A[i*k+j]/(sigma[i]*sigma[i]);double lambda=.25*tr/std::max(1e-12,trref);for(int j=0;j<k;j++){for(int l=0;l<k;l++){G[j*k+l]+=G0[j*k+l];rhs[j]+=G0[j*k+l]*v0[l];}for(int i:refok){double res=std::abs(z[i]-dot(&s.A[i*k],cur,k)),w=lambda/(sigma[i]*sigma[i])*std::min(1.,1.345*sigma[i]/std::max(res,1e-12));rhs[j]+=w*s.A[i*k+j]*z[i];for(int l=0;l<k;l++)G[j*k+l]+=w*s.A[i*k+j]*s.A[i*k+l];}}}
   Vec next;if(!solve(G,rhs,k,next)){d.fallback=3;return v0;}cur=next;
  }
  if(a){double mx=0;Vec diff(k);for(int j=0;j<k;j++)diff[j]=cur[j]-v0[j];for(int i=0;i<p;i++)if(s.use[i])mx=std::max(mx,std::abs(dot(&s.A[i*k],diff,k)));if(mx>.25)for(int j=0;j<k;j++)cur[j]=v0[j]+diff[j]*(.25/mx);}
  d.active=1;return cur;
 }
 template<class S> void buildSpatial(S&s){
  bd=mode=="B0"?1:mode=="B1"?2:3;bqual=false;bscore=NAN;bcond=NAN;if(!coords.count(night)||refs.size()<3)return;Vec uv=coords[night];if(uv.size()!=size_t(2*p))return;for(double v:uv)if(!std::isfinite(v))return;
  Vec g=gram(s,s.learn),inv;if(!inverse(g,k,inv))return;Vec raw(p*bd,0);double umin=1e9,umax=-1e9,vmin=1e9,vmax=-1e9;for(int i:refs){umin=std::min(umin,uv[2*i]);umax=std::max(umax,uv[2*i]);vmin=std::min(vmin,uv[2*i+1]);vmax=std::max(vmax,uv[2*i+1]);}int axis=(vmax-vmin>umax-umin)?1:0;
  for(int i=0;i<p;i++){raw[i*bd]=1;if(bd>=2)raw[i*bd+1]=uv[2*i+axis];if(bd==3)raw[i*bd+2]=uv[2*i+1-axis];}
  // Project out A and previously retained residual columns. A redundant
  // translation must not suppress an independently identifiable gradient.
  std::vector<Vec> retained;int nominal=bd;
  for(int c=0;c<nominal;c++){Vec rhs(k,0),proj,col(p);for(int i=0;i<p;i++)if(s.learn[i])for(int a=0;a<k;a++)rhs[a]+=s.A[i*k+a]*raw[i*nominal+c];if(!solve(g,rhs,k,proj))return;for(int i=0;i<p;i++)col[i]=s.use[i]?raw[i*nominal+c]-dot(&s.A[i*k],proj,k):0;
   for(const Vec&prev:retained){double cross=0;for(int i=0;i<p;i++)if(s.learn[i])cross+=col[i]*prev[i];for(int i=0;i<p;i++)col[i]-=cross*prev[i];}
   double sq=0,orig=0;for(int i=0;i<p;i++)if(s.learn[i]){sq+=col[i]*col[i];orig+=raw[i*nominal+c]*raw[i*nominal+c];}if(sq<.05*std::max(orig,1e-20))continue;for(double&v:col)v/=std::sqrt(sq);retained.push_back(col);
  }
  bd=int(retained.size());if(!bd||refs.size()<size_t(bd+2))return;Q.assign(p*bd,0);for(int i=0;i<p;i++)for(int c=0;c<bd;c++)Q[i*bd+c]=retained[c][i];
  double totalerr=0,totalbase=0,cond=0;
  for(int held:refs){Vec gr(bd*bd,0),iv;for(int j:refs)if(j!=held)for(int a=0;a<bd;a++)for(int b=0;b<bd;b++)gr[a*bd+b]+=Q[j*bd+a]*Q[j*bd+b];if(!inverse(gr,bd,iv))return;double tg=0,ti=0;for(int a=0;a<bd;a++){tg+=gr[a*bd+a];ti+=iv[a*bd+a];}cond=std::max(cond,std::sqrt(tg*ti));if(cond>30)return;Vec coeff(p,0);for(int j:refs)if(j!=held)for(int a=0;a<bd;a++)for(int b=0;b<bd;b++)coeff[j]+=Q[held*bd+a]*iv[a*bd+b]*Q[j*bd+b];double err=R[held*p+held];for(int i:refs)if(i!=held){err-=2*coeff[i]*R[i*p+held];for(int j:refs)if(j!=held)err+=coeff[i]*coeff[j]*R[i*p+j];}totalerr+=std::max(0.,err);totalbase+=std::max(0.,R[held*p+held]);}
  bcond=cond;bscore=totalbase>1e-8?1-totalerr/totalbase:NAN;bqual=std::isfinite(bscore)&&bscore>=.2;
 }
 template<class S> Vec spatial(S&s,const Vec&z,const std::vector<char>&valid,const Vec&v0,int exclude){
  Vec out(p,0);if(!bqual)return out;for(int i=0;i<p;i++)if(s.learn[i]&&!valid[i])return out;std::vector<int> js;for(int i:refs)if(i!=exclude&&valid[i])js.push_back(i);if(js.size()<size_t(bd+2))return out;Vec g(bd*bd,0),rhs(bd,0),coef;for(int i:js){double r=z[i]-dot(&s.A[i*k],v0,k);for(int a=0;a<bd;a++){rhs[a]+=Q[i*bd+a]*r;for(int b=0;b<bd;b++)g[a*bd+b]+=Q[i*bd+a]*Q[i*bd+b];}}if(!solve(g,rhs,bd,coef))return out;double mx=0;for(int i=0;i<p;i++)if(s.use[i]){out[i]=dot(&Q[i*bd],coef,bd);mx=std::max(mx,std::abs(out[i]));}if(mx>.25)for(double&v:out)v*=.25/mx;return out;
 }
 template<class S> void apply(S&s,const Vec&z,const std::vector<char>&valid,Vec&v,Vec&ex,int64_t ts){
  if(night!=s.night_id){auto frame_active=s.research_active;init(s);s.research_active=frame_active;}diag=Diag();diag.v0=v;diag.v=v;diag.bscore=bscore;diag.bcond=bcond;loo.assign(p,NAN);ex.assign(p,0);
  if(mode.rfind("D",0)==0){bool reset=filter.size()!=size_t(k)||ts-lastts>90000;Vec next=v;if(reset){filter=v;P=noise;diag.reset=1;}else for(int a=0;a<k;a++){if(mode=="D_EMA")next[a]=.5*v[a]+.5*filter[a];else{double prior=P[a]+noise[a];double innovation=v[a]-filter[a];if(std::abs(innovation)>3*std::sqrt(prior+noise[a])){next[a]=v[a];P[a]=noise[a];diag.reset=1;}else{double gain=prior/(prior+noise[a]);next[a]=filter[a]+gain*innovation;P[a]=(1-gain)*prior;}}}filter=next;lastts=ts;v=next;diag.active=!reset;}
  else v=estimate(s,z,valid,v,-1,diag);
  if(mode.rfind("B",0)==0){int currentrefs=0;bool alllearn=true;for(int i=0;i<p;i++)if(s.learn[i]&&!valid[i])alllearn=false;for(int i:refs)currentrefs+=bool(valid[i]);bool available=bqual&&currentrefs>=bd+2&&alllearn;ex=spatial(s,z,valid,diag.v0,-1);diag.active=available;diag.fallback=!available;if(available)for(int i=0;i<p;i++)ex[i]-=extraBar[i];}
  else if(diag.active)for(int a=0;a<k;a++)v[a]-=deltaBar[a];
  if(mode=="A"||mode=="EA"){
   auto trust=[&](Vec&vv){Vec delta(k);for(int a=0;a<k;a++)delta[a]=vv[a]-diag.v0[a];double mx=0;for(int i=0;i<p;i++)if(s.use[i])mx=std::max(mx,std::abs(dot(&s.A[i*k],delta,k)));if(mx>.25)for(int a=0;a<k;a++)vv[a]=diag.v0[a]+delta[a]*(.25/mx);};
   trust(v);
   for(int j:refs){Diag tmp;Vec lv=estimate(s,z,valid,diag.v0,j,tmp);if(valid[j]&&tmp.active){for(int a=0;a<k;a++)lv[a]-=looBar[j][a];trust(lv);loo[j]=z[j]-dot(&s.A[j*k],lv,k)+s.cbar[j];}}
  }
  diag.v=v;for(int a=0;a<k;a++)diag.dv+=std::pow(v[a]-diag.v0[a],2);diag.dv=std::sqrt(diag.dv);double n=0;for(int i=0;i<p;i++)if(valid[i]&&s.learn[i]){diag.rms0+=std::pow(z[i]-dot(&s.A[i*k],diag.v0,k),2);diag.rms1+=std::pow(z[i]-dot(&s.A[i*k],v,k),2);n++;}if(n){diag.rms0=std::sqrt(diag.rms0/n);diag.rms1=std::sqrt(diag.rms1/n);}
 }
};
inline thread_local Context* current=nullptr;
inline thread_local bool axis_x=false;
} // namespace rx
