import ssl

from fcn_chart import network

CERTIFI_PEM = "# certifi\n-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n"


def test_build_bundle_appends_extra_certs_once():
    der = b"\x30\x03\x02\x01\x01"
    bundle = network.build_bundle(CERTIFI_PEM, [der, der])
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
    monkeypatch.setattr(
        network.ssl, "enum_certificates", lambda store: entries[store], raising=False
    )
    assert network.windows_certificates() == [b"root", b"server"]


def test_ca_bundle_falls_back_to_certifi_without_windows_certs(monkeypatch):
    monkeypatch.setattr(network, "windows_certificates", lambda: [])
    network.ca_bundle_path.cache_clear()
    try:
        assert network.ca_bundle_path() == network.certifi.where()
    finally:
        network.ca_bundle_path.cache_clear()


def test_system_proxies_prefers_environment(monkeypatch):
    monkeypatch.setattr(
        network.urllib.request,
        "getproxies_environment",
        lambda: {"https": "http://env:8080", "no": "x"},
    )
    monkeypatch.setattr(
        network.urllib.request,
        "getproxies_registry",
        lambda: {"https": "https://reg:8080"},
        raising=False,
    )
    assert network.system_proxies() == {"https": "http://env:8080"}


def test_system_proxies_falls_back_to_windows_settings(monkeypatch):
    monkeypatch.setattr(network.urllib.request, "getproxies_environment", lambda: {})
    registry = {"http": "http://corp:3128", "https": "https://corp:3128", "ftp": "ftp://corp:21"}
    monkeypatch.setattr(
        network.urllib.request, "getproxies_registry", lambda: registry, raising=False
    )
    assert network.system_proxies() == {"http": "http://corp:3128", "https": "http://corp:3128"}
