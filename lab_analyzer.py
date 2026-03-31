"""
kitt Lab — Pre-Analysis Engine

Runs comprehensive analysis on CSV data BEFORE sending to the LLM.
Produces detailed findings that the LLM then writes into a report.

This ensures the LLM has real computed data, not guesses.
"""

from collections import Counter, defaultdict
from datetime import datetime
import re


def run_lab_analysis(transactions, analyst_context=''):
    """
    Run comprehensive pre-analysis on transaction data.
    Returns a detailed findings dict that the LLM can write a report from.
    """
    successful = [tx for tx in transactions if tx.is_paid_out()]
    failed = [tx for tx in transactions if tx.is_failed()]
    p2p_all = [tx for tx in transactions if tx.is_p2p()]
    p2p_success = [tx for tx in p2p_all if tx.is_paid_out()]
    
    subjects = sorted(set(tx.subject for tx in transactions))
    
    findings = {
        'overview': analyze_overview(transactions, successful, subjects),
        'hotel_pattern': analyze_hotels(successful),
        'adult_content': analyze_adult_content(successful),
        'late_night': analyze_late_night(transactions),
        'suspicious_comments': analyze_suspicious_comments(p2p_all),
        'cash_pattern': analyze_cash_pattern(successful),
        'merchant_pattern': analyze_merchants(successful),
        'counterparty_analysis': analyze_counterparties(p2p_all, subjects),
        'temporal_pattern': analyze_temporal(successful),
        'amount_pattern': analyze_amounts(p2p_success),
        'institutional_indicators': analyze_institutional(successful),
        'drug_indicators': analyze_drug_indicators(p2p_all, successful),
        'trafficking_indicators': analyze_trafficking_indicators(p2p_all, successful),
        'digital_content_indicators': analyze_digital_content(successful, p2p_all),
    }
    
    # Build summary of key red flags
    red_flags = []
    for category, data in findings.items():
        if isinstance(data, dict) and data.get('red_flags'):
            for flag in data['red_flags']:
                red_flags.append(f"[{category.upper()}] {flag}")
    
    findings['red_flag_summary'] = red_flags
    findings['analyst_context'] = analyst_context
    
    return findings


def analyze_overview(transactions, successful, subjects):
    """Basic case overview."""
    return {
        'total_transactions': len(transactions),
        'successful': len(successful),
        'failed': len(transactions) - len(successful),
        'subject_count': len(subjects),
        'subjects': subjects,
        'date_range': (
            min(tx.date for tx in transactions).isoformat() if transactions else '',
            max(tx.date for tx in transactions).isoformat() if transactions else '',
        ),
        'red_flags': [],
    }


def analyze_hotels(successful):
    """Detect hotel/motel purchases."""
    hotel_keywords = ['hotel', 'motel', 'inn ', 'inn-', 'suites', 'lodge', 'la quinta', 
                      'comfort', 'quality inn', 'econo lodge', 'woodspring', 'clarion',
                      'holiday inn', 'best western', 'days inn', 'super 8', 'red roof',
                      'marriott', 'hilton', 'hampton', 'courtyard', 'fairfield',
                      'residence inn', 'springhill', 'extended stay', 'studio 6',
                      'motel 6', 'americas best']
    
    cc = [tx for tx in successful if (tx.product_type or '').upper() == 'CASH_CARD']
    
    hotel_txns = []
    hotel_names = Counter()
    for tx in cc:
        comment = (tx.comment or '').lower()
        for kw in hotel_keywords:
            if kw in comment:
                hotel_txns.append({
                    'date': tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date),
                    'amount': tx.amount,
                    'merchant': tx.comment,
                    'subject': tx.subject,
                })
                hotel_names[tx.comment] += 1
                break
    
    red_flags = []
    if len(hotel_txns) >= 3:
        total = sum(t['amount'] for t in hotel_txns)
        unique_hotels = len(hotel_names)
        red_flags.append(f"{len(hotel_txns)} hotel/motel purchases totaling ${total:,.2f} at {unique_hotels} different properties")
        if unique_hotels >= 3:
            red_flags.append(f"Multiple different hotels suggests movement/rotation pattern")
    
    return {
        'count': len(hotel_txns),
        'total': sum(t['amount'] for t in hotel_txns),
        'transactions': hotel_txns[:20],
        'hotel_names': dict(hotel_names.most_common(10)),
        'red_flags': red_flags,
    }


def analyze_adult_content(successful):
    """Detect adult content/services purchases."""
    adult_keywords = ['onlyfans', 'fansly', 'chaturbate', 'stripchat', 'pornhub',
                      'adult', 'enchant', 'sex shop', 'adam & eve', 'lovers lane',
                      'tinder', 'bumble', 'hinge', 'grindr', 'seeking',
                      'escort', 'backpage', 'skipthegames', 'megapersonal']
    
    cc = [tx for tx in successful if (tx.product_type or '').upper() == 'CASH_CARD']
    
    adult_txns = []
    adult_merchants = Counter()
    for tx in cc:
        comment = (tx.comment or '').lower()
        for kw in adult_keywords:
            if kw in comment:
                adult_txns.append({
                    'date': tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date),
                    'amount': tx.amount,
                    'merchant': tx.comment,
                    'subject': tx.subject,
                })
                adult_merchants[tx.comment] += 1
                break
    
    red_flags = []
    if len(adult_txns) >= 2:
        total = sum(t['amount'] for t in adult_txns)
        red_flags.append(f"{len(adult_txns)} purchases at adult content/dating platforms totaling ${total:,.2f}")
        merchants = ', '.join(adult_merchants.keys())
        red_flags.append(f"Platforms: {merchants}")
    
    return {
        'count': len(adult_txns),
        'total': sum(t['amount'] for t in adult_txns),
        'transactions': adult_txns[:20],
        'merchants': dict(adult_merchants.most_common(10)),
        'red_flags': red_flags,
    }


def analyze_late_night(transactions):
    """Analyze late night activity (10pm - 5am)."""
    late_night_txns = []
    late_night_comments = []
    
    for tx in transactions:
        if not hasattr(tx.date, 'hour'):
            continue
        hour = tx.date.hour
        if hour >= 22 or hour < 5:
            late_night_txns.append(tx)
            if tx.comment and tx.comment.strip() and tx.comment.strip().lower() != 'nan':
                late_night_comments.append({
                    'time': tx.date.strftime('%I:%M%p') if hasattr(tx.date, 'strftime') else '',
                    'comment': tx.comment.strip(),
                    'amount': tx.amount,
                    'direction': 'IN' if tx.is_incoming() else 'OUT',
                    'product': tx.product_type,
                })
    
    # Flag suspicious late night comments
    suspicious_keywords = ['fun', 'party', 'meet', 'come', 'show', 'head', 'pics', 'pic',
                          'video', 'see', 'visit', 'room', 'hotel', 'skip', 'teaser',
                          'babysitter', 'sitter']
    
    suspicious_late = []
    for c in late_night_comments:
        comment_lower = c['comment'].lower()
        for kw in suspicious_keywords:
            if kw in comment_lower:
                suspicious_late.append(c)
                break
    
    red_flags = []
    if len(late_night_txns) > 20:
        red_flags.append(f"{len(late_night_txns)} transactions between 10pm-5am")
    if suspicious_late:
        red_flags.append(f"{len(suspicious_late)} suspicious late-night comments including: " + 
                        ', '.join(f'"{s["comment"]}" at {s["time"]} (${s["amount"]:.2f})' for s in suspicious_late[:5]))
    
    return {
        'total_late_night': len(late_night_txns),
        'suspicious_comments': suspicious_late[:20],
        'all_comments': late_night_comments[:30],
        'red_flags': red_flags,
    }


def analyze_suspicious_comments(p2p_all):
    """Analyze P2P comments for suspicious patterns."""
    suspicious_terms = {
        'explicit': ['head', 'suck', 'raw', 'pussy', 'dick', 'sex', 'nude', 'nudes', 'naked', 'bj'],
        'meetup': ['meet', 'come over', 'show up', 'pull up', 'room', 'hotel', 'visit'],
        'content': ['pics', 'pic', 'video', 'vid', 'show', 'teaser', 'preview', 'ft'],
        'drug': ['bundle', 'pack', 'za', 'cart', 'plug', 'dispo', 'weed', 'smoke'],
        'coded': ['stuff', 'thing', 'that', 'it', 'usual', 'same', 'regular'],
        'contact': ['hmu', 'hit me up', 'call me', 'text me', 'dm me'],
    }
    
    flagged = defaultdict(list)
    phone_numbers = []
    
    for tx in p2p_all:
        if not tx.comment or tx.comment.strip().lower() == 'nan':
            continue
        comment = tx.comment.strip()
        comment_lower = comment.lower()
        
        # Check for phone numbers
        if re.search(r'\d{10}|\d{3}[-.\s]\d{3}[-.\s]\d{4}', comment):
            phone_numbers.append({
                'comment': comment,
                'amount': tx.amount,
                'direction': 'IN' if tx.is_incoming() else 'OUT',
                'date': tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date),
            })
        
        for category, terms in suspicious_terms.items():
            for term in terms:
                if term in comment_lower:
                    flagged[category].append({
                        'comment': comment,
                        'term': term,
                        'amount': tx.amount,
                        'direction': 'IN' if tx.is_incoming() else 'OUT',
                        'counterparty': tx.counterparty,
                        'date': tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date),
                        'time': tx.date.strftime('%I:%M%p') if hasattr(tx.date, 'strftime') else '',
                    })
                    break
    
    red_flags = []
    for category, items in flagged.items():
        if items:
            samples = ', '.join(f'"{i["comment"]}"' for i in items[:3])
            red_flags.append(f"{len(items)} {category} comments detected: {samples}")
    if phone_numbers:
        red_flags.append(f"{len(phone_numbers)} comments contain phone numbers (contact solicitation)")
    
    return {
        'flagged_by_category': {k: v[:10] for k, v in flagged.items()},
        'phone_numbers': phone_numbers[:10],
        'red_flags': red_flags,
    }


def analyze_cash_pattern(successful):
    """Analyze ATM withdrawals and cash deposits."""
    atm = [tx for tx in successful if (tx.product_subtype or '').upper() == 'ATM_WITHDRAWAL']
    pmd = [tx for tx in successful if 'PAPER_MONEY' in (tx.product_subtype or '').upper() and 'FEE' not in (tx.product_subtype or '').upper()]
    
    atm_total = sum(tx.amount for tx in atm)
    pmd_total = sum(tx.amount for tx in pmd)
    
    red_flags = []
    if atm_total > 5000:
        red_flags.append(f"${atm_total:,.2f} in ATM withdrawals across {len(atm)} transactions — high cash usage")
    if len(atm) > 10:
        # Check for structuring
        atm_amounts = [tx.amount for tx in atm]
        near_limit = [a for a in atm_amounts if 200 <= a <= 500]
        if len(near_limit) > 5:
            red_flags.append(f"{len(near_limit)} ATM withdrawals between $200-$500 — possible structuring")
    
    return {
        'atm_count': len(atm),
        'atm_total': atm_total,
        'pmd_count': len(pmd),
        'pmd_total': pmd_total,
        'atm_locations': Counter((tx.comment or '')[:30] for tx in atm).most_common(10),
        'red_flags': red_flags,
    }


def analyze_merchants(successful):
    """Analyze Cash Card merchant purchases for patterns."""
    cc = [tx for tx in successful if (tx.product_type or '').upper() == 'CASH_CARD']
    merchants = Counter((tx.comment or '').strip() for tx in cc if tx.comment)
    
    return {
        'total_purchases': len(cc),
        'total_amount': sum(tx.amount for tx in cc),
        'unique_merchants': len(merchants),
        'top_merchants': merchants.most_common(20),
        'red_flags': [],
    }


def analyze_counterparties(p2p_all, subjects):
    """Analyze counterparty patterns."""
    from csv_parser import SYSTEM_COUNTERPARTY_TOKENS
    
    cp_data = defaultdict(lambda: {'in_count': 0, 'out_count': 0, 'in_total': 0.0, 'out_total': 0.0, 'comments': [], 'subjects': set()})
    
    for tx in p2p_all:
        if tx.counterparty in SYSTEM_COUNTERPARTY_TOKENS or not tx.has_real_counterparty():
            continue
        cp = cp_data[tx.counterparty]
        cp['subjects'].add(tx.subject)
        if tx.is_incoming():
            cp['in_count'] += 1
            cp['in_total'] += tx.amount
        else:
            cp['out_count'] += 1
            cp['out_total'] += tx.amount
        if tx.comment and tx.comment.strip().lower() != 'nan':
            cp['comments'].append(tx.comment.strip())
    
    # Format for output
    top_cps = sorted(cp_data.items(), key=lambda x: x[1]['in_total'] + x[1]['out_total'], reverse=True)
    
    formatted = []
    for token, data in top_cps[:20]:
        formatted.append({
            'token': token,
            'in_count': data['in_count'],
            'out_count': data['out_count'],
            'in_total': data['in_total'],
            'out_total': data['out_total'],
            'subjects': len(data['subjects']),
            'sample_comments': list(set(data['comments']))[:5],
        })
    
    multi_subject = sum(1 for _, d in cp_data.items() if len(d['subjects']) > 1)
    
    return {
        'total_counterparties': len(cp_data),
        'multi_subject_count': multi_subject,
        'top_counterparties': formatted,
        'red_flags': [f"{multi_subject} counterparties transact with multiple subjects"] if multi_subject > 0 else [],
    }


def analyze_temporal(successful):
    """Analyze time-of-day and day-of-week patterns."""
    hour_counts = Counter()
    dow_counts = Counter()
    dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    for tx in successful:
        if hasattr(tx.date, 'hour'):
            hour_counts[tx.date.hour] += 1
        if hasattr(tx.date, 'weekday'):
            dow_counts[tx.date.weekday()] += 1
    
    # Find peak hours
    peak_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    
    red_flags = []
    late_night_total = sum(hour_counts.get(h, 0) for h in [22, 23, 0, 1, 2, 3, 4])
    if late_night_total > len(successful) * 0.15:
        red_flags.append(f"{late_night_total} transactions ({late_night_total/len(successful)*100:.0f}%) occur between 10pm-5am — unusual activity hours")
    
    return {
        'hour_distribution': dict(hour_counts),
        'dow_distribution': {dow_names[k]: v for k, v in dow_counts.items()},
        'peak_hours': peak_hours,
        'red_flags': red_flags,
    }


def analyze_amounts(p2p_success):
    """Analyze P2P amount patterns."""
    incoming = [tx for tx in p2p_success if tx.is_incoming()]
    outgoing = [tx for tx in p2p_success if tx.is_outgoing()]
    
    in_amounts = [tx.amount for tx in incoming]
    out_amounts = [tx.amount for tx in outgoing]
    
    return {
        'incoming_count': len(incoming),
        'incoming_total': sum(in_amounts),
        'incoming_avg': sum(in_amounts) / len(in_amounts) if in_amounts else 0,
        'outgoing_count': len(outgoing),
        'outgoing_total': sum(out_amounts),
        'outgoing_avg': sum(out_amounts) / len(out_amounts) if out_amounts else 0,
        'red_flags': [],
    }


def analyze_institutional(successful):
    """Detect institutional/correctional facility indicators."""
    institutional_keywords = ['usconnect', 'corporate dining', 'aramark', 'keefe', 
                             'jpay', 'securus', 'global tel', 'icsolutions',
                             'commissary', 'canteen']
    
    cc = [tx for tx in successful if (tx.product_type or '').upper() == 'CASH_CARD']
    
    inst_txns = []
    inst_merchants = Counter()
    for tx in cc:
        comment = (tx.comment or '').lower()
        for kw in institutional_keywords:
            if kw in comment:
                inst_txns.append(tx)
                inst_merchants[tx.comment] += 1
                break
    
    red_flags = []
    if len(inst_txns) > 10:
        total = sum(tx.amount for tx in inst_txns)
        red_flags.append(f"{len(inst_txns)} purchases at institutional/vending merchants totaling ${total:,.2f} — may indicate time in correctional or institutional facility")
    
    return {
        'count': len(inst_txns),
        'total': sum(tx.amount for tx in inst_txns),
        'merchants': dict(inst_merchants.most_common(10)),
        'red_flags': red_flags,
    }


def analyze_drug_indicators(p2p_all, successful):
    """Detect drug-related indicators."""
    drug_terms = ['za', 'zaza', 'cart', 'dispo', 'plug', 'weed', 'bud', 'pack',
                  'bundle', 'smoke', 'gas', 'loud', 'fire', 'tree', 'flower',
                  'edible', 'dab', 'wax', 'percs', 'pills', 'lean', 'xan']
    
    drug_comments = []
    for tx in p2p_all:
        if not tx.comment:
            continue
        comment_lower = tx.comment.strip().lower()
        for term in drug_terms:
            if re.search(r'\b' + re.escape(term) + r'\b', comment_lower):
                drug_comments.append({
                    'comment': tx.comment.strip(),
                    'term': term,
                    'amount': tx.amount,
                    'direction': 'IN' if tx.is_incoming() else 'OUT',
                    'date': tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date),
                })
                break
    
    red_flags = []
    if len(drug_comments) > 5:
        terms = Counter(d['term'] for d in drug_comments)
        red_flags.append(f"{len(drug_comments)} comments with drug-related terms: {dict(terms.most_common(5))}")
    
    return {
        'count': len(drug_comments),
        'comments': drug_comments[:20],
        'red_flags': red_flags,
    }


def analyze_trafficking_indicators(p2p_all, successful):
    """Detect human trafficking / CSAM indicators."""
    # HT indicators: hotels + adult content + late night + multiple subjects + cash
    ht_keywords_comments = ['babysitter', 'sitter', 'watch them', 'watch the kids',
                           'formula', 'diapers', 'wipes']
    
    ht_comments = []
    for tx in p2p_all:
        if not tx.comment:
            continue
        comment_lower = tx.comment.strip().lower()
        for kw in ht_keywords_comments:
            if kw in comment_lower:
                ht_comments.append({
                    'comment': tx.comment.strip(),
                    'keyword': kw,
                    'amount': tx.amount,
                    'time': tx.date.strftime('%I:%M%p') if hasattr(tx.date, 'strftime') else '',
                    'date': tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date),
                })
                break
    
    red_flags = []
    if ht_comments:
        red_flags.append(f"{len(ht_comments)} comments referencing childcare/baby supplies: " +
                        ', '.join(f'"{c["comment"]}" at {c["time"]}' for c in ht_comments[:3]))
    
    return {
        'comments': ht_comments[:20],
        'red_flags': red_flags,
    }


def analyze_digital_content(successful, p2p_all):
    """Detect digital content sales/purchases (potential CSAM/OCSE)."""
    content_keywords_cc = ['onlyfans', 'fansly', 'chaturbate', 'manyvids', 'clips4sale']
    content_keywords_p2p = ['pics', 'pic', 'video', 'vid', 'content', 'preview',
                           'teaser', 'show', 'ft', 'facetime', 'dropbox', 'mega',
                           'camera', '📷', '🤳', '📸', '🎥']
    
    cc = [tx for tx in successful if (tx.product_type or '').upper() == 'CASH_CARD']
    
    cc_content = []
    for tx in cc:
        comment = (tx.comment or '').lower()
        for kw in content_keywords_cc:
            if kw in comment:
                cc_content.append({'merchant': tx.comment, 'amount': tx.amount, 'date': tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date)})
                break
    
    p2p_content = []
    for tx in p2p_all:
        if not tx.comment:
            continue
        comment_lower = tx.comment.strip().lower()
        comment_raw = tx.comment.strip()
        for kw in content_keywords_p2p:
            if kw in comment_lower or kw in comment_raw:
                p2p_content.append({
                    'comment': tx.comment.strip(),
                    'amount': tx.amount,
                    'direction': 'IN' if tx.is_incoming() else 'OUT',
                    'time': tx.date.strftime('%I:%M%p') if hasattr(tx.date, 'strftime') else '',
                    'date': tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date),
                })
                break
    
    red_flags = []
    if cc_content:
        red_flags.append(f"{len(cc_content)} purchases at adult content platforms")
    if p2p_content:
        red_flags.append(f"{len(p2p_content)} P2P comments referencing digital content/media: " +
                        ', '.join(f'"{c["comment"]}" at {c["time"]}' for c in p2p_content[:3]))
    
    return {
        'cc_content': cc_content[:20],
        'p2p_content': p2p_content[:20],
        'red_flags': red_flags,
    }


def format_findings_for_llm(findings):
    """Format the pre-computed findings into a text block for the LLM."""
    lines = []
    lines.append("=" * 60)
    lines.append("PRE-COMPUTED ANALYSIS FINDINGS")
    lines.append("Use these EXACT numbers and details in your report.")
    lines.append("=" * 60)
    
    # Overview
    o = findings['overview']
    lines.append(f"\nOVERVIEW:")
    lines.append(f"  Subjects: {o['subject_count']} — {', '.join(o['subjects'])}")
    lines.append(f"  Transactions: {o['total_transactions']} total ({o['successful']} successful, {o['failed']} failed)")
    lines.append(f"  Date range: {o['date_range'][0][:10]} to {o['date_range'][1][:10]}")
    
    # Red flag summary
    if findings['red_flag_summary']:
        lines.append(f"\nRED FLAGS DETECTED ({len(findings['red_flag_summary'])}):")
        for flag in findings['red_flag_summary']:
            lines.append(f"  ⚠ {flag}")
    
    # Hotel pattern
    h = findings['hotel_pattern']
    if h['count'] > 0:
        lines.append(f"\nHOTEL/MOTEL PURCHASES: {h['count']} transactions, ${h['total']:,.2f}")
        for name, count in h['hotel_names'].items():
            lines.append(f"  {count}x {name}")
    
    # Adult content
    a = findings['adult_content']
    if a['count'] > 0:
        lines.append(f"\nADULT CONTENT/DATING PURCHASES: {a['count']} transactions, ${a['total']:,.2f}")
        for name, count in a['merchants'].items():
            lines.append(f"  {count}x {name}")
    
    # Late night
    ln = findings['late_night']
    if ln['total_late_night'] > 0:
        lines.append(f"\nLATE NIGHT ACTIVITY (10pm-5am): {ln['total_late_night']} transactions")
        if ln['suspicious_comments']:
            lines.append("  Suspicious late-night comments:")
            for c in ln['suspicious_comments'][:10]:
                lines.append(f"    {c['time']} — \"{c['comment']}\" ${c['amount']:.2f} ({c['direction']})")
    
    # Suspicious comments
    sc = findings['suspicious_comments']
    for category, items in sc['flagged_by_category'].items():
        if items:
            lines.append(f"\n{category.upper()} COMMENTS ({len(items)}):")
            for item in items[:5]:
                lines.append(f"  \"{item['comment']}\" — ${item['amount']:.2f} at {item['time']} ({item['direction']})")
    if sc['phone_numbers']:
        lines.append(f"\nPHONE NUMBERS IN COMMENTS ({len(sc['phone_numbers'])}):")
        for pn in sc['phone_numbers'][:5]:
            lines.append(f"  \"{pn['comment']}\" — ${pn['amount']:.2f}")
    
    # Cash pattern
    cp = findings['cash_pattern']
    if cp['atm_count'] > 0:
        lines.append(f"\nATM WITHDRAWALS: {cp['atm_count']} transactions, ${cp['atm_total']:,.2f}")
    if cp['pmd_count'] > 0:
        lines.append(f"PAPER MONEY DEPOSITS: {cp['pmd_count']} transactions, ${cp['pmd_total']:,.2f}")
    
    # Institutional
    inst = findings['institutional_indicators']
    if inst['count'] > 0:
        lines.append(f"\nINSTITUTIONAL/VENDING PURCHASES: {inst['count']} transactions, ${inst['total']:,.2f}")
        for name, count in inst['merchants'].items():
            lines.append(f"  {count}x {name}")
    
    # Drug indicators
    di = findings['drug_indicators']
    if di['count'] > 0:
        lines.append(f"\nDRUG-RELATED COMMENTS: {di['count']}")
        for c in di['comments'][:8]:
            lines.append(f"  \"{c['comment']}\" — ${c['amount']:.2f} ({c['direction']})")
    
    # Trafficking
    ti = findings['trafficking_indicators']
    if ti['comments']:
        lines.append(f"\nTRAFFICKING/CHILDCARE INDICATORS: {len(ti['comments'])}")
        for c in ti['comments'][:5]:
            lines.append(f"  \"{c['comment']}\" at {c['time']} — ${c['amount']:.2f}")
    
    # Digital content
    dc = findings['digital_content_indicators']
    if dc['cc_content'] or dc['p2p_content']:
        lines.append(f"\nDIGITAL CONTENT INDICATORS:")
        if dc['cc_content']:
            lines.append(f"  Cash Card purchases at content platforms: {len(dc['cc_content'])}")
            for c in dc['cc_content'][:5]:
                lines.append(f"    {c['merchant']} — ${c['amount']:.2f}")
        if dc['p2p_content']:
            lines.append(f"  P2P content-related comments: {len(dc['p2p_content'])}")
            for c in dc['p2p_content'][:5]:
                lines.append(f"    \"{c['comment']}\" at {c['time']} — ${c['amount']:.2f} ({c['direction']})")
    
    # Counterparties
    cpa = findings['counterparty_analysis']
    lines.append(f"\nCOUNTERPARTY SUMMARY: {cpa['total_counterparties']} total, {cpa['multi_subject_count']} multi-subject")
    lines.append("TOP COUNTERPARTIES:")
    for cp in cpa['top_counterparties'][:10]:
        total = cp['in_total'] + cp['out_total']
        comments = ', '.join(f'"{c}"' for c in cp['sample_comments'][:3])
        lines.append(f"  {cp['token']}: In ${cp['in_total']:,.2f} ({cp['in_count']}), Out ${cp['out_total']:,.2f} ({cp['out_count']}), Subjects: {cp['subjects']} — {comments}")
    
    # Analyst context
    if findings.get('analyst_context'):
        lines.append(f"\nANALYST-PROVIDED CONTEXT:")
        lines.append(f"  {findings['analyst_context']}")
    
    return '\n'.join(lines)
