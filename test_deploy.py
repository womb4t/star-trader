"""The server image (Dockerfile COPY line, .dockerignore allow-list) holds every module the server imports."""
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


if __name__ == '__main__':
    unittest.main()
