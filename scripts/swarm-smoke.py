"""Execute on the Swarm manager: sudo python3 swarm-smoke.py PHASE.

Requires a voting stack with PostgreSQL placed on this manager.
Creates and removes only its own randomly identified vote.
"""
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def sql(statement):
    container = run('docker', 'ps', '-q', '--filter',
                    'label=com.docker.swarm.service.name=voting_postgres')
    assert container and '\n' not in container, 'PostgreSQL manager task missing'
    return run('docker', 'exec', container, 'sh', '-c',
               'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"',
               'sh', statement)


def http(port, path='/', data=None, voter=None):
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data,
        headers={'Cookie': f'voter_id={voter}'} if voter else {})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read().decode()


phase = sys.argv[1] if len(sys.argv) > 1 else 'manual'
voter = 'swarm-smoke-' + uuid.uuid4().hex
checks = []
for port in (8080, 8888):
    assert json.loads(http(port, '/health'))['status'] == 'ok'
    checks.append(f'health:{port}')
assert 'name="vote"' in http(8080)
assert 'statsCtrl' in http(8888)
checks.append('both-pages-http')
try:
    for choice in ('a', 'b'):
        http(8080, data=f'vote={choice}'.encode(), voter=voter)
        for attempt in range(30):
            if sql(f"SELECT vote FROM votes WHERE id='{voter}'") == choice:
                break
            time.sleep(1)
        else:
            raise AssertionError(f'Vote {choice} missing')
        checks.append(f'vote:{choice}:postgres-confirmed')
        expected = sql("SELECT json_build_object('a',COUNT(*) FILTER (WHERE vote='a'),'b',COUNT(*) FILTER (WHERE vote='b')) FROM votes")
        subprocess.run(['docker', 'run', '--rm', '--network', 'host', '-i',
                        '-e', 'EXPECTED_SCORES=' + expected,
                        'supinfo.local/voting-result:1.0', 'node'],
                       input=Path(__file__).with_name('socket-smoke.js').read_text(),
                       text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        checks.append(f'result-scores:{choice}:websocket-confirmed')
    try:
        http(8080, data=b'vote=invalid', voter=voter)
        raise AssertionError('Invalid vote accepted')
    except urllib.error.HTTPError as error:
        assert error.code == 400
    checks.append('invalid-vote:400')
finally:
    sql(f"DELETE FROM votes WHERE id='{voter}'")
print(json.dumps({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'phase': phase, 'status': 'PASS', 'checks': checks,
                  'test_vote_removed': True}))
