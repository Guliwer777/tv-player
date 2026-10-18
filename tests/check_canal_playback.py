"""Manual official-player test; persist only playback events, never session data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
env=dict(os.environ)
env['CANAL_QA']='1'
if '--silent' in sys.argv:env['CANAL_QA_SILENT']='1'
env['PYTHONPATH']=os.pathsep.join([str(ROOT/'research/gui-deps'),str(ROOT/'addon/globalPlugins/tvpVod')])
env['CANAL_ACCOUNT_FILE']=str(Path(os.environ['APPDATA'])/'nvda/tvpPlayer-canal-account.dat')
env['WEBVIEW2_USER_DATA_FOLDER']=str(Path(os.environ['APPDATA'])/'nvda/tvpPlayer-canal-webview')
events=[]
channel=sys.argv[1] if len(sys.argv)>1 else '20318'
if not channel.isdigit():raise ValueError('Invalid channel')
launcher=[str(ROOT/'addon/globalPlugins/tvpVod/bin/tvpWebPlayer.exe')] if '--packaged' in sys.argv else [sys.executable,str(ROOT/'webplayer/host.py')]
extra=[]
for value in sys.argv:
    if value.startswith('--start-at='):extra=['--canal-start',value.split('=',1)[1],'--canal-probe']
process=subprocess.Popen(launcher+extra+['--canal','--url','https://www.canalplus.com/pl/#tvp-player-channel='+channel],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8')
def read():
    for line in process.stdout:
        try:event=json.loads(line)
        except ValueError:continue
        if event.get('event') not in ('file-loaded','property-change','player-error','player-notice') and 'request_id' not in event:continue
        # Host's public playback events contain no credential data.
        events.append(event)
        if event.get('event')!='property-change' or event.get('name')=='pause':print(json.dumps(event,ensure_ascii=True),flush=True)
threading.Thread(target=read,daemon=True).start()
try:
    for tick in range(25 if '--initial-test' in sys.argv else 45):
        if process.poll() is not None:break
        command={20:['set_property','pause',True],25:['set_property','pause',False],30:['set_property','volume',0 if '--silent' in sys.argv else 50],32:['set_property','aid',2],36:['seek',-10,'relative'],39:['restart']}.get(tick)
        if '--audio-test' in sys.argv:
            command={10:['set_property','aid',1],15:['get_property','aid'],20:['set_property','aid',2],25:['get_property','aid'],30:['set_property','aid',3],35:['get_property','aid']}.get(tick)
        if '--restart-test' in sys.argv:
            command={12:['get_property','time-pos'],16:['restart'],23:['get_property','time-pos'],36:['get_property','time-pos']}.get(tick)
        if '--initial-test' in sys.argv:command=None
        if command:
            process.stdin.write(json.dumps({'command':command,'request_id':tick})+'\n');process.stdin.flush()
        time.sleep(1)
finally:
    if process.poll() is None:
        process.stdin.write(json.dumps({'command':['quit']})+'\n');process.stdin.flush()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.terminate()
    (ROOT/('research/canal-playback-events-'+channel+'.json')).write_text(json.dumps(events),encoding='utf-8')
print('EXIT',process.returncode,flush=True)
