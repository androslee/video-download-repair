"""Check the git index for common private/generated files before publication."""
from pathlib import Path
import hashlib
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRS = {'.local', '.venv', '__pycache__', '.pytest_cache', 'build', 'dist'}
MEDIA_SUFFIXES = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.m4v', '.wav', '.flac', '.mp3', '.aac', '.blend', '.blend1'}
# Only these reviewed demonstration videos may bypass the general media ban.
APPROVED_MEDIA = {'examples/gamers-nexus-mixed-resolution/inputs/clip-01987b3d104a.mp4': '01987b3d104a1bcf21e1e5e2c5032b221f88007edaf829b1a5751217ced413e5', 'examples/gamers-nexus-mixed-resolution/inputs/clip-91d2b5ce146f.mp4': '91d2b5ce146fbde90c0e6cdf1a789c45e78e34f5234376bcf10a4ad3b88fea48', 'examples/gamers-nexus-mixed-resolution/inputs/clip-953131e12000.mp4': '953131e12000f771aa5c7c5f0ffd7285fe6792786367c16ec6408c8960c7c40f', 'examples/gamers-nexus-mixed-resolution/inputs/clip-96440462db6d.mp4': '96440462db6d49899a283007f9dc3d1f8b6184d415ddd383ab250472ded9dcd4', 'examples/gamers-nexus-mixed-resolution/inputs/clip-9863090b3064.mp4': '9863090b3064cea49b51d4c7ddadf5e10cd14d221f2628063c54cfef89395162', 'examples/gamers-nexus-mixed-resolution/inputs/clip-b8fbec23accd.mp4': 'b8fbec23accd935545b6c563c11f9d7836a548fbe5b3622b475ba14b5829b3cf', 'examples/gamers-nexus-mixed-resolution/reconstructed.mp4': 'd275525fd7c5dd96aa627e25ab94f4e9dd504f29ff16a168b9661e6dc73950d2'}
SECRET_PATTERNS = (
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{36,}'),
    re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),
)


def main():
    result = subprocess.run(['git', 'ls-files', '--stage', '-z'], cwd=ROOT, capture_output=True)
    if result.returncode:
        print('Repository check requires an initialized git repository and git index.', file=sys.stderr)
        return 2
    errors = []
    entries = [e for e in result.stdout.decode('utf-8', errors='surrogateescape').split('\0') if e]
    for entry in entries:
        header, name = entry.split('\t', 1)
        mode, object_id, stage = header.split(' ')
        path = Path(name)
        if any(part in PRIVATE_DIRS or part.endswith('.egg-info') for part in path.parts):
            errors.append((path, 'generated/private directory'))
        elif stage != '0':
            errors.append((path, 'unresolved index conflict'))
        elif mode not in ('100644', '100755'):
            errors.append((path, 'symlink or non-file needs manual review'))
        elif name in APPROVED_MEDIA:
            blob = subprocess.run(['git', 'cat-file', 'blob', object_id], cwd=ROOT, capture_output=True)
            if blob.returncode or hashlib.sha256(blob.stdout).hexdigest() != APPROVED_MEDIA[name]:
                errors.append((path, 'approved example media does not match reviewed hash'))
        elif path.name == '.env' or path.name.startswith('.env.') or path.suffix.lower() in MEDIA_SUFFIXES:
            errors.append((path, 'private configuration or media'))
        else:
            size = subprocess.run(['git', 'cat-file', '-s', object_id], cwd=ROOT, capture_output=True)
            if size.returncode:
                errors.append((path, 'cannot read staged object'))
            elif int(size.stdout) > 2_000_000:
                errors.append((path, 'larger than 2 MB; review before publication'))
            else:
                blob = subprocess.run(['git', 'cat-file', 'blob', object_id], cwd=ROOT, capture_output=True)
                if blob.returncode:
                    errors.append((path, 'cannot read staged contents'))
                elif any(pattern.search(blob.stdout) for pattern in SECRET_PATTERNS):
                    errors.append((path, 'possible credential; inspect privately'))
    if errors:
        for path, reason in errors:
            print(f'{path}: {reason}', file=sys.stderr)
        return 1
    print(f'Repository hygiene: checked {len(entries)} staged files. Review history separately.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
