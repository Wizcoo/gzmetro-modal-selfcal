#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
namespace xtrend {
constexpr int Window=15;
struct Point {
 std::array<double,Window> y{},level{};std::array<double,Window-2>dual{};
 int count=0,iterations=0;int64_t last=0;double lambda=0,gap=0;
 static double median(double*v,int n){std::sort(v,v+n);return n%2?v[n/2]:.5*(v[n/2-1]+v[n/2]);}
 void observe(double x,int64_t t){
  if(!std::isfinite(x)){count=0;last=0;return;}
  if(last&&(t-last>90000||t<=last))count=0;last=t;
  if(count<Window)y[count++]=x;else{for(int k=1;k<Window;k++)y[k-1]=y[k];y[Window-1]=x;}
 }
 double solve(){
  int n=count,m=n-2;iterations=0;gap=0;dual.fill(0);level=y;if(n<3)return n?y[n-1]:NAN;
  std::array<double,13>q{},u{},z{},old{},v{},tmp{};for(int k=0;k<m;k++)q[k]=y[k]-2*y[k+1]+y[k+2];tmp=q;double center=median(tmp.data(),m);for(int k=0;k<m;k++)tmp[k]=std::abs(q[k]-center);double sigma=std::max(.01,1.4826*median(tmp.data(),m)/std::sqrt(6.));lambda=sigma*std::sqrt(12*std::log(double(n)));double momentum=1;
  // Box-constrained dual: .5*u' D D' u - (D y)'u, |u|<=lambda.
  // D D' is pentadiagonal with6,-4,1; its spectral norm is <=16.
  for(int it=0;it<2000;it++){
   old=u;double next=.5*(1+std::sqrt(1+4*momentum*momentum));
   for(int k=0;k<m;k++){
    double gr=6*z[k]-q[k];if(k)gr-=4*z[k-1];if(k+1<m)gr-=4*z[k+1];if(k>=2)gr+=z[k-2];if(k+2<m)gr+=z[k+2];u[k]=std::clamp(z[k]-gr/16.,-lambda,lambda);
   }
   double restart=0;for(int k=0;k<m;k++)restart+=(z[k]-u[k])*(u[k]-old[k]);
   for(int k=0;k<m;k++)v[k]=u[k]+(momentum-1)/next*(u[k]-old[k]);
   if(restart>0){z=u;momentum=1;}else{z=v;momentum=next;}
   iterations=it+1;
   if(it%10==9||it==1999){
    level=y;for(int k=0;k<m;k++){level[k]-=u[k];level[k+1]+=2*u[k];level[k+2]-=u[k];}gap=0;
    for(int k=0;k<m;k++){double d=level[k]-2*level[k+1]+level[k+2];gap+=lambda*std::abs(d)-u[k]*d;}
    gap=std::max(0.,gap);if(gap<=5e-7)break;
   }
  }
  dual=u;return level[n-1];
 }
};
} // namespace xtrend
