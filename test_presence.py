"""Shared presence protocol and cockpit/world coordinate regression checks."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

from presence import SharedPresence, PresenceBusy
import star_trader as game
from save_server import Store, make_server
from save_sync import RemoteSave


def state(system=0,position=None):
    return dict(system=system,mode='flight',position=position or [0.,0.,-1500.],velocity=[0.,0.,30.],
                session='a'*32,sequence=1,epoch='c'*32)


class UniverseTests(unittest.TestCase):
    def test_shared_roster_and_all_eight_systems(self):
        world = SharedPresence()
        for i in range(8):
            data = state(i); data['session'] = str(i)*32
            reply = world.exchange(i,'Pilot'+str(i),data)
        self.assertEqual(len(reply['players']),8)
        self.assertEqual({p['system'] for p in reply['players']},set(range(8)))
        self.assertNotIn('session',reply['players'][0])
        data = state(7); data.update(sequence=2,session='7'*32)
        reply = world.exchange(7,'Pilot7',data)
        self.assertEqual(reply['you'],7)

    def test_sequence_movement_validation_and_no_forged_identity(self):
        world = SharedPresence()
        with patch('presence.time.monotonic',return_value=100): world.exchange(1,'RealName',state())
        with patch('presence.time.monotonic',return_value=100.1):
            with self.assertRaises(ValueError): world.exchange(1,'RealName',state())
            data = state(position=[0.,0.,100000]); data['sequence']=2
            with self.assertRaises(ValueError): world.exchange(1,'RealName',data)
            data = state(); data.update(sequence=2,velocity=[float('nan'),0,0])
            with self.assertRaises(ValueError): world.exchange(1,'RealName',data)
            data = state(); data.update(sequence=2,system=8)
            with self.assertRaises(ValueError): world.exchange(1,'RealName',data)
        self.assertEqual(world.players[1]['sequence'],1)

    def test_duplicate_login_and_expiring_disconnected_players(self):
        world = SharedPresence()
        with patch('presence.time.monotonic',return_value=100): world.exchange(1,'Kenton',state())
        other = state(); other['session']='b'*32
        with patch('presence.time.monotonic',return_value=101):
            with self.assertRaises(PresenceBusy): world.exchange(1,'Kenton',other)
        with patch('presence.time.monotonic',return_value=111):
            reply = world.exchange(2,'Tester',other)
            self.assertEqual([p['id'] for p in reply['players']],[2])
            world.exchange(1,'Kenton',other)

    def test_http_two_authenticated_players_share_presence_without_touching_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); store=Store(root/'server.sqlite3')
            tokens=('a'*43,'b'*43)
            for i,token in enumerate(tokens): store.create_player('Pilot'+str(i),token)
            server=make_server(store,port=0)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            try:
                clients=[]
                for i,token in enumerate(tokens):
                    token_path=root/f'{i}.token'; token_path.write_text(token)
                    clients.append(RemoteSave(f'http://127.0.0.1:{server.server_port}',token_path,root/f'client{i}'))
                clients[0].request(state(),endpoint='/v1/presence')
                result=clients[1].request(state(7),endpoint='/v1/presence')
                self.assertEqual({p['name'] for p in result['players']},{'Pilot0','Pilot1'})
                self.assertEqual({p['system'] for p in result['players']},{0,7})
                self.assertTrue(all(store.read(token)['save'] is None for token in tokens))
                data=state(); data.update(sequence=2,system=7)
                result=clients[0].request(data,endpoint='/v1/presence')
                self.assertEqual(sum(p['system']==7 for p in result['players']),2)
                spoof=state(); spoof['session']='d'*32
                with self.assertRaises(RuntimeError): clients[0].request(spoof,endpoint='/v1/presence')
            finally: server.shutdown();server.server_close();thread.join()


class CoordinateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patch=patch.object(game,'SAVE',Path(self.tmp.name)/'save.json');self.patch.start()
        self.g=game.Game(None)

    def tearDown(self): self.patch.stop();self.tmp.cleanup()

    def test_turning_does_not_teleport_player_in_world_frame(self):
        g=self.g;g.mode='flight';g.station=[100.,50.,1500.]
        position=g.presence_state()['position']
        g.roll=.6;g.turn_world(.3,-.2);g.turn_world(-.5,.4)
        for before,after in zip(position,g.presence_state()['position']): self.assertAlmostEqual(before,after,places=8)
        g.move_world(0,0,10)
        self.assertAlmostEqual(sum((a-b)**2 for a,b in zip(position,g.presence_state()['position'])),100,places=7)

    def test_players_are_visible_only_in_same_system_and_scanner_selectable(self):
        class FakePresence:
            def offer(self,value): self.last=value
        g=self.g;g.mode='flight';g.presence=FakePresence()
        g.presence.snapshot=dict(you=1,players=[
            dict(id=1,name='You',system=0,mode='flight',position=[0,0,0]),
            dict(id=2,name='Friend',system=0,mode='flight',position=[100,0,-600]),
            dict(id=3,name='Elsewhere',system=1,mode='flight',position=[0,0,0]),
            dict(id=4,name='Docked',system=0,mode='docked',position=[0,0,0])])
        g.update_shared_presence()
        self.assertEqual(list(g.other_players),[2])
        obj=g.other_players[2]['object']
        self.assertEqual(obj,[100.,0.,900.])
        sx,sy=g.scanner_position(obj);g.buttons=[];g.click(sx,sy)
        self.assertIs(g.ship_target,obj)
        self.assertEqual(g.player_label(obj),'PLAYER Friend')
        g.turn_world(.3,.2);g.update_shared_presence()
        self.assertIs(g.other_players[2]['object'],obj)
        g.p.system=1;g.update_shared_presence()
        self.assertEqual(list(g.other_players),[3])

    def test_frame_survives_save_reload_and_new_flight_resets_it(self):
        g=self.g;g.mode='flight';g.roll=.2;g.turn_world(.3,.1);g.spawn=10000
        g.checkpoint();expected=g.presence_state()['position']
        restored=game.Game(None)
        for a,b in zip(expected,restored.presence_state()['position']): self.assertAlmostEqual(a,b,delta=.1)
        old_epoch=restored.world_epoch
        restored.launch(False)
        self.assertNotEqual(restored.world_epoch,old_epoch)
        self.assertEqual(restored.world_basis,[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])


if __name__=='__main__':unittest.main()
