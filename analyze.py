#!/usr/bin/env python3
"""
Simple script to analyze a CSV file
Usage: python3 analyze.py /path/to/your/file.csv
"""

import sys
from pattern_detector import analyze_case

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 analyze.py /path/to/your/file.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    results = analyze_case(csv_path)
    
    print(f"\n✅ Analysis complete! Risk Score: {results['risk_score']:.1f}/100")
    print(f"📋 Detected Typology: {results['detected_typology']}")
