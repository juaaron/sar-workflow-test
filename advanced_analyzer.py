"""
SAR Platform - Advanced Multi-Typology Analyzer
Integrates context-aware detection with multi-typology support
"""

from csv_parser import CSVParser, TransactionRecord
from pattern_detector import NetworkAnalyzer, TemporalAnalyzer
from context_aware_detector import WeightedSlangDetector, LayeringDetector, MultiTypologyDetector
from typing import List, Dict
from collections import defaultdict


class AdvancedAnalyzer:
    """
    Comprehensive analyzer with context-aware detection and multi-typology support
    """
    
    def __init__(self, transactions: List[TransactionRecord]):
        self.transactions = transactions
        self.subject = transactions[0].subject if transactions else None
        
        # Initialize detectors
        self.slang_detector = WeightedSlangDetector()
        self.layering_detector = LayeringDetector()
        self.multi_typology = MultiTypologyDetector()
        self.network_analyzer = NetworkAnalyzer(transactions)
        self.temporal_analyzer = TemporalAnalyzer(transactions)
    
    def analyze(self) -> Dict:
        """Perform comprehensive multi-typology analysis"""
        
        print(f"\n{'='*70}")
        print(f"ADVANCED MULTI-TYPOLOGY ANALYSIS")
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
        
        # Multi-typology detection
        typology_results = self.multi_typology.detect_typologies(
            self.transactions, analysis_results
        )
        
        analysis_results.update(typology_results)
        
        return analysis_results
    
    def _calculate_basic_stats(self) -> Dict:
        """Calculate basic transaction statistics"""
        
        incoming_txs = [tx for tx in self.transactions if tx.is_incoming()]
        outgoing_txs = [tx for tx in self.transactions if tx.is_outgoing()]
        
        incoming_paid = [tx for tx in incoming_txs if tx.is_paid_out()]
        outgoing_paid = [tx for tx in outgoing_txs if tx.is_paid_out()]
        
        incoming_failed = [tx for tx in incoming_txs if tx.is_failed()]
        outgoing_failed = [tx for tx in outgoing_txs if tx.is_failed()]
        
        p2p_txs = [tx for tx in self.transactions if tx.is_p2p() and tx.is_paid_out()]
        
        return {
            'total_transactions': len(self.transactions),
            'incoming_attempts': len(incoming_txs),
            'outgoing_attempts': len(outgoing_txs),
            'incoming_paid_count': len(incoming_paid),
            'outgoing_paid_count': len(outgoing_paid),
            'incoming_failed_count': len(incoming_failed),
            'outgoing_failed_count': len(outgoing_failed),
            'incoming_total': sum(tx.amount for tx in incoming_paid),
            'outgoing_total': sum(tx.amount for tx in outgoing_paid),
            'net_flow': sum(tx.amount for tx in incoming_paid) - sum(tx.amount for tx in outgoing_paid),
            'p2p_count': len(p2p_txs),
            'p2p_total': sum(tx.amount for tx in p2p_txs),
            'unique_counterparties': len(set(tx.counterparty for tx in self.transactions)),
            'date_range': (
                min(tx.date for tx in self.transactions),
                max(tx.date for tx in self.transactions)
            ) if self.transactions else None
        }
    
    def _detect_patterns(self) -> Dict:
        """Detect suspicious patterns"""
        
        paid_txs = [tx for tx in self.transactions if tx.is_paid_out()]
        amounts = [tx.amount for tx in paid_txs]
        
        if not amounts:
            return {}
        
        # Round dollar amounts
        round_amounts = [a for a in amounts if a == int(a) and 10 <= a <= 150]
        round_pct = (len(round_amounts) / len(amounts)) * 100 if amounts else 0
        
        # Small transactions
        under_100 = [a for a in amounts if a <= 100]
        under_100_pct = (len(under_100) / len(amounts)) * 100 if amounts else 0
        
        # Average amount
        avg_amount = sum(amounts) / len(amounts) if amounts else 0
        
        # Incoming vs outgoing ratio
        incoming_paid = [tx for tx in paid_txs if tx.is_incoming()]
        incoming_pct = (len(incoming_paid) / len(paid_txs)) * 100 if paid_txs else 0
        
        return {
            'round_dollar_pct': round_pct,
            'under_100_pct': under_100_pct,
            'average_amount': avg_amount,
            'incoming_pct': incoming_pct,
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
        """Analyze comments with context-aware detection"""
        
        # Get counterparty stats for context
        cp_stats = self.network_analyzer.get_counterparty_stats(self.subject)
        cp_velocity = {cp['counterparty']: cp['total_transactions'] for cp in cp_stats}
        
        total_cps = len(cp_stats)
        
        high_confidence_comments = []
        medium_confidence_comments = []
        low_confidence_comments = []
        all_detected_terms = []
        
        for tx in self.transactions:
            if tx.comment and tx.is_p2p() and tx.is_paid_out():
                # Build context
                context = {
                    'amount': tx.amount,
                    'is_incoming': tx.is_incoming(),
                    'counterparty_velocity': cp_velocity.get(tx.counterparty, 0),
                    'total_counterparties': total_cps
                }
                
                # Detect with context
                result = self.slang_detector.detect_with_context(tx.comment, context)
                
                if result['detected']:
                    comment_data = {
                        'comment': tx.comment,
                        'counterparty': tx.counterparty,
                        'amount': tx.amount,
                        'date': tx.date,
                        'confidence': result['confidence'],
                        'confidence_level': self.slang_detector.categorize_confidence(result['confidence']),
                        'context_score': result['context_score'],
                        'detected_terms': result['detected']
                    }
                    
                    # Categorize by confidence
                    if result['confidence'] >= 0.85:
                        high_confidence_comments.append(comment_data)
                    elif result['confidence'] >= 0.50:
                        medium_confidence_comments.append(comment_data)
                    else:
                        low_confidence_comments.append(comment_data)
                    
                    all_detected_terms.extend(result['detected'])
        
        # Count term frequencies
        from collections import Counter
        term_counts = Counter([d['term'] for d in all_detected_terms])
        
        return {
            'total_comments': len([tx for tx in self.transactions if tx.comment]),
            'high_confidence_count': len(high_confidence_comments),
            'medium_confidence_count': len(medium_confidence_comments),
            'low_confidence_count': len(low_confidence_comments),
            'total_detected': len(high_confidence_comments) + len(medium_confidence_comments) + len(low_confidence_comments),
            'high_confidence_samples': high_confidence_comments[:10],
            'medium_confidence_samples': medium_confidence_comments[:5],
            'top_terms': term_counts.most_common(10)
        }
    
    def _analyze_counterparties(self) -> Dict:
        """Analyze counterparty patterns"""
        
        cp_stats = self.network_analyzer.get_counterparty_stats(self.subject)
        
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


def analyze_case_advanced(csv_path: str) -> Dict:
    """Main function to analyze a case with advanced detection"""
    
    print(f"\n{'#'*70}")
    print(f"# SAR PLATFORM - ADVANCED MULTI-TYPOLOGY ANALYZER")
    print(f"{'#'*70}\n")
    
    # Parse CSV
    print("📄 Loading CSV...")
    parser = CSVParser()
    transactions = parser.parse(csv_path)
    
    # Run advanced analysis
    print("\n🔍 Running advanced multi-typology analysis...")
    analyzer = AdvancedAnalyzer(transactions)
    results = analyzer.analyze()
    
    # Display results
    _display_advanced_results(results)
    
    return results


def _display_advanced_results(results: Dict):
    """Display advanced analysis results"""
    
    stats = results['basic_stats']
    patterns = results['patterns']
    comments = results['comments']
    cps = results['counterparties']
    layering = results['layering']
    products = results['products']
    
    print(f"\n{'='*70}")
    print(f"ANALYSIS RESULTS")
    print(f"{'='*70}\n")
    
    # Typology Detection
    print(f"🎯 DETECTED TYPOLOGIES:")
    if results.get('detected_typologies'):
        for typology, data in results['detected_typologies'].items():
            print(f"   ✓ {typology}: {data['confidence']*100:.1f}% confidence")
            for indicator in data['primary_indicators']:
                print(f"      - {indicator}")
    else:
        print(f"   No suspicious typologies detected")
    
    print(f"\n📊 PRIMARY TYPOLOGY: {results.get('primary_typology', 'Unknown')}")
    print(f"   Confidence: {results.get('primary_confidence', 0)*100:.1f}%\n")
    
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
    
    print(f"💬 CONTEXT-AWARE COMMENT ANALYSIS:")
    print(f"   Total Comments: {comments['total_comments']}")
    print(f"   VERY HIGH Confidence: {comments['high_confidence_count']}")
    print(f"   MEDIUM Confidence: {comments['medium_confidence_count']}")
    print(f"   LOW Confidence: {comments['low_confidence_count']}")
    
    if comments['high_confidence_samples']:
        print(f"\n   📝 HIGH CONFIDENCE SAMPLES:")
        for i, c in enumerate(comments['high_confidence_samples'][:5], 1):
            terms = ', '.join([f"{d['term']} ({d['final_confidence']:.2f})" 
                             for d in c['detected_terms'][:3]])
            print(f"   {i}. \"{c['comment']}\"")
            print(f"      Confidence: {c['confidence']:.2f} | Context: {c['context_score']:.2f}x | Terms: {terms}")
    
    print(f"\n🔄 LAYERING ANALYSIS:")
    if layering['detected']:
        print(f"   ⚠️  LAYERING DETECTED (Confidence: {layering['confidence']*100:.1f}%)")
        print(f"   Name Mentions: {layering['name_mention_count']}")
        print(f"   Vague Comments: {layering['vague_comment_count']}")
        print(f"   Rapid Forwards: {layering['rapid_forward_count']}")
        
        if layering['name_mentions']:
            print(f"\n   Sample Name Mentions:")
            for nm in layering['name_mentions'][:5]:
                print(f"      \"{nm['comment']}\" - Names: {', '.join(nm['names'])}")
    else:
        print(f"   No significant layering patterns detected")
    
    print(f"\n📦 PRODUCT TYPE ANALYSIS:")
    print(f"   Product Diversity: {products['diversity_score']} types")
    for ptype, count in products['product_types'].items():
        amount = products['product_amounts'][ptype]
        print(f"   - {ptype}: {count} transactions (${amount:,.2f})")
    
    if products['has_btc']:
        print(f"   ⚠️  BTC transactions detected (potential laundering)")
    if products['has_equities']:
        print(f"   ⚠️  Equities trades detected (potential obfuscation)")
    
    print(f"\n👥 COUNTERPARTY ANALYSIS:")
    print(f"   High-Velocity (5+ txs): {cps['high_velocity_count']}")
    print(f"   Bidirectional Flow: {cps['bidirectional_count']}")
    print(f"   Incoming-Only: {cps['incoming_only_count']}")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        # Test with B3D4FAB9AE
        csv_path = '/Users/gkirk/Desktop/kitt Training CSV\'s/Drug Sales/SAR/B3D4FAB9AE.csv'
    
    results = analyze_case_advanced(csv_path)
