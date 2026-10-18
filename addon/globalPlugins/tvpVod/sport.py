"""TVP Sport adapter for the native accessible catalogue."""
from .catalog import Folder,Material,CatalogError
from . import sport_api

def browse(folder):
    if folder.resource=='root':
        return [Folder(1,'Trwające teraz','SPORT','now'),Folder(2,'Nadchodzące transmisje','SPORT','upcoming'),
            Material(51696827,'TVP Sport — kanał na żywo','Stały kanał telewizyjny TVP Sport. Osobne wydarzenia internetowe znajdziesz w folderach transmisji.',
                'https://sport.tvp.pl/51696827/transmisja','LIVE',False)],False
    try:events=sport_api.schedule()
    except Exception as error:raise CatalogError('Nie udało się pobrać transmisji TVP Sport: '+str(error)) from error
    events=[item for item in events if item['active']==(folder.resource=='now')]
    materials=[Material(item['id'],('Na żywo — ' if item['active'] else 'Zaplanowane — ')+sport_api.local_time(item['start'])+' — '+item['title'],
        item['discipline']+'. Początek: '+sport_api.local_time(item['start'])+'. Koniec planowany: '+sport_api.local_time(item['end'])+'. F5 odświeża listę. Dostępność potwierdza serwer przy odtwarzaniu.',
        item['url'],'LIVE',False,start=item['start'],end=item['end']) for item in events]
    return materials,False
