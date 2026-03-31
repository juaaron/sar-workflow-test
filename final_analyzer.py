"""
SAR Platform - Final Integrated Analyzer
Combines all detection systems with legitimate business filtering
"""

from csv_parser import CSVParser, TransactionRecord
from pattern_detector import NetworkAnalyzer, TemporalAnalyzer
from context_aware_detector import WeightedSlangDetector, LayeringDetector, MultiTypologyDetector
from legitimate_business_detector import LegitimateBusinessDetector
from passthrough_detector import PassThroughDetector
from typing import List, Dict
from collections import defaultdict


class FinalAnalyzer:
    """
    Complete analyzer with:
    - Context-aware drug slang detection
    - Multi-typology detection
    - Legitimate business filtering
    - False positive reduction
    """
    
    def __init__(self, transactions: List[TransactionRecord]):
        self.transactions = transactions
        self.subject = transactions[0].subject if transactions else None
        
        # Initialize all detectors
        self.slang_detector = WeightedSlangDetector()
        self.layering_detector = LayeringDetector()
        self.multi_typology = MultiTypologyDetector()
        self.legitimate_detector = LegitimateBusinessDetector()
        self.passthrough_detector = PassThroughDetector()
        self.network_analyzer = NetworkAnalyzer(transactions)
        self.temporal_analyzer = TemporalAnalyzer(transactions)
    
    def analyze(self) -> Dict:
        """Perform complete analysis with legitimate business filtering"""
        
        print(f"\n{'='*70}")
        print(f"FINAL INTEGRATED ANALYSIS")
        print(f"Subject: {self.subject}")
        print(f"{'='*70}\n")
        
        # Basic stats
        basic_stats = self._calculate_basic_stats()
        
        # Pattern detection
        patterns = self._detect_patterns()
        
        # Context-aware comment analysis
        comment_analysis = self._analyze_comments_with_context()
        
        # Counterparty analysis
        counterparty_analysis = self._analyze_counterparties()
        
        # Layering detection
        layering_analysis = self.layering_detector.analyze_layering_patterns(
            self.transactions, self.subject
        )
        
        # Product type analysis
        product_analysis = self._analyze_product_types()
        
        # Temporal analysis
        temporal_analysis = self._analyze_temporal_patterns()
        
        # Build analysis dict
        analysis_results = {
            'subject': self.subject,
            'basic_stats': basic_stats,
            'patterns': patterns,
            'comments': comment_analysis,
            'counterparties': counterparty_analysis,
            'layering': layering_analysis,
            'products': product_analysis,
            'temporal': temporal_analysis
        }
        
        # Multi-typology detection (BEFORE legitimate business check)
        typology_results = self.multi_typology.detect_typologies(
            self.transactions, analysis_results
        )
        
        # Pass-through money laundering detection
        transaction_dicts = [
            {
                'date': t.date,
                'counterparty': t.counterparty,
                'amount': t.amount,
                'direction': t.direction,
                'comment': t.comment,
                'product_type': t.product_type,
                'status': t.status
            }
            for t in self.transactions
        ]
        passthrough_indicators = self.passthrough_detector.analyze(transaction_dicts)
        
        # Add pass-through to detected typologies if confidence is high
        # But NOT if gambling was detected (gambling facilitation has similar flow patterns)
        gambling_class = typology_results.get('gambling_classification', 'none')
        suppress_passthrough = gambling_class in ('facilitation', 'participation')
        
        if passthrough_indicators.confidence >= 60 and not suppress_passthrough:
            if 'detected_typologies' not in typology_results:
                typology_results['detected_typologies'] = {}
            
            # Add as a new typology in the dict
            typology_results['detected_typologies']['Pass-Through Money Laundering'] = {
                'confidence': passthrough_indicators.confidence / 100.0,  # Normalize to 0-1
                'risk_level': passthrough_indicators.risk_level,
                'primary_indicators': [
                    f"{passthrough_indicators.incoming_count:,} incoming P2P transactions",
                    f"{passthrough_indicators.outgoing_count:,} outgoing transfers",
                    f"{passthrough_indicators.incoming_to_outgoing_ratio:.1f}:1 incoming:outgoing ratio",
                    f"{passthrough_indicators.unique_senders} unique senders",
                    f"{passthrough_indicators.coded_comments_pct:.1f}% coded comments"
                ],
                'details': {
                    'incoming_count': passthrough_indicators.incoming_count,
                    'outgoing_count': passthrough_indicators.outgoing_count,
                    'ratio': passthrough_indicators.incoming_to_outgoing_ratio,
                    'unique_senders': passthrough_indicators.unique_senders,
                    'total_incoming': passthrough_indicators.total_incoming,
                    'total_outgoing': passthrough_indicators.total_outgoing,
                    'coded_comments_pct': passthrough_indicators.coded_comments_pct
                }
            }
            
            # Update primary typology if pass-through has higher confidence
            # BUT: If Drug Sales is detected with high confidence, prioritize it over Pass-Through
            normalized_confidence = passthrough_indicators.confidence / 100.0
            
            drug_sales_detected = 'Illegal Drug Sales' in typology_results.get('detected_typologies', {})
            drug_sales_confidence = typology_results.get('detected_typologies', {}).get('Illegal Drug Sales', {}).get('confidence', 0)
            
            # Priority logic: Drug Sales > Pass-Through if both are high confidence
            if drug_sales_detected and drug_sales_confidence >= 0.70:
                # Keep Drug Sales as primary if it's already high confidence
                if typology_results.get('primary_typology') != 'Illegal Drug Sales':
                    # Only override if pass-through is significantly higher (20+ points)
                    if normalized_confidence > drug_sales_confidence + 0.20:
                        typology_results['primary_typology'] = 'Pass-Through Money Laundering'
                        typology_results['primary_confidence'] = normalized_confidence
            else:
                # Normal logic: highest confidence wins
                if not typology_results.get('primary_typology') or normalized_confidence > typology_results.get('primary_confidence', 0):
                    typology_results['primary_typology'] = 'Pass-Through Money Laundering'
                    typology_results['primary_confidence'] = normalized_confidence
        
        # Add pass-through indicators to results
        analysis_results['passthrough'] = {
            'confidence': passthrough_indicators.confidence,
            'risk_level': passthrough_indicators.risk_level,
            'incoming_count': passthrough_indicators.incoming_count,
            'outgoing_count': passthrough_indicators.outgoing_count,
            'ratio': passthrough_indicators.incoming_to_outgoing_ratio,
            'unique_senders': passthrough_indicators.unique_senders,
            'total_incoming': passthrough_indicators.total_incoming,
            'total_outgoing': passthrough_indicators.total_outgoing,
            'coded_comments_pct': passthrough_indicators.coded_comments_pct
        }
        
        # Legitimate business analysis
        legitimacy_analysis = self.legitimate_detector.analyze_account_legitimacy(
            self.transactions, comment_analysis
        )
        
        # Check if legitimate business should override suspicious detection
        override_decision = self.legitimate_detector.should_override_suspicious_detection(
            legitimacy_analysis, typology_results
        )
        
        # Add to results
        analysis_results.update(typology_results)
        analysis_results['legitimacy'] = legitimacy_analysis
        analysis_results['override'] = override_decision
        
        # Final analysis summary (NO SAR RECOMMENDATION - humans decide)
        # Check for gambling participation (not suspicious, but worth noting)
        gambling_class = typology_results.get('gambling_classification', 'none')
        gambling_details = typology_results.get('gambling_details', {})
        analysis_results['gambling_classification'] = gambling_class
        analysis_results['gambling_details'] = gambling_details
        
        if override_decision['should_override']:
            analysis_results['final_recommendation'] = 'Legitimate Business Activity Detected'
            analysis_results['suspicious_activity_detected'] = False
        elif gambling_class == 'participation' and not typology_results.get('detected_typologies'):
            # Gambling participation with no other suspicious typologies = not suspicious
            cash_card_info = gambling_details.get('cash_card_gambling', {})
            p2p_risk = gambling_details.get('p2p_risk', {})
            analysis_results['final_recommendation'] = 'Gambling Participation Detected (Not Facilitation)'
            analysis_results['suspicious_activity_detected'] = False
            analysis_results['gambling_participation'] = {
                'purchases': cash_card_info.get('count', 0),
                'total_spent': cash_card_info.get('total_spent', 0),
                'platforms': cash_card_info.get('platforms', []),
                'p2p_risk': p2p_risk.get('risk', 'unknown'),
                'p2p_details': p2p_risk.get('details', [])
            }
        else:
            if typology_results.get('detected_typologies'):
                analysis_results['final_recommendation'] = f"Potential {typology_results['primary_typology']}"
                analysis_results['suspicious_activity_detected'] = True
            else:
                analysis_results['final_recommendation'] = 'No Suspicious Patterns Detected'
                analysis_results['suspicious_activity_detected'] = False
        
        return analysis_results
    
    def _calculate_basic_stats(self) -> Dict:
        """Calculate basic transaction statistics.
        
        RULE: Dollar totals/averages only count SUCCESSFUL transactions.
        Comment analysis includes all transactions (even failed).
        """
        from collections import defaultdict
        
        successful = [tx for tx in self.transactions if tx.is_paid_out()]
        
        incoming_paid = [tx for tx in successful if tx.is_incoming()]
        outgoing_paid = [tx for tx in successful if tx.is_outgoing()]
        
        p2p_paid = [tx for tx in successful if tx.is_p2p()]
        
        # Build product-type breakdowns for inflows and outflows
        def build_product_breakdown(txns):
            """Group transactions by product type/subtype with counts and totals"""
            breakdown = defaultdict(lambda: {'count': 0, 'total': 0.0, 'avg': 0.0})
            for tx in txns:
                # Create a readable label from product_type + product_subtype
                product = tx.product_type or 'Unknown'
                subtype = tx.product_subtype or ''
                
                # Build human-readable label
                if product == 'P2P':
                    label = 'P2P Payments'
                elif product == 'CASH_CARD' and subtype == 'PURCHASE':
                    label = 'Cash Card Purchases'
                elif product == 'CASH_CARD' and subtype == 'ATM_WITHDRAWAL':
                    label = 'ATM Withdrawals'
                elif product == 'CASH_CARD' and subtype == 'ACCOUNT_CREDIT':
                    label = 'Account Credits'
                elif product == 'CASH_CARD' and subtype == 'CASHBACK':
                    label = 'Cash Card Cashback'
                elif product == 'CASH_CARD' and subtype == 'ACCOUNT_FUNDING':
                    label = 'Account Funding'
                elif product == 'TRANSFERS' and subtype == 'CASH_OUT':
                    label = 'Bank Transfers (Cash Out)'
                elif product == 'TRANSFERS' and subtype == 'CASH_IN':
                    label = 'Bank Transfers (Cash In)'
                elif product == 'TRANSFERS' and subtype == 'PAPER_MONEY_DEPOSIT':
                    label = 'Paper Money Deposits'
                elif product == 'TRANSFERS' and subtype == 'PAPER_MONEY_DEPOSIT_FEE':
                    label = 'Paper Money Deposit Fees'
                elif product == 'TRANSFERS' and subtype == 'OVERDRAFT_REPAYMENT':
                    label = 'Overdraft Repayments'
                elif product == 'TRANSFERS' and subtype == 'ACH':
                    label = 'ACH Transfers'
                elif product == 'CASH_APP_PAY':
                    label = 'Cash App Pay'
                elif product == 'LENDING_AFTERPAY_RETRO':
                    label = 'Afterpay/Lending'
                elif product == 'TRANSFERS':
                    label = f'Transfers ({subtype})' if subtype else 'Transfers'
                else:
                    label = f'{product} ({subtype})' if subtype else product
                
                breakdown[label]['count'] += 1
                breakdown[label]['total'] += tx.amount
            
            # Calculate averages
            for label in breakdown:
                if breakdown[label]['count'] > 0:
                    breakdown[label]['avg'] = breakdown[label]['total'] / breakdown[label]['count']
            
            # Sort by total descending
            sorted_breakdown = sorted(breakdown.items(), key=lambda x: x[1]['total'], reverse=True)
            return sorted_breakdown
        
        # All transactions by direction (including failed — for SAR reporting)
        all_incoming = [tx for tx in self.transactions if tx.is_incoming()]
        all_outgoing = [tx for tx in self.transactions if tx.is_outgoing()]
        all_p2p = [tx for tx in self.transactions if tx.is_p2p()]
        
        # Successful breakdowns (for pattern analysis)
        inflow_breakdown = build_product_breakdown(incoming_paid)
        outflow_breakdown = build_product_breakdown(outgoing_paid)
        
        # Attempted breakdowns (ALL transactions including failed — for SAR narrative)
        inflow_attempted_breakdown = build_product_breakdown(all_incoming)
        outflow_attempted_breakdown = build_product_breakdown(all_outgoing)
        
        return {
            'total_transactions': len(self.transactions),
            'successful_transactions': len(successful),
            'incoming_attempts': len(all_incoming),
            'outgoing_attempts': len(all_outgoing),
            'incoming_paid_count': len(incoming_paid),
            'outgoing_paid_count': len(outgoing_paid),
            # Successful totals (for pattern analysis)
            'incoming_total': sum(tx.amount for tx in incoming_paid),
            'outgoing_total': sum(tx.amount for tx in outgoing_paid),
            'net_flow': sum(tx.amount for tx in incoming_paid) - sum(tx.amount for tx in outgoing_paid),
            'p2p_count': len(p2p_paid),
            'p2p_total': sum(tx.amount for tx in p2p_paid),
            # Attempted totals (ALL transactions — for SAR narrative reporting)
            'incoming_attempted_total': sum(tx.amount for tx in all_incoming),
            'outgoing_attempted_total': sum(tx.amount for tx in all_outgoing),
            'p2p_attempted_count': len(all_p2p),
            'p2p_attempted_total': sum(tx.amount for tx in all_p2p),
            'unique_counterparties': len(set(tx.counterparty for tx in self.transactions if tx.has_real_counterparty())),
            'subject_tokens': list(set(tx.subject for tx in self.transactions)),
            'subject_count': len(set(tx.subject for tx in self.transactions)),
            'date_range': (
                min(tx.date for tx in self.transactions),
                max(tx.date for tx in self.transactions)
            ) if self.transactions else None,
            'inflow_breakdown': inflow_breakdown,
            'outflow_breakdown': outflow_breakdown,
            'inflow_attempted_breakdown': inflow_attempted_breakdown,
            'outflow_attempted_breakdown': outflow_attempted_breakdown,
        }
    
    def _detect_patterns(self) -> Dict:
        """Detect suspicious patterns.
        
        RULE: Only count successful transactions for dollar amounts/averages.
        Break out patterns by product type for contextual analysis.
        """
        from collections import defaultdict
        
        paid_txs = [tx for tx in self.transactions if tx.is_paid_out()]
        amounts = [tx.amount for tx in paid_txs]
        
        if not amounts:
            return {}
        
        # P2P round dollar analysis (only P2P matters for round dollar suspicion)
        p2p_amounts = [tx.amount for tx in paid_txs if tx.is_p2p()]
        p2p_round = [a for a in p2p_amounts if a == int(a) and 10 <= a <= 150]
        round_pct = (len(p2p_round) / len(p2p_amounts) * 100) if p2p_amounts else 0
        
        under_100 = [a for a in amounts if a <= 100]
        under_100_pct = (len(under_100) / len(amounts)) * 100 if amounts else 0
        
        avg_amount = sum(amounts) / len(amounts) if amounts else 0
        
        incoming_paid = [tx for tx in paid_txs if tx.is_incoming()]
        incoming_pct = (len(incoming_paid) / len(paid_txs)) * 100 if paid_txs else 0
        
        # Per-product-type pattern analysis (successful only for patterns)
        product_patterns = {}
        product_groups_success = defaultdict(list)
        product_groups_all = defaultdict(list)
        
        for tx in paid_txs:
            product_groups_success[tx.product_type or 'Unknown'].append(tx)
        for tx in self.transactions:
            product_groups_all[tx.product_type or 'Unknown'].append(tx)
        
        for product in set(list(product_groups_success.keys()) + list(product_groups_all.keys())):
            success_txns = product_groups_success.get(product, [])
            all_txns = product_groups_all.get(product, [])
            
            s_amounts = [tx.amount for tx in success_txns]
            a_amounts = [tx.amount for tx in all_txns]
            s_round = [a for a in s_amounts if a == int(a) and 10 <= a <= 150]
            s_incoming = [tx for tx in success_txns if tx.is_incoming()]
            s_outgoing = [tx for tx in success_txns if tx.is_outgoing()]
            a_incoming = [tx for tx in all_txns if tx.is_incoming()]
            a_outgoing = [tx for tx in all_txns if tx.is_outgoing()]
            
            product_patterns[product] = {
                # Successful
                'count': len(success_txns),
                'total': sum(s_amounts),
                'average': sum(s_amounts) / len(s_amounts) if s_amounts else 0,
                'min': min(s_amounts) if s_amounts else 0,
                'max': max(s_amounts) if s_amounts else 0,
                'round_pct': (len(s_round) / len(s_amounts) * 100) if s_amounts else 0,
                'incoming_count': len(s_incoming),
                'outgoing_count': len(s_outgoing),
                'incoming_total': sum(tx.amount for tx in s_incoming),
                'outgoing_total': sum(tx.amount for tx in s_outgoing),
                # Attempted (all)
                'attempted_count': len(all_txns),
                'attempted_total': sum(a_amounts),
                'attempted_incoming_count': len(a_incoming),
                'attempted_outgoing_count': len(a_outgoing),
                'attempted_incoming_total': sum(tx.amount for tx in a_incoming),
                'attempted_outgoing_total': sum(tx.amount for tx in a_outgoing),
                'failed_count': len(all_txns) - len(success_txns),
            }
        
        return {
            'round_dollar_pct': round_pct,
            'under_100_pct': under_100_pct,
            'average_amount': avg_amount,
            'incoming_pct': incoming_pct,
            'product_patterns': product_patterns,
            'amount_distribution': {
                '1-10': len([a for a in amounts if 1 <= a <= 10]),
                '11-25': len([a for a in amounts if 11 <= a <= 25]),
                '26-50': len([a for a in amounts if 26 <= a <= 50]),
                '51-100': len([a for a in amounts if 51 <= a <= 100]),
                '101-200': len([a for a in amounts if 101 <= a <= 200]),
                '201+': len([a for a in amounts if a > 200])
            }
        }
    
    def _analyze_comments_with_context(self) -> Dict:
        """Analyze comments with context-aware detection.
        
        Checks BOTH drug slang AND gambling terms/usernames so that
        all suspicious comments appear in a single unified list.
        """
        from gambling_detector import GamblingDetector
        from adult_services_detector import AdultServicesDetector
        gambling_det = GamblingDetector()
        adult_det = AdultServicesDetector()
        
        # Get counterparty stats for context
        cp_stats = self.network_analyzer.get_counterparty_stats(self.subject)
        cp_velocity = {cp['counterparty']: cp['total_transactions'] for cp in cp_stats}
        
        total_cps = len(cp_stats)
        
        high_confidence_comments = []
        medium_confidence_comments = []
        low_confidence_comments = []
        all_detected_terms = []
        drug_only_count = 0  # Track drug-specific slang separately from gambling
        seen_comments_set = set()  # track (comment, counterparty) to avoid dupes from both detectors
        
        for tx in self.transactions:
            if tx.comment and tx.is_p2p() and tx.is_paid_out():
                comment_key = (tx.comment.strip().lower(), tx.counterparty)
                
                # Build context for drug slang detector
                context = {
                    'amount': tx.amount,
                    'is_incoming': tx.is_incoming(),
                    'counterparty_velocity': cp_velocity.get(tx.counterparty, 0),
                    'total_counterparties': total_cps
                }
                
                # 1. Drug slang detection
                drug_result = self.slang_detector.detect_with_context(tx.comment, context)
                
                # 2. Gambling term detection
                gambling_result = gambling_det.detect_gambling_terms(tx.comment)
                
                # 3. Gambling username detection
                username_result = gambling_det.detect_username_pattern(tx.comment)
                
                # Merge results — pick the highest confidence hit
                best_confidence = 0.0
                detected_terms = []
                
                if drug_result['detected']:
                    best_confidence = max(best_confidence, drug_result['confidence'])
                    detected_terms.extend(drug_result['detected'])
                
                if gambling_result['detected']:
                    conf = gambling_result['confidence']
                    best_confidence = max(best_confidence, conf)
                    for t in gambling_result['terms']:
                        detected_terms.append({
                            'term': t['term'],
                            'base_confidence': t['confidence'],
                            'type': 'gambling_' + t['type'],
                            'final_confidence': t['confidence']
                        })
                
                if username_result.get('detected'):
                    conf = username_result.get('confidence', 0.85)
                    best_confidence = max(best_confidence, conf)
                    for u in username_result.get('usernames', []):
                        detected_terms.append({
                            'term': u + ' (username)',
                            'base_confidence': conf,
                            'type': 'gambling_username',
                            'final_confidence': conf
                        })
                
                # 4. Adult services detection
                adult_result = adult_det.detect_adult_terms(tx.comment)
                if adult_result['detected']:
                    conf = adult_result['confidence']
                    best_confidence = max(best_confidence, conf)
                    for t in adult_result['terms']:
                        detected_terms.append({
                            'term': t['term'],
                            'base_confidence': t['confidence'],
                            'type': 'adult_' + t['category'],
                            'final_confidence': t['confidence']
                        })
                
                if detected_terms and comment_key not in seen_comments_set:
                    seen_comments_set.add(comment_key)
                    
                    # Track drug-only hits (not gambling terms/usernames)
                    has_drug_terms = bool(drug_result['detected'])
                    if has_drug_terms:
                        drug_only_count += 1
                    
                    comment_data = {
                        'comment': tx.comment,
                        'counterparty': tx.counterparty,
                        'amount': tx.amount,
                        'date': tx.date,
                        'confidence': best_confidence,
                        'confidence_level': self.slang_detector.categorize_confidence(best_confidence),
                        'context_score': drug_result.get('context_score', 1.0),
                        'detected_terms': detected_terms
                    }
                    
                    if best_confidence >= 0.85:
                        high_confidence_comments.append(comment_data)
                    elif best_confidence >= 0.50:
                        medium_confidence_comments.append(comment_data)
                    else:
                        low_confidence_comments.append(comment_data)
                    
                    all_detected_terms.extend(detected_terms)
        
        # Count term frequencies
        from collections import Counter
        term_counts = Counter([d['term'] for d in all_detected_terms])
        
        return {
            'total_comments': len([tx for tx in self.transactions if tx.comment]),
            'high_confidence_count': len(high_confidence_comments),
            'medium_confidence_count': len(medium_confidence_comments),
            'low_confidence_count': len(low_confidence_comments),
            'total_detected': len(high_confidence_comments) + len(medium_confidence_comments) + len(low_confidence_comments),
            'comments_with_slang': drug_only_count,
            'high_confidence_samples': high_confidence_comments[:20],
            'medium_confidence_samples': medium_confidence_comments[:10],
            'top_terms': term_counts.most_common(10)
        }
    
    def _analyze_counterparties(self) -> Dict:
        """Analyze counterparty patterns.
        Only counts real P2P counterparties — excludes system tokens,
        internal balance tokens (B$_), and merchant tokens (M_).
        """
        from csv_parser import SYSTEM_COUNTERPARTY_TOKENS
        
        cp_stats = self.network_analyzer.get_counterparty_stats(self.subject)
        # Filter to real P2P counterparties only
        cp_stats = [cp for cp in cp_stats 
                    if cp['counterparty'] not in SYSTEM_COUNTERPARTY_TOKENS
                    and not cp['counterparty'].startswith('B$_')
                    and not cp['counterparty'].startswith('M_')]
        
        # High velocity counterparties (5+ transactions)
        high_velocity = [cp for cp in cp_stats if cp['total_transactions'] >= 5]
        
        # Bidirectional flow
        bidirectional = [cp for cp in cp_stats if cp['bidirectional']]
        
        # Incoming-only (potential customers)
        incoming_only = [cp for cp in cp_stats 
                        if cp['incoming_count'] > 0 and cp['outgoing_count'] == 0]
        
        return {
            'total_counterparties': len(cp_stats),
            'high_velocity_count': len(high_velocity),
            'bidirectional_count': len(bidirectional),
            'incoming_only_count': len(incoming_only),
            'top_counterparties': cp_stats[:10],
            'high_velocity_counterparties': high_velocity[:10]
        }
    
    def _analyze_product_types(self) -> Dict:
        """Analyze product type diversity"""
        
        product_counts = defaultdict(int)
        product_amounts = defaultdict(float)
        
        for tx in self.transactions:
            if tx.is_paid_out() and tx.product_type:
                product_type = tx.product_type.upper()
                product_counts[product_type] += 1
                product_amounts[product_type] += tx.amount
        
        return {
            'product_types': dict(product_counts),
            'product_amounts': dict(product_amounts),
            'diversity_score': len(product_counts),
            'has_btc': any('BTC' in p or 'BITCOIN' in p for p in product_counts.keys()),
            'has_equities': any('EQUIT' in p or 'STOCK' in p for p in product_counts.keys())
        }
    
    def _analyze_temporal_patterns(self) -> Dict:
        """Analyze temporal patterns"""
        
        velocity_changes = self.temporal_analyzer.detect_velocity_changes()
        time_distribution = self.temporal_analyzer.get_time_of_day_distribution()
        
        return {
            'velocity_changes': velocity_changes,
            'time_of_day_distribution': time_distribution
        }


def analyze_case_final(csv_path: str) -> Dict:
    """Main function to analyze a case with complete system"""
    
    print(f"\n{'#'*70}")
    print(f"# SAR PLATFORM - FINAL INTEGRATED ANALYZER")
    print(f"# With Legitimate Business Detection & False Positive Reduction")
    print(f"{'#'*70}\n")
    
    # Parse CSV
    print("📄 Loading CSV...")
    parser = CSVParser()
    transactions = parser.parse(csv_path)
    
    # Run complete analysis
    print("\n🔍 Running complete analysis...")
    analyzer = FinalAnalyzer(transactions)
    results = analyzer.analyze()
    
    # Display results
    _display_final_results(results)
    
    return results


def _display_final_results(results: Dict):
    """Display complete analysis results"""
    
    stats = results['basic_stats']
    patterns = results['patterns']
    comments = results['comments']
    cps = results['counterparties']
    layering = results['layering']
    products = results['products']
    legitimacy = results['legitimacy']
    override = results['override']
    
    print(f"\n{'='*70}")
    print(f"FINAL ANALYSIS RESULTS")
    print(f"{'='*70}\n")
    
    # Final Recommendation (MOST IMPORTANT)
    print(f"🎯 FINAL RECOMMENDATION: {results['final_recommendation']}")
    print(f"📋 SUSPICIOUS ACTIVITY: {'YES' if results.get('suspicious_activity_detected', False) else 'NO'}\n")
    
    # Legitimacy Analysis
    if legitimacy['is_legitimate']:
        print(f"✅ LEGITIMATE BUSINESS ACTIVITY DETECTED")
        print(f"   Confidence: {legitimacy['confidence']*100:.0f}%")
        print(f"   Business Comments: {legitimacy['business_count']}")
        print(f"   Personal Comments: {legitimacy['personal_count']}")
        print(f"   Legitimacy Rate: {legitimacy['legitimacy_percentage']:.0f}%")
        
        if legitimacy['sample_business_comments']:
            print(f"\n   Sample Business Comments:")
            for c in legitimacy['sample_business_comments'][:5]:
                print(f"      \"{c['comment']}\" ({c['category']})")
        
        print(f"\n   Reasoning:")
        for reason in legitimacy['reasoning']:
            print(f"      - {reason}")
        print()
    
    # Override Decision
    if override['should_override']:
        print(f"⚠️  OVERRIDE: Legitimate business overrides suspicious detection")
        for reason in override['reasoning']:
            print(f"   - {reason}")
        print()
    
    # Typology Detection (if suspicious)
    if results.get('detected_typologies') and not override['should_override']:
        print(f"🚨 DETECTED TYPOLOGIES:")
        for typology, data in results['detected_typologies'].items():
            print(f"   ✓ {typology}: {data['confidence']*100:.1f}% confidence")
            for indicator in data['primary_indicators']:
                print(f"      - {indicator}")
        print()
    
    print(f"📈 TRANSACTION SUMMARY:")
    print(f"   Total Transactions: {stats['total_transactions']}")
    print(f"   Incoming: {stats['incoming_attempts']} attempts (${stats['incoming_total']:,.2f})")
    print(f"   Outgoing: {stats['outgoing_attempts']} attempts (${stats['outgoing_total']:,.2f})")
    print(f"   Net Flow: ${stats['net_flow']:,.2f}")
    print(f"   P2P: {stats['p2p_count']} transactions (${stats['p2p_total']:,.2f})")
    print(f"   Unique Counterparties: {stats['unique_counterparties']}\n")
    
    print(f"🚩 TRANSACTION PATTERNS:")
    print(f"   Round Dollar Amounts: {patterns['round_dollar_pct']:.1f}%")
    print(f"   Under $100: {patterns['under_100_pct']:.1f}%")
    print(f"   Average Amount: ${patterns['average_amount']:.2f}")
    print(f"   Incoming %: {patterns['incoming_pct']:.1f}%\n")
    
    if comments['high_confidence_count'] > 0:
        print(f"💬 DRUG SLANG DETECTED:")
        print(f"   VERY HIGH Confidence: {comments['high_confidence_count']}")
        print(f"   MEDIUM Confidence: {comments['medium_confidence_count']}")
        
        if comments['high_confidence_samples']:
            print(f"\n   Sample High-Confidence Comments:")
            for i, c in enumerate(comments['high_confidence_samples'][:3], 1):
                terms = ', '.join([f"{d['term']}" for d in c['detected_terms'][:3]])
                print(f"   {i}. \"{c['comment']}\" - Terms: {terms}")
        print()
    
    if layering['detected']:
        print(f"🔄 LAYERING DETECTED:")
        print(f"   Confidence: {layering['confidence']*100:.0f}%")
        print(f"   Name Mentions: {layering['name_mention_count']}")
        print(f"   Rapid Forwards: {layering['rapid_forward_count']}\n")
    
    print(f"{'='*70}\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        # Test with the legitimate business case
        csv_path = '/Users/gkirk/Desktop/sar-workflow-test Training CSV\'s/Ht:Prost/NSAR/17899254.csv'
    
    results = analyze_case_final(csv_path)
