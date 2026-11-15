"""Download only dashboard inputs from the configured Microsoft Graph folder."""
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


GRAPH = "https://graph.microsoft.com/v1.0"
WANTED = re.compile(
    r"(?:ds_\d{6}\.pdf|Balancepos\d{8}\.txt|IHSG_Trading_Data_.*\.tsv|IHSG_Stock_Data_\d{4}-\d{2}-\d{2}\.csv|"
    r"peng-\d{4}-\d{2}(?:-\d{2})?-\d+-(?:lima-persen|satu-persen|klasifikasi)\.xlsx)$",
    re.IGNORECASE,
)


def graph(url, token):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com":
        raise ValueError("Unexpected Graph URL")
    return Request(url,headers={"Authorization":"Bearer "+token})


def main():
    tenant, client, secret, drive, folder = (os.environ[key] for key in (
        "MS_TENANT_ID","MS_CLIENT_ID","MS_CLIENT_SECRET","ONEDRIVE_DRIVE_ID","ONEDRIVE_FOLDER_ID"))
    body = urlencode({"client_id":client,"client_secret":secret,"grant_type":"client_credentials",
                      "scope":"https://graph.microsoft.com/.default"}).encode()
    with urlopen(f"https://login.microsoftonline.com/{quote(tenant,safe='')}/oauth2/v2.0/token",body,timeout=45) as response:
        token = json.load(response)["access_token"]
    base = f"{GRAPH}/drives/{quote(drive,safe='')}/items/"
    queue = [(folder,Path(os.environ["INPUT_FOLDER"]))]
    while queue:
        parent, destination = queue.pop()
        url = base+quote(parent,safe="")+"/children?$select=id,name,file,folder,@microsoft.graph.downloadUrl"
        while url:
            with urlopen(graph(url,token),timeout=45) as response:
                page = json.load(response)
            for item in page["value"]:
                name = item["name"]
                if name in {".",".."} or "/" in name or "\\" in name:
                    raise ValueError("Unexpected OneDrive item name")
                target = destination/name
                if "folder" in item:
                    queue.append((item["id"],target))
                elif "file" in item and WANTED.fullmatch(name):
                    download_url = item.get("@microsoft.graph.downloadUrl")
                    if not download_url or urlsplit(download_url).scheme!="https":
                        raise ValueError("Missing HTTPS download URL")
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with urlopen(download_url,timeout=90) as response, target.open("wb") as out:
                        shutil.copyfileobj(response,out)
            url = page.get("@odata.nextLink")


if __name__ == "__main__":
    main()
