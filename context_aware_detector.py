"""
SAR Platform - Context-Aware Pattern Detection
Sophisticated detection that considers context, not just keywords
"""

from typing import List, Dict, Tuple
from collections import Counter
import re


class WeightedSlangDetector:
    """
    Context-aware drug slang detector with confidence weighting
    
    Terms are weighted by confidence:
    - HIGH (0.9-1.0): Almost always drugs (za, cart, dispo, plug)
    - MEDIUM (0.5-0.7): Often drugs but context-dependent (gas, food, candy)
    - LOW (0.3-0.5): Ambiguous, needs strong context (good, stuff)
    
    Context boosters increase confidence:
    - Round dollar amounts ($10-$100)
    - Many-to-one payment pattern
    - High velocity counterparty
    - Multiple slang terms in same comment
    - Suspicious emojis
    """
    
    # High confidence terms - almost always drugs
    HIGH_CONFIDENCE = {
        'za': 0.95, 'zaza': 0.95, 'z': 0.85, 'zzz': 0.90,
        'cart': 0.90, 'cartridge': 0.90, 'dispo': 0.95, 'dispos': 0.95,
        'plug': 0.95, 'weed': 0.95, 'bud': 0.90, 'dank': 0.90,
        'eighth': 0.95, 'quarter': 0.95, 'ounce': 0.95, 'zip': 0.90,
        'dab': 0.90, 'wax': 0.85, 'shatter': 0.90, 'edible': 0.85,
        'coke': 0.95, 'blow': 0.95, 'snow': 0.90, 'yayo': 0.95,
        'molly': 0.95, 'ecstasy': 0.95, 'percs': 0.95, 'oxys': 0.95,
        'meth': 0.95, 'crystal': 0.85, 'ice': 0.80,
        'addys': 0.90, 'addy': 0.90, 'gummies': 0.75,
        'tree': 0.85, 'loud': 0.85, 'fire': 0.80, 'pack': 0.75,
        'flower': 0.85, 'seamoss': 0.85, 'sea moss': 0.85
    }
    
    # Medium confidence - often drugs but context-dependent
    MEDIUM_CONFIDENCE = {
        'candy': 0.65, 'candies': 0.65,
        'good': 0.55, 'stuff': 0.60, 'green': 0.65, 'white': 0.60,
        'blue': 0.55, 'product': 0.65, 'work': 0.60, 'supply': 0.70,
        'bag': 0.65, 'sack': 0.70, 'piece': 0.60
    }
    
    # Highly ambiguous terms — everyday words that CAN mean drugs but usually don't.
    # Base weight is LOW. Context (round amounts, other drug flags) boosts them.
    # Non-round amounts REDUCE them further.
    AMBIGUOUS_DRUG_TERMS = {
        'gas': 0.35, 'food': 0.35,
    }
    
    # Low confidence - very ambiguous
    LOW_CONFIDENCE = {
        'gift': 0.40, 'thanks': 0.35, 'appreciate': 0.35,
        'owe': 0.45, 'boss': 0.40, 'bro': 0.40
    }
    
    # Transaction-related terms (indicate drug dealing context)
    TRANSACTION_TERMS = {
        'otw': 0.75, 'on the way': 0.75, 'omw': 0.75, 'on my way': 0.75,
        'pull up': 0.80, 'slide': 0.75, 'swing by': 0.70, 'come through': 0.70,
        'meet up': 0.65, 'link': 0.70, 'link up': 0.70, 'hurry': 0.60,
        'add snap': 0.85, 'add my snap': 0.85, 'snapchat': 0.75, 'snap': 0.65,
        'hmu': 0.70, 'hit me up': 0.70, 'text me': 0.60, 'call me': 0.60,
        'discreet': 0.85, 'low key': 0.80, 'lowkey': 0.80, 'dl': 0.75
    }
    
    # Suspicious emojis
    EMOJI_CONFIDENCE = {
        '🌲': 0.95, '🍃': 0.90, '🌿': 0.90, '💨': 0.85, '🔥': 0.75,
        '⛽': 0.80, '🚀': 0.70, '🍄': 0.85, '💊': 0.95, '💉': 0.95,
        '❄️': 0.90, '⚪': 0.75, '🟢': 0.80, '💚': 0.75,
        '🔌': 0.85, '📦': 0.70, '💰': 0.65, '💵': 0.65
    }
    
    def __init__(self):
        # Combine all dictionaries
        self.all_terms = {
            **self.HIGH_CONFIDENCE,
            **self.MEDIUM_CONFIDENCE,
            **self.AMBIGUOUS_DRUG_TERMS,
            **self.LOW_CONFIDENCE,
            **self.TRANSACTION_TERMS
        }
    
    def detect_with_context(self, comment: str, context: Dict) -> Dict:
        """
        Detect slang with context awareness
        
        Args:
            comment: Payment comment text
            context: Dict with keys:
                - amount: Transaction amount
                - is_incoming: Bool, is this incoming to subject
                - counterparty_velocity: Number of transactions with this counterparty
                - total_counterparties: Total unique counterparties for subject
        
        Returns:
            Dict with detection results and confidence scores
        """
        if not comment or not isinstance(comment, str):
            return {'detected': [], 'confidence': 0.0, 'context_score': 0.0}
        
        comment_lower = comment.lower()
        detected_terms = []
        
        # Detect text terms
        for term, base_confidence in self.all_terms.items():
            # Use word boundaries for better matching
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, comment_lower):
                detected_terms.append({
                    'term': term,
                    'base_confidence': base_confidence,
                    'type': 'text'
                })
        
        # Detect emojis
        for emoji, confidence in self.EMOJI_CONFIDENCE.items():
            if emoji in comment:
                detected_terms.append({
                    'term': emoji,
                    'base_confidence': confidence,
                    'type': 'emoji'
                })
        
        if not detected_terms:
            return {'detected': [], 'confidence': 0.0, 'context_score': 0.0}
        
        # Calculate context score
        context_score = self._calculate_context_score(context, detected_terms)
        
        # Apply context multiplier to each term
        for term_data in detected_terms:
            term_data['context_multiplier'] = context_score
            term_data['final_confidence'] = min(
                term_data['base_confidence'] * context_score,
                1.0
            )
        
        # Overall confidence is max of individual terms
        max_confidence = max(t['final_confidence'] for t in detected_terms)
        
        return {
            'detected': detected_terms,
            'confidence': max_confidence,
            'context_score': context_score,
            'comment': comment
        }
    
    def _calculate_context_score(self, context: Dict, detected_terms: List[Dict]) -> float:
        """
        Calculate context multiplier based on transaction patterns.
        
        Returns multiplier between 0.3 (very weak) and 2.0 (very strong).
        
        Special handling for ambiguous terms ("gas", "food"):
        - Round dollar amount → boost (more likely drug slang)
        - Non-round dollar amount → penalize (more likely literal)
        - No other drug terms in account → penalize
        """
        multiplier = 1.0
        amount = context.get('amount', 0)
        is_round = amount > 0 and amount == int(amount)
        
        # Check if ONLY ambiguous terms are detected (no strong drug terms)
        ambiguous_terms = {'gas', 'food'}
        only_ambiguous = all(
            t['term'] in ambiguous_terms for t in detected_terms if t['type'] == 'text'
        )
        
        # For ambiguous-only detections, amount rounding matters a LOT
        if only_ambiguous:
            if is_round and 10 <= amount <= 100:
                multiplier += 0.4  # Round $10-$100 with "gas"/"food" = more suspicious
            elif is_round and 1 <= amount <= 500:
                multiplier += 0.2  # Round but outside sweet spot
            else:
                multiplier -= 0.4  # Non-round amount = probably literal food/gas
        else:
            # Normal round-amount boost for non-ambiguous terms
            if is_round and 10 <= amount <= 100:
                multiplier += 0.3
            elif is_round and 1 <= amount <= 150:
                multiplier += 0.2
        
        # Incoming payment (receiving money = potential sale)
        if context.get('is_incoming', False):
            multiplier += 0.2
        
        # High velocity counterparty (5+ transactions)
        velocity = context.get('counterparty_velocity', 0)
        if velocity >= 10:
            multiplier += 0.3
        elif velocity >= 5:
            multiplier += 0.2
        
        # Many counterparties (dealer pattern)
        total_cps = context.get('total_counterparties', 0)
        if total_cps > 100:
            multiplier += 0.3
        elif total_cps > 50:
            multiplier += 0.2
        elif total_cps > 25:
            multiplier += 0.1
        
        # Multiple slang terms in same comment (strong indicator)
        if len(detected_terms) >= 3:
            multiplier += 0.4
        elif len(detected_terms) >= 2:
            multiplier += 0.2
        
        # High confidence terms present (za, weed, cart, plug, etc.)
        high_conf_terms = [t for t in detected_terms if t['base_confidence'] >= 0.85]
        if high_conf_terms:
            multiplier += 0.2
        
        # If ONLY ambiguous terms and no other strong signals, cap low
        if only_ambiguous and not context.get('is_incoming', False) and velocity < 5:
            multiplier = min(multiplier, 0.8)
        
        # Cap multiplier
        return max(0.3, min(multiplier, 2.0))
    
    def categorize_confidence(self, confidence: float) -> str:
        """Categorize confidence level"""
        if confidence >= 0.85:
            return "VERY HIGH"
        elif confidence >= 0.70:
            return "HIGH"
        elif confidence >= 0.50:
            return "MEDIUM"
        elif confidence >= 0.30:
            return "LOW"
        else:
            return "VERY LOW"


class LayeringDetector:
    """
    Detects money laundering layering patterns
    
    Indicators:
    - Name mentions in comments (forwarding to others)
    - Rapid receive → send patterns
    - Vague/ambiguous comments
    - Multiple product types (P2P + BTC + Equities)
    """
    
    # Common first names that indicate forwarding
    COMMON_NAMES = [
        'john', 'mike', 'chris', 'david', 'james', 'robert', 'michael',
        'william', 'richard', 'joseph', 'thomas', 'charles', 'daniel',
        'matthew', 'anthony', 'mark', 'donald', 'steven', 'paul', 'andrew',
        'joshua', 'kenneth', 'kevin', 'brian', 'george', 'edward', 'ronald',
        'timothy', 'jason', 'jeffrey', 'ryan', 'jacob', 'gary', 'nicholas',
        'eric', 'jonathan', 'stephen', 'larry', 'justin', 'scott', 'brandon',
        'mary', 'patricia', 'jennifer', 'linda', 'elizabeth', 'barbara',
        'susan', 'jessica', 'sarah', 'karen', 'nancy', 'lisa', 'betty',
        'margaret', 'sandra', 'ashley', 'kimberly', 'emily', 'donna',
        'michelle', 'dorothy', 'carol', 'amanda', 'melissa', 'deborah',
        'stephanie', 'rebecca', 'sharon', 'laura', 'cynthia', 'kathleen',
        'amy', 'angela', 'shirley', 'anna', 'brenda', 'pamela', 'nicole',
        'julie', 'sam', 'alex', 'tyler', 'taylor', 'jordan', 'casey',
        'morgan', 'riley', 'jamie', 'nikko', 'ray', 'lee'
    ]
    
    # Vague/ambiguous terms
    VAGUE_TERMS = [
        'gift', 'thanks', 'appreciate', 'owe', 'only', 'just because',
        'here', 'there', 'stuff', 'thing', 'things', 'that', 'this'
    ]
    
    def detect_name_mentions(self, comment: str) -> List[str]:
        """Detect name mentions in comments"""
        if not comment:
            return []
        
        comment_lower = comment.lower()
        found_names = []
        
        for name in self.COMMON_NAMES:
            # Look for name as separate word
            pattern = r'\b' + re.escape(name) + r'\b'
            if re.search(pattern, comment_lower):
                found_names.append(name)
        
        return found_names
    
    def detect_vague_comments(self, comment: str) -> bool:
        """Check if comment is vague/ambiguous"""
        if not comment:
            return True  # Empty comment is vague
        
        comment_lower = comment.lower()
        
        # Check for vague terms
        for term in self.VAGUE_TERMS:
            if term in comment_lower:
                return True
        
        # Very short comments are often vague
        if len(comment.strip()) <= 3:
            return True
        
        return False
    
    def analyze_layering_patterns(self, transactions: List, subject: str) -> Dict:
        """
        Analyze transactions for layering patterns
        
        Returns:
            Dict with layering indicators and confidence
        """
        name_mentions = []
        vague_comments = []
        rapid_forwards = []
        
        # Group by date for rapid forwarding detection
        from collections import defaultdict
        from datetime import timedelta
        
        daily_activity = defaultdict(lambda: {'incoming': [], 'outgoing': []})
        
        for tx in transactions:
            if not hasattr(tx, 'is_paid_out') or not tx.is_paid_out():
                continue
            
            date_key = tx.date.date()
            
            # Check comment for names
            if tx.comment:
                names = self.detect_name_mentions(tx.comment)
                if names:
                    name_mentions.append({
                        'comment': tx.comment,
                        'names': names,
                        'date': tx.date,
                        'amount': tx.amount
                    })
                
                # Check for vague comments
                if self.detect_vague_comments(tx.comment):
                    vague_comments.append({
                        'comment': tx.comment,
                        'date': tx.date,
                        'amount': tx.amount
                    })
            
            # Track daily activity
            if tx.is_incoming():
                daily_activity[date_key]['incoming'].append(tx)
            else:
                daily_activity[date_key]['outgoing'].append(tx)
        
        # Detect rapid forwarding (receive and send on same day)
        for date, activity in daily_activity.items():
            if activity['incoming'] and activity['outgoing']:
                # Calculate time differences
                for inc_tx in activity['incoming']:
                    for out_tx in activity['outgoing']:
                        time_diff = abs((out_tx.date - inc_tx.date).total_seconds() / 3600)
                        if time_diff <= 24:  # Within 24 hours
                            rapid_forwards.append({
                                'date': date,
                                'incoming_amount': inc_tx.amount,
                                'outgoing_amount': out_tx.amount,
                                'time_diff_hours': time_diff
                            })
        
        # Calculate layering confidence
        confidence = 0.0
        
        if len(name_mentions) > 10:
            confidence += 0.4
        elif len(name_mentions) > 5:
            confidence += 0.3
        elif len(name_mentions) > 0:
            confidence += 0.2
        
        if len(vague_comments) > 50:
            confidence += 0.3
        elif len(vague_comments) > 20:
            confidence += 0.2
        
        if len(rapid_forwards) > 20:
            confidence += 0.3
        elif len(rapid_forwards) > 10:
            confidence += 0.2
        
        return {
            'detected': confidence > 0.3,
            'confidence': min(confidence, 1.0),
            'name_mentions': name_mentions[:20],  # Top 20
            'name_mention_count': len(name_mentions),
            'vague_comment_count': len(vague_comments),
            'rapid_forward_count': len(rapid_forwards),
            'sample_rapid_forwards': rapid_forwards[:10]
        }


class MultiTypologyDetector:
    """
    Detects multiple typologies simultaneously
    """
    
    def __init__(self):
        self.slang_detector = WeightedSlangDetector()
        self.layering_detector = LayeringDetector()
        
        # Import gambling detector
        try:
            from gambling_detector import GamblingDetector
            self.gambling_detector = GamblingDetector()
        except:
            self.gambling_detector = None
        
        # Import adult services detector
        try:
            from adult_services_detector import AdultServicesDetector
            self.adult_services_detector = AdultServicesDetector()
        except:
            self.adult_services_detector = None
    
    def detect_typologies(self, transactions: List, analysis_results: Dict) -> Dict:
        """
        Detect all applicable typologies
        
        Returns:
            Dict with detected typologies and confidence scores
        """
        typologies = {}
        
        # Gambling Detection (check first - very specific patterns)
        # Only flags FACILITATION as suspicious, not PARTICIPATION
        gambling_analysis = None
        if self.gambling_detector:
            gambling_analysis = self.gambling_detector.analyze_gambling_activity(transactions)
            if gambling_analysis['detected']:
                # Only facilitation triggers a typology flag
                typologies['Gambling Facilitation'] = {
                    'confidence': gambling_analysis['confidence'],
                    'primary_indicators': gambling_analysis['indicators'],
                    'details': gambling_analysis
                }
        
        # Adult Services Detection
        adult_analysis = None
        if self.adult_services_detector:
            adult_analysis = self.adult_services_detector.analyze_adult_services(transactions)
            if adult_analysis['detected']:
                typologies['Adult Services'] = {
                    'confidence': adult_analysis['confidence'],
                    'primary_indicators': adult_analysis['indicators'],
                    'details': adult_analysis
                }
        
        # Check if gambling was detected (facilitation or participation)
        # If so, suppress drug sales and ML detection — gambling facilitation
        # has the same patterns (many-to-one, small amounts, round dollars)
        # and would cause false positives for drug sales / ML
        is_gambling_participation = (
            gambling_analysis and 
            gambling_analysis['classification'] == 'participation' and
            gambling_analysis.get('p2p_risk', {}).get('risk', 'high') in ('low', 'moderate')
        )
        
        is_gambling_facilitation = (
            gambling_analysis and
            gambling_analysis['classification'] == 'facilitation' and
            gambling_analysis['confidence'] >= 0.5
        )
        
        # Adult services does NOT suppress other typologies.
        # A case can have both adult services AND money laundering.
        # Only gambling suppresses drug sales/ML (because the patterns overlap).
        suppress_other_typologies = is_gambling_participation or is_gambling_facilitation
        
        # Drug Sales Detection
        # Skip if gambling detected (facilitation looks identical to drug sales pattern)
        if not suppress_other_typologies:
            drug_sales_score = self._calculate_drug_sales_score(
                transactions, analysis_results
            )
            if drug_sales_score > 0.5:
                typologies['Illegal Drug Sales'] = {
                    'confidence': drug_sales_score,
                    'primary_indicators': self._get_drug_sales_indicators(analysis_results)
                }
        
        # Money Laundering Detection
        # Skip if gambling detected
        if not suppress_other_typologies:
            ml_score = self._calculate_money_laundering_score(
                transactions, analysis_results
            )
            if ml_score > 0.5:
                typologies['Money Laundering'] = {
                    'confidence': ml_score,
                    'primary_indicators': self._get_ml_indicators(analysis_results)
                }
        
        # Determine primary typology
        if typologies:
            primary = max(typologies.items(), key=lambda x: x[1]['confidence'])
            
            # Tie-breaking: when Drug Sales and ML are both very high,
            # check ML-specific indicators (layering, name mentions) to decide.
            # ML with strong layering should win over Drug Sales.
            has_drugs = 'Illegal Drug Sales' in typologies
            has_ml = 'Money Laundering' in typologies
            if has_drugs and has_ml:
                drug_conf = typologies['Illegal Drug Sales']['confidence']
                ml_conf = typologies['Money Laundering']['confidence']
                layering = analysis_results.get('layering', {})
                name_mentions = layering.get('name_mention_count', 0)
                layering_conf = layering.get('confidence', 0)
                
                # If ML has strong layering indicators, prioritize ML
                # Require BOTH high layering confidence AND significant name mentions
                # Low name mentions + high layering can be a false positive
                if ml_conf >= drug_conf and name_mentions > 50 and layering_conf > 0.7:
                    primary = ('Money Laundering', typologies['Money Laundering'])
            
            result = {
                'detected_typologies': typologies,
                'primary_typology': primary[0],
                'primary_confidence': primary[1]['confidence']
            }
        else:
            result = {
                'detected_typologies': {},
                'primary_typology': 'Unknown',
                'primary_confidence': 0.0
            }
        
        # Attach gambling classification even if not flagged as suspicious
        # This lets the final analyzer report participation vs facilitation
        if gambling_analysis:
            result['gambling_classification'] = gambling_analysis['classification']
            result['gambling_details'] = gambling_analysis
        
        return result
    
    def _calculate_drug_sales_score(self, transactions: List, analysis: Dict) -> float:
        """
        Calculate drug sales confidence score
        
        M2O pattern + payment comments + round dollar amounts ($10-$100) 
        is HIGHLY indicative of drug sales
        """
        score = 0.0
        
        patterns = analysis.get('patterns', {})
        comments = analysis.get('comments', {})
        stats = analysis.get('basic_stats', {})
        
        # Drug slang detection (weighted heavily)
        # Give extra weight to HIGH confidence terms (weed, za, cart, plug, etc.)
        slang_count = comments.get('comments_with_slang', 0)
        high_confidence_count = comments.get('high_confidence_count', 0)
        
        # Base scoring for any slang
        if slang_count > 100:
            score += 0.40
        elif slang_count > 50:
            score += 0.35
        elif slang_count > 20:
            score += 0.30
        elif slang_count > 10:
            score += 0.25
        elif slang_count > 0:
            score += 0.15
        
        # Bonus for HIGH confidence terms (za, weed, cart, plug, dispo, etc.)
        if high_confidence_count > 50:
            score += 0.20  # Many high-confidence terms = definitely drugs
        elif high_confidence_count > 20:
            score += 0.15
        elif high_confidence_count > 10:
            score += 0.10
        elif high_confidence_count > 5:
            score += 0.05
        
        # Round amounts (critical indicator)
        round_pct = patterns.get('round_dollar_pct', 0)
        if round_pct > 85:
            score += 0.25
        elif round_pct > 70:
            score += 0.20
        elif round_pct > 50:
            score += 0.15
        
        # Flow pattern (critical indicator)
        # Drug dealers can be MANY-TO-ONE (receiving payments) or ONE-TO-MANY (sending drugs)
        incoming_pct = patterns.get('incoming_pct', 0)
        outgoing_pct = 100 - incoming_pct
        
        # Many-to-one (receiving payments for drugs)
        if incoming_pct > 90:
            score += 0.25
        elif incoming_pct > 70:
            score += 0.20
        elif incoming_pct > 60:
            score += 0.15
        # One-to-many (sending drugs/services)
        elif outgoing_pct > 60:
            score += 0.20  # Still suspicious if combined with other indicators
        elif outgoing_pct > 50:
            score += 0.15
        
        # Small-to-medium transactions $10-$500 (critical indicator)
        # Drug sales can go up to $500 for larger quantities
        under_100_pct = patterns.get('under_100_pct', 0)
        avg_amount = patterns.get('average_amount', 0)
        
        # Ideal range: most under $100
        if under_100_pct > 90:
            score += 0.25
        elif under_100_pct > 80:
            score += 0.20
        elif under_100_pct > 70:
            score += 0.15
        # But also accept if average is under $200 (allows for some larger sales)
        elif avg_amount < 200 and under_100_pct > 60:
            score += 0.15
        elif avg_amount < 150 and under_100_pct > 50:
            score += 0.10
        
        # High velocity (many unique counterparties)
        unique_cps = stats.get('unique_counterparties', 0)
        if unique_cps > 50:
            score += 0.10
        elif unique_cps > 30:
            score += 0.08
        elif unique_cps > 20:
            score += 0.05
        
        # Bonus: Strong combination of indicators (drug slang + round amounts + under $100)
        has_slang = slang_count > 10
        has_round = round_pct > 70
        has_small = under_100_pct > 90
        
        if has_slang and has_round and has_small:
            score += 0.15  # Strong combination bonus
        elif (has_slang and has_round) or (has_slang and has_small) or (has_round and has_small):
            score += 0.10  # Two indicators bonus
        
        return min(score, 1.0)
    
    def _calculate_money_laundering_score(self, transactions: List, analysis: Dict) -> float:
        """
        Calculate money laundering confidence score
        
        Includes both layering patterns and pass-through patterns
        """
        score = 0.0
        
        # Check for layering patterns
        layering = self.layering_detector.analyze_layering_patterns(
            transactions, analysis.get('subject', '')
        )
        
        if layering['detected']:
            score += layering['confidence']
        
        # Check for pass-through patterns (P2P incoming → Transfers outgoing)
        patterns = analysis.get('patterns', {})
        stats = analysis.get('basic_stats', {})
        
        incoming_pct = patterns.get('incoming_pct', 0)
        
        # Count product types
        incoming_p2p = 0
        outgoing_transfers = 0
        for tx in transactions:
            if hasattr(tx, 'is_incoming') and tx.is_incoming():
                if hasattr(tx, 'is_p2p') and tx.is_p2p():
                    incoming_p2p += 1
            elif hasattr(tx, 'direction') and tx.direction == 'OUT':
                if hasattr(tx, 'product_type') and 'TRANSFER' in tx.product_type.upper():
                    outgoing_transfers += 1
        
        total_txs = stats.get('total_transactions', 0)
        
        # If high incoming P2P and high outgoing transfers = pass-through ML
        if incoming_p2p > 50 and outgoing_transfers > 10:
            incoming_p2p_pct = (incoming_p2p / total_txs * 100) if total_txs > 0 else 0
            if incoming_p2p_pct > 80:
                score += 0.30  # Strong pass-through indicator
            elif incoming_p2p_pct > 60:
                score += 0.20
        
        # Multiple product types (traditional layering)
        product_types = set()
        for tx in transactions:
            if hasattr(tx, 'product_type') and tx.product_type:
                product_types.add(tx.product_type.upper())
        
        if len(product_types) > 2:
            score += 0.20
        
        # P2P + BTC + Equities = layering
        if 'BTC' in str(product_types) or 'BITCOIN' in str(product_types):
            score += 0.25
        if 'EQUIT' in str(product_types) or 'STOCK' in str(product_types):
            score += 0.25
        
        # High volume
        if stats.get('total_transactions', 0) > 1000:
            score += 0.15
        elif stats.get('total_transactions', 0) > 500:
            score += 0.10
        elif stats.get('total_transactions', 0) > 200:
            score += 0.05
        
        # Reduce ML score if this looks primarily like drug sales
        # (high drug slang + round amounts + small transactions = drug dealer, not launderer)
        comments_data = analysis.get('comments', {})
        patterns_data = analysis.get('patterns', {})
        
        high_confidence_slang = comments_data.get('high_confidence_count', 0)
        round_pct = patterns_data.get('round_dollar_pct', 0)
        under_100_pct = patterns_data.get('under_100_pct', 0)
        avg_amount = patterns_data.get('average_amount', 0)
        
        # If strong drug sales indicators, reduce ML confidence significantly
        if high_confidence_slang > 100 and round_pct > 70:
            score *= 0.70  # Reduce by 30% - this is primarily drug sales
        elif high_confidence_slang > 50 and round_pct > 70:
            score *= 0.75  # Reduce by 25%
        elif high_confidence_slang > 20 and round_pct > 60 and avg_amount < 200:
            score *= 0.80  # Reduce by 20%
        
        return min(score, 1.0)
    
    def _get_drug_sales_indicators(self, analysis: Dict) -> List[str]:
        """Get primary drug sales indicators"""
        indicators = []
        
        patterns = analysis.get('patterns', {})
        comments = analysis.get('comments', {})
        
        if patterns.get('round_dollar_pct', 0) > 70:
            indicators.append(f"{patterns['round_dollar_pct']:.0f}% round dollar amounts")
        
        if comments.get('comments_with_slang', 0) > 0:
            indicators.append(f"{comments['comments_with_slang']} comments with drug slang")
        
        if patterns.get('incoming_pct', 0) > 70:
            indicators.append(f"{patterns['incoming_pct']:.0f}% incoming (many-to-one pattern)")
        
        return indicators
    
    def _get_ml_indicators(self, analysis: Dict) -> List[str]:
        """Get primary money laundering indicators"""
        indicators = []
        
        # This will be populated with layering analysis
        indicators.append("Layering patterns detected")
        indicators.append("Multiple product types (P2P + BTC/Equities)")
        indicators.append("Rapid forwarding of funds")
        
        return indicators


# Test the new detectors
if __name__ == "__main__":
    print("Testing Context-Aware Detection...\n")
    
    detector = WeightedSlangDetector()
    
    # Test cases
    test_cases = [
        {
            'comment': 'for the za',
            'context': {'amount': 40.0, 'is_incoming': True, 'counterparty_velocity': 8, 'total_counterparties': 150}
        },
        {
            'comment': 'gas money',
            'context': {'amount': 45.0, 'is_incoming': True, 'counterparty_velocity': 2, 'total_counterparties': 10}
        },
        {
            'comment': 'gas',
            'context': {'amount': 35.0, 'is_incoming': True, 'counterparty_velocity': 12, 'total_counterparties': 200}
        },
        {
            'comment': 'food',
            'context': {'amount': 127.50, 'is_incoming': False, 'counterparty_velocity': 1, 'total_counterparties': 5}
        },
        {
            'comment': 'cart and pen 🔥',
            'context': {'amount': 60.0, 'is_incoming': True, 'counterparty_velocity': 15, 'total_counterparties': 180}
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        result = detector.detect_with_context(test['comment'], test['context'])
        print(f"Test {i}: \"{test['comment']}\"")
        print(f"  Amount: ${test['context']['amount']}, Incoming: {test['context']['is_incoming']}")
        print(f"  Confidence: {result['confidence']:.2f} ({detector.categorize_confidence(result['confidence'])})")
        print(f"  Context Score: {result['context_score']:.2f}x")
        if result['detected']:
            for term in result['detected']:
                print(f"    - {term['term']}: {term['base_confidence']:.2f} → {term['final_confidence']:.2f}")
        print()
