"""Create a Moodle archive from an explicit source allowlist (no local secrets)."""
import hashlib
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
output = root / 'SUPINFO-voting-app-final.zip'
files = [root / name for name in (
    'README.md', '.env.example', '.dockerignore', '.gitignore',
    'docker-compose.yml', 'docker-compose.swarm.yml')]
for directory in ('vote', 'worker', 'result', 'docs', 'scripts'):
    for path in (root / directory).rglob('*'):
        relative = path.relative_to(root / directory)
        if path.relative_to(root).as_posix() in {
            'docs/VM-PLAN.md', 'docs/WSL-QEMU-PLAN.md', 'docs/proofs/multipass-installation.md',
            'scripts/create-vms.ps1', 'scripts/cloud-init.yaml'
        }:
            # Keep the abandoned Multipass plan in the workspace, outside the submission.
            continue
        if not path.is_file() or any(part in {
            'node_modules', '__pycache__', 'bin', 'obj', '.git', '.local'
        } for part in relative.parts):
            continue
        if path.name.endswith('.env') or path.suffix.lower() in {
            '.zip', '.tar', '.gz', '.msi', '.pem', '.key', '.pyc', '.dump', '.sql'
        }:
            continue
        files.append(path)
files = sorted(set(files))
with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, 'voting-app/' + path.relative_to(root).as_posix())
with zipfile.ZipFile(output) as archive:
    assert archive.testzip() is None
    assert not any(Path(name).name == '.env' for name in archive.namelist())
digest = hashlib.sha256(output.read_bytes()).hexdigest()
output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n')
print(f'{output.name}: {len(files)} files, {output.stat().st_size} bytes, SHA256 {digest}')
