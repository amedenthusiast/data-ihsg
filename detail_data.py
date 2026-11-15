"""Build the ungrouped KSEI balance and investor classification charts."""
import argparse
import csv
import gzip
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from build_data import files, number, read_xlsx


CATEGORIES = "CP PF IB ID MF OT SC FD IS".split()
ORIGINS = ["Local","Foreign"]


def balance(root):
    snapshots = {}
    by_date = {path.stem[-8:]:path for path in files(root,"Balancepos????????.txt")}
    for day,path in sorted(by_date.items())[-12:]:
        date = datetime.strptime(day,"%Y%m%d").date().isoformat()
        with path.open(encoding="utf-8-sig",errors="replace",newline="") as source:
            for row in csv.DictReader(source,delimiter="|"):
                code = row["Code"].strip()
                if row["Type"]!="EQUITY" or not re.fullmatch(r"[A-Z0-9]{4}",code):
                    continue
                values = [number(row[f"{origin} {group}"]) for origin in ORIGINS for group in CATEGORIES]
                if any(v is None or v<0 for v in values) or not sum(values):
                    continue
                snapshots.setdefault(code,[]).append([date,[int(v) for v in values]])
    return snapshots


def investor(root):
    matches = {p.name:p for p in files(root,"peng-????-??-*-klasifikasi.xlsx")}
    snapshots = []
    for path in sorted(matches.values(),key=lambda p:p.name)[-2:]:
        rows = {}
        columns = []
        dates = set()
        for row in read_xlsx(path):
            if len(row)>2 and row[0]=="DATE" and row[1]=="SHARE_CODE":
                columns=[(i,label.split("_",1)) for i,label in enumerate(row)
                         if str(label).lower().startswith(("local_","foreign_")) and "total" not in label.lower()]
            if not columns or not isinstance(row[0],datetime) or not row[1]:
                continue
            dates.add(row[0].date().isoformat())
            rows[row[1]] = {tuple(group):int(number(row[i]) or 0) for i,group in columns}
        if len(dates)!=1 or not rows:
            raise ValueError(f"Unexpected classification layout: {path.name}")
        snapshots.append((dates.pop(),rows))
    if len(snapshots)!=2 or snapshots[0][0]>=snapshots[1][0]:
        return {},[]
    (prior,old),(current,new)=snapshots
    details={}
    for code in sorted(old.keys() & new.keys()):
        before,after=old[code],new[code]
        totals=[sum(before.values()),sum(after.values())]
        if min(totals)<=0:
            continue
        details[code]=[[origin,label,before.get((origin,label),0),after.get((origin,label),0)]
                       for origin,label in sorted(before.keys()|after.keys(),key=lambda k:(ORIGINS.index(k[0]),k[1]))
                       if before.get((origin,label),0) or after.get((origin,label),0)]
    return details,[prior,current]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("folder",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args()
    old=json.loads(gzip.decompress(args.output.read_bytes())) if args.output.exists() else {}
    data=old.copy()
    groups=balance(args.folder)
    investor_rows,periods=investor(args.folder)
    stamp=datetime.now(timezone.utc).isoformat(timespec="seconds")
    if groups and groups!=old.get("balance"):
        data.update(balance=groups,balanceUpdate=stamp)
    if investor_rows and (investor_rows,periods)!=(old.get("investor"),old.get("periods")):
        data.update(investor=investor_rows,periods=periods,investorUpdate=stamp)
    if data!=old:
        temporary=args.output.with_suffix(".tmp")
        temporary.write_bytes(gzip.compress(json.dumps(data,separators=(",",":")).encode(),mtime=0))
        temporary.replace(args.output)
    print(f"{len(groups)} balance tickers, {len(investor_rows)} investor tickers")


if __name__=="__main__":
    main()
