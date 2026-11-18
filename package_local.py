"""Build a portable WSL source bundle without machine state or credentials."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

BASE = Path(__file__).resolve().parent
SOURCES = ('launch.py', 'local_server.py', 'project_runtime.py', 'usage_guides.py', 'package_local.py',
           'README.md', '打开Skills.html', 'build.mjs')


def build(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'w', ZIP_DEFLATED) as bundle:
        files = [BASE / name for name in SOURCES]
        files += sorted(path for path in (BASE / 'static').rglob('*') if path.is_file())
        for path in files:
            bundle.write(path, 'skills-hub/' + path.relative_to(BASE).as_posix())
    return destination


if __name__ == '__main__':
    print(build(BASE / 'dist/skills-hub-local.zip'))
