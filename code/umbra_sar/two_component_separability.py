"""Compact variable-projection two-component coefficient experiment (Block15G)."""
import numpy as np
from scipy.optimize import minimize_scalar


def tukey(n,alpha=.1):
    x=np.linspace(0,1,n); w=np.ones(n); edge=alpha/2
    if alpha>0:
        lo=x<edge; hi=x>1-edge
        w[lo]=.5*(1+np.cos(np.pi*(2*x[lo]/alpha-1)))
        w[hi]=.5*(1+np.cos(np.pi*(2*x[hi]/alpha-2/alpha+1)))
    return w


def window_response(shape,q_coords,k):
    """Exact DFT of separable BP12 Tukey window at possibly fractional modes."""
    nr,nc=shape; w=np.outer(tukey(nr),tukey(nc)); rr=np.arange(nr)[:,None];cc=np.arange(nc)[None,:]
    out=[]
    for q in q_coords:
        phase=-2j*np.pi*((q[0]-k[0])*rr/nr+(q[1]-k[1])*cc/nc)
        out.append(np.sum(w*np.exp(phase)))
    return np.asarray(out)/np.sum(w)


def window_noise_cov(shape,q_coords):
    nr,nc=shape; w=np.outer(tukey(nr),tukey(nc))**2;rr=np.arange(nr)[:,None];cc=np.arange(nc)[None,:];n=len(q_coords)
    C=np.empty((n,n),complex)
    for i,q in enumerate(q_coords):
        for j,r in enumerate(q_coords):C[i,j]=np.sum(w*np.exp(-2j*np.pi*((q[0]-r[0])*rr/nr+(q[1]-r[1])*cc/nc)))/np.sum(w)
    return C


def correlated_noise(t,cov,sigma,tau,rng):
    t=np.asarray(t);L=np.linalg.cholesky(cov+1e-12*np.eye(len(cov)));n=len(t)
    e=(rng.normal(size=(n,len(cov)))+1j*rng.normal(size=(n,len(cov))))/np.sqrt(2)@L.T
    out=e.copy()
    if tau>0:
        for i in range(1,n):
            rho=np.exp(-(t[i]-t[i-1])/tau);out[i]=rho*out[i-1]+np.sqrt(1-rho*rho)*e[i]
    return sigma*out


def design(t,templates,Hs,slopes):
    return np.column_stack([(h[:,None]*np.exp(1j*s*t[:,None])*w[None,:]).ravel() for h,w,s in zip(Hs,templates,slopes)])


def solve_linear(y,X):
    a,_,rank,_=np.linalg.lstsq(X,y,rcond=None);return a,float(np.sum(abs(y-X@a)**2)),rank


def fit_q(y,t,templates,Hs,bounds,model,grid=31):
    """Q0/Q1/Q2 global coarse search, one-dimensional refinements for Q0/Q1."""
    y=np.asarray(y).ravel();t=np.asarray(t); gg=np.linspace(bounds[0],bounds[1],grid); candidates=[]; alternative_count=None
    if model=='Q0':
        for s in gg:
            a,cost,rank=solve_linear(y,design(t,[templates[0]],[Hs[0]],[s]));candidates.append((cost,(s,),a,rank))
    elif model=='Q1':
        static=np.tile(templates[0],len(t))[:,None]
        for s in gg:
            X=np.column_stack((design(t,[templates[0]],[Hs[0]],[s]),static));a,cost,rank=solve_linear(y,X);candidates.append((cost,(s,),a,rank))
    elif model=='Q2':
        # Variable projection in a full global grid.  Evaluate normal equations
        # vectorially: this is algebraically identical to 31*31 two-column LS
        # solves, but makes the purged Monte Carlo tractable.
        b1=np.vstack([design(t,[templates[0]],[Hs[0]],[s]).ravel() for s in gg])
        b2=np.vstack([design(t,[templates[1]],[Hs[1]],[s]).ravel() for s in gg])
        p1=b1.conj()@y;p2=b2.conj()@y;g11=np.sum(abs(b1)**2,axis=1);g22=np.sum(abs(b2)**2,axis=1);g12=b1.conj()@b2.T
        det=g11[:,None]*g22[None,:]-abs(g12)**2; num=g22[None,:]*abs(p1[:,None])**2+g11[:,None]*abs(p2[None,:])**2-2*np.real(np.conj(p1[:,None])*g12*p2[None,:])
        cost=np.sum(abs(y)**2)-np.divide(num,det,out=np.zeros_like(num),where=det>1e-12)
        ii,jj=np.unravel_index(np.argmin(cost),cost.shape);X=np.column_stack((b1[ii],b2[jj]));a,bestcost,rank=solve_linear(y,X);candidates=[(bestcost,(gg[ii],gg[jj]),a,rank)]
        # Coarse-grid ambiguity count; approximate grid costs are not fitted
        # candidates, hence cannot replace the solution with linear amplitudes.
        alternative_count=max(0,int(np.sum(cost<=bestcost*1.01))-1)
    else:raise ValueError(model)
    candidates.sort(key=lambda x:x[0]); best=candidates[0]; alt=[x for x in candidates[1:] if x[0]<=best[0]*1.01]
    return dict(model=model,s=list(best[1]),coeff=[[float(z.real),float(z.imag)] for z in best[2]],sse=best[0],rank=best[3],
      boundary=any(abs(v-bounds[0])<1e-12 or abs(v-bounds[1])<1e-12 for v in best[1]),alternatives=(len(alt) if alternative_count is None else alternative_count),grid_best=best[1])


def predict(fit,t,templates,Hs):
    X=design(t,templates[:len(fit['s'])],Hs[:len(fit['s'])],fit['s'])
    if fit['model']=='Q1':X=np.column_stack((X,np.tile(templates[0],len(t))))
    return X@np.array([complex(*a) for a in fit['coeff']])


def purged_folds(n=32):
    out=[]
    for start in range(0,n,4):
        test=np.arange(start,start+4);guard=np.arange(max(0,start-2),min(n,start+6));guard=np.setdiff1d(guard,test);train=np.setdiff1d(np.arange(n),np.r_[test,guard]);out.append((train,test,guard))
    return out


def validate(y,t,templates,Hs,bounds,model,folds=None):
    fold_spec=purged_folds(len(t)) if folds is None else folds
    folds=[]
    for item in fold_spec:
        train,test,guard=item
        f=fit_q(y.reshape(len(t),-1)[train],t[train],templates,[h[train] for h in Hs],bounds,model)
        pred=predict(f,t[test],templates,[h[test] for h in Hs]);actual=y.reshape(len(t),-1)[test].ravel();folds.append((float(np.sum(abs(actual-pred)**2)),f))
    return dict(sse=sum(x[0] for x in folds),folds=folds)


def block15d_folds(n=32):
    return [(np.setdiff1d(np.arange(n),np.arange(i,i+8)),np.arange(i,i+8),np.array([],int)) for i in range(0,n,8)]
