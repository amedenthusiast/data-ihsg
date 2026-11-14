# Data IHSG

Dashboard statis dengan data IHSG, Screener, dan Stock Detail. Snapshot awal
termasuk katalog Screener dan angka terakhir dari workbook untuk migrasi. Tanda
- berarti sumber tidak menyediakan nilai. Tabel Custom dapat dibuka per 100
ticker dan menyertakan semua kolom kriteria.

## Deploy

Pada Settings  Pages, pilih GitHub Actions. Atur repository variable
`PAGES_ENABLED=true` untuk mengaktifkan workflow. GitHub Pages dapat menyajikan
data secara publik meskipun repository privat. Pastikan distribusi snapshot
dan data sumber yang ditampilkan sesuai dengan akses yang diinginkan.

Workflow dijadwalkan 17.00 UTC (00.00 WIB) dan dapat dijalankan manual. Untuk
refresh, konfigurasikan aplikasi Microsoft Entra dengan akses baca folder
OneDrive `Trading/Data`. Isi repository variables `MS_TENANT_ID`,
`MS_CLIENT_ID`, `ONEDRIVE_DRIVE_ID`, `ONEDRIVE_FOLDER_ID`, serta secret
`MS_CLIENT_SECRET`. Jika secret kosong, deployment hanya memakai snapshot
awal. Kesalahan transfer atau parsing menghentikan deployment.

Sumber langsung sekarang mencakup laporan kepemilikan 5% dan 1%, ekspor IHSG
TSV, Balancepos, klasifikasi investor, dan kolom Stockbit yang tersedia di
ekspor CSV. Kolom turunan Master dan model khusus workbook masih merupakan
snapshot awal sampai rumusnya dipindahkan ke pipeline. Untuk memperbarui
IHSG, ekspor sumber harus memuat Date, Close, dan Net Foreign Buy/Sell.

## Tes lokal

```sh
python -m pip install openpyxl==3.1.5
python build_data.py /path/to/Trading/Data dashboard.json.gz
python -m http.server 8000
```
