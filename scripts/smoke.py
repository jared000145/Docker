"""Run from the project root in WSL: python3 scripts/smoke.py."""
import json
import subprocess
import time
import urllib.request
import urllib.error
import uuid

def sql(statement):
    return subprocess.check_output([
        'docker', 'compose', 'exec', '-T', 'postgres', 'sh', '-c',
        'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"',
        'sh', statement], text=True).strip()

def request(port, path='/', data=None, voter=None):
    req = urllib.request.Request(f'http://localhost:{port}{path}', data=data,
        headers={'Cookie': f'voter_id={voter}'} if voter else {})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read().decode()

voter = 'smoke-' + uuid.uuid4().hex
for port in (8080, 8888):
    assert json.loads(request(port, '/health'))['status'] == 'ok'
assert 'name="vote"' in request(8080)
assert 'statsCtrl' in request(8888)
try:
    for choice in ('a', 'b'):
        request(8080, data=f'vote={choice}'.encode(), voter=voter)
        for attempt in range(30):
            if sql(f"SELECT vote FROM votes WHERE id='{voter}'") == choice:
                break
            time.sleep(1)
        else:
            raise AssertionError(f'Vote {choice} absent de PostgreSQL')
    try:
        request(8080, data=b'vote=invalid', voter=voter)
        raise AssertionError('Vote invalide accepté')
    except urllib.error.HTTPError as error:
        assert error.code == 400
finally:
    sql(f"DELETE FROM votes WHERE id='{voter}'")
print('OK : HTTP, santé, vote, modification, validation ; données de test supprimées.')
