"""Collect current runtime evidence without dumping environment variables/secrets."""
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROOFS = ROOT / 'docs/proofs'
spec = importlib.util.spec_from_file_location('qemu_lab', ROOT / 'scripts/qemu-lab.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def remote(node, statement):
    return command(*lab.ssh_args(node), statement)


stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
subprocess.run(['docker', 'compose', 'config', '--quiet'], check=True, cwd=ROOT)
with (PROOFS / 'final-build.txt').open('w') as stream:
    stream.write(stamp + '\n')
    stream.flush()
    subprocess.run(['docker', 'compose', '--progress', 'plain', 'build'], check=True,
                   cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)

containers = command('docker', 'compose', 'ps', '-q').splitlines()
assert len(containers) == 5
compose = []
for cid in containers:
    data = json.loads(command('docker', 'inspect', cid))[0]
    item = {'name': data['Name'], 'health': data['State']['Health']['Status'],
            'user': data['Config']['User'],
            'networks': sorted(data['NetworkSettings']['Networks']),
            'ports': data['NetworkSettings']['Ports'],
            'volumes': [{'name': mount.get('Name'), 'destination': mount['Destination']}
                        for mount in data['Mounts'] if mount['Type'] == 'volume']}
    assert item['health'] == 'healthy', item
    if any(app in item['name'] for app in ('-vote-', '-worker-', '-result-')):
        assert item['user'] and item['user'] not in ('root', '0'), item
    compose.append(item)

cluster = {}
for node in lab.SPECS:
    value = remote(node, 'sudo docker ps --format "{{json .}}"')
    cluster[node] = [json.loads(line) for line in value.splitlines() if line]
    assert all('(healthy)' in item['Status'] for item in cluster[node]), cluster[node]
assert len(cluster['manager']) == 3
assert len(cluster['worker1']) == len(cluster['worker2']) == 2

down = json.loads((PROOFS / 'swarm-worker1-down-live-web-tasks.json').read_text())
recovered = json.loads((PROOFS / 'swarm-recovered-live-web-tasks.json').read_text())
assert down['ready_nodes'] == ['supinfo-manager', 'supinfo-worker2']
assert all(item['running_on_ready_nodes'] == 1 for item in down['services'].values())
assert len(recovered['ready_nodes']) == 3
assert all(item['running_on_ready_nodes'] == 2 for item in recovered['services'].values())
stopped = json.loads((PROOFS / 'swarm-worker1-down-vms.json').read_text())
assert next(vm for vm in stopped['qemu'] if vm['node'] == 'worker1')['running'] is False
for phase in ('swarm-before', 'swarm-worker1-down', 'swarm-recovered'):
    result = json.loads((PROOFS / f'{phase}-smoke.json').read_text())
    assert result['status'] == 'PASS'
    assert 'result-scores:a:websocket-confirmed' in result['checks']
    assert 'result-scores:b:websocket-confirmed' in result['checks']
phase_times = [datetime.datetime.fromisoformat(json.loads((PROOFS / f'{phase}-smoke.json').read_text())['utc'])
               for phase in ('swarm-before', 'swarm-worker1-down', 'swarm-recovered')]
assert phase_times[0] < phase_times[1] < phase_times[2]
down_time = datetime.datetime.fromisoformat(stopped['utc'])
recovery_time = datetime.datetime.fromisoformat(recovered['utc'])
persistence = json.loads((PROOFS / 'swarm-persistence.json').read_text())
assert persistence['status'] == 'PASS'
for item in persistence['persistence'].values():
    assert item['previous_container'] != item['new_container'] and item['health'] == 'healthy'
for phase in ('swarm-worker1-down', 'swarm-recovered'):
    host = json.loads((PROOFS / f'{phase}-windows-http.json').read_text(encoding='utf-8-sig'))
    assert len(host) == 10
    assert all(item['Status'] == 200 and item['ExpectedContent'] for item in host)
    times = [datetime.datetime.fromisoformat(item['Utc'].replace('Z', '+00:00')) for item in host]
    if phase == 'swarm-worker1-down':
        assert all(down_time <= timestamp < recovery_time for timestamp in times)
    else:
        assert all(timestamp >= recovery_time for timestamp in times)
evidence = {'utc': stamp, 'status': 'PASS', 'compose': compose,
            'swarm_containers': cluster,
            'verified': ['build', 'compose-config', 'all-containers-healthy',
                         'three-vms', 'worker1-really-stopped', 'web-on-worker2-during-failure',
                         'vote-and-websocket-before-during-after', 'database-persistence',
                         'windows-http-during-and-after', 'two-web-replicas-restored']}
(PROOFS / 'final-audit.json').write_text(json.dumps(evidence, indent=2) + '\n')
print(json.dumps({'utc': stamp, 'status': 'PASS', 'checks': evidence['verified']}))
