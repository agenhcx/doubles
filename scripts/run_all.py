#!/usr/bin/env python3
"""Run data collection and roster merge with one command; stop if source pages fail."""
import argparse
import subprocess
import sys
from pathlib import Path

def run(cmd):
    print("RUN:"," ".join(map(str,cmd)),flush=True)
    return subprocess.run(cmd,check=False).returncode

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--season-start",type=int,default=2018)
    p.add_argument("--season-end",type=int,default=2025)
    p.add_argument("--level",default="senior,junior")
    p.add_argument("--offline",action="store_true")
    p.add_argument("--refresh",action="store_true")
    p.add_argument("--proxy")
    p.add_argument("--no-env-proxy",action="store_true")
    a=p.parse_args()
    base=[sys.executable,str(Path(__file__).parent/"collect_isu_seasons.py"),"--season-start",str(a.season_start),"--season-end",str(a.season_end),"--level",a.level]
    if a.offline:base.append("--offline")
    if a.refresh:base.append("--refresh")
    if a.proxy:base.extend(["--proxy",a.proxy])
    if a.no_env_proxy:base.append("--no-env-proxy")
    rc=run(base)
    # Partial outputs are still useful, but must not be called complete.
    file=Path("output/isu/isu_season_roster.csv")
    if file.exists():
        rc2=run([sys.executable,str(Path(__file__).parent/"build_master_roster.py")])
        if rc2:return rc2
    return rc

if __name__=="__main__":
    raise SystemExit(main())
