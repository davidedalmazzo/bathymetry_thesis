# Prepared official download — NOT executed or authorized by this screening

Product UUID: `c49a9c1f-9b00-5676-ab05-683975d898a2`.
Catalogue size: 7,799,368,890 bytes; delivered ZIP size not independently known.
First prefer the small authenticated manifest/VV annotation preflight described
in REPORT.md. Full SAR download requires a new explicit user instruction,
storage check and private CDSE access token. Do not store credentials in Git.

Prepared PowerShell command, to run ONLY after separate download authorization
and creation of the explicitly named local destination folder:

```powershell
curl.exe --fail --location --proto '=https' --proto-redir '=https' --header "Authorization: Bearer $env:CDSE_ACCESS_TOKEN" 'https://download.dataspace.copernicus.eu/odata/v1/Products(c49a9c1f-9b00-5676-ab05-683975d898a2)/$value' --output 'duck_frf/Block35_s1_spatial_selection/source_products/S1A_IW_SLC__1SDV_20211028T230636_20211028T230703_040326_04C765_B6FA.zip'
```

Source ZIP/products are excluded from Git. This command neither runs during
screening nor forwards bearer credentials to a different origin with
`--location-trusted`. Follow the official CDSE authentication/download procedure
if an authenticated redirect requires additional handling; do not bypass access.

Documentation verified during this tranche:
[CDSE OData](https://documentation.dataspace.copernicus.eu/APIs/OData.html).
