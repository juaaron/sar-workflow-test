"""
KITT - Gambling Detector
Distinguishes between Gambling FACILITATION (suspicious) and Gambling PARTICIPATION (not suspicious)

KEY COMPLIANCE RULE:
  - FACILITATION = Many people send INCOMING P2P payments ($1-$50) with gambling comments
    → Subject is gambling on behalf of others → SAR-worthy
  - PARTICIPATION = Subject uses their OWN Cash Card to buy at gambling sites
    → P2P is normal family/personal activity → NOT SAR-worthy
    
The question KITT asks: "Where is the gambling money coming from?"
  - From many P2P senders → Facilitation → Flag it
  - From their own bank/card → Participation → Don't flag it
"""

from typing import List, Dict
import re
from collections import Counter, defaultdict


class GamblingDetector:
    """
    Detects gambling facilitation vs participation patterns.
    Only flags FACILITATION as suspicious.
    """
    
    # Known gambling platforms and apps
    GAMBLING_PLATFORMS = {
        'orion stars': 0.95, 'orion': 0.85, 'os': 0.70,
        'fire kirin': 0.95, 'firekirin': 0.95, 'kirin': 0.80,
        'juwa': 0.95, 'juwa777': 0.95,
        'milky way': 0.90, 'milkyway': 0.90,
        'ultra panda': 0.95, 'ultrapanda': 0.95, 'panda': 0.75,
        'game vault': 0.90, 'gamevault': 0.90,
        'river monster': 0.95, 'rivermonster': 0.95,
        'vegas x': 0.90, 'vegasx': 0.90,
        'blue dragon': 0.90, 'bluedragon': 0.90,
        'cash tornado': 0.90, 'cashtornado': 0.90,
        'golden dragon': 0.90, 'goldendragon': 0.90,
        'game room': 0.85, 'gameroom': 0.85,
        'skill games': 0.80, 'skillgames': 0.80,
        'sweepstakes': 0.85, 'sweeps': 0.85,
        'slots': 0.80, 'slot': 0.75,
        'casino': 0.75, 'poker': 0.75, 'blackjack': 0.80,
        'roulette': 0.85, 'baccarat': 0.85,
        'crown coins': 0.95, 'crowncoins': 0.95,
        'chumba': 0.90, 'chumba casino': 0.95,
        'luckyland': 0.90, 'luckyland slots': 0.95,
        'global poker': 0.90, 'funzpoints': 0.90,
        'pulsz': 0.90, 'stake.us': 0.90, 'stake': 0.70,
        'wow vegas': 0.90, 'mcluck': 0.90,
        'high 5 casino': 0.90, 'fortune coins': 0.90,
        'pava': 0.90, 'pavami': 0.90,
        'clash royale': 0.75, 'easyfun': 0.80,
    }
    
    # Gambling-related terms (found in P2P comments for facilitation)
    # NOTE: Only include terms that are STRONG gambling indicators.
    # Generic words like "play", "game", "chips", "balance", "account" cause
    # false positives in drug sales and ML cases. Those are only meaningful
    # when combined with platform names or username patterns.
    GAMBLING_TERMS = {
        'bet': 0.70, 'bets': 0.70, 'betting': 0.75,
        'wager': 0.80,
        'payout': 0.85, 'payouts': 0.85, 'cashout': 0.85,
        'winnings': 0.90, 'jackpot': 0.90,
        'reload': 0.75,
        'spin': 0.65, 'spins': 0.65,
    }
    
    def __init__(self):
        self.all_gambling_terms = {
            **self.GAMBLING_PLATFORMS,
            **self.GAMBLING_TERMS
        }
    
    def detect_gambling_terms(self, comment: str) -> Dict:
        """Detect gambling-related terms in a single comment"""
        if not comment or not isinstance(comment, str):
            return {'detected': False, 'confidence': 0.0, 'terms': []}
        
        comment_lower = comment.lower()
        detected_terms = []
        
        for term, confidence in self.all_gambling_terms.items():
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, comment_lower):
                detected_terms.append({
                    'term': term,
                    'confidence': confidence,
                    'type': 'platform' if term in self.GAMBLING_PLATFORMS else 'term'
                })
        
        if not detected_terms:
            return {'detected': False, 'confidence': 0.0, 'terms': []}
        
        max_confidence = max(t['confidence'] for t in detected_terms)
        
        return {
            'detected': True,
            'confidence': max_confidence,
            'terms': detected_terms,
            'comment': comment
        }
    
    def detect_username_pattern(self, comment: str) -> Dict:
        """
        Detect username patterns common in gambling facilitation.
        
        Real examples from cases:
        - SummerR786, Dayten786, JackA888 (name + 3-4 digits)
        - beebeetas4, gordontea1, ciaramilk1 (name + 1-2 digits)
        - Fatt1a, Fattair1 (name with digits mixed in)
        - VictDez88, Jalagorgv98 (name + 2 digits)
        - mich3, patrickcof1 (short name + digit)
        
        Pattern: looks like a username, not a normal word or name.
        Must have letters AND digits mixed together, min 4 chars total.
        Excludes pure numbers and common words.
        """
        if not comment or not isinstance(comment, str):
            return {'detected': False, 'username': None}
        
        comment_stripped = comment.strip()
        
        # Skip very short or very long comments
        if len(comment_stripped) < 4 or len(comment_stripped) > 30:
            return {'detected': False, 'username': None}
        
        # Skip if it looks like a normal sentence or social media handle
        common_phrases = ['for ', 'to ', 'my ', 'the ', 'and ', 'money', 'payment', 'thank',
                          'bill', 'towards', 'plus', 'video', 'ball ', 'at ',
                          'snap', 'snapchat', 'instagram', 'ig ', 'tiktok', 'twitter',
                          'facebook', 'venmo', 'paypal', 'zelle', 'add me', 'follow']
        lower = comment_stripped.lower()
        if any(p in lower for p in common_phrases) and ' ' in comment_stripped:
            return {'detected': False, 'username': None}
        
        # Pattern: letters mixed with digits, looks like a username
        # Real gambling usernames: beebeetas4, gordontea1, Fatt1a, VictDez88, ciaramilk1
        # NOT usernames: JustinRay1 (real name), 50paypal, 29th, 100-50=50bal
        matches = []
        words = comment_stripped.split()
        for word in words:
            # Clean punctuation
            clean = re.sub(r'[^\w]', '', word)
            if len(clean) < 5:
                continue
            
            has_letters = bool(re.search(r'[a-zA-Z]', clean))
            has_digits = bool(re.search(r'\d', clean))
            
            if not (has_letters and has_digits):
                continue
            
            # Exclude things starting with $ or #
            if word.startswith('$') or word.startswith('#'):
                continue
            
            # Exclude ordinals (29th, 1st, 2nd, 3rd)
            if re.match(r'^\d+(st|nd|rd|th)$', clean, re.IGNORECASE):
                continue
            
            # Exclude if starts with digits then common word (50paypal, 100bal)
            if re.match(r'^\d+[a-zA-Z]+$', clean) and len(re.findall(r'\d+', clean)[0]) >= 2:
                continue
            
            # Exclude real names with a single trailing digit (JustinRay1)
            # Real usernames tend to be lowercase or have unusual letter combos
            # Names have capital first letters of each part
            if re.match(r'^[A-Z][a-z]+[A-Z][a-z]+\d{1}$', clean):
                continue
            
            matches.append(clean)
        
        if matches:
            return {
                'detected': True,
                'usernames': matches,
                'confidence': 0.85,
                'comment': comment
            }
        
        return {'detected': False, 'username': None}
    
    def _detect_cash_card_gambling(self, transactions: List) -> Dict:
        """
        Detect Cash Card purchases at gambling sites.
        This indicates PARTICIPATION (subject gambling with their own money).
        """
        gambling_purchases = []
        
        for tx in transactions:
            if not hasattr(tx, 'product_type'):
                continue
            
            product_type = (tx.product_type or '').upper()
            comment = tx.comment or ''
            
            # CASH_CARD is the product type for card purchases
            is_cash_card = product_type == 'CASH_CARD'
            
            if is_cash_card and comment:
                gambling_result = self.detect_gambling_terms(comment)
                if gambling_result['detected']:
                    gambling_purchases.append({
                        'comment': comment,
                        'amount': tx.amount,
                        'date': tx.date,
                        'terms': gambling_result['terms'],
                        'confidence': gambling_result['confidence']
                    })
        
        total_spent = sum(p['amount'] for p in gambling_purchases)
        
        return {
            'detected': len(gambling_purchases) > 0,
            'count': len(gambling_purchases),
            'total_spent': total_spent,
            'purchases': gambling_purchases[:20],
            'platforms': Counter(
                t['term'] for p in gambling_purchases for t in p['terms'] if t['type'] == 'platform'
            ).most_common(5)
        }
    
    def _detect_p2p_gambling_facilitation(self, transactions: List) -> Dict:
        """
        Detect P2P payments that look like gambling facilitation.
        
        Key indicators:
        - INCOMING P2P payments (people sending money TO the subject to gamble)
        - OUTGOING P2P payments with gambling platform/username comments (paying out winnings)
        - Amounts between $1 and $50 (incoming)
        - Gambling-related comments (platform names, usernames, terms)
        - Multiple unique senders
        - High frequency
        """
        facilitation_txns = []
        gambling_p2p_comments = []
        username_matches = []
        
        for tx in transactions:
            # Check BOTH incoming and outgoing P2P for gambling indicators
            if not tx.is_p2p():
                continue
            
            comment = tx.comment or ''
            amount = tx.amount
            
            # Check for gambling terms in P2P comments
            gambling_result = self.detect_gambling_terms(comment)
            username_result = self.detect_username_pattern(comment)
            
            is_facilitation_amount = 1.0 <= amount <= 50.0
            has_gambling_comment = gambling_result['detected']
            has_username = username_result['detected']
            
            if has_gambling_comment or has_username:
                facilitation_txns.append({
                    'comment': comment,
                    'amount': amount,
                    'counterparty': tx.counterparty,
                    'date': tx.date,
                    'direction': 'incoming' if tx.is_incoming() else 'outgoing',
                    'gambling_terms': gambling_result.get('terms', []),
                    'usernames': username_result.get('usernames', []),
                    'in_amount_range': is_facilitation_amount
                })
                
                if has_gambling_comment:
                    gambling_p2p_comments.append(comment)
                if has_username:
                    username_matches.extend(username_result['usernames'])
        
        # Also count incoming P2P in the $1-$50 range even without gambling comments
        # (facilitation often has generic comments too)
        incoming_p2p_small = [
            tx for tx in transactions
            if tx.is_incoming() and tx.is_p2p() and 1.0 <= tx.amount <= 50.0
        ]
        
        unique_senders = len(set(tx.counterparty for tx in incoming_p2p_small))
        
        # Separate incoming vs outgoing gambling signals
        incoming_gambling = [t for t in facilitation_txns if t['direction'] == 'incoming']
        outgoing_gambling = [t for t in facilitation_txns if t['direction'] == 'outgoing']
        incoming_gambling_comments = [t['comment'] for t in incoming_gambling if t['gambling_terms']]
        incoming_usernames = []
        for t in incoming_gambling:
            incoming_usernames.extend(t.get('usernames', []))
        
        # Calculate facilitation confidence
        # CRITICAL: Incoming gambling signals are the PRIMARY indicator
        # Outgoing signals alone are NOT enough (could be ML with some gambling on the side)
        confidence = 0.0
        indicators = []
        
        # Gambling terms/usernames in INCOMING P2P (strongest signal)
        incoming_signal_count = len(incoming_gambling)
        if incoming_signal_count > 20:
            confidence += 0.5
            indicators.append(f"{incoming_signal_count} incoming P2P payments with gambling terms/usernames")
        elif incoming_signal_count > 10:
            confidence += 0.4
            indicators.append(f"{incoming_signal_count} incoming P2P payments with gambling terms/usernames")
        elif incoming_signal_count > 3:
            confidence += 0.3
            indicators.append(f"{incoming_signal_count} incoming P2P payments with gambling terms/usernames")
        elif incoming_signal_count > 0:
            confidence += 0.15
            indicators.append(f"{incoming_signal_count} incoming P2P payments with gambling terms/usernames")
        
        # Outgoing gambling signals are supplementary only (boost, don't trigger)
        if len(outgoing_gambling) > 5 and incoming_signal_count > 0:
            confidence += 0.1
            indicators.append(f"{len(outgoing_gambling)} outgoing P2P payments with gambling terms (payouts)")
        
        # Username patterns in INCOMING P2P (strong signal for facilitation)
        unique_incoming_usernames = len(set(incoming_usernames))
        if unique_incoming_usernames > 10:
            confidence += 0.3
            indicators.append(f"{unique_incoming_usernames} unique username patterns in incoming P2P")
        elif unique_incoming_usernames > 5:
            confidence += 0.2
            indicators.append(f"{unique_incoming_usernames} unique username patterns in incoming P2P")
        elif unique_incoming_usernames > 0:
            confidence += 0.1
            indicators.append(f"{unique_incoming_usernames} unique username patterns in incoming P2P")
        
        # Many unique senders sending small amounts (facilitation pattern)
        if unique_senders > 20:
            confidence += 0.2
            indicators.append(f"{unique_senders} unique senders of small P2P payments ($1-$50)")
        elif unique_senders > 10:
            confidence += 0.15
            indicators.append(f"{unique_senders} unique senders of small P2P payments ($1-$50)")
        
        # In-range amounts with gambling comments
        in_range_count = sum(1 for t in facilitation_txns if t['in_amount_range'])
        if in_range_count > 10:
            confidence += 0.1
            indicators.append(f"{in_range_count} gambling-related P2P payments in $1-$50 range")
        
        confidence = min(confidence, 1.0)
        
        return {
            'detected': confidence >= 0.5,
            'confidence': confidence,
            'facilitation_txns': facilitation_txns[:20],
            'facilitation_count': len(facilitation_txns),
            'gambling_p2p_comment_count': len(gambling_p2p_comments),
            'username_count': unique_incoming_usernames,
            'unique_senders_small': unique_senders,
            'total_incoming_small': sum(tx.amount for tx in incoming_p2p_small),
            'indicators': indicators,
            'top_usernames': Counter(username_matches).most_common(10)
        }
    
    def _assess_p2p_risk(self, transactions: List) -> Dict:
        """
        Assess whether P2P activity looks like normal personal/family use
        or suspicious facilitation-like patterns.
        
        Low-risk P2P indicators:
        - Few unique counterparties (family/friends)
        - Personal comments (son, mom, food, gas, love, etc.)
        - Bidirectional (sending AND receiving)
        - Normal amounts
        """
        p2p_txns = [tx for tx in transactions if tx.is_p2p() and 
                     tx.status in ('COMPLETED', 'PAID_OUT', 'SETTLED', 'CAPTURED')]
        
        if not p2p_txns:
            return {'risk': 'none', 'detail': 'No P2P activity'}
        
        incoming = [tx for tx in p2p_txns if tx.is_incoming()]
        outgoing = [tx for tx in p2p_txns if tx.is_outgoing()]
        unique_cps = len(set(tx.counterparty for tx in p2p_txns))
        
        # Check for personal/family comments
        personal_terms = {
            'son', 'daughter', 'mom', 'dad', 'mother', 'father', 'brother', 'sister',
            'cousin', 'uncle', 'aunt', 'grandma', 'grandpa', 'granddaughter', 'grandson',
            'baby', 'babe', 'honey', 'love', 'family', 'sis', 'bro', 'pops', 'mama', 'papa',
            'food', 'gas', 'rent', 'bill', 'bills', 'groceries', 'lunch', 'dinner',
            'birthday', 'christmas', 'gift', 'thank', 'thanks', 'repayment',
            'cigs', 'cigarettes', 'decorations', 'paint', 'hair', 'nails',
            'hey', 'ok', 'please', 'pleaseeee', 'you', 'gg',
        }
        
        personal_count = 0
        for tx in p2p_txns:
            if tx.comment:
                comment_lower = tx.comment.lower().strip()
                # Check if comment contains personal terms
                for term in personal_terms:
                    if term in comment_lower:
                        personal_count += 1
                        break
        
        personal_pct = (personal_count / len(p2p_txns) * 100) if p2p_txns else 0
        is_bidirectional = len(incoming) > 0 and len(outgoing) > 0
        
        # Risk assessment
        risk_score = 0
        details = []
        
        if unique_cps <= 10:
            details.append(f"Small network ({unique_cps} counterparties) — likely family/friends")
        else:
            risk_score += 1
            details.append(f"Larger network ({unique_cps} counterparties)")
        
        if personal_pct > 50:
            details.append(f"{personal_pct:.0f}% personal/family comments")
        elif personal_pct > 25:
            details.append(f"{personal_pct:.0f}% personal/family comments")
        else:
            risk_score += 1
        
        if is_bidirectional:
            details.append("Bidirectional flow (sending and receiving)")
        else:
            risk_score += 1
            details.append("One-directional flow")
        
        if len(p2p_txns) < 50:
            details.append(f"Low P2P volume ({len(p2p_txns)} transactions)")
        else:
            risk_score += 1
            details.append(f"Higher P2P volume ({len(p2p_txns)} transactions)")
        
        if risk_score <= 1:
            risk = 'low'
        elif risk_score <= 2:
            risk = 'moderate'
        else:
            risk = 'high'
        
        return {
            'risk': risk,
            'risk_score': risk_score,
            'total_p2p': len(p2p_txns),
            'incoming_count': len(incoming),
            'outgoing_count': len(outgoing),
            'unique_counterparties': unique_cps,
            'personal_comment_pct': personal_pct,
            'is_bidirectional': is_bidirectional,
            'details': details
        }
    
    def analyze_gambling_activity(self, transactions: List) -> Dict:
        """
        Complete gambling analysis — distinguishes FACILITATION from PARTICIPATION.
        
        Only returns detected=True for FACILITATION (SAR-worthy).
        Participation is noted but NOT flagged as suspicious.
        """
        
        # Step 1: Check for Cash Card gambling purchases (PARTICIPATION)
        cash_card_gambling = self._detect_cash_card_gambling(transactions)
        
        # Step 2: Check for incoming P2P gambling facilitation
        facilitation = self._detect_p2p_gambling_facilitation(transactions)
        
        # Step 3: Assess overall P2P risk level
        p2p_risk = self._assess_p2p_risk(transactions)
        
        # Step 4: Make the determination
        indicators = []
        classification = 'none'  # none, participation, facilitation
        confidence = 0.0
        
        has_cash_card_gambling = cash_card_gambling['detected'] and cash_card_gambling['count'] >= 3
        has_facilitation = facilitation['detected']
        
        if has_facilitation and has_cash_card_gambling:
            # Both present — facilitation is the concern
            classification = 'facilitation'
            confidence = facilitation['confidence']
            indicators = facilitation['indicators']
            indicators.append(f"Also detected {cash_card_gambling['count']} Cash Card gambling purchases (${cash_card_gambling['total_spent']:,.2f})")
            
        elif has_facilitation and not has_cash_card_gambling:
            # Pure facilitation — definitely suspicious
            classification = 'facilitation'
            confidence = facilitation['confidence']
            indicators = facilitation['indicators']
            
        elif has_cash_card_gambling and not has_facilitation:
            # Pure participation — NOT suspicious
            classification = 'participation'
            confidence = 0.0  # Not flagged
            indicators.append(f"Gambling PARTICIPATION detected: {cash_card_gambling['count']} Cash Card purchases at gambling sites (${cash_card_gambling['total_spent']:,.2f})")
            indicators.append(f"P2P risk level: {p2p_risk['risk'].upper()} — {'; '.join(p2p_risk['details'])}")
            indicators.append("No incoming P2P gambling facilitation pattern detected")
            indicators.append("Classification: Gambling Participation (not SAR-worthy)")
            
            # If P2P risk is also low, add that as reinforcement
            if p2p_risk['risk'] == 'low':
                indicators.append("P2P activity appears to be normal family/personal transactions")
        
        else:
            # No gambling detected at all
            classification = 'none'
            confidence = 0.0
        
        return {
            # CRITICAL: Only flag facilitation as detected/suspicious
            'detected': classification == 'facilitation',
            'confidence': confidence,
            'classification': classification,  # 'none', 'participation', 'facilitation'
            'indicators': indicators,
            'cash_card_gambling': cash_card_gambling,
            'facilitation': facilitation,
            'p2p_risk': p2p_risk,
            'gambling_comments': facilitation.get('facilitation_txns', [])[:20],
            'gambling_comment_count': facilitation.get('facilitation_count', 0),
            'username_comments': [],
            'username_count': facilitation.get('username_count', 0),
            'velocity_patterns': {'detected': False, 'confidence': 0, 'pattern_count': 0, 'patterns': [], 'total_counterparties_with_pattern': 0},
            'top_platforms': cash_card_gambling.get('platforms', []),
            'top_usernames': facilitation.get('top_usernames', [])
        }


if __name__ == "__main__":
    print("Gambling Detector v2 — Facilitation vs Participation")
    print("=" * 50)
    print()
    print("FACILITATION (SAR-worthy):")
    print("  → Many incoming P2P payments ($1-$50)")
    print("  → Gambling platform names in P2P comments")
    print("  → Username patterns (SummerR786, JackA888)")
    print("  → Subject gambling on behalf of others")
    print()
    print("PARTICIPATION (NOT SAR-worthy):")
    print("  → Cash Card purchases at gambling sites")
    print("  → Normal family/personal P2P activity")
    print("  → Subject gambling with their own money")
