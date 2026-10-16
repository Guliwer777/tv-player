import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch,Mock

spec=importlib.util.spec_from_file_location('runtime_setup',Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod/runtimeSetup.py')
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

class RuntimeSetupTests(unittest.TestCase):
    def test_present_runtime_does_not_download_or_run_installer(self):
        with patch.object(runtime,'installed_version',return_value='155.0.1.2'),patch.object(runtime,'download_installer') as download:
            runtime.ensure_runtime()
            download.assert_not_called()

    def test_missing_runtime_verifies_before_install_and_checks_result(self):
        order=[]
        with patch.object(runtime,'installed_version',side_effect=[None,None,None,'155.0.1.2']),patch.object(runtime,'download_installer',side_effect=lambda p:order.append('download')),patch.object(runtime,'verify_installer',side_effect=lambda p:order.append('verify')),patch.object(runtime.subprocess,'run',side_effect=lambda *a,**kw:(order.append('install') or Mock(returncode=0))) as run:
            runtime.ensure_runtime()
            self.assertEqual(order,['download','verify','install'])
            self.assertEqual(run.call_args.args[0][1:],['/silent','/install'])

    def test_untrusted_installer_is_never_executed(self):
        with patch.object(runtime,'installed_version',return_value=None),patch.object(runtime,'download_installer'),patch.object(runtime,'verify_installer',side_effect=runtime.RuntimeSetupError('Bad signature')),patch.object(runtime.subprocess,'run') as run:
            with self.assertRaises(runtime.RuntimeSetupError):runtime.ensure_runtime()
            run.assert_not_called()

    def test_success_exit_code_alone_does_not_claim_runtime_is_installed(self):
        with patch.object(runtime,'installed_version',return_value=None),patch.object(runtime,'download_installer'),patch.object(runtime,'verify_installer'),patch.object(runtime.subprocess,'run',return_value=Mock(returncode=0)),patch.object(runtime.time,'sleep'):
            with self.assertRaisesRegex(runtime.RuntimeSetupError,'Nie potwierdzono'):runtime.ensure_runtime()

    def test_signature_and_microsoft_publisher_both_required(self):
        for status,subject in [('Valid','CN=Someone, O=Other Company'),('NotSigned','CN=Microsoft, O=Microsoft Corporation')]:
            output=runtime.json.dumps({'status':status,'subject':subject}).encode()
            with patch.object(runtime.subprocess,'run',return_value=Mock(returncode=0,stdout=output)):
                with self.assertRaises(runtime.RuntimeSetupError):runtime.verify_installer(Path('unused.exe'))

    def test_redirect_destination_must_stay_on_microsoft_https_hosts(self):
        for url in ['http://go.microsoft.com/file','https://microsoft.com.evil.example/file','https://user@go.microsoft.com/file','https://go.microsoft.com:8443/file']:
            self.assertFalse(runtime.microsoft_url(url))
        self.assertTrue(runtime.microsoft_url('https://msedge.sf.dl.delivery.mp.microsoft.com/file'))
