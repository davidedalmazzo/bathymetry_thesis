# Block36 download status: NOT EXECUTED

Neither the full SAFE/ZIP nor any measurement TIFF was downloaded. The only
authorized live operation in this block is the bounded metadata preflight.

## Resume the metadata preflight

Copy the tracked `.env.example` to the Git-ignored root `.env`, without
overwriting an existing file, and fill `CDSE_USERNAME` and `CDSE_PASSWORD`.
Do not put either value on the command line or in a tracked file. As an
alternative, set `CDSE_ACCESS_TOKEN` in the process environment. Then run from
the repository root:

```powershell
.\.venv-umbra-thesis\Scripts\python.exe code\run_block36_s1_iw_preflight.py fetch
```

The command resumes the existing named tranche; it does not reset its ledger.
It is allow-listed to `manifest.safe`, three VV annotation XML files and, only
after the pertinent subswath is identified, its calibration/noise XML pair.
It performs the official CDSE login automatically. If the account requires
MFA, it prompts once for the TOTP in the local terminal without echoing it.

## Prepared full-product command (do not run automatically)

`GATE.json` is now `READY`, but this does not itself authorize the full-product
transfer. Only after separate user authorization:

```powershell
.\.venv-umbra-thesis\Scripts\python.exe code\download_cdse_product.py --destination "duck_frf/source_products"
```

The destination is configurable but must remain under the repository root.
The downloader checks free space (remaining bytes plus 1 GiB), preserves a
`.part` file for safe resume, requires a matching Range response, checks the
catalogue size 7,799,368,890 bytes and vendor MD5
`d1886a92315be184489eea0e072c0578`, then renames atomically. The bearer is
loaded in memory and is never an argument or logged value. Cross-origin bearer
redirects are refused.
