# -*- coding: utf-8 -*-
"""
Created on Thu Jan 14 14:46:40 2016

@author: flo
"""
import core.fscLVM as sparseFA
from sklearn.decomposition import RandomizedPCA,PCA
import h5py
import scipy as SP
import matplotlib as mpl
import matplotlib.lines as mlines
mpl.use('Agg')
import pylab as plt
import brewer2mpl



def mad(X):
    median = SP.median(X, axis=0)
    return SP.median(abs(X-median), axis=0)
    
def secdev(x):
    return 1/(2*SP.pi)*(SP.exp(-x*x/2.))*(x*x-1)
    
    
def saveFA(FA, idx=None, Ycorr=None, Ycorr_lat = None):
    MAD = mad(FA.S.E1)
    alpha02 = (MAD>.5)*(1/(FA.Alpha.E1))
    out_file = h5py.File(FA.out_name+'_it_'+str(FA.iterationCount)+'.hdf5','w')    
    out_file['alphaRaw'] = FA.Alpha.E1
    out_file['alpha02'] = alpha02  
    out_file['W'] = FA.W.E1
    out_file['Eps'] = FA.Eps.E1
    out_file['S'] = FA.S.E1        
    out_file['Gamma'] = FA.W.C[:,:,0]
    out_file['pi'] = FA.Pi
    out_file['terms'] = FA.terms
    if idx != None:
        out_file['idx'] = idx
    if Ycorr != None:
        out_file['Ycorr'] = Ycorr
    if Ycorr_lat != None:
        out_file['Ycorr_lat'] = Ycorr_lat               
    out_file.close()    
    
    
    
def loadFA(out_name):
    out_file = h5py.File(out_name,'r')    
    res = {}   
    for key in out_file.keys():    
        res[key] = out_file[key]    
    return res
    
    
def plotFactors(idx1, idx2,FA=None, X = None,  lab=None, terms=None, cols=None, isCont=True):
    if FA!=None:
        MAD = mad(FA.S.E1)
        alpha = (MAD>.5)*(1/(FA.Alpha.E1))
        idxF = SP.argsort(-alpha)    
        X1 = FA.S.E1[:,idxF[idx1]]
        X2 = FA.S.E1[:,idxF[idx2]]
    else:
        X1 = X[:,idx1]
        X2 = X[:,idx2]        
    
    if isCont==False:
        uLab = SP.unique(lab)  
        if cols==None:
             bmap=brewer2mpl.get_map('Paired', 'Qualitative', len(uLab))
             cols = bmap.hex_colors         
        pList=list()
        for i in range(len(X1)):
            pList.append(plt.plot(X1[i], X2[i], '.',color=cols[SP.where(lab[i]==uLab)[0]]))
        plt.xlabel(terms[idx1])
        plt.ylabel(terms[idx2])
        lList=list()
        for i in range(len(uLab)):
            lList.append( mlines.Line2D([], [], color=cols[i], marker='.',
                              markersize=7, label=uLab[i], linewidth=0))     
        plt.legend(handles=lList)
    else:
        plt.scatter(X1, X2, c=lab, s=20)
        plt.xlabel(terms[idx1])
        plt.ylabel(terms[idx2])
    plt.show()


    
def plotTerms(FA=None, S=None, alpha=None, terms=None, doFilter=True, thre=.5):
    assert terms!=None
#        print 'terms need to be same length as relevance score'    
    if FA!=None:
        MAD = mad(FA.S.E1)
        if doFilter==True:
            alpha = (MAD>thre)*(1/(FA.Alpha.E1))
        else:
            alpha = (1/(FA.Alpha.E1))
    elif doFilter==True:
        MAD = mad(S) 
        alpha = (MAD>thre)*(1/(alpha))
    else:
        alpha = 1./alpha
                 
    idx_sort = SP.argsort(terms)
    Y = alpha[idx_sort]
    X =SP.arange(len(alpha))#[idx_sort]
    plt.plot(X, Y, '.',markersize=10)
    plt.xticks(X, terms[idx_sort], size='small', rotation='vertical')    
    plt.ylabel("Relevance score")
    plt.show()
    


def regressOut(Y,idx, FA=None, S=None, W=None, C=None, use_latent=False):
    #assert Y.shape[1] == FA.W.E1.shape[0] and Y.shape[0] == FA.W.E1.shape[0]
    if FA != None:
        S = FA.S.E1
        W = FA.W.E1
        C = FA.W.C[:,:,0]        
    idx = SP.array(idx)        
    if use_latent==False:
        Ycorr = Y-SP.dot(S[:,idx], (C[:,idx]*W[:,idx]))
    else:
        idx_use = SP.array(set(SP.arange(S.shape[1]))-set(idx))
        Ycorr = SP.dot(S[:,idx_use], (C[:,idx_use]*W[:,idx_use,0]))    
    return Ycorr
    
    

def vcorrcoef(X,y):
    Xm = SP.reshape(SP.mean(X,axis=1),(X.shape[0],1))
    ym = SP.mean(y)
    r_num = SP.sum((X-Xm)*(y-ym),axis=1)
    r_den = SP.sqrt(SP.sum((X-Xm)**2,axis=1)*SP.sum((y-ym)**2))
    r = r_num/r_den
    return r

 
def getIlabel(order, Y, terms, pi,init_factors=None):
    assert (order in ['preTrain', 'PCA'])

    if order=='preTrain':
        assert init_factors!=None
        Ilabel = preTrain(Y, terms, pi,init_factors)
        return Ilabel
    else:
        PCs = SP.zeros((Y.shape[0], pi.shape[1]))
        for k in pi.shape[1]:
            pca = PCA(n_components=1)
            pca.fit_transform(Y[:,pi[:,k]>.5])
            PCs[:,k] = pca.score[:,0]

        X  = pca.fit_transform(Y)
        nFix = (SP.where(terms=='hidden')[0]).min()+len(SP.where(terms=='hidden')[0])
        MPC = abs(vcorrcoef(PCs.T,X.T))[nFix:]
        IpiRev = SP.argsort(MPC.ravel())      
        Ilabel = range(len(terms))
        Ilabel[nFix:] = IpiRev+nFix
        return Ilabel
        

def preTrain(Y, terms, pi,init_factors):
    K = pi.shape[1]

    #data for sparseFA instance    
    pi[pi>.2] =0.99
    pi[pi<.8] =1e-8
    

    init={'init_data':sparseFA.CGauss(Y),'Pi':pi,'init_factors':init_factors}
    sigmaOff = 1E-3
    sparsity = 'VB'

    #prior on noise level 
    priors = {'Eps': {'priors':[1E-3,1E-3]}}
    #how to initialize network?
    initType = 'pcaRand'
    terms0=terms
    pi0=pi
    FA0 = sparseFA.CSparseFA(components=K,sigmaOff=sigmaOff,sigmaOn=SP.ones(pi.shape[1])*1.0,sparsity=sparsity,nIterations=50,permutation_move=False,priors=priors,initType=initType)
    FA0.init(**init)

                        
#Fit PCA        
    pca = PCA(n_components=1)
    pca.fit(FA0.Z.E1)
    X = pca.transform(FA0.Z.E1)
    nFix = FA0.nKnown+FA0.nLatent
    
    

#Sort by correlation to PC1    
    MPC = abs(vcorrcoef(FA0.initS[:,SP.argsort(FA0.W.Ilabel)].T,X.T))[nFix:]
    Ipi = SP.argsort(-MPC.ravel())
    IpiRev = SP.argsort(MPC.ravel())


    mRange = range(FA0.components)
    mRange[nFix:] = Ipi+nFix
    
    mRangeRev = range(FA0.components)
    mRangeRev[nFix:] = IpiRev+nFix

#Run model for 50 iterations         
    pi = pi0[:,mRange]
    terms = terms0[mRange]     
    init={'init_data':sparseFA.CGauss(Y),'Pi':pi,'init_factors':init_factors}
    FA = sparseFA.CSparseFA(components=K,sigmaOff=sigmaOff,sigmaOn=SP.ones(pi.shape[1])*1.0,sparsity=sparsity,nIterations=50,permutation_move=False,priors=priors,initType=initType)            
    FA.shuffle=True
    FA.init(**init) 
    for j in range(50):
        FA.update()      
        

    #Run reverse model for 50 iterations         
    pi = pi0[:,mRangeRev]
    terms = terms0[mRangeRev]
    init={'init_data':sparseFA.CGauss(Y),'Pi':pi,'init_factors':init_factors}        
    FArev = sparseFA.CSparseFA(components=K,sigmaOff=sigmaOff,sigmaOn=SP.ones(pi.shape[1])*1.0,sparsity=sparsity,nIterations=50,permutation_move=False,priors=priors,initType=initType)            
    FArev.shuffle=True
    FArev.init(**init) 
    #FArev.iterate(forceIterations=True, nIterations=nIterations)
    for j in range(50):
        FArev.update() 
            
    
    
    IpiM = (0.5*FArev.Alpha.E1[SP.argsort(mRangeRev)][nFix:]+.5*FA.Alpha.E1[SP.argsort(mRange)][nFix:]).argsort()    
    Ilabel = SP.hstack([SP.arange(nFix),IpiM+nFix])
    return Ilabel
    
