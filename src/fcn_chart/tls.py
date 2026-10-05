"""HTTPS 憑證：讓連線同時信任 certifi 與 Windows 憑證存放區。

公司網路常以自有根憑證做 HTTPS 檢查，該憑證只裝在 Windows 憑證存放區；
yfinance 底層的 curl_cffi 預設只用 certifi，會出現「憑證簽發者不明」而連不上。
"""

import functools
import ssl
import tempfile
from pathlib import Path

import certifi

WINDOWS_STORES = ("ROOT", "CA")
BUNDLE_NAME = "fcn-chart-ca-bundle.pem"


def windows_certificates() -> list[bytes]:
    """Windows 憑證存放區中可用於伺服器驗證的憑證（DER）；非 Windows 回傳空清單。"""
    if not hasattr(ssl, "enum_certificates"):
        return []
    certs = []
    for store in WINDOWS_STORES:
        for der, encoding, trust in ssl.enum_certificates(store):
            # trust 為 True（全用途）或 OID 集合；1.3.6.1.5.5.7.3.1 = 伺服器驗證
            if encoding == "x509_asn" and (trust is True or "1.3.6.1.5.5.7.3.1" in trust):
                certs.append(der)
    return certs


def build_bundle(certifi_pem: str, extra_der: list[bytes]) -> str:
    extra = [ssl.DER_cert_to_PEM_cert(der) for der in dict.fromkeys(extra_der)]
    return certifi_pem.rstrip("\n") + "\n" + "".join(extra)


@functools.cache
def ca_bundle_path() -> str:
    """certifi＋Windows 憑證的 PEM 檔路徑；沒有 Windows 憑證時直接用 certifi。"""
    extra = windows_certificates()
    if not extra:
        return certifi.where()
    path = Path(tempfile.gettempdir()) / BUNDLE_NAME
    certifi_pem = Path(certifi.where()).read_text(encoding="utf-8")  # 註解含非 ASCII 字元
    path.write_text(build_bundle(certifi_pem, extra), encoding="utf-8")
    return str(path)
