#!/usr/bin/env python3
"""Render with a real sing-box binary; validate configs, credentials and permissions.

Usage: python3 tests/test-reality.py /path/to/sing-box
Requires PyYAML on the test machine only. Never installs a service.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import parse_qs, urlsplit

import yaml

binary = str(pathlib.Path(sys.argv[1]).resolve())
script = pathlib.Path(__file__).resolve().parents[1] / 'install-reality.sh'
with tempfile.TemporaryDirectory() as tmp:
    out = pathlib.Path(tmp)
    subprocess.run(['bash', str(script), '--test-render', binary, tmp,
                    'www.microsoft.com'], check=True)
    for name in ('server.json', 'check-client.json'):
        subprocess.run([binary, 'check', '-c', str(out / name)], check=True)
    server = json.loads((out / 'server.json').read_text())['inbounds'][0]
    client = json.loads((out / 'check-client.json').read_text())['outbounds'][0]
    clash = yaml.safe_load((out / 'clash-verge.yaml').read_text())
    node = clash['proxies'][0]
    uri = urlsplit((out / 'vless-uri.txt').read_text().strip())
    query = parse_qs(uri.query)
    assert uri.scheme == 'vless' and uri.hostname == node['server']
    assert uri.port == node['port'] == server['listen_port']
    assert str(uuid.UUID(uri.username)) == node['uuid'] == client['uuid'] == server['users'][0]['uuid']
    assert query['flow'] == [node['flow']] == [client['flow']]
    assert query['pbk'] == [node['reality-opts']['public-key']] == [client['tls']['reality']['public_key']]
    assert query['sid'] == [node['reality-opts']['short-id']] == server['tls']['reality']['short_id']
    assert query['sni'] == [node['servername']] == [server['tls']['server_name']]
    assert query['security'] == ['reality'] and node['skip-cert-verify'] is False
    assert node['network'] == 'tcp' and node['tls'] is True
    assert clash['rules'][-1] == 'MATCH,PROXY'
    assert 'FINAL,PROXY' in (out / 'shadowrocket.conf').read_text()
    private = server['tls']['reality']['private_key']
    for name in ('clash-verge.yaml', 'shadowrocket.conf', 'vless-uri.txt'):
        assert private not in (out / name).read_text()
    for file in out.iterdir():
        assert file.stat().st_mode & 0o777 == 0o600
    bad = subprocess.run(['bash', str(script), '--test-render', binary, tmp,
                          'example.com/path'], capture_output=True)
    assert bad.returncode != 0
print('PASS: sing-box config validation, client credential consistency, private-key isolation, permissions and invalid input rejection')
