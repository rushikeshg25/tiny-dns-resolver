from tiny_dns_resolver.resolver import resolve

def test_resolve_google():
    ip = resolve("google.com")
    assert ip != "Not found"
    parts = ip.split(".")
    assert len(parts) == 4
    assert all(part.isdigit() for part in parts)
