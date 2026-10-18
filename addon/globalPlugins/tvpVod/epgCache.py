"""Bounded disk cache for public daily EPG text; never stores sessions or playback rights."""
from datetime import date,datetime,timedelta
import hashlib,json,os,threading,time,uuid
from pathlib import Path

MAX_BYTES=30*1024*1024
MAX_FILE=2*1024*1024
_lock=threading.RLock()
_key_locks=[threading.Lock() for _ in range(32)]
_epochs={}
_last_cleanup={}
TEXT_FIELDS=('title','subtitle','description','detail_url','polsat_epg_id')


def root():
    override=os.environ.get('TVPLAYER_EPG_CACHE_DIR')
    if override:return Path(override)
    try:
        import globalVars
        return Path(globalVars.appArgs.configPath)/'tvPlayer-epg-cache'
    except (ImportError,AttributeError):return None


def prefix(provider,channel):
    return hashlib.sha256((provider+'|'+str(channel)).encode()).hexdigest()[:32]


def pack(rows):
    return [dict({key:str(row[key]) for key in TEXT_FIELDS if key in row},start=row['start'].isoformat(),end=row['end'].isoformat()) for row in rows]


def unpack(rows):
    out=[]
    if not isinstance(rows,list):raise ValueError('Bad EPG cache')
    for row in rows:
        start=datetime.fromisoformat(row['start']);end=datetime.fromisoformat(row['end'])
        if start.tzinfo is None or end.tzinfo is None or end<=start:raise ValueError('Bad EPG time')
        out.append(dict({key:str(row[key]) for key in TEXT_FIELDS if key in row},start=start,end=end))
    return out


def cleanup(directory,force=False):
    with _lock:
        now=time.time();key=str(directory)
        if not force and now-_last_cleanup.get(key,0)<60:return
        _last_cleanup[key]=now
        files=[];today=datetime.now().astimezone().date()
        for path in directory.glob('*.json'):
            try:
                day=date.fromisoformat(path.stem.rsplit('_',1)[-1])
                stat=path.stat()
                if day<today-timedelta(days=2) or day>today+timedelta(days=14) or stat.st_size>MAX_FILE:
                    path.unlink();continue
                files.append((stat.st_mtime,stat.st_size,path))
            except (OSError,ValueError):continue
        size=sum(row[1] for row in files)
        for _,length,path in sorted(files):
            if size<=MAX_BYTES:break
            try:path.unlink();size-=length
            except OSError:pass
        for path in directory.glob('*.tmp'):
            try:
                if now-path.stat().st_mtime>3600:path.unlink()
            except OSError:pass


def load(provider,channel,day,fetch,stop=None):
    directory=root()
    if directory is None:return fetch()
    key=(str(directory),prefix(provider,channel));path=directory/(key[1]+'_'+day.isoformat()+'.json')
    gate=_key_locks[hash((key,day))%len(_key_locks)]
    while not gate.acquire(timeout=.2):
        if stop is not None and stop.is_set():return []
    try:
        if stop is not None and stop.is_set():return []
        try:
            directory.mkdir(parents=True,exist_ok=True);cleanup(directory)
            with _lock:
                epoch=_epochs.get(key,0)
                if path.exists() and path.stat().st_size<=MAX_FILE:
                    document=json.loads(path.read_text(encoding='utf-8'))
                    today=datetime.now().astimezone().date()
                    ttl=2*3600 if day==today else 12*3600 if day>today else 24*3600
                    if not document['rows']:ttl=15*60
                    age=time.time()-document['fetched']
                    if document['version']==1 and document['day']==day.isoformat() and 0<=age<ttl:return unpack(document['rows'])
        except (OSError,ValueError,KeyError,TypeError):
            with _lock:epoch=_epochs.get(key,0)
        rows=fetch()
        if stop is not None and stop.is_set():return rows
        try:
            data=json.dumps({'version':1,'day':day.isoformat(),'fetched':time.time(),'rows':pack(rows)},ensure_ascii=False)
            if len(data.encode('utf-8'))>MAX_FILE:return rows
            with _lock:
                if epoch!=_epochs.get(key,0):return rows
                temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
                try:
                    temporary.write_text(data,encoding='utf-8');temporary.replace(path)
                finally:temporary.unlink(missing_ok=True)
                cleanup(directory,force=True)
        except (OSError,ValueError,KeyError,TypeError):pass
        return rows
    finally:gate.release()


def invalidate(provider,channel):
    directory=root()
    if directory is None:return
    key=(str(directory),prefix(provider,channel))
    with _lock:
        _epochs[key]=_epochs.get(key,0)+1
        for path in directory.glob(key[1]+'_*.json'):
            try:path.unlink()
            except OSError:pass
