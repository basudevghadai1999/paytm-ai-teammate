"""Container start: load the demo seed only when tm_merchants is empty, so redeploys keep existing tickets."""
from app import seed
from app.core.db import db

with db() as d:
    if d.one("select count(*) as n from tm_merchants")["n"] == 0:
        seed.reset(d)
        print("seeded demo data")
