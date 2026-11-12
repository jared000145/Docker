"""Manage three real Ubuntu VMs under WSL2. Run as root after approval.

State/private key/disks: /var/tmp/supinfo-swarm-lab (excluded from submission).
No deletion commands; stop requests ACPI shutdown, preserving disks.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time

LAB = Path('/var/tmp/supinfo-swarm-lab')
BASE_URL = 'https://cloud-images.ubuntu.com/noble/current/'
IMAGE = 'noble-server-cloudimg-amd64.img'
SPECS = {
    'manager': {'name': 'supinfo-manager', 'memory': 4096, 'disk': '25G', 'ssh': 2201, 'ip': '10.77.0.11', 'mac': '11'},
    'worker1': {'name': 'supinfo-worker1', 'memory': 2048, 'disk': '20G', 'ssh': 2202, 'ip': '10.77.0.12', 'mac': '12'},
    'worker2': {'name': 'supinfo-worker2', 'memory': 2048, 'disk': '20G', 'ssh': 2203, 'ip': '10.77.0.13', 'mac': '13'},
}


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def live(directory):
    try:
        pid = int((directory / 'qemu.pid').read_text())
        cmdline = Path(f'/proc/{pid}/cmdline').read_bytes()
        return b'qemu-system-x86_64' in cmdline and str(directory).encode() in cmdline
    except (FileNotFoundError, ValueError, ProcessLookupError):
        return False


def prepare():
    LAB.mkdir(mode=0o700, exist_ok=True)
    if not (LAB / 'id_ed25519').exists():
        run('ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(LAB / 'id_ed25519'))
    if not (LAB / IMAGE).exists():
        run('curl', '-fL', '--retry', '3', '-o', str(LAB / (IMAGE + '.partial')), BASE_URL + IMAGE)
        run('curl', '-fsSL', '-o', str(LAB / 'SHA256SUMS'), BASE_URL + 'SHA256SUMS')
        expected = next(line.split()[0] for line in (LAB / 'SHA256SUMS').read_text().splitlines()
                        if line.split()[-1].lstrip('*') == IMAGE)
        digest = hashlib.file_digest((LAB / (IMAGE + '.partial')).open('rb'), 'sha256').hexdigest()
        assert digest == expected, 'Ubuntu cloud image checksum mismatch'
        (LAB / (IMAGE + '.partial')).rename(LAB / IMAGE)
        (LAB / 'image-sha256.txt').write_text(f'{digest}  {IMAGE}\n')
    key = (LAB / 'id_ed25519.pub').read_text().strip()
    for spec in SPECS.values():
        directory = LAB / spec['name']
        directory.mkdir(exist_ok=True)
        if (directory / 'disk.qcow2').exists():
            continue
        run('qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(LAB / IMAGE),
            str(directory / 'disk.qcow2'), spec['disk'])
        (directory / 'meta-data').write_text(f"instance-id: {spec['name']}\nlocal-hostname: {spec['name']}\n")
        (directory / 'user-data').write_text(f'''#cloud-config
hostname: {spec['name']}
manage_etc_hosts: true
ssh_pwauth: false
users:
  - name: ubuntu
    groups: [sudo, docker]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
    ssh_authorized_keys:
      - {key}
package_update: true
packages: [docker.io, curl, python3]
runcmd:
  - [systemctl, enable, --now, docker]
''')
        (directory / 'network-config').write_text(f'''version: 2
ethernets:
  wan0:
    match: {{macaddress: "52:54:00:77:01:{spec['mac']}"}}
    set-name: wan0
    dhcp4: true
    dhcp6: false
  lan0:
    match: {{macaddress: "52:54:00:77:02:{spec['mac']}"}}
    set-name: lan0
    addresses: [{spec['ip']}/24]
    dhcp4: false
    dhcp6: false
''')
        run('cloud-localds', '--network-config', str(directory / 'network-config'),
            str(directory / 'seed.img'), str(directory / 'user-data'), str(directory / 'meta-data'))


def start(node):
    spec = SPECS[node]
    directory = LAB / spec['name']
    if live(directory):
        print(f"{spec['name']} already running")
        return
    forwards = f"hostfwd=tcp:127.0.0.1:{spec['ssh']}-:22"
    if node == 'manager':
        forwards += ',hostfwd=tcp:127.0.0.1:18080-:8080,hostfwd=tcp:127.0.0.1:18888-:8888'
    run('qemu-system-x86_64', '-name', spec['name'], '-machine', 'q35,accel=kvm',
        '-cpu', 'host', '-m', str(spec['memory']), '-smp', '2',
        '-drive', f"file={directory / 'disk.qcow2'},if=virtio,format=qcow2",
        '-drive', f"file={directory / 'seed.img'},if=virtio,format=raw,readonly=on",
        '-netdev', f'user,id=wan,{forwards}',
        '-device', f"virtio-net-pci,netdev=wan,mac=52:54:00:77:01:{spec['mac']}",
        '-netdev', 'socket,id=lan,mcast=230.77.0.1:17777,localaddr=127.0.0.1',
        '-device', f"virtio-net-pci,netdev=lan,mac=52:54:00:77:02:{spec['mac']}",
        '-display', 'none', '-serial', f"file:{directory / 'serial.log'}",
        '-qmp', f"unix:{directory / 'qmp.sock'},server=on,wait=off",
        '-pidfile', str(directory / 'qemu.pid'), '-daemonize')
    print(f"Started {spec['name']}: KVM, SSH localhost:{spec['ssh']}, LAN {spec['ip']}")


def ssh_args(node):
    return ['ssh', '-i', str(LAB / 'id_ed25519'), '-p', str(SPECS[node]['ssh']),
            '-o', f'UserKnownHostsFile={LAB / "known_hosts"}', '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes', 'ubuntu@127.0.0.1']


def stop(node):
    directory = LAB / SPECS[node]['name']
    if not live(directory):
        print('Already stopped')
        return
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(directory / 'qmp.sock'))
        stream = sock.makefile('rwb', buffering=0)
        stream.readline()
        for command in ('qmp_capabilities', 'system_powerdown'):
            stream.write((json.dumps({'execute': command}) + '\n').encode())
            stream.readline()
    for attempt in range(60):
        if not live(directory):
            print(f"Stopped {SPECS[node]['name']}; disks preserved")
            return
        time.sleep(1)
    raise RuntimeError('ACPI shutdown not completed; no forced kill issued')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'start', 'stop', 'status', 'ssh'])
    parser.add_argument('node', nargs='?', choices=[*SPECS, 'all'], default='all')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    elif args.action == 'ssh':
        assert args.node != 'all'
        raise SystemExit(subprocess.call(ssh_args(args.node) + args.command))
    else:
        for node in SPECS if args.node == 'all' else [args.node]:
            if args.action == 'start':
                start(node)
            elif args.action == 'stop':
                stop(node)
            else:
                print(json.dumps({'node': node, 'running': live(LAB / SPECS[node]['name']), **SPECS[node]}))


if __name__ == '__main__':
    main()
