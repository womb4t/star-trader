#!/usr/bin/env python3
"""Read players' bug reports and suggestions from the progress server (admin key required)."""
import argparse
import json
from pathlib import Path
import time
import urllib.request


def call(server, token, path, data=None):
    req = urllib.request.Request(server.rstrip('/')+path,data=json.dumps(data).encode() if data is not None else None,
                                 method='POST' if data is not None else 'GET',
                                 headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req,timeout=10) as response: return json.loads(response.read())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server',default='https://141-147-67-78.sslip.io')
    parser.add_argument('--token-file',type=Path,default=Path.home()/'.config/star-trader/admin.token')
    parser.add_argument('--status',choices=('new','seen','done'),default='new')
    parser.add_argument('--json',action='store_true',help='print raw JSON')
    parser.add_argument('--mark',choices=('seen','done'),help='after listing, mark the listed reports')
    args = parser.parse_args()
    token = args.token_file.read_text().strip()
    items = call(args.server,token,'/v1/admin/feedback?status='+args.status)['feedback']
    if args.json: print(json.dumps(items,indent=2))
    else:
        for item in items:
            when = time.strftime('%Y-%m-%d %H:%M',time.localtime(item['received']))
            details = ', '.join(f'{k} {v}' for k,v in item['details'].items())
            print(f"{item['id'][:8]}  {when}  {item['player']}  {item['kind'].upper()}  ({details})\n    {item['text']}\n")
        print(f'{len(items)} {args.status} report(s).')
    if args.mark and items:
        changed = call(args.server,token,'/v1/admin/feedback/status',dict(ids=[i['id'] for i in items],status=args.mark))['changed']
        print(f'Marked {changed} as {args.mark}.')


if __name__ == '__main__':
    main()
