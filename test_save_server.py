"""Progress storage, authentication, conflict and offline recovery regression checks."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

import star_trader as game
from save_server import Store, make_server, validate_save
from save_sync import RemoteSave, Conflict, canonical, digest


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root/'progress.sqlite3')
        self.token = 'a'*43
        self.other = 'b'*43
        self.store.create_player('Kenton',self.token)
        self.store.create_player('Other',self.other)
        self.token_file = self.root/'kenton.token'
        self.token_file.write_text(self.token)
        self.save = vars(game.Pilot()).copy()

    def tearDown(self): self.tmp.cleanup()

    def client(self):
        client = RemoteSave('http://127.0.0.1:8765',self.token_file,self.root/'client')
        def request(data=None):
            if data is None: return self.store.read(self.token)
            revision = self.store.write(self.token,data['revision'],data['save'])
            if revision is None: raise Conflict('Newer server save')
            return dict(revision=revision)
        client.request = request
        return client

    def test_accounts_are_private_and_persist_across_restart(self):
        self.assertEqual(self.store.write(self.token,0,self.save),1)
        self.assertIsNone(self.store.read(self.other)['save'])
        self.assertEqual(Store(self.root/'progress.sqlite3').read(self.token)['save'],self.save)
        with self.assertRaises(PermissionError): self.store.read('unknown')
        with self.store.connect() as db:
            self.assertNotIn(self.token,str(db.execute('SELECT * FROM players').fetchall()))

    def test_compare_and_swap_and_idempotent_retry(self):
        self.assertEqual(self.store.write(self.token,0,self.save),1)
        self.assertEqual(self.store.write(self.token,0,self.save),1)
        newer = dict(self.save,credits=999)
        self.assertEqual(self.store.write(self.token,1,newer),2)
        self.assertIsNone(self.store.write(self.token,1,self.save))
        self.assertEqual(self.store.read(self.token)['save']['credits'],999)

    def test_concurrent_writers_only_one_wins(self):
        results = []
        threads = [threading.Thread(target=lambda n=n: results.append(self.store.write(self.token,0,dict(self.save,credits=n)))) for n in (123,456)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sorted(str(v) for v in results),['1','None'])

    def test_history_bounded_and_accounts_limited(self):
        for i in range(25): self.store.write(self.token,i,dict(self.save,credits=i))
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM history').fetchone()[0],20)
        for i in range(6): self.store.create_player('p'+str(i),'token'+str(i))
        with self.assertRaises(ValueError): self.store.create_player('ninth','x')

    def test_invalid_payloads_do_not_replace_save(self):
        self.store.write(self.token,0,self.save)
        for bad in (dict(self.save,credits=-1),dict(self.save,fuel=float('nan')),dict(self.save,notes='x'*4001)):
            with self.assertRaises(ValueError): self.store.write(self.token,1,bad)
        self.assertEqual(self.store.read(self.token)['revision'],1)

    def test_import_and_sync_keep_offline_save_untouched(self):
        offline = self.root/'offline.json'
        offline.write_bytes(canonical(self.save))
        client = self.client()
        client.prepare(import_path=offline)
        client.start()
        client.offer(dict(self.save,credits=777))
        client.close()
        self.assertEqual(self.store.read(self.token)['save']['credits'],777)
        self.assertEqual(json.loads(offline.read_text()),self.save)
        self.assertEqual(json.loads(client.meta_path.read_text())['revision'],1)

    def test_clean_client_downloads_newer_progress(self):
        self.store.write(self.token,0,self.save)
        client = self.client(); client.prepare()
        newer = dict(self.save,credits=1234)
        self.store.write(self.token,1,newer)
        client.prepare()
        self.assertEqual(json.loads(client.save_path.read_text()),newer)

    def test_diverged_save_requires_explicit_restore_and_keeps_backup(self):
        self.store.write(self.token,0,self.save)
        client = self.client(); client.prepare()
        local = dict(self.save,credits=111)
        client.save_path.write_bytes(canonical(local))
        self.store.write(self.token,1,dict(self.save,credits=222))
        with self.assertRaises(Conflict): client.prepare()
        self.assertEqual(json.loads(client.save_path.read_text()),local)
        client.prepare(restore=True)
        backups = list(client.save_path.parent.glob('save.before-restore-*.json'))
        self.assertEqual(json.loads(backups[0].read_text()),local)
        self.assertEqual(json.loads(client.save_path.read_text())['credits'],222)

    def test_network_failure_requires_known_local_save_and_explicit_offline(self):
        self.store.write(self.token,0,self.save)
        client = self.client(); client.prepare()
        with patch.object(client,'request',side_effect=OSError('Unavailable')):
            with self.assertRaises(OSError): client.prepare()
            client.prepare(offline=True)
            client.offer(dict(self.save,credits=456))
            client.start(); client.close()
        self.assertEqual(self.store.read(self.token)['save'],self.save)
        self.assertIn('locally',client.status)

    def test_full_game_checkpoint_round_trip_including_session_and_notes(self):
        client = self.client(); client.prepare()
        with patch.object(game,'SAVE',client.save_path):
            original = game.Game(None)
            original.p.notes = 'Meet at Diso'
            original.p.crymto = 321
            original.station_hostilities[2] = True
            original.station_hostile_until[2] = 12345678900.
            original.remote_save = client
            client.start()
            original.checkpoint()
            client.close()
        saved = self.store.read(self.token)['save']
        self.assertEqual(saved['notes'],'Meet at Diso')
        self.assertEqual(saved['crymto'],321)
        self.assertIn('_session',saved)
        other_token = self.root/'other-device.token'; other_token.write_text(self.token)
        second = RemoteSave('http://127.0.0.1:8765',other_token,self.root/'second-device')
        second.request = client.request
        second.prepare()
        with patch.object(game,'SAVE',second.save_path):
            restored = game.Game(None)
            self.assertEqual(restored.p.notes,'Meet at Diso')
            self.assertEqual(restored.p.crymto,321)
            self.assertTrue(restored.station_hostilities[2])
            self.assertEqual(restored.station_hostile_until[2],12345678900.)

    def test_urls_cannot_send_tokens_to_public_http_or_embedded_userinfo(self):
        for url in ('http://example.com','http://8.8.8.8','https://user:password@example.com','http://localhost/other'):
            with self.assertRaises(ValueError): RemoteSave(url,self.token_file,self.root,allow_lan=True)

    def test_http_auth_validation_conflicts_and_restart(self):
        server = make_server(self.store,port=0)
        worker = threading.Thread(target=server.serve_forever,daemon=True); worker.start()
        try:
            url = 'http://127.0.0.1:'+str(server.server_port)
            with urllib.request.urlopen(url+'/health') as response: self.assertEqual(json.load(response)['protocol'],1)
            with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(url+'/v1/save')
            self.assertEqual(error.exception.code,401)
            error.exception.close()
            client = RemoteSave(url,self.token_file,self.root)
            self.assertIsNone(client.request()['save'])
            self.assertEqual(client.request(dict(revision=0,save=self.save))['revision'],1)
            with self.assertRaises(Conflict): client.request(dict(revision=0,save=dict(self.save,credits=321)))
            with self.assertRaises(RuntimeError): client.request(dict(revision=1,save=dict(self.save,credits=-10)))
        finally:
            server.shutdown(); server.server_close(); worker.join()


class HostilityTests(unittest.TestCase):
    def test_cooldown_requires_leaving_and_preserves_fines(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(game,'SAVE',Path(folder)/'save.json'):
            g = game.Game(None)
            g.station_hostilities[0] = True
            g.p.fine = 500
            g.station = [0.,0.,500.]
            with patch.object(game.time,'time',return_value=1000): g.refresh_station_hostility()
            self.assertEqual(g.station_hostile_until[0],2800)
            with patch.object(game.time,'time',return_value=3000): g.refresh_station_hostility()
            self.assertTrue(g.station_hostilities[0])
            self.assertEqual(g.station_hostile_until[0],4800)
            g.station = [0.,0.,15000.]
            with patch.object(game.time,'time',return_value=4799): g.refresh_station_hostility()
            self.assertTrue(g.station_hostilities[0])
            with patch.object(game.time,'time',return_value=4801): g.refresh_station_hostility()
            self.assertFalse(g.station_hostilities[0])
            self.assertEqual(g.p.fine,500)


if __name__ == '__main__': unittest.main()
