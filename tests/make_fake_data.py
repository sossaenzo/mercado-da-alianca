"""Gera dados simulados para testar a análise e o site sem depender da API.

Uso: python tests/make_fake_data.py <pasta-do-projeto-de-teste> [dias]
Nunca rode na pasta real do projeto: sobrescreve data/.
"""
import csv
import gzip
import json
import os
import random
import sys
from datetime import date, timedelta

root = sys.argv[1]
n_days = int(sys.argv[2]) if len(sys.argv) > 2 else 13
random.seed(7)
items = {
    "2589": ["Linen Cloth", 1, 7, 5, 13], "2592": ["Wool Cloth", 1, 7, 5, 33], "4306": ["Silk Cloth", 1, 7, 5, 150],
    "4338": ["Mageweave Cloth", 1, 7, 5, 250], "14047": ["Runecloth", 1, 7, 5, 400],
    "2318": ["Light Leather", 1, 7, 6, 15], "2319": ["Medium Leather", 1, 7, 6, 50], "4234": ["Heavy Leather", 1, 7, 6, 150],
    "4304": ["Thick Leather", 1, 7, 6, 300], "8170": ["Rugged Leather", 1, 7, 6, 375],
    "2770": ["Copper Ore", 1, 7, 7, 5], "2771": ["Tin Ore", 1, 7, 7, 25], "2772": ["Iron Ore", 1, 7, 7, 150],
    "3858": ["Mithril Ore", 1, 7, 7, 250], "10620": ["Thorium Ore", 1, 7, 7, 250],
    "765": ["Silverleaf", 1, 7, 9, 10], "2447": ["Peacebloom", 1, 7, 9, 10], "785": ["Mageroyal", 1, 7, 9, 15],
    "2452": ["Swiftthistle", 1, 7, 9, 15], "3820": ["Stranglekelp", 1, 7, 9, 25], "3356": ["Kingsblood", 1, 7, 9, 30],
    "8831": ["Purple Lotus", 1, 7, 9, 75], "13463": ["Dreamfoil", 1, 7, 9, 200],
    "10940": ["Strange Dust", 1, 7, 12, 0], "10938": ["Lesser Magic Essence", 2, 7, 12, 0], "11083": ["Soul Dust", 1, 7, 12, 0],
    "7067": ["Elemental Earth", 1, 7, 10, 400], "7068": ["Elemental Fire", 1, 7, 10, 400], "7077": ["Heart of Fire", 1, 7, 10, 400],
    "858": ["Lesser Healing Potion", 1, 0, 1, 20], "929": ["Healing Potion", 1, 0, 1, 75], "1710": ["Greater Healing Potion", 1, 0, 1, 115],
    "3928": ["Superior Healing Potion", 1, 0, 1, 250], "13444": ["Major Mana Potion", 1, 0, 1, 1000],
    "3390": ["Elixir of Lesser Agility", 1, 0, 2, 50], "8949": ["Elixir of Agility", 1, 0, 2, 100], "9187": ["Elixir of Greater Agility", 1, 0, 2, 200],
    "3825": ["Elixir of Fortitude", 1, 0, 2, 110], "13452": ["Elixir of the Mongoose", 1, 0, 2, 1000],
    "1251": ["Linen Bandage", 1, 0, 7, 10], "14529": ["Runecloth Bandage", 1, 0, 7, 400],
    "4599": ["Cured Ham Steak", 1, 0, 5, 100], "13931": ["Nightfin Soup", 1, 0, 5, 300],
    "12359": ["Thorium Bar", 1, 7, 7, 600], "2840": ["Copper Bar", 1, 7, 7, 10],
    "7076": ["Essence of Earth", 2, 7, 10, 2000], "7078": ["Essence of Fire", 2, 7, 10, 2000],
    "12037": ["Mystery Meat", 1, 7, 8, 87],
}
items["3667"] = ["Tender Crocolisk Meat", 1, 7, 8, 25]
os.makedirs(os.path.join(root, "data"), exist_ok=True)
json.dump({"build": "fake", "items": items}, open(os.path.join(root, "data", "items.json"), "w"))
start = date(2026, 11, 5)
markets = {"forever.normal.alliance.us": 1.0, "forever.pvp.alliance.us": 0.7, "forever.rp.alliance.us": 0.2}
for m, depth in markets.items():
    price = {k: max(20, v[4] * random.uniform(2, 6) * 10) for k, v in items.items()}
    trend = {k: random.uniform(-0.06, 0.08) for k in items}
    for d in range(n_days):
        day = start + timedelta(days=d)
        path = os.path.join(root, "data", "obs", m, f"{day.isoformat()}.csv.gz")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        rows = []
        for h in range(0, 24, 3):
            run = f"{day.isoformat()}T{h:02d}:05Z#{d * 100 + h}"
            for k in items:
                if random.random() > depth:
                    continue
                p = price[k] * random.uniform(0.92, 1.08)
                rows.append({"run_at": run, "key": k, "price": int(p), "qty": random.randint(1, 120), "seen_at": ""})
        for k in price:
            price[k] *= 1 + trend[k] + random.uniform(-0.03, 0.03)
        with gzip.open(path, "wt", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["run_at", "key", "price", "qty", "seen_at"])
            w.writeheader()
            w.writerows(rows)
print("dados simulados prontos")
