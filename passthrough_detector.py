"""
Pass-Through Money Laundering Detection Module

Detects pass-through/aggregation money laundering schemes where:
- Many incoming P2P payments from different senders
- Few outgoing transfers to payment sources (withdrawals)
- Incoming amounts typically $30-$300
- Outgoing amounts typically $700-$1000
- Rapid aggregation and withdrawal (hours to days)
- Coded/cryptic payment comments
"""

from dataclasses import dataclass
from typing import List, Dict, Set, Tuple
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import re


@dataclass
class PassThroughIndicators:
    """Indicators of pass-through money laundering"""
    # Flow metrics
    incoming_count: int
    outgoing_count: int
    incoming_to_outgoing_ratio: float
    unique_senders: int
    unique_receivers: int
    
    # Amount metrics
    total_incoming: float
    total_outgoing: float
    avg_incoming: float
    avg_outgoing: float
    incoming_in_range: int  # $30-$300
    outgoing_in_range: int  # $700-$1000
    
    # Product type metrics
    incoming_p2p_pct: float
    outgoing_transfer_pct: float
    
    # Timing metrics
    aggregation_velocity: float  # avg hours between incoming and outgoing
    same_day_withdrawals: int
    
    # Comment metrics
    coded_comments_pct: float
    number_only_comments: int
    single_letter_comments: int
    emoji_comments: int
    short_code_comments: int
    
    # Round amounts
    round_incoming_pct: float
    
    # Risk score
    confidence: float
    risk_level: str


class PassThroughDetector:
    """Detects pass-through/aggregation money laundering schemes"""
    
    def __init__(self):
        # Thresholds for detection
        self.MIN_INCOMING_COUNT = 50  # At least 50 incoming transactions
        self.MIN_RATIO = 5.0  # At least 5:1 incoming:outgoing ratio
        self.MIN_UNIQUE_SENDERS = 20  # At least 20 different senders
        self.INCOMING_RANGE = (30, 300)  # Typical incoming range
        self.OUTGOING_RANGE = (700, 1000)  # Typical outgoing range
        self.MIN_CODED_COMMENTS_PCT = 30  # At least 30% coded comments
        
    def analyze(self, transactions: List[Dict]) -> PassThroughIndicators:
        """
        Analyze transactions for pass-through money laundering patterns
        
        Args:
            transactions: List of transaction dictionaries
            
        Returns:
            PassThroughIndicators with detection results
        """
        # Separate incoming and outgoing
        incoming = [t for t in transactions if t.get('direction') == 'IN']
        outgoing = [t for t in transactions if t.get('direction') == 'OUT']
        
        if not incoming or not outgoing:
            return self._create_low_confidence_result()
        
        # Calculate flow metrics
        incoming_count = len(incoming)
        outgoing_count = len(outgoing)
        ratio = incoming_count / outgoing_count if outgoing_count > 0 else 0
        
        unique_senders = len(set(t.get('counterparty', '') for t in incoming))
        unique_receivers = len(set(t.get('counterparty', '') for t in outgoing))
        
        # Calculate amount metrics
        total_incoming = sum(t.get('amount', 0) for t in incoming)
        total_outgoing = sum(t.get('amount', 0) for t in outgoing)
        avg_incoming = total_incoming / incoming_count if incoming_count > 0 else 0
        avg_outgoing = total_outgoing / outgoing_count if outgoing_count > 0 else 0
        
        # Check amount ranges
        incoming_in_range = sum(1 for t in incoming 
                               if self.INCOMING_RANGE[0] <= t.get('amount', 0) <= self.INCOMING_RANGE[1])
        outgoing_in_range = sum(1 for t in outgoing 
                               if self.OUTGOING_RANGE[0] <= t.get('amount', 0) <= self.OUTGOING_RANGE[1])
        
        # Product type analysis
        incoming_p2p = sum(1 for t in incoming if t.get('product_type', '').upper() == 'P2P')
        outgoing_transfers = sum(1 for t in outgoing if 'TRANSFER' in t.get('product_type', '').upper())
        
        incoming_p2p_pct = (incoming_p2p / incoming_count * 100) if incoming_count > 0 else 0
        outgoing_transfer_pct = (outgoing_transfers / outgoing_count * 100) if outgoing_count > 0 else 0
        
        # Timing analysis
        aggregation_velocity, same_day_withdrawals = self._analyze_timing(incoming, outgoing)
        
        # Comment analysis
        comment_metrics = self._analyze_comments(incoming)
        
        # Round amount analysis
        round_incoming = sum(1 for t in incoming if self._is_round_amount(t.get('amount', 0)))
        round_incoming_pct = (round_incoming / incoming_count * 100) if incoming_count > 0 else 0
        
        # Calculate confidence score
        confidence, risk_level = self._calculate_confidence(
            incoming_count, ratio, unique_senders, 
            incoming_in_range, outgoing_in_range,
            incoming_p2p_pct, outgoing_transfer_pct,
            comment_metrics['coded_pct'],
            round_incoming_pct,
            aggregation_velocity
        )
        
        return PassThroughIndicators(
            incoming_count=incoming_count,
            outgoing_count=outgoing_count,
            incoming_to_outgoing_ratio=ratio,
            unique_senders=unique_senders,
            unique_receivers=unique_receivers,
            total_incoming=total_incoming,
            total_outgoing=total_outgoing,
            avg_incoming=avg_incoming,
            avg_outgoing=avg_outgoing,
            incoming_in_range=incoming_in_range,
            outgoing_in_range=outgoing_in_range,
            incoming_p2p_pct=incoming_p2p_pct,
            outgoing_transfer_pct=outgoing_transfer_pct,
            aggregation_velocity=aggregation_velocity,
            same_day_withdrawals=same_day_withdrawals,
            coded_comments_pct=comment_metrics['coded_pct'],
            number_only_comments=comment_metrics['number_only'],
            single_letter_comments=comment_metrics['single_letter'],
            emoji_comments=comment_metrics['emoji'],
            short_code_comments=comment_metrics['short_code'],
            round_incoming_pct=round_incoming_pct,
            confidence=confidence,
            risk_level=risk_level
        )
    
    def _analyze_timing(self, incoming: List[Dict], outgoing: List[Dict]) -> Tuple[float, int]:
        """Analyze timing patterns between incoming and outgoing transactions"""
        if not incoming or not outgoing:
            return 0.0, 0
        
        # Group by date
        from collections import defaultdict
        daily_incoming = defaultdict(list)
        daily_outgoing = defaultdict(list)
        
        for t in incoming:
            date_str = t.get('date', '')
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    date_only = dt.date()
                    daily_incoming[date_only].append(dt)
                except:
                    pass
        
        for t in outgoing:
            date_str = t.get('date', '')
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    date_only = dt.date()
                    daily_outgoing[date_only].append(dt)
                except:
                    pass
        
        # Count same-day withdrawals
        same_day = sum(1 for date in daily_incoming if date in daily_outgoing)
        
        # Calculate average aggregation velocity
        velocities = []
        for date in sorted(daily_incoming.keys()):
            if date in daily_outgoing:
                last_in = max(daily_incoming[date])
                first_out = min(daily_outgoing[date])
                if first_out > last_in:
                    hours = (first_out - last_in).total_seconds() / 3600
                    velocities.append(hours)
        
        avg_velocity = sum(velocities) / len(velocities) if velocities else 0
        
        return avg_velocity, same_day
    
    def _analyze_comments(self, incoming: List[Dict]) -> Dict:
        """Analyze payment comments for coded/cryptic patterns"""
        comments = [t.get('comment', '') for t in incoming if t.get('comment')]
        
        if not comments:
            return {
                'coded_pct': 0,
                'number_only': 0,
                'single_letter': 0,
                'emoji': 0,
                'short_code': 0
            }
        
        number_only = 0
        single_letter = 0
        emoji = 0
        short_code = 0
        
        for comment in comments:
            if not comment or comment in ['.', '..', '...', '....']:
                continue
            
            # Number only (like IDs)
            if re.match(r'^\d+$', comment):
                number_only += 1
            
            # Single letter
            elif re.match(r'^[a-zA-Z]$', comment):
                single_letter += 1
            
            # Short codes (2-3 letters like "rc", "fun", "bag")
            elif re.match(r'^[a-zA-Z]{2,3}$', comment):
                short_code += 1
            
            # Emojis or special characters
            elif re.search(r'[^\w\s,]', comment, re.UNICODE):
                emoji += 1
        
        # Calculate percentage of coded comments
        coded_count = number_only + single_letter + short_code + emoji
        coded_pct = (coded_count / len(comments) * 100) if comments else 0
        
        return {
            'coded_pct': coded_pct,
            'number_only': number_only,
            'single_letter': single_letter,
            'emoji': emoji,
            'short_code': short_code
        }
    
    def _is_round_amount(self, amount: float) -> bool:
        """Check if amount is a round number"""
        return amount % 5 == 0 or amount % 10 == 0
    
    def _calculate_confidence(
        self,
        incoming_count: int,
        ratio: float,
        unique_senders: int,
        incoming_in_range: int,
        outgoing_in_range: int,
        incoming_p2p_pct: float,
        outgoing_transfer_pct: float,
        coded_comments_pct: float,
        round_incoming_pct: float,
        aggregation_velocity: float
    ) -> Tuple[float, str]:
        """Calculate confidence score for pass-through money laundering"""
        
        score = 0.0
        max_score = 100.0
        
        # Flow pattern (30 points)
        if incoming_count >= self.MIN_INCOMING_COUNT:
            score += 10
        if ratio >= self.MIN_RATIO:
            score += 10
        if unique_senders >= self.MIN_UNIQUE_SENDERS:
            score += 10
        
        # Amount patterns (25 points)
        if incoming_count > 0:
            in_range_pct = (incoming_in_range / incoming_count * 100)
            if in_range_pct >= 50:
                score += 12
        
        if outgoing_in_range > 0:
            score += 13
        
        # Product types (15 points)
        if incoming_p2p_pct >= 90:
            score += 8
        if outgoing_transfer_pct >= 90:
            score += 7
        
        # Comment patterns (20 points)
        if coded_comments_pct >= self.MIN_CODED_COMMENTS_PCT:
            score += 20
        elif coded_comments_pct >= 20:
            score += 10
        
        # Round amounts (10 points)
        if round_incoming_pct >= 70:
            score += 10
        elif round_incoming_pct >= 50:
            score += 5
        
        # Normalize to 0-100
        confidence = min(score, max_score)
        
        # Determine risk level
        if confidence >= 80:
            risk_level = "CRITICAL"
        elif confidence >= 60:
            risk_level = "HIGH"
        elif confidence >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return confidence, risk_level
    
    def _create_low_confidence_result(self) -> PassThroughIndicators:
        """Create a low confidence result when data is insufficient"""
        return PassThroughIndicators(
            incoming_count=0,
            outgoing_count=0,
            incoming_to_outgoing_ratio=0,
            unique_senders=0,
            unique_receivers=0,
            total_incoming=0,
            total_outgoing=0,
            avg_incoming=0,
            avg_outgoing=0,
            incoming_in_range=0,
            outgoing_in_range=0,
            incoming_p2p_pct=0,
            outgoing_transfer_pct=0,
            aggregation_velocity=0,
            same_day_withdrawals=0,
            coded_comments_pct=0,
            number_only_comments=0,
            single_letter_comments=0,
            emoji_comments=0,
            short_code_comments=0,
            round_incoming_pct=0,
            confidence=0,
            risk_level="LOW"
        )
    
    def format_analysis(self, indicators: PassThroughIndicators) -> str:
        """Format analysis results as human-readable text"""
        
        lines = [
            "=== PASS-THROUGH MONEY LAUNDERING ANALYSIS ===",
            "",
            f"🎯 CONFIDENCE: {indicators.confidence:.1f}% ({indicators.risk_level})",
            "",
            "📊 FLOW PATTERN:",
            f"  • Incoming transactions: {indicators.incoming_count:,}",
            f"  • Outgoing transactions: {indicators.outgoing_count:,}",
            f"  • Ratio: {indicators.incoming_to_outgoing_ratio:.1f}:1",
            f"  • Unique senders: {indicators.unique_senders:,}",
            f"  • Unique receivers: {indicators.unique_receivers:,}",
            "",
            "💰 AMOUNT ANALYSIS:",
            f"  • Total incoming: ${indicators.total_incoming:,.2f}",
            f"  • Total outgoing: ${indicators.total_outgoing:,.2f}",
            f"  • Avg incoming: ${indicators.avg_incoming:.2f}",
            f"  • Avg outgoing: ${indicators.avg_outgoing:.2f}",
            f"  • Incoming in $30-$300 range: {indicators.incoming_in_range:,} ({indicators.incoming_in_range/indicators.incoming_count*100:.1f}%)" if indicators.incoming_count > 0 else "  • Incoming in $30-$300 range: 0",
            f"  • Outgoing in $700-$1000 range: {indicators.outgoing_in_range:,} ({indicators.outgoing_in_range/indicators.outgoing_count*100:.1f}%)" if indicators.outgoing_count > 0 else "  • Outgoing in $700-$1000 range: 0",
            "",
            "📦 PRODUCT TYPES:",
            f"  • Incoming P2P: {indicators.incoming_p2p_pct:.1f}%",
            f"  • Outgoing Transfers: {indicators.outgoing_transfer_pct:.1f}%",
            "",
            "⏱️ TIMING:",
            f"  • Same-day withdrawals: {indicators.same_day_withdrawals}",
            f"  • Avg aggregation velocity: {indicators.aggregation_velocity:.1f} hours",
            "",
            "💬 COMMENT PATTERNS:",
            f"  • Coded comments: {indicators.coded_comments_pct:.1f}%",
            f"  • Number-only: {indicators.number_only_comments:,}",
            f"  • Single letter: {indicators.single_letter_comments:,}",
            f"  • Emoji/symbols: {indicators.emoji_comments:,}",
            f"  • Short codes: {indicators.short_code_comments:,}",
            "",
            "🔢 OTHER INDICATORS:",
            f"  • Round incoming amounts: {indicators.round_incoming_pct:.1f}%",
            ""
        ]
        
        return "\n".join(lines)


def detect_passthrough(transactions: List[Dict]) -> Tuple[bool, float, PassThroughIndicators]:
    """
    Convenience function to detect pass-through money laundering
    
    Args:
        transactions: List of transaction dictionaries
        
    Returns:
        Tuple of (is_passthrough, confidence, indicators)
    """
    detector = PassThroughDetector()
    indicators = detector.analyze(transactions)
    
    is_passthrough = indicators.confidence >= 60  # 60% threshold for detection
    
    return is_passthrough, indicators.confidence, indicators
