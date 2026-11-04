# Mercado da Aliança

Boletim semanal em PT-BR sobre o leilão da Aliança no WoW Forever, mais uma calculadora de rank PvP.

## Como funciona

1. A cada 3 horas o GitHub roda `scripts/collect.py`, que baixa o snapshot público de preços do
   [auctionhouse.fyi](https://auctionhouse.fyi/) para os três mercados da Aliança (Normal, PvP, RP)
   e guarda tudo em `data/`.
2. Em seguida roda `scripts/build_site.py`, que calcula as variações e gera o site em `_site/`.
3. O site é publicado no GitHub Pages. Custo zero.

Toda segunda-feira aparece um boletim novo, com dados até domingo. O boletim usa o mercado da Aliança
com mais itens negociados (troque em `config.json`, campo `bulletin_market`).

## Pastas

| Pasta ou arquivo | O que tem |
| --- | --- |
| `config.json` | Nome do site, mercados, filtros de liquidez, links de Discord, e-mail e apoio |
| `scripts/collect.py` | Coletor de preços |
| `scripts/analysis.py` | Cálculos do boletim |
| `scripts/build_site.py` | Gerador das páginas |
| `site_src/` | Calculadora PvP, página Sobre e o visual (CSS) |
| `opinioes/` | Sua opinião da semana, um arquivo por boletim |
| `data/obs/` | Todas as coletas, um arquivo por dia e mercado |
| `data/history/` | Histórico diário por item (CSV que abre no Excel) |
| `tests/make_fake_data.py` | Dados simulados para testar sem a API |

## Colocar no ar (uma vez)

1. Crie uma conta em github.com, se ainda não tiver.
2. Crie um repositório público chamado `mercado-da-alianca`.
3. Envie todos os arquivos deste projeto para ele.
4. No repositório: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
5. Em **Actions**, abra "Coletar preços e publicar o site" e clique **Run workflow**.
6. Em alguns minutos o site fica em `https://SEU-USUARIO.github.io/mercado-da-alianca/`.

## Rotina semanal

- Segunda de manhã: abra o boletim novo no site e confira 2 ou 3 preços no jogo.
- Se quiser, escreva sua opinião em `opinioes/AAAA-MM-DD.md` direto pelo site do GitHub
  (botão **Add file → Create new file**). O site se atualiza sozinho.

## Testar no computador

```
python tests/make_fake_data.py pasta-de-teste 13
```
Depois copie `config.json`, `scripts` e `site_src` para `pasta-de-teste`, entre nela e rode
`python scripts/collect.py --rebuild-only` e `TODAY=2026-11-17 python scripts/build_site.py`.

## Dados e crédito

Os preços vêm de scans de jogadores reunidos pelo auctionhouse.fyi. O site sempre dá o crédito e o link
da fonte. Antes de ligar anúncios, confirme com o operador do auctionhouse.fyi que o uso é permitido.
