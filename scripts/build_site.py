"""Gera o site estático em _site/: página inicial, boletins semanais, arquivo, calculadora PvP e sobre.

Os boletins saem toda segunda-feira com dados até o domingo anterior.
A sua opinião da semana entra pelo arquivo opinioes/AAAA-MM-DD.md (data da segunda); sem ele, a seção some.
"""
import html
import json
import os
import shutil
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analysis import CONFIG, ROOT, all_dates, gold, load_history, pick_market, weekly_report  # noqa: E402

OUT = os.path.join(ROOT, "_site")
SRC = os.path.join(ROOT, "site_src")
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
E = html.escape


def br_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {MESES[d.month - 1]} {d.year}"


def pct(x, signed=True):
    if x is None:
        return "–"
    s = f"{x * 100:+.1f}%" if signed else f"{x * 100:.1f}%"
    return s.replace(".", ",")


def page(title, body, depth=0, description=""):
    up = "../" * depth
    name = E(CONFIG["site_name"])
    first, _, rest = CONFIG["site_name"].partition(" ")
    brand = f"{E(first)} <span>{E(rest)}</span>" if rest else name
    links = []
    if CONFIG.get("discord_url"):
        links.append(f'<a href="{E(CONFIG["discord_url"])}">Discord</a>')
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title) if title == CONFIG["site_name"] else E(title) + " · " + name}</title>
<meta name="description" content="{E(description or CONFIG['site_tagline'])}">
<link rel="stylesheet" href="{up}style.css">
</head>
<body>
<header class="site"><div class="wrap">
<a class="brand" href="{up}index.html">{brand}</a>
<nav><a href="{up}boletins/index.html">Boletins</a><a href="{up}calculadora-pvp.html">Calculadora PvP</a><a href="{up}sobre.html">Sobre</a>{''.join(links)}</nav>
</div></header>
<main><div class="wrap">
{body}
</div></main>
<footer><div class="wrap">
Dados de preço: <a href="{E(CONFIG['source_url'])}">{E(CONFIG['source_name'])}</a>, coletados de scans de jogadores no leilão da Aliança (região Américas).
Site independente de fã, sem ligação com a Blizzard Entertainment. World of Warcraft é marca da Blizzard Entertainment.
</div></footer>
</body>
</html>
"""


# ---------- gráficos SVG ----------

def _bars_svg(rows, label_key, title, W, name_end, x0, x1, maxlen):
    row_h, top = 26, 8
    zero = (x0 + x1) / 2
    m = max(abs(r["change"]) for r in rows) or 1
    half = (x1 - x0) / 2 - 52
    H = top + row_h * len(rows) + 12
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{E(title)}">']
    parts.append(f'<line class="axis" x1="{zero}" x2="{zero}" y1="{top - 4}" y2="{H - 6}"/>')
    for i, r in enumerate(rows):
        y = top + i * row_h
        w = max(2, abs(r["change"]) / m * half)
        up = r["change"] >= 0
        x = zero if up else zero - w
        label = r[label_key]
        short = label if len(label) <= maxlen else label[:maxlen - 1] + "…"
        tip = f'{label}: {pct(r["change"])}'
        if "price" in r:
            tip += f' · {gold(r["price"])}'
        parts.append(f'<g class="bar"><title>{E(tip)}</title>')
        parts.append(f'<text class="lbl" x="{name_end}" y="{y + 17}" text-anchor="end">{E(short)}</text>')
        parts.append(f'<rect class="{"bar-up" if up else "bar-down"}" x="{x:.1f}" y="{y + 5}" width="{w:.1f}" height="{row_h - 10}" rx="3"/>')
        vx = zero + w + 5 if up else zero - w - 5
        parts.append(f'<text x="{vx:.1f}" y="{y + 17}" text-anchor="{"start" if up else "end"}">{pct(r["change"])}</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


def diverging_bars(rows, label_key="name", title=""):
    """Barras horizontais em torno do zero: alta em azul à direita, baixa em vermelho à esquerda.

    Duas versões: uma larga para computador e uma compacta para celular (o CSS mostra a certa).
    """
    if not rows:
        return ""
    wide = _bars_svg(rows, label_key, title, 760, 236, 300, 700, 30)
    narrow = _bars_svg(rows, label_key, title, 380, 138, 146, 374, 19)
    return f'<div class="chart"><div class="only-lg">{wide}</div><div class="only-sm">{narrow}</div></div>'


def sparkline(values):
    if len(values) < 2:
        return ""
    W, H, pad = 84, 22, 2
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pts = []
    for i, v in enumerate(values):
        x = pad + i * (W - 2 * pad) / (len(values) - 1)
        y = H - pad - (v - lo) / span * (H - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    return f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" aria-hidden="true"><polyline class="spark" points="{" ".join(pts)}"/></svg>'


def item_table(rows):
    if not rows:
        return '<p class="meta">Ainda sem itens suficientes nesta lista.</p>'
    out = ['<table><thead><tr><th>Item</th><th class="num">Preço mediano</th><th class="num">Variação</th>'
           '<th class="num hide-sm">Oferta típica</th><th class="hide-sm">Últimos dias</th></tr></thead><tbody>']
    for r in rows:
        cls = "up" if r["change"] >= 0 else "down"
        q = r.get("quality") or 1
        out.append(
            f'<tr><td class="q{q}">{E(r["name"])}</td><td class="num">{gold(r["price"])}</td>'
            f'<td class="num {cls}">{pct(r["change"])}</td><td class="num hide-sm">{int(r["qty"] or 0)}</td>'
            f'<td class="hide-sm">{sparkline(r["spark"])}</td></tr>'
        )
    out.append("</tbody></table>")
    return "".join(out)


# ---------- conteúdo ----------

def opinion_html(monday_iso):
    path = os.path.join(ROOT, "opinioes", f"{monday_iso}.md")
    if not os.path.exists(path):
        return ""
    text = open(path, encoding="utf-8").read().strip()
    paras = [p.strip() for p in text.split("\n\n") if p.strip() and not p.startswith("#")]
    body = "".join(f"<p>{E(p)}</p>" for p in paras)
    return f'<h2>O que vale farmar agora</h2><div class="note">{body}</div>'


def report_body(rep, heading, monday_iso=None, number=None):
    w = rep["windows"]
    if w["full"]:
        compare = f'Semana de {br_date(w["cur"][0])} a {br_date(w["cur"][1])} contra os 7 dias anteriores.'
    else:
        compare = (f'Histórico ainda curto: compara {br_date(w["cur"][0])} a {br_date(w["cur"][1])} '
                   f'com {br_date(w["prev"][0])} a {br_date(w["prev"][1])}, os primeiros dias de dados.')
    lead_bits = []
    if rep["ups"]:
        lead_bits.append(f'A maior alta foi {E(rep["ups"][0]["name"])} ({pct(rep["ups"][0]["change"])})')
    if rep["downs"]:
        lead_bits.append(f'a maior queda, {E(rep["downs"][0]["name"])} ({pct(rep["downs"][0]["change"])})')
    lead = ("; ".join(lead_bits) + ".") if lead_bits else "Ainda não há itens com negociação suficiente para comparar."
    num = f"Boletim nº {number} · " if number else ""
    parts = [
        f"<h1>{E(heading)}</h1>",
        f'<p class="meta">{num}Mercado {E(rep["market_label"])} · dados até {br_date(rep["as_of"])}</p>',
        f'<p class="lead">{lead}</p>',
        '<div class="tiles">',
        f'<div class="tile"><div class="v">{rep["tracked"]:,}</div><div class="l">itens vistos no leilão na semana</div></div>'.replace(",", "."),
        f'<div class="tile"><div class="v">{rep["liquid"]:,}</div><div class="l">materiais e consumíveis comparados</div></div>'.replace(",", "."),
        f'<div class="tile"><div class="v">{pct(rep["median_change"])}</div><div class="l">variação mediana desses itens</div></div>',
        "</div>",
        opinion_html(monday_iso) if monday_iso else "",
    ]
    if rep["ups"] or rep["downs"]:
        movers = rep["ups"] + list(reversed(rep["downs"]))
        parts += ["<h2>Maiores altas e quedas</h2>", f'<p class="meta">{compare}</p>',
                  diverging_bars(movers, title="Maiores altas e quedas de preço da semana")]
        parts += ["<h2>Em alta</h2>", item_table(rep["ups"]), "<h2>Em queda</h2>", item_table(rep["downs"])]
    if rep["categories"]:
        parts += ["<h2>Por categoria</h2>",
                  '<p class="meta">Variação mediana dos itens de cada categoria com pelo menos 3 itens negociados.</p>',
                  diverging_bars(rep["categories"], title="Variação mediana por categoria")]
    parts.append(
        '<h2>Como ler</h2><p class="meta">Preço mediano = mediana do menor preço de compra imediata por unidade, '
        'nas coletas feitas a cada 3 horas. Entram só itens vistos em vários dias, com oferta típica de pelo '
        'menos 5 unidades e preço acima de 1 prata. Os dados vêm de scans de jogadores e podem ter lacunas.</p>'
    )
    return "\n".join(p for p in parts if p)


def cta():
    links = []
    if CONFIG.get("newsletter_url"):
        links.append(f'<a class="btn" href="{E(CONFIG["newsletter_url"])}">Receber o boletim por e-mail</a>')
    if CONFIG.get("discord_url"):
        links.append(f'<a class="btn ghost" href="{E(CONFIG["discord_url"])}">Entrar no Discord</a>')
    if CONFIG.get("support_url"):
        links.append(f'<a class="btn ghost" href="{E(CONFIG["support_url"])}">Apoiar o projeto</a>')
    return f'<div class="cta">{"".join(links)}</div>' if links else ""


def today_utc():
    # TODAY=AAAA-MM-DD permite testar como se fosse outro dia.
    t = os.environ.get("TODAY")
    return date.fromisoformat(t) if t else datetime.now(timezone.utc).date()


def mondays_with_data(dates):
    if not dates:
        return []
    first = date.fromisoformat(dates[0])
    today = today_utc()
    d = first + timedelta(days=(7 - first.weekday()) % 7 or 7)
    out = []
    while d <= today:
        as_of = d - timedelta(days=1)
        if (as_of - first).days >= 2:
            out.append(d)
        d += timedelta(days=7)
    return out


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "boletins"))
    for f in os.listdir(SRC):
        if f.endswith(".html"):
            body = open(os.path.join(SRC, f), encoding="utf-8").read()
            title = body.split("<h1>", 1)[1].split("</h1>", 1)[0] if "<h1>" in body else CONFIG["site_name"]
            write(os.path.join(OUT, f), page(html.unescape(title), body))
        else:
            shutil.copy(os.path.join(SRC, f), OUT)

    market, wanted = pick_market()
    dates = all_dates(load_history(market)) if market else []
    today = today_utc().isoformat()
    banner = ""
    if wanted:
        banner = (f'<p class="note">Ainda não há scans do leilão {E(CONFIG["markets"].get(wanted, wanted))} na fonte de dados. '
                  f'Enquanto isso, este boletim acompanha o mercado {E(CONFIG["markets"].get(market, market))}, '
                  'o único com scans suficientes. Os preços de materiais costumam andar juntos entre as facções, '
                  'mas não são iguais.</p>')

    # Boletins semanais
    bulletins = []
    for i, monday in enumerate(mondays_with_data(dates), start=1):
        as_of = (monday - timedelta(days=1)).isoformat()
        rep = weekly_report(market, as_of)
        if not rep:
            continue
        mi = monday.isoformat()
        heading = f"Boletim de {br_date(mi)}"
        write(os.path.join(OUT, "boletins", f"{mi}.html"),
              page(heading, banner + report_body(rep, heading, mi, i) + cta(), depth=1,
                   description=f"Leilão do WoW Forever: altas e quedas até {br_date(as_of)}."))
        bulletins.append((mi, i, rep))

    items = "".join(
        f'<li><a href="{mi}.html">Boletim nº {n} · {br_date(mi)}</a>'
        f'<div class="meta">{rep["liquid"]} itens comparados · variação mediana {pct(rep["median_change"])}</div></li>'
        for mi, n, rep in reversed(bulletins)
    ) or '<li class="meta">O primeiro boletim sai na segunda-feira depois de 3 dias de dados.</li>'
    write(os.path.join(OUT, "boletins", "index.html"),
          page("Boletins", f'<h1>Boletins</h1><p class="lead">Um boletim por semana, toda segunda de manhã.</p><ul class="list">{items}</ul>', depth=1))

    # Página inicial: painel com os dados até o último dia completo
    complete = [d for d in dates if d < today] or dates
    rep = weekly_report(market, complete[-1]) if complete else None
    if rep:
        body = banner + report_body(rep, "O mercado agora" if wanted else "O mercado da Aliança agora")
        if bulletins:
            mi, n, _ = bulletins[-1]
            body = f'<p class="note">Saiu o <a href="boletins/{mi}.html">boletim nº {n}</a>.</p>' + body
    else:
        body = ('<h1>O mercado da Aliança no WoW Forever</h1>'
                '<p class="lead">A coleta de preços começou com o lançamento do jogo. '
                'O painel aparece aqui assim que houver dois dias de dados, e o primeiro boletim sai na segunda seguinte.</p>')
    write(os.path.join(OUT, "index.html"), page(CONFIG["site_name"], body + cta()))
    print(f"Site gerado em {OUT}: mercado {market}, {len(dates)} dias de dados, {len(bulletins)} boletins")


if __name__ == "__main__":
    main()
