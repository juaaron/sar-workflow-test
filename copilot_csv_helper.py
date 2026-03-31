"""
SAR Workflow Test CSV Helper — Pre-built functions for the copilot to use when analyzing CSVs.
Import this file to get clean, correct data from any SAR Workflow Test CSV.

Usage:
    from copilot_csv_helper import load_case
    data = load_case('/path/to/file.csv')
    
    # Then use:
    data['incoming_p2p']  — all successful incoming P2P transactions
    data['outgoing_p2p']  — all successful outgoing P2P transactions
    data['all_p2p']       — all P2P (including failed)
    data['successful']    — all successful transactions
    data['subjects']      — list of subject tokens
    data['top_senders']   — top counterparties by incoming amount
    data['multi_subject_cps'] — counterparties sending to multiple subjects
"""

import pandas as pd
from collections import defaultdict


def load_case(csv_path):
    """Load and parse a SAR Workflow Test CSV file. Returns a dict with clean, queryable data."""
    
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    
    # Detect format and normalize column names
    if 'TARGET_TOKEN' in df.columns or 'USER_TOKEN' in df.columns:
        # Legacy format
        col_map = {
            'USER_TOKEN': 'subject',
            'COUNTERPARTY_TOKEN': 'counterparty',
            'DIRECTION': 'direction',
            'TRANSACTION_STATUS': 'status',
            'PRODUCT_TYPE': 'product',
            'PRODUCT_SUBTYPE': 'subtype',
            'COMMENT': 'comment',
            'BASE_AMOUNT': 'amount_raw',
            'CREATED_AT': 'date',
        }
    else:
        # Current format
        col_map = {
            'Target Token': 'subject',
            'Counter Party Token': 'counterparty',
            'Role': 'direction',
            'Status': 'status',
            'Product': 'product',
            'Product Type': 'subtype',
            'Comment': 'comment',
            'Amount': 'amount_raw',
            'Date': 'date',
        }
    
    # Rename columns that exist
    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)
    
    # Clean amount
    if 'amount_raw' in df.columns:
        df['amount'] = df['amount_raw'].astype(str).str.replace('$', '').str.replace(',', '').str.strip()
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    elif 'amount' not in df.columns:
        df['amount'] = 0
    
    # Normalize direction
    if 'direction' in df.columns:
        df['is_incoming'] = df['direction'].isin(['RECIPIENT', 'IN'])
        df['is_outgoing'] = df['direction'].isin(['SENDER', 'OUT'])
    
    # Filter system tokens
    system_tokens = ['C_OUTGOING_TRANSFER', 'C_INCOMING_TRANSFER', 'C_BITCOIN_TRANSACTION', 'C_SAVINGS_TRANSFER']
    df['real_cp'] = ~df['counterparty'].isin(system_tokens) & ~df['counterparty'].str.startswith('B$_', na=False) & ~df['counterparty'].str.startswith('M_', na=False)
    
    # Build filtered views
    successful = df[df['status'].isin(['COMPLETED', 'PAID_OUT', 'SETTLED', 'CAPTURED'])]
    p2p = df[df['product'] == 'P2P']
    p2p_success = p2p[p2p['status'].isin(['COMPLETED', 'PAID_OUT', 'SETTLED', 'CAPTURED'])]
    incoming_p2p = p2p_success[(p2p_success['is_incoming']) & (p2p_success['real_cp'])]
    outgoing_p2p = p2p_success[(p2p_success['is_outgoing']) & (p2p_success['real_cp'])]
    
    # Subjects
    subjects = sorted(df['subject'].unique().tolist())
    
    # Top senders by amount
    top_senders = incoming_p2p.groupby('counterparty').agg(
        total_amount=('amount', 'sum'),
        txn_count=('amount', 'count'),
        subjects=('subject', 'nunique'),
        subject_list=('subject', lambda x: sorted(x.unique().tolist())),
        comments=('comment', lambda x: [c for c in x.dropna().unique()[:10] if str(c) != 'nan']),
    ).sort_values('total_amount', ascending=False)
    
    # Multi-subject counterparties
    cp_subjects = incoming_p2p.groupby('counterparty')['subject'].nunique()
    multi_subject = cp_subjects[cp_subjects > 1]
    
    return {
        'df': df,
        'successful': successful,
        'p2p': p2p,
        'p2p_success': p2p_success,
        'incoming_p2p': incoming_p2p,
        'outgoing_p2p': outgoing_p2p,
        'subjects': subjects,
        'subject_count': len(subjects),
        'top_senders': top_senders,
        'multi_subject_cps': multi_subject,
        'multi_subject_count': len(multi_subject),
        'total_incoming': incoming_p2p['amount'].sum(),
        'total_outgoing': outgoing_p2p['amount'].sum(),
    }
