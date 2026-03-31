# 🔍 KGB CASE - PASS-THROUGH MONEY LAUNDERING ANALYSIS

**Case ID:** KGB.csv  
**Analysis Date:** March 20, 2026  
**Typology:** Pass-Through Money Laundering (Aggregation Scheme)  
**Confidence:** 100% (CRITICAL)

---

## 📊 EXECUTIVE SUMMARY

This case represents a **textbook pass-through money laundering operation** involving 17 subject accounts that collectively received **$1,333,965.23** from 432 unique senders via 20,063 P2P transactions, then withdrew **$1,199,167.91** through 1,728 transfers to linked payment sources.

**Key Indicators:**
- ✅ Many-to-One flow pattern (11.6:1 incoming:outgoing ratio)
- ✅ P2P incoming → Transfer outgoing (classic pass-through)
- ✅ 432 unique senders aggregating to 17 subjects
- ✅ 71.9% coded/cryptic payment comments
- ✅ 81.4% round dollar amounts
- ✅ High-velocity senders (239 sending 10+ times)
- ✅ Rapid aggregation and withdrawal patterns

---

## 🎯 THE 17 SUBJECTS

| # | Subject Token | Transactions | Unique Senders | Total Incoming | Avg per Txn |
|---|---------------|--------------|----------------|----------------|-------------|
| 1 | C_saepk1ybw | 1,234 | 45 | $88,419.87 | $78.88 |
| 2 | C_nh2h40ygq | 921 | 35 | $50,635.22 | $60.50 |
| 3 | C_nc2yjgydq | 1,337 | 32 | $58,130.21 | $46.50 |
| 4 | C_na2tkpyda | 1,346 | 22 | $66,331.79 | $53.24 |
| 5 | C_gxcpk1yj4 | 1,732 | 32 | $76,458.40 | $46.65 |
| 6 | C_nc2c4gyea | 1,203 | 27 | $53,104.44 | $47.29 |
| 7 | C_nh2hk0ype | 1,316 | 28 | $64,730.49 | $53.23 |
| 8 | C_haexjpygr | 1,722 | 32 | $86,799.52 | $54.01 |
| 9 | C_s9c4wpm7d | 899 | 10 | $42,829.04 | $51.35 |
| 10 | C_nx2a48y4e | 1,364 | 24 | $59,602.11 | $46.89 |
| 11 | C_nh2h4hy5e | 1,465 | 30 | $96,718.04 | $71.01 |
| 12 | C_fac2khy7n | 1,560 | 33 | $111,904.22 | $78.81 |
| 13 | C_8cee48y0x | 1,128 | 45 | $57,345.67 | $55.30 |
| 14 | C_geeawhm8h | 1,590 | 19 | $57,012.16 | $38.06 |
| 15 | C_fxc24hy46 | 980 | 18 | $65,108.35 | $72.83 |
| 16 | C_nh2nr0y9e | 685 | 36 | $42,759.70 | $69.64 |
| 17 | C_fech41yc9 | 1,309 | 13 | $256,076.00 | $234.07 |
| **TOTAL** | **21,791** | **432** | **$1,333,965.23** | **$66.49** |

---

## 🔥 COUNTERPARTY ANALYSIS: 432 UNIQUE SENDERS

### High-Velocity Senders (10+ transactions)

**239 senders (55.3% of all senders) responsible for 97.0% of all incoming transactions**

This concentration is a **major red flag** - the vast majority of money comes from a relatively small group of repeat senders, indicating an organized operation rather than legitimate business activity.

### Velocity Tiers

| Tier | Senders | Transactions | % of Total |
|------|---------|--------------|------------|
| **1-9 transactions** | 193 | 605 | 3.0% |
| **10-49 transactions** | 126 | 3,188 | 15.9% |
| **50-99 transactions** | 52 | 3,747 | 18.7% |
| **100+ transactions** | 61 | 12,523 | **62.4%** |

**Analysis:** 61 senders (14.1% of all senders) sent 100+ transactions each, accounting for 62.4% of all incoming money. This extreme concentration indicates a coordinated network.

---

## 🏆 TOP 20 HIGH-VELOCITY SENDERS

| Rank | Sender Token | Transactions | Total Amount | Avg Amount |
|------|--------------|--------------|--------------|------------|
| 1 | C_h42aahy44 | 567 | $34,423.00 | $60.71 |
| 2 | C_5q28x8m3s | 474 | $208,674.00 | $440.24 |
| 3 | C_8mepc0m3j | 466 | $9,016.93 | $19.35 |
| 4 | C_0senaayxw | 432 | $8,880.00 | $20.56 |
| 5 | C_nycxx1ygx | 411 | $13,245.00 | $32.23 |
| 6 | C_gtw9j1y2d | 405 | $19,581.00 | $48.35 |
| 7 | C_892xaqm63 | 366 | $48,860.12 | $133.50 |
| 8 | C_5jedkpmy2 | 353 | $14,160.00 | $40.11 |
| 9 | C_gscy20m26 | 304 | $13,761.90 | $45.27 |
| 10 | C_89eyxpmmy | 298 | $9,025.00 | $30.29 |
| 11 | C_gqctrgyga | 289 | $17,995.00 | $62.27 |
| 12 | C_8cwqjpyay | 288 | $20,700.00 | $71.88 |
| 13 | C_ssc4a1mvq | 273 | $12,385.00 | $45.37 |
| 14 | C_njdn4hy4j | 272 | $35,892.81 | $131.96 |
| 15 | C_5tcxqqm75 | 268 | $11,000.00 | $41.04 |
| 16 | C_g0cheqmsz | 261 | $10,899.00 | $41.76 |
| 17 | C_fq2zrqmyp | 254 | $15,208.00 | $59.87 |
| 18 | C_g42pdgy7r | 248 | $18,534.00 | $74.73 |
| 19 | C_00dvwhyzf | 246 | $20,416.21 | $82.99 |
| 20 | C_hxcn9hy6h | 242 | $6,230.00 | $25.74 |

**Top 20 senders alone:** 6,617 transactions = 33.0% of all incoming

---

## 🔄 NETWORK OVERLAP: SENDERS TO MULTIPLE SUBJECTS

**47 senders (10.9%) sent money to multiple subject accounts**

This indicates coordination between the 17 subject accounts - they're not operating independently but as part of a connected network.

### Top Cross-Network Senders

| Sender Token | Subjects Served | Transactions | Total Amount |
|--------------|-----------------|--------------|--------------|
| C_h42aahy44 | 3 | 567 | $34,423.00 |
| C_f4c8cpy56 | 3 | 40 | $930.17 |
| C_s9c8jhy5x | 2 | 170 | $5,188.00 |
| C_5jedkpmy2 | 2 | 353 | $14,160.00 |
| C_8qdtaamfz | 2 | 102 | $2,755.00 |
| C_5tcxqqm75 | 2 | 268 | $11,000.00 |
| C_00dvwhyzf | 2 | 246 | $20,416.21 |
| C_ssc4a1mvq | 2 | 273 | $12,385.00 |

**Analysis:** The presence of senders who transact with multiple subjects strongly suggests the 17 accounts are part of a coordinated money laundering network, not independent actors.

---

## ⏱️ TEMPORAL VELOCITY ANALYSIS

### Timeline
- **Date Range:** October 20, 2024 → March 20, 2026 (517 days)
- **Average Transactions per Day:** 38.8 incoming P2P
- **Peak Activity:** March 1, 2025 (101 transactions, $6,141.37)

### Top 10 Busiest Days

| Date | Transactions | Total Amount |
|------|--------------|--------------|
| 2025-03-01 | 101 | $6,141.37 |
| 2025-02-27 | 98 | $7,039.28 |
| 2025-05-01 | 96 | $7,200.47 |
| 2025-02-28 | 94 | $7,540.33 |
| 2025-05-30 | 94 | $8,752.81 |
| 2025-06-06 | 81 | $8,972.19 |
| 2025-08-27 | 77 | $5,792.98 |
| 2025-04-11 | 76 | $8,444.16 |
| 2025-05-10 | 75 | $6,832.77 |
| 2025-06-21 | 75 | $7,732.21 |

**Analysis:** Consistent daily activity over 517 days with periodic spikes indicates an ongoing, organized operation rather than sporadic legitimate business.

---

## 💬 COMMENT ANALYSIS

### Coded/Cryptic Comments: 71.9%

**Sample coded comments:**
- Number-only IDs: "363691699", "308770150", "303006057", "38302382"
- Short codes: "rc", "g", "y"
- Emojis: "🔥", "🌐🌐", "😊"
- Punctuation: "..", "....", "....", ","
- Single names: "Salvo"
- Platform IDs: "LIVE ME ID. 303006057"

**Analysis:** The overwhelming presence of coded comments (rather than legitimate payment descriptions like "rent", "dinner", "photography services") is a strong indicator of illicit activity. Legitimate businesses would have descriptive payment purposes.

---

## 💰 AMOUNT ANALYSIS

### Incoming Transactions (P2P)
- **Total:** $1,333,965.23
- **Average:** $66.49
- **Median:** $33.33
- **Range:** $1.00 - $25,678.00
- **$30-$300 range:** 11,950 transactions (59.6%)
- **Round amounts:** 81.4%

### Outgoing Transactions (Transfers)
- **Total:** $1,199,167.91
- **Average:** $693.96
- **Median:** $775.50
- **Range:** $1.00 - $1,990.00
- **$700-$1,000 range:** 898 transactions (52.0%)

### Net Flow
- **Retained:** $134,797.32 (10.1% of incoming)
- **Analysis:** The 10% retention suggests a fee/commission structure typical of money laundering operations

---

## 🚨 SUSPICIOUS ACTIVITY INDICATORS

### ✅ CRITICAL INDICATORS (All Present)

1. **Many-to-One Flow Pattern**
   - 432 senders → 17 subjects
   - 11.6:1 incoming:outgoing ratio
   - Textbook aggregation scheme

2. **Product Type Mismatch**
   - Incoming: 100% P2P (peer-to-peer payments)
   - Outgoing: 98.2% Transfers (withdrawals to linked accounts)
   - Classic pass-through pattern

3. **High-Velocity Senders**
   - 239 senders with 10+ transactions (55.3%)
   - 61 senders with 100+ transactions (14.1%)
   - 97.0% of money from repeat senders

4. **Network Coordination**
   - 47 senders transact with multiple subjects
   - Indicates organized network, not independent activity

5. **Coded Communications**
   - 71.9% coded/cryptic comments
   - Number IDs, emojis, single letters
   - No legitimate business descriptions

6. **Round Amount Concentration**
   - 81.4% round dollar amounts
   - Typical of cash-based illicit activity

7. **Rapid Aggregation & Withdrawal**
   - Money received via P2P
   - Aggregated in account
   - Withdrawn via transfers
   - Often same-day or within hours

8. **Sustained High Volume**
   - 517 days of continuous activity
   - 38.8 transactions per day average
   - Organized, ongoing operation

---

## 🎯 TYPOLOGY DETERMINATION

**Primary Typology:** Pass-Through Money Laundering (Aggregation Scheme)

**Confidence:** 100% (CRITICAL)

**Risk Level:** CRITICAL

### Why This is Pass-Through Money Laundering:

1. **Aggregation Pattern:** Multiple senders → Few subjects → Withdrawals
2. **Product Mismatch:** P2P in, Transfers out (not P2P both ways)
3. **No Legitimate Business Purpose:** Coded comments, no business terminology
4. **High Velocity:** Repeat senders, consistent daily activity
5. **Network Coordination:** Cross-subject sender relationships
6. **Fee Structure:** 10% retention suggests commission-based operation

### What This is NOT:

- ❌ **Legitimate Business:** No business terminology, coded comments
- ❌ **Personal Payments:** Too many counterparties, too organized
- ❌ **Gambling:** No platform names, wrong amount patterns
- ❌ **Drug Sales:** Wrong flow pattern (not many-to-one with small amounts)

---

## 📋 RECOMMENDATION

**🚨 FILE SUSPICIOUS ACTIVITY REPORT (SAR)**

**Basis for SAR:**
- Pass-through money laundering with 100% confidence
- $1.3M in suspicious incoming funds
- 432 unique senders in coordinated network
- 17 subject accounts operating as aggregation points
- Coded communications indicating illicit activity
- Sustained operation over 517 days
- No legitimate business purpose identified

**Suggested SAR Narrative Focus:**
1. Describe the many-to-one aggregation pattern
2. Highlight the 432 unique senders and high-velocity patterns
3. Detail the P2P → Transfer product type mismatch
4. Explain the coded comment analysis
5. Note the network coordination (47 cross-subject senders)
6. Emphasize the lack of legitimate business indicators
7. Calculate the $1.3M total suspicious funds

---

## 📊 COMPARISON TO OTHER TYPOLOGIES

| Metric | KGB Case | Typical Drug Sales | Typical Gambling | Legitimate Business |
|--------|----------|-------------------|------------------|---------------------|
| **Flow Pattern** | Many-to-One | Many-to-One | Many-to-One | Many-to-Many |
| **Product Types** | P2P → Transfers | P2P → P2P | P2P → P2P | Mixed |
| **Incoming Avg** | $66.49 | $50-$100 | $100-$500 | Varies |
| **Outgoing Avg** | $693.96 | $50-$100 | $100-$500 | Varies |
| **Comments** | Coded (72%) | Drug slang | Platform names | Business terms |
| **Senders** | 432 | 50-200 | 20-100 | 10-50 |
| **Velocity** | 239 high-vel | High | High | Low-Medium |

**Conclusion:** KGB case matches pass-through money laundering profile, not drug sales, gambling, or legitimate business.

---

## 🔬 TECHNICAL DETECTION DETAILS

### PassThroughDetector Scoring

**Confidence Calculation (100/100 points):**
- ✅ Flow Pattern (30/30): High incoming count, 11.6:1 ratio, 432 senders
- ✅ Amount Patterns (25/25): 59.6% in $30-$300 range, 52% out in $700-$1000 range
- ✅ Product Types (15/15): 100% P2P incoming, 98.2% Transfer outgoing
- ✅ Comment Patterns (20/20): 71.9% coded comments
- ✅ Round Amounts (10/10): 81.4% round incoming amounts

**Total: 100/100 = CRITICAL Risk Level**

---

## 📝 NEXT STEPS

1. **File SAR** with FinCEN
2. **Investigate Sender Network** - Identify the 432 senders
3. **Link Analysis** - Map relationships between 17 subjects
4. **Destination Analysis** - Where did the $1.2M go after withdrawal?
5. **Historical Review** - Any prior SARs on these accounts?
6. **Law Enforcement Referral** - Consider referring to appropriate agencies

---

**Analysis Completed:** March 20, 2026  
**Analyst:** SAR Workflow Test  
**Review Status:** Ready for CCO Presentation
