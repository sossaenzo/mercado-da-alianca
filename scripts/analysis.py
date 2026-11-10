"""Cálculos do boletim: variação semanal, maiores altas e baixas, índice por categoria."""
import csv
import json
import os
import statistics
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CONFIG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))

# Classe 7 = Trade Goods, classe 0 = Consumables (tabelas do cliente clássico).
CATEGORIES = {
    (7, 5): "Tecido", (7, 6): "Couro", (7, 7): "Metal e pedra", (7, 8): "Carne",
    (7, 9): "Ervas", (7, 10): "Elementais", (7, 12): "Encantamento",
    (7, 1): "Peças de engenharia", (7, 2): "Explosivos", (7, 0): "Materiais diversos",
    (0, 1): "Poções", (0, 2): "Elixires", (0, 3): "Frascos", (0, 5): "Comida e bebida",
    (0, 7): "Ataduras",
}


def load_items():
    path = os.path.join(DATA, "items.json")
    if not os.path.exists(path):
        return {}
    return json.load(open(path, encoding="utf-8")).get("items", {})


def item_info(items, key):
    it = items.get(str(key))
    if not it:
        return {"name": f"Item {key}", "quality": 1, "category": None}
    name, q, c, sc, _sell = (it + [None] * 5)[:5]
    return {"name": name or f"Item {key}", "quality": q or 1, "category": CATEGORIES.get((c, sc))}


def load_history(market):
    """key -> {date: (preço mediano, quantidade mediana)}"""
    path = os.path.join(DATA, "history", f"{market}.csv")
    hist = {}
    if not os.path.exists(path):
        return hist
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            q = int(r["qty_median"]) if r["qty_median"] else None
            hist.setdefault(r["key"], {})[r["date"]] = (int(r["price_median"]), q)
    return hist


def all_dates(hist):
    return sorted({d for days in hist.values() for d in days})


def market_days(market):
    return len(all_dates(load_history(market)))


def pick_market():
    """Mercado do boletim. Se o mercado escolhido ainda não tem 3 dias de dados e
    bulletin_fallback estiver ligado, usa o mercado com mais dias, deixando isso claro na página.

    Devolve (mercado usado, mercado desejado ou None quando não houve troca).
    """
    target = CONFIG.get("bulletin_market", "auto")
    ranked = sorted(CONFIG["markets"], key=lambda m: -market_days(m))
    if target == "auto":
        return ranked[0], None
    if market_days(target) >= 3 or not CONFIG.get("bulletin_fallback"):
        return target, None
    best = ranked[0]
    if market_days(best) == 0:
        return target, None
    return best, target


def window_median(days, start, end):
    vals = [p for d, (p, _q) in days.items() if start <= d <= end]
    qtys = [q for d, (_p, q) in days.items() if start <= d <= end and q is not None]
    if not vals:
        return None, 0, None
    return statistics.median(vals), len(vals), (statistics.median(qtys) if qtys else None)


def weekly_report(market, as_of):
    """as_of = último dia completo (AAAA-MM-DD). Compara os 7 dias até as_of com os 7 anteriores.

    Com menos de 14 dias de histórico, compara os 3 dias mais recentes com os 3 primeiros dias disponíveis.
    """
    cfg = CONFIG["liquidity"]
    hist = load_history(market)
    items = load_items()
    dates = [d for d in all_dates(hist) if d <= as_of]
    if len(dates) < 2:
        return None
    end = date.fromisoformat(as_of)
    cur_start = (end - timedelta(days=6)).isoformat()
    prev_end = (end - timedelta(days=7)).isoformat()
    prev_start = (end - timedelta(days=13)).isoformat()
    full = dates[0] <= prev_start
    min_days = cfg["min_days_per_window"]
    if not full:
        span = min(3, len(dates) // 2)
        prev_start, prev_end = dates[0], dates[span - 1]
        cur_start = dates[-span]
        min_days = max(1, min(min_days, span - 1))
    rows = []
    for key, days in hist.items():
        cur, n_cur, q_cur = window_median(days, cur_start, as_of)
        prev, n_prev, _ = window_median(days, prev_start, prev_end)
        if cur is None or prev is None or prev <= 0:
            continue
        if n_cur < min_days or n_prev < min_days:
            continue
        if (q_cur or 0) < cfg["min_median_qty"] or cur < cfg["min_price_copper"]:
            continue
        info = item_info(items, key)
        spark = [days[d][0] for d in dates[-14:] if d in days]
        rows.append({
            "key": key, **info, "price": cur, "prev": prev, "qty": q_cur,
            "change": cur / prev - 1, "spark": spark,
        })
    tracked = sum(1 for days in hist.values() if any(cur_start <= d <= as_of for d in days))
    # Destaques só entre materiais e consumíveis com nome conhecido: é o que o leitor farma, fabrica e compra.
    focus = [r for r in rows if r["category"] and not r["name"].startswith("Item ")]
    ups = sorted([r for r in focus if r["change"] > 0], key=lambda r: -r["change"])[:10]
    downs = sorted([r for r in focus if r["change"] < 0], key=lambda r: r["change"])[:10]
    cats = {}
    for r in rows:
        if r["category"]:
            cats.setdefault(r["category"], []).append(r["change"])
    categories = sorted(
        [{"name": k, "change": statistics.median(v), "n": len(v)} for k, v in cats.items() if len(v) >= 3],
        key=lambda c: -c["change"],
    )
    return {
        "market": market,
        "market_label": CONFIG["markets"].get(market, market),
        "as_of": as_of,
        "windows": {"cur": (cur_start, as_of), "prev": (prev_start, prev_end), "full": full},
        "tracked": tracked,
        "liquid": len(focus),
        "median_change": statistics.median([r["change"] for r in focus]) if focus else None,
        "ups": ups,
        "downs": downs,
        "categories": categories,
        "first_date": dates[0],
    }


def gold(copper):
    copper = int(round(copper))
    g, rest = divmod(copper, 10000)
    s, c = divmod(rest, 100)
    parts = []
    if g:
        parts.append(f"{g}g")
    if s or g:
        parts.append(f"{s}s")
    parts.append(f"{c}c")
    return " ".join(parts)
