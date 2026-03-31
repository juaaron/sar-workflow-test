"""
SAR Platform - Web Server
Connects the UI to the Python analysis engine
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import tempfile
from final_analyzer import FinalAnalyzer
from csv_parser import CSVParser
from narrative_generator import NarrativeGenerator, CaseNotesGenerator

app = Flask(__name__)
CORS(app)  # Enable CORS for local development

# Store last analysis for narrative/case notes generation
last_analysis_raw = None
last_analysis_formatted = None
last_case_id = None
last_transactions_summary = None
last_transactions_raw = None
lab_conversation = []

# Serve the UI
@app.route('/')
def index():
    return send_from_directory('.', 'demo_ui.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Analyze uploaded CSV file
    Returns JSON with analysis results
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.csv', delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            # Parse CSV
            parser = CSVParser()
            transactions = parser.parse(tmp_path)
            
            # Run analysis
            analyzer = FinalAnalyzer(transactions)
            results = analyzer.analyze()
            
            # Format results for UI
            response = format_results_for_ui(results)
            
            # Store for narrative/case notes/chat generation
            global last_analysis_raw, last_analysis_formatted, last_case_id, last_transactions_summary, last_transactions_raw
            last_analysis_raw = results
            last_analysis_formatted = response
            last_case_id = file.filename.replace('.csv', '') if file.filename else ''
            last_transactions_summary = build_transactions_summary(transactions)
            last_transactions_raw = transactions
            
            # Save CSV for Goose copilot access
            global last_csv_path
            persistent_csv = os.path.join(os.path.dirname(__file__), 'last_upload.csv')
            import shutil
            shutil.copy2(tmp_path, persistent_csv)
            last_csv_path = persistent_csv
            
            return jsonify(response)
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/narrative', methods=['GET', 'POST'])
def get_narrative():
    """Generate SAR narrative from last analysis.
    GET: auto-generate with typologies >= 80%
    POST: analyst specifies which typologies to include
    """
    global last_analysis_formatted, last_case_id
    
    if not last_analysis_formatted:
        return jsonify({'error': 'No analysis available. Upload a CSV first.'}), 400
    
    try:
        gen = NarrativeGenerator()
        
        # Check if analyst manually selected typologies
        analysis_data = dict(last_analysis_formatted)
        if request.method == 'POST':
            body = request.json or {}
            included = body.get('included_typologies', None)
            if included is not None:
                analysis_data['_included_typologies'] = included
        
        result = gen.generate_narrative(analysis_data, last_case_id or '')
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/casenotes', methods=['GET'])
def get_case_notes():
    """Generate case notes from last analysis"""
    global last_analysis_formatted, last_case_id
    
    if not last_analysis_formatted:
        return jsonify({'error': 'No analysis available. Upload a CSV first.'}), 400
    
    try:
        gen = CaseNotesGenerator()
        result = gen.generate_case_notes(last_analysis_formatted, last_case_id or '')
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def build_transactions_summary(transactions):
    """Build a detailed transaction summary for the LLM chat context."""
    from collections import Counter, defaultdict
    from csv_parser import SYSTEM_COUNTERPARTY_TOKENS
    
    lines = []
    
    successful = [tx for tx in transactions if tx.is_paid_out()]
    failed = [tx for tx in transactions if tx.is_failed()]
    p2p = [tx for tx in transactions if tx.is_p2p()]
    p2p_success = [tx for tx in p2p if tx.is_paid_out()]
    
    # Subject analysis
    subjects = sorted(set(tx.subject for tx in transactions))
    lines.append(f"SUBJECT ACCOUNTS ({len(subjects)} total):")
    for subj in subjects:
        subj_txns = [tx for tx in transactions if tx.subject == subj]
        subj_success = [tx for tx in subj_txns if tx.is_paid_out()]
        subj_in = [tx for tx in subj_success if tx.is_incoming()]
        subj_out = [tx for tx in subj_success if tx.is_outgoing()]
        lines.append(f"  {subj}: {len(subj_txns)} txns ({len(subj_success)} successful), In: {len(subj_in)} (${sum(tx.amount for tx in subj_in):,.2f}), Out: {len(subj_out)} (${sum(tx.amount for tx in subj_out):,.2f})")
    lines.append('')
    
    # Cross-subject counterparty analysis (counterparties sending to multiple subjects)
    cp_to_subjects = defaultdict(set)
    for tx in transactions:
        if tx.is_incoming() and tx.is_p2p() and tx.counterparty not in SYSTEM_COUNTERPARTY_TOKENS:
            cp_to_subjects[tx.counterparty].add(tx.subject)
    
    multi_subject_cps = {cp: subs for cp, subs in cp_to_subjects.items() if len(subs) > 1}
    if multi_subject_cps:
        lines.append(f"COUNTERPARTIES SENDING TO MULTIPLE SUBJECTS ({len(multi_subject_cps)} found):")
        for cp, subs in sorted(multi_subject_cps.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
            cp_txns = [tx for tx in transactions if tx.counterparty == cp and tx.is_incoming() and tx.is_p2p()]
            total = sum(tx.amount for tx in cp_txns)
            lines.append(f"  {cp}: sends to {len(subs)} subjects ({', '.join(sorted(subs))}), {len(cp_txns)} txns, ${total:,.2f}")
        lines.append('')
    
    # Top counterparties
    cp_data = defaultdict(lambda: {'in_count': 0, 'out_count': 0, 'in_total': 0.0, 'out_total': 0.0, 'comments': []})
    for tx in p2p:
        if tx.counterparty in SYSTEM_COUNTERPARTY_TOKENS:
            continue
        cp = cp_data[tx.counterparty]
        if tx.is_incoming():
            cp['in_count'] += 1
            cp['in_total'] += tx.amount
        else:
            cp['out_count'] += 1
            cp['out_total'] += tx.amount
        if tx.comment and tx.comment.strip():
            cp['comments'].append(tx.comment.strip())
    
    # Sort by total volume
    sorted_cps = sorted(cp_data.items(), key=lambda x: x[1]['in_total'] + x[1]['out_total'], reverse=True)
    
    lines.append(f"TOP 20 COUNTERPARTIES:")
    for cp_token, data in sorted_cps[:20]:
        total = data['in_total'] + data['out_total']
        total_count = data['in_count'] + data['out_count']
        sample_comments = list(set(data['comments']))[:5]
        comments_str = ', '.join(f'"{c}"' for c in sample_comments) if sample_comments else 'no comments'
        lines.append(f"  {cp_token}: {total_count} txns (In: {data['in_count']} ${data['in_total']:,.2f}, Out: {data['out_count']} ${data['out_total']:,.2f}) Comments: {comments_str}")
    
    # All unique comments with frequency
    all_comments = Counter()
    for tx in p2p:
        if tx.comment and tx.comment.strip() and tx.comment.strip().lower() != 'nan':
            all_comments[tx.comment.strip()] += 1
    
    lines.append(f"\nALL P2P COMMENTS (by frequency):")
    for comment, count in all_comments.most_common(50):
        lines.append(f"  {count}x \"{comment}\"")
    
    # Product breakdown
    product_counts = Counter()
    for tx in successful:
        label = f"{tx.product_type}/{tx.product_subtype}" if tx.product_subtype else tx.product_type
        product_counts[label] += 1
    
    lines.append(f"\nPRODUCT BREAKDOWN (successful):")
    for product, count in product_counts.most_common():
        total = sum(tx.amount for tx in successful if (f"{tx.product_type}/{tx.product_subtype}" if tx.product_subtype else tx.product_type) == product)
        lines.append(f"  {count}x {product} — ${total:,.2f}")
    
    # Amount distribution for incoming P2P
    incoming_p2p = [tx for tx in p2p_success if tx.is_incoming()]
    if incoming_p2p:
        amounts = [tx.amount for tx in incoming_p2p]
        lines.append(f"\nINCOMING P2P AMOUNT DISTRIBUTION:")
        lines.append(f"  Range: ${min(amounts):.2f} - ${max(amounts):.2f}")
        lines.append(f"  Average: ${sum(amounts)/len(amounts):.2f}")
        ranges = [(1,10),(11,25),(26,50),(51,100),(101,200),(201,500),(501,99999)]
        for lo, hi in ranges:
            count = sum(1 for a in amounts if lo <= a <= hi)
            if count > 0:
                lines.append(f"  ${lo}-${hi}: {count} transactions")
    
    # Top incoming senders specifically
    incoming_senders = sorted(
        [(cp, d) for cp, d in cp_data.items() if d['in_count'] > 0],
        key=lambda x: x[1]['in_total'], reverse=True
    )
    lines.append(f"\nTOP 15 INCOMING SENDERS:")
    for cp_token, data in incoming_senders[:15]:
        sample = list(set(data['comments']))[:3]
        comments_str = ', '.join(f'"{c}"' for c in sample) if sample else 'no comments'
        lines.append(f"  {cp_token}: {data['in_count']} payments, ${data['in_total']:,.2f} — {comments_str}")
    
    # Top outgoing recipients
    outgoing_recipients = sorted(
        [(cp, d) for cp, d in cp_data.items() if d['out_count'] > 0],
        key=lambda x: x[1]['out_total'], reverse=True
    )
    if outgoing_recipients:
        lines.append(f"\nTOP 15 OUTGOING RECIPIENTS:")
        for cp_token, data in outgoing_recipients[:15]:
            sample = list(set(data['comments']))[:3]
            comments_str = ', '.join(f'"{c}"' for c in sample) if sample else 'no comments'
            lines.append(f"  {cp_token}: {data['out_count']} payments, ${data['out_total']:,.2f} — {comments_str}")
    
    # Raw transaction list (every P2P transaction — the LLM needs this to answer specific questions)
    # Limit to 500 most recent to stay within token limits
    lines.append(f"\n{'='*40}")
    lines.append(f"RAW P2P TRANSACTION LOG ({len(p2p)} total, showing up to 500):")
    lines.append(f"{'='*40}")
    lines.append(f"{'Date':<22} {'Dir':>3} {'Status':<10} {'Amount':>10} {'Counterparty':<20} Comment")
    lines.append(f"{'-'*22} {'-'*3} {'-'*10} {'-'*10} {'-'*20} {'-'*30}")
    
    sorted_p2p = sorted(p2p, key=lambda tx: tx.date, reverse=True)
    for tx in sorted_p2p[:500]:
        date_str = tx.date.strftime('%Y-%m-%d %H:%M') if hasattr(tx.date, 'strftime') else str(tx.date)[:16]
        direction = 'IN' if tx.is_incoming() else 'OUT'
        status = 'OK' if tx.is_paid_out() else 'FAIL'
        comment = (tx.comment or '')[:40]
        cp = (tx.counterparty or '')[:20]
        lines.append(f"{date_str:<22} {direction:>3} {status:<10} ${tx.amount:>9.2f} {cp:<20} {comment}")
    
    # Also include non-P2P transactions (Cash Card, Transfers, ATM)
    non_p2p = [tx for tx in transactions if not tx.is_p2p() and tx.is_paid_out()]
    if non_p2p:
        lines.append(f"\nNON-P2P TRANSACTIONS ({len(non_p2p)} successful):")
        lines.append(f"{'Date':<22} {'Dir':>3} {'Product':<25} {'Amount':>10} Comment")
        lines.append(f"{'-'*22} {'-'*3} {'-'*25} {'-'*10} {'-'*30}")
        
        sorted_nonp2p = sorted(non_p2p, key=lambda tx: tx.date, reverse=True)
        for tx in sorted_nonp2p[:200]:
            date_str = tx.date.strftime('%Y-%m-%d %H:%M') if hasattr(tx.date, 'strftime') else str(tx.date)[:16]
            direction = 'IN' if tx.is_incoming() else 'OUT'
            product = f"{tx.product_type}/{tx.product_subtype}"[:25]
            comment = (tx.comment or '')[:40]
            lines.append(f"{date_str:<22} {direction:>3} {product:<25} ${tx.amount:>9.2f} {comment}")
    
    # Time-of-day analysis
    from collections import defaultdict as dd2
    hour_counts = dd2(int)
    for tx in p2p_success:
        if hasattr(tx.date, 'hour'):
            hour_counts[tx.date.hour] += 1
    
    if hour_counts:
        lines.append(f"\nTRANSACTION TIME-OF-DAY (successful P2P):")
        for hour in sorted(hour_counts.keys()):
            bar = '█' * min(hour_counts[hour], 50)
            period = 'AM' if hour < 12 else 'PM'
            display_hour = hour if hour <= 12 else hour - 12
            if display_hour == 0: display_hour = 12
            lines.append(f"  {display_hour:>2}{period}: {hour_counts[hour]:>4} txns {bar}")
    
    # Day-of-week analysis
    dow_counts = dd2(int)
    dow_names = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    for tx in p2p_success:
        if hasattr(tx.date, 'weekday'):
            dow_counts[tx.date.weekday()] += 1
    
    if dow_counts:
        lines.append(f"\nTRANSACTION DAY-OF-WEEK (successful P2P):")
        for dow in range(7):
            bar = '█' * min(dow_counts[dow], 50)
            lines.append(f"  {dow_names[dow]}: {dow_counts[dow]:>4} txns {bar}")
    
    return '\n'.join(lines)


def format_results_for_ui(results):
    """
    Format analysis results for the UI
    """
    stats = results['basic_stats']
    patterns = results.get('patterns', {})
    comments = results.get('comments', {})
    cps = results.get('counterparties', {})
    
    # Determine which typologies are high-confidence (>=80%)
    # Only show comments relevant to those typologies
    high_conf_typologies = set()
    for typ_name, typ_data in results.get('detected_typologies', {}).items():
        if typ_data['confidence'] >= 0.80:
            high_conf_typologies.add(typ_name)
    
    # Map typology names to comment term types
    # drug terms = 'text', 'emoji'  |  gambling terms = 'gambling_platform', 'gambling_term', 'gambling_username'
    show_drug_comments = any(t in high_conf_typologies for t in ('Illegal Drug Sales', 'Money Laundering', 'Pass-Through Money Laundering'))
    show_gambling_comments = 'Gambling Facilitation' in high_conf_typologies
    show_adult_comments = 'Adult Services' in high_conf_typologies
    # If nothing is high-confidence, show everything (don't hide all comments)
    show_all = not high_conf_typologies
    
    # Format detected typologies
    typologies = []
    if results.get('detected_typologies'):
        for typ_name, typ_data in results['detected_typologies'].items():
            # Enrich each indicator with drill-down details where possible
            raw_indicators = typ_data.get('primary_indicators', [])
            enriched_typ_indicators = []
            
            for ind_text in raw_indicators:
                details = []
                ind_lower = ind_text.lower() if isinstance(ind_text, str) else ''
                
                # Add relevant drill-down details based on indicator content
                if 'gambling' in ind_lower and 'comment' in ind_lower or 'username' in ind_lower:
                    # Show sample gambling comments/usernames
                    gambling_details = typ_data.get('details', {})
                    flagged = gambling_details.get('facilitation', {}).get('facilitation_txns', []) if isinstance(gambling_details, dict) else []
                    for f in flagged[:8]:
                        if isinstance(f, dict):
                            details.append(f'"{f.get("comment","")}" — ${f.get("amount",0):,.2f} from {f.get("counterparty","")}')
                
                elif 'explicit' in ind_lower or 'sexual' in ind_lower or 'content' in ind_lower or 'meetup' in ind_lower or 'emoji' in ind_lower:
                    # Show sample adult services comments
                    adult_details = typ_data.get('details', {})
                    flagged = adult_details.get('flagged_comments', []) if isinstance(adult_details, dict) else []
                    for f in flagged[:8]:
                        if isinstance(f, dict):
                            cats = ', '.join(f.get('categories', []))
                            details.append(f'"{f.get("comment","")}" — ${f.get("amount",0):,.2f} [{cats}]')
                
                elif 'high-confidence' in ind_lower or 'suspicious comment' in ind_lower:
                    # Show sample comments from comment analysis
                    for c in comments.get('high_confidence_samples', [])[:8]:
                        terms = ', '.join([d['term'] for d in c.get('detected_terms', [])[:3]])
                        details.append(f'"{c["comment"]}" → {terms}')
                
                elif 'counterpart' in ind_lower or 'sender' in ind_lower:
                    # Show top counterparties
                    for cp_data_item in cps.get('top_counterparties', [])[:6]:
                        details.append(f"{cp_data_item['counterparty']} — {cp_data_item['total_transactions']} txns, ${cp_data_item['incoming_total'] + cp_data_item['outgoing_total']:,.2f}")
                
                elif 'round dollar' in ind_lower:
                    for cp_data_item in cps.get('top_counterparties', [])[:5]:
                        details.append(f"{cp_data_item['counterparty']} — {cp_data_item['total_transactions']} txns, ${cp_data_item['incoming_total'] + cp_data_item['outgoing_total']:,.2f}")
                
                enriched_typ_indicators.append({
                    'text': ind_text,
                    'details': details
                })
            
            typologies.append({
                'name': typ_name,
                'confidence': typ_data['confidence'] * 100,
                'indicators': enriched_typ_indicators
            })
    
    # Sort by confidence
    typologies.sort(key=lambda x: x['confidence'], reverse=True)
    
    # Format sample comments (deduplicated, filtered by relevant typology)
    sample_comments = []
    seen_comments = set()
    if comments.get('high_confidence_samples'):
        for c in comments['high_confidence_samples']:
            comment_text = c['comment'].strip().lower()
            if comment_text in seen_comments:
                continue
            
            # Filter: only show comments relevant to high-confidence typologies
            if not show_all:
                term_types = [d.get('type', '') for d in c.get('detected_terms', [])]
                has_drug = any(t in ('text', 'emoji') for t in term_types)
                has_gambling = any('gambling' in t for t in term_types)
                has_adult = any('adult' in t for t in term_types)
                
                if has_drug and not show_drug_comments and not has_gambling and not has_adult:
                    continue
                if has_gambling and not show_gambling_comments and not has_drug and not has_adult:
                    continue
                if has_adult and not show_adult_comments and not has_drug and not has_gambling:
                    continue
            
            seen_comments.add(comment_text)
            terms = [d['term'] for d in c['detected_terms'][:3]]
            sample_comments.append({
                'comment': c['comment'],
                'terms': ', '.join(terms),
                'confidence': c['confidence'] * 100
            })
            if len(sample_comments) >= 10:
                break
    
    # Format top counterparties
    top_cps = []
    if cps.get('top_counterparties'):
        for cp in cps['top_counterparties'][:5]:
            pattern_type = 'Incoming Only' if cp['outgoing_count'] == 0 else \
                          'Outgoing Only' if cp['incoming_count'] == 0 else \
                          'Bidirectional'
            
            top_cps.append({
                'token': cp['counterparty'],
                'total_txs': cp['total_transactions'],
                'incoming_total': cp['incoming_total'],
                'outgoing_total': cp['outgoing_total'],
                'pattern': pattern_type
            })
    
    # Build response (NO SAR RECOMMENDATIONS - analysis only)
    response = {
        'success': True,
        'analysis_summary': {
            'suspicious_activity_detected': results.get('suspicious_activity_detected', False),
            'final_recommendation': results.get('final_recommendation', 'Unknown'),
            'primary_typology': results.get('primary_typology', 'Unknown'),
            'primary_confidence': results.get('primary_confidence', 0) * 100
        },
        'typologies': typologies,
        'stats': {
            'total_transactions': stats.get('total_transactions', 0),
            'successful_transactions': stats.get('successful_transactions', 0),
            'incoming_attempts': stats.get('incoming_attempts', 0),
            'outgoing_attempts': stats.get('outgoing_attempts', 0),
            'incoming_paid_count': stats.get('incoming_paid_count', 0),
            'outgoing_paid_count': stats.get('outgoing_paid_count', 0),
            'incoming_total': stats.get('incoming_total', 0),
            'outgoing_total': stats.get('outgoing_total', 0),
            'net_flow': stats.get('net_flow', 0),
            'unique_counterparties': stats.get('unique_counterparties', 0),
            'subject_count': stats.get('subject_count', 1),
            'subject_tokens': stats.get('subject_tokens', []),
            'p2p_count': stats.get('p2p_count', 0),
            'incoming_attempted_total': stats.get('incoming_attempted_total', 0),
            'outgoing_attempted_total': stats.get('outgoing_attempted_total', 0),
            'p2p_attempted_count': stats.get('p2p_attempted_count', 0),
            'p2p_attempted_total': stats.get('p2p_attempted_total', 0),
            'subject': results.get('subject', ''),
            'date_range': [
                str(stats['date_range'][0]) if stats.get('date_range') else '',
                str(stats['date_range'][1]) if stats.get('date_range') else '',
            ] if stats.get('date_range') else None,
            'inflow_breakdown': [
                {'label': label, 'count': data['count'], 'total': data['total'], 'avg': data['avg']}
                for label, data in stats.get('inflow_breakdown', [])
            ],
            'outflow_breakdown': [
                {'label': label, 'count': data['count'], 'total': data['total'], 'avg': data['avg']}
                for label, data in stats.get('outflow_breakdown', [])
            ],
            'inflow_attempted_breakdown': [
                {'label': label, 'count': data['count'], 'total': data['total'], 'avg': data['avg']}
                for label, data in stats.get('inflow_attempted_breakdown', [])
            ],
            'outflow_attempted_breakdown': [
                {'label': label, 'count': data['count'], 'total': data['total'], 'avg': data['avg']}
                for label, data in stats.get('outflow_attempted_breakdown', [])
            ],
        },
        'patterns': {
            'round_dollar_pct': patterns.get('round_dollar_pct', 0),
            'under_100_pct': patterns.get('under_100_pct', 0),
            'average_amount': patterns.get('average_amount', 0),
            'incoming_pct': patterns.get('incoming_pct', 0),
            'product_patterns': patterns.get('product_patterns', {}),
        },
        'comments': {
            'total': comments.get('total_comments', 0),
            'high_confidence_count': comments.get('high_confidence_count', 0),
            'samples': sample_comments
        },
        'counterparties': {
            'total': cps.get('total_counterparties', 0),
            'high_velocity_count': cps.get('high_velocity_count', 0),
            'top': top_cps
        },
        'legitimacy': {
            'is_legitimate': results.get('legitimacy', {}).get('is_legitimate', False),
            'confidence': results.get('legitimacy', {}).get('confidence', 0) * 100,
            'business_count': results.get('legitimacy', {}).get('business_count', 0)
        },
        'indicators': []
    }
    
    # Add gambling participation data if present
    if results.get('gambling_classification') == 'participation':
        gp = results.get('gambling_participation', {})
        response['gambling_participation'] = {
            'detected': True,
            'purchases': gp.get('purchases', 0),
            'total_spent': gp.get('total_spent', 0),
            'platforms': gp.get('platforms', []),
            'p2p_risk': gp.get('p2p_risk', 'unknown'),
            'p2p_details': gp.get('p2p_details', [])
        }
        # Add gambling participation indicators
        response['indicators'].append(f"Gambling PARTICIPATION detected: {gp.get('purchases', 0)} Cash Card purchases at gambling sites (${gp.get('total_spent', 0):,.2f})")
        response['indicators'].append(f"P2P risk: {gp.get('p2p_risk', 'unknown').upper()} — appears to be personal/family activity")
        response['indicators'].append("No gambling facilitation pattern detected")
    
    # Build enriched indicator list with drill-down details
    # Each indicator is now { text, details[] } where details are sample transactions/accounts
    enriched_indicators = []
    
    if patterns.get('round_dollar_pct', 0) > 50:
        # Get sample round-dollar transactions
        round_samples = []
        for cp_data in cps.get('top_counterparties', [])[:5]:
            round_samples.append(f"{cp_data['counterparty']} — {cp_data['total_transactions']} txns, ${cp_data['incoming_total'] + cp_data['outgoing_total']:,.2f} total")
        enriched_indicators.append({
            'text': f"{patterns['round_dollar_pct']:.1f}% round dollar amounts",
            'details': round_samples if round_samples else ['Round dollar amounts detected across multiple counterparties']
        })
    
    if comments.get('high_confidence_count', 0) > 0:
        comment_details = []
        seen_drill = set()
        for c in comments.get('high_confidence_samples', []):
            comment_text = c['comment'].strip().lower()
            if comment_text in seen_drill:
                continue
            
            # Same typology-relevance filter as sample comments
            if not show_all:
                term_types = [d.get('type', '') for d in c.get('detected_terms', [])]
                has_drug = any(t in ('text', 'emoji') for t in term_types)
                has_gambling = any('gambling' in t for t in term_types)
                has_adult = any('adult' in t for t in term_types)
                if has_drug and not show_drug_comments and not has_gambling and not has_adult:
                    continue
                if has_gambling and not show_gambling_comments and not has_drug and not has_adult:
                    continue
                if has_adult and not show_adult_comments and not has_drug and not has_gambling:
                    continue
            
            seen_drill.add(comment_text)
            terms = ', '.join([d['term'] for d in c.get('detected_terms', [])[:3]])
            comment_details.append(f'"{c["comment"]}" → {terms} (confidence: {c["confidence"]*100:.0f}%)')
            if len(comment_details) >= 12:
                break
        enriched_indicators.append({
            'text': f"{comments['high_confidence_count']} high-confidence suspicious comments",
            'details': comment_details if comment_details else ['Suspicious comments detected']
        })
    
    if patterns.get('under_100_pct', 0) > 80:
        enriched_indicators.append({
            'text': f"{patterns['under_100_pct']:.1f}% transactions under $100",
            'details': [
                f"Average transaction amount: ${patterns.get('average_amount', 0):.2f}",
                f"Total transactions analyzed: {stats.get('total_transactions', 0):,}",
                f"Incoming average: ${stats.get('incoming_total', 0) / max(stats.get('incoming_attempts', 1), 1):.2f}",
                f"Outgoing average: ${stats.get('outgoing_total', 0) / max(stats.get('outgoing_attempts', 1), 1):.2f}"
            ]
        })
    
    if cps.get('high_velocity_count', 0) > 0:
        hv_details = []
        for cp_data in cps.get('top_counterparties', [])[:8]:
            if cp_data['total_transactions'] >= 10:
                direction = 'Incoming' if cp_data['outgoing_count'] == 0 else 'Outgoing' if cp_data['incoming_count'] == 0 else 'Bidirectional'
                hv_details.append(f"{cp_data['counterparty']} — {cp_data['total_transactions']} txns, ${cp_data['incoming_total'] + cp_data['outgoing_total']:,.2f} ({direction})")
        enriched_indicators.append({
            'text': f"{cps['high_velocity_count']} high-velocity counterparties (10+ transactions)",
            'details': hv_details if hv_details else ['Multiple counterparties with 10+ transactions']
        })
    
    if patterns.get('incoming_pct', 0) > 60:
        enriched_indicators.append({
            'text': f"{patterns['incoming_pct']:.1f}% incoming (many-to-one pattern)",
            'details': [
                f"Incoming: {stats.get('incoming_attempts', 0):,} transactions (${stats.get('incoming_total', 0):,.2f})",
                f"Outgoing: {stats.get('outgoing_attempts', 0):,} transactions (${stats.get('outgoing_total', 0):,.2f})",
                f"Ratio: {stats.get('incoming_attempts', 0) / max(stats.get('outgoing_attempts', 1), 1):.1f}:1 incoming to outgoing",
                f"Unique counterparties: {stats.get('unique_counterparties', 0):,}"
            ]
        })
    
    # Add gambling participation indicators if present
    if results.get('gambling_classification') == 'participation':
        gp = results.get('gambling_participation', {})
        enriched_indicators.insert(0, {
            'text': f"Gambling PARTICIPATION detected: {gp.get('purchases', 0)} Cash Card purchases (${gp.get('total_spent', 0):,.2f})",
            'details': gp.get('p2p_details', []) + ['No gambling facilitation pattern detected']
        })
    
    response['indicators'] = enriched_indicators
    
    # Build enriched network data with drill-down details
    network_details = {}
    
    # Total counterparties detail
    cp_list = cps.get('top_counterparties', [])
    network_details['total_counterparties'] = {
        'value': cps.get('total_counterparties', 0),
        'details': [f"{cp['counterparty']} — {cp['total_transactions']} txns, In: ${cp['incoming_total']:,.2f}, Out: ${cp['outgoing_total']:,.2f}" for cp in cp_list[:10]]
    }
    
    # High velocity detail
    hv_cps = [cp for cp in cp_list if cp['total_transactions'] >= 10]
    network_details['high_velocity'] = {
        'value': cps.get('high_velocity_count', 0),
        'details': [f"{cp['counterparty']} — {cp['total_transactions']} txns, ${cp['incoming_total'] + cp['outgoing_total']:,.2f}" for cp in hv_cps[:10]]
    }
    
    # Avg txns per CP
    total_cps = cps.get('total_counterparties', 0)
    total_txns = stats.get('total_transactions', 0)
    avg_per_cp = total_txns / max(total_cps, 1)
    network_details['avg_txns_per_cp'] = {
        'value': round(avg_per_cp, 1),
        'details': [
            f"Total transactions: {total_txns:,}",
            f"Unique counterparties: {total_cps:,}",
            f"Top CP: {cp_list[0]['counterparty']} ({cp_list[0]['total_transactions']} txns)" if cp_list else 'No counterparties'
        ]
    }
    
    # Network density
    hv_count = cps.get('high_velocity_count', 0)
    density = (hv_count / max(total_cps, 1)) * 100
    network_details['density'] = {
        'value': round(density, 1),
        'details': [
            f"{hv_count} counterparties with 10+ transactions",
            f"{total_cps} total counterparties",
            f"Density: {density:.1f}% are high-velocity"
        ]
    }
    
    # Flow pattern
    in_count = stats.get('incoming_attempts', 0)
    out_count = stats.get('outgoing_attempts', 0)
    in_ratio = (in_count / max(in_count + out_count, 1)) * 100
    if in_ratio > 70:
        flow = 'Many-to-One'
    elif in_ratio < 30:
        flow = 'One-to-Many'
    else:
        flow = 'Bidirectional'
    
    # Get top incoming and outgoing CPs
    incoming_cps = sorted(cp_list, key=lambda x: x['incoming_total'], reverse=True)[:5]
    outgoing_cps = sorted(cp_list, key=lambda x: x['outgoing_total'], reverse=True)[:5]
    flow_details = [f"Pattern: {flow} ({in_ratio:.1f}% incoming)"]
    flow_details += [f"Top incoming: {cp['counterparty']} (${cp['incoming_total']:,.2f})" for cp in incoming_cps[:3] if cp['incoming_total'] > 0]
    flow_details += [f"Top outgoing: {cp['counterparty']} (${cp['outgoing_total']:,.2f})" for cp in outgoing_cps[:3] if cp['outgoing_total'] > 0]
    
    network_details['flow_pattern'] = {
        'value': flow,
        'details': flow_details
    }
    
    response['network_details'] = network_details
    
    return response


# ── LLM CHAT ──
from openai import OpenAI

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'your-api-key-here')
openai_client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """You are SAR Workflow Test's AI assistant, built into the SAR Workflow Test platform at Block/Cash App. You help compliance analysts investigate suspicious activity in Cash App transaction data.

You have deep knowledge of:
- BSA/AML regulations and SAR filing requirements
- Cash App transaction types: P2P payments, Cash Card purchases, ATM withdrawals, funds transfers, paper money deposits
- Suspicious activity typologies: Drug Sales, Money Laundering, Gambling Facilitation, Gambling Participation, Adult Services/IPSS, Pass-Through ML, Legitimate Business
- Block's SAR narrative writing style and Cash App investigation note format
- FinCEN reporting requirements

Key compliance rules you follow:
- You provide ANALYSIS ONLY. You never make SAR filing recommendations — that decision belongs to compliance officers.
- You use the word "Potential" not "Suspicious" when describing detected activity (to avoid triggering regulatory clocks).
- You understand the difference between gambling FACILITATION (SAR-worthy: many people sending money to subject to gamble on their behalf) and gambling PARTICIPATION (not SAR-worthy: subject gambling with their own money).
- You understand that "gas" and "food" are ambiguous terms that may or may not indicate drug sales depending on context.
- All attempted transactions should be included in SAR suspicious totals, not just successful ones.

When an analyst asks you to help with a narrative or case notes, match this style:
- Opening: "Block, Inc. ("Block") is filing a Suspicious Activity Report ("SAR") #[case] for activity indicative of [typology] on the Cash App platform."
- Use formal compliance language
- Quote specific payment comments as evidence
- Describe flow patterns (many-to-one, layering, etc.)
- Reference transaction counts, amounts, and date ranges with precision
- Sections analysts must complete should be marked with [ANALYST: description]

You have FULL ACCESS to the current case's transaction data, including:
- Every P2P transaction (date, time, direction, amount, counterparty, comment, status)
- Every Cash Card purchase, ATM withdrawal, and funds transfer
- Counterparty details (transaction counts, amounts, comments per counterparty)
- Time-of-day and day-of-week patterns
- Amount distributions and product breakdowns

When an analyst asks about specific transactions, counterparties, patterns, or data — you CAN answer because you have the raw data. Search through the transaction log provided in your context. Be specific with dates, amounts, and counterparty tokens.

You can also analyze patterns that SAR Workflow Test's automated detectors may not cover, such as:
- Unusual timing patterns (late night activity, weekend spikes)
- Specific counterparty relationships and transaction histories
- Novel typologies not yet built into SAR Workflow Test's detection engine
- Cross-referencing comments across different counterparties
- Identifying potential structuring or layering patterns

HOW YOU RESPOND:
- Lead with the answer in plain English, then provide a few sentences of supporting detail.
- Use exact numbers naturally: "$172,644 across 394 transactions" — never show raw data, DataFrames, or code output.
- Give enough context to be useful — explain why a finding matters or what it could indicate.
- When you spot something interesting, flag it and connect the dots.
- Think like a senior investigator briefing their team — clear, precise, informative.
- Never explain your process. Never say "Let me analyze" or "I'll run the data."
- No filler phrases like "I'd be happy to help" or "Great question."
- Your context includes PRE-COMPUTED ANALYSIS with exact numbers. Use those numbers directly — do not guess or approximate.

You speak like an experienced BSA/AML investigator."""

chat_history = []

# Copilot backend: 'goose' or 'openai'
COPILOT_BACKEND = 'openai'
last_csv_path = None  # Store path to last uploaded CSV for Goose

@app.route('/network', methods=['GET'])
def get_network():
    """Return network graph data for D3.js visualization"""
    global last_transactions_raw, last_case_id
    
    if not last_transactions_raw:
        return jsonify({'error': 'No analysis available. Upload a CSV first.'}), 400
    
    try:
        from collections import defaultdict
        from csv_parser import SYSTEM_COUNTERPARTY_TOKENS
        
        nodes = {}
        edges = []
        
        # Build nodes and edges from P2P transactions (successful only)
        p2p = [tx for tx in last_transactions_raw if tx.is_p2p() and tx.is_paid_out()]
        
        # Collect all subjects
        subjects = set(tx.subject for tx in last_transactions_raw)
        for subj in subjects:
            nodes[subj] = {'id': subj, 'type': 'subject', 'in_total': 0, 'out_total': 0, 'txn_count': 0, 'subjects_connected': 0}
        
        # Collect counterparty data
        cp_data = defaultdict(lambda: {'in_total': 0, 'out_total': 0, 'txn_count': 0, 'subjects': set(), 'comments': []})
        
        for tx in p2p:
            if not tx.has_real_counterparty():
                continue
            
            cp = cp_data[tx.counterparty]
            cp['txn_count'] += 1
            cp['subjects'].add(tx.subject)
            
            if tx.is_incoming():
                cp['in_total'] += tx.amount
                if tx.counterparty in nodes:
                    nodes[tx.counterparty]['in_total'] += tx.amount
            else:
                cp['out_total'] += tx.amount
                if tx.counterparty in nodes:
                    nodes[tx.counterparty]['out_total'] += tx.amount
            
            if tx.comment and tx.comment.strip() and tx.comment != 'nan':
                cp['comments'].append(tx.comment.strip())
        
        # Only include top counterparties (by total volume) to keep graph readable
        sorted_cps = sorted(cp_data.items(), key=lambda x: x[1]['in_total'] + x[1]['out_total'], reverse=True)
        max_nodes = 50  # Limit for readability
        
        for cp_token, data in sorted_cps[:max_nodes]:
            multi = len(data['subjects']) > 1
            nodes[cp_token] = {
                'id': cp_token,
                'type': 'counterparty',
                'in_total': data['in_total'],
                'out_total': data['out_total'],
                'txn_count': data['txn_count'],
                'subjects_connected': len(data['subjects']),
                'multi_subject': multi,
                'sample_comments': list(set(data['comments']))[:5],
            }
            
            # Build edges to each subject
            for subj in data['subjects']:
                # Calculate per-subject amounts
                subj_txns = [tx for tx in p2p if tx.counterparty == cp_token and tx.subject == subj and tx.has_real_counterparty()]
                in_amt = sum(tx.amount for tx in subj_txns if tx.is_incoming())
                out_amt = sum(tx.amount for tx in subj_txns if tx.is_outgoing())
                count = len(subj_txns)
                
                if in_amt > 0:
                    edges.append({
                        'source': cp_token,
                        'target': subj,
                        'amount': in_amt,
                        'count': sum(1 for tx in subj_txns if tx.is_incoming()),
                        'direction': 'incoming',
                    })
                if out_amt > 0:
                    edges.append({
                        'source': subj,
                        'target': cp_token,
                        'amount': out_amt,
                        'count': sum(1 for tx in subj_txns if tx.is_outgoing()),
                        'direction': 'outgoing',
                    })
        
        # Build timeline for time filtering
        net_timeline = []
        for tx in p2p:
            if not tx.has_real_counterparty():
                continue
            date_str = tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date)
            net_timeline.append({
                'date': date_str,
                'source': tx.counterparty if tx.is_incoming() else tx.subject,
                'target': tx.subject if tx.is_incoming() else tx.counterparty,
                'amount': tx.amount,
                'direction': 'incoming' if tx.is_incoming() else 'outgoing',
            })
        net_timeline.sort(key=lambda x: x['date'])
        
        dates = [t['date'] for t in net_timeline]
        
        return jsonify({
            'nodes': list(nodes.values()),
            'edges': edges,
            'subjects': list(subjects),
            'case_id': last_case_id or '',
            'timeline': net_timeline,
            'date_range': [dates[0] if dates else '', dates[-1] if dates else ''],
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/sankey', methods=['GET'])
def get_sankey():
    """Return Sankey diagram data with inter-subject flow detection.
    
    Layers:
    0: External counterparties (source of funds)
    1: Receiving subjects (first layer of subjects who receive from external CPs)
    2: Forwarding subjects (subjects who receive from other subjects — layering)
    3: Exit methods (cash out, transfers, purchases)
    """
    global last_transactions_raw, last_case_id
    
    if not last_transactions_raw:
        return jsonify({'error': 'No analysis available. Upload a CSV first.'}), 400
    
    try:
        from collections import defaultdict
        from csv_parser import SYSTEM_COUNTERPARTY_TOKENS
        
        successful = [tx for tx in last_transactions_raw if tx.is_paid_out()]
        subjects = set(tx.subject for tx in last_transactions_raw)
        subject_list = sorted(subjects)
        max_cps = int(request.args.get('max_cps', 25))
        
        # Detect inter-subject P2P flows (Subject A sends to Subject B)
        # A counterparty that is ALSO a subject = inter-subject flow
        inter_subject_flows = defaultdict(lambda: defaultdict(float))
        
        for tx in successful:
            if tx.is_p2p() and tx.is_incoming():
                # If the counterparty is another subject in this case
                if tx.counterparty in subjects and tx.counterparty != tx.subject:
                    inter_subject_flows[tx.counterparty][tx.subject] += tx.amount
        
        # Determine subject layers based on flow
        # Subjects that ONLY receive from external CPs = layer 1 (receivers)
        # Subjects that receive from other subjects = layer 2 (forwarders)
        # Subjects can appear in both if they receive from both external and internal
        subjects_receiving_from_subjects = set()
        subjects_sending_to_subjects = set()
        for sender, recipients in inter_subject_flows.items():
            subjects_sending_to_subjects.add(sender)
            for recipient in recipients:
                subjects_receiving_from_subjects.add(recipient)
        
        # External counterparties → Subjects (incoming P2P from non-subjects)
        cp_to_subject = defaultdict(lambda: defaultdict(float))
        for tx in successful:
            if tx.is_p2p() and tx.is_incoming() and tx.has_real_counterparty():
                if tx.counterparty not in subjects:  # External only
                    cp_to_subject[tx.counterparty][tx.subject] += tx.amount
        
        # Top external counterparties
        cp_totals = {cp: sum(subs.values()) for cp, subs in cp_to_subject.items()}
        top_cps = sorted(cp_totals.items(), key=lambda x: x[1], reverse=True)[:max_cps]
        top_cp_ids = set(cp for cp, _ in top_cps)
        
        # "Other" counterparties
        other_total_per_subject = defaultdict(float)
        for cp, subs in cp_to_subject.items():
            if cp not in top_cp_ids:
                for subj, amt in subs.items():
                    other_total_per_subject[subj] += amt
        
        # Exit methods per subject (outgoing non-P2P + P2P to non-subjects)
        subject_to_exit = defaultdict(lambda: defaultdict(float))
        for tx in successful:
            if tx.is_outgoing() and tx.subject in subjects:
                # Skip inter-subject P2P (handled separately)
                if tx.is_p2p() and tx.counterparty in subjects:
                    continue
                
                product = tx.product_type or 'Unknown'
                subtype = tx.product_subtype or ''
                
                if product == 'P2P':
                    exit_label = 'P2P Outgoing (External)'
                elif product == 'TRANSFERS' and subtype == 'CASH_OUT':
                    exit_label = 'Bank Transfer (Cash Out)'
                elif product == 'TRANSFERS' and subtype == 'ACH':
                    exit_label = 'ACH Transfer'
                elif product == 'CASH_CARD' and subtype == 'ATM_WITHDRAWAL':
                    exit_label = 'ATM Withdrawal'
                elif product == 'CASH_CARD':
                    exit_label = 'Cash Card Purchases'
                elif product == 'CASH_APP_PAY':
                    exit_label = 'Cash App Pay'
                elif product == 'TRANSFERS' and subtype == 'OVERDRAFT_REPAYMENT':
                    exit_label = 'Overdraft Repayment'
                else:
                    exit_label = product
                
                subject_to_exit[tx.subject][exit_label] += tx.amount
        
        # Determine layers for subjects
        # If inter-subject flows exist, use 4 layers: CPs → Receivers → Forwarders → Exits
        # If no inter-subject flows, use 3 layers: CPs → Subjects → Exits
        has_inter_subject = len(inter_subject_flows) > 0
        
        if has_inter_subject:
            max_layer = 3
        else:
            max_layer = 2
        
        # Build nodes
        nodes = []
        node_index = {}
        
        # Layer 0: External counterparties
        for cp, total in top_cps:
            node_index[f'cp_{cp}'] = len(nodes)
            nodes.append({'name': cp, 'type': 'counterparty', 'layer': 0, 'total': total})
        
        if sum(other_total_per_subject.values()) > 0:
            other_count = len(cp_to_subject) - len(top_cp_ids)
            node_index['cp_OTHER'] = len(nodes)
            nodes.append({'name': f'Other ({other_count} CPs)', 'type': 'other', 'layer': 0, 'total': sum(other_total_per_subject.values())})
        
        if has_inter_subject:
            # Layer 1: Subjects that receive from external CPs (and may forward)
            # Layer 2: Subjects that receive from other subjects
            for subj in subject_list:
                ext_total = sum(cp_to_subject[cp].get(subj, 0) for cp in cp_to_subject)
                int_received = sum(inter_subject_flows[s].get(subj, 0) for s in inter_subject_flows)
                int_sent = sum(inter_subject_flows.get(subj, {}).values())
                total = ext_total + int_received
                
                if subj in subjects_sending_to_subjects and ext_total > 0:
                    # Receives externally AND forwards — layer 1
                    layer = 1
                elif subj in subjects_receiving_from_subjects and subj not in subjects_sending_to_subjects:
                    # Only receives from other subjects — layer 2
                    layer = 2
                elif ext_total > 0:
                    # Only receives externally — layer 1
                    layer = 1
                else:
                    layer = 1
                
                node_index[f'subj_{subj}'] = len(nodes)
                nodes.append({'name': subj, 'type': 'subject', 'layer': layer, 'total': total,
                             'inter_subject_sender': subj in subjects_sending_to_subjects,
                             'inter_subject_receiver': subj in subjects_receiving_from_subjects})
        else:
            # Simple: all subjects at layer 1
            for subj in subject_list:
                ext_total = sum(cp_to_subject[cp].get(subj, 0) for cp in cp_to_subject)
                node_index[f'subj_{subj}'] = len(nodes)
                nodes.append({'name': subj, 'type': 'subject', 'layer': 1, 'total': ext_total})
        
        # Exit methods at final layer
        all_exits = set()
        for subj_exits in subject_to_exit.values():
            all_exits.update(subj_exits.keys())
        
        for exit_label in sorted(all_exits):
            node_index[f'exit_{exit_label}'] = len(nodes)
            exit_total = sum(subject_to_exit[subj].get(exit_label, 0) for subj in subject_list)
            nodes.append({'name': exit_label, 'type': 'exit', 'layer': max_layer, 'total': exit_total})
        
        # Build links
        links = []
        
        # External CP → Subject
        for cp, _ in top_cps:
            for subj, amt in cp_to_subject[cp].items():
                if amt > 0:
                    src = node_index.get(f'cp_{cp}')
                    tgt = node_index.get(f'subj_{subj}')
                    if src is not None and tgt is not None:
                        links.append({'source': src, 'target': tgt, 'value': amt, 'flow_type': 'external'})
        
        # Other → Subject
        for subj, amt in other_total_per_subject.items():
            if amt > 0:
                src = node_index.get('cp_OTHER')
                tgt = node_index.get(f'subj_{subj}')
                if src is not None and tgt is not None:
                    links.append({'source': src, 'target': tgt, 'value': amt, 'flow_type': 'external'})
        
        # Inter-subject flows (Subject → Subject)
        for sender, recipients in inter_subject_flows.items():
            for recipient, amt in recipients.items():
                if amt > 0:
                    src = node_index.get(f'subj_{sender}')
                    tgt = node_index.get(f'subj_{recipient}')
                    if src is not None and tgt is not None:
                        links.append({'source': src, 'target': tgt, 'value': amt, 'flow_type': 'inter_subject'})
        
        # Subject → Exit
        for subj in subject_list:
            for exit_label, amt in subject_to_exit[subj].items():
                if amt > 0:
                    src = node_index.get(f'subj_{subj}')
                    tgt = node_index.get(f'exit_{exit_label}')
                    if src is not None and tgt is not None:
                        links.append({'source': src, 'target': tgt, 'value': amt, 'flow_type': 'exit'})
        
        # Build timeline data — individual transactions with timestamps for animation
        timeline_txns = []
        for tx in successful:
            # For incoming: skip system tokens (but allow inter-subject)
            # For outgoing: always include (cash outs, ATM, etc. have system counterparties)
            if tx.is_incoming() and not tx.has_real_counterparty() and tx.counterparty not in subjects:
                continue
            
            date_str = tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date)
            
            # Determine source and target node indices
            src_idx = None
            tgt_idx = None
            flow_type = ''
            
            if tx.is_p2p() and tx.is_incoming():
                if tx.counterparty in subjects:
                    src_idx = node_index.get(f'subj_{tx.counterparty}')
                    tgt_idx = node_index.get(f'subj_{tx.subject}')
                    flow_type = 'inter_subject'
                elif f'cp_{tx.counterparty}' in node_index:
                    src_idx = node_index.get(f'cp_{tx.counterparty}')
                    tgt_idx = node_index.get(f'subj_{tx.subject}')
                    flow_type = 'external'
            elif tx.is_outgoing() and tx.subject in subjects:
                if tx.is_p2p() and tx.counterparty in subjects:
                    continue  # Already captured as inter-subject incoming
                product = tx.product_type or 'Unknown'
                subtype = tx.product_subtype or ''
                if product == 'P2P':
                    exit_key = 'P2P Outgoing (External)'
                elif product == 'TRANSFERS' and subtype == 'CASH_OUT':
                    exit_key = 'Bank Transfer (Cash Out)'
                elif product == 'TRANSFERS' and subtype == 'ACH':
                    exit_key = 'ACH Transfer'
                elif product == 'CASH_CARD' and subtype == 'ATM_WITHDRAWAL':
                    exit_key = 'ATM Withdrawal'
                elif product == 'CASH_CARD':
                    exit_key = 'Cash Card Purchases'
                elif product == 'CASH_APP_PAY':
                    exit_key = 'Cash App Pay'
                elif product == 'TRANSFERS' and subtype == 'OVERDRAFT_REPAYMENT':
                    exit_key = 'Overdraft Repayment'
                else:
                    exit_key = product
                
                src_idx = node_index.get(f'subj_{tx.subject}')
                tgt_idx = node_index.get(f'exit_{exit_key}')
                flow_type = 'exit'
            
            if src_idx is not None and tgt_idx is not None:
                timeline_txns.append({
                    'date': date_str,
                    'source': src_idx,
                    'target': tgt_idx,
                    'amount': tx.amount,
                    'flow_type': flow_type,
                    'comment': (tx.comment or '')[:30],
                })
        
        # Sort by date
        timeline_txns.sort(key=lambda x: x['date'])
        
        # Get date range
        dates = [t['date'] for t in timeline_txns if t['date']]
        date_min = dates[0] if dates else ''
        date_max = dates[-1] if dates else ''
        
        return jsonify({
            'nodes': nodes,
            'links': links,
            'case_id': last_case_id or '',
            'has_inter_subject_flows': has_inter_subject,
            'inter_subject_count': len(inter_subject_flows),
            'timeline': timeline_txns,
            'date_range': [date_min, date_max],
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/sankey/transactions', methods=['GET'])
def get_sankey_transactions():
    """Return individual transactions for a specific flow in the Sankey"""
    global last_transactions_raw
    
    if not last_transactions_raw:
        return jsonify({'error': 'No data'}), 400
    
    source_id = request.args.get('source', '')
    target_id = request.args.get('target', '')
    
    if not source_id or not target_id:
        return jsonify({'error': 'source and target required'}), 400
    
    try:
        successful = [tx for tx in last_transactions_raw if tx.is_paid_out()]
        subjects = set(tx.subject for tx in last_transactions_raw)
        
        txns = []
        for tx in successful:
            match = False
            
            # CP → Subject (incoming P2P)
            if tx.is_p2p() and tx.is_incoming() and tx.counterparty == source_id and tx.subject == target_id:
                match = True
            # Subject → Subject (inter-subject)
            elif tx.is_p2p() and tx.is_incoming() and tx.counterparty == source_id and tx.subject == target_id and source_id in subjects:
                match = True
            # Subject → Exit (outgoing from subject)
            elif tx.is_outgoing() and tx.subject == source_id:
                match = True
            
            if match:
                txns.append({
                    'date': tx.date.isoformat() if hasattr(tx.date, 'isoformat') else str(tx.date),
                    'amount': tx.amount,
                    'comment': (tx.comment or '')[:40],
                    'counterparty': tx.counterparty,
                    'product': tx.product_type,
                    'direction': 'IN' if tx.is_incoming() else 'OUT',
                })
        
        txns.sort(key=lambda x: x['date'], reverse=True)
        
        return jsonify({'transactions': txns[:50], 'total_count': len(txns)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/deep-analysis', methods=['POST'])
def deep_analysis():
    """Run deep analysis — pre-computes findings, then uses LLM to write the report"""
    global last_analysis_formatted, last_case_id, last_csv_path, last_transactions_raw
    
    data = request.json
    question = data.get('question', '')
    case_context = data.get('context', '')
    
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    
    if not last_transactions_raw:
        return jsonify({'error': 'No CSV data loaded. Upload a CSV first.'}), 400
    
    try:
        # Step 1: Pre-compute comprehensive analysis from the actual data
        from lab_analyzer import run_lab_analysis, format_findings_for_llm
        
        findings = run_lab_analysis(last_transactions_raw, case_context)
        findings_text = format_findings_for_llm(findings)
        
        # Step 2: Send pre-computed findings + question to OpenAI to write the report
        lab_system_prompt = (
            "You are a seasoned forensic accountant and AML investigator with 20+ years of experience. "
            "You've seen thousands of cases — drug trafficking, human trafficking, CSAM, fraud rings, money laundering networks. "
            "You know exactly what to look for and you don't miss details.\n\n"
            "You have PRE-COMPUTED FINDINGS from real transaction data. Use these EXACT numbers — never approximate or guess.\n\n"
            "HOW YOU COMMUNICATE:\n"
            "- Talk like you're sitting across from the analyst pointing at a spreadsheet: 'Look at this — 9 hotel purchases across 5 different properties in Huntsville. That's not vacation, that's rotation.'\n"
            "- Be specific and precise: exact dollar amounts, exact dates, exact counterparty tokens, exact times.\n"
            "- Connect dots the analyst might miss: 'The babysitter payments at 11pm, combined with the hotel charges and OnlyFans purchases — that's a pattern.'\n"
            "- Call out what's normal vs what's not: 'Dollar General and gas stations are expected. 7 purchases at Enchantasys adult shop is not.'\n"
            "- Flag the investigative leads: 'This counterparty sent $X at 3am with comment Y — worth pulling their account next.'\n"
            "- Don't waste words on obvious things. Skip the boilerplate. Get to what matters.\n"
            "- Short paragraphs. Punch hard. Every sentence should tell the analyst something useful.\n"
            "- When multiple red flags converge on the same conclusion, say so explicitly.\n\n"
            "RULES:\n"
            "- Use 'Potential' not 'Suspicious' when describing activity.\n"
            "- Never recommend whether to file a SAR — that's the analyst's decision.\n"
            "- Never say 'I recommend further investigation' — the analyst already knows that. Instead, tell them WHERE to look next."
        )
        
        # Build messages with conversation history
        messages = [
            {'role': 'system', 'content': lab_system_prompt},
            {'role': 'user', 'content': f"{findings_text}\n\nANALYST QUESTION: {question}"},
        ]
        
        # Add previous lab conversation for continuity
        is_followup = data.get('is_followup', False)
        if is_followup and lab_conversation:
            # Insert previous exchanges before the new question
            messages = [
                {'role': 'system', 'content': lab_system_prompt},
                {'role': 'user', 'content': f"{findings_text}\n\nINITIAL ANALYSIS REQUEST: {lab_conversation[0]['question']}"},
                {'role': 'assistant', 'content': lab_conversation[0]['report']},
            ]
            for prev in lab_conversation[1:]:
                messages.append({'role': 'user', 'content': prev['question']})
                messages.append({'role': 'assistant', 'content': prev['report']})
            messages.append({'role': 'user', 'content': question})
        
        response = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=messages,
            temperature=0.7,
            max_tokens=4000,
        )
        
        report = response.choices[0].message.content
        
        # Store in lab conversation
        lab_conversation.append({'question': question, 'report': report})
        
        return jsonify({
            'report': report,
            'case_id': last_case_id or '',
            'question': question,
            'findings_summary': findings['red_flag_summary'],
            'conversation_length': len(lab_conversation),
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/lab/narrative', methods=['POST'])
def lab_narrative():
    """Generate a SAR narrative from lab findings with analyst-selected typologies"""
    global last_transactions_raw, last_case_id, last_csv_path, lab_conversation
    
    if not last_transactions_raw:
        return jsonify({'error': 'No CSV data loaded.'}), 400
    
    data = request.json
    typologies = data.get('typologies', [])
    instructions = data.get('instructions', '')
    context = data.get('context', '')
    
    if not typologies:
        return jsonify({'error': 'Select at least one typology.'}), 400
    
    try:
        from lab_analyzer import run_lab_analysis, format_findings_for_llm
        
        findings = run_lab_analysis(last_transactions_raw, context)
        findings_text = format_findings_for_llm(findings)
        
        # Build the lab conversation summary for context
        conv_summary = ''
        if lab_conversation:
            conv_summary = '\nPREVIOUS LAB ANALYSIS:\n'
            for entry in lab_conversation[-3:]:
                conv_summary += f"Q: {entry['question'][:200]}\n"
                conv_summary += f"A: {entry['report'][:500]}\n\n"
        
        typology_list = ', '.join(typologies)
        
        narrative_prompt = (
            "You are writing a SAR narrative for Block/Cash App. "
            "Use the pre-computed findings and lab analysis below to write a complete SAR narrative. "
            "Follow this EXACT structure:\n\n"
            "1. OPENING: 'Block, Inc. (\"Block\") is filing a Suspicious Activity Report (\"SAR\") #[CASE NUMBER] "
            f"for activity indicative of {typology_list} on the Cash App platform.' "
            "Include total suspicious activity amount, transaction counts by product type, date range, and subject tokens.\n\n"
            "2. BLOCK BOILERPLATE: 'Block provides a money transmission product for non-commercial and commercial use known as Cash App...'\n\n"
            "3. ALERT SOURCE: '[ANALYST: internal/external] referral which identified [ANALYST: referral reason].'\n\n"
            "4. TRANSACTION ANALYSIS: Attempted vs successful counts, amount ranges, common amounts. "
            "Include P2P, Cash Card, ATM, and transfer breakdowns.\n\n"
            f"5. TYPOLOGY-SPECIFIC ANALYSIS: Write detailed paragraphs for each typology: {typology_list}. "
            "Quote SPECIFIC transaction examples — exact dates, times, amounts, merchants, comments, counterparty tokens. "
            "Connect the dots between different indicators. Explain WHY each pattern is concerning.\n\n"
            "6. SUMMARY: Tie it all together.\n\n"
            "7. CLOSING: 'As a result of this suspicious activity, the relevant subject Cash App accounts were closed...'\n\n"
            "Mark sections requiring analyst input with [ANALYST: description] in the text.\n"
            "Use 'Potential' not 'Suspicious' in the body. Be specific and thorough."
        )
        
        if instructions:
            narrative_prompt += f"\n\nADDITIONAL ANALYST INSTRUCTIONS: {instructions}"
        
        messages = [
            {'role': 'system', 'content': narrative_prompt},
            {'role': 'user', 'content': f"{findings_text}{conv_summary}\n\nWrite the SAR narrative for typologies: {typology_list}"},
        ]
        
        response = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=messages,
            temperature=0.7,
            max_tokens=4000,
        )
        
        narrative = response.choices[0].message.content
        
        return jsonify({
            'narrative': narrative,
            'typologies': typologies,
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/lab/similar', methods=['GET'])
def lab_similar_cases():
    """Search for similar cases in the RAG database (empty architecture for now)"""
    global last_transactions_raw, last_case_id
    
    if not last_transactions_raw:
        return jsonify({'error': 'No CSV data loaded.'}), 400
    
    try:
        from lab_analyzer import run_lab_analysis
        
        findings = run_lab_analysis(last_transactions_raw)
        red_flags = findings.get('red_flag_summary', [])
        
        # Check if RAG database has any data
        rag_available = False
        try:
            import chromadb
            client = chromadb.PersistentClient(path='./sar_workflow_test_rag_db')
            collection = client.get_or_create_collection('sar_narratives')
            rag_available = collection.count() > 0
        except:
            pass
        
        if rag_available:
            # Query the vector database with our red flags
            query_text = ' '.join(red_flags[:5])
            results = collection.query(query_texts=[query_text], n_results=5)
            
            similar = []
            for i, doc in enumerate(results['documents'][0]):
                similar.append({
                    'case_id': results['metadatas'][0][i].get('case_id', 'Unknown'),
                    'typology': results['metadatas'][0][i].get('typology', 'Unknown'),
                    'similarity': f"{(1 - results['distances'][0][i]) * 100:.0f}%",
                    'excerpt': doc[:200],
                })
            
            return jsonify({
                'status': 'available',
                'similar_cases': similar,
                'query': query_text,
            })
        else:
            # RAG not populated yet — return the architecture status
            return jsonify({
                'status': 'awaiting_data',
                'message': 'RAG database is set up but awaiting SAR data ingestion. Once approved, historical SARs will be searchable.',
                'red_flags_detected': red_flags,
                'would_search_for': [
                    f"Cases with {len(red_flags)} matching red flags",
                    f"Hotel pattern: {'Yes' if findings['hotel_pattern']['count'] > 0 else 'No'}",
                    f"Adult content: {'Yes' if findings['adult_content']['count'] > 0 else 'No'}",
                    f"Late night activity: {'Yes' if findings['late_night']['total_late_night'] > 0 else 'No'}",
                    f"Drug indicators: {'Yes' if findings['drug_indicators']['count'] > 0 else 'No'}",
                    f"Trafficking indicators: {'Yes' if findings['trafficking_indicators']['comments'] else 'No'}",
                ],
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/chat', methods=['POST'])
def chat():
    """LLM chat endpoint — routes to Goose or OpenAI based on config"""
    global chat_history, last_analysis_formatted, last_case_id
    
    data = request.json
    user_message = data.get('message', '')
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    if COPILOT_BACKEND == 'goose':
        return chat_goose(user_message)
    else:
        return chat_openai(user_message)

goose_conversation = []  # Full conversation history for Goose

def chat_goose(user_message):
    """Route chat through Goose for full capabilities"""
    global goose_conversation
    from copilot_goose import run_goose_query
    
    try:
        # Build rich context from SAR Workflow Test's analysis
        context = ''
        if last_analysis_formatted:
            a = last_analysis_formatted.get('analysis_summary', {})
            stats = last_analysis_formatted.get('stats', {})
            typs = last_analysis_formatted.get('typologies', [])
            patterns = last_analysis_formatted.get('patterns', {})
            comments = last_analysis_formatted.get('comments', {})
            indicators = last_analysis_formatted.get('indicators', [])
            
            context = f"Case: {last_case_id or 'Unknown'}\n"
            context += f"Detection: {a.get('final_recommendation', 'None')}\n"
            context += f"Typologies: {', '.join(t['name'] + ' (' + str(t['confidence']) + '%)' for t in typs) if typs else 'None'}\n"
            context += f"Subjects: {stats.get('subject_count', 1)} | Counterparties: {stats.get('unique_counterparties', 0):,}\n"
            context += f"Total txns: {stats.get('total_transactions', 0):,} ({stats.get('successful_transactions', 0):,} successful)\n"
            context += f"Incoming: ${stats.get('incoming_total', 0):,.2f} | Outgoing: ${stats.get('outgoing_total', 0):,.2f}\n"
            context += f"P2P attempted: {stats.get('p2p_attempted_count', 0):,} (${stats.get('p2p_attempted_total', 0):,.2f})\n"
            context += f"Round dollar %: {patterns.get('round_dollar_pct', 0):.1f}% | Incoming ratio: {patterns.get('incoming_pct', 0):.1f}%\n"
            
            # Add key indicators
            if indicators:
                context += "Key indicators: "
                ind_texts = [ind.get('text', str(ind)) if isinstance(ind, dict) else str(ind) for ind in indicators[:5]]
                context += ' | '.join(ind_texts) + '\n'
            
            # Add suspicious comments
            samples = comments.get('samples', [])
            if samples:
                context += "Suspicious comments: "
                context += ', '.join(f'"{s.get("comment","")}"' for s in samples[:6]) + '\n'
        
        # Include CSV path and conversation history in the message
        csv_instruction = ''
        if last_csv_path and os.path.exists(last_csv_path):
            csv_instruction = (
                f"TO ANSWER DATA QUESTIONS, run this Python script:\n"
                f"cd /Users/gkirk/Desktop/sar-workflow-test && python3 << 'EOF'\n"
                f"from copilot_csv_helper import load_case\n"
                f"data = load_case('{last_csv_path}')\n"
                f"print(data['top_senders'][['total_amount','txn_count','subjects']].head(5))\n"
                f"print('Multi-subject CPs:', data['multi_subject_count'])\n"
                f"EOF\n"
                f"Modify the print statements as needed for the question. ALWAYS use copilot_csv_helper.\n\n"
            )
        
        full_message = csv_instruction + user_message
        if goose_conversation:
            history = '\n'.join([f"{'Analyst' if m['role']=='user' else 'Copilot'}: {m['content'][:200]}" for m in goose_conversation[-6:]])
            full_message = csv_instruction + f"CONVERSATION HISTORY:\n{history}\n\nNEW QUESTION: {user_message}"
        
        response = run_goose_query(
            message=full_message,
            case_context=context,
            csv_path=last_csv_path or '',
        )
        
        # Store in conversation history (keep all messages)
        goose_conversation.append({'role': 'user', 'content': user_message})
        goose_conversation.append({'role': 'assistant', 'content': response})
        
        return jsonify({
            'response': response,
            'case_context': last_case_id or None,
            'backend': 'goose',
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def chat_openai(user_message):
    """Route chat through OpenAI with function calling"""
    global chat_history
    
    try:
        # Build comprehensive context from current analysis
        context = ''
        if last_analysis_formatted:
            a = last_analysis_formatted.get('analysis_summary', {})
            stats = last_analysis_formatted.get('stats', {})
            typs = last_analysis_formatted.get('typologies', [])
            patterns = last_analysis_formatted.get('patterns', {})
            comments = last_analysis_formatted.get('comments', {})
            counterparties = last_analysis_formatted.get('counterparties', {})
            indicators = last_analysis_formatted.get('indicators', [])
            
            context = f"\n\n{'='*60}\nCURRENT CASE DATA (Case {last_case_id or 'Unknown'})\n{'='*60}\n\n"
            
            # Detection results
            context += f"SAR WORKFLOW TEST DETECTION RESULTS:\n"
            context += f"  Result: {a.get('final_recommendation', 'None')}\n"
            context += f"  Typologies: {', '.join(t['name'] + ' (' + str(t['confidence']) + '%)' for t in typs) if typs else 'None'}\n\n"
            
            # Transaction overview
            context += f"TRANSACTION OVERVIEW:\n"
            context += f"  Total attempted: {stats.get('total_transactions', 0):,}\n"
            context += f"  Successful: {stats.get('successful_transactions', 0):,}\n"
            context += f"  Failed/Declined: {stats.get('total_transactions', 0) - stats.get('successful_transactions', 0):,}\n"
            context += f"  Unique counterparties: {stats.get('unique_counterparties', 0):,}\n"
            context += f"  Subject accounts: {stats.get('subject_count', 1)}\n"
            if stats.get('subject_count', 1) > 1:
                context += f"  Subject tokens: {', '.join(stats.get('subject_tokens', []))}\n"
            context += f"  Incoming (successful): {stats.get('incoming_paid_count', 0):,} txns, ${stats.get('incoming_total', 0):,.2f}\n"
            context += f"  Outgoing (successful): {stats.get('outgoing_paid_count', 0):,} txns, ${stats.get('outgoing_total', 0):,.2f}\n"
            context += f"  Incoming (attempted): {stats.get('incoming_attempts', 0):,} txns, ${stats.get('incoming_attempted_total', 0):,.2f}\n"
            context += f"  Outgoing (attempted): {stats.get('outgoing_attempts', 0):,} txns, ${stats.get('outgoing_attempted_total', 0):,.2f}\n"
            context += f"  P2P (successful): {stats.get('p2p_count', 0):,} txns\n"
            context += f"  P2P (attempted): {stats.get('p2p_attempted_count', 0):,} txns, ${stats.get('p2p_attempted_total', 0):,.2f}\n\n"
            
            # Inflow breakdown
            inflows = stats.get('inflow_breakdown', [])
            if inflows:
                context += f"SUCCESSFUL INFLOW BREAKDOWN:\n"
                for item in inflows:
                    context += f"  {item['label']}: {item['count']} txns, ${item['total']:,.2f} (avg ${item['avg']:.2f})\n"
                context += '\n'
            
            # Outflow breakdown
            outflows = stats.get('outflow_breakdown', [])
            if outflows:
                context += f"SUCCESSFUL OUTFLOW BREAKDOWN:\n"
                for item in outflows:
                    context += f"  {item['label']}: {item['count']} txns, ${item['total']:,.2f} (avg ${item['avg']:.2f})\n"
                context += '\n'
            
            # Patterns
            context += f"PATTERN ANALYSIS:\n"
            context += f"  Round dollar %: {patterns.get('round_dollar_pct', 0):.1f}%\n"
            context += f"  Under $100 %: {patterns.get('under_100_pct', 0):.1f}%\n"
            context += f"  Average amount: ${patterns.get('average_amount', 0):.2f}\n"
            context += f"  Incoming %: {patterns.get('incoming_pct', 0):.1f}%\n\n"
            
            # Risk indicators
            if indicators:
                context += f"RISK INDICATORS:\n"
                for ind in indicators:
                    text = ind.get('text', ind) if isinstance(ind, dict) else str(ind)
                    context += f"  - {text}\n"
                context += '\n'
            
            # Suspicious comments
            samples = comments.get('samples', [])
            if samples:
                context += f"SUSPICIOUS COMMENTS (deduplicated):\n"
                for s in samples:
                    context += f"  \"{s.get('comment', '')}\" → {s.get('terms', '')} (confidence: {s.get('confidence', 0):.0f}%)\n"
                context += '\n'
            
            # Full transaction detail from raw data
            if last_transactions_summary:
                context += f"\nDETAILED TRANSACTION DATA:\n{last_transactions_summary}\n"
            
            # Pre-computed CSV helper data for precise answers
            if last_csv_path and os.path.exists(last_csv_path):
                try:
                    from copilot_csv_helper import load_case
                    helper_data = load_case(last_csv_path)
                    
                    context += f"\n{'='*40}\nPRE-COMPUTED ANALYSIS (use these exact numbers):\n{'='*40}\n"
                    context += f"Subjects: {helper_data['subject_count']} — {', '.join(helper_data['subjects'])}\n"
                    context += f"Total incoming P2P: ${helper_data['total_incoming']:,.2f}\n"
                    context += f"Total outgoing P2P: ${helper_data['total_outgoing']:,.2f}\n"
                    context += f"Counterparties sending to multiple subjects: {helper_data['multi_subject_count']}\n\n"
                    
                    context += "TOP 15 SENDERS (by total amount sent to subjects):\n"
                    for i, (token, row) in enumerate(helper_data['top_senders'].head(15).iterrows(), 1):
                        context += f"  {i}. {token}: ${row['total_amount']:,.2f} across {row['txn_count']} txns to {row['subjects']} subject(s)\n"
                    
                    if helper_data['multi_subject_count'] > 0:
                        context += f"\nCOUNTERPARTIES SENDING TO MULTIPLE SUBJECTS ({helper_data['multi_subject_count']} total):\n"
                        for token, count in helper_data['multi_subject_cps'].sort_values(ascending=False).head(20).items():
                            context += f"  {token}: sends to {count} subjects\n"
                except Exception:
                    pass
        
        # Build messages
        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT + context}
        ]
        
        # Add full chat history for session memory
        for msg in chat_history:
            messages.append(msg)
        
        # Add new user message
        messages.append({'role': 'user', 'content': user_message})
        
        # Call OpenAI with function calling tools
        from copilot_tools import TOOL_DEFINITIONS, CopilotTools
        
        tools = TOOL_DEFINITIONS if last_transactions_raw else None
        
        response = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=messages,
            temperature=0.7,
            max_tokens=4000,
            tools=tools,
        )
        
        response_message = response.choices[0].message
        
        # Handle function calls — the LLM wants to query data
        if response_message.tool_calls and last_transactions_raw:
            tool_helper = CopilotTools(last_transactions_raw)
            
            # Add the assistant's response (with tool calls) to messages
            messages.append(response_message)
            
            # Execute each tool call
            for tool_call in response_message.tool_calls:
                func_name = tool_call.function.name
                import json as _json
                func_args = _json.loads(tool_call.function.arguments)
                
                # Call the appropriate function
                if hasattr(tool_helper, func_name):
                    result = getattr(tool_helper, func_name)(**func_args)
                else:
                    result = f"Unknown function: {func_name}"
                
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tool_call.id,
                    'content': result,
                })
            
            # Call OpenAI again with the tool results
            response2 = openai_client.chat.completions.create(
                model='gpt-4o',
                messages=messages,
                temperature=0.7,
                max_tokens=4000,
            )
            
            assistant_message = response2.choices[0].message.content
        else:
            assistant_message = response_message.content
        
        # Store in history
        chat_history.append({'role': 'user', 'content': user_message})
        chat_history.append({'role': 'assistant', 'content': assistant_message})
        
        return jsonify({
            'response': assistant_message,
            'case_context': last_case_id or None,
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/chat/clear', methods=['POST'])
def clear_chat():
    """Clear chat history"""
    global chat_history, goose_conversation
    chat_history = []
    goose_conversation = []
    return jsonify({'success': True})


if __name__ == '__main__':
    print("\n" + "="*60)
    print("SAR PLATFORM - WEB SERVER")
    print("="*60)
    print("\n🚀 Starting server...")
    print("📍 Open your browser to: http://localhost:8888")
    print("📁 Make sure demo_ui.html is in the same directory")
    print("\n⚠️  Press Ctrl+C to stop the server\n")
    
    app.run(debug=True, port=8888, host='127.0.0.1')
