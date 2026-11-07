#!/usr/bin/env python3
"""Catalogo NBA Recap: playlist NBA e Ximo Pierto, senza perdere lo storico."""
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'catalog.json'
PLAYLISTS = {
    'nightly_recap': 'https://www.youtube.com/playlist?list=PLaMWIRum7wA0',
    'nba_game': 'https://www.youtube.com/playlist?list=PLftRqjkDhxkg',
    'ximo_game': 'https://www.youtube.com/playlist?list=PLXBbEV1pljZA',
}
TEAMS = {
    'Hawks':['hawks','atlanta'], 'Celtics':['celtics','boston'],
    'Nets':['nets','brooklyn'], 'Hornets':['hornets','charlotte'],
    'Bulls':['bulls','chicago'], 'Cavaliers':['cavaliers','cavs','cleveland'],
    'Mavericks':['mavericks','mavs','dallas'], 'Nuggets':['nuggets','denver'],
    'Pistons':['pistons','detroit'], 'Warriors':['warriors','golden state','gsw'],
    'Rockets':['rockets','houston'], 'Pacers':['pacers','indiana'],
    'Clippers':['clippers','la clippers','lac'],
    'Lakers':['lakers','los angeles lakers','lal'],
    'Grizzlies':['grizzlies','memphis'], 'Heat':['heat','miami'],
    'Bucks':['bucks','milwaukee'], 'Timberwolves':['timberwolves','wolves','minnesota'],
    'Pelicans':['pelicans','new orleans'], 'Knicks':['knicks','new york'],
    'Thunder':['thunder','oklahoma city','okc'], 'Magic':['magic','orlando'],
    '76ers':['76ers','sixers','philadelphia'], 'Suns':['suns','phoenix'],
    'Trail Blazers':['trail blazers','blazers','portland'],
    'Kings':['kings','sacramento'], 'Spurs':['spurs','san antonio'],
    'Raptors':['raptors','toronto'], 'Jazz':['jazz','utah'],
    'Wizards':['wizards','washington'],
}
MONTHS={name.lower():n for n,name in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'],1)}
MONTHS.update({'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'aug':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12})
DATE_RE=re.compile(r'\b('+'|'.join(MONTHS)+r')\.?\s+(\d{1,2}),?\s+(\d{4})\b',re.I)
NUM_DATE_RE=re.compile(r'(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](20\d{2})(?!\d)')

def game_day(title):
    m=DATE_RE.search(title)
    if m:
        try: return dt.date(int(m[3]),MONTHS[m[1].lower()],int(m[2])).isoformat()
        except ValueError: return None
    m=NUM_DATE_RE.search(title)
    if m:
        a,b,y=map(int,m.groups())
        # Titoli statunitensi: mese/giorno/anno; se non è inequivocabile, non indovinare.
        if a<=12 and b>12:
            try: return dt.date(y,a,b).isoformat()
            except ValueError: return None
        if b<=12 and a>12:
            try: return dt.date(y,b,a).isoformat()
            except ValueError: return None
    return None

def get_teams(title):
    # Evita di interpretare la data o i testi promozionali come nomi delle squadre.
    matchup=re.split(r'\b(?:FULL GAME HIGHLIGHTS|GAME HIGHLIGHTS|HIGHLIGHTS|NBA SEASON)\b',title,1,flags=re.I)[0]
    found=[]
    for name,aliases in TEAMS.items():
        if any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',matchup,re.I) for a in aliases):found.append(name)
    return found

def get_published_at(video,title,previous=None):
    if previous and previous.get('publishedAt'):return previous['publishedAt']
    if video.get('timestamp'):
        return dt.datetime.fromtimestamp(video['timestamp'],dt.timezone.utc).isoformat()
    stamp=str(video.get('upload_date') or '')
    if re.fullmatch(r'\d{8}',stamp):
        try:return dt.datetime.strptime(stamp,'%Y%m%d').replace(tzinfo=dt.timezone.utc).isoformat()
        except ValueError:pass
    day=game_day(title)
    if day:return (dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc)+dt.timedelta(days=1,hours=8)).isoformat()
    return None

def fetch_playlist(name,url):
    for attempt in range(1,4):
        try:
            cmd=[sys.executable,'-m','yt_dlp','--flat-playlist','--playlist-end','500','--dump-single-json','--no-warnings',url]
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
            if p.returncode:raise RuntimeError(p.stderr[-700:] or 'Errore yt-dlp')
            data=json.loads(p.stdout)
            entries=[x for x in data.get('entries',[]) if isinstance(x,dict) and x.get('id')]
            if not entries:raise ValueError('Playlist vuota')
            print(f'OK: {name}: {len(entries)} video',flush=True)
            return entries
        except (subprocess.TimeoutExpired,RuntimeError,ValueError,json.JSONDecodeError) as e:
            print(f'ATTENZIONE: {name} tentativo {attempt}/3: {e}',flush=True)
            if attempt<3:time.sleep(5*attempt)
    return None

def main():
    old={}
    if OUT.exists():
        data=json.loads(OUT.read_text(encoding='utf-8'))
        old={x['videoId']:x for x in data.get('items',[]) if x.get('videoId')}
    catalog={k:v for k,v in old.items() if v.get('contentType') in ('nightly_recap','game_recap')}
    succeeded=0;added=0
    for playlist,url in PLAYLISTS.items():
        entries=fetch_playlist(playlist,url)
        if entries is None:
            print(f'ATTENZIONE: {playlist} non disponibile; video precedenti conservati.',flush=True)
            continue
        succeeded+=1
        for v in entries:
            video_id=str(v.get('id',''))
            title=v.get('title') or ''
            if not re.fullmatch(r'[\w-]{11}',video_id):continue
            previous=catalog.get(video_id) or old.get(video_id)
            published=get_published_at(v,title,previous)
            if not published:continue
            is_nightly=playlist=='nightly_recap'
            teams=[] if is_nightly else get_teams(title)
            day=game_day(title)
            # Per Ximo ammettiamo solo partite identificate in modo attendibile.
            if playlist=='ximo_game' and (len(teams)!=2 or not day):continue
            if video_id not in catalog:added+=1
            catalog[video_id]={
                'videoId':video_id,'title':title,'publishedAt':published,
                'videoUrl':'https://www.youtube.com/watch?v='+video_id,
                'source':'Ximo Pierto' if playlist=='ximo_game' else 'NBA (YouTube ufficiale)',
                'contentType':'nightly_recap' if is_nightly else 'game_recap',
                'teams':teams,
                **({'gameDate':day} if day else {}),
            }
    if not succeeded:
        print('ATTENZIONE: nessuna playlist disponibile. Catalogo originale conservato.')
        return
    # Arricchisci anche i vecchi video con la data di partita, quando ricavabile.
    for item in catalog.values():
        if item.get('contentType')=='game_recap':
            item.setdefault('gameDate',game_day(item.get('title','')))
            if not item.get('teams'):item['teams']=get_teams(item.get('title',''))
    items=sorted(catalog.values(),key=lambda x:x.get('publishedAt',''),reverse=True)[:2500]
    OUT.write_text(json.dumps({'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'items':items},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'OK: playlist riuscite {succeeded}/3; nuovi {added}; totale {len(items)}',flush=True)

if __name__=='__main__':main()
