
import yaml
import json
import os

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

""")


class Config:
    local_var_db: str



with open(META_CONFIG) as f:
    for k, v in yaml.safe_load(f).items():
        setattr(Config, k.replace(' ', '_'), v)


#make sure needed files exist
if not os.path.exists(Config.local_var_db):
    with open(Config.local_var_db, 'w') as f:
        json.dump({}, f)



