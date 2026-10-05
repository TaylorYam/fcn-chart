import ssl

from fcn_chart import tls

CERTIFI_PEM = "# certifi\n-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n"


def test_build_bundle_appends_extra_certs_once():
    der = b"\x30\x03\x02\x01\x01"
    bundle = tls.build_bundle(CERTIFI_PEM, [der, der])
    assert bundle.startswith(CERTIFI_PEM)
    assert bundle.count("BEGIN CERTIFICATE") == 2
    assert ssl.DER_cert_to_PEM_cert(der) in bundle


def test_windows_certificates_filters_by_server_auth(monkeypatch):
    entries = {
        "ROOT": [(b"root", "x509_asn", True), (b"pkcs", "pkcs_7_asn", True)],
        "CA": [
            (b"server", "x509_asn", {"1.3.6.1.5.5.7.3.1"}),
            (b"email", "x509_asn", {"1.3.6.1.5.5.7.3.4"}),
        ],
    }
    monkeypatch.setattr(tls.ssl, "enum_certificates", lambda store: entries[store], raising=False)
    assert tls.windows_certificates() == [b"root", b"server"]


def test_ca_bundle_falls_back_to_certifi_without_windows_certs(monkeypatch):
    monkeypatch.setattr(tls, "windows_certificates", lambda: [])
    tls.ca_bundle_path.cache_clear()
    try:
        assert tls.ca_bundle_path() == tls.certifi.where()
    finally:
        tls.ca_bundle_path.cache_clear()
