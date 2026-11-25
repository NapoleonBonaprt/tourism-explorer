"""Reconstructed TCI scoring, verified against every original city-month row.
Unobserved extreme temperature/wind ranges are explicit assumptions, not recovered source code.
"""
import numpy as np
import pandas as pd

def comfort(t, rh):
    effective = t - .4*(t-10)*(1-rh/100)
    return np.select([effective<12,effective<14,effective<16,effective<18,effective<20,
                      effective<27,effective<29,effective<31,effective<33,effective<35],
                     [0,1,2,3,4,5,4,3,2,1],default=0).astype(float)

def score_tci(data):
    d=data.copy()
    d["CID"]=comfort(d.Temp_Max_Mean,d.RH_Min_Mean)
    d["CIA"]=comfort(d.Temp_Mean,d.RH_Mean)
    d["P_score"]=np.clip(5-.5*np.floor(d.Precip_Total_mm/15),0,5)
    d["S_score"]=np.clip(.5*np.floor(d.Sunshine_h_per_day),0,5)
    # The historical 4 / 3.5 boundary is bracketed by 2.511 and 2.512 m/s.
    d["W_score"]=np.select([d.Wind_Mean_ms<.8,d.Wind_Mean_ms<1.6,d.Wind_Mean_ms<2.512,
                            d.Wind_Mean_ms<3.4,d.Wind_Mean_ms<5.5,d.Wind_Mean_ms<6.8],
                           [5,4.5,4,3.5,3,2.5],default=2.)
    d["TCI"]=2*(4*d.CID+d.CIA+2*d.P_score+2*d.S_score+d.W_score)
    d["TCI_Category"]=np.select([d.TCI>=90,d.TCI>=80,d.TCI>=70,d.TCI>=60,d.TCI>=50,
                                 d.TCI>=40,d.TCI>=30,d.TCI>=20],
                                ["Ideal","Excellent","Very Good","Good","Acceptable","Marginal","Unfavorable","Very Unfavorable"],
                                default="Extremely Unfavorable")
    d["Hemisphere"]=np.where(d.City_Center_Lat<0,"South","North")
    d["is_south"]=(d.City_Center_Lat<0).astype(int)
    d["month_sin"]=np.round(np.sin(2*np.pi*d.Month/12),3)
    d["month_cos"]=np.round(np.cos(2*np.pi*d.Month/12),3)
    return d

def verify_original(data):
    regenerated=score_tci(data)
    cols=["CID","CIA","P_score","S_score","W_score","TCI","TCI_Category"]
    mismatches={c:int((regenerated[c]!=data[c]).sum()) for c in cols}
    if any(mismatches.values()):
        raise ValueError(f"TCI reconstruction differs from original: {mismatches}")
    return mismatches
