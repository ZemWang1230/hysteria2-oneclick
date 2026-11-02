"""Hysteria 2 configuration, based on yeahwu/v2ray-wss hy2.sh (Apache-2.0).

This module only renders data; it does not write files or start services.
The reference configuration deliberately disables TLS certificate verification.
"""
import ipaddress
from urllib.parse import urlencode

WINDOW_STREAM = 26843545
WINDOW_CONN = 67108864

def server_config(port, password, cert, key):
    if not 1 <= int(port) <= 65535 or not password:
        raise ValueError('invalid port or password')
    return {
        'listen': ':' + str(int(port)),
        'tls': {'cert': str(cert), 'key': str(key)},
        'auth': {'type': 'password', 'password': password},
        'masquerade': {'type': 'proxy', 'proxy': {'url': 'https://bing.com', 'rewriteHost': True}},
        'quic': {'initStreamReceiveWindow': WINDOW_STREAM, 'maxStreamReceiveWindow': WINDOW_STREAM,
                 'initConnReceiveWindow': WINDOW_CONN, 'maxConnReceiveWindow': WINDOW_CONN},
    }

def client_node(address, port, password):
    ip = ipaddress.ip_address(address)
    if not 1 <= int(port) <= 65535 or not password:
        raise ValueError('invalid port or password')
    return {'name': 'HY2-IPv' + str(ip.version), 'type': 'hysteria2', 'server': str(ip),
            'port': int(port), 'password': password, 'sni': 'bing.com', 'skip-cert-verify': True}

def client_uri(address, port, password):
    ip = ipaddress.ip_address(address)
    if not 1 <= int(port) <= 65535 or not password:
        raise ValueError('invalid port or password')
    from urllib.parse import quote
    host = '[' + str(ip) + ']' if ip.version == 6 else str(ip)
    query = urlencode({'insecure': '1', 'sni': 'bing.com'})
    return 'hysteria2://' + quote(password, safe='') + '@' + host + ':' + str(int(port)) + '/?' + query + '#HY2-IPv' + str(ip.version)
