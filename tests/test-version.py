#!/usr/bin/env python3
"""Check Ubuntu os-release does not alter the actual release download URL."""
import pathlib, re, subprocess, tempfile
script=(pathlib.Path(__file__).resolve().parents[1]/'install.sh').read_text()
assignment=re.search(r'^MIHOMO_VERSION=.*$',script,re.M)
assert assignment, 'missing dedicated Mihomo version variable'
url=re.search(r'https://github\.com/MetaCubeX/mihomo/releases/download/[^"\s]+',script).group()
with tempfile.TemporaryDirectory() as tmp:
 release=pathlib.Path(tmp)/'os-release'
 for version in ('22.04.5 LTS (Jammy Jellyfish)','24.04.3 LTS (Noble Numbat)'):
  release.write_text('ID=ubuntu\nVERSION="'+version+'"\n')
  result=subprocess.check_output(['bash','-c',assignment.group()+'\n. "$1"\nARCH=amd64-compatible\nprintf "%s" "'+url+'"','_',str(release)],text=True)
  assert result=='https://github.com/MetaCubeX/mihomo/releases/download/v1.19.33/mihomo-linux-amd64-compatible-v1.19.33.gz',result
print('PASS: Ubuntu VERSION cannot overwrite the release URL')
