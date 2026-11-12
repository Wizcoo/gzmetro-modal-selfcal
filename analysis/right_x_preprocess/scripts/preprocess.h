#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <deque>
#include <numeric>
#include <string>
#include <vector>
namespace pre {
using V=std::vector<double>;
inline double median(V v){if(v.empty())return NAN;std::sort(v.begin(),v.end());return v.size()%2?v[v.size()/2]:.5*(v[v.size()/2-1]+v[v.size()/2]);}
inline double mad(const V&v){double m=median(v);V r;for(double x:v)r.push_back(std::abs(x-m));return 1.4826*median(r);}
inline bool solve(V g,V r,int k,V&x){double scale=0;for(int i=0;i<k;i++)scale=std::max(scale,std::abs(g[i*k+i]));for(int c=0;c<k;c++){int p=c;for(int i=c+1;i<k;i++)if(std::abs(g[i*k+c])>std::abs(g[p*k+c]))p=i;if(std::abs(g[p*k+c])<1e-10*std::max(scale,1e-20))return false;for(int j=0;j<k;j++)std::swap(g[p*k+j],g[c*k+j]);std::swap(r[p],r[c]);double d=g[c*k+c];for(int j=c;j<k;j++)g[c*k+j]/=d;r[c]/=d;for(int i=0;i<k;i++)if(i!=c){double a=g[i*k+c];for(int j=c;j<k;j++)g[i*k+j]-=a*g[c*k+j];r[i]-=a*r[c];}}x=r;return true;}
struct Sample{int64_t t;double x;};
struct Stats{bool ready=false,eligible=false;double sigma=.06955713017732815,rho=NAN;};
struct Point {
 std::deque<Sample> h;double level=0,velocity=0;int64_t last=0;bool initialized=false,pending=false;std::deque<std::pair<int,double>> pulses;
 void clear(){h.clear();pulses.clear();last=0;initialized=false;pending=false;velocity=0;}
 Stats stats()const{Stats s;if(h.size()<31)return s;V delta,d2;for(size_t j=1;j<h.size();j++)delta.push_back(h[j].x-h[j-1].x);for(size_t j=1;j<delta.size();j++)d2.push_back(delta[j]-delta[j-1]);s.sigma=std::max(.0001,mad(d2)/std::sqrt(6.));double a=std::accumulate(delta.begin()+1,delta.end(),0.)/(delta.size()-1),b=std::accumulate(delta.begin(),delta.end()-1,0.)/(delta.size()-1),xx=0,yy=0,xy=0;for(size_t j=1;j<delta.size();j++){double x=delta[j]-a,y=delta[j-1]-b;xx+=x*x;yy+=y*y;xy+=x*y;}s.rho=xx>1e-20&&yy>1e-20?xy/std::sqrt(xx*yy):NAN;s.ready=true;s.eligible=s.rho>=-.75&&s.rho<=-.15;return s;}
 double trend()const{V v;for(size_t j=h.size()>4?h.size()-3:1;j<h.size();j++){double dt=(h[j].t-h[j-1].t)/60000.;if(dt>0)v.push_back((h[j].x-h[j-1].x)/dt);}double z=median(v);return std::isfinite(z)?z:0;}
 void append(int64_t t,double x){if(!std::isfinite(x)){clear();return;}if(last&&t-last>90000)clear();h.push_back({t,x});while(h.size()>31)h.pop_front();last=t;}
 double filter(int64_t t,double x,bool linear,int&eligible,int&reset){
  if(!std::isfinite(x)){clear();return x;}if(last&&t-last>90000)clear();Stats s=stats();double dt=last?(t-last)/60000.:1.;double predict=initialized?level+velocity*dt:x;
  if(!s.ready||!s.eligible){level=x;velocity=trend();initialized=true;append(t,x);return x;}
  eligible++;if(std::abs(x-predict)>3*s.sigma){level=x;velocity=0;initialized=true;reset++;append(t,x);return x;}
  double value;
  if(linear){double st=0,st2=0,sx=x,stx=0;int n=1;for(size_t j=h.size()-4;j<h.size();j++){double a=(h[j].t-t)/60000.;st+=a;st2+=a*a;sx+=h[j].x;stx+=a*h[j].x;n++;}double den=n*st2-st*st;value=den>1e-12?(sx*st2-st*stx)/den:x;}
  else{double e=x-predict;value=predict+.8*e;velocity+=.2*e/std::max(.01,dt);}
  value=std::clamp(value,x-.5*s.sigma,x+.5*s.sigma);level=value;initialized=true;append(t,x);return value;
 }
};
struct Model{int64_t night=-1;bool ready=false;V A,b,cbar;std::vector<char> learn,use;int learned=0;};
struct Feature{std::vector<Stats> s;V delta;double participation=0,previous_participation=0;};
struct RawHistory{
 std::vector<Point> points;double previous=0;
 explicit RawHistory(size_t p=0):points(p){}
 Feature feature(int64_t t,const V&x){Feature f;f.previous_participation=previous;int n=0,big=0;for(size_t i=0;i<x.size();i++){auto&p=points[i];if(p.last&&t-p.last>90000)p.clear();auto s=p.stats();f.s.push_back(s);double d=p.h.empty()?NAN:x[i]-p.h.back().x;f.delta.push_back(d);if(s.ready&&std::isfinite(d)){n++;big+=std::abs(d)>3*s.sigma;}}f.participation=n?double(big)/n:1;return f;}
 void update(int64_t t,const V&x,const Feature&f){for(size_t i=0;i<x.size();i++)points[i].append(t,x[i]);previous=f.participation;}
};
struct Diagnostics{int changed=0,eligible=0,reset=0,reference_model=0,projection_failed=0;double max_delta=0,projection_leakage=0;};
struct Processor{
 std::string method;std::vector<Point> state;int frame=0;int64_t modelnight=-1;V lastcommon;Diagnostics diag;
 explicit Processor(std::string m={},size_t p=0):method(m),state(p),lastcommon(p,NAN){}
 V run(int64_t t,const V&raw,const V&shadow,const Model&model,bool common_valid,const Feature&f){
  diag=Diagnostics();frame++;V out=raw,common(raw.size()),proposal(raw.size(),0),sigma(raw.size(),1);std::vector<char> eligible(raw.size(),0);
  for(size_t i=0;i<raw.size();i++)common[i]=raw[i]-shadow[i];
  if(method=="B0_raw")return out;
  if(method=="B3_N3"&&(!common_valid||modelnight!=model.night)){for(auto&p:state)p.clear();modelnight=model.night;if(!common_valid){lastcommon=common;return out;}}
  for(size_t i=0;i<raw.size();i++){
   auto&p=state[i];if(!std::isfinite(raw[i])){p.clear();continue;}if(p.last&&t-p.last>90000)p.clear();
   if(method=="B1_N1"){
    Stats s=f.s[i];bool completion=false;double amp=0;if(s.ready&&p.h.size()>=2){double prev=p.h.back().x,before=p.h[p.h.size()-2].x;amp=std::abs(prev-.5*(before+raw[i]));completion=amp>6*s.sigma&&std::abs(raw[i]-before)<=2*s.sigma&&f.participation<=.1&&f.previous_participation<=.1;}
    while(!p.pulses.empty()&&frame-p.pulses.front().first>60)p.pulses.pop_front();
    bool persistent=p.pending&&!p.h.empty()&&std::abs(raw[i]-p.h.back().x)<=2*s.sigma;
    if(persistent){p.pulses.clear();p.pending=false;}
    if(s.ready&&!completion&&!persistent&&p.pulses.size()>=2&&f.participation<=.1&&!p.h.empty()){
     double dt=(t-p.h.back().t)/60000.,pred=p.h.back().x+p.trend()*dt,e=raw[i]-pred;V pastamp;for(auto q:p.pulses)pastamp.push_back(q.second);double a=median(pastamp);double dc=common[i]-lastcommon[i];bool common_protect=common_valid&&std::isfinite(dc)&&std::abs(dc)>=std::max(2*s.sigma,.5*std::abs(f.delta[i]));
     if(std::abs(e)>6*s.sigma&&std::abs(e)<=4*a&&!common_protect){out[i]=pred+std::copysign(6*s.sigma,e);p.pending=true;diag.eligible++;}
    }
    if(completion)p.pulses.push_back({frame,amp});p.append(t,raw[i]);
   } else if(method=="B2_N2_ab"||method=="B2ll_N2_linear")out[i]=p.filter(t,raw[i],method=="B2ll_N2_linear",diag.eligible,diag.reset);
   else if(method=="B3_N3"){
    Stats s=p.stats();double filtered=p.filter(t,shadow[i],false,diag.eligible,diag.reset);proposal[i]=filtered-shadow[i];sigma[i]=s.sigma;eligible[i]=s.ready&&s.eligible&&std::abs(proposal[i])>1e-15;diag.reference_model=1;
   }
  }
  if(method=="B3_N3"){
   V g(9,0),rhs(3,0),coef;int n=0;
   for(size_t i=0;i<raw.size();i++)if(model.learn[i]&&eligible[i]){n++;for(int a=0;a<3;a++){rhs[a]+=model.A[3*i+a]*proposal[i];for(int b=0;b<3;b++)g[3*a+b]+=model.A[3*i+a]*model.A[3*i+b];}}
   bool solved=n>=5&&solve(g,rhs,3,coef);if(!solved)diag.projection_failed=1;double ratio=1;
   for(size_t i=0;i<raw.size();i++)if(model.learn[i]&&eligible[i]){if(!solved)proposal[i]=0;else for(int a=0;a<3;a++)proposal[i]-=model.A[3*i+a]*coef[a];if(std::abs(proposal[i])>0)ratio=std::min(ratio,.5*sigma[i]/std::abs(proposal[i]));}
   V leakage(3,0);for(size_t i=0;i<raw.size();i++)if(model.learn[i]&&eligible[i]){proposal[i]*=ratio;for(int a=0;a<3;a++)leakage[a]+=model.A[3*i+a]*proposal[i];}
   for(double a:leakage)diag.projection_leakage=std::max(diag.projection_leakage,std::abs(a));for(size_t i=0;i<raw.size();i++)if(eligible[i]&&std::isfinite(raw[i]))out[i]+=proposal[i];
  }
  for(size_t i=0;i<raw.size();i++)if(std::isfinite(out[i])&&std::isfinite(raw[i])){double d=std::abs(out[i]-raw[i]);diag.changed+=d>1e-12;diag.max_delta=std::max(diag.max_delta,d);}lastcommon=common;return out;
 }
};
} // namespace pre
