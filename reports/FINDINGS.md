# Polymarket Perps — "The Big Treasure" research (Sept 5–6, 2026)

Scope: Polymarket Perps (launched publicly Sept 3, 2026; early access since ~July 20), 67 markets, 20x max leverage.
Data: 7 weeks of Polymarket perps history (funding, 1m candles, 1m mark, public trades for the largest markets, live
order books/BBO for all 67), Hyperliquid comparables (main + xyz HIP-3 equity/commodity perps), Coinbase 1m spot,
and ~5,000 Polymarket binary markets on the same underlyings (daily strike ladders, touch ladders, 15m/4h up-or-down).
All code is in `src/`, raw data is not committed (see `.gitignore`); every number below is reproducible from the scripts.
The full Polymarket-vs-Hyperliquid funding differential table is in `reports/funding_differential_table.csv`.

## Verdict, in one paragraph

There is no single robust, retail-executable, high-edge strategy hiding in Polymarket perps ("the treasure" as a
directional or arbitrage trade does not exist in the data). Every candidate that first looked like it — binary-vs-perps
mispricing, cross-venue price convergence, liquidation sweeps, session gaps — either disappeared under audit (look-ahead,
stale prints, placeholder prices, trend-contaminated samples) or belongs to sub-second bots. What survives is a small set
of **structural carry edges** created by how the venue is built and who trades on it. They are real, proven over the
sample, delta-neutral, and executable by a regular trader with two accounts, but they pay 10–35 %/yr on notional
(roughly 30–100 %/yr on capital at 3–5x leverage), with capacity in the low millions. That is gold, not treasure, and
this report says so plainly rather than dressing it up.

## What the venue is (facts that drive everything)

- Hybrid exchange: off-chain matching, Polygon settlement, pUSD collateral. Taker fee 4.0 bps, maker 1.25 bps (tiered).
- Funding hourly. Premium measured from $1,000-notional impact prices; `F_8h = scale*(P + clamp(0.01% - P, ±0.05%))`,
  scale 1.0 crypto / 0.5 non-crypto, hourly cap ±4 %. Because books are extremely tight, funding sits at the interest
  floor (10.95 %/yr crypto, 5.475 %/yr non-crypto) most of the time (BTC/ETH: 100 % of hours in the last week).
- Mark = median(index-anchored EMA of mid, local median(bid,ask,last), external mark feeds); Index from Pyth,
  Chainlink Data Streams and Hyperliquid, with session-dependent feed sets for equities.
- Liquidations are IOC market orders with no protective band; insurance fund + ADL backstop; BLP program is invite-only.
- Liquidity rewards: $75k/day split *evenly* across all 67 markets ($1,119/market/day), scored on two-sided depth
  within 5/10/20 bps (weights 1/0.25/0.10, $100k cap per tier), 7-day maker-share gate of 1 %, exponent 0.65 on
  liquidity, 0.35 on maker share. OI rewards (6 % APR) now require $5M average OI — whales only.
- Books are deep and tight in majors because of the subsidy: BTC 0.1 bps spread with ~$0.9M within 5 bps each side;
  SP500/GOLD ~$2M within 5 bps. Venue volume $40–300M/day, OI ~$53M.

## Everything tested, and what happened

| # | Idea | Result | Why |
|---|------|--------|-----|
| 1 | Funding arbitrage vs Hyperliquid (all assets) | **Silver**. Alt basket long-PM/short-HL realized 12.1 %/yr (6/6 weeks positive, min 5.3 %); newest listings 20–60 %/yr for 1–2 weeks; commodities short-PM/long-HL 9.3 %/yr (75 % weeks). OOS weekly rotation of top-3 by trailing differential: 11.9 %/yr gross (90 % hit), ~3 % net of rotation costs. | Polymarket alt books sit 7–12 bps below Hyperliquid prices; shorts pay longs. Lumpy (a few big days), decays with rotation. |
| 2 | STRC (12 %-yielding preferred) perp: dividend leakage + funding asymmetry | **Gold, tiny capacity**. Perp index does not adjust for the semi-monthly $0.50 dividend (drop observed Aug 14–15 and Aug 31); PM funding averaged +21 %/yr since listing (longs pay), HL STRC −7.6 %/yr. Short PM / long STRC stock ≈ 12 % (dividend leakage) + 5.5–21 % (funding) per year; short PM / long HL ≈ 28.5 %/yr funding differential (5/5 weeks positive). PM OI only $51k. | No corporate-action handling anywhere in docs; retail longs on a bond-like instrument. |
| 3 | Liquidity-reward farming | **Silver (needs an MM bot)**. Incumbents saturate the $100k tier in almost every market. A $100k/side newcomer earns ≈ $275–370/day/market; worst-case pick-off cost (every 1-min move >5 bps fills you) exceeds that everywhere except SP500-USD (+$46/day) and, marginally, NAS100. Dead markets (DELL, ZM, CXMT, WLD) pay $800–1,100/day to a lone tight quoter but their feeds jump 27–44 times a day by >30 bps. | Program is public, contested, sub-second re-quoting required; not "no infra". |
| 4 | Daily BTC/ETH/SOL strike ladders vs perps (delta-hedged) | **Nothing**. 320 events, ~5,000 markets. Hedged PnL −2 to −7 c/share at 3–24 h horizons after 1 c half-spread, 7 %·p(1−p) fee and 4 bps hedge costs; both realized-vol and ATM-implied models. Unhedged "edges" were the May–June downtrend. | Ladder prices are close to fair; the crude model beats the market by Brier but not by enough to pay costs. |
| 5 | Touch ("hit $K by …") ladders | **Nothing**. After removing the 0.50 placeholder prices at market creation (which produced a fake 92 %-win "sell" signal), sell-rich PnL is +7 c ± 3–6 c (trend) and buy-cheap ≈ 0; market Brier beats the reflection-principle model. Far-OTM "lottery" touches (≤1 c) went 0 for 21 despite a +19 % BTC sample. | Markets track the spot path well; the earlier signal was an artifact. |
| 6 | 15-minute up/down binaries (Chainlink TWAP) | **Fee sink**. 872k trades / 1,328 markets / 8 days / $11.3M taker notional. Takers −1.18 % after fees, +0.83 % *pre-fee*; fees = 2.0 % of notional; wallets with <20 trades −6.4 %; 58 wallets with >2,000 trades +2.0 % pre-fee but −0.36 % after fees. First candle-based test showing +4 c/share was look-ahead (prev-minute-close alignment killed it); CLOB history within windows is sparse. | The only winner is fees. Makers lose pre-fee to fast takers. |
| 7 | 4-hour up/down binaries | **Silver, tiny**. Takers +0.8 % after fees on $0.7M/8 days (stale makers). ≈ $700/day for all takers combined. | Too small to matter. |
| 8 | Cross-venue 1-minute convergence (PM vs HL) | **Illusion**. Candle test showed beta −0.9 and +10–45 bps/trade; but 60–100 % of the deviation is gone by the next print (those minutes have 1–3 tiny prints). Live BBO-vs-HL-mid test (1 Hz, all 67 markets): where HL mid sits outside PM's BBO it does so *persistently* (LIT 17 bps, CXMT 16, TSLA 13, ZEC 11 median), PM's BBO does not converge within 15 s (round trip −2 to −10 bps) and HL does not lead. | Stale-print artifact + stable basis; MMs re-quote 50–1,000×/min. |
| 9 | Liquidation sweeps / far-from-mark prints | **Nothing**. Big dislocations are macro releases (12:30 UTC NFP: $3.9M gold traded 50 bps off), CME Sunday open, and one $684k fat-finger (SP500 Aug 28). Resting-order harvesting: negative in GOLD/WTI/SILVER at 15/25/40 bps; marginally positive in SP500/NAS100 at 40 bps with <1 fill/day. | Far prints are informed; fat fingers are sniped by bots in seconds. |
| 10 | Session effects (US open/close, 23:00 UTC jumps, overnight/weekend reversal) | **Nothing**. Overnight→open and weekend→Monday fades: |t|<1.5. 23:00 UTC variance spike is 4 SK Hynix events. | |
| 11 | Taker-flow imbalance (SP500, BTC) | **Nothing** (|corr| < 0.06 at 1–24 h). | Flow is noise. |
| 12 | Twin listings SKHY vs SKHYNIX pairs; BRENT/WTI; NAS100/SP500 | **Nothing robust**. Log-ratio wanders ±3 % with 27 h half-life; z-score strategy flips sign across windows; 65 % stop-outs. 1-min lead of SKHY over SKHYNIX (corr 0.15) too small vs costs. | |
| 13 | Stale-index instruments (DRAM, SPCX, CXMT) | **Nothing**. Indices move continuously (HL xyz-driven); no step behaviour. | |
| 14 | Weekend/hour-of-day funding structure | Weak: alt carry 19 %/yr on weekends vs 11 % weekdays. | |

## The surviving edges, specified

### A. Hedged funding carry, Polymarket vs Hyperliquid (the broadest)
- Long Polymarket alt perps (ZEC, PUMP, KPEPE, XRP, DOGE, KSHIB, NEAR, ADA, SUI, FARTCOIN, ONDO, ENA …) / short the
  same coins on Hyperliquid, equal notional, 3–5x. Realized 12.1 %/yr on notional over 6 weeks (every week positive),
  20–60 %/yr in the first 1–2 weeks after a listing wave. Weekends pay ~2x weekdays.
- Short Polymarket commodity perps (GOLD, SILVER, WTI, BRENT) / long HL xyz: 9.3 %/yr, 75 % of weeks positive.
- Costs: ~17 bps round trip (4 bps PM + 4.5 bps HL, both ways). Basis risk: PM-vs-HL 1-min deviations p95 15–40 bps
  (alts), so enter/exit passively. Capacity: PM OI per alt $20k–320k (total alt OI ≈ $1.5M); commodities $0.3–3M.
- Why it exists: Polymarket books sit below index on alts (prediction-market users short "shitcoins"); funding floor
  and thin arbitrage capital on a 3-day-old venue. Expect decay as arbitrageurs arrive; monitor weekly.

### B. STRC short (dividend leakage + funding)
- Short STRC-USD on Polymarket (10x max; book $176k/$468k at top, 6 bps spread), hedge with STRC shares (12 % coupon,
  semi-monthly, next ex-dates Sept 15 and Sept 30) or with long xyz:STRC on Hyperliquid.
- Stock hedge: ≈ 12.3 %/yr dividend leakage + Polymarket funding received (21 %/yr average since Aug 6, 5.5 % floor,
  5–17 % in the last three weeks) ⇒ 18–33 %/yr on notional. HL hedge: 28.5 %/yr funding differential (5/5 weeks).
- Capacity today ≈ $50k (PM OI). Risk: STRC price risk is small (par-anchored preferred) but 10x leverage on a 6 %
  drawdown instrument still needs ≤5x; basis vs HL p95 25 bps.

### C. Liquidity rewards where the index barely moves (bot required)
- Weekdays: only SP500-USD survives at 1-second latency. Two-sided quotes within 5 bps, $10k–100k per side,
  re-centered every second: ≈ $78/day ($10k) to ≈ $280/day ($100k) gross, worst-case pick-off $24–235/day.
- Weekends (Sat 00:00 → Sun 21:00 UTC): CME-hours and equity indices are quasi-frozen (SP500 2.6, NAS100 3.5, GOLD 0.9,
  NVDA 4.6, TSLA 7.3 moves >5 bps per day vs 16–276 on weekdays). Quoting $100k/side then nets, even in the worst case
  where every breach fills you, ≈ +$228 (SP500), +$163 (NAS100), +$276 (GOLD), +$70–190 (AAPL/MSFT/NVDA/TSLA) per market
  per weekend day. Roughly $1.5–2k/day across ~10 markets on ~$2M resting notional.
- The catch is the eligibility gate: ≥1 % of the market's trailing-7-day maker volume. In SP500 that is ≈ $140k of fills
  per week, which a ±5 bps weekend-only quoter (behind incumbents at ±0.2 bps) will not get; it is feasible only in
  low-volume equities (AAPL ≈ $120/week, TSLA ≈ $8k/week, NVDA ≈ $12k/week). Silver-plus, not treasure.

## Audit trail (bugs and biases found before they became "results")
- 15m binaries: aligning quotes to the *same*-minute Coinbase/PM close leaked 40 s of future price; fixed to the
  previous fully closed minute. Trade-level data-API timestamps are settlement times; live CLOB capture used instead.
- Touch ladders: CLOB history reports 0.50 at market creation before any trade; a 92 %-win "sell" signal was entirely
  this placeholder. Filter: >12 h after creation and price ∉ [0.49, 0.51].
- Strike ladders: unhedged calibration tables were dominated by the May–June BTC downtrend (YES realized 14 % at 45 c);
  only the delta-hedged test is trend-neutral, and it is negative net of costs.
- Cross-venue convergence: candle closes are stale prints in thin books; verified against next-print and live BBO.
- Funding panel: an early parquet contained only the latest 100 hours for 30 instruments (the API returns newest-first);
  rebuilt from complete files before the basket/event-time conclusions.
- Hyperliquid 1m candles are only served for the latest ~3.5 days; longer comparisons use funding (full) and Coinbase.

## Live-executability notes for a regular trader
- Polymarket perps: non-US, referral-gated access; REST/WS public data needs no key; trading via the SDK.
- Carry (A, B) needs a Hyperliquid account (or a brokerage for STRC shares); hourly funding on both venues; no speed.
- Rewards (C) need a quoting bot; without it every market except SP500 is net negative at 1-second latency.
- Everything in the "Nothing"/"Fee sink" rows is either bot-only (sub-second) or negative for takers after fees.

## Suggested next step
Paper-trade A and B for 4 weeks with real passive entries, logging realized funding on both legs and basis at entry/exit;
the go/no-go is whether realized carry stays above 8 %/yr on notional after costs. Re-run `src/` weekly: the venue is
three days into public launch and every number here has a short history.
