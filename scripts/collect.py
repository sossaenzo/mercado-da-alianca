"""Coleta os preços do leilão da Aliança no WoW Forever.

Roda a cada 3 horas (GitHub Actions). Para cada mercado da Aliança:
  1. baixa o snapshot horário público do auctionhouse.fyi;
  2. acrescenta as linhas ao arquivo de observações do dia (data/obs/<mercado>/<AAAA-MM-DD>.csv.gz);
  3. recalcula o histórico diário (data/history/<mercado>.csv).
Uma vez por semana atualiza o catálogo de itens (data/items.json).

Só usa a biblioteca padrão do Python, sem instalar nada.
"""
import csv
import gzip
import io
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
DATA = os.path.join(ROOT, "data")
VARIANT_BASE = 2147483648


def get_json(path):
    url = CONFIG["api_base"] + path
    for attempt in range(5):
        req = urllib.request.Request(url, headers={
            "User-Agent": CONFIG["user_agent"],
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                wait = int(e.headers.get("Retry-After") or 0) or (2 ** attempt) * 5
                print(f"  {e.code} em {path}; esperando {wait}s")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            print(f"  erro de rede em {path}: {e}; tentando de novo")
            time.sleep((2 ** attempt) * 5)
    raise RuntimeError(f"Falhou depois de 5 tentativas: {url}")


def refresh_items(force=False):
    """Catálogo compacto: chave -> [nome, qualidade, classe, subclasse, preço de venda ao NPC]."""
    path = os.path.join(DATA, "items.json")
    if not force and os.path.exists(path) and time.time() - os.path.getmtime(path) < 7 * 86400:
        return
    print("Atualizando catálogo de itens")
    j = get_json("/items")
    out = {}
    for k, it in (j.get("items") or {}).items():
        out[k] = [it.get("n"), it.get("q"), it.get("c"), it.get("sc"), it.get("sell")]
    for k, v in (j.get("variants") or {}).items():
        base = str(int(k) % VARIANT_BASE)
        b = out.get(base) or [None, None, None, None, None]
        out[k] = [v.get("n"), v.get("q"), b[2], b[3], b[4]]
    os.makedirs(DATA, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"build": j.get("build"), "items": out}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  {len(out)} itens no catálogo")


OBS_FIELDS = ["run_at", "key", "price", "qty", "seen_at"]


def read_obs(path):
    if not os.path.exists(path):
        return []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_obs(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OBS_FIELDS)
        w.writeheader()
        w.writerows(rows)


def collect_market(market, run_at):
    snap = get_json(f"/ah/{market}/snapshot")
    rows = snap.get("rows") or []
    if not rows:
        print(f"  {market}: snapshot vazio (sem scans ainda)")
        return 0
    day = run_at[:10]
    path = os.path.join(DATA, "obs", market, f"{day}.csv.gz")
    existing = read_obs(path)
    snap_at = snap.get("at")
    # O snapshot só muda de hora em hora: não grava duas vezes o mesmo snapshot.
    if existing and any(r["run_at"].endswith(f"#{snap_at}") for r in existing):
        print(f"  {market}: snapshot {snap_at} já gravado")
        return 0
    tag = f"{run_at}#{snap_at}"
    new = []
    for r in rows:
        key, price, qty, seen = (list(r) + [None] * 4)[:4]
        if price is None:
            continue
        new.append({"run_at": tag, "key": key, "price": price, "qty": "" if qty is None else qty, "seen_at": seen or ""})
    write_obs(path, existing + new)
    print(f"  {market}: {len(new)} preços gravados em {day}")
    return len(new)


def rebuild_history(market):
    """Uma linha por dia e item: mínimo, mediana e quantidade mediana entre as coletas do dia."""
    folder = os.path.join(DATA, "obs", market)
    if not os.path.isdir(folder):
        return
    out = []
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".csv.gz"):
            continue
        day = fname[:10]
        by_key = {}
        for r in read_obs(os.path.join(folder, fname)):
            d = by_key.setdefault(r["key"], {"p": [], "q": [], "runs": set()})
            d["p"].append(int(float(r["price"])))
            if r["qty"] not in ("", None):
                d["q"].append(int(float(r["qty"])))
            d["runs"].add(r["run_at"])
        for key, d in by_key.items():
            out.append({
                "date": day,
                "key": key,
                "price_min": min(d["p"]),
                "price_median": int(statistics.median(d["p"])),
                "qty_median": int(statistics.median(d["q"])) if d["q"] else "",
                "n_obs": len(d["runs"]),
            })
    os.makedirs(os.path.join(DATA, "history"), exist_ok=True)
    with open(os.path.join(DATA, "history", f"{market}.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "key", "price_min", "price_median", "qty_median", "n_obs"])
        w.writeheader()
        w.writerows(out)


def main():
    if "--rebuild-only" in sys.argv:
        for market in CONFIG["markets"]:
            rebuild_history(market)
        print("Histórico recalculado")
        return
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    print(f"Coleta {run_at}")
    refresh_items(force="--items" in sys.argv)
    total = 0
    for market in CONFIG["markets"]:
        try:
            total += collect_market(market, run_at)
        except Exception as e:  # um mercado com problema não derruba os outros
            print(f"  {market}: ERRO {e}")
        rebuild_history(market)
    print(f"Total de preços gravados nesta coleta: {total}")


if __name__ == "__main__":
    main()
