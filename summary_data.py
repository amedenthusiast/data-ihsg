"""Export the workbook's Stock Detail Summary inputs by ticker."""
import argparse
import csv
import gzip
import json
import re
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

from build_data import number


MASTER = {
    "price":"Last Price", "marketCap":"Market Cap", "shares":"No. of Shares", "scripless":"Total Scripless",
    "bei":"FF BEI", "ftse":"FF FTSE", "ffMsci":"Minimum-Adjusted FF (MSCI Rounding)", "hsc":"HSC",
    "local":"Local (%)", "foreign":"Foreign (%)", "institutionChange":"1 Month Change_Institution",
    "foreignChange":"1 Month Change_Foreign", "retailChange":"1 Month Change_Ritel",
    "standard":"Currently Included in MSCI Global Standards Cap", "small":"Currently Included in MSCI Small Cap",
    "standardLow":"Price Needed to Downgrade from MSCI Global Standards Cap with buffer (based on FFMC)",
    "standardHigh":"Price Needed to Downgrade from MSCI Global Standards Cap without buffer (based on FFMC)",
    "smallLow":"Price Needed to Downgrade From MSCI Global Small Cap with buffer",
    "smallHigh":"Price Needed to Downgrade From MSCI Global Small Cap without buffer",
    "upgrade":"Price Needed to Upgrade to MSCI Global Standards Cap",
    "enterStandard":"Price Needed to Enter MSCI Standard Cap (based on FFMC)",
    "enterSmall":"Price Needed to Enter MSCI Small Cap (based on FFMC)",
    "progressSmall":"Progress of Entering MSCI Global Small Cap",
}
STOCKBIT = {"dailyChange":"Change%", "dailyPrice":"Price", "holders":"Number of Shareholders"}
for period in ("1M","3M","6M","1Y"):
    relative="of " if period in {"6M","1Y"} else ""
    STOCKBIT["holders"+period]=f"Number of Shareholders (# of changes {period})"
    STOCKBIT["holdersPct"+period]=f"Number of Shareholders (% {relative}changes {period})"


def stockbit_values(row):
    values={}
    for key,column in STOCKBIT.items():
        raw=row.get(column)
        value=number(raw)
        if value is not None:
            if isinstance(raw,str) and raw.strip().endswith("%"):
                value/=100
            values[key]=value
    return values


def main():
    p=argparse.ArgumentParser()
    p.add_argument("folder",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--seed-xlsx",type=Path)
    args=p.parse_args()
    payload=json.loads(gzip.decompress(args.output.read_bytes())) if args.output.exists() else {"stocks":{}}
    stocks=payload["stocks"]
    if args.seed_xlsx:
        book=load_workbook(args.seed_xlsx,read_only=True,data_only=True)
        for sheet in ("Master","Scripless","Balance Analysis","Stockbit"):
            rows=iter(book[sheet].iter_rows(min_row=3 if sheet=="Master" else 1,values_only=True))
            headers=next(rows)
            code_index=headers.index("Code")
            for cells in rows:
                code=cells[code_index]
                if not isinstance(code,str) or not re.fullmatch(r"[A-Z0-9]{4}",code):
                    continue
                row=dict(zip(headers,cells))
                stock=stocks.setdefault(code,{})
                if sheet=="Master":
                    stock.update({key:row[column] for key,column in MASTER.items()
                                  if isinstance(row[column],(int,float,bool)) or row[column] in ("Yes","No")})
                elif sheet=="Scripless":
                    for key,column in (("scriplessChange","Scripless Change"),("scriplessPctChange","%Scripless Change")):
                        if isinstance(row[column],(int,float)):
                            stock[key]=row[column]
                    current,old=row["Total Scripless"],row["StatisEfek PRE.Total Scripless"]
                    if isinstance(current,(int,float)) and isinstance(old,(int,float)):
                        stock.setdefault("scriplessChange",current-old)
                        if old>0:
                            stock.setdefault("scriplessPctChange",current/old-1)
                elif sheet=="Balance Analysis":
                    values=[row[key] for key in ("Sec. Num","Local ID","Foreign ID")]
                    if all(isinstance(v,(int,float)) for v in values) and values[0]>0:
                        stock["retail"]=(values[1]+values[2])/values[0]
                else:
                    stock.update(stockbit_values(row))
                    if isinstance(row["Date"],datetime) and "dailyChange" in stock:
                        stock["dailyDate"]=row["Date"].date().isoformat()
        book.close()
    files=sorted(args.folder.rglob("IHSG_Stock_Data_????-??-??.csv"),key=lambda x:x.name)
    if files:
        path=files[-1]
        day=path.stem[-10:]
        with path.open(encoding="utf-8-sig",newline="") as source:
            for row in csv.DictReader(source):
                stock=stocks.get(row.get("Code"))
                if stock is None or day<stock.get("dailyDate",""):
                    continue
                values=stockbit_values(row)
                if "dailyChange" not in values:
                    values.pop("dailyPrice",None)
                elif "dailyPrice" not in values:
                    stock.pop("dailyPrice",None)
                stock.update(values)
                if "dailyChange" in values:
                    stock["dailyDate"]=day
    if stocks:
        temporary=args.output.with_suffix(".tmp")
        temporary.write_bytes(gzip.compress(json.dumps(payload,separators=(",",":"),allow_nan=False).encode(),mtime=0))
        temporary.replace(args.output)
    print(f"{len(stocks)} Stock Detail summaries")


if __name__=="__main__":
    main()
