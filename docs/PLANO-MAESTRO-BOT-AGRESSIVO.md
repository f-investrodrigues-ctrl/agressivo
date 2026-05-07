# Projeto Bot Agressivo (Assimetria) — Plano mestre

**Versão:** 1.0  
**Data:** 2026-05-03  
**Uso:** documento vivo — consultar em kickoff, reviews, gates de decisão e fecho do projeto.

**Objetivo do produto:** sistema sistemático orientado a **expectativa líquida positiva**, **crescimento geométrico sustentável** (Kelly fracionário) e **sobrevivência em regimes de alta correlação**, com núcleo em momentum/breakout e satélite event-driven opcional.

**Avisos:** resultados passados não garantem futuros; alavancagem amplifica perdas; cripto/DeFi envolve contratos inteligentes, contraparte e risco jurisdicional. Este documento **não** é recomendação de investimento.

---

## Índice

1. [Síntese executiva e referências externas](#1-síntese-executiva-e-referências-externas)  
2. [Narrativa para apresentação](#2-narrativa-para-apresentação-slides)  
3. [Fundamentos e KPIs](#3-fundamentos-e-kpis)  
4. [Arquitetura em três camadas](#4-arquitetura-em-três-camadas)  
5. [Motor “Sniper” (score + vetos)](#5-motor-sniper-score--vetos)  
6. [Gestão de risco e carteira](#6-gestão-de-risco-e-carteira)  
7. [Ciclo de validação e gates](#7-ciclo-de-validação-e-gates)  
8. [Implementação por fases](#8-implementação-por-fases)  
9. [Rituais, papéis e checklists](#9-rituais-papéis-e-checklists)  
10. [Definition of Done (conclusão do projeto)](#10-definition-of-done-conclusão-do-projeto)  
11. [Changelog](#11-changelog)

---

## 1. Síntese executiva e referências externas

### 1.1 O que maximiza “probabilidade de bom resultado”

- Não confundir **taxa de acerto** com **valor esperado** ou **crescimento geométrico** do patrimônio.
- Objectivo operacional recomendável: maximizar **E[log(patrimônio)]** ao longo do tempo → **Kelly** como *teto* teórico; na prática **Kelly fracionário** (¼ a ½) por causa de **erro de estimação** dos parâmetros e caudas gordas.
- **Custos** (fees, slippage, funding) entram sempre na expectancy; estratégias com muito turnover podem morrer net-of-fees mesmo com lucro bruto ([literatura trend following / turnout e custos — ex. SSRN “Does Trend Following Still Work on Stocks?”](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5084316)).
- Payoffs assimétricos (poucos ganhos grandes) podem alterar **probabilidade de ruína** e trajetórias mesmo com EV nominal semelhante — sizing conservador quando o edge é incerto ([discussão teórica com payoffs assimétricos](https://www.karlwhelan.com/Papers/Ruin.pdf)).

### 1.2 Leituras úteis (não inclusas no repo)

- Kelly e Kelly fracionário: prática habitual [Coriva — Kelly na prática](https://coriva.eu.org/en/kelly-criterion-position-sizing/), [Quant Decoded — half-Kelly](https://quantdecoded.com/en/kelly-criterion-optimal-position-sizing).
- Correlação e regimes em crypto: matrizes **rolling**, convergência em stress ([exemplo didático correlation risk](https://smartmoneyapi.com/resources/risk-management/corpus/correlation-risk.html)).
- Exemplo de framework acadêmico aplicável a seleção/regime em cripto (inspirar *process*, não copiar números): [AdaptiveTrend, arxiv](https://arxiv.org/abs/2602.11708).

---

## 2. Narrativa para apresentação (slides)

| # | Mensagem principal |
|---|---------------------|
| 1 — Problema | Retorno assimétrico sem gestão de risco/correlação eleva probabilidade de ruína; “yield bot” não é caçador de caudas. |
| 2 — Solução | Core momentum/breakout + satélite event-driven + opcional vol; decisões por **score + vetos**. |
| 3 — Diferencial | Sucesso medido por **expectativa líquida**, drawdown dentro de budget e gates OOS — não apenas win rate. |
| 4 — Arquitetura | Ingestão → qualidade → features versionadas → motor de sinais → risk engine → execução → ledger → monitorização. |
| 5 — Risco | Kelly ¼–½, caps leverage, budget de correlação, stops diários/semanais, kill switch de modelo. |
| 6 — Roadmap | Fases 0–7 com artefactos e gates explícitos. |
| 7 — Antigo escopo | Maximizar acerto ignorando custos; escalar satélite sem edge mensurável. |

---

## 3. Fundamentos e KPIs

### 3.1 KPIs obrigatórios (dashboard)

| Métrica | Definição operacional |
|---------|-------------------------|
| Expectativa por trade líquida | \(E = p\bar{W} - (1-p)\bar{L} - \text{custos}\) |
| Profit factor líquido | Soma ganhos / \|soma perdas\| |
| Max drawdown / tempo em DD | Pico a vale e duração |
| Skew / tail da PnL | Coerência com design assimétrico |
| Correlação efectiva do book | Agregar posição–posição (regime-aware) |
| Cost per trade | Fee + slip + funding médio |
| Tag de regime | bull / chop / crash (definição **versionada** no git) |

### 3.2 Ideias originais do produto (preservadas e refinadas)

**Três estratégias candidatas:**

1. **Momentum + Breakout (Core)** — cauda direita via trend-following agressivo; filtros durados; entrada alavancada com limites; saídas: SL, trailing, TP parcial.  
2. **Event-driven DeFi Hunter (Satélite)** — catalisadores (lançamentos, incentivos, airdrops, tokenomics, governance, unlocks, migrações); baixa frequência, maior dispersão informacional.  
3. **Volatility Hunter (Opcional)** — só após infra e validação; risco alto de overfitting.

**Ideia “Sniper”:** poucas entradas fortes quando múltiplos sinais alinham (volume, OI, funding “não insano”, on-chain, breakout estrutural) — refinado para **sistema de pontuação + vetos** (secção 5).

**Travas comportamentais (manter):** stop diário (ex.: -5%), semanal (ex.: -10%), pausa após N losses seguidos, leverage máximo (ex.: ≤5×), nunca 100% do capital em risco simultâneo.

**Alocação inicial discutida (ajustável por gates):** ~50/30/20 momentum/event/caixa → **refinamento profissional:** orçamento por **risco**, não só notional; satélite **15–25%** do risco até métricas OOS próprias; caixa **15–25%** como sobrevivência em crash correlacionado.

---

## 4. Arquitetura em três camadas

### A — Core (55–70% do risco inicial)

- Compressão antes da expansão + breakout estrutural.  
- Volume/OI compatíveis com continuação (penaliza falsos breaks).  
- Funding/OI: **condição ou veto**, não único disparo.  
- On-chain: confirmação por **persistência** em janela.  
- Social/narrativa: **veto** (“precificado”) até estudo próprio com edge.

### B — Satélite event-driven (15–25% do risco inicial)

- Pipeline: calendário → catalisador → liquidez → janela de execução → saída.  
- Promoção só com histórico OOS e sem degradar carteira agregada.

### C — Vol sleeve (0–15% risco — R&D)

- Congelado até Core estável e dados de regime/vol adequados.

---

## 5. Motor “Sniper” (score + vetos)

### Blocos de score (pesos **versionados** no repositório)

| Bloco | Papel típico |
|-------|----------------|
| Breakout estrutural + compressão | Aumentar \(P(\text{follow-through})\) |
| Volume / OI alinhados | Filtrar armadilhas de breakout |
| Funding | Veto ou downweight em extremos |
| On-chain persistente | Confirmação, não gatilho isolado |
| Macro / cronómetro | Lista de veto (FOMC, incidentes systemic, …) |

**Regra:** operar apenas se **score ≥ S\*** *(calibrado em walk-forward)* **e** nenhum veto ativo.

**Nota empírica de mercado:** win rates baixos (ex. 20–40%) são comuns em breakout; edge vem dos **multiples-R** ganhadores vs perdas cortadas — validar sempre **líquido de custos**.

---

## 6. Gestão de risco e carteira

### 6.1 Sizing

- Estimar Kelly com \(p\), payoff médio vencedores e perdas médias (**após custos**).  
- Aplicar **¼ a ½ Kelly** na prática por incerteza de parâmetros.  
- **Nunca exceder** o Kelly verdadeiro: acima ~2× Kelly o crescimento geométrico tende a piorar fortemente ([literatura Kelly / Thorp linha narrativa — ver links secção 1](https://quantdecoded.com/en/kelly-criterion-optimal-position-sizing)).

### 6.2 Exemplo mental (referência apenas)

- Capital R\$1.000; risco 2% por trade = R\$20; alvo payoff 1:5 — válido apenas se \(p\) e custos sustentarem a expectancy; clustered losses em regime único invalidam independência das perdas nos exemplos i.i.d.

### 6.3 Correlação e stress

- Ativos com correlação elevada ⇒ **uma** posição para limite agregado.  
- Monitorizar correlações **rolling** (7d/30d/90d); em stress crypto as correlações tendem a convergir.  
- Stress test: cenário correlações → alta; reduzir exposures ou hedge conforme política.

### 6.4 Leverage

- Limite declarado (ex.: máx. 5×) — alívio adicional por vol de carteira e sequência adversa.

---

## 7. Ciclo de validação e gates

Para **cada** release material de estratégia:

1. Hipótese **falsificável** por escrito.  
2. Backtest com **atrito realista**.  
3. **Walk-forward** + holdout.  
4. Paper trading (latência real).  
5. Canário (capital micro).  
6. Produção com limites e **rollback**.

**Kill switch de modelo:**

- deterioração OOS de PF/expectancy além do limiar; ou  
- violação persistente da qualidade de dados; ou  
- drift de custos/fees não modelado.

**Gate exemplo para Core:** PF líquido > 1 (ou expectancy > 0) com DD dentro do orçamento; sensibilidade a parâmetros documentada **sem** “parameter bomb” injustificado.

---

## 8. Implementação por fases

Cada fase termina em **artefactos** + **gate** (aprovar antes de avançar).

### Fase 0 — Fundação

- Repo, ambientes, segredos, convenções de log (correlation id por ordem).  
- Documento único de **política de risco** (risco/trade, max posições, leverage cap).  
- **Gate 0:** CI básico; segredos fora do código; prova de ingestão mínima.

### Fase 1 — Data plane

- OHLCV; funding/OI se perps; on-chain MVP; qualidade (gaps, sync, outliers).  
- Versionamento de datasets.  
- **Gate 1:** relatório cobertura e SLAs.

### Fase 2 — Backtester + exec simulada

- Slippage, fees, funding, latência; relatórios equity/R-multiple/custo.  
- **Gate 2:** sanity parity curta paper vs sim.

### Fase 3 — Core strategy v1

- Regras formais entrada/saída; regime filter v1; integração risk.  
- **Gate 3:** walk-forward conforme §7.

### Fase 4 — Risk engine e portfolio layer

- Kelly rolling conservador + ¼–½; clusters correlacionados; stops portfolio; cooldown pós-loss.  
- **Gate 4:** stress scenarios documentados dentro de limites.

### Fase 5 — Execução ao vivo

- Exchange adapters: retries, idempotência, reconciliação.  
- Runbooks falhas API/order/posição.  
- **Gate 5:** ≥2 semanas paper sem incidente crítico; reconciliação ok.

### Fase 6 — Satélite event-driven

- Calendário + scoring dedicado + orçamento de risco.  
- **Gate 6:** OOS próprio sem piorar agregados.

### Fase 7 — Conclusão formal

- Ver §10 Definition of Done.

---

## 9. Rituais, papéis e checklists

### Rituais

| Ritual | Frequência | Output |
|--------|------------|--------|
| Data health | Semanal | Log gaps/latência |
| Strategy review | Quinzenal | manter / ajustar / matar feature |
| Risk review | Mensal | caps e Kelly rolling |
| Pós-mortem DD | Eventual | novos vetos / regime |

### Checklist — antes de trade em produção

- [ ] Dados dentro do SLA  
- [ ] Spread e profundidade ok  
- [ ] Risco agregado e correlação ok  
- [ ] Funding / manutenção verificados  
- [ ] Ordem idempotente + logs com trace id  

### Checklist — release nova regra

- [ ] Hipótese escrita  
- [ ] Backtest + walk-forward com custos  
- [ ] Sem lookahead  
- [ ] Plano de rollback  

---

## 10. Definition of Done (conclusão do projeto)

- [ ] Diagrama de arquitectura e fluxo de dados actualizados  
- [ ] Runbooks operacionais (API, exchange, divergence)  
- [ ] Política de risco e catálogo de métricas (§3) implantados em dashboard  
- [ ] **Versionamento** de regras, pesos do score \(S\) e definições de regime  
- [ ] Replay reprodutível de pelo menos uma janela histórica  
- [ ] Processo de manutenção (keys, revisão mensal de \(S^\*\), custos) escrito  
- [ ] Retrospectiva formal com lista de falhas/incidentes  

---

## 11. Changelog

| Versão | Data | Alterações |
|--------|------|------------|
| 1.0 | 2026-05-03 | Documento inicial: apresentação, implementação, fundamentos externos, KPIs e fases. |

---

**Regra:** incrementar versão ao mudar caps de risco, definição de regime, pesos do score, ou conectores críticos; registar neste changelog.
