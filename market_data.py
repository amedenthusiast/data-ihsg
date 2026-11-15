"""Update the IHSG series from IDX daily statistics PDFs and matching TSVs."""
import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


NUM = r"[-+]?[0-9][0-9,]*(?:\.[0-9]+)?"


def numeric(value):
    return float(value.replace(",", "").rstrip("%"))


def chart_participation(page):
    """Read the rounded Today split from the two solid fills in the IDX chart."""
    heading = page.search_for("Investor Composition")
    if len(heading)!=1:
        return {}
    for image in page.get_images():
        for rect in page.get_image_rects(image[0]):
            if not (rect.x0 < heading[0].x0 < rect.x1 and 0 < rect.y0-heading[0].y1 < 30):
                continue
            import pymupdf
            pixels = pymupdf.Pixmap(page.parent,image[0])
            if pixels.n != 3 or pixels.width < 150:
                continue
            estimates = []
            for fraction in (.16,.18,.20,.21,.22):
                x = round(pixels.width*fraction)
                counts=Counter()
                for y in range(pixels.height):
                    r,g,b=pixels.pixel(x,y)
                    if r>175 and 80<g<158 and b<75:
                        counts["local"]+=1
                    if r<85 and 105<g<180 and 130<b<210:
                        counts["foreign"]+=1
                total=counts.total()
                if total>=pixels.height*.65:
                    estimates.append(100*counts["foreign"]/total)
            if len(estimates)>=3:
                estimates.sort()
                value=estimates[len(estimates)//2]
                if estimates[-1]-estimates[0]<2 and .2<value<99.8 and abs(value-round(value))<=.36:
                    foreign=round(value)
                    return {"foreign":foreign,"local":100-foreign}
    return {}


def parse_pdf(path):
    import pymupdf
    with pymupdf.open(path) as pdf:
        first, second = (pdf[i].get_text() for i in (0, 1))
        participation=chart_participation(pdf[1])
    label = re.search(r"\b\d{1,2} [A-Za-z]+ 20\d{2}\b", first)
    price = re.search(r"IDX Composite Index \(IHSG\)\s*("+NUM+")", first)
    net = re.search(r"\bToday\s*(Net Buy|Net Sell)\s*("+NUM+r")\s*"+NUM+r"\s*\(billion IDR\)", second)
    if not all((label,price,net)):
        raise ValueError("Unsupported IDX daily statistics layout")
    date = datetime.strptime(label[0],"%d %B %Y").date()
    if path.stem.lower()!=date.strftime("ds_%y%m%d"):
        raise ValueError("Report date disagrees with filename")
    flow = abs(numeric(net[2])) * (-1 if net[1]=="Net Sell" else 1)
    levels = re.search(r"\bPrevious\s+Highest\s+Lowest\s+("+NUM+r")\s+("+NUM+r")\s+("+NUM+r")",first)
    opening = re.search(r"(?m)^Opening(?: Price)?\s+("+NUM+r")\s*$",first)
    close = numeric(price[1])
    ohlc = {}
    if levels and numeric(levels[3]) <= close <= numeric(levels[2]):
        ohlc.update(high=numeric(levels[2]),low=numeric(levels[3]))
        if opening and ohlc["low"]<=numeric(opening[1])<=ohlc["high"]:
            ohlc["open"]=numeric(opening[1])
    return {"date":date.isoformat(),"price":close,"flow":flow/1000,**participation,**ohlc}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("folder",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--seed-xlsx",type=Path)
    args=parser.parse_args()
    previous=json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {}
    rows={row["date"]:row for row in previous.get("rows",[])}
    if args.seed_xlsx:
        from openpyxl import load_workbook
        w=load_workbook(args.seed_xlsx,read_only=True,data_only=True,keep_links=False)
        records = iter(w["IHSG Data"].values)
        headers = next(row for row in records if row[0]=="Date")
        fields = {key:headers.index(label) for key,label in (("open","Open"),("high","High"),("low","Low"),("price","Close")) if label in headers}
        for row in records:
            if isinstance(row[0],datetime):
                date=row[0].date().isoformat()
                participation={name:row[i]*100 for name,i in (("foreign",11),("local",12)) if isinstance(row[i],(int,float)) and 0<=row[i]<=1}
                rows[date]={"date":date,**participation}
                rows[date].update({key:row[i] for key,i in fields.items() if isinstance(row[i],(int,float)) and row[i]>0})
                if isinstance(row[13],(int,float)):
                    rows[date]["flow"]=row[13]/1e12
        w.close()
    for path in sorted(args.folder.rglob("IHSG_Trading_Data_*.tsv")):
        with path.open(encoding="utf-8-sig",newline="") as source:
            for row in csv.DictReader(source,delimiter="\t"):
                date=datetime.strptime(row["Date"],"%Y-%m-%d").date().isoformat()
                fields={"price":"Close","open":"Open","high":"High","low":"Low","flow":"Net Foreign Buy/Sell","foreign":"Foreign (%)","local":"Domestic (%)"}
                try:
                    values={k:numeric(row[v]) for k,v in fields.items() if row.get(v) not in (None,"","-")}
                except ValueError:
                    continue
                if "flow" in values:
                    values["flow"]/=1e12
                record=rows.get(date,{})
                rows[date]={**values,**record,"date":date}
    for path in sorted(args.folder.rglob("ds_*.pdf")):
        try:
            row=parse_pdf(path)
        except (RuntimeError,ValueError,IndexError) as exc:
            print(f"Skipped {path.name}: {exc}")
            continue
        rows[row["date"]]={**rows.get(row["date"],{}),**row}
    output=sorted((row for row in rows.values() if any(key in row for key in ("price","flow","foreign","local"))),key=lambda row:row["date"])
    if not output:
        raise ValueError("No IHSG observations")
    if output!=previous.get("rows"):
        payload={"update":datetime.now(timezone.utc).isoformat(timespec="seconds"),"rows":output}
        temporary=args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload,separators=(",",":"),allow_nan=False),encoding="utf-8")
        temporary.replace(args.output)
    print(f"{len(output)} trading days, latest {output[-1]['date']}")


if __name__=="__main__":
    main()
