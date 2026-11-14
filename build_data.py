"""Create dashboard snapshots from the Trading/Data exports."""
import argparse
import csv
import gzip
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", "").rstrip("%"))
    except ValueError:
        return None


def files(root, pattern):
    return sorted(root.rglob(pattern), key=lambda p: (p.name, -len(p.parts)))


def read_xlsx(path):
    with path.open("rb") as source:
        workbook = load_workbook(source, read_only=True, data_only=True, keep_links=False)
        try:
            yield from workbook.active.values
        finally:
            workbook.close()


def date_label(value):
    return value.date().isoformat() if isinstance(value, datetime) else str(value)[:10]


def publish(payload, key, rows, periods):
    payload[key] = rows
    payload["sources"][key] = {
        "period": " / ".join(periods),
        "update": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def ownership5(path):
    records = []
    for row in read_xlsx(path):
        if len(row) < 17:
            continue
        if row[1] == "Kode Efek":
            dates = [datetime.strptime(str(row[i]).split()[-1], "%d-%b-%Y").date().isoformat() for i in (11, 14)]
        code, name = row[1], row[4]
        if not code or not name or not re.fullmatch(r"[A-Z0-9]{4}", str(code)):
            continue
        before, after = number(row[13]), number(row[16])
        if before is None and after is None:
            continue
        origin = {"L": "Lokal", "F": "Asing"}.get(str(row[10]).strip().upper(), "-")
        status = "New" if (before or 0) == 0 else "Exited" if (after or 0) == 0 else "Existing"
        record = [code, str(name).strip(), origin, "-", after, before, status, number(row[15]), number(row[12])]
        if row[0] is not None:
            records.append(record)
    if not records:
        raise ValueError(f"No 5% records in {path.name}")
    return records, dates


def ownership1(path):
    groups = {}
    for row in read_xlsx(path):
        if len(row) < 13 or not isinstance(row[0], datetime) or not row[1] or not row[3]:
            continue
        code, name, kind, origin = row[1], str(row[3]).strip(), row[4] or "-", row[6]
        percentage, quantity = number(row[12]), number(row[11])
        key = (code, " ".join(name.casefold().split()), origin)
        records = groups.setdefault(date_label(row[0]), {})
        if key in records:
            prior = records[key]
            if prior[2] != kind:
                key = (code,key[1]+" ["+str(kind)+"]",origin)
            else:
                percentage = sum(v for v in (prior[3],percentage) if v is not None)
                quantity = sum(v for v in (prior[4],quantity) if v is not None)
        records[key] = (name, {"L": "Lokal", "F": "Asing"}.get(origin, "-"), kind, percentage, quantity)
    if len(groups) != 1:
        raise ValueError(f"Expected one reporting period in {path.name}")
    return next(iter(groups.items()))


def index_history(root, previous):
    results = {row["date"]: row for row in previous}
    for path in files(root, "IHSG_Trading_Data_*.tsv"):
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source, delimiter="\t"):
                date = row["Date"]
                datetime.strptime(date, "%Y-%m-%d")
                price, flow = number(row["Close"]), number(row["Net Foreign Buy/Sell"])
                if price is not None and price > 0 and flow is not None:
                    results[date] = {"date": date, "price": price, "flow": flow / 1e12}
    return sorted(results.values(), key=lambda row: row["date"])


def balance_snapshots(root):
    result = {}
    for path in files(root,"Balancepos????????.txt")[-12:]:
        period = datetime.strptime(path.stem[-8:],"%Y%m%d").date().isoformat()
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as source:
            for row in csv.reader(source,delimiter="|"):
                if len(row)<25 or row[2].strip().upper() not in {"EQUITY","ORDI","SHARE","S"}:
                    continue
                code = row[1].strip()
                if not re.fullmatch(r"[A-Z0-9]{4}",code):
                    continue
                values = [number(row[i]) or 0 for i in (9,6,14,24,19)]
                result.setdefault(code,[]).append([period,[values[0],values[1],values[2]-values[0]-values[1],values[3]-values[4],values[4],0]])
    return result


def investor_snapshots(root):
    paths = files(root,"peng-????-??-*-klasifikasi.xlsx")
    if len(paths)<2:
        return {}, []
    snapshots = []
    for path in paths[-2:]:
        result = {}
        columns = []
        periods = set()
        for row in read_xlsx(path):
            if len(row)>2 and row[0]=="DATE" and row[1]=="SHARE_CODE":
                columns = [(i,str(label)) for i,label in enumerate(row)
                           if str(label).lower().startswith(("local_","foreign_"))]
            if not columns or not isinstance(row[0],datetime) or not row[1]:
                continue
            periods.add(date_label(row[0]))
            values = {name:number(row[i]) or 0 for i,name in columns}
            total = sum(values.values())
            if total>0:
                result[row[1]] = {name:round(100*value/total,6) for name,value in values.items() if value}
        if len(periods)!=1 or not result:
            raise ValueError(f"Unexpected classification format in {path.name}")
        snapshots.append((periods.pop(),result))
    (start,old),(end,new) = sorted(snapshots,key=lambda pair:pair[0])
    return {
        code:[[key,old[code].get(key,0),new[code].get(key,0)]
              for key in sorted(old[code].keys()|new[code].keys())]
        for code in old.keys() & new.keys()
    },[start,end]


def screener_seed(path):
    workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    try:
        screener = workbook["Screener"]
        catalogue = [list(row) for row in screener.iter_rows(min_row=4, max_row=136, min_col=2, max_col=7, values_only=True) if all(row[:3])]
        sheets = {"Master":"Master", "Balance_Analysis":"Balance Analysis",
                  "Investor_Type_Analysis":"Investor Type Analysis", "Scripless":"Scripless", "Stockbit":"Stockbit"}
        tickers = {}
        periods = {}
        for source, sheet in sheets.items():
            rows = iter(workbook[sheet].iter_rows(min_row=3 if source=="Master" else 1, values_only=True))
            headers = next(rows)
            ticker_column = headers.index("Code")
            fields = [(name,headers.index(column)) for name, dataset, column, *_ in catalogue
                      if dataset == source and column in headers]
            for row in rows:
                code = row[ticker_column]
                if not isinstance(code, str) or not re.fullmatch(r"[A-Z0-9]{4}", code):
                    continue
                record = tickers.setdefault(code, {"code": code, "name": code})
                if source == "Master":
                    record["name"] = row[headers.index("Name")] or code
                for key, index in fields:
                    value = row[index]
                    if isinstance(value, (int, float, bool)) or isinstance(value, str) and value and not value.startswith("#"):
                        record[key] = value
                if isinstance(row[0], datetime):
                    periods[source] = max(periods.get(source,""),date_label(row[0]))
        preferences = {
            "Market Cap":"cap", "Weight to IHSG":"weight", "Price":"price", "FF BEI":"free",
            "Dividend Yield":"yield", "High Shareholder Concentration List":"hsc", "Sector":"sector",
        }
        for row in tickers.values():
            for original, alias in preferences.items():
                value = row.get(original)
                if original != "High Shareholder Concentration List" or value is not None:
                    row.setdefault(alias, value)
            if isinstance(row["cap"], (int,float)):
                row["cap"] /= 1e12
            for key in ("weight","free","yield"):
                if isinstance(row[key], (int,float)):
                    row[key] *= 100
        return catalogue, list(tickers.values()), periods
    finally:
        workbook.close()


def refresh_screener(root,payload):
    catalogue = payload.get("catalogue",[])
    stocks = {row["code"]:row for row in payload.get("screen",[])}
    if not catalogue:
        return
    sources = files(root,"IHSG_Stock_Data_????-??-??.csv")
    previous = payload.setdefault("screenerPeriods",{})
    if not sources:
        return
    path = sources[-1]
    date = path.stem[-10:]
    if date[:7] <= previous.get("Stockbit","")[:7]:
        return
    with path.open(encoding="utf-8-sig",newline="") as source:
        reader = csv.DictReader(source)
        fields = [(name,column,shape) for name,dataset,column,_,shape,*_ in catalogue
                  if dataset=="Stockbit" and column in (reader.fieldnames or [])]
        for row in reader:
            code = row.get("Code","")
            if not re.fullmatch(r"[A-Z0-9]{4}",code):
                continue
            stock = stocks.setdefault(code,{"code":code,"name":row.get("Name") or code})
            for name,column,shape in fields:
                raw = row[column]
                value = number(raw)
                if value is not None and raw.strip().endswith("%") and "%" in (shape or ""):
                    value /= 100
                stock[name] = value
    previous["Stockbit"] = date
    publish(payload,"screen",list(stocks.values()),["Snapshot gabungan � periode menurut sumber"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed-screener", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raw = args.output.read_bytes()
        payload = json.loads(gzip.decompress(raw) if args.output.suffix==".gz" else raw)
    else:
        payload = {"sources": {}}
    files5 = files(args.folder, "peng-????-??-??-*-lima-persen.xlsx")
    files1 = files(args.folder, "peng-????-??-*-satu-persen.xlsx")
    if files5:
        rows, dates = ownership5(files5[-1])
        if rows != payload.get("own5") or " / ".join(dates) != payload["sources"].get("own5",{}).get("period"):
            publish(payload,"own5",rows,dates)
    if len(files1) >= 2:
        latest = sorted((ownership1(p) for p in sorted({p.name:p for p in files1}.values(), key=lambda p:p.name)[-2:]), key=lambda pair:pair[0])
        (before, previous), (after, current) = latest
        if before >= after:
            raise ValueError("Two distinct monthly ownership periods are required")
        rows = []
        for code, identity, origin in sorted(previous.keys() | current.keys(),key=str):
            key = code, identity, origin
            name, home, kind, *_ = current.get(key) or previous[key]
            new, old = current.get(key), previous.get(key)
            rows.append([code,name,home,kind,new[3] if new else None,old[3] if old else None,
                         "Existing" if new and old else "New" if new else "Exited",
                         new[4] if new else None,old[4] if old else None])
        if rows != payload.get("own1") or " / ".join([before,after]) != payload["sources"].get("own1",{}).get("period"):
            publish(payload,"own1",rows,[before,after])
    history = index_history(args.folder,payload.get("market",[]))
    if history and history != payload.get("market"):
        publish(payload,"market",history,[history[0]["date"],history[-1]["date"]])
    if args.seed_screener:
        payload["catalogue"], rows, payload["screenerPeriods"] = screener_seed(args.seed_screener)
        publish(payload,"screen",rows,["Snapshot Excel awal � periode berbeda menurut sumber"])
    else:
        refresh_screener(args.folder,payload)
    balance = balance_snapshots(args.folder)
    if balance and balance != payload.get("balance"):
        periods = sorted({row[0] for series in balance.values() for row in series})
        publish(payload,"balance",balance,[periods[0],periods[-1]])
    investor, dates = investor_snapshots(args.folder)
    if investor and investor != payload.get("investor"):
        publish(payload,"investor",investor,dates)
    temporary = args.output.with_suffix(".tmp")
    raw = json.dumps(payload,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")
    temporary.write_bytes(gzip.compress(raw,mtime=0) if args.output.suffix==".gz" else raw)
    temporary.replace(args.output)
    print({key:len(value) for key,value in payload.items() if isinstance(value,list)})


if __name__ == "__main__":
    main()
