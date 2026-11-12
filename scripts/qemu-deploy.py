"""Deployment and evidence collection for the approved QEMU lab.

Run as root from the project root in Ubuntu WSL2. No destructive cleanup.
"""
import argparse
import concurrent.futures
import datetime
import fcntl
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
PROOFS = ROOT / 'docs' / 'proofs'
module_spec = importlib.util.spec_from_file_location('qemu_lab', ROOT / 'scripts/qemu-lab.py')
lab = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(lab)


def ssh(node, command, **kwargs):
    return subprocess.run(lab.ssh_args(node) + [command], check=True, **kwargs)


def output(node, command):
    return ssh(node, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()


def record(name, content):
    PROOFS.mkdir(exist_ok=True)
    (PROOFS / name).write_text(content + '\n', encoding='utf-8')


def wait_ready(node):
    for attempt in range(90):
        try:
            result = output(node, 'command -v docker >/dev/null && sudo docker info --format "{{.ServerVersion}}" && test -f /var/lib/cloud/instance/boot-finished')
            print(f'{node}: cloud-init completed; Docker {result}', flush=True)
            return
        except subprocess.CalledProcessError:
            if attempt % 6 == 0:
                print(f'{node}: waiting for cloud-init/SSH ({attempt})', flush=True)
            time.sleep(5)
    raise RuntimeError(f'{node} did not become ready')


def put(node, source, destination):
    with Path(source).open('rb') as stream:
        ssh(node, f'cat > {shlex.quote(destination)}', stdin=stream)


def inventory(prefix):
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = {'utc': stamp, 'qemu': []}
    for node, spec in lab.SPECS.items():
        directory = lab.LAB / spec['name']
        item = {'node': node, 'running': lab.live(directory), 'ip': spec['ip']}
        if item['running']:
            item['details'] = output(node, 'hostname; uname -r; ip -br address; sudo docker info --format "Docker={{.ServerVersion}} Swarm={{.Swarm.LocalNodeState}} Node={{.Swarm.NodeID}}"')
        result['qemu'].append(item)
    record(prefix + '-vms.json', json.dumps(result, indent=2))
    for name, command in {
        'nodes': 'sudo docker node ls',
        'services': 'sudo docker stack services voting',
        'tasks': 'sudo docker stack ps --no-trunc voting',
        'networks': 'sudo docker network inspect voting_frontend voting_backend',
        'volumes': 'sudo docker volume inspect voting_postgres_data voting_redis_data',
    }.items():
        record(prefix + '-' + name + '.txt', stamp + '\n' + output('manager', command))
    nodes = [json.loads(line) for line in output('manager', 'sudo docker node ls --format "{{json .}}"').splitlines()]
    ready = {node['Hostname'] for node in nodes if node['Status'] == 'Ready'}
    web = {}
    for service in ('vote', 'result'):
        tasks = [json.loads(line) for line in output('manager', f'sudo docker service ps --no-trunc --filter desired-state=running --format "{{{{json .}}}}" voting_{service}').splitlines()]
        web[service] = {'desired_tasks': tasks,
                        'running_on_ready_nodes': sum(task['Node'] in ready and task['CurrentState'].startswith('Running') for task in tasks)}
    record(prefix + '-live-web-tasks.json', json.dumps({'utc': stamp, 'ready_nodes': sorted(ready), 'services': web}, indent=2))


def smoke(phase):
    result = output('manager', f'sudo python3 /home/ubuntu/swarm-smoke.py {shlex.quote(phase)}')
    record(phase + '-smoke.json', result)
    print(result, flush=True)
    result = output('manager', 'sudo docker run --rm --network host -i supinfo.local/voting-result:1.0 node < /home/ubuntu/socket-smoke.js')
    record(phase + '-websocket.txt', datetime.datetime.now(datetime.timezone.utc).isoformat() + '\n' + result)
    print(result, flush=True)


parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['logs', 'wait', 'images', 'init', 'deploy', 'sync-tests', 'ready', 'before', 'persistence', 'down', 'recover'])
args = parser.parse_args()
orchestration_lock = (lab.LAB / '.orchestration.lock').open('w')
fcntl.flock(orchestration_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
if args.action == 'logs':
    for spec in lab.SPECS.values():
        print('\n' + spec['name'])
        print('\n'.join((lab.LAB / spec['name'] / 'serial.log').read_text(errors='replace').splitlines()[-15:]))
elif args.action == 'wait':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(wait_ready, lab.SPECS))
elif args.action == 'images':
    image_names = []
    for service in ('vote', 'worker', 'result'):
        tag = f'supinfo.local/voting-{service}:1.0'
        subprocess.run(['docker', 'tag', f'voting-{service}:local', tag], check=True)
        image_names.append(tag)
    image_names += ['redis:7-alpine', 'postgres:15-alpine']
    archive = lab.LAB / 'images.tar'
    subprocess.run(['docker', 'save', '-o', str(archive), *image_names], check=True)
    for node in lab.SPECS:
        print(f'Loading images on {node}', flush=True)
        with archive.open('rb') as stream:
            ssh(node, 'sudo docker load', stdin=stream)
    record('swarm-images.txt', output('manager', 'sudo docker image ls --digests'))
elif args.action == 'init':
    for node in lab.SPECS:
        for peer, spec in lab.SPECS.items():
            if peer != node:
                print(output(node, f'ping -c 2 -W 2 {spec["ip"]}'), flush=True)
    state = output('manager', 'sudo docker info --format "{{.Swarm.LocalNodeState}}"')
    if state == 'inactive':
        output('manager', 'sudo docker swarm init --advertise-addr 10.77.0.11 --data-path-addr 10.77.0.11')
    token = output('manager', 'sudo docker swarm join-token -q worker')
    for node in ('worker1', 'worker2'):
        state = output(node, 'sudo docker info --format "{{.Swarm.LocalNodeState}}"')
        if state == 'inactive':
            output(node, f'sudo docker swarm join --token {shlex.quote(token)} --advertise-addr {lab.SPECS[node]["ip"]} --data-path-addr {lab.SPECS[node]["ip"]} 10.77.0.11:2377')
    print(output('manager', 'sudo docker node ls'))
elif args.action == 'deploy':
    for filename in ('docker-compose.swarm.yml', 'scripts/manager-deploy.sh', 'scripts/swarm-smoke.py', 'scripts/socket-smoke.js', 'scripts/swarm-persistence.py'):
        put('manager', ROOT / filename, '/home/ubuntu/' + Path(filename).name)
    print(output('manager', 'cd /home/ubuntu && sudo bash manager-deploy.sh'))
elif args.action == 'sync-tests':
    for filename in ('swarm-smoke.py', 'socket-smoke.js', 'swarm-persistence.py'):
        put('manager', ROOT / 'scripts' / filename, '/home/ubuntu/' + filename)
    print('Test scripts synchronized')
elif args.action == 'ready':
    for attempt in range(120):
        result = output('manager', 'sudo docker stack services voting --format "{{.Name}} {{.Replicas}}"')
        if result.count('1/1') == 3 and result.count('2/2') == 2:
            print(result)
            break
        if attempt % 6 == 0:
            print(result, flush=True)
        time.sleep(3)
    else:
        raise RuntimeError('Services did not converge')
elif args.action == 'before':
    inventory('swarm-before')
    smoke('swarm-before')
elif args.action == 'persistence':
    result = output('manager', 'sudo python3 /home/ubuntu/swarm-persistence.py')
    record('swarm-persistence.json', result)
    print(result)
elif args.action == 'down':
    lab.stop('worker1')
    for attempt in range(90):
        state = output('manager', 'sudo docker node inspect supinfo-worker1 --format "{{.Status.State}}"')
        if state == 'down':
            break
        time.sleep(2)
    else:
        raise RuntimeError('Worker did not become Down')
    inventory('swarm-worker1-down')
    live = json.loads((PROOFS / 'swarm-worker1-down-live-web-tasks.json').read_text())
    assert live['ready_nodes'] == ['supinfo-manager', 'supinfo-worker2']
    assert all(service['running_on_ready_nodes'] == 1 for service in live['services'].values())
    smoke('swarm-worker1-down')
elif args.action == 'recover':
    lab.start('worker1')
    wait_ready('worker1')
    for attempt in range(90):
        result = output('manager', 'sudo docker stack services voting --format "{{.Name}} {{.Replicas}}"')
        if result.count('1/1') == 3 and result.count('2/2') == 2:
            break
        time.sleep(3)
    else:
        raise RuntimeError('Replicas did not recover')
    inventory('swarm-recovered')
    live = json.loads((PROOFS / 'swarm-recovered-live-web-tasks.json').read_text())
    assert len(live['ready_nodes']) == 3
    assert all(service['running_on_ready_nodes'] == 2 for service in live['services'].values())
    smoke('swarm-recovered')
