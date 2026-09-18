"""Calendar-aware bounded event windows, independent of mission and cache."""
import math
from datetime import datetime, timezone
from .data import utc


def half_width(config,family):
    width=max(float(config.get("event_context_seconds",0)),float(config.get("time_tolerance_seconds",{}).get(family,0)))
    if not math.isfinite(width) or width<0:raise ValueError("Invalid event search interval")
    return width


def event_windows(acquisitions,config,family):
    width=half_width(config,family)
    windows=sorted((utc(a["timestamp_utc"]).timestamp()-width,utc(a["timestamp_utc"]).timestamp()+width) for a in acquisitions)
    merged=[]
    for lo,hi in windows:
        if merged and lo<=merged[-1][1]:merged[-1][1]=max(hi,merged[-1][1])
        else:merged.append([lo,hi])
    return merged


def months_needed(acquisitions,config,family):
    months=set()
    for lo,hi in event_windows(acquisitions,config,family):
        date=datetime.fromtimestamp(lo,timezone.utc)
        last=datetime.fromtimestamp(hi,timezone.utc)
        year,month=date.year,date.month
        while (year,month)<=(last.year,last.month):
            months.add(f"{year:04d}{month:02d}")
            year,month=(year+1,1) if month==12 else (year,month+1)
    return sorted(months,reverse=True)
