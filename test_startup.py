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
        screen.settings = False
        screen.field = 0
        screen.selected = 0
        screen.error = ''
        screen.replace_field = False
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
        self.assertTrue(loaded['allow_lan'])
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
        self.assertEqual(startup.load_connection()['server'],'')
        self.path.write_text('{"server": false, "allow_lan": "no"}')
        self.assertFalse(startup.load_connection()['allow_lan'])


if __name__ == '__main__': unittest.main()
