#!/usr/bin/env python3
"""Exercise both installers' platform guards with mocked OS metadata/commands.
No root, package installation or system changes. This is not a VPS install test.
"""
import os
import pathlib
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    release = pathlib.Path(tmp) / 'os-release'
    for name in ('install.sh', 'install-reality.sh'):
        source = (root / name).read_text()
        guard = source.split('# Check the platform, not an Ubuntu release number.\n', 1)[1]
        guard = guard.split('[[ ! -e ', 1)[0]
        guard = guard.replace('/etc/os-release', str(release))
        for distro, version, arch, systemd, apt, success in (
            ('ubuntu', '20.04', 'x86_64', 0, 0, True),
            ('ubuntu', '22.04', 'x86_64', 0, 0, True),
            ('ubuntu', '24.04', 'aarch64', 0, 0, True),
            ('ubuntu', '99.99', 'x86_64', 0, 0, True),
            ('debian', '12', 'x86_64', 0, 0, False),
            ('', '', 'x86_64', 0, 0, False),
            ('ubuntu', '22.04', 'i686', 0, 0, False),
            ('ubuntu', '22.04', 'x86_64', 1, 0, False),
            ('ubuntu', '22.04', 'x86_64', 0, 1, False),
        ):
            release.write_text('ID="{}"\nVERSION_ID="{}"\n'.format(distro, version))
            mocks = '''set -Eeuo pipefail
fail() { echo "$*" >&2; exit 1; }
command() { if [[ $2 == apt-get ]]; then return "$APT_STATUS"; else builtin command "$@"; fi; }
systemctl() { return "$SYSTEMD_STATUS"; }
uname() { echo "$TEST_ARCH"; }
'''
            env = dict(os.environ, APT_STATUS=str(apt), SYSTEMD_STATUS=str(systemd), TEST_ARCH=arch)
            result = subprocess.run(['bash', '-c', mocks + guard], env=env, capture_output=True, text=True)
            assert (result.returncode == 0) == success, (name, distro, version, arch, result.stderr)
        release.unlink()
        result = subprocess.run(['bash', '-c', mocks + guard], env=env, capture_output=True, text=True)
        assert result.returncode != 0 and '无法识别系统' in result.stderr
print('PASS: both installers accept Ubuntu versions and reject non-Ubuntu, missing metadata, unsupported CPU, unavailable apt and inactive systemd')
