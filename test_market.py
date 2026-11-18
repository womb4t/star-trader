"""Shared station market: supply-and-demand prices, bot traders, server sync and visible traffic."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import star_trader as st
from market import Market, MarketClient, demand_factor
from save_server import Store, make_server
from save_sync import RemoteSave


class MarketTests(unittest.TestCase):
    def market(self):
        return st.new_market(dict(stock=[row[:] for row in st.NORMAL_STOCK],shipments=[],next_trade=None,seq=0,seed='test'))

    def test_scarcity_raises_prices_and_gluts_lower_them(self):
        self.assertEqual(demand_factor(20,20),1)
        self.assertGreater(demand_factor(0,20),demand_factor(10,20))
        self.assertLess(demand_factor(40,20),1)
        try:
            st.STOCK = [row[:] for row in st.NORMAL_STOCK]
            normal = st.price(0,0)
            st.STOCK[0][0] = 0
            self.assertGreater(st.price(0,0),normal)
            st.STOCK[0][0] = 3*st.NORMAL_STOCK[0][0]
            self.assertLess(st.price(0,0),normal)
        finally: st.STOCK = None

    def test_bots_ship_cargo_from_cheap_to_dear_and_deliver_on_arrival(self):
        m = self.market()
        m.advance(1000.)
        m.advance(1600.)
        self.assertTrue(m.state['shipments'] or m.state['seq'] > 30)
        for s in m.state['shipments']:
            self.assertGreater(s['arrive'],s['depart'])
            self.assertNotEqual(s['source'],s['dest'])
        total_before = sum(map(sum,m.stock))+sum(s['n'] for s in m.state['shipments'])
        pending = list(m.state['shipments'])
        m.deliver(10**9)
        self.assertEqual(m.state['shipments'],[])
        self.assertLessEqual(sum(map(sum,m.stock)),total_before)  # capped stations can turn cargo away, never invent it
        self.assertTrue(pending)

    def test_intercepted_traders_never_deliver(self):
        m = self.market()
        m.advance(1000.); m.advance(1400.)
        s = m.state['shipments'][0]
        before = m.stock[s['dest']][s['good']]
        m.apply(intercepts=[s['id']])
        m.deliver(s['arrive']+1)
        self.assertEqual(m.stock[s['dest']][s['good']],before)

    def test_player_trades_are_clamped_and_validated(self):
        m = self.market()
        m.apply(trades=[[0,0,-10]]*10)
        self.assertEqual(m.stock[0][0],0)
        with self.assertRaises(ValueError): m.apply(trades=[[0,0,99]])
        with self.assertRaises(ValueError): m.apply(trades=[[9,0,1]])

    def test_long_idle_spell_catches_up_quickly(self):
        m = self.market()
        m.advance(0.)
        start = time.monotonic()
        m.advance(10**8)
        self.assertLess(time.monotonic()-start,2)


class SharedMarketServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root/'p.sqlite3')
        for name,token in (('Kenton','k'*43),('Frank','f'*43)):
            self.store.create_player(name,token)
            (self.root/(name+'.token')).write_text(token)
        server = make_server(self.store,port=0)
        worker = threading.Thread(target=server.serve_forever,daemon=True); worker.start()
        self.addCleanup(lambda: (server.shutdown(),server.server_close(),worker.join()))
        self.url = 'http://127.0.0.1:'+str(server.server_port)

    def tearDown(self): self.tmp.cleanup()

    def remote(self, name):
        return RemoteSave(self.url,self.root/(name+'.token'),self.root/name)

    def test_every_commander_sees_the_same_station_stock(self):
        kenton,frank = self.remote('Kenton'),self.remote('Frank')
        first = kenton.request(dict(trades=[[2,0,-3]]),endpoint='/v1/market')
        seen = frank.request(dict(),endpoint='/v1/market')
        self.assertEqual(seen['stock'][2][0],first['stock'][2][0])
        self.assertEqual(seen['stock'],first['stock'])

    def test_bad_market_requests_are_rejected(self):
        kenton = self.remote('Kenton')
        with self.assertRaises(RuntimeError): kenton.request(dict(trades=[[0,0,500]]),endpoint='/v1/market')
        with self.assertRaises(RuntimeError): kenton.request(dict(trades='lots'),endpoint='/v1/market')

    def test_market_client_syncs_trades_into_the_game(self):
        client = MarketClient(self.remote('Kenton'),interval=.05)
        self.addCleanup(client.close)
        client.queue_trade(1,2,-2)
        for _ in range(100):
            snap = client.take()
            if snap and not client.trades: break
            time.sleep(.05)
        shared = self.store.market_exchange()
        self.assertEqual(shared['stock'][1][2],max(0,snap['stock'][1][2]))
        self.assertEqual(client.status,'Market: shared')


class TrafficTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_save = st.SAVE
        st.SAVE = Path(self.tmp.name)/'save.json'
        self.game = st.Game(None)

    def tearDown(self):
        st.SAVE = self.original_save
        st.STOCK = None
        self.tmp.cleanup()

    def shipment(self, **changes):
        now = time.time()
        s = dict(id='t-1',name='Kestrel',source=self.game.p.system,dest=(self.game.p.system+1)%8,good=0,n=4,depart=now-1,arrive=now+90)
        s.update(changes)
        return s

    def test_launching_trader_flies_out_and_jumps_away(self):
        g = self.game
        g.launch(); g.spawn = 999
        g.update_market()
        g.shipments = [self.shipment()]
        g.update_traffic(.1)
        self.assertEqual(len(g.traffic),1)
        self.assertIn('TRADER KESTREL',[c[2] for c in g.scanner_contacts()])
        g.traffic[0]['leave_at'] = time.time()-1
        g.update_traffic(.1)
        self.assertEqual(g.traffic,[])
        self.assertTrue(any(e.get('jump') for e in g.explosions))

    def test_arriving_trader_jumps_in_and_docks(self):
        g = self.game
        g.launch(); g.spawn = 999
        now = time.time()
        g.shipments = [self.shipment(id='t-2',source=(g.p.system+1)%8,dest=g.p.system,depart=now-60,arrive=now+30)]
        g.update_traffic(.1)
        self.assertEqual(g.traffic[0]['phase'],'inbound')
        for _ in range(400):
            g.shipments[0]['arrive'] -= .1  # the clock moves on
            g.update_traffic(.1)
            if not g.traffic: break
        self.assertEqual(g.traffic,[])

    def test_destroying_a_trader_spills_its_cargo_and_stops_delivery(self):
        g = self.game
        g.launch(); g.spawn = 999
        g.update_market()
        s = g.market.bot_trade(__import__('random').Random(1),time.time()) or self.shipment()
        if s not in g.market.state['shipments']: g.market.state['shipments'].append(s)
        g.shipments = [s]
        g.traffic = [dict(shipment=s,name=s['name'],phase='inbound',object=[0.,0.,400.,1])]
        g.trader_struck(g.traffic[0],2)
        self.assertEqual(g.traffic,[])
        self.assertEqual(len(g.fragments),min(s['n'],5))
        self.assertNotIn(s['id'],[x['id'] for x in g.market.state['shipments']])
        self.assertEqual(g.p.kills,1)

    def test_market_trades_go_to_the_shared_market(self):
        g = self.game
        g.mode = 'market'
        class Client:
            def __init__(self): self.trades = []
            def queue_trade(self,*t): self.trades.append(t)
            def take(self): return None
        g.market_client = Client()
        g.market_trade(0,True)
        self.assertEqual(g.market_client.trades,[(g.p.system,0,-1)])


if __name__ == '__main__':
    unittest.main()
