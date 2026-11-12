"""Controlled recreation of database tasks in the isolated demonstration stack."""
import datetime
import json
import subprocess
import time
import uuid


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def container(service):
    ids = run('docker', 'ps', '-q', '--filter',
              f'label=com.docker.swarm.service.name=voting_{service}').splitlines()
    assert len(ids) == 1, f'Expected one running {service} task'
    return ids[0]


def sql(statement):
    return run('docker', 'exec', container('postgres'), 'sh', '-c',
               'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"', 'sh', statement)


def redis(*args):
    return run('docker', 'exec', container('redis'), 'redis-cli', '--raw', *args)


def recreate(service):
    old = container(service)
    subprocess.run(['docker', 'service', 'update', '--force', '--detach=true',
                    f'voting_{service}'], check=True, stdout=subprocess.DEVNULL)
    for attempt in range(120):
        try:
            current = container(service)
            health = run('docker', 'inspect', '-f', '{{.State.Health.Status}}', current)
            if current != old and health == 'healthy':
                return {'previous_container': old, 'new_container': current, 'health': health}
        except (AssertionError, subprocess.CalledProcessError):
            pass
        time.sleep(1)
    raise AssertionError(f'{service} did not recover')


key = 'supinfo-persistence-' + uuid.uuid4().hex
sql(f"INSERT INTO votes(id,vote) VALUES('{key}','a')")
assert redis('SET', key, 'preserved') == 'OK'
time.sleep(2)
results = {}
try:
    results['postgres'] = recreate('postgres')
    assert sql(f"SELECT vote FROM votes WHERE id='{key}'") == 'a'
    results['redis'] = recreate('redis')
    assert redis('GET', key) == 'preserved'
finally:
    sql(f"DELETE FROM votes WHERE id='{key}'")
    redis('DEL', key)
print(json.dumps({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'status': 'PASS', 'persistence': results, 'test_data_removed': True}))
