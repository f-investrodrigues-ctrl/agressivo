# agressivo

Bot sistemático alinhado ao [plano mestre](docs/PLANO-MAESTRO-BOT-AGRESSIVO.md): ingestão de dados, qualidade, backtest com custos, política de risco (Kelly fracionário) e estratégia Core v1 (compressão + breakout).

## Ambiente

Requer Python 3.11+.

No **PowerShell 5.x** (omissão no Windows), encadeie com `;` em vez de `&&` (ex.: `cd c:\agressivo; pip install -e ".[dev]"`). Também podes usar `python -m agressivo …` com o pacote instalado.

```powershell
cd c:\agressivo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

## CLI

```powershell
agressivo fetch-ohlcv --symbol BTC/USDT --timeframe 1h --limit 500

# Preflight local (config/paths/credenciais presentes)

agressivo doctor

# Qualidade OHLCV sem abortar por veto (data health)

agressivo ohlcv-qc --symbol BTC/USDT --timeframe 1h --bars 800

# Kelly fraccionado (modelo binário aproximado)

agressivo kelly-calc --win-rate 0.45 --win-mean 120 --lose-mean 80 --fractional 0.5

# Backtest único (entrada por omissão = open da barra seguinte ao sinal)

agressivo backtest-breakout --symbol BTC/USDT --timeframe 1h --bars 1500 --fill-timing next-bar

# Regime (MA de tendência + close>MA): `.env` (`AGRESSIVO_CORE_*`) ou `--trend-ma` / `--no-trend-filter`

# Custos: fee/slip em bps opcionais + slippage proporcional ao ATR (frac)

agressivo backtest-breakout --symbol ETH/USDT --fee-bps 5 --slip-bps 3 --slip-atr-frac 0.03

# Opcional — calendário JSON (mesmas regras que Paper): só corta novas entradas

agressivo backtest-breakout --symbol BTC/USDT --satellite-catalog data/satellite/catalog.example.json

# Walk-forward: um backtest causal completo; métricas apenas em trades com entrada na janela de teste

agressivo wf --symbol BTC/USDT --train 900 --test 300 --bars 2200

agressivo wf --symbol BTC/USDT --train 900 --test 300 --bars 2200 --export-json data/reports/wf_last.json

agressivo wf --symbol BTC/USDT --train 900 --test 300 --bars 2200 --export-json data/reports/wf.json --export-include-trades

agressivo backtest-breakout --symbol BTC/USDT --bars 800 --export-json data/reports/bt_last.json

agressivo backtest-breakout --symbol BTC/USDT --bars 800 --export-json data/reports/bt.json --export-include-trades

# Satélite (calendário JSON — veto_core bloqueia **novos** longs no Paper)

agressivo satellite-scan --catalog data/satellite/catalog.example.json --within-hours 200

agressivo paper-once --symbol BTC/USDT --satellite-catalog data/satellite/catalog.example.json

# Satelite: saidas com --satellite-catalog mostram satellite_audit (sha256_full) para registos

# Paper (sem API keys trade): estado em `AGRESSIVO_PAPER_STATE_PATH`

agressivo paper-reset

agressivo paper-once --symbol BTC/USDT --bars 400

# Ciclo (--loops 0 = infinito; Ctrl+C para parar)

agressivo paper-run --symbol BTC/USDT --bars 400 --sleep 120 --loops 5

# Guardrail opcional: abortar após N falhas consecutivas de polling (0 = desativa)

agressivo paper-run --symbol BTC/USDT --bars 400 --sleep 120 --max-consecutive-failures 3

# Opcional: salvar resumo operacional do loop em JSON

agressivo paper-run --symbol BTC/USDT --bars 400 --run-summary-json data/reports/paper_run_summary.json

agressivo paper-close --symbol BTC/USDT

agressivo reconcile --local-qty 0 --exchange-qty 0

# Spot balance (opcional `.env`: AGRESSIVO_EXCHANGE_API_KEY / _SECRET)

agressivo exchange-balance --symbol BTC/USDT

agressivo exchange-open-orders --symbol BTC/USDT --limit 20

agressivo exchange-order-fetch --symbol BTC/USDT --id YOUR_ORDER_ID

agressivo exchange-my-trades --symbol BTC/USDT --limit 30

agressivo paper-vs-exchange --symbol BTC/USDT

agressivo paper-vs-exchange --symbol BTC/USDT --use-free

# Espelho paper → mesmo JSONL que ordens (`--mirror-ledger` opcional)

agressivo paper-once --symbol BTC/USDT --mirror-ledger

# Ordens ccxt (por omissão só regista dry-run no ledger — não envia à exchange)

agressivo order-send --symbol BTC/USDT --side buy --qty 0.001 --kind market

# Últimas linhas JSON do ledger (`data/order_ledger.jsonl` ou AGRESSIVO_ORDER_LEDGER_PATH)

agressivo order-ledger-tail --last 15

agressivo version
```

**Execução real:** só com `AGRESSIVO_EXECUTE_ORDERS=true` no `.env` **e** flag `--execute` em `order-send`, mais API keys válidas. Sem isto continuam apenas entradas de *dry-run* / `paper_mirror` no ledger. Erros de sizing, outages e regras da exchange são responsabilidade de quem opera.

Dados públicos não exigem API keys. Leituras autenticadas e envio de ordens exigem chaves com permissões mínimas e revisão de risco antes de usar capital real.

## Testes

```powershell
pytest
ruff check src tests
```

## Aviso

Software educacional / pesquisa. Não é recomendação financeira. Cripto e alavancagem envolvem risco de perda total.
