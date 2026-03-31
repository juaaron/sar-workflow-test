"""
kitt Copilot Tools — Functions the LLM can call to query transaction data.

These give the copilot real data analysis capabilities instead of
just reading a text summary.
"""

from typing import List, Dict, Optional
from collections import Counter, defaultdict
from csv_parser import SYSTEM_COUNTERPARTY_TOKENS


class CopilotTools:
    """Tools the LLM can call to query the current case's transaction data."""
    
    def __init__(self, transactions: List):
        self.transactions = transactions
        self.successful = [tx for tx in transactions if tx.is_paid_out()]
        self.failed = [tx for tx in transactions if tx.is_failed()]
        self.p2p = [tx for tx in transactions if tx.is_p2p()]
        self.p2p_success = [tx for tx in self.p2p if tx.is_paid_out()]
        self.subjects = sorted(set(tx.subject for tx in transactions))
    
    def get_top_counterparties(self, direction: str = 'all', limit: int = 10) -> str:
        """Get top counterparties by transaction volume.
        
        Args:
            direction: 'incoming', 'outgoing', or 'all'
            limit: number of results (default 10)
        """
        cp_data = defaultdict(lambda: {'in_count': 0, 'out_count': 0, 'in_total': 0.0, 'out_total': 0.0, 'subjects': set(), 'comments': []})
        
        for tx in self.p2p:
            if tx.counterparty in SYSTEM_COUNTERPARTY_TOKENS:
                continue
            cp = cp_data[tx.counterparty]
            cp['subjects'].add(tx.subject)
            if tx.is_incoming():
                cp['in_count'] += 1
                cp['in_total'] += tx.amount
            else:
                cp['out_count'] += 1
                cp['out_total'] += tx.amount
            if tx.comment and tx.comment.strip():
                cp['comments'].append(tx.comment.strip())
        
        # Sort based on direction
        if direction == 'incoming':
            sorted_cps = sorted(cp_data.items(), key=lambda x: x[1]['in_total'], reverse=True)
        elif direction == 'outgoing':
            sorted_cps = sorted(cp_data.items(), key=lambda x: x[1]['out_total'], reverse=True)
        else:
            sorted_cps = sorted(cp_data.items(), key=lambda x: x[1]['in_total'] + x[1]['out_total'], reverse=True)
        
        lines = [f"Top {limit} counterparties ({direction}):\n"]
        for i, (token, data) in enumerate(sorted_cps[:limit], 1):
            total = data['in_total'] + data['out_total']
            total_count = data['in_count'] + data['out_count']
            unique_comments = list(set(data['comments']))[:5]
            comments_str = ', '.join(f'"{c}"' for c in unique_comments) if unique_comments else 'no comments'
            subjects_list = sorted(data['subjects'])
            
            lines.append(f"{i}. {token}")
            lines.append(f"   Total: {total_count} txns, ${total:,.2f}")
            lines.append(f"   Incoming: {data['in_count']} txns, ${data['in_total']:,.2f}")
            lines.append(f"   Outgoing: {data['out_count']} txns, ${data['out_total']:,.2f}")
            lines.append(f"   Sends to {len(subjects_list)} subject(s): {', '.join(subjects_list)}")
            lines.append(f"   Comments: {comments_str}")
            lines.append("")
        
        return '\n'.join(lines)
    
    def get_transactions_for_counterparty(self, counterparty_token: str) -> str:
        """Get all transactions for a specific counterparty.
        
        Args:
            counterparty_token: The counterparty token (e.g., C_abc123). Partial match supported.
        """
        # Support partial matching
        matches = [tx for tx in self.transactions 
                   if counterparty_token.lower() in (tx.counterparty or '').lower()]
        
        if not matches:
            return f"No transactions found for counterparty matching '{counterparty_token}'"
        
        lines = [f"Transactions for {counterparty_token} ({len(matches)} total):\n"]
        
        # Summary
        successful = [tx for tx in matches if tx.is_paid_out()]
        failed = [tx for tx in matches if tx.is_failed()]
        incoming = [tx for tx in successful if tx.is_incoming()]
        outgoing = [tx for tx in successful if tx.is_outgoing()]
        subjects = set(tx.subject for tx in matches)
        
        lines.append(f"Summary: {len(successful)} successful, {len(failed)} failed")
        lines.append(f"Incoming: {len(incoming)} txns, ${sum(tx.amount for tx in incoming):,.2f}")
        lines.append(f"Outgoing: {len(outgoing)} txns, ${sum(tx.amount for tx in outgoing):,.2f}")
        lines.append(f"Transacts with {len(subjects)} subject account(s): {', '.join(sorted(subjects))}")
        lines.append(f"\nTransaction detail:")
        lines.append(f"{'Date':<20} {'Dir':>3} {'Status':<6} {'Amount':>10} {'Subject':<18} Comment")
        
        sorted_txns = sorted(matches, key=lambda tx: tx.date, reverse=True)
        for tx in sorted_txns[:100]:
            date_str = tx.date.strftime('%Y-%m-%d %H:%M') if hasattr(tx.date, 'strftime') else str(tx.date)[:16]
            d = 'IN' if tx.is_incoming() else 'OUT'
            s = 'OK' if tx.is_paid_out() else 'FAIL'
            comment = (tx.comment or '')[:35]
            lines.append(f"{date_str:<20} {d:>3} {s:<6} ${tx.amount:>9.2f} {tx.subject:<18} {comment}")
        
        if len(matches) > 100:
            lines.append(f"\n... and {len(matches) - 100} more transactions")
        
        return '\n'.join(lines)
    
    def search_comments(self, keyword: str) -> str:
        """Search all transaction comments for a keyword.
        
        Args:
            keyword: Search term (case-insensitive)
        """
        matches = []
        for tx in self.transactions:
            if tx.comment and keyword.lower() in tx.comment.lower():
                matches.append(tx)
        
        if not matches:
            return f"No transactions found with comment containing '{keyword}'"
        
        lines = [f"Transactions with '{keyword}' in comment ({len(matches)} found):\n"]
        
        successful = [tx for tx in matches if tx.is_paid_out()]
        failed = [tx for tx in matches if tx.is_failed()]
        lines.append(f"Successful: {len(successful)}, Failed: {len(failed)}")
        lines.append(f"Total amount (successful): ${sum(tx.amount for tx in successful):,.2f}\n")
        
        sorted_txns = sorted(matches, key=lambda tx: tx.date, reverse=True)
        for tx in sorted_txns[:50]:
            date_str = tx.date.strftime('%Y-%m-%d %H:%M') if hasattr(tx.date, 'strftime') else str(tx.date)[:16]
            d = 'IN' if tx.is_incoming() else 'OUT'
            s = 'OK' if tx.is_paid_out() else 'FAIL'
            lines.append(f"{date_str} {d:>3} {s:<6} ${tx.amount:>9.2f} {tx.counterparty:<18} \"{tx.comment}\"")
        
        if len(matches) > 50:
            lines.append(f"\n... and {len(matches) - 50} more")
        
        return '\n'.join(lines)
    
    def get_transactions_by_amount(self, min_amount: float = 0, max_amount: float = 999999) -> str:
        """Get transactions within an amount range.
        
        Args:
            min_amount: Minimum amount (default 0)
            max_amount: Maximum amount (default 999999)
        """
        matches = [tx for tx in self.successful if min_amount <= tx.amount <= max_amount]
        
        if not matches:
            return f"No successful transactions found between ${min_amount:.2f} and ${max_amount:.2f}"
        
        lines = [f"Transactions between ${min_amount:.2f} and ${max_amount:.2f} ({len(matches)} found):\n"]
        
        incoming = [tx for tx in matches if tx.is_incoming()]
        outgoing = [tx for tx in matches if tx.is_outgoing()]
        lines.append(f"Incoming: {len(incoming)} (${sum(tx.amount for tx in incoming):,.2f})")
        lines.append(f"Outgoing: {len(outgoing)} (${sum(tx.amount for tx in outgoing):,.2f})\n")
        
        sorted_txns = sorted(matches, key=lambda tx: tx.amount, reverse=True)
        for tx in sorted_txns[:50]:
            date_str = tx.date.strftime('%Y-%m-%d %H:%M') if hasattr(tx.date, 'strftime') else str(tx.date)[:16]
            d = 'IN' if tx.is_incoming() else 'OUT'
            comment = (tx.comment or '')[:30]
            lines.append(f"{date_str} {d:>3} ${tx.amount:>9.2f} {tx.counterparty:<18} {comment}")
        
        if len(matches) > 50:
            lines.append(f"\n... and {len(matches) - 50} more")
        
        return '\n'.join(lines)
    
    def get_transactions_by_time(self, start_hour: int = 0, end_hour: int = 24) -> str:
        """Get transactions within a time-of-day range.
        
        Args:
            start_hour: Start hour (0-23)
            end_hour: End hour (0-24)
        """
        matches = []
        for tx in self.successful:
            if hasattr(tx.date, 'hour'):
                if start_hour <= tx.date.hour < end_hour:
                    matches.append(tx)
        
        if not matches:
            return f"No transactions found between {start_hour}:00 and {end_hour}:00"
        
        lines = [f"Transactions between {start_hour}:00 and {end_hour}:00 ({len(matches)} found):\n"]
        
        incoming = [tx for tx in matches if tx.is_incoming()]
        outgoing = [tx for tx in matches if tx.is_outgoing()]
        lines.append(f"Incoming: {len(incoming)} (${sum(tx.amount for tx in incoming):,.2f})")
        lines.append(f"Outgoing: {len(outgoing)} (${sum(tx.amount for tx in outgoing):,.2f})\n")
        
        sorted_txns = sorted(matches, key=lambda tx: tx.date, reverse=True)
        for tx in sorted_txns[:50]:
            date_str = tx.date.strftime('%Y-%m-%d %H:%M') if hasattr(tx.date, 'strftime') else str(tx.date)[:16]
            d = 'IN' if tx.is_incoming() else 'OUT'
            comment = (tx.comment or '')[:30]
            lines.append(f"{date_str} {d:>3} ${tx.amount:>9.2f} {tx.counterparty:<18} {comment}")
        
        if len(matches) > 50:
            lines.append(f"\n... and {len(matches) - 50} more")
        
        return '\n'.join(lines)
    
    def get_subject_summary(self, subject_token: str = '') -> str:
        """Get detailed summary for a specific subject account, or all subjects.
        
        Args:
            subject_token: Subject token. If empty, summarizes all subjects.
        """
        if subject_token:
            txns = [tx for tx in self.transactions if subject_token.lower() in tx.subject.lower()]
            subjects = [subject_token]
        else:
            txns = self.transactions
            subjects = self.subjects
        
        if not txns:
            return f"No transactions found for subject '{subject_token}'"
        
        lines = [f"Subject Summary ({len(subjects)} subjects):\n"]
        
        for subj in subjects:
            s_txns = [tx for tx in txns if tx.subject == subj]
            s_success = [tx for tx in s_txns if tx.is_paid_out()]
            s_in = [tx for tx in s_success if tx.is_incoming()]
            s_out = [tx for tx in s_success if tx.is_outgoing()]
            s_cps = set(tx.counterparty for tx in s_txns if tx.has_real_counterparty())
            
            lines.append(f"{subj}:")
            lines.append(f"  Total: {len(s_txns)} txns ({len(s_success)} successful, {len(s_txns)-len(s_success)} failed)")
            lines.append(f"  Incoming: {len(s_in)} txns, ${sum(tx.amount for tx in s_in):,.2f}")
            lines.append(f"  Outgoing: {len(s_out)} txns, ${sum(tx.amount for tx in s_out):,.2f}")
            lines.append(f"  Unique counterparties: {len(s_cps)}")
            lines.append("")
        
        return '\n'.join(lines)
    
    def get_cross_subject_counterparties(self) -> str:
        """Find counterparties that transact with multiple subject accounts."""
        
        cp_subjects = defaultdict(lambda: {'subjects': set(), 'txn_count': 0, 'total': 0.0})
        
        for tx in self.p2p:
            if tx.counterparty in SYSTEM_COUNTERPARTY_TOKENS:
                continue
            cp = cp_subjects[tx.counterparty]
            cp['subjects'].add(tx.subject)
            cp['txn_count'] += 1
            cp['total'] += tx.amount
        
        multi = {k: v for k, v in cp_subjects.items() if len(v['subjects']) > 1}
        
        if not multi:
            return "No counterparties found transacting with multiple subject accounts."
        
        lines = [f"Counterparties sending to multiple subjects ({len(multi)} found):\n"]
        
        sorted_multi = sorted(multi.items(), key=lambda x: len(x[1]['subjects']), reverse=True)
        for cp, data in sorted_multi[:30]:
            lines.append(f"{cp}: {len(data['subjects'])} subjects, {data['txn_count']} txns, ${data['total']:,.2f}")
            lines.append(f"  Subjects: {', '.join(sorted(data['subjects']))}")
            lines.append("")
        
        return '\n'.join(lines)
    
    def get_amount_distribution(self, product: str = 'P2P', direction: str = 'incoming') -> str:
        """Get amount distribution for a product type.
        
        Args:
            product: Product type (P2P, CASH_CARD, TRANSFERS, etc.)
            direction: 'incoming', 'outgoing', or 'all'
        """
        txns = [tx for tx in self.successful if (tx.product_type or '').upper() == product.upper()]
        
        if direction == 'incoming':
            txns = [tx for tx in txns if tx.is_incoming()]
        elif direction == 'outgoing':
            txns = [tx for tx in txns if tx.is_outgoing()]
        
        if not txns:
            return f"No {direction} {product} transactions found"
        
        amounts = [tx.amount for tx in txns]
        
        lines = [f"Amount distribution for {direction} {product} ({len(txns)} txns):\n"]
        lines.append(f"Range: ${min(amounts):.2f} - ${max(amounts):.2f}")
        lines.append(f"Average: ${sum(amounts)/len(amounts):.2f}")
        lines.append(f"Median: ${sorted(amounts)[len(amounts)//2]:.2f}")
        lines.append(f"Round dollar: {sum(1 for a in amounts if a == int(a))}/{len(amounts)} ({sum(1 for a in amounts if a == int(a))/len(amounts)*100:.0f}%)\n")
        
        ranges = [(1,5),(6,10),(11,25),(26,50),(51,100),(101,200),(201,500),(501,1000),(1001,99999)]
        for lo, hi in ranges:
            count = sum(1 for a in amounts if lo <= a <= hi)
            total = sum(a for a in amounts if lo <= a <= hi)
            if count > 0:
                bar = '█' * min(int(count / len(amounts) * 40), 40)
                lines.append(f"  ${lo:>6}-${hi:<6}: {count:>4} txns (${total:>10,.2f}) {bar}")
        
        return '\n'.join(lines)
    
    def get_timeline(self, counterparty: str = '', days: int = 0) -> str:
        """Get transaction timeline, optionally filtered by counterparty.
        
        Args:
            counterparty: Filter by counterparty token (optional, partial match)
            days: Show last N days only (0 = all)
        """
        txns = self.successful
        
        if counterparty:
            txns = [tx for tx in txns if counterparty.lower() in (tx.counterparty or '').lower()]
        
        if not txns:
            return "No transactions found"
        
        # Group by date
        daily = defaultdict(lambda: {'count': 0, 'in_total': 0.0, 'out_total': 0.0})
        for tx in txns:
            if hasattr(tx.date, 'date'):
                day = tx.date.date()
            else:
                day = str(tx.date)[:10]
            daily[day]['count'] += 1
            if tx.is_incoming():
                daily[day]['in_total'] += tx.amount
            else:
                daily[day]['out_total'] += tx.amount
        
        sorted_days = sorted(daily.items(), reverse=True)
        if days > 0:
            sorted_days = sorted_days[:days]
        
        lines = [f"Transaction timeline ({len(sorted_days)} days with activity):\n"]
        lines.append(f"{'Date':<12} {'Txns':>5} {'Inflows':>12} {'Outflows':>12}")
        
        for day, data in sorted_days[:60]:
            lines.append(f"{str(day):<12} {data['count']:>5} ${data['in_total']:>11,.2f} ${data['out_total']:>11,.2f}")
        
        if len(sorted_days) > 60:
            lines.append(f"\n... and {len(sorted_days) - 60} more days")
        
        return '\n'.join(lines)


# Tool definitions for OpenAI function calling
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_top_counterparties",
            "description": "Get the top counterparties by transaction volume. Use this when the analyst asks about top senders, top recipients, biggest counterparties, or who is sending/receiving the most money.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["incoming", "outgoing", "all"], "description": "Filter by direction. 'incoming' = senders, 'outgoing' = recipients."},
                    "limit": {"type": "integer", "description": "Number of results to return (default 10)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_transactions_for_counterparty",
            "description": "Get all transactions for a specific counterparty. Use when analyst asks about a specific person/token's activity, history, or transactions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "counterparty_token": {"type": "string", "description": "The counterparty token (e.g., C_abc123). Partial match supported."}
                },
                "required": ["counterparty_token"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_comments",
            "description": "Search all transaction comments for a keyword. Use when analyst asks about specific comments, slang terms, or patterns in payment descriptions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Search term (case-insensitive)"}
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_transactions_by_amount",
            "description": "Get transactions within an amount range. Use when analyst asks about large transactions, small transactions, or specific dollar amounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_amount": {"type": "number", "description": "Minimum amount"},
                    "max_amount": {"type": "number", "description": "Maximum amount"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_transactions_by_time",
            "description": "Get transactions within a time-of-day range. Use when analyst asks about late night activity, morning transactions, or time patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_hour": {"type": "integer", "description": "Start hour (0-23)"},
                    "end_hour": {"type": "integer", "description": "End hour (0-24)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_subject_summary",
            "description": "Get detailed summary for subject account(s). Use when analyst asks about subjects, account holders, or wants a breakdown per subject.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject_token": {"type": "string", "description": "Subject token. Leave empty for all subjects."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cross_subject_counterparties",
            "description": "Find counterparties that transact with multiple subject accounts. Use when analyst asks about shared counterparties, network connections, or cross-account activity.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_amount_distribution",
            "description": "Get amount distribution breakdown for a product type. Use when analyst asks about payment patterns, common amounts, or amount ranges.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product": {"type": "string", "description": "Product type: P2P, CASH_CARD, TRANSFERS"},
                    "direction": {"type": "string", "enum": ["incoming", "outgoing", "all"], "description": "Filter direction"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_timeline",
            "description": "Get daily transaction timeline. Use when analyst asks about activity over time, specific dates, or temporal patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "counterparty": {"type": "string", "description": "Optional: filter by counterparty token"},
                    "days": {"type": "integer", "description": "Show last N days only (0 = all)"}
                }
            }
        }
    }
]
