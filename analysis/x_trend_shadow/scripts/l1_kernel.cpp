#include "XTrendL1.h"
#include <vector>
#ifdef _WIN32
#define XS_EXPORT extern "C" __declspec(dllexport)
#else
#define XS_EXPORT extern "C"
#endif
struct Context{std::vector<xtrend::Point>points;explicit Context(int n):points(n){}};
XS_EXPORT void* xs_create(int n){return new Context(n);}
XS_EXPORT void xs_free(void*p){delete static_cast<Context*>(p);}
XS_EXPORT int xs_step(void*p,int64_t t,const double*x,double gate,double*out,double*stats){
 auto&v=static_cast<Context*>(p)->points;double largest=0,iterations=0,failed=0,eligible=0;
 for(size_t j=0;j<v.size();j++){
  auto&s=v[j];s.observe(x[j],t);out[j]=x[j];if(gate>0&&std::isfinite(x[j])&&s.count>=3){double l=s.solve();out[j]=x[j]+gate*(l-x[j]);largest=std::max(largest,s.gap);iterations=std::max(iterations,double(s.iterations));failed+=s.gap>5e-7;eligible++;}
 }
 stats[0]=largest;stats[1]=iterations;stats[2]=failed;stats[3]=eligible;return 0;
}
XS_EXPORT void xs_dump(void*p,double*y,int*count,int64_t*last){auto&v=static_cast<Context*>(p)->points;for(size_t j=0;j<v.size();j++){count[j]=v[j].count;last[j]=v[j].last;for(int k=0;k<15;k++)y[j*15+k]=v[j].y[k];}}
XS_EXPORT void xs_restore(void*p,const double*y,const int*count,const int64_t*last){auto&v=static_cast<Context*>(p)->points;for(size_t j=0;j<v.size();j++){v[j].count=count[j];v[j].last=last[j];for(int k=0;k<15;k++)v[j].y[k]=y[j*15+k];}}
XS_EXPORT void xs_certificate(void*p,int j,double*y,double*l,double*u,double*stats){auto&s=static_cast<Context*>(p)->points[j];for(int k=0;k<15;k++){y[k]=s.y[k];l[k]=s.level[k];}for(int k=0;k<13;k++)u[k]=s.dual[k];stats[0]=s.count;stats[1]=s.lambda;stats[2]=s.gap;stats[3]=s.iterations;}
