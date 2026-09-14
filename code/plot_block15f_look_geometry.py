"""Block15F plots from stored results only; no PVP or radar reads."""
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_block15f_look_geometry import OUT

def main():
    with (OUT/'BLOCK15F_LOOK_GEOMETRY.csv').open() as f:g=list(csv.DictReader(f))
    with (OUT/'BLOCK15F_TRANSFER_RESULTS.csv').open() as f:x=list(csv.DictReader(f))
    t=[float(r['tx_time_mean_s']) for r in g]
    fig,a=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    a[0,0].plot(t,[float(r['incidence_mean_deg']) for r in g],'o-');a[0,0].set(ylabel='Incidence [deg]',title='PVP geometry at BP12 target')
    a[0,1].plot(t,[float(r['view_azimuth_mean_deg']) for r in g],'o-',label='view');a[0,1].plot(t,[float(r['flight_azimuth_mean_deg']) for r in g],'o-',label='flight');a[0,1].set(ylabel='Bearing [deg]');a[0,1].legend()
    a[1,0].plot(t,[float(r['squint_mean_deg'])-90 for r in g],'o-');a[1,0].axhline(0,color='k',lw=.5);a[1,0].set(xlabel='Representative TxTime [s]',ylabel='Signed squint from broadside [deg]')
    a[1,1].plot(t,[float(r['k_los_mean_rad_m']) for r in g],'o-',label='k dot horizontal LOS');a[1,1].plot(t,[float(r['k_flight_mean_rad_m']) for r in g],'o-',label='k dot flight');a[1,1].set(xlabel='Representative TxTime [s]',ylabel='Projection [rad/m]');a[1,1].legend()
    fig.savefig(OUT/'BLOCK15F_LOOK_GEOMETRY.png',dpi=150);plt.close(fig)
    groups={}
    for r in x:groups.setdefault(r['scenario'],[]).append(r)
    fig,a=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for name,q in groups.items():
        tt=[float(r['time_s']) for r in q];a[0,0].plot(tt,[float(r['H_abs']) for r in q],label=name);a[0,1].plot(tt,[float(r['H_phase_rad']) for r in q],label=name);a[1,0].plot(tt,[float(r['transfer_slope_rad_s']) for r in q],label=name);a[1,1].plot(tt,[float(r['cancellation_ratio']) for r in q],label=name)
    a[0,0].set(ylabel='|H| [m^-1]',title='Limited transfer');a[0,1].set(ylabel='arg H [rad]');a[1,0].set(xlabel='TxTime [s]',ylabel='OLS s_transfer [rad/s]');a[1,1].set(xlabel='TxTime [s]',ylabel='|H|/(|Tt|+|Tvb|)');a[0,0].legend(fontsize=7)
    fig.savefig(OUT/'BLOCK15F_TRANSFER.png',dpi=150);plt.close(fig)
if __name__=='__main__':main()
