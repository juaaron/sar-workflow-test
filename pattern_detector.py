"""
SAR Platform - Advanced Pattern Detection Engine
Sophisticated analysis for detecting suspicious activity patterns
"""

import pandas as pd
import networkx as nx
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Set
import re
from csv_parser import TransactionRecord, CSVParser


class DrugSlangDetector:
    """Detects drug-related terminology in payment comments"""
    
    # Comprehensive drug slang dictionary
    SLANG_TERMS = {
        'marijuana': [
            'weed', 'pot', 'dope', 'grass', 'herb', 'bud', 'ganja', 'mary jane', 
            'chronic', 'reefer', 'za', 'zaza', 'z', 'zzz', 'gas', 'loud', 'fire', 
            'tree', 'green', 'kush', 'dank', 'pack', 'cart', 'cartridge', 'dispo', 
            'dispos', 'dispensary', 'pen', 'vape', 'thc', 'eighth', 'quarter', 
            'half', 'zip', 'ounce', 'blunt', 'joint', 'spliff', 'bowl', 'bong', 
            'dab', 'wax', 'shatter', 'edible', 'candy', 'good', 'food'
        ],
        'cocaine': [
            'coke', 'blow', 'snow', 'powder', 'white', 'yayo', 'nose candy', 
            'flake', 'crack', 'rock', 'base', 'hard', 'soft', 'yay', 'girl', 
            'white girl', 'charlie', 'coca', 'bump', 'line', 'rail', 'eight ball', 
            'ball', 'brick', 'key', 'kilo', 'bird'
        ],
        'heroin': [
            'dope', 'smack', 'h', 'junk', 'tar', 'black', 'boy', 'china white', 
            'skag', 'horse', 'brown', 'mud', 'cheese', 'diesel', 'fent', 'fentanyl', 
            'blues', 'm30', 'percs', 'percocet', 'oxy', 'oxys', 'roxys', 'pills', 
            'tabs', 'beans'
        ],
        'meth': [
            'meth', 'crystal', 'ice', 'glass', 'crank', 'speed', 'tweak', 'tina', 
            'shards', 'clear', 'go fast', 'chalk', 'gak', 'pookie'
        ],
        'mdma': ['molly', 'ecstasy', 'x', 'e', 'rolls', 'beans'],
        'generic': [
            'stuff', 'shit', 'product', 'work', 'supply', 'plug', 'connect', 
            'dealer', 're-up', 'reup', 'cop', 'score', 'grab', 'pick up', 'pickup', 
            'drop', 'serve', 'front', 'spot', 'trap', 'move', 'flip', 'sack', 
            'bag', 'piece', 'weight', 'bundle', 'stash', 'hustle', 'push', 'slang', 
            'deal'
        ],
        'transaction': [
            'otw', 'on the way', 'omw', 'on my way', 'pull up', 'slide', 'swing by', 
            'come through', 'meet up', 'link', 'link up', 'hurry', 'quick', 'asap', 
            'rn', 'right now', 'add me', 'add my snap', 'snapchat', 'snap', 'hmu', 
            'hit me up', 'dm', 'text me', 'call me', 'number', 'contact', 'discreet', 
            'low key', 'lowkey', 'dl', 'down low'
        ]
    }
    
    # Suspicious emojis
    SUSPICIOUS_EMOJIS = ['🌲', '🍃', '🌿', '💨', '🔥', '⛽', '🚀', '🍄', '💊', '💉', 
                         '❄️', '⚪', '🟢', '🔌', '📦', '📫', '💰', '💵', '💴', '🎁', 
                         '🛒', '💚']
    
    def detect(self, comment: str) -> List[Dict]:
        """Detect drug slang in a comment"""
        if not comment or pd.isna(comment):
            return []
        
        comment_lower = comment.lower()
        detected = []
        
        # Check for slang terms
        for category, terms in self.SLANG_TERMS.items():
            for term in terms:
                if re.search(r'\b' + re.escape(term) + r'\b', comment_lower):
                    detected.append({
                        'term': term,
                        'category': category,
                        'type': 'slang'
                    })
        
        # Check for suspicious emojis
        for emoji in self.SUSPICIOUS_EMOJIS:
            if emoji in comment:
                detected.append({
                    'term': emoji,
                    'category': 'emoji',
                    'type': 'emoji'
                })
        
        return detected


class NetworkAnalyzer:
    """Analyzes counterparty networks and relationships"""
    
    def __init__(self, transactions: List[TransactionRecord]):
        self.transactions = transactions
        self.graph = self._build_graph()
    
    def _build_graph(self) -> nx.DiGraph:
        """Build directed graph of transactions"""
        G = nx.DiGraph()
        
        for tx in self.transactions:
            if tx.is_paid_out():
                if tx.is_incoming():
                    # Money flowing from counterparty to subject
                    G.add_edge(tx.counterparty, tx.subject, 
                              amount=tx.amount, date=tx.date)
                else:
                    # Money flowing from subject to counterparty
                    G.add_edge(tx.subject, tx.counterparty, 
                              amount=tx.amount, date=tx.date)
        
        return G
    
    def get_hub_score(self, node: str) -> float:
        """Calculate hub score (how central is this node)"""
        if node not in self.graph:
            return 0.0
        
        # Combine in-degree and out-degree
        in_degree = self.graph.in_degree(node)
        out_degree = self.graph.out_degree(node)
        
        # Hub score: high incoming connections
        return in_degree / (in_degree + out_degree + 1)
    
    def get_counterparty_stats(self, subject: str) -> List[Dict]:
        """Get detailed stats for all counterparties"""
        stats = defaultdict(lambda: {
            'incoming_count': 0,
            'outgoing_count': 0,
            'incoming_total': 0.0,
            'outgoing_total': 0.0,
            'incoming_amounts': [],
            'outgoing_amounts': [],
            'dates': [],
            'failed_count': 0
        })
        
        for tx in self.transactions:
            cp = tx.counterparty
            
            if tx.is_paid_out():
                stats[cp]['dates'].append(tx.date)
                
                if tx.is_incoming():
                    stats[cp]['incoming_count'] += 1
                    stats[cp]['incoming_total'] += tx.amount
                    stats[cp]['incoming_amounts'].append(tx.amount)
                else:
                    stats[cp]['outgoing_count'] += 1
                    stats[cp]['outgoing_total'] += tx.amount
                    stats[cp]['outgoing_amounts'].append(tx.amount)
            elif tx.is_failed():
                stats[cp]['failed_count'] += 1
        
        # Convert to list and sort by total transactions
        result = []
        for cp, data in stats.items():
            total_txs = data['incoming_count'] + data['outgoing_count']
            if total_txs > 0:
                result.append({
                    'counterparty': cp,
                    'total_transactions': total_txs,
                    'incoming_count': data['incoming_count'],
                    'outgoing_count': data['outgoing_count'],
                    'incoming_total': data['incoming_total'],
                    'outgoing_total': data['outgoing_total'],
                    'failed_count': data['failed_count'],
                    'date_range': (min(data['dates']), max(data['dates'])) if data['dates'] else None,
                    'bidirectional': data['incoming_count'] > 0 and data['outgoing_count'] > 0,
                    'incoming_amounts': data['incoming_amounts'],
                    'outgoing_amounts': data['outgoing_amounts']
                })
        
        result.sort(key=lambda x: x['total_transactions'], reverse=True)
        return result


class TemporalAnalyzer:
    """Analyzes temporal patterns in transactions"""
    
    def __init__(self, transactions: List[TransactionRecord]):
        self.transactions = sorted(transactions, key=lambda x: x.date)
    
    def detect_velocity_changes(self) -> List[Dict]:
        """Detect sudden changes in transaction velocity"""
        if len(self.transactions) < 10:
            return []
        
        # Group by day
        daily_counts = defaultdict(int)
        for tx in self.transactions:
            if tx.is_paid_out():
                day = tx.date.date()
                daily_counts[day] += 1
        
        # Calculate rolling average
        days = sorted(daily_counts.keys())
        changes = []
        
        for i in range(7, len(days)):
            prev_week_avg = sum(daily_counts[days[j]] for j in range(i-7, i)) / 7
            current_day = daily_counts[days[i]]
            
            if prev_week_avg > 0 and current_day > prev_week_avg * 2:
                changes.append({
                    'date': days[i],
                    'count': current_day,
                    'previous_avg': prev_week_avg,
                    'increase_factor': current_day / prev_week_avg
                })
        
        return changes
    
    def get_time_of_day_distribution(self) -> Dict[str, int]:
        """Analyze what times of day transactions occur"""
        distribution = {
            'night': 0,      # 12am-6am
            'morning': 0,    # 6am-12pm
            'afternoon': 0,  # 12pm-6pm
            'evening': 0     # 6pm-12am
        }
        
        for tx in self.transactions:
            if tx.is_paid_out():
                hour = tx.date.hour
                if 0 <= hour < 6:
                    distribution['night'] += 1
                elif 6 <= hour < 12:
                    distribution['morning'] += 1
                elif 12 <= hour < 18:
                    distribution['afternoon'] += 1
                else:
                    distribution['evening'] += 1
        
        return distribution


class DrugSalesDetector:
    """Sophisticated detector for illegal drug sales patterns"""
    
    def __init__(self, transactions: List[TransactionRecord]):
        self.transactions = transactions
        self.subject = transactions[0].subject if transactions else None
        self.slang_detector = DrugSlangDetector()
        self.network_analyzer = NetworkAnalyzer(transactions)
        self.temporal_analyzer = TemporalAnalyzer(transactions)
    
    def analyze(self) -> Dict:
        """Perform comprehensive analysis"""
        
        print(f"\n{'='*60}")
        print(f"ANALYZING SUBJECT: {self.subject}")
        print(f"{'='*60}\n")
        
        # Basic stats
        basic_stats = self._calculate_basic_stats()
        
        # Pattern detection
        patterns = self._detect_patterns()
        
        # Comment analysis
        comment_analysis = self._analyze_comments()
        
        # Counterparty analysis
        counterparty_analysis = self._analyze_counterparties()
        
        # Temporal analysis
        temporal_analysis = self._analyze_temporal_patterns()
        
        # Risk scoring
        risk_score = self._calculate_risk_score(
            basic_stats, patterns, comment_analysis, counterparty_analysis
        )
        
        return {
            'subject': self.subject,
            'basic_stats': basic_stats,
            'patterns': patterns,
            'comments': comment_analysis,
            'counterparties': counterparty_analysis,
            'temporal': temporal_analysis,
            'risk_score': risk_score,
            'detected_typology': 'Illegal Drug Sales' if risk_score > 70 else 'Unknown'
        }
    
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
    
    def _analyze_comments(self) -> Dict:
        """Analyze payment comments for drug slang"""
        
        comments_with_slang = []
        all_detected_terms = []
        
        for tx in self.transactions:
            if tx.comment and tx.is_p2p():
                detected = self.slang_detector.detect(tx.comment)
                if detected:
                    comments_with_slang.append({
                        'comment': tx.comment,
                        'counterparty': tx.counterparty,
                        'amount': tx.amount,
                        'date': tx.date,
                        'detected_terms': detected
                    })
                    all_detected_terms.extend(detected)
        
        # Count term frequencies
        term_counts = Counter([d['term'] for d in all_detected_terms])
        category_counts = Counter([d['category'] for d in all_detected_terms])
        
        return {
            'total_comments': len([tx for tx in self.transactions if tx.comment]),
            'comments_with_slang': len(comments_with_slang),
            'sample_comments': comments_with_slang[:10],
            'top_terms': term_counts.most_common(10),
            'categories': dict(category_counts)
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
    
    def _analyze_temporal_patterns(self) -> Dict:
        """Analyze temporal patterns"""
        
        velocity_changes = self.temporal_analyzer.detect_velocity_changes()
        time_distribution = self.temporal_analyzer.get_time_of_day_distribution()
        
        return {
            'velocity_changes': velocity_changes,
            'time_of_day_distribution': time_distribution
        }
    
    def _calculate_risk_score(self, basic_stats: Dict, patterns: Dict, 
                             comments: Dict, counterparties: Dict) -> float:
        """Calculate overall risk score (0-100)"""
        
        score = 0.0
        
        # Round dollar amounts (0-20 points)
        if patterns.get('round_dollar_pct', 0) > 70:
            score += 20
        elif patterns.get('round_dollar_pct', 0) > 50:
            score += 15
        elif patterns.get('round_dollar_pct', 0) > 30:
            score += 10
        
        # Small transactions (0-15 points)
        if patterns.get('under_100_pct', 0) > 85:
            score += 15
        elif patterns.get('under_100_pct', 0) > 70:
            score += 10
        
        # Drug slang in comments (0-25 points)
        slang_pct = (comments.get('comments_with_slang', 0) / 
                    max(comments.get('total_comments', 1), 1)) * 100
        if slang_pct > 20:
            score += 25
        elif slang_pct > 10:
            score += 20
        elif slang_pct > 5:
            score += 15
        elif slang_pct > 0:
            score += 10
        
        # Many-to-one pattern (0-15 points)
        if patterns.get('incoming_pct', 0) > 70:
            score += 15
        elif patterns.get('incoming_pct', 0) > 60:
            score += 10
        
        # High velocity counterparties (0-15 points)
        hv_count = counterparties.get('high_velocity_count', 0)
        if hv_count > 20:
            score += 15
        elif hv_count > 10:
            score += 10
        elif hv_count > 5:
            score += 5
        
        # Unique counterparties (0-10 points)
        unique_cp = basic_stats.get('unique_counterparties', 0)
        if unique_cp > 100:
            score += 10
        elif unique_cp > 50:
            score += 7
        elif unique_cp > 25:
            score += 5
        
        return min(score, 100)


def analyze_case(csv_path: str) -> Dict:
    """Main function to analyze a case"""
    
    print(f"\n{'#'*60}")
    print(f"# SAR PLATFORM - PATTERN DETECTION ENGINE")
    print(f"{'#'*60}\n")
    
    # Parse CSV
    print("📄 Loading CSV...")
    parser = CSVParser()
    transactions = parser.parse(csv_path)
    
    # Run analysis
    print("\n🔍 Running advanced pattern detection...")
    detector = DrugSalesDetector(transactions)
    results = detector.analyze()
    
    # Display results
    _display_results(results)
    
    return results


def _display_results(results: Dict):
    """Display analysis results"""
    
    stats = results['basic_stats']
    patterns = results['patterns']
    comments = results['comments']
    cps = results['counterparties']
    
    print(f"\n{'='*60}")
    print(f"ANALYSIS RESULTS")
    print(f"{'='*60}\n")
    
    print(f"🎯 RISK SCORE: {results['risk_score']:.1f}/100")
    print(f"🏷️  DETECTED TYPOLOGY: {results['detected_typology']}\n")
    
    print(f"📊 TRANSACTION SUMMARY:")
    print(f"   Total Transactions: {stats['total_transactions']}")
    print(f"   Incoming Attempts: {stats['incoming_attempts']} (${stats['incoming_total']:,.2f})")
    print(f"   Outgoing Attempts: {stats['outgoing_attempts']} (${stats['outgoing_total']:,.2f})")
    print(f"   Net Flow: ${stats['net_flow']:,.2f}")
    print(f"   P2P Transactions: {stats['p2p_count']} (${stats['p2p_total']:,.2f})")
    print(f"   Unique Counterparties: {stats['unique_counterparties']}\n")
    
    print(f"🚩 SUSPICIOUS PATTERNS:")
    print(f"   Round Dollar Amounts: {patterns['round_dollar_pct']:.1f}%")
    print(f"   Transactions Under $100: {patterns['under_100_pct']:.1f}%")
    print(f"   Average Transaction: ${patterns['average_amount']:.2f}")
    print(f"   Incoming Transaction %: {patterns['incoming_pct']:.1f}%\n")
    
    print(f"💬 COMMENT ANALYSIS:")
    print(f"   Total Comments: {comments['total_comments']}")
    print(f"   Comments with Drug Slang: {comments['comments_with_slang']}")
    if comments['top_terms']:
        print(f"   Top Terms Detected: {', '.join([t[0] for t in comments['top_terms'][:5]])}\n")
    
    print(f"👥 COUNTERPARTY ANALYSIS:")
    print(f"   High-Velocity Counterparties (5+ txs): {cps['high_velocity_count']}")
    print(f"   Bidirectional Flow: {cps['bidirectional_count']}")
    print(f"   Incoming-Only (Customers): {cps['incoming_only_count']}\n")
    
    if comments['sample_comments']:
        print(f"📝 SAMPLE SUSPICIOUS COMMENTS:")
        for i, c in enumerate(comments['sample_comments'][:5], 1):
            terms = ', '.join([d['term'] for d in c['detected_terms'][:3]])
            print(f"   {i}. \"{c['comment']}\" - Detected: {terms}")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    # Test with new format
    print("\n🧪 Testing with NEW format (23316445.csv)...")
    results = analyze_case('/Users/gkirk/Downloads/23316445.csv')
    
    print("\n\n🧪 Testing with OLD format (B456100271.csv)...")
    results = analyze_case('/Users/gkirk/Desktop/Thu Mar 12 18-47-53 2026/Downloads/B456100271.csv')
