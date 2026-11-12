"""Read-only KVM capability check; run as root in Ubuntu WSL2."""
import fcntl
import os

fd = os.open('/dev/kvm', os.O_RDWR)
try:
    version = fcntl.ioctl(fd, 0xAE00, 0)
    print(f'KVM API version: {version} (expected: 12)')
    assert version == 12
finally:
    os.close(fd)
