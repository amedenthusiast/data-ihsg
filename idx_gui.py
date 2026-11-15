"""Private desktop interface for an existing IDX CLI installation."""
import csv
import json
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


COMMANDS = ("Quote", "History", "Ownership")
PERIODS = ("1mo", "3mo", "6mo", "1y")


def cli(*args):
    command = ["idx", *args]
    if sys.platform == "win32":
        command = ["wsl.exe", "--exec", "sh", "-lc",
                   'PATH="$HOME/.local/bin:$PATH"; export PATH; exec idx "$@"', *command]
    completed = subprocess.run(command, check=True, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120,
                               creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    return completed.stdout


def query(symbol, operation, period):
    symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{4}",symbol):
        raise ValueError("Masukkan satu ticker IDX, misalnya BBRI.")
    if operation == "Quote":
        args = ["stocks","quote",symbol]
    elif operation == "History" and period in PERIODS:
        args = ["stocks","history",symbol,"--period",period]
    elif operation == "Ownership":
        args = ["ownership","ticker",symbol]
    else:
        raise ValueError("Jenis kueri atau periodenya tidak valid.")
    return json.loads(cli("-o","json",*args))


def table_records(data):
    if isinstance(data,list):
        return [row for row in data if isinstance(row,dict)]
    if isinstance(data,dict):
        for key in ("data","holdings","holders","shareholders","quotes","history","prices","items","results"):
            if isinstance(data.get(key),(dict,list)) and (rows:=table_records(data[key])):
                return rows
        return [data]
    return []


class App:
    def __init__(self, root):
        self.root=root
        root.title("IDX CLI")
        root.geometry("930x560")
        root.minsize(565,330)
        self.result=None
        self.rows=[]
        self.fields=[]
        self.busy=False
        self.status=tk.StringVar(value="Masukkan ticker dan pilih jenis kueri.")
        self.symbol=tk.StringVar(value="BBRI")
        self.operation=tk.StringVar(value=COMMANDS[0])
        self.period=tk.StringVar(value=PERIODS[1])
        controls=ttk.Frame(root,padding=14)
        controls.pack(fill="x")
        for column,label in enumerate(("Ticker","Kueri","Periode History")):
            ttk.Label(controls,text=label).grid(row=0,column=column,sticky="w",padx=4)
        ttk.Entry(controls,textvariable=self.symbol,width=11).grid(row=1,column=0,padx=4)
        ttk.Combobox(controls,textvariable=self.operation,values=COMMANDS,width=14,state="readonly").grid(row=1,column=1,padx=4)
        ttk.Combobox(controls,textvariable=self.period,values=PERIODS,width=14,state="readonly").grid(row=1,column=2,padx=4)
        self.run=ttk.Button(controls,text="Ambil data",command=self.start)
        self.run.grid(row=1,column=3,padx=4)
        self.sync=ttk.Button(controls,text="Sinkron KSEI ≥1%",command=lambda:self.start(sync=True))
        self.sync.grid(row=1,column=4,padx=4)
        frame=ttk.Frame(root,padding=(14,0,14,0))
        frame.pack(fill="both",expand=True)
        self.grid=ttk.Treeview(frame,show="headings",selectmode="browse")
        scrollbar=ttk.Scrollbar(frame,orient="vertical",command=self.grid.yview)
        horizontal=ttk.Scrollbar(frame,orient="horizontal",command=self.grid.xview)
        self.grid.configure(yscrollcommand=scrollbar.set,xscrollcommand=horizontal.set)
        self.grid.grid(row=0,column=0,sticky="nsew")
        scrollbar.grid(row=0,column=1,sticky="ns")
        horizontal.grid(row=1,column=0,sticky="ew")
        frame.grid_rowconfigure(0,weight=1)
        frame.grid_columnconfigure(0,weight=1)
        footer=ttk.Frame(root,padding=14)
        footer.pack(fill="x")
        ttk.Label(footer,textvariable=self.status,wraplength=700).pack(side="left",fill="x",expand=True)
        self.save=ttk.Button(footer,text="Simpan hasil",state="disabled",command=self.export)
        self.save.pack(side="right")

    def start(self,sync=False):
        if self.busy:
            return
        self.busy=True
        for button in (self.run,self.sync,self.save):
            button.configure(state="disabled")
        self.status.set("Menyinkronkan register KSEI…" if sync else "Mengambil data…")
        symbol, operation, period=self.symbol.get(),self.operation.get(),self.period.get()
        def worker():
            try:
                result=cli("ownership","sync") if sync else query(symbol,operation,period)
                self.root.after(0,self.finish,result,sync,None)
            except (OSError,ValueError,subprocess.SubprocessError) as error:
                detail=(getattr(error,"stderr","") or str(error)).strip()[:350]
                self.root.after(0,self.finish,None,sync,detail)
        threading.Thread(target=worker,daemon=True).start()

    def finish(self,result,sync,error):
        self.busy=False
        for button in (self.run,self.sync):
            button.configure(state="normal")
        if error:
            self.status.set("Kueri gagal. Periksa instalasi IDX CLI, koneksi data, atau sinkronisasi KSEI.")
            messagebox.showerror("IDX CLI",error,parent=self.root)
        elif sync:
            self.status.set("Register tersinkron. Pilih Ownership lalu Ambil data.")
        else:
            self.result=result
            self.rows=table_records(result)
            self.fields=list(dict.fromkeys(key for row in self.rows for key in row))
            self.grid.delete(*self.grid.get_children())
            self.grid.configure(columns=[str(i) for i in range(len(self.fields))])
            for i,field in enumerate(self.fields):
                self.grid.heading(str(i),text=field)
                self.grid.column(str(i),width=145,anchor="w")
            for row in self.rows:
                self.grid.insert("","end",values=[row.get(field,"") for field in self.fields])
            self.status.set(f"{len(self.rows)} baris. Hasil tersimpan lokal saat Anda memilih Simpan hasil.")
        self.save.configure(state="normal" if self.result is not None else "disabled")

    def export(self):
        path=filedialog.asksaveasfilename(parent=self.root,defaultextension=".json",
                                          filetypes=[("JSON","*.json"),("CSV","*.csv")])
        if path:
            try:
                with open(path,"w",encoding="utf-8",newline="") as output:
                    if path.lower().endswith(".csv"):
                        writer=csv.DictWriter(output,fieldnames=self.fields)
                        writer.writeheader()
                        writer.writerows(self.rows)
                    else:
                        json.dump(self.result,output,ensure_ascii=False,indent=2)
            except OSError as error:
                messagebox.showerror("Simpan hasil",str(error),parent=self.root)


if __name__=="__main__":
    root=tk.Tk()
    App(root)
    root.mainloop()
