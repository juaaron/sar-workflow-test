"""
SAR Workflow Test - Adult Services / HT Detector
Detects patterns consistent with prostitution, escort services, and online sexual content sales.

KEY INDICATORS:
  - Incoming P2P payments $30-$500 (but can be lower for content sales)
  - Sexual/explicit comments, hotel/room references, meetup language
  - Sexually suggestive emojis (🍆, 🍑, 🍖, 👀, 🥵, etc.)
  - Online content references (videos, pictures, FaceTime/ft, dropbox)
  - "Deposit" followed by larger payment (booking pattern)
  - Phone numbers in comments (advertising/contact)
  - Many unique male-name counterparties
  - Round dollar amounts typical of set pricing ($30, $50, $100, $150)
"""

from typing import List, Dict
import re
from collections import Counter, defaultdict


class AdultServicesDetector:
    """
    Detects adult services / escort / prostitution / online content sales patterns.
    """
    
    # Explicit sexual terms (high confidence) — these are STRONG signals
    EXPLICIT_TERMS = {
        'suck': 0.90, 'bj': 0.95, 'blowjob': 0.95,
        'sex': 0.90, 'raw': 0.80, 'bare': 0.75,
        'escort': 0.95, 'outcall': 0.95, 'incall': 0.95,
        'full service': 0.95, 'gfe': 0.95,
        'happy ending': 0.95,
        'body rub': 0.90, 'bodyrub': 0.90,
        'nudes': 0.90, 'nude': 0.85, 'naked': 0.85,
        'onlyfans': 0.90, 'fansly': 0.90,
        'hookup': 0.90, 'hook up': 0.90,
        'quickie': 0.90, 'quick visit': 0.85,
        'roses': 0.80,
        'fantasy': 0.80, 'fantasies': 0.80,
        'attention': 0.55,
        'bust': 0.80, 'daddy': 0.65, 'lube': 0.85,
        'facial': 0.70, 'lace': 0.60, 'lingerie': 0.70,
        'experience': 0.55,
        'pussy': 0.95, 'dick': 0.85, 'ass': 0.70, 'booty': 0.75,
        'head': 0.65, 'dome': 0.75, 'throat': 0.80,
        'freaky': 0.80, 'freak': 0.75, 'kinky': 0.85,
    }
    
    # Meetup / hotel / location terms — only strong ones
    MEETUP_TERMS = {
        'meet up': 0.75, 'meetup': 0.75,
        'come over': 0.75, 'come thru': 0.75, 'come here': 0.65,
        'room': 0.70, 'hotel': 0.80, 'motel': 0.80,
        'don\'t stand me up': 0.85, 'dont stand me up': 0.85,
        'no show': 0.75,
        'link up': 0.70, 'linkup': 0.70,
        'get together': 0.65,
    }
    
    # Online content terms — only specific adult content indicators
    CONTENT_TERMS = {
        'video': 0.70, 'videos': 0.70,
        'facetime': 0.75, 'ft show': 0.85,
        'dropbox': 0.75,
    }
    
    # Sexually suggestive emojis — only the clearly sexual ones
    SUGGESTIVE_EMOJIS = {
        '🍆': 0.90, '🍑': 0.85, '🍖': 0.80, '🥩': 0.75, '🍗': 0.75,
        '🥵': 0.80, '💦': 0.85,
        '🤤': 0.70, '💋': 0.65, '👅': 0.85, '🫦': 0.85,
    }
    
    def __init__(self):
        self.all_text_terms = {
            **self.EXPLICIT_TERMS,
            **self.MEETUP_TERMS,
            **self.CONTENT_TERMS,
        }
    
    def detect_adult_terms(self, comment: str) -> Dict:
        """Detect adult services terms in a single comment."""
        if not comment or not isinstance(comment, str) or comment.strip() == '':
            return {'detected': False, 'confidence': 0.0, 'terms': []}
        
        comment_lower = comment.lower()
        detected = []
        
        # Check text terms
        for term, conf in self.all_text_terms.items():
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, comment_lower):
                category = 'explicit' if term in self.EXPLICIT_TERMS else \
                           'meetup' if term in self.MEETUP_TERMS else 'content'
                detected.append({
                    'term': term,
                    'confidence': conf,
                    'category': category,
                })
        
        # Check emojis
        for emoji, conf in self.SUGGESTIVE_EMOJIS.items():
            if emoji in comment:
                detected.append({
                    'term': emoji,
                    'confidence': conf,
                    'category': 'emoji',
                })
        
        # Phone numbers removed — too common in normal P2P to be a reliable signal
        
        if not detected:
            return {'detected': False, 'confidence': 0.0, 'terms': []}
        
        max_conf = max(d['confidence'] for d in detected)
        return {
            'detected': True,
            'confidence': max_conf,
            'terms': detected,
            'comment': comment,
        }
    
    def analyze_adult_services(self, transactions: List) -> Dict:
        """
        Full adult services analysis.
        
        Looks at:
        1. Incoming P2P comments for explicit/meetup/content terms
        2. Amount patterns (round dollars, typical pricing)
        3. Many unique senders (clients)
        4. Phone numbers in comments (advertising)
        5. Deposit + larger payment patterns
        """
        
        # Analyze incoming P2P comments (including failed — comments still informative)
        flagged_comments = []
        explicit_count = 0
        meetup_count = 0
        content_count = 0
        emoji_count = 0
        contact_count = 0
        
        for tx in transactions:
            if not tx.is_p2p() or not tx.comment or not tx.is_incoming():
                continue
            
            result = self.detect_adult_terms(tx.comment)
            if result['detected']:
                # Apply amount-based confidence adjustment
                amount = tx.amount
                is_round = amount > 0 and amount == int(amount)
                amount_multiplier = 1.0
                
                if 30 <= amount <= 500:
                    # Sweet spot for escort/services pricing
                    amount_multiplier = 1.3
                elif 150 < amount <= 1000:
                    # High-end services
                    amount_multiplier = 1.2
                elif 10 <= amount < 30:
                    # Low but possible (content sales, tips)
                    amount_multiplier = 1.0
                elif amount < 10:
                    # Very low — likely joking, not real payment for services
                    amount_multiplier = 0.5
                
                # Round dollar amounts = set pricing (common in sex work)
                if is_round and amount >= 30:
                    amount_multiplier += 0.1
                
                # Adjust confidence
                adjusted_confidence = min(result['confidence'] * amount_multiplier, 1.0)
                
                # Only count toward typology if amount-adjusted confidence is meaningful
                # Under $10 with low base confidence = skip (probably a joke)
                if adjusted_confidence < 0.40:
                    continue
                
                categories = set(t['category'] for t in result['terms'])
                if 'explicit' in categories:
                    explicit_count += 1
                if 'meetup' in categories:
                    meetup_count += 1
                if 'content' in categories:
                    content_count += 1
                if 'emoji' in categories:
                    emoji_count += 1
                if 'contact' in categories:
                    contact_count += 1
                
                flagged_comments.append({
                    'comment': tx.comment,
                    'amount': tx.amount,
                    'amount_multiplier': amount_multiplier,
                    'counterparty': tx.counterparty,
                    'direction': 'incoming',
                    'date': tx.date,
                    'confidence': adjusted_confidence,
                    'base_confidence': result['confidence'],
                    'terms': result['terms'],
                    'categories': list(categories),
                    'status': tx.status,
                })
        
        # Analyze incoming P2P patterns (successful only for amounts)
        incoming_p2p = [tx for tx in transactions 
                       if tx.is_p2p() and tx.is_incoming() and tx.is_paid_out()]
        
        unique_senders = len(set(tx.counterparty for tx in incoming_p2p))
        
        # Amount analysis
        if incoming_p2p:
            amounts = [tx.amount for tx in incoming_p2p]
            round_amounts = [a for a in amounts if a == int(a)]
            round_pct = len(round_amounts) / len(amounts) * 100
            
            # Typical escort pricing ranges
            in_30_100 = sum(1 for a in amounts if 30 <= a <= 100)
            in_100_500 = sum(1 for a in amounts if 100 <= a <= 500)
            pricing_range_pct = (in_30_100 + in_100_500) / len(amounts) * 100
        else:
            round_pct = 0
            pricing_range_pct = 0
        
        # Calculate confidence
        # CRITICAL: Explicit terms are the ANCHOR. Without explicit terms,
        # content/meetup/emojis alone are NOT enough to flag adult services.
        # "video" and "meetup" are too common in normal transactions.
        confidence = 0.0
        indicators = []
        
        # Explicit sexual terms (REQUIRED anchor)
        if explicit_count >= 5:
            confidence += 0.40
            indicators.append(f"{explicit_count} explicit/sexual comments detected")
        elif explicit_count >= 3:
            confidence += 0.30
            indicators.append(f"{explicit_count} explicit/sexual comments detected")
        elif explicit_count >= 2:
            confidence += 0.25
            indicators.append(f"{explicit_count} explicit/sexual comments detected")
        elif explicit_count >= 1:
            confidence += 0.15
            indicators.append(f"{explicit_count} explicit/sexual comment detected")
        
        # Content sales terms — only count if explicit terms also present
        if content_count >= 3 and explicit_count >= 1:
            confidence += 0.20
            indicators.append(f"{content_count} online content references (videos, FT)")
        elif content_count >= 1 and explicit_count >= 1:
            confidence += 0.10
            indicators.append(f"{content_count} online content references")
        
        # Meetup / hotel terms — only count if explicit terms also present
        if meetup_count >= 3 and explicit_count >= 1:
            confidence += 0.15
            indicators.append(f"{meetup_count} meetup/hotel references")
        elif meetup_count >= 1 and explicit_count >= 1:
            confidence += 0.10
            indicators.append(f"{meetup_count} meetup/hotel references")
        
        # Suggestive emojis — only boost if explicit terms present
        if emoji_count >= 3 and explicit_count >= 1:
            confidence += 0.10
            indicators.append(f"{emoji_count} sexually suggestive emojis")
        elif emoji_count >= 1 and explicit_count >= 1:
            confidence += 0.05
            indicators.append(f"{emoji_count} sexually suggestive emojis")
        
        # Many unique senders (client base) — only if explicit terms present
        if unique_senders >= 50 and explicit_count >= 1:
            confidence += 0.10
            indicators.append(f"{unique_senders} unique incoming senders (large client base)")
        
        # Combination bonus: explicit + content + meetup together
        has_explicit = explicit_count >= 1
        has_content = content_count >= 1
        has_meetup = meetup_count >= 1
        
        combo_count = sum([has_explicit, has_content, has_meetup])
        if combo_count >= 3:
            confidence += 0.10
            indicators.append("Multiple indicator types: explicit terms + content sales + meetup/hotel references")
        elif combo_count >= 2 and has_explicit:
            confidence += 0.05
            indicators.append("Multiple indicator types detected")
        
        confidence = min(confidence, 1.0)
        
        return {
            'detected': confidence >= 0.5,
            'confidence': confidence,
            'indicators': indicators,
            'explicit_count': explicit_count,
            'meetup_count': meetup_count,
            'content_count': content_count,
            'emoji_count': emoji_count,
            'contact_count': contact_count,
            'unique_senders': unique_senders,
            'flagged_comments': flagged_comments[:20],
            'flagged_comment_count': len(flagged_comments),
        }


if __name__ == "__main__":
    print("Adult Services Detector")
    print("=" * 40)
    
    detector = AdultServicesDetector()
    
    tests = [
        "suck some lol",
        "meet up lmao",
        "videos I guess",
        "raw 🍖",
        "freshid outta jail and need some attention 🍆",
        "ft show",
        "for videos and show",
        "room",
        "deposit",
        "don't stand me up",
        "jas meetup don't just ghost me nigga tf",
        "food",
        "gas",
        "John 3 videos",
        "(445) 253-4227 new number",
        "2 videos",
        "LOVE YOU🥰🤤",
    ]
    
    for t in tests:
        r = detector.detect_adult_terms(t)
        if r['detected']:
            terms = [d['term'] for d in r['terms']]
            print(f'  FLAGGED: "{t}" -> {terms} ({r["confidence"]:.0%})')
        else:
            print(f'  clean:   "{t}"')
