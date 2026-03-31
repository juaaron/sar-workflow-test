"""
SAR Platform - Legitimate Business Activity Detector
Reduces false positives by identifying legitimate business patterns
"""

from typing import List, Dict
import re
from collections import Counter


class LegitimateBusinessDetector:
    """
    Detects legitimate business activity to reduce false positives
    
    Key indicators of legitimate business:
    - Business-related payment comments (photography, video, services)
    - Mixed personal and business expenses
    - Consistent service-based income pattern
    - Professional terminology
    - No drug slang or suspicious indicators
    """
    
    # Legitimate business service terms
    BUSINESS_SERVICES = {
        # Creative/Media Services
        'photography': 0.9, 'photo': 0.85, 'photographer': 0.9, 'photoshoot': 0.9,
        'video': 0.85, 'videography': 0.9, 'videographer': 0.9, 'filming': 0.85,
        'editing': 0.8, 'edit': 0.75, 'production': 0.8,
        
        # Marketing/Social Media
        'promo': 0.85, 'promotion': 0.85, 'promotional': 0.85, 'marketing': 0.9,
        'social media': 0.9, 'instagram': 0.8, 'facebook': 0.8, 'tiktok': 0.8,
        'story': 0.75, 'post': 0.75, 'content': 0.8, 'ad': 0.7, 'advertisement': 0.8,
        'influencer': 0.85, 'brand': 0.8, 'sponsor': 0.85, 'collaboration': 0.85,
        
        # Events
        'event': 0.85, 'party': 0.7, 'wedding': 0.9, 'birthday': 0.8, 'celebration': 0.8,
        'concert': 0.85, 'show': 0.75, 'performance': 0.85, 'gig': 0.8,
        
        # Professional Services
        'consultation': 0.9, 'consulting': 0.9, 'service': 0.8, 'session': 0.8,
        'appointment': 0.85, 'booking': 0.85, 'reservation': 0.85,
        'lesson': 0.85, 'tutoring': 0.9, 'coaching': 0.85, 'training': 0.8,
        'design': 0.85, 'graphic': 0.85, 'logo': 0.85, 'website': 0.85,
        'repair': 0.85, 'fix': 0.75, 'maintenance': 0.85, 'installation': 0.85,
        
        # Beauty/Personal Care
        'haircut': 0.9, 'hair': 0.8, 'salon': 0.9, 'barber': 0.9, 'styling': 0.85,
        'nails': 0.9, 'manicure': 0.9, 'pedicure': 0.9, 'massage': 0.85, 'spa': 0.85,
        'makeup': 0.85, 'lashes': 0.85, 'brows': 0.85, 'wax': 0.8, 'facial': 0.85,
        
        # Retail/Products
        'shirt': 0.8, 'clothes': 0.8, 'clothing': 0.8, 'shoes': 0.8, 'dress': 0.8,
        'jewelry': 0.85, 'accessories': 0.8, 'merchandise': 0.85, 'product': 0.75,
        
        # Food/Hospitality
        'catering': 0.9, 'cake': 0.85, 'baking': 0.85, 'cooking': 0.8,
        'restaurant': 0.85, 'menu': 0.8, 'order': 0.7, 'delivery': 0.75,
        
        # Transportation
        'ride': 0.8, 'uber': 0.85, 'lyft': 0.85, 'taxi': 0.85, 'transport': 0.8,
        'delivery': 0.75, 'shipping': 0.8, 'moving': 0.8,
        
        # Real Estate/Housing
        'rent': 0.9, 'lease': 0.9, 'deposit': 0.85, 'utilities': 0.9,
        'cleaning': 0.85, 'housekeeping': 0.85, 'lawn': 0.85, 'yard': 0.8,
        
        # Fitness/Health
        'gym': 0.85, 'fitness': 0.85, 'workout': 0.85, 'yoga': 0.85, 'pilates': 0.85,
        'personal training': 0.9, 'trainer': 0.85, 'nutrition': 0.85,
        
        # Entertainment
        'dj': 0.85, 'music': 0.8, 'band': 0.85, 'entertainment': 0.85,
        'ticket': 0.8, 'tickets': 0.8, 'admission': 0.85,
        
        # Childcare/Pet Care
        'babysitting': 0.9, 'childcare': 0.9, 'daycare': 0.9, 'nanny': 0.9,
        'pet sitting': 0.9, 'dog walking': 0.9, 'grooming': 0.85,
        
        # General Business
        'invoice': 0.9, 'payment': 0.7, 'bill': 0.8, 'fee': 0.8, 'charge': 0.75,
        'commission': 0.85, 'tip': 0.8, 'gratuity': 0.85, 'donation': 0.85,
        'membership': 0.85, 'subscription': 0.85, 'dues': 0.85
    }
    
    # Personal/household expenses (not business, but legitimate)
    PERSONAL_EXPENSES = {
        'food': 0.8, 'groceries': 0.9, 'grocery': 0.9, 'lunch': 0.85, 'dinner': 0.85,
        'breakfast': 0.85, 'coffee': 0.85, 'drinks': 0.75, 'meal': 0.8,
        'hotel': 0.85, 'motel': 0.85, 'airbnb': 0.85, 'lodging': 0.85,
        'gas': 0.7, 'fuel': 0.8, 'parking': 0.85, 'toll': 0.85,
        'movie': 0.85, 'movies': 0.85, 'netflix': 0.9, 'spotify': 0.9,
        'gift': 0.7, 'present': 0.75, 'birthday': 0.8, 'christmas': 0.85,
        'thank you': 0.75, 'thanks': 0.7, 'appreciate': 0.7,
        'loan': 0.7, 'borrow': 0.7, 'owe': 0.6, 'payback': 0.7,
        'split': 0.75, 'share': 0.7, 'half': 0.6, 'portion': 0.7
    }
    
    # Ambiguous terms that need context (could be business OR drug slang)
    AMBIGUOUS_TERMS = {
        'gas', 'food', 'candy', 'good', 'stuff', 'product', 'work',
        'bag', 'pack', 'green', 'blue', 'white', 'fire'
    }
    
    def __init__(self):
        self.all_legitimate_terms = {
            **self.BUSINESS_SERVICES,
            **self.PERSONAL_EXPENSES
        }
    
    def detect_legitimate_activity(self, comment: str) -> Dict:
        """
        Detect if comment indicates legitimate business or personal activity
        
        Returns:
            Dict with detection results and confidence
        """
        if not comment or not isinstance(comment, str):
            return {'detected': False, 'confidence': 0.0, 'terms': [], 'category': None}
        
        comment_lower = comment.lower()
        detected_terms = []
        
        # Check for legitimate business terms
        for term, confidence in self.all_legitimate_terms.items():
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, comment_lower):
                category = 'business' if term in self.BUSINESS_SERVICES else 'personal'
                detected_terms.append({
                    'term': term,
                    'confidence': confidence,
                    'category': category
                })
        
        if not detected_terms:
            return {'detected': False, 'confidence': 0.0, 'terms': [], 'category': None}
        
        # Calculate overall confidence (max of detected terms)
        max_confidence = max(t['confidence'] for t in detected_terms)
        
        # Determine primary category
        business_terms = [t for t in detected_terms if t['category'] == 'business']
        personal_terms = [t for t in detected_terms if t['category'] == 'personal']
        
        if business_terms:
            category = 'business'
        elif personal_terms:
            category = 'personal'
        else:
            category = 'unknown'
        
        return {
            'detected': True,
            'confidence': max_confidence,
            'terms': detected_terms,
            'category': category,
            'comment': comment
        }
    
    def analyze_account_legitimacy(self, transactions: List, comment_analysis: Dict) -> Dict:
        """
        Analyze entire account to determine if it's legitimate business activity.
        
        Looks at the FULL picture:
        1. P2P comments (business terms like "promo", "video", "photography")
        2. Personal P2P comments ("food", "hotel", "haircut", "birthday")
        3. Cash Card spending at normal merchants (gas stations, Walmart, Starbucks)
        4. Flow pattern (bidirectional = more likely legitimate)
        5. Drug slang presence (reduces legitimacy)
        """
        legitimate_comments = []
        business_comments = []
        personal_comments = []
        
        # Analyze P2P comments
        p2p_txns = [tx for tx in transactions if hasattr(tx, 'is_p2p') and tx.is_p2p()]
        for tx in p2p_txns:
            if tx.comment:
                result = self.detect_legitimate_activity(tx.comment)
                if result['detected']:
                    legitimate_comments.append({
                        'comment': tx.comment,
                        'confidence': result['confidence'],
                        'category': result['category'],
                        'terms': result['terms'],
                        'amount': tx.amount,
                        'direction': 'IN' if tx.is_incoming() else 'OUT'
                    })
                    
                    if result['category'] == 'business':
                        business_comments.append(result)
                    elif result['category'] == 'personal':
                        personal_comments.append(result)
        
        # Analyze Cash Card spending (normal merchant purchases = legitimacy signal)
        normal_merchant_keywords = [
            'shell', 'texaco', 'chevron', 'exxon', 'bp ', 'murphy', 'sprint mart',
            'walmart', 'target', 'costco', 'kroger', 'publix', 'aldi',
            'starbucks', 'mcdonald', 'chick-fil', 'subway', 'wendy', 'taco bell',
            'amazon', 'apple.com', 'netflix', 'spotify', 'google', 'uber',
            'walgreens', 'cvs', 'dollar general', 'dollar tree', 'family dollar',
            'home depot', 'lowes', 'autozone', 'o\'reilly',
            'att ', 't-mobile', 'verizon', 'sprint', 'comcast',
            'state farm', 'geico', 'progressive', 'allstate',
            'hibbett', 'nike', 'foot locker', 'old navy', 'ross',
            'bluesky', 'dodge store', 'mi casa',
        ]
        
        cash_card_txns = [tx for tx in transactions 
                         if (tx.product_type or '').upper() == 'CASH_CARD' and tx.comment]
        normal_merchant_count = 0
        for tx in cash_card_txns:
            comment_lower = (tx.comment or '').lower()
            if any(m in comment_lower for m in normal_merchant_keywords):
                normal_merchant_count += 1
        
        # Flow analysis
        completed_p2p = [tx for tx in p2p_txns 
                        if tx.status in ('COMPLETED', 'PAID_OUT', 'SETTLED', 'CAPTURED')]
        incoming_p2p = [tx for tx in completed_p2p if tx.is_incoming()]
        outgoing_p2p = [tx for tx in completed_p2p if tx.is_outgoing()]
        is_bidirectional = len(incoming_p2p) > 0 and len(outgoing_p2p) > 0
        
        # Calculate flow balance (closer to 50/50 = more legitimate)
        total_p2p = len(incoming_p2p) + len(outgoing_p2p)
        if total_p2p > 0:
            flow_balance = min(len(incoming_p2p), len(outgoing_p2p)) / max(len(incoming_p2p), len(outgoing_p2p))
        else:
            flow_balance = 0
        
        # Calculate legitimacy score
        total_comments = len([tx for tx in transactions if tx.comment])
        legitimate_count = len(legitimate_comments)
        business_count = len(business_comments)
        personal_count = len(personal_comments)
        
        if total_comments == 0:
            legitimacy_pct = 0.0
        else:
            legitimacy_pct = (legitimate_count / total_comments) * 100
        
        # Determine if this looks like legitimate business
        is_legitimate_business = False
        confidence = 0.0
        reasoning = []
        
        # Business-related P2P comments
        if business_count > 20:
            confidence += 0.4
            reasoning.append(f"{business_count} business-related P2P comments")
        elif business_count > 10:
            confidence += 0.3
            reasoning.append(f"{business_count} business-related P2P comments")
        elif business_count > 5:
            confidence += 0.2
            reasoning.append(f"{business_count} business-related P2P comments")
        elif business_count > 0:
            confidence += 0.1
            reasoning.append(f"{business_count} business-related P2P comments")
        
        # Personal expense comments
        if personal_count > 10:
            confidence += 0.15
            reasoning.append(f"{personal_count} personal expense comments (food, hotel, etc.)")
        elif personal_count > 5:
            confidence += 0.1
            reasoning.append(f"{personal_count} personal expense comments")
        
        # Mixed personal and business is normal
        if business_count > 0 and personal_count > 0:
            confidence += 0.1
            reasoning.append("Mixed business and personal expenses (normal pattern)")
        
        # Normal Cash Card merchant spending
        if normal_merchant_count > 20:
            confidence += 0.2
            reasoning.append(f"{normal_merchant_count} Cash Card purchases at normal merchants")
        elif normal_merchant_count > 10:
            confidence += 0.15
            reasoning.append(f"{normal_merchant_count} Cash Card purchases at normal merchants")
        elif normal_merchant_count > 5:
            confidence += 0.1
            reasoning.append(f"{normal_merchant_count} Cash Card purchases at normal merchants")
        
        # Bidirectional P2P flow (legitimate accounts send AND receive)
        if is_bidirectional and flow_balance > 0.5:
            confidence += 0.15
            reasoning.append(f"Balanced bidirectional P2P flow ({len(incoming_p2p)} in / {len(outgoing_p2p)} out)")
        elif is_bidirectional and flow_balance > 0.3:
            confidence += 0.1
            reasoning.append(f"Bidirectional P2P flow ({len(incoming_p2p)} in / {len(outgoing_p2p)} out)")
        
        # High percentage of legitimate comments
        if legitimacy_pct > 30:
            confidence += 0.15
            reasoning.append(f"{legitimacy_pct:.0f}% of comments are legitimate")
        elif legitimacy_pct > 20:
            confidence += 0.1
        elif legitimacy_pct > 10:
            confidence += 0.05
        
        # Check for drug slang - if present, reduces legitimacy
        drug_slang_count = comment_analysis.get('high_confidence_count', 0)
        if drug_slang_count > 20:
            confidence -= 0.4
            reasoning.append(f"BUT: {drug_slang_count} high-confidence drug slang comments detected")
        elif drug_slang_count > 10:
            confidence -= 0.3
            reasoning.append(f"BUT: {drug_slang_count} high-confidence drug slang comments detected")
        elif drug_slang_count > 5:
            confidence -= 0.2
        
        # Final determination
        confidence = max(0.0, min(confidence, 1.0))
        is_legitimate_business = confidence > 0.5
        
        return {
            'is_legitimate': is_legitimate_business,
            'confidence': confidence,
            'total_comments': total_comments,
            'legitimate_count': legitimate_count,
            'business_count': business_count,
            'personal_count': personal_count,
            'normal_merchant_count': normal_merchant_count,
            'is_bidirectional': is_bidirectional,
            'flow_balance': flow_balance,
            'legitimacy_percentage': legitimacy_pct,
            'sample_business_comments': legitimate_comments[:10],
            'reasoning': reasoning,
            '_drug_slang_count': drug_slang_count
        }
    
    def should_override_suspicious_detection(self, legitimacy_analysis: Dict, 
                                             typology_results: Dict) -> Dict:
        """
        Determine if legitimate business activity should override suspicious detection.
        
        Key principle: If the account tells a coherent story of legitimate business
        + personal spending, it should override ML/drug sales detection UNLESS
        there are very strong specific indicators (high-confidence drug slang, etc.)
        """
        should_override = False
        reasoning = []
        
        if not legitimacy_analysis['is_legitimate']:
            return {
                'should_override': False,
                'reasoning': ['Legitimacy confidence too low to override'],
                'recommendation': 'Review Required'
            }
        
        legit_confidence = legitimacy_analysis['confidence']
        detected_typologies = typology_results.get('detected_typologies', {})
        
        # No suspicious typologies detected — nothing to override
        if not detected_typologies:
            return {
                'should_override': False,
                'reasoning': ['No suspicious typologies to override'],
                'recommendation': 'Review Required'
            }
        
        # If only Money Laundering detected (no drug sales, no gambling facilitation)
        # ML is the most common false positive for legitimate businesses because
        # high volume + multiple products + bidirectional flow triggers ML patterns
        has_ml = 'Money Laundering' in detected_typologies
        has_drugs = 'Illegal Drug Sales' in detected_typologies
        has_gambling_fac = 'Gambling Facilitation' in detected_typologies
        has_passthrough = 'Pass-Through Money Laundering' in detected_typologies
        
        if has_ml and not has_drugs and not has_gambling_fac:
            # Legitimate business can override ML if confidence is decent
            if legit_confidence >= 0.5:
                should_override = True
                reasoning.append(f"Legitimate business confidence: {legit_confidence:.0%}")
                reasoning.append(f"{legitimacy_analysis['business_count']} business-related comments")
                reasoning.append(f"{legitimacy_analysis.get('personal_count', 0)} personal expense comments")
                if legitimacy_analysis.get('normal_merchant_count', 0) > 0:
                    reasoning.append(f"{legitimacy_analysis['normal_merchant_count']} normal merchant Cash Card purchases")
                if legitimacy_analysis.get('is_bidirectional'):
                    reasoning.append("Balanced bidirectional P2P flow (consistent with legitimate activity)")
                reasoning.append("ML pattern likely triggered by high volume business activity")
        
        # If Drug Sales detected — be very cautious about overriding.
        # Drug dealers can also have normal spending patterns.
        # HOWEVER: if drug slang count is very low (<=5) and legitimacy is very strong,
        # the "drug slang" is likely false positives (🔥 in music context, "Bud" as a name, etc.)
        if has_drugs:
            drug_confidence = detected_typologies['Illegal Drug Sales']['confidence']
            drug_slang_count = legitimacy_analysis.get('_drug_slang_count', 0)
            
            strong_legit_signals = (
                legitimacy_analysis.get('business_count', 0) >= 5 and
                legitimacy_analysis.get('normal_merchant_count', 0) >= 10 and
                legitimacy_analysis.get('is_bidirectional', False) and
                legit_confidence >= 0.7
            )
            
            if strong_legit_signals and drug_slang_count <= 10 and drug_confidence < 0.80:
                should_override = True
                reasoning.append(f"Very strong legitimate pattern ({legit_confidence:.0%}) with only {drug_slang_count} weak drug slang hits")
                reasoning.append("Drug terms likely false positives in legitimate context")
            else:
                should_override = False
                reasoning.append(f"Drug sales detected at {drug_confidence:.0%} — legitimate business cannot override")
        
        # Gambling facilitation should NOT be overridden by legitimacy
        if has_gambling_fac:
            should_override = False
            reasoning.append("Gambling facilitation cannot be overridden by legitimate business indicators")
        
        return {
            'should_override': should_override,
            'reasoning': reasoning,
            'recommendation': 'NOT SUSPICIOUS - Legitimate Business Activity' if should_override else 'Review Required'
        }


# Test the detector
if __name__ == "__main__":
    print("Testing Legitimate Business Detector...\n")
    
    detector = LegitimateBusinessDetector()
    
    # Test cases
    test_cases = [
        "Photography 7.26.24",
        "video editing",
        "story promo",
        "Miami promo",
        "haircut",
        "food",
        "hotel",
        "birthday gift",
        "for the za",
        "gas",
        "cart and pen",
        "rent payment",
        "utilities",
        "massage therapy session"
    ]
    
    print("Individual Comment Tests:\n")
    for comment in test_cases:
        result = detector.detect_legitimate_activity(comment)
        if result['detected']:
            print(f"✓ \"{comment}\"")
            print(f"  Category: {result['category']}")
            print(f"  Confidence: {result['confidence']:.0%}")
            print(f"  Terms: {', '.join([t['term'] for t in result['terms']])}")
        else:
            print(f"✗ \"{comment}\" - No legitimate terms detected")
        print()
