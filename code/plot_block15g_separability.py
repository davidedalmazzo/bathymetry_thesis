import csv,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_block15g_separability import OUT
def main():
 s=json.load(open(OUT/'BLOCK15G_SUMMARY.json'));g=s['groups'];names=sorted(set(x['case'] for x in g));fig,a=plt.subplots(1,2,figsize=(12,5),layout='constrained')
 for tr,col in [('constant','C1'),('geometry','C0')]:
  x=[r for r in g if r['transfer']==tr];a[0].plot([r['selected']/r['n'] for r in x],range(len(x)),'o-',label=tr,color=col);a[1].plot([r['recovered']/r['n'] for r in x],range(len(x)),'o-',label=tr,color=col)
 for ax,title in zip(a,['Q2 selected','Both frequencies recovered']):ax.set(yticks=range(len(names)),yticklabels=names,xlim=(-.05,1.05),xlabel='Monte Carlo fraction',title=title);ax.legend()
 fig.savefig(OUT/'BLOCK15G_SELECTION_RECOVERY.png',dpi=150);plt.close(fig)
 with (OUT/'BLOCK15G_RESULTS.csv').open() as f:r=list(csv.DictReader(f));fig,a=plt.subplots(figsize=(9,5),layout='constrained')
 for tr,col in [('constant','C1'),('geometry','C0')]:
  x=[q for q in r if q['phase']=='evaluation' and q['transfer']==tr];a.scatter([float(q['separation_true']) for q in x],[float(q['gain']) for q in x],label=tr,alpha=.7,color=col)
 a.axhline(s['threshold'],color='k',ls='--');a.set(xlabel='True temporal separation [rad/s]',ylabel='Q2 predictive gain',title='Evaluation only; each dot is one full realization');a.legend();fig.savefig(OUT/'BLOCK15G_GAIN_SEPARATION.png',dpi=150);plt.close(fig)
if __name__=='__main__':main()
