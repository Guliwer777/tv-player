"""Build the isolated browser host with project-local build dependencies."""
import os
from pathlib import Path
import subprocess
import sys
import shutil

root=Path(__file__).resolve().parents[1]
env=dict(os.environ)
env['PYTHONPATH']=os.pathsep.join(str(root/'research'/name) for name in ('build-deps','gui-deps'))
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--console',
    '--name','tvpWebPlayer','--distpath',str(root/'research/webplayer-dist'),
    '--workpath',str(root/'research/webplayer-build'),'--specpath',str(root/'research'),
    '--add-data',str(root/'webplayer/bridge.js')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/index.html')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/direct.js')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/bootstrap.js')+os.pathsep+'.',
    '--add-data',str(root/'webplayer/vendor')+os.pathsep+'vendor',
    '--add-binary',str(root/'research/gui-deps/wx/WebView2Loader.dll')+os.pathsep+'.',
    '--paths',str(root/'addon/globalPlugins/tvpVod'),
    '--paths',str(root/'research/gui-deps'),str(root/'webplayer/host.py')],
    cwd=root,env=env,check=True)
shutil.copytree(root/'research/webplayer-dist/tvpWebPlayer',root/'addon/globalPlugins/tvpVod/bin',dirs_exist_ok=True)
