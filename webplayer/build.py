"""Build the isolated browser host with project-local build dependencies."""
import os
from pathlib import Path
import subprocess
import sys
import shutil
import ssl

root=Path(__file__).resolve().parents[1]
env=dict(os.environ)
env['PYTHONPATH']=os.pathsep.join(str(root/'research'/name) for name in ('build-deps','gui-deps'))
# Some bundled Python runtimes require an adjacent TLS resource from ssl.py.
# Preserve that runtime's TLS configuration when freezing; never disable verification.
tls_resource=Path(ssl.__file__).with_name('codex-rejected-cas.pem')
tls_data=['--add-data',str(tls_resource)+os.pathsep+'.'] if tls_resource.is_file() else []
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--console',
    *tls_data,
    '--name','tvpWebPlayer','--distpath',str(root/'research/webplayer-dist'),
    '--workpath',str(root/'research/webplayer-build'),'--specpath',str(root/'research'),
    '--add-data',str(root/'webplayer/bridge.js')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/canal_bridge.js')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/polsat_bridge.js')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/playerpl_bridge.js')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/audio_hooks.js')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/index.html')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/direct.js')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/bootstrap.js')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/vendor')+os.pathsep+'vendor',
    '--add-binary',str(root/'research/gui-deps/wx/WebView2Loader.dll')+os.pathsep+'.',
    '--paths',str(root/'addon/globalPlugins/tvpVod'),
    '--paths',str(root/'research/gui-deps'),str(root/'webplayer/host.py')],
    cwd=root,env=env,check=True)
check_env=dict(env);check_env.pop('SSLKEYLOGFILE',None)
subprocess.run([str(root/'research/webplayer-dist/tvpWebPlayer/tvpWebPlayer.exe'),'--check-components'],env=check_env,check=True,capture_output=True,timeout=20)
if '--stage-only' not in sys.argv:
    shutil.copytree(root/'research/webplayer-dist/tvpWebPlayer',root/'addon/globalPlugins/tvpVod/bin',dirs_exist_ok=True)
