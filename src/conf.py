
from dataclasses import dataclass as dc
import yaml
import json
import os
import locale
import typing

# it would be in the spirit of dreambird have a
# config config file but i'll leave that for
# someone else to do.
META_CONFIG = 'db-conf.yaml'

if not os.path.exists(META_CONFIG):
    with open(META_CONFIG, 'w') as f:
        f.write(
"""
#the local variable database is used for variable persistence 
# over program runs for example for variable with an `Infinite` lifetime.
local var db: db-var.json

#the eternal variable data is used for "immutable" data
# declared by `const const const` which can never change.
eternal var db: 192.168.178.68

#locale for currency symbol for string interpolation.
# default locale (locale.getlocale) is used if not specified.
#locale :

""")


@dc
class Currency:
    symbol : str
    kind   : typing.Literal['prefix', 'infix', 'suffix']

locale_currency_mapper = {
    # TODO: oh so you're a DB programmer?
    #           name every locale.
    'de_DE': Currency("€", 'suffix'),
    'en_US': Currency("$", 'prefix'),
    'en_GB': Currency("£", 'prefix'),
    'ja_JP': Currency("¥", 'prefix'),
    'pt_CV': Currency("$", 'infix'),
}

class Config:
    local_var_db   : str
    eternal_var_db : str
    locale         : str = locale.getlocale()[0]

with open(META_CONFIG) as f:
    for k, v in yaml.safe_load(f).items():
        setattr(Config, k.replace(' ', '_'), v)

#make sure needed files exist
if not os.path.exists(Config.local_var_db):
    with open(Config.local_var_db, 'w') as f:
        json.dump({}, f)



