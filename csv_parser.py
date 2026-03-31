"""
SAR Platform - Flexible CSV Parser
Handles multiple CSV formats and normalizes to internal data model
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import re


class CSVFormat:
    """Defines a CSV format mapping"""
    
    def __init__(self, name: str, column_mapping: Dict[str, str]):
        self.name = name
        self.column_mapping = column_mapping
    
    def matches(self, df: pd.DataFrame) -> bool:
        """Check if this format matches the dataframe columns"""
        required_cols = set(self.column_mapping.values())
        actual_cols = set(df.columns)
        return required_cols.issubset(actual_cols)


# Define supported formats
OLD_FORMAT = CSVFormat(
    name="Legacy Format (2023)",
    column_mapping={
        'date': 'CREATED_AT',
        'subject': 'USER_TOKEN',
        'counterparty': 'COUNTERPARTY_TOKEN',
        'amount': 'BASE_AMOUNT',
        'currency': 'BASE_AMOUNT_CURRENCY_CODE',
        'direction': 'DIRECTION',
        'comment': 'COMMENT',
        'status': 'TRANSACTION_STATUS',
        'product_type': 'PRODUCT_TYPE',
    }
)

NEW_FORMAT = CSVFormat(
    name="Current Format (2024+)",
    column_mapping={
        'date': 'Date',
        'subject': 'Target Token',
        'counterparty': 'Counter Party Token',
        'amount': 'Amount',
        'currency': 'Amount (currency)',
        'direction': 'Role',  # RECIPIENT or SENDER
        'comment': 'Comment',
        'status': 'Status',
        'product_type': 'Product',  # Changed from 'Product Type' to 'Product'
        'action': 'Action',
    }
)


    # System-generated counterparty tokens that represent internal transfers, not real people
SYSTEM_COUNTERPARTY_TOKENS = {
    'C_OUTGOING_TRANSFER', 'C_INCOMING_TRANSFER', 'C_BITCOIN_TRANSACTION',
    'C_SAVINGS_TRANSFER', 'C_EXTERNAL_MERCHANT',
}


class TransactionRecord:
    """Normalized transaction record"""
    
    def __init__(self, data: Dict):
        self.date = data['date']
        self.subject = data['subject']
        self.counterparty = data['counterparty']
        self.amount = data['amount']
        self.currency = data.get('currency', 'USD')
        self.direction = data['direction']  # IN or OUT
        self.comment = data.get('comment', '')
        self.status = data['status']
        self.product_type = data.get('product_type', '')      # e.g. P2P, CASH_CARD, TRANSFERS
        self.product_subtype = data.get('product_subtype', '') # e.g. PAYMENT_FIAT, CASH_OUT, PAPER_MONEY_DEPOSIT
        self.raw_data = data
    
    def is_incoming(self) -> bool:
        """Check if transaction is incoming to subject"""
        return self.direction == 'IN'
    
    def is_outgoing(self) -> bool:
        """Check if transaction is outgoing from subject"""
        return self.direction == 'OUT'
    
    def is_paid_out(self) -> bool:
        """Check if transaction completed successfully.
        Covers all success statuses: PAID_OUT, COMPLETED, SETTLED, CAPTURED.
        """
        status = self.status.upper()
        return any(s in status for s in ('PAID_OUT', 'COMPLETED', 'SETTLED', 'CAPTURED'))
    
    def is_failed(self) -> bool:
        """Check if transaction failed"""
        return 'FAIL' in self.status.upper()
    
    def has_real_counterparty(self) -> bool:
        """Check if counterparty is a real person (not a system/internal token)"""
        if not self.counterparty or self.counterparty in ('nan', ''):
            return False
        if self.counterparty in SYSTEM_COUNTERPARTY_TOKENS:
            return False
        # Filter out internal balance/wallet tokens (B$_, B$_BTC_, M_, etc.)
        if self.counterparty.startswith('B$_') or self.counterparty.startswith('M_'):
            return False
        return True
    
    def is_p2p(self) -> bool:
        """Check if this is a P2P transaction"""
        return 'P2P' in self.product_type.upper()
    
    def __repr__(self):
        return f"Transaction({self.date}, {self.direction}, ${self.amount}, {self.status})"


class CSVParser:
    """Flexible CSV parser that handles multiple formats"""
    
    def __init__(self):
        self.formats = [NEW_FORMAT, OLD_FORMAT]
        self.detected_format = None
    
    def parse(self, filepath: str) -> List[TransactionRecord]:
        """Parse CSV file and return normalized transaction records"""
        
        # Read CSV
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        print(f"✓ Loaded CSV: {len(df)} rows, {len(df.columns)} columns")
        
        # Detect format
        self.detected_format = self._detect_format(df)
        if not self.detected_format:
            raise ValueError(f"Could not detect CSV format. Columns found: {list(df.columns)}")
        
        print(f"✓ Detected format: {self.detected_format.name}")
        
        # Normalize data
        transactions = self._normalize_data(df, self.detected_format)
        print(f"✓ Parsed {len(transactions)} transactions")
        
        return transactions
    
    def _detect_format(self, df: pd.DataFrame) -> Optional[CSVFormat]:
        """Auto-detect which format this CSV uses"""
        for fmt in self.formats:
            if fmt.matches(df):
                return fmt
        return None
    
    def _normalize_data(self, df: pd.DataFrame, fmt: CSVFormat) -> List[TransactionRecord]:
        """Convert CSV data to normalized transaction records"""
        transactions = []
        
        for _, row in df.iterrows():
            try:
                # Extract and normalize fields based on format
                # Get product subtype if available (e.g. PAYMENT_FIAT, CASH_OUT, PAPER_MONEY_DEPOSIT)
                product_subtype = ''
                if 'Product Type' in row.index:
                    product_subtype = str(row.get('Product Type', ''))
                elif 'PRODUCT_SUBTYPE' in row.index:
                    product_subtype = str(row.get('PRODUCT_SUBTYPE', ''))
                    if product_subtype in ('nan', 'None'):
                        product_subtype = ''
                
                normalized = {
                    'date': self._parse_date(row[fmt.column_mapping['date']]),
                    'subject': str(row[fmt.column_mapping['subject']]),
                    'counterparty': str(row[fmt.column_mapping['counterparty']]),
                    'amount': self._parse_amount(row[fmt.column_mapping['amount']]),
                    'currency': row.get(fmt.column_mapping.get('currency', ''), 'USD'),
                    'direction': self._normalize_direction(
                        row[fmt.column_mapping['direction']], 
                        fmt.name
                    ),
                    'comment': str(row.get(fmt.column_mapping.get('comment', ''), '')) if str(row.get(fmt.column_mapping.get('comment', ''), '')) not in ('nan', 'None', '') else '',
                    'status': str(row[fmt.column_mapping['status']]),
                    'product_type': str(row.get(fmt.column_mapping.get('product_type', ''), '')),
                    'product_subtype': product_subtype,
                }
                
                transactions.append(TransactionRecord(normalized))
                
            except Exception as e:
                print(f"Warning: Could not parse row: {e}")
                continue
        
        return transactions
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date from various formats"""
        try:
            # Try ISO format first
            if 'T' in str(date_str):
                return pd.to_datetime(date_str)
            # Try common formats
            return pd.to_datetime(date_str)
        except:
            return datetime.now()
    
    def _parse_amount(self, amount_str) -> float:
        """Parse amount from string (handles $X.XX format)"""
        if pd.isna(amount_str):
            return 0.0
        
        # Remove currency symbols and commas
        amount_str = str(amount_str).replace('$', '').replace(',', '').strip()
        
        try:
            return float(amount_str)
        except:
            return 0.0
    
    def _normalize_direction(self, direction_str: str, format_name: str) -> str:
        """Normalize direction to IN or OUT"""
        direction_str = str(direction_str).upper()
        
        if 'CURRENT FORMAT' in format_name or '2024' in format_name:
            # New format uses RECIPIENT/SENDER
            # RECIPIENT = money coming IN to subject
            # SENDER = money going OUT from subject
            if 'RECIPIENT' in direction_str:
                return 'IN'
            elif 'SENDER' in direction_str:
                return 'OUT'
        else:
            # Old format uses IN/OUT directly
            if direction_str == 'IN':
                return 'IN'
            elif direction_str == 'OUT':
                return 'OUT'
        
        return 'UNKNOWN'


def test_parser():
    """Test the parser with both formats"""
    
    print("=" * 60)
    print("TESTING CSV PARSER")
    print("=" * 60)
    
    parser = CSVParser()
    
    # Test new format
    print("\n📄 Testing NEW format (23316445.csv)...")
    try:
        transactions = parser.parse('/Users/gkirk/Downloads/23316445.csv')
        print(f"\n✅ Successfully parsed {len(transactions)} transactions")
        print(f"   Format: {parser.detected_format.name}")
        print(f"\n   Sample transactions:")
        for tx in transactions[:3]:
            print(f"   - {tx}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test old format
    print("\n📄 Testing OLD format (B456100271.csv)...")
    try:
        transactions = parser.parse('/Users/gkirk/Desktop/Thu Mar 12 18-47-53 2026/Downloads/B456100271.csv')
        print(f"\n✅ Successfully parsed {len(transactions)} transactions")
        print(f"   Format: {parser.detected_format.name}")
        print(f"\n   Sample transactions:")
        for tx in transactions[:3]:
            print(f"   - {tx}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_parser()
