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


if __name__ == '__main__': unittest.main()
