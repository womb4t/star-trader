"""The server image (Dockerfile COPY line, .dockerignore allow-list) holds every module the server imports,
and the game install holds every module the game imports."""
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def copied():
    line = next(l for l in (ROOT/'Dockerfile').read_text().splitlines() if l.startswith('COPY '))
    return line.split()[1:-1]


class DeployTests(unittest.TestCase):
    def test_the_dockerfile_and_allow_list_agree(self):
        allowed = {l[1:] for l in (ROOT/'.dockerignore').read_text().splitlines() if l.startswith('!')}
        self.assertEqual(set(copied()), allowed)

    def test_the_server_runs_from_only_the_copied_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in copied(): shutil.copy(ROOT/name, tmp)
            script = ("import save_server, json\n"
                      "store = save_server.Store('p.sqlite3')\n"
                      "snap = store.market_exchange(trades=[[1,0,-1]], now=1.8e9)\n"
                      "store.market_exchange(now=1.8e9+20*3600)\n"
                      "assert 'council' in store.market_exchange(now=1.8e9+26*3600)\n"
                      "assert store.relay()['acts']\n")
            env = dict(os.environ, PYTHONPATH='', STAR_TRADER_NO_UPDATE_CHECK='1')
            result = subprocess.run([sys.executable, '-c', script], cwd=tmp, env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])


def local_imports(path):
    """This repository's modules that a file imports, anywhere in it (including inside functions)."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import): names.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level: names.add(node.module.split('.')[0])
    return {n+'.py' for n in names if (ROOT/(n+'.py')).exists()}


class InstallTests(unittest.TestCase):
    def test_the_install_holds_every_module_the_game_imports(self):
        sys.path.insert(0, str(ROOT))
        import install
        installed = set(install.GAME_FILES)
        for name in sorted(n for n in installed if n.endswith('.py')):
            self.assertLessEqual(local_imports(ROOT/name), installed, f'{name} imports a module the installer does not copy')

    def test_the_installed_game_reads_an_online_market(self):
        """0.9.0 closed as soon as it went online: council.py was not installed."""
        sys.path.insert(0, str(ROOT))
        import install
        with tempfile.TemporaryDirectory() as tmp:
            for name in install.GAME_FILES: shutil.copy(ROOT/name, tmp)
            server = tempfile.mkdtemp(dir=tmp)
            for name in copied(): shutil.copy(ROOT/name, server)
            # A server makes a real online market snapshot; then the game runs from only the installed files.
            script = ("import sys\n"
                      "sys.path.insert(0, sys.argv[2])\n"
                      "import save_server\n"
                      "store = save_server.Store('p.sqlite3')\n"
                      "store.market_exchange(now=1.8e9)\n"
                      "snap = store.market_exchange(now=1.8e9+26*3600)\n"
                      "sys.path[:] = [sys.argv[1]]+[p for p in sys.path if p != sys.argv[2]]\n"
                      "for m in [m for m in sys.modules if m in ('star_trader','market','economy','council','tally','startup','presence','save_sync')]: del sys.modules[m]\n"
                      "import star_trader as st\n"
                      "assert st.__file__.startswith(sys.argv[1])\n"
                      "g = st.Game(None)\n"
                      "st.VIEW = st.view_from(snap)\n"
                      "g.systems_in_range(st.FUEL_CAPACITY)\n"
                      "[st.quote(s, 0, False) for s in range(8)]\n")
            env = dict(os.environ, PYTHONPATH='', STAR_TRADER_NO_UPDATE_CHECK='1', XDG_DATA_HOME=tmp)
            result = subprocess.run([sys.executable, '-I', '-c', script, tmp, server], cwd=server, env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])


if __name__ == '__main__':
    unittest.main()
