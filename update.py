#!/usr/bin/env python3
"""Update an official checkout, then reinstall without touching the saved game."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true',help='validate and show the update without changing files')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    try:
        repo = resolve_checkout(here)
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
            print('Dry run: would fetch origin/main, merge --ff-only, then run bash install.sh.')
            return
        subprocess.run(['git','-C',str(repo),'fetch','origin','main'],check=True)
        subprocess.run(['git','-C',str(repo),'merge','--ff-only','origin/main'],check=True)
        subprocess.run(['bash',str(repo/'install.sh')],check=True,cwd=repo)
        print('Update complete. Restart Star Trader to use the new version.')
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as error:
        print(f'Update stopped: {error}',file=sys.stderr)
        print('If the original checkout was moved or removed, clone the official repository again and run bash install.sh.',file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
