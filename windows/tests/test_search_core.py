from __future__ import annotations
import importlib.util, sqlite3, sys, types, unicodedata, re
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

# Minimal stubs matching Just InCard's normalization/set parsing contracts.
# IMPORTANT: keep the real package directory on __path__.  Older versions used
# an empty package path here, which poisoned sys.modules during pytest
# collection and made later tests fail with
# ``ModuleNotFoundError: justincard.v108_core``.
ROOT = Path(__file__).resolve().parents[1]
pkg = types.ModuleType('justincard')
pkg.__path__ = [str(ROOT / 'justincard')]
sys.modules['justincard'] = pkg
utils = types.ModuleType('justincard.utils')
def normalize_text(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii','ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()
def set_search_parts(value):
    raw=str(value or '').upper().replace('_','-').strip()
    m=re.search(r'(?:^|-)(DE|EN|FR|IT|PT|ES|SP|JP|JA|KR|KO|CN|SC|TC|NL|PL|RU|TR)(?=-?\d|$)',raw)
    lang={'DE':'de','EN':'en','FR':'fr','IT':'it','PT':'pt','ES':'es','SP':'es','JP':'ja','JA':'ja','KR':'ko','KO':'ko','CN':'zh','SC':'zh','TC':'zh-tw','NL':'nl','PL':'pl','RU':'ru','TR':'tr'}.get(m.group(1),'') if m else ''
    prefix=raw.split('-')[0] if raw else ''
    num=''.join(re.findall(r'\d+',raw)[-1:])
    return prefix,lang,num
utils.normalize_text=normalize_text; utils.set_search_parts=set_search_parts; sys.modules['justincard.utils']=utils

spec=importlib.util.spec_from_file_location('justincard.search_core', str(ROOT / 'justincard' / 'search_core.py'))
mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod)

@dataclass
class F:
    quick_text:str=''; name:str=''; passcode:str=''; effect:str=''; archetype:str=''; set_query:str=''; rarity:str=''
    language:str='all'; category:str='all'; card_type:str='all'; race:str='all'; attribute:str='all'; format_name:str='all'; ban_status:str='all'
    atk_min:int|None=None; atk_max:int|None=None; def_min:int|None=None; def_max:int|None=None; level_min:int|None=None; level_max:int|None=None
    scale_min:int|None=None; scale_max:int|None=None; link_min:int|None=None; link_max:int|None=None; link_markers:tuple[str,...]=()
    pendulum_only:bool=False; alternative_artwork_only:bool=False; owned_state:str='all'; condition:str='all'; min_quantity:int|None=None
    price_min:float|None=None; price_max:float|None=None; sort_by:str='name_asc'; limit:int=250

class DB:
    def __init__(self):
        self.c=sqlite3.connect(':memory:'); self.c.row_factory=sqlite3.Row
        self.c.executescript('''
        CREATE TABLE cards(card_key TEXT PRIMARY KEY,card_id INTEGER,language TEXT,name TEXT,name_norm TEXT,effect TEXT,effect_norm TEXT,card_type TEXT,frame_type TEXT,race TEXT,attribute TEXT,archetype TEXT,archetype_norm TEXT,atk INTEGER,def INTEGER,level INTEGER,scale INTEGER,linkval INTEGER,linkmarkers TEXT,set_blob TEXT,set_codes TEXT,set_signatures TEXT,rarity_blob TEXT,formats TEXT,ban_tcg TEXT,ban_ocg TEXT,ban_goat TEXT,price_min REAL,artwork_count INTEGER,image_url TEXT,image_url_small TEXT,raw_json TEXT,updated_at REAL);
        CREATE TABLE collection(collection_key TEXT PRIMARY KEY,card_key TEXT,card_id INTEGER,print_code TEXT,set_name TEXT,rarity TEXT,artwork_url TEXT,language TEXT,quantity INTEGER,condition TEXT,purchase_price REAL,note TEXT,wishlist INTEGER,trade INTEGER,card_json TEXT,created_at REAL,updated_at REAL);
        ''')
        cards=[
          ('be-de',89631139,'de','Blauäugiger w. Drache','blauaugiger w drache','Legendärer Drache','legendarer drache','Normal Monster','normal','Dragon','LIGHT','Blue-Eyes','blue eyes',3000,2500,8,None,None,'','|Legend of Blue Eyes White Dragon|LOB-DE001|','|LOB-DE001|','|LOB-001|','|Ultra Rare|','|TCG|','', '', '',12.5,2,'','','{}',100),
          ('be-en',89631139,'en','Blue-Eyes White Dragon','blue eyes white dragon','Legendary dragon','legendary dragon','Normal Monster','normal','Dragon','LIGHT','Blue-Eyes','blue eyes',3000,2500,8,None,None,'','|Legend of Blue Eyes White Dragon|LOB-EN001|','|LOB-EN001|','|LOB-001|','|Ultra Rare|','|TCG|','', '', '',11.0,2,'','','{}',101),
          ('dm-de',46986414,'de','Dunkler Magier','dunkler magier','Der ultimative Zauberer','der ultimative zauberer','Normal Monster','normal','Spellcaster','DARK','Dark Magician','dark magician',2500,2100,7,None,None,'','|Starter Deck Yugi|SDY-DE006|','|SDY-DE006|','|SDY-006|','|Ultra Rare|','|TCG|','Limited','','',8.0,1,'','','{}',90),
          ('link-en',1001,'en','Link Test','link test','Link effect','link effect','Link Effect Monster','link','Cyberse','DARK','Test','test',1800,None,None,None,2,'|Bottom-Left|Bottom-Right|','|Code Set|COTS-EN001|','|COTS-EN001|','|COTS-001|','|Secret Rare|','|TCG|','Forbidden','','',3.0,1,'','','{}',110),
          ('pend-de',1002,'de','Pendel Test','pendel test','Pendulum effect','pendulum effect','Pendulum Effect Monster','effect_pendulum','Spellcaster','FIRE','Pendulum','pendulum',1500,1500,4,8,None,'','|Pendulum Set|PEND-DE002|','|PEND-DE002|','|PEND-002|','|Super Rare|','|OCG|','Semi-Limited','','',2.0,1,'','','{}',120),
          ('spell-de',1003,'de','Zauber Test','zauber test','Ziehe eine Karte','ziehe eine karte','Spell Card','spell','Normal','','','',None,None,None,None,None,'','|Magic Set|MAG-DE003|','|MAG-DE003|','|MAG-003|','|Common|','|TCG|','', '', '',0.2,1,'','','{}',130),
        ]
        self.c.executemany('INSERT INTO cards VALUES('+','.join('?'*33)+')', cards)
        coll=[
          ('c1','be-de',89631139,'LOB-DE001','Legend','Ultra Rare','','de',2,'Near Mint',10.0,'',1,1,'{}',1,1),
          ('c2','dm-de',46986414,'SDY-DE006','Yugi','Ultra Rare','','de',1,'Played',5.0,'',0,0,'{}',1,1),
        ]
        self.c.executemany('INSERT INTO collection VALUES('+','.join('?'*17)+')',coll); self.c.commit()
    @contextmanager
    def connect(self):
        yield self.c
    def installed_languages(self):
        return [dict(r) for r in self.c.execute('SELECT language,COUNT(*) total,MAX(updated_at) updated FROM cards GROUP BY language')]
    @staticmethod
    def _decode_card_row(row): return dict(row)
    @classmethod
    def _set_match_any_language_sql(cls,value,alias='c'):
        raw=str(value or '').strip().upper(); sig=re.sub(r'-(DE|EN|FR|IT|PT|ES|SP|JP|JA|KR|KO|CN|SC|TC|NL|PL|RU|TR)(?=\d)', '-', raw)
        prefix=raw.split('-')[0]
        # Mimic cross-language print matching: exact raw, language-neutral signature, or set prefix/name.
        q=f'''EXISTS(SELECT 1 FROM cards sl WHERE sl.card_id={alias}.card_id AND (
          UPPER(sl.set_codes) LIKE ? OR UPPER(sl.set_signatures) LIKE ? OR UPPER(sl.set_codes) LIKE ? OR UPPER(sl.set_blob) LIKE ?))'''
        return q,[f'%{raw}%',f'%{sig}%',f'%{prefix}%',f'%{raw}%']

def names(rows): return {r['card_key'] for r in rows}
def check(label, filters, expected):
    rows,note=mod.search_cards(db,filters)
    got=names(rows)
    assert got==set(expected), f'{label}: expected {expected}, got {got}, note={note}'
    print('OK',label,sorted(got),note)

db=DB()
# Every major filter family individually.
checks=[
 ('name',F(name='magier'),{'dm-de'}),
 ('passcode exact',F(passcode='89631139'),{'be-de','be-en'}),
 ('passcode partial',F(passcode='86414'),{'dm-de'}),
 ('effect',F(effect='zieh'),{'spell-de'}),
 ('archetype',F(archetype='blue eyes'),{'be-de','be-en'}),
 ('set lower EN auto language',F(set_query='lob-en001',language='de'),{'be-en'}),
 ('set DE uses English reference row',F(set_query='LOB-DE001'),{'be-en'}),
 ('rarity',F(rarity='secret'),{'link-en'}),
 ('language de',F(language='de'),{'be-de','dm-de','pend-de','spell-de'}),
 ('category monster',F(category='monster'),{'be-de','be-en','dm-de','link-en','pend-de'}),
 ('category spell',F(category='spell'),{'spell-de'}),
 ('category extra',F(category='extra'),{'link-en'}),
 ('category pendulum',F(category='pendulum'),{'pend-de'}),
 ('card type',F(card_type='Normal Monster'),{'be-de','be-en','dm-de'}),
 ('race',F(race='Dragon'),{'be-de','be-en'}),
 ('attribute',F(attribute='FIRE'),{'pend-de'}),
 ('format',F(format_name='OCG'),{'pend-de'}),
 ('ban allowed',F(ban_status='allowed'),{'be-de','be-en','spell-de'}),
 ('ban forbidden',F(ban_status='Forbidden'),{'link-en'}),
 ('atk min',F(atk_min=2900),{'be-de','be-en'}),
 ('atk max',F(atk_max=1600),{'pend-de'}),
 ('def range',F(def_min=2200,def_max=2600),{'be-de','be-en'}),
 ('level',F(level_min=7,level_max=7),{'dm-de'}),
 ('scale',F(scale_min=8,scale_max=8),{'pend-de'}),
 ('link',F(link_min=2,link_max=2),{'link-en'}),
 ('link marker',F(link_markers=('Bottom-Left',)),{'link-en'}),
 ('pend only',F(pendulum_only=True),{'pend-de'}),
 ('alt art',F(alternative_artwork_only=True),{'be-de','be-en'}),
 ('price range',F(price_min=7,price_max=9),{'dm-de'}),
 ('owned',F(owned_state='owned'),{'be-de','be-en','dm-de'}),
 ('missing',F(owned_state='missing'),{'link-en','pend-de','spell-de'}),
 ('condition',F(condition='Played'),{'dm-de'}),
 ('min qty',F(min_quantity=2),{'be-de','be-en'}),
 ('combined AND',F(category='monster',attribute='LIGHT',atk_min=3000,rarity='Ultra'),{'be-de','be-en'}),
 ('quick passcode',F(quick_text='89631139'),{'be-de','be-en'}),
 ('quick set language',F(quick_text='LOB-EN001',language='de'),{'be-en'}),
]
for item in checks: check(*item)

assert mod.infer_set_language('blmr-de024')=='de'
assert mod.infer_set_language('LOB-EN001')=='en'
assert mod.infer_set_language('abc-tc012')=='zh-tw'
print('OK language inference')

class LangDB:
    def installed_languages(self): return [{'language':'de'},{'language':'en'}]
langdb=LangDB()
lang,note=mod.effective_language(langdb,F(set_query='ABC-JP001',language='de'))
assert lang=='en' and 'JA' in note and 'EN' in note
lang,note=mod.effective_language(langdb,F(language='fr'))
assert lang=='all' and 'FR' in note
print('OK unavailable language fallback')
print('ALL SEARCH CORE TESTS PASSED:', len(checks)+5)

# Regression: current localized sets can be stored on a translated card row
# with a different language marker in card_sets. Since v1.2.6, CORI-DE must
# deliberately resolve the English reference row; DE is restored only when the
# selected print is written to the collection.
cori_rows = [
  ('cori-de',20010005,'de','CORI Deutsch','cori deutsch','Test','test','Effect Monster','effect','Fiend','DARK','Chaos','chaos',1000,1000,4,None,None,'','|Chaos Origins|CORI-EN005|','|CORI-EN005|','|CORI:005|','|Super Rare|','|TCG|','', '', '',1.0,1,'','','{}',200),
  ('cori-en',20010005,'en','CORI English','cori english','Test','test','Effect Monster','effect','Fiend','DARK','Chaos','chaos',1000,1000,4,None,None,'','|Chaos Origins|CORI-EN005|','|CORI-EN005|','|CORI:005|','|Super Rare|','|TCG|','', '', '',1.0,1,'','','{}',200),
]
db.c.executemany('INSERT INTO cards VALUES('+','.join('?'*33)+')', cori_rows)
db.c.commit()
check('CORI-DE prefix uses English row',F(set_query='CORI-DE',language='all'),{'cori-en'})
check('cori-de lowercase prefix',F(set_query='cori-de',language='en'),{'cori-en'})
check('CORI-DE full code via EN reference',F(set_query='CORI-DE005',language='all'),{'cori-en'})
check('CORI-EN prefix uses English row',F(set_query='CORI-EN',language='de'),{'cori-en'})
check('quick CORI-DE prefix',F(quick_text='CORI-DE',language='all'),{'cori-en'})
assert mod._set_query_parts('CORI-DE')[:3] == ('CORI-DE','CORI','de')
assert mod._set_query_parts('CORI-DE005') == ('CORI-DE005','CORI','de','005')
assert mod.english_set_query('BLMR-DE001') == 'BLMR-EN001'
assert mod.english_set_query('BLMR-FR001') == 'BLMR-EN001'
assert mod.english_set_query('CORI-DE') == 'CORI-EN'
assert mod.requested_collection_language('BLMR-DE001') == 'de'
card, print_item = mod.localized_collection_print(
    {'id': 1, 'name': 'Test', '_language': 'en'},
    {'set_code': 'BLMR-EN001', 'set_name': 'Battles', 'set_rarity': 'Ultra Rare'},
    'BLMR-DE001',
)
assert card['_language'] == 'de' and card['_reference_language'] == 'en'
assert print_item['set_code'] == 'BLMR-DE001'
assert print_item['_language'] == 'de'
assert print_item['_reference_set_code'] == 'BLMR-EN001'
print('OK localized set-prefix regression: CORI-DE / CORI-DE005')

# Pytest collection anchor: all detailed regression assertions above execute
# during module import.  This named test makes the suite return a normal
# success code instead of pytest's "no tests collected" exit code 5.
def test_search_core_regression_suite_collected():
    assert True
