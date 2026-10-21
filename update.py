#!/usr/bin/env python3
"""Update Star Trader to the latest release without touching the saved game.

Installs made from a Git checkout update that checkout; others download the release archive."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

OFFICIAL = 'https://github.com/womb4t/star-trader'


def output(repo, *args):
    return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()


def is_checkout(path):
    """A .git name alone is insufficient (it can be an empty placeholder)."""
    try:
        result = subprocess.run(['git','-C',str(path),'rev-parse','--show-toplevel'],
                                capture_output=True,text=True,check=False)
        return result.returncode == 0 and Path(result.stdout.strip()).resolve() == path.resolve()
    except OSError:
        return False


def resolve_checkout(here):
    if is_checkout(here): return here
    metadata = here/'install-info.json'
    if metadata.is_file():
        data = json.loads(metadata.read_text())
        source = data.get('source')
        if not isinstance(source,str) or not source.strip(): raise ValueError('Invalid source checkout in install-info.json.')
        repo = Path(source).expanduser().resolve()
        if is_checkout(repo): return repo
        raise ValueError(f'The recorded source checkout is not a valid Git repository: {repo}')
    raise ValueError('No valid checkout or installation metadata found. Run the installer from the official checkout.')


def installer_name():
    return 'install-mac.sh' if sys.platform == 'darwin' else 'install.sh'


def fetch(url):
    req = urllib.request.Request(url,headers={'User-Agent':'StarTrader-updater','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=30) as response: return response.read(64*1024*1024)


def release_update(dry_run):
    tag = json.loads(fetch('https://api.github.com/repos/womb4t/star-trader/releases/latest')).get('tag_name')
    if not isinstance(tag,str) or not tag.startswith('v') or '/' in tag: raise ValueError('Could not find the latest release.')
    print(f'Updating to release {tag}. Saved progress will be preserved.',flush=True)
    if dry_run:
        print(f'Dry run: would download {tag} and rerun {installer_name()}.')
        return
    work = Path(tempfile.mkdtemp(prefix='star-trader-update-'))
    try:
        archive = work/'release.tar.gz'
        archive.write_bytes(fetch(f'{OFFICIAL}/archive/refs/tags/{tag}.tar.gz'))
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                name = Path(member.name)
                if name.is_absolute() or '..' in name.parts or member.issym() or member.islnk() or member.isdev():
                    raise ValueError(f'Unexpected file in release archive: {member.name}')
            tar.extractall(work)
        source = next(path for path in work.iterdir() if path.is_dir() and path.name.startswith('star-trader-'))
        subprocess.run(['bash',str(source/installer_name())],check=True,cwd=source)
    finally:
        shutil.rmtree(work,ignore_errors=True)
    print('Update complete. Restart Star Trader to use the new version.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true',help='validate and show the update without changing files')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    try:
        try: repo = resolve_checkout(here)
        except ValueError: return release_update(args.dry_run)
        remote = output(repo,'remote','get-url','origin').removesuffix('.git').rstrip('/')
        if remote not in (OFFICIAL,'git@github.com:womb4t/star-trader'):
            raise ValueError('This updater only fetches the official womb4t/star-trader repository.')
        if output(repo,'branch','--show-current') != 'main':
            raise ValueError('Switch to main before updating. Your current branch has been left unchanged.')
        if output(repo,'status','--porcelain'):
            raise ValueError('Local edits or untracked files found. Commit or back up your changes before updating.')
        print(f'Updating official checkout: {repo}',flush=True)
        print('Saved progress will be preserved. Dependency installation may ask for your password.',flush=True)
        if args.dry_run:
            print('Dry run: would fetch origin/main, merge --ff-only, then rerun the installer.')
            return
        subprocess.run(['git','-C',str(repo),'fetch','origin','main'],check=True)
        subprocess.run(['git','-C',str(repo),'merge','--ff-only','origin/main'],check=True)
        subprocess.run(['bash',str(repo/installer_name())],check=True,cwd=repo)
        print('Update complete. Restart Star Trader to use the new version.')
    except (OSError,ValueError,KeyError,StopIteration,tarfile.TarError,subprocess.CalledProcessError) as error:
        print(f'Update stopped: {error}',file=sys.stderr)
        print('You can reinstall at any time; saved progress is kept. See README.md for the install command.',file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
