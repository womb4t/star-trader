"""Updater boundary checks; never contacts GitHub or changes the checkout."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import update


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo/'.git').mkdir()
        self.file = patch.object(update,'__file__',str(self.repo/'update.py'))
        self.file.start()
        self.checkout = patch.object(update,'is_checkout',side_effect=lambda path:path == self.repo)
        self.checkout.start()

    def tearDown(self):
        self.checkout.stop()
        self.file.stop()
        self.tmp.cleanup()

    def answers(self, dirty='', origin=update.OFFICIAL+'.git', branch='main'):
        def answer(repo,*args):
            return origin if args[0] == 'remote' else branch if args[0] == 'branch' else dirty
        return answer

    def test_empty_git_placeholder_does_not_override_install_metadata(self):
        import json
        installed = self.repo/'installed'
        installed.mkdir()
        (installed/'.git').mkdir()
        (installed/'install-info.json').write_text(json.dumps(dict(source=str(self.repo))))
        self.assertEqual(update.resolve_checkout(installed),self.repo)

    def test_real_git_probe_rejects_empty_directory(self):
        self.checkout.stop()
        try: self.assertFalse(update.is_checkout(self.repo))
        finally: self.checkout.start()

    def test_missing_recorded_checkout_stops_with_clear_error(self):
        import json
        installed = self.repo/'installed'
        installed.mkdir()
        (installed/'install-info.json').write_text(json.dumps(dict(source=str(self.repo/'missing'))))
        with self.assertRaisesRegex(ValueError,'recorded source checkout'):
            update.resolve_checkout(installed)

    def test_dry_run_does_not_fetch_or_install(self):
        with patch.object(update,'output',side_effect=self.answers()), patch.object(update.sys,'argv',['update.py','--dry-run']), patch.object(update.subprocess,'run') as run, contextlib.redirect_stdout(io.StringIO()):
            update.main()
        run.assert_not_called()

    def test_local_edits_or_wrong_origin_stop_before_network(self):
        for dirty,origin,branch in [(' M star_trader.py',update.OFFICIAL,'main'),('?? my-notes',update.OFFICIAL,'main'),('','https://example.com/untrusted','main'),('',update.OFFICIAL,'experiment')]:
            with self.subTest(dirty=dirty,origin=origin,branch=branch), patch.object(update,'output',side_effect=self.answers(dirty,origin,branch)), patch.object(update.sys,'argv',['update.py']), patch.object(update.subprocess,'run') as run, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit): update.main()
                run.assert_not_called()

    def test_update_only_fast_forwards_and_reruns_installer(self):
        with patch.object(update,'output',side_effect=self.answers()), patch.object(update.sys,'argv',['update.py']), patch.object(update.subprocess,'run') as run, contextlib.redirect_stdout(io.StringIO()):
            update.main()
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(calls,[['git','-C',str(self.repo),'fetch','origin','main'],['git','-C',str(self.repo),'merge','--ff-only','origin/main'],['bash',str(self.repo/'install.sh')]])

    def test_mac_update_reruns_mac_installer(self):
        with patch.object(update,'output',side_effect=self.answers()), patch.object(update.sys,'argv',['update.py']), patch.object(update.sys,'platform','darwin'), patch.object(update.subprocess,'run') as run, contextlib.redirect_stdout(io.StringIO()):
            update.main()
        self.assertEqual(run.call_args_list[-1].args[0],['bash',str(self.repo/'install-mac.sh')])


class MacInstallTests(unittest.TestCase):
    def test_mac_app_bundle_launches_installed_game(self):
        import install
        with tempfile.TemporaryDirectory() as home, patch.object(install.Path,'home',return_value=Path(home)), contextlib.redirect_stdout(io.StringIO()):
            target = Path(home)/"Game's folder"
            install.install_mac_app(target)
            contents = Path(home)/'Applications'/'Star Trader.app'/'Contents'
            self.assertIn('<string>star-trader</string>',(contents/'Info.plist').read_text())
            launcher = contents/'MacOS'/'star-trader'
            self.assertTrue(launcher.stat().st_mode & 0o111)
            import subprocess
            out = subprocess.run(['sh','-n',str(launcher)],capture_output=True)
            self.assertEqual(out.returncode,0)
            self.assertIn("'"+str(target).replace("'","'\\''")+"/star_trader.py'",launcher.read_text())

    def test_mac_app_runs_python_from_inside_its_own_bundle(self):
        import install
        with tempfile.TemporaryDirectory() as home, contextlib.redirect_stdout(io.StringIO()):
            prefix = Path(home)/'Python.framework'
            binary = prefix/'Resources'/'Python.app'/'Contents'/'MacOS'/'Python'
            binary.parent.mkdir(parents=True); binary.write_text('python')
            with patch.object(install.Path,'home',return_value=Path(home)), patch.object(install.sys,'base_prefix',str(prefix)):
                install.install_mac_app(Path(home)/'game')
            macos = Path(home)/'Applications'/'Star Trader.app'/'Contents'/'MacOS'
            self.assertEqual((macos/'Star Trader').read_text(),'python')
            self.assertIn('"$(dirname "$0")/Star Trader"',(macos/'star-trader').read_text())


class AutoUpdateTests(unittest.TestCase):
    def setUp(self):
        import os, star_trader
        self.st = star_trader
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patches = [patch.object(star_trader,'__file__',str(self.root/'star_trader.py')),
                        patch.object(star_trader,'SAVE',self.root/'data'/'save.json'),
                        patch.dict(os.environ,{'STAR_TRADER_NO_UPDATE_CHECK':'0'}),
                        patch.object(star_trader.sys,'argv',['star_trader.py']),
                        patch.object(star_trader,'notify')]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def install(self):
        (self.root/'install-info.json').write_text('{}')
        (self.root/'update.py').write_text('')

    def run_update(self, latest, returncode=0):
        result = type('Result',(),dict(returncode=returncode,stdout='out',stderr=''))()
        with patch.object(self.st.UpdateNotice,'fetch_latest',return_value=latest), \
             patch.object(self.st.subprocess,'run',return_value=result) as run, \
             patch.object(self.st.os,'execv') as execv:
            self.st.auto_update()
        return run,execv

    def test_installs_newer_release_and_restarts(self):
        self.install()
        run,execv = self.run_update('v99.0.0')
        self.assertEqual(run.call_args.args[0][1],str(self.root/'update.py'))
        self.assertIs(run.call_args.kwargs['stdin'],self.st.subprocess.DEVNULL)
        self.assertTrue(execv.called)
        self.assertIn('--no-update-check',execv.call_args.args[1])

    def test_failed_update_starts_current_version(self):
        self.install()
        run,execv = self.run_update('v99.0.0',returncode=1)
        self.assertTrue(run.called)
        self.assertFalse(execv.called)
        self.assertIn('out',(self.root/'data'/'update.log').read_text())

    def test_same_version_or_source_checkout_does_nothing(self):
        run,execv = self.run_update('v99.0.0')
        self.assertFalse(run.called)
        self.install()
        run,execv = self.run_update('v'+self.st.VERSION)
        self.assertFalse(run.called)


if __name__ == '__main__': unittest.main()
