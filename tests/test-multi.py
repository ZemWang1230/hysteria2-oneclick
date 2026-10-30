#!/usr/bin/env python3
"""Offline render and certificate checks; requires sing-box and PyYAML."""
import json
import pathlib
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import yaml

root = pathlib.Path(__file__).resolve().parents[1]
script = root / 'install-multi.sh'
binary = str(pathlib.Path(sys.argv[1]).resolve())
def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
with tempfile.TemporaryDirectory() as tmp:
    p = pathlib.Path(tmp)
    out = p / 'out'
    run('bash', str(script), '--test-render', binary, str(out), 'www.microsoft.com')
    run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=Test CA', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-keyout', str(p/'ca.key'), '-out', str(out/'root-ca.crt'))
    run('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=8.8.8.8', '-keyout', str(out/'server.key'), '-out', str(p/'csr'))
    (p/'ext').write_text('subjectAltName=IP:8.8.8.8\nbasicConstraints=critical,CA:FALSE\nextendedKeyUsage=serverAuth\n')
    run('openssl', 'x509', '-req', '-in', str(p/'csr'), '-CA', str(out/'root-ca.crt'), '-CAkey', str(p/'ca.key'), '-CAcreateserial', '-out', str(out/'server.crt'), '-days', '1', '-extfile', str(p/'ext'))
    source = script.read_text().split('augment() {\n', 1)[1].split('\nshow() {', 1)[0]
    run('bash', '-c', 'augment() {\n' + source + '\naugment "$1" "$2" "$3" "$4" "$5"', '_', str(out), '8.8.8.8', '22111', '22222', '22333')
    run(binary, 'check', '-c', str(out/'server.json'))
    run('openssl', 'verify', '-CAfile', str(out/'root-ca.crt'), '-verify_ip', '8.8.8.8', str(out/'server.crt'))
    config = json.loads((out/'server.json').read_text())
    yaml_config = yaml.safe_load((out/'clash-verge.yaml').read_text())
    assert {x['type'] for x in config['inbounds']} == {'vless','shadowsocks','hysteria2','tuic'}
    assert [x['name'] for x in yaml_config['proxies']] == ['REALITY','SS','HY2','TUIC']
    tuic = next(x for x in config['inbounds'] if x['type'] == 'tuic')
    assert tuic['tls']['alpn'] == ['h3'] == yaml_config['proxies'][3]['alpn']
    assert yaml_config['log-level'] == 'warning'
    if len(sys.argv) > 2:
        run(str(pathlib.Path(sys.argv[2]).resolve()), '-t', '-f', str(out/'clash-verge.yaml'), '-d', str(p))
    assert yaml_config['proxy-groups'][0]['proxies'] == ['REALITY','SS','HY2','TUIC']
    assert all(not x.get('skip-cert-verify') for x in yaml_config['proxies'])
    expected_ports = [18443, 22111, 22222, 22333]
    assert [x['listen_port'] for x in config['inbounds']] == expected_ports
    assert [x['port'] for x in yaml_config['proxies']] == expected_ports
    nodes = (out/'shadowrocket-nodes.txt').read_text().splitlines()
    assert [urlsplit(x).scheme for x in nodes] == ['vless','ss','hysteria2','tuic']
    assert [urlsplit(x).port for x in nodes] == expected_ports
    for f in ('clash-verge.yaml','shadowrocket.conf','shadowrocket-nodes.txt','root-ca.crt'):
        assert 'PRIVATE KEY' not in (out/f).read_text()
        assert (out/f).stat().st_mode & 0o777 == 0o600
# Exercise port selection with a mocked ss so no privileged operations are needed.
import os
with tempfile.TemporaryDirectory() as tmp:
    p = pathlib.Path(tmp)
    ss = p/'ss'
    ss.write_text('#!/bin/sh\nexit 0\n')
    ss.chmod(0o755)
    selection = script.read_text().split("<<'PYPORTS'\n", 1)[1].split('\nPYPORTS', 1)[0]
    env = dict(os.environ, PATH=tmp + os.pathsep + os.environ['PATH'])
    result = subprocess.run([sys.executable, '-', ''], input=selection, text=True, capture_output=True, env=env, check=True)
    ports = list(map(int, result.stdout.split()))
    assert len(ports) == len(set(ports)) == 4 and all(20000 <= port <= 29999 for port in ports)
    result = subprocess.run([sys.executable, '-', '18080'], input=selection, text=True, capture_output=True, env=env)
    assert result.returncode != 0
    ss.write_text('#!/bin/sh\necho occupied\n')
    result = subprocess.run([sys.executable, '-', '21111'], input=selection, text=True, capture_output=True, env=env)
    assert result.returncode != 0
print('PASS: random port selection, server config, certificate chain, client exports, permissions')
