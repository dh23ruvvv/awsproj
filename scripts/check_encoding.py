"""Check publishable source and documentation for BOMs and common mojibake."""
from pathlib import Path
import re

roots = [Path('frontend/src'), Path('server'), Path('docs'), Path('tests'), Path('scripts'), Path('skills')]
files = list(Path('.').glob('*.md')) + [Path('frontend/index.html'), Path('package.json'), Path('.env.example')]
for root in roots:
    files.extend(p for p in root.rglob('*') if p.is_file() and p.suffix in {'.md', '.py', '.tsx', '.ts', '.css', '.html', '.json'})
pattern = re.compile(r'\u00c3|\u00c2[\u0080-\u00bf]|\u00e2[\u0080-\u00bf\u20ac]|\u00f0[\u009f\u0178]|\ufffd')
problems = []
for path in files:
    raw = path.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        problems.append(f'{path}: UTF-8 BOM')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        problems.append(f'{path}: invalid UTF-8')
        continue
    for number, line in enumerate(text.splitlines(), 1):
        if pattern.search(line):
            problems.append(f'{path}:{number}: mojibake candidate')
if problems:
    print('\n'.join(problems))
    raise SystemExit(1)
print(f'PASS: {len(files)} source/documentation files; 0 mojibake sequences; 0 UTF-8 BOMs.')
