from fio_cli.manifest import endpoint_map, load_endpoints


def test_manifest_has_get_endpoints() -> None:
	endpoints = load_endpoints()
	assert endpoints
	assert any(e.method == "GET" for e in endpoints)


def test_blacklisted_auth_endpoints_are_omitted() -> None:
	endpoints = load_endpoints()
	assert all(not e.path.lstrip("/").startswith("auth") for e in endpoints)
	assert all(not path.startswith("auth") for path in endpoint_map())
