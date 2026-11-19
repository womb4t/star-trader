"""Shared station market: supply-and-demand prices, bot traders, server sync and visible traffic."""
import json
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
        # The economy keeps flowing between the two requests, so a line may round one tonne apart.
        for row_a,row_b in zip(seen['stock'],first['stock']):
            for a,b in zip(row_a,row_b): self.assertLessEqual(abs(a-b),1)

    def test_bad_market_requests_are_rejected(self):
        kenton = self.remote('Kenton')
        with self.assertRaises(RuntimeError): kenton.request(dict(trades=[[0,0,500]]),endpoint='/v1/market')
        with self.assertRaises(RuntimeError): kenton.request(dict(trades='lots'),endpoint='/v1/market')

    def test_market_request_rejects_bad_smuggling(self):
        kenton = self.remote('Kenton')
        with self.assertRaises(RuntimeError): kenton.request(dict(smuggling=[[1,0,5,0]]),endpoint='/v1/market')
        with self.assertRaises(RuntimeError): kenton.request(dict(smuggling='lots'),endpoint='/v1/market')

    def test_market_client_reports_smuggling(self):
        client = MarketClient(self.remote('Kenton'),interval=.05)
        self.addCleanup(client.close)
        client.report_smuggling(1,6,lost=4)
        for _ in range(100):
            if client.take() and not client.smuggling: break
            time.sleep(.05)
        self.assertEqual(client.smuggling,[])
        self.assertEqual(json.loads(self.store_market())['smuggling']['1']['6'][0],4)   # 4 t lost, on the server's books

    def store_market(self):
        with self.store.connect() as db: return db.execute("SELECT value FROM settings WHERE key='market'").fetchone()[0]

    def test_news_needs_no_token_and_has_the_act(self):
        import urllib.request
        self.store.market_exchange(trades=[[1,0,-1]])
        with urllib.request.urlopen(self.url+'/v1/news',timeout=5) as reply: news = json.loads(reply.read())
        self.assertEqual(news['protocol'],1)
        self.assertEqual(news['acts'][0]['title'],'The Living Economy Act')
        self.assertIsInstance(news['decrees'],list)
        self.assertIn('tally',news)

    def test_market_client_syncs_trades_into_the_game(self):
        client = MarketClient(self.remote('Kenton'),interval=.05)
        self.addCleanup(client.close)
        client.queue_trade(1,2,-2)
        for _ in range(100):
            snap = client.take()
            if snap and not client.trades: break
            time.sleep(.05)
        shared = self.store.market_exchange()
        self.assertLessEqual(abs(shared['stock'][1][2]-max(0,snap['stock'][1][2])),1)
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


class LiveEconomyTests(unittest.TestCase):
    """Release 1: the live market runs the adaptive economy and the Galactic Council."""
    START = 1.8e9

    def setUp(self):
        import economy
        self.adaptive = economy.ADAPTIVE

    def tearDown(self):
        import economy
        economy.ADAPTIVE = self.adaptive

    def reviewed(self, market):
        import council
        market.advance(self.START)
        market.advance(self.START+council.WARM_UP+council.REVIEW_EVERY+60)
        return market

    def test_new_market_runs_the_council(self):
        m = self.reviewed(st.new_market(seed='t'))
        self.assertIn('council', m.state)
        self.assertEqual(len(m.state['council']['tax']), 8)

    def test_legal_prices_follow_make_and_use(self):
        m = self.reviewed(st.new_market(seed='t'))
        i, g = 1, 0
        expected = st.BASE[g]*st.quirk(i, g)*m.economy.price_adjust(i, g)*demand_factor(m.stock[i][g], m.normal[i][g]*m.depth(i))
        self.assertAlmostEqual(m.price(i, g), expected)

    def test_old_saved_market_still_loads(self):
        import json, economy
        economy.ADAPTIVE = False
        old = st.new_market(dict(stock=[row[:] for row in st.NORMAL_STOCK], shipments=[], next_trade=None, seq=0, seed='old'))
        old.advance(self.START)
        saved = json.loads(json.dumps(old.state))
        economy.ADAPTIVE = True
        m = self.reviewed(st.new_market(saved))
        self.assertEqual([len(r) for r in m.stock], [len(r) for r in st.NORMAL_STOCK])
        self.assertIn('council', m.state)

    def test_game_prices_match_the_servers_as_worlds_grow(self):
        m = self.reviewed(st.new_market(seed='t'))
        for station in m.state['stations'].values(): station['population'] = 3.   # busy worlds hold deeper stock
        m.advance(self.START+30*3600)
        self.assertGreater(m.depth(1), 1.2)
        try:
            st.STOCK, st.VIEW = m.stock, st.view_from(m.snapshot(self.START+30*3600))
            for i in range(8):
                for g in range(len(st.GOODS)): self.assertEqual(st.price(i, g), round(m.price(i, g)), (i, g))
        finally: st.STOCK = st.VIEW = None

    def test_beacon_cuts_jump_fuel_both_ways(self):
        here, there = st.coordinates(5), st.coordinates(0)
        self.assertAlmostEqual(st.jump_fuel(here, 0, [5], source=5), st.jump_fuel(here, 0, [], source=5)*.9)
        self.assertAlmostEqual(st.jump_fuel(there, 5, [5], source=0), st.jump_fuel(there, 5, [], source=0)*.9)
        deep = [4.0, 4.0]   # in deep space only the destination's beacon counts
        self.assertEqual(st.jump_fuel(deep, 5, [0]), st.jump_fuel(deep, 5, []))
        self.assertAlmostEqual(st.jump_fuel(deep, 5, [5]), st.jump_fuel(deep, 5, [])*.9)

    def test_beacon_brings_neighbours_in_range(self):
        far = [j for j in range(8) if j != 5 and j not in st.systems_in_range(5)]
        self.assertTrue(any(j in st.systems_in_range(5, [5]) for j in far))


class CouncilViewTests(unittest.TestCase):
    """Release 1: player trades pay tax, smuggling reports feed the risk premium, the snapshot carries the Council's view."""
    START = 1.8e9

    def market(self):
        import council
        m = st.new_market(seed='view')
        m.advance(self.START)
        m.advance(self.START+council.WARM_UP+council.REVIEW_EVERY+60)
        self.now = self.START+council.WARM_UP+council.REVIEW_EVERY+60
        return m

    def test_player_trades_pay_tax(self):
        import council
        m = self.market()
        m.state['council']['tax']['1'] = .05
        before, price = m.state['council']['treasury'], m.price(1, 0)
        m.apply([[1, 0, -2]], now=self.now)
        self.assertAlmostEqual(m.state['council']['treasury']-before, 2*price*.05*(1-council.HOUSE_SHARE))

    def test_smuggling_reports_move_the_premium(self):
        m = self.market()
        before = m.risk_premium(1, 6)
        m.apply(smuggling=[[1, 6, 10, 0]], now=self.now)
        self.assertGreater(m.risk_premium(1, 6), before)

    def test_one_player_cannot_flood_the_premium(self):
        import market as M
        m = self.market()
        m.apply(smuggling=[[1, 6, 50, 0]]*10, ship='Spammer', now=self.now)
        m.apply(smuggling=[[1, 6, 50, 0]]*10, ship='Spammer', now=self.now+60)
        self.assertAlmostEqual(m.state['smuggling']['1']['6'][0], M.REPORT_CAP)
        m.apply(smuggling=[[1, 6, 5, 0]], ship='Honest', now=self.now+60)   # another commander still counts
        self.assertAlmostEqual(m.state['smuggling']['1']['6'][0], M.REPORT_CAP+5, places=3)
        m.apply(smuggling=[[1, 6, 10, 0]], ship='Spammer', now=self.now+3*M.SMUGGLING_HALF_LIFE)   # allowance recovers
        self.assertGreater(m.state['smuggling']['1']['6'][0], 10)

    def test_a_docked_player_reports_only_for_their_station(self):
        m = self.market()
        m.apply(smuggling=[[1, 6, 10, 0]], ship='Kenton', system=2, now=self.now)
        self.assertNotIn('1', m.state.get('smuggling', {}))
        m.apply(smuggling=[[2, 6, 10, 0]], ship='Kenton', system=2, now=self.now)
        self.assertEqual(m.state['smuggling']['2']['6'][0], 10)

    def test_bad_smuggling_reports_are_refused(self):
        m = self.market()
        state = json.dumps(m.state, sort_keys=True)
        for bad in ([[1, 0, 5, 0]], [[9, 6, 5, 0]], [[1, 6, -1, 0]], [[1, 6, 51, 0]], [['1', 6, 1, 0]], [[1, 6, 1]], [[1, 6, 1, 0]]*11, 'lots'):
            with self.assertRaises(ValueError, msg=bad): m.apply(smuggling=bad, now=self.now)
        self.assertEqual(json.dumps(m.state, sort_keys=True), state)

    def test_snapshot_keeps_old_keys_and_adds_the_councils_view(self):
        m = self.market()
        m.state['council']['decrees'].append(dict(kind='relief', system=5, at=self.now, text='Relief convoy sent to Velmora', id='relief-5-1'))
        snap = m.snapshot(self.now)
        self.assertEqual(snap['protocol'], 1)
        self.assertEqual(len(snap['stock']), 8)
        self.assertIsInstance(snap['shipments'], list)
        self.assertEqual(len(snap['economy']), 8)
        council = snap['council']
        self.assertEqual(len(council['tax']), 8)
        self.assertEqual(len(council['safety']), 8)
        self.assertIsInstance(council['rate'], float)
        self.assertIsInstance(council['beacons'], list)
        self.assertEqual(council['decrees'][-1], dict(id='relief-5-1', at=self.now, kind='relief', system=5, text='Relief convoy sent to Velmora'))
        self.assertLessEqual(len(council['decrees']), 10)
        prices = snap['prices']
        self.assertEqual([len(r) for r in prices['adjust']], [10]*8)
        self.assertEqual([len(r) for r in prices['contraband']], [len(st.ILLEGAL)]*8)
        premium, loss = prices['contraband'][1][0]
        self.assertAlmostEqual(premium, m.risk_premium(1, st.ILLEGAL[0]))
        self.assertAlmostEqual(loss, m.loss_share(1, st.ILLEGAL[0]))
        json.dumps(snap)   # it must travel as JSON

    def test_decrees_get_ids(self):
        import council
        m = self.market()
        made = []
        council.record(m.state['council'], dict(kind='relief', good=None), 5, self.now, ['a']*8, st.GOODS, made)
        self.assertEqual(made[0]['id'], f'relief-5-{int(self.now)}')
