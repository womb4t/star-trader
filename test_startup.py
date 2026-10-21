"""Startup mode selection, settings and safe legacy launcher migration."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import startup
import star_trader as st


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'connection.json'
        self.patch = patch.object(startup,'config_path',return_value=self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop(); self.tmp.cleanup()

    def screen(self):
        screen = startup.StartScreen.__new__(startup.StartScreen)
        screen.config = startup.load_connection()
        screen.config['server'] = 'http://192.168.1.45:8766'
        token = Path(self.tmp.name)/'existing.token'
        token.write_text('t'*43)
        screen.config['token_file'] = str(token)
        screen.settings = False
        screen.field = 0
        screen.selected = 0
        screen.error = ''
        screen.replace_field = False
        screen.signup = None
        screen.auto_at = None
        return screen

    def test_keyboard_and_mouse_select_both_modes(self):
        screen = self.screen()
        self.assertEqual(screen.event('down',13),'online')
        screen.event('down',st.RIGHT)
        self.assertEqual(screen.event('down',13),'offline')
        self.assertEqual(screen.event('click',(200,640)),'online')
        self.assertEqual(screen.event('click',(500,640)),'offline')
        self.assertIsNone(screen.event('click',(100,200)))

    def test_escape_always_closes_including_settings_and_text(self):
        screen = self.screen()
        for settings in (False,True):
            screen.settings = settings
            self.assertEqual(screen.event('down',27),'quit')
            self.assertEqual(screen.event('quit',0),'quit')

    def test_missing_connection_opens_settings(self):
        screen = self.screen(); screen.config['server'] = ''
        self.assertIsNone(screen.activate(0))
        self.assertTrue(screen.settings)
        self.assertIn('server address',screen.error)

    def test_settings_persist_paths_without_reading_token(self):
        screen = self.screen(); screen.settings = True
        screen.field = 1; screen.replace_field = True
        screen.event('text',str(Path(self.tmp.name)/'private.token'))
        screen.event('click',(100,390))
        screen.event('click',(100,570))
        self.assertFalse(screen.settings)
        loaded = startup.load_connection()
        self.assertEqual(loaded['token_file'],str(Path(self.tmp.name)/'private.token'))
        self.assertFalse(loaded['allow_lan'])  # the click toggled the default off
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)

    def test_legacy_migration_never_executes_shell_and_preserves_existing_config(self):
        script = Path(self.tmp.name)/'launcher'
        marker = Path(self.tmp.name)/'should-not-exist'
        script.write_text('#!/bin/bash\nexec python3 game.py --server http://192.168.1.45:8766 \\\n --token-file "$HOME/.config/star-trader/kenton.token" --allow-lan --import-local-save\ntouch '+str(marker))
        self.assertTrue(startup.migrate_online_launcher(script))
        self.assertFalse(marker.exists())
        self.assertEqual(startup.load_connection()['server'],'http://192.168.1.45:8766')
        self.assertTrue(startup.load_connection()['token_file'].startswith(str(Path.home())))
        script.write_text('bad launcher')
        self.assertFalse(startup.migrate_online_launcher(script))
        self.assertEqual(startup.load_connection()['server'],'http://192.168.1.45:8766')

    def test_connection_failure_can_return_to_offline_without_touching_online_save(self):
        from unittest.mock import MagicMock
        fake_display = MagicMock()
        fake_game = MagicMock(running=False)
        screen = MagicMock()
        screen.config = dict(server='http://192.168.1.45:8766',token_file='/private/token',allow_lan=True,import_local_save=False)
        screen.choose.side_effect = ['online','offline']
        offline_save = Path(self.tmp.name)/'offline/save.json'
        with patch.object(st,'SAVE',offline_save), patch.object(st.sys,'argv',['star_trader.py']), \
             patch.object(st,'Display',return_value=fake_display), patch.object(st,'Game',return_value=fake_game) as create_game, \
             patch.object(startup,'StartScreen',return_value=screen), \
             patch('save_sync.RemoteSave',side_effect=OSError('Server unavailable')):
            st.main()
            self.assertEqual(st.SAVE,offline_save)
            create_game.assert_called_once_with(fake_display)
            self.assertEqual(screen.choose.call_count,2)
            self.assertIn('Offline play',screen.error)
            screen.close.assert_called_once()
            self.assertFalse(offline_save.exists())

    def test_bad_config_falls_back_without_breaking_offline(self):
        self.path.write_text('{broken')
        self.assertEqual(startup.load_connection()['server'],startup.DEFAULT_SERVER)
        self.path.write_text('{"server": false, "allow_lan": "no"}')
        self.assertEqual(startup.load_connection()['server'],startup.DEFAULT_SERVER)
        self.assertTrue(startup.load_connection()['allow_lan'])

    def test_fresh_install_defaults_to_the_community_server(self):
        config = startup.load_connection()
        self.assertEqual(config['server'],startup.DEFAULT_SERVER)
        self.assertTrue(config['allow_lan'])

    def test_clicking_a_field_focuses_it_without_hiding_replacement(self):
        screen = self.screen(); screen.settings = True
        screen.config['token_file'] = '/old/path'
        screen.event('click',(100,310))
        self.assertEqual((screen.field,screen.replace_field),(1,False))
        screen.event('down',8)
        self.assertEqual(screen.config['token_file'],'/old/pat')

    def test_invite_code_round_trip_sets_server_and_private_token(self):
        code = startup.make_invite('http://192.168.1.45:8766/','Friend_1','t'*43)
        screen = self.screen(); screen.settings = True
        screen.event('text',code)
        self.assertFalse(screen.settings)
        self.assertIn('Friend_1',screen.error)
        loaded = startup.load_connection()
        token_file = Path(loaded['token_file'])
        self.assertEqual(token_file,self.path.with_name('friend_1.token'))
        self.assertEqual(token_file.read_text().strip(),'t'*43)
        self.assertEqual(token_file.stat().st_mode & 0o777,0o600)
        self.assertEqual(loaded['server'],'http://192.168.1.45:8766')
        self.assertNotIn('t'*43,self.path.read_text())

    def test_bad_invite_codes_change_nothing(self):
        good = startup.make_invite('http://192.168.1.45:8766','Friend','t'*43)
        for code in ('hello',good[:-10],startup.make_invite('ftp://x','Friend','t'*43),startup.make_invite('http://x:1','bad name','t'*43),startup.make_invite('http://x:1','Friend','short')):
            with self.subTest(code=code):
                screen = self.screen(); screen.settings = True
                screen.paste_invite(code)
                self.assertTrue(screen.settings)
                self.assertTrue(screen.error)
                self.assertFalse(self.path.exists())

    def test_online_without_a_login_opens_signup(self):
        screen = self.screen()
        screen.config['token_file'] = str(Path(self.tmp.name)/'missing.token')
        self.assertIsNone(screen.activate(0))
        self.assertIsNotNone(screen.signup)
        self.assertIn('Paste invite',screen.error)

    def test_signup_form_creates_account_and_saves_private_token(self):
        screen = self.screen(); screen.draw = lambda: None
        screen.open_signup()
        screen.event('text','Nova_7')
        screen.event('down',9)
        screen.event('text','nova@example.com')
        with patch('save_sync.signup',return_value='z'*43) as call:
            screen.event('down',13)
        call.assert_called_once_with('http://192.168.1.45:8766','Nova_7','nova@example.com',allow_lan=True)
        self.assertIsNone(screen.signup)
        self.assertIn('Welcome aboard, Nova_7',screen.error)
        loaded = startup.load_connection()
        self.assertEqual(Path(loaded['token_file']).read_text().strip(),'z'*43)
        self.assertEqual(Path(loaded['token_file']).stat().st_mode & 0o777,0o600)
        self.assertEqual(screen.activate(0),'online')

    def test_signup_errors_keep_the_form_open(self):
        screen = self.screen(); screen.draw = lambda: None
        screen.open_signup()
        screen.event('down',13)
        self.assertIn('pilot name',screen.error)
        screen.event('text','Taken')
        with patch('save_sync.signup',side_effect=RuntimeError('That pilot name is taken. Choose another.')):
            screen.event('down',13)
        self.assertIsNotNone(screen.signup)
        self.assertIn('taken',screen.error)
        self.assertFalse(self.path.exists())

    def test_last_online_player_reconnects_automatically_unless_a_key_is_pressed(self):
        from unittest.mock import MagicMock
        token = Path(self.tmp.name)/'me.token'; token.write_text('t'*43)
        config = dict(startup.load_connection(),last_mode='online',token_file=str(token))
        display = MagicMock(); display.events.return_value = []
        with patch.object(startup.StartScreen,'draw'), patch.object(startup.time,'sleep'):
            screen = startup.StartScreen(display,config)
            screen.auto_at = startup.time.monotonic()-1
            self.assertEqual(screen.choose(),'online')
            screen = startup.StartScreen(display,config)
            screen.event('down',st.DOWN)
            self.assertIsNone(screen.auto_at)
            self.assertIsNone(startup.StartScreen(display,dict(config,last_mode='offline')).auto_at)
            self.assertIsNone(startup.StartScreen(display,config,error='Server unavailable').auto_at)

    def test_chosen_mode_is_remembered(self):
        from unittest.mock import MagicMock
        display = MagicMock(); display.events.return_value = [('down',st.DOWN),('down',13)]
        with patch.object(startup.StartScreen,'draw'), patch.object(startup.time,'sleep'):
            screen = startup.StartScreen(display,startup.load_connection())
            self.assertEqual(screen.choose(),'offline')
        self.assertEqual(startup.load_connection()['last_mode'],'offline')

    def test_new_install_uses_public_server_and_invite_works_from_signup(self):
        self.assertTrue(startup.DEFAULT_SERVER.startswith('https://'))
        screen = self.screen(); screen.draw = lambda: None
        screen.open_signup()
        screen.event('text',startup.make_invite(startup.DEFAULT_SERVER,'Frank','f'*43))
        self.assertIsNone(screen.signup)
        self.assertIn('Frank',screen.error)
        self.assertEqual(startup.load_connection()['server'],startup.DEFAULT_SERVER)
        screen.open_signup()
        screen.invite_from_signup('not an invite')
        self.assertIsNotNone(screen.signup)


if __name__ == '__main__': unittest.main()
