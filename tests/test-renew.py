#!/usr/bin/env python3
"""Verify certificate deploy retry and no-op logic without systemd."""
import os, pathlib, subprocess, tempfile
root=pathlib.Path(__file__).resolve().parents[1]
script=(root/'install.sh').read_text().split('cat > "$BIN/deploy-cert" <<HOOK\n',1)[1].split('\nHOOK\n',1)[0]
with tempfile.TemporaryDirectory() as tmp:
 p=pathlib.Path(tmp); target=p/'target'; target.mkdir(); lineage=p/'lineage'; lineage.mkdir(); fake=p/'systemctl'
 (lineage/'fullchain.pem').write_text('cert-one'); (lineage/'privkey.pem').write_text('key-one')
 fake.write_text('#!/bin/sh\necho invoked >> "$CALLS"\n[ ! -e "$FAIL" ]\n'); fake.chmod(0o755)
 env=dict(os.environ, ROOT=str(target), BIN=str(p), GROUP=subprocess.check_output(['id','-gn'],text=True).strip(),IP='127.0.0.1',RENEWED_LINEAGE=str(lineage),PATH=tmp+os.pathsep+os.environ['PATH'],CALLS=str(p/'calls'),FAIL=str(p/'fail'))
 env['TEMPLATE']=script
 hook=p/'deploy-cert'
 # Expand exactly like the installer's unquoted here-document.
 with hook.open('w') as f: subprocess.run(['bash','-c','eval "cat <<HOOK\n$TEMPLATE\nHOOK"'],env=env,stdout=f,check=True)
 hook.chmod(0o755); (p/'fail').touch()
 r=subprocess.run(['bash',str(hook)],env=env,capture_output=True)
 assert r.returncode != 0 and not (target/'loaded-cert.sha256').exists()
 (p/'fail').unlink(); subprocess.run(['bash',str(hook)],env=env,check=True)
 assert (target/'loaded-cert.sha256').exists() and (target/'fullchain.pem').read_text()=='cert-one'
 assert len((p/'calls').read_text().splitlines())==2
 subprocess.run(['bash',str(hook)],env=env,check=True)
 assert len((p/'calls').read_text().splitlines())==2
 (lineage/'fullchain.pem').write_text('cert-two'); subprocess.run(['bash',str(hook)],env=env,check=True)
 assert len((p/'calls').read_text().splitlines())==3 and (target/'fullchain.pem').read_text()=='cert-two'
print('PASS: failed certificate reload retries, unchanged certificate no-op, changed certificate reloads')
