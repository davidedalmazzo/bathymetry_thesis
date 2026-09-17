"""THREDDS discovery from declared catalogs/services, never guessed monthly filenames."""
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from .data import das_attributes, dds_shapes
from .transport import FetchError

ROOT = "https://chldata.erdc.dren.mil/thredds/catalog/frf/catalog.xml"
NS = {"t": "http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0"}
XLINK = "{http://www.w3.org/1999/xlink}href"


def catalog(transport, url):
    root = ET.fromstring(transport.get(url))
    refs = [{"name": r.get("name"), "url": urljoin(url, r.get(XLINK))} for r in root.findall(".//t:catalogRef",NS)]
    services = {s.get("serviceType"): urljoin(url, s.get("base", "")) for s in root.findall(".//t:service",NS) if s.get("serviceType") != "compound"}
    products = []
    for dataset in root.findall(".//t:dataset",NS):
        path = dataset.get("urlPath")
        if path:
            products.append({"name": dataset.get("name"), "url_path": path,
                             "services": {kind: base+path for kind, base in services.items()},
                             "catalog_source": url})
    return {"references": refs, "products": products, "services": services}


def discover_month(transport, instrument_url, month):
    listing = catalog(transport, instrument_url)
    year = next((r for r in listing["references"] if r["name"] == month[:4]), None)
    if year is None:
        return [], {"status": "year_not_listed_in_catalog", "source": instrument_url,
                    "available_years": [r["name"] for r in listing["references"]]}
    annual = catalog(transport, year["url"])
    products = [p for p in annual["products"] if re.search(r"(?<!\d)"+month+r"(?!\d)",p["name"] or "")]
    return products, {"status": "catalog_month_match" if products else "month_not_listed_in_catalog",
                      "source": year["url"], "not_global_absence": True}


def metadata(transport, product):
    url = product["services"].get("OpenDAP")
    if not url:
        raise FetchError("product_not_supported_no_verified_opendap_adapter")
    attrs = das_attributes(transport.get(url+".das").decode("utf-8","replace"))
    shapes = dds_shapes(transport.get(url+".dds").decode("utf-8","replace"))
    return {"attributes": attrs, "shapes": shapes, "source": url,
            "available_services": product["services"], "auth": "anonymous", "tls": "verified"}
