import os, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
O = os.path.join(HERE, "out") + os.sep
def load(fn, n):
    d=np.loadtxt(O+fn); return [d[:,0]]+[d[:,2*i+1] for i in range(n)]
plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,"grid.alpha":0.25,"font.family":"DejaVu Sans"})
c1,c2,c3,c4,cr="#2563eb","#ea580c","#16a34a","#7c3aed","#dc2626"
fig,ax=plt.subplots(2,2,figsize=(13,8.8))
t,vd,vg,ic=load("relay_voh2.64_vt1.45_kp25_v4.75_L0.2.dat",3)
a=ax[0,0]; a.plot(t*1e3,vg,c=c1,label="gate (GPIO high at its 2.64 V minimum)"); a.plot(t*1e3,vd,c=c2,label="relay drain"); a.set_ylabel("V"); a.set_xlabel("ms")
a2=a.twinx(); a2.plot(t*1e3,ic*1e3,c=c3,label="coil current (needs ~40 mA)"); a2.set_ylabel("coil current (mA)",color=c3); a2.spines["right"].set_visible(True); a2.grid(False)
a.set_xlim(0,60); a.set_ylim(-0.3,6.3); a2.set_ylim(-3,63)
a.set_title("Relay driver, worst case: weak GPIO, max VGS(th), weak FET, 5 V at 4.75 V",fontsize=10.5,loc="left")
h=a.get_legend_handles_labels(); h2=a2.get_legend_handles_labels(); a.legend(h[0]+h2[0],h[1]+h2[1],loc="lower center",bbox_to_anchor=(0.42,0.1),fontsize=8.5,frameon=False)
t,vd,vg,ic=load("relay_voh3.3_vt0.65_kp80_v5.1_L0.5.dat",3)
a=ax[0,1]; m=(t>0.0405)&(t<0.056)
a.plot((t[m]-0.041)*1e3,vd[m],c=c2,label="drain: SS14 clamps the coil at 5.1 V + ~0.3 V")
a2=a.twinx(); a2.plot((t[m]-0.041)*1e3,ic[m]*1e3,c=c3,label="coil current decaying through SS14"); a2.set_ylabel("coil current (mA)",color=c3); a2.spines["right"].set_visible(True); a2.grid(False); a2.set_ylim(-3,63)
a.axhline(30,c=cr,ls="--",lw=1); a.text(14.8,28.6,"AO3400A VDS max 30 V",color=cr,fontsize=8.5,ha="right")
a.set_ylim(-0.3,32); a.set_xlim(-0.5,15); a.set_xlabel("ms after GPIO goes low"); a.set_ylabel("V")
a.set_title("Turn-off, worst flyback corner (big coil L): drain peaks at 5.38 V",fontsize=10.5,loc="left")
h=a.get_legend_handles_labels(); h2=a2.get_legend_handles_labels(); a.legend(h[0]+h2[0],h[1]+h2[1],loc="center right",bbox_to_anchor=(1,0.55),fontsize=8.5,frameon=False)
a=ax[1,0]
for fn,lab,col in [("rails_ipk0.379_cint220u_tau2u_v5.0.dat","typical: 379 mA TX peaks, LDO loop ~40 kHz → min 3.26 V",c1),("rails_ipk0.5_cint47u_tau10u_v4.9.dat","pessimistic: 500 mA peaks, slow LDO, weak HLK → min 3.04 V",c2)]:
    t,v5,v33,ih=load(fn,3); a.plot(t*1e3,v33,c=col,lw=1.1,label=lab)
a.axhspan(3.0,3.6,color=c3,alpha=0.07); a.axhline(3.0,c=cr,ls="--",lw=1); a.axhline(3.6,c=cr,ls="--",lw=1)
a.text(19.8,3.012,"ESP32 min 3.0 V",ha="right",color=cr,fontsize=8.5); a.text(19.8,3.612,"ESP32 max 3.6 V",ha="right",color=cr,fontsize=8.5)
a.axvline(6,c="#888",ls=":",lw=1); a.text(6.15,3.66,"relay switches on",fontsize=8,color="#666")
a.set_ylim(2.72,3.75); a.set_xlim(1,20); a.set_xlabel("ms"); a.set_ylabel("V"); a.legend(fontsize=8.2,frameon=False,loc="lower center")
a.set_title("3.3 V rail during WiFi TX bursts + relay switching",fontsize=10.5,loc="left")
t,v5,v33,en,g=load("powerup.dat",4)
a=ax[1,1]; a.plot(t*1e3,v5,c=c4,label="5 V (HLK-PM01)"); a.plot(t*1e3,v33,c=c1,label="3.3 V"); a.plot(t*1e3,en,c=c2,label="ESP32 EN (R1 10k / C5 1 µF)"); a.plot(t*1e3,g,c=c3,label="relay gate (GPIO26 floating, +1 µA leak)")
a.axhline(2.475,c="#888",ls=":",lw=1); a.text(59,2.25,"EN threshold 0.75·VDD",fontsize=8,color="#666",ha="right")
a.annotate("",xy=(16,2.475),xytext=(2.9,2.475),arrowprops=dict(arrowstyle="<->",color=c2)); a.text(17,1.35,"EN releases 13 ms after\n3.3 V is valid",fontsize=8.5,color=c2)
a.set_xlim(0,60); a.set_ylim(-0.2,5.6); a.set_xlabel("ms"); a.set_ylabel("V"); a.legend(fontsize=8.5,frameon=False,loc="upper right",bbox_to_anchor=(1,0.93))
a.set_title("Power-up: supplies settle before the ESP32 starts; relay stays off",fontsize=10.5,loc="left")
fig.suptitle("Boili PCB – ngspice checks",fontsize=14,fontweight="bold",x=0.01,ha="left")
fig.tight_layout(rect=(0,0,1,0.96)); fig.savefig(os.path.join(HERE, "boili_spice_results.png"), dpi=130)
