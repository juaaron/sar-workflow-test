#!/usr/bin/env python3
"""
Test Pass-Through Money Laundering Detector on KGB.csv
"""

from csv_parser import CSVParser
from passthrough_detector import PassThroughDetector

def main():
    # Parse the CSV
    parser = CSVParser()
    transactions = parser.parse('/Users/gkirk/Downloads/KGB.csv')
    
    print(f"Loaded {len(transactions)} transactions")
    print()
    
    # Convert to dict format for detector
    transaction_dicts = []
    for t in transactions:
        transaction_dicts.append({
            'date': t.date,
            'counterparty': t.counterparty,
            'amount': t.amount,
            'direction': t.direction,
            'comment': t.comment,
            'product_type': t.product_type,
            'status': t.status
        })
    
    # Run pass-through detection
    detector = PassThroughDetector()
    indicators = detector.analyze(transaction_dicts)
    
    # Print results
    print(detector.format_analysis(indicators))
    
    # Recommendation
    if indicators.confidence >= 80:
        print("🚨 RECOMMENDATION: FILE SAR - CRITICAL PASS-THROUGH MONEY LAUNDERING")
    elif indicators.confidence >= 60:
        print("⚠️  RECOMMENDATION: FILE SAR - HIGH CONFIDENCE PASS-THROUGH MONEY LAUNDERING")
    elif indicators.confidence >= 40:
        print("⚡ RECOMMENDATION: INVESTIGATE FURTHER - MEDIUM CONFIDENCE")
    else:
        print("✅ RECOMMENDATION: NO SAR - LOW CONFIDENCE")

if __name__ == '__main__':
    main()
