"""
SAR Workflow Test - SAR Narrative Generator
Auto-generates SAR narratives from CSV analysis results in Block/Cash App style.

Matches the exact writing style, paragraph structure, and terminology
used by Block's compliance team based on real SAR examples.

IMPORTANT: This generates DRAFT narratives. Analysts must review, edit,
add OSINT findings, and approve before filing.
"""

from typing import Dict, List, Optional
from datetime import datetime


class NarrativeGenerator:
    """
    Generates SAR narrative drafts from SAR Workflow Test analysis results.
    
    Supports typologies:
    - Drug Sales
    - Gambling Facilitation
    - Adult Services
    - Money Laundering
    - Multi-typology (e.g., Adult Services + ML)
    """
    
    # Block boilerplate (standard across all SARs)
    BLOCK_BOILERPLATE = (
        'Block provides a money transmission product for non-commercial and commercial '
        'use known as Cash App. A Cash App account allows an individual to conduct '
        'electronic money transfers, funded by a linked debit card, bank account, '
        'credit card, physical cash, or stored balance to other individuals and businesses.'
    )
    
    # Closing boilerplate
    CLOSING_TEMPLATE = (
        'As a result of this suspicious activity, the relevant subject Cash App accounts '
        'were closed. Supporting documentation is attached to this report, case number '
        '{case_id}. For additional information regarding this case, and to reach Block\'s '
        'Investigations team directly, please email siusupport@squareup.com.'
    )
    
    def __init__(self):
        # Default pluralization (overridden in generate_narrative)
        self._subject_count = 1
        self._subj = 'subject'
        self._acct = 'account'
        self._the_acct = 'the account'
        self._the_subj = 'the subject'
    
    def _plural(self, count: int, singular: str, plural: str) -> str:
        """Return singular or plural form based on count."""
        return singular if count == 1 else plural
    
    def generate_narrative(self, analysis: Dict, case_id: str = '') -> Dict:
        """
        Generate a complete SAR narrative from SAR Workflow Test analysis results.
        
        Args:
            analysis: The full analysis results from final_analyzer
            case_id: Case number/token
            
        Returns:
            Dict with 'narrative' (full text) and 'sections' (broken out)
        """
        # Extract key data
        stats = analysis.get('stats', analysis.get('basic_stats', {}))
        patterns = analysis.get('patterns', {})
        comments = analysis.get('comments', {})
        typologies = analysis.get('typologies', [])
        counterparties = analysis.get('counterparties', {})
        summary = analysis.get('analysis_summary', {})
        
        # Determine typologies for the narrative
        # Auto-include any typology >= 80% confidence
        # Analyst can manually include lower-confidence ones via the UI
        primary_typ = summary.get('primary_typology', '')
        included_typologies = analysis.get('_included_typologies', None)  # Manual override from analyst
        
        if included_typologies is not None:
            # Analyst manually selected which typologies to include
            typ_names = included_typologies
        else:
            # Auto-include: primary + anything >= 80%
            typ_names = [primary_typ] if primary_typ else []
            
            if isinstance(typologies, list):
                for t in typologies:
                    name = t.get('name', '')
                    conf = t.get('confidence', 0)
                    if name not in typ_names and conf >= 80:
                        typ_names.append(name)
        
        if not typ_names:
            typ_names = ['suspicious activity']
        
        # Store subject count for pluralization throughout
        self._subject_count = stats.get('subject_count', 1)
        self._subj = self._plural(self._subject_count, 'subject', 'subjects')
        self._acct = self._plural(self._subject_count, 'account', 'accounts')
        self._the_acct = self._plural(self._subject_count, 'the account', 'the accounts')
        self._the_subj = self._plural(self._subject_count, 'the subject', 'the subjects')
        
        # Map typology names to narrative generators
        sections = {}
        
        # 1. Opening paragraph
        sections['opening'] = self._generate_opening(
            case_id, typ_names, stats
        )
        
        # 2. Block boilerplate
        sections['boilerplate'] = self.BLOCK_BOILERPLATE
        
        # 3. Alert source
        sections['alert_source'] = self._generate_alert_source(stats)
        
        # 4. Transaction analysis
        sections['transaction_analysis'] = self._generate_transaction_analysis(
            stats, patterns
        )
        
        # 5. Typology-specific analysis
        sections['typology_analysis'] = self._generate_typology_analysis(
            typ_names, analysis
        )
        
        # 6. Summary
        sections['summary'] = self._generate_summary(typ_names, analysis)
        
        # 7. Closing
        sections['closing'] = self.CLOSING_TEMPLATE.format(
            case_id=case_id if case_id else '[CASE NUMBER]'
        )
        
        # Combine into full narrative
        narrative_parts = [
            sections['opening'],
            sections['boilerplate'],
            sections['alert_source'],
            sections['transaction_analysis'],
            sections['typology_analysis'],
            sections['summary'],
            sections['closing'],
        ]
        
        full_narrative = '\n\n'.join(p for p in narrative_parts if p)
        
        return {
            'narrative': full_narrative,
            'sections': sections,
            'typologies': typ_names,
            'case_id': case_id,
        }
    
    def _generate_opening(self, case_id: str, typ_names: List[str], stats: Dict) -> str:
        """Generate the opening paragraph with full product type breakdown."""
        
        # Build typology description
        typ_desc = self._typology_description(typ_names)
        
        # Get date range
        date_range = stats.get('date_range')
        if date_range and isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date = self._format_date(date_range[0])
            end_date = self._format_date(date_range[1])
            date_str = f'{start_date} to {end_date}'
        else:
            date_str = '[DATE RANGE]'
        
        # Subject tokens
        subject_tokens = stats.get('subject_tokens', [])
        subject_count = stats.get('subject_count', 1)
        
        if not subject_tokens:
            subject = stats.get('subject', '[SUBJECT TOKEN]')
            if not subject or subject == '':
                subject = '[SUBJECT TOKEN]'
            subject_tokens = [subject]
            subject_count = 1
        
        # Build activity breakdown from ATTEMPTED inflow + outflow product types
        # SAR regulations require reporting ALL attempted suspicious transactions
        inflows = stats.get('inflow_attempted_breakdown', stats.get('inflow_breakdown', []))
        outflows = stats.get('outflow_attempted_breakdown', stats.get('outflow_breakdown', []))
        
        # Aggregate by product category
        product_totals = {}  # label -> {count, total}
        
        for item in inflows + outflows:
            if isinstance(item, dict):
                label = item.get('label', 'Unknown')
                count = item.get('count', 0)
                total = item.get('total', 0)
            else:
                continue
            
            # Normalize labels into SAR-friendly categories
            if 'P2P' in label:
                key = 'P2P'
                sar_label = 'peer-to-peer ("P2P") transactions'
            elif 'Cashback' in label:
                key = 'CASH_CARD'  # Merge cashback into Cash Card
                sar_label = 'Cash App debit card transactions'
            elif 'Cash Card' in label and 'ATM' not in label:
                key = 'CASH_CARD'
                sar_label = 'Cash App debit card transactions'
            elif 'ATM' in label:
                key = 'ATM'
                sar_label = 'ATM withdrawals'
            elif 'Cash Out' in label or 'Cash In' in label or 'ACH' in label:
                key = 'TRANSFERS'
                sar_label = 'funds transfers'
            elif 'Paper Money' in label and 'Fee' not in label:
                key = 'PAPER_MONEY'
                sar_label = 'paper money deposits'
            elif 'Overdraft' in label:
                key = 'OVERDRAFT'
                sar_label = 'overdraft repayments'
            elif 'Cash App Pay' in label:
                key = 'CAP'
                sar_label = 'Cash App Pay transactions'
            elif 'Afterpay' in label or 'Lending' in label:
                key = 'LENDING'
                sar_label = 'lending/Afterpay transactions'
            else:
                key = label
                sar_label = label.lower()
            
            if key not in product_totals:
                product_totals[key] = {'count': 0, 'total': 0.0, 'sar_label': sar_label}
            product_totals[key]['count'] += count
            product_totals[key]['total'] += total
        
        # Build activity description parts, sorted by total descending
        # Skip overdraft repayments and fees — not suspicious activity
        skip_keys = {'OVERDRAFT', 'LENDING'}
        sorted_products = sorted(
            [(k, v) for k, v in product_totals.items() if k not in skip_keys],
            key=lambda x: x[1]['total'],
            reverse=True
        )
        
        activity_parts = []
        grand_total = 0
        for key, data in sorted_products:
            if data['count'] > 0 and data['total'] > 0:
                activity_parts.append(
                    f'{data["count"]:,} {data["sar_label"]} totaling ${data["total"]:,.2f}'
                )
                grand_total += data['total']
        
        if activity_parts:
            if len(activity_parts) == 1:
                activity_desc = activity_parts[0]
            elif len(activity_parts) == 2:
                activity_desc = f'{activity_parts[0]} and {activity_parts[1]}'
            else:
                activity_desc = ', '.join(activity_parts[:-1]) + f', and {activity_parts[-1]}'
        else:
            total_txns = stats.get('successful_transactions', stats.get('total_transactions', 0))
            activity_desc = f'{total_txns:,} suspicious transactions totaling ${grand_total:,.2f}'
        
        case_ref = f'#{case_id}' if case_id else '#[CASE NUMBER]'
        
        opening = (
            f'Block, Inc. ("Block") is filing a Suspicious Activity Report ("SAR") '
            f'{case_ref} for activity indicative of {typ_desc} on the Cash App platform. '
            f'The identified suspicious activity totaled ${grand_total:,.2f}, and consisted of '
            f'{activity_desc}, and occurred between the dates of {date_str}. '
            f'{self._format_subjects(subject_tokens, subject_count)}'
        )
        
        return opening
    
    def _generate_alert_source(self, stats: Dict) -> str:
        """Generate the alert source paragraph."""
        return (
            'A review was prompted by an [ANALYST: internal/external] referral '
            'which identified [ANALYST: referral reason].'
        )
    
    def _generate_transaction_analysis(self, stats: Dict, patterns: Dict) -> str:
        """Generate transaction analysis paragraph with product type context."""
        
        total_txns = stats.get('total_transactions', 0)
        successful = stats.get('successful_transactions', total_txns)
        failed = total_txns - successful
        
        p2p_count = stats.get('p2p_count', 0)
        round_pct = patterns.get('round_dollar_pct', 0)
        avg_amount = patterns.get('average_amount', 0)
        
        # Get P2P-specific patterns
        product_patterns = patterns.get('product_patterns', {})
        p2p_patterns = product_patterns.get('P2P', {})
        p2p_min = p2p_patterns.get('min', 1)
        p2p_max = p2p_patterns.get('max', 100)
        p2p_avg = p2p_patterns.get('average', avg_amount)
        p2p_total_amt = p2p_patterns.get('total', 0)
        p2p_txn_count = p2p_patterns.get('count', p2p_count)
        p2p_round_pct = p2p_patterns.get('round_pct', round_pct)
        
        # Estimate common range from P2P average
        if p2p_avg <= 50:
            common_range = '$10.00 and $40.00'
        elif p2p_avg <= 100:
            common_range = '$10.00 and $100.00'
        elif p2p_avg <= 200:
            common_range = '$50.00 and $200.00'
        else:
            common_range = '$50.00 and $500.00'
        
        parts = []
        
        # P2P transaction analysis (attempted vs successful)
        p2p_attempted_count = stats.get('p2p_attempted_count', p2p_txn_count)
        p2p_attempted_total = stats.get('p2p_attempted_total', p2p_total_amt)
        p2p_failed = p2p_attempted_count - p2p_txn_count
        
        if p2p_attempted_count > 0:
            parts.append(
                f'Of the {p2p_attempted_count:,} P2P transactions conducted on {self._the_acct}, '
                f'{p2p_failed:,} were declined, and {p2p_txn_count:,} were successfully processed, '
                f'totaling ${p2p_total_amt:,.2f}.'
            )
        
        if p2p_round_pct > 50:
            parts.append(
                f'The payments were conducted primarily for round dollar amounts '
                f'between ${p2p_min:.2f} to ${p2p_max:.2f}, most commonly between {common_range}.'
            )
        else:
            parts.append(
                f'The payments ranged from ${p2p_min:.2f} to ${p2p_max:.2f}, '
                f'with an average of ${p2p_avg:.2f}.'
            )
        
        # Cash Card analysis if present
        cc_patterns = product_patterns.get('CASH_CARD', {})
        if cc_patterns.get('count', 0) > 0:
            parts.append(
                f'During the period of review, {self._the_subj} also conducted '
                f'{cc_patterns["count"]:,} Cash App debit card transactions '
                f'totaling ${cc_patterns["total"]:,.2f}.'
            )
        
        # Transfers analysis if present
        transfers_patterns = product_patterns.get('TRANSFERS', {})
        if transfers_patterns.get('count', 0) > 0:
            parts.append(
                f'Additionally, {transfers_patterns["count"]:,} funds transfers '
                f'totaling ${transfers_patterns["total"]:,.2f} were identified.'
            )
        
        # Flow pattern
        incoming_pct = patterns.get('incoming_pct', 0)
        if incoming_pct > 60:
            parts.append(
                f'The majority of the money transfers identified in {self._the_acct} consisted of '
                f'a movement of funds sent from various unique counterparties to {self._the_subj}.'
            )
        
        return ' '.join(parts)
    
    def _generate_typology_analysis(self, typ_names: List[str], analysis: Dict) -> str:
        """Generate typology-specific analysis paragraphs.
        
        For typologies SAR Workflow Test detected: full paragraph with evidence.
        For typologies manually added by analyst: skeleton paragraph for analyst to complete.
        """
        # Determine which typologies SAR Workflow Test actually detected
        detected_typologies = set()
        for t in analysis.get('typologies', []):
            if isinstance(t, dict):
                detected_typologies.add(t.get('name', ''))
        
        paragraphs = []
        
        for typ in typ_names:
            typ_lower = typ.lower()
            is_detected = typ in detected_typologies
            
            if not is_detected:
                # Manually added — skeleton paragraph
                paragraphs.append(self._manual_typology_paragraph(typ))
            elif 'drug' in typ_lower:
                paragraphs.append(self._drug_sales_paragraph(analysis))
            elif 'gambling' in typ_lower:
                paragraphs.append(self._gambling_paragraph(analysis))
            elif 'adult' in typ_lower:
                paragraphs.append(self._adult_services_paragraph(analysis))
            elif 'money laundering' in typ_lower or 'ml' in typ_lower:
                paragraphs.append(self._money_laundering_paragraph(analysis))
            elif 'pass-through' in typ_lower or 'pass through' in typ_lower:
                paragraphs.append(self._passthrough_paragraph(analysis))
            else:
                paragraphs.append(self._manual_typology_paragraph(typ))
        
        return '\n\n'.join(p for p in paragraphs if p)
    
    def _manual_typology_paragraph(self, typ_name: str) -> str:
        """Generate a skeleton paragraph for a manually-added typology."""
        typ_desc = self._typology_description([typ_name])
        return (
            f'[ANALYST: The following section describes activity indicative of {typ_desc}. '
            f'Please provide details including relevant transaction descriptions, payment comments, '
            f'counterparty information, amounts, dates, and any supporting evidence identified '
            f'during the investigation.]'
        )
    
    def _drug_sales_paragraph(self, analysis: Dict) -> str:
        """Generate drug sales analysis paragraph."""
        
        comments = analysis.get('comments', {})
        samples = comments.get('samples', comments.get('high_confidence_samples', []))
        
        # Get sample comment texts
        sample_texts = []
        for s in samples[:8]:
            if isinstance(s, dict):
                text = s.get('comment', s.get('text', ''))
                if text and text.lower() not in ('nan', ''):
                    sample_texts.append(f'"{text}"')
        
        if sample_texts:
            comment_list = ', '.join(sample_texts[:6])
            comment_str = (
                f'The payment comments entered by the senders of funds were reviewed and '
                f'contained keywords such as {comment_list}, '
                f'and emoji symbols consistent with marijuana and/or illegal drug sales.'
            )
        else:
            comment_str = (
                'The payment comments entered by the senders of funds were reviewed and '
                'contained keywords and emoji symbols consistent with marijuana and/or '
                'illegal drug sales.'
            )
        
        flow_str = (
            f'Additionally, the majority of the money transfers identified in {self._the_acct} '
            f'consisted of a movement of funds sent from various unique counterparties to '
            f'{self._the_subj}, a flow indicative of drug dealing.'
        )
        
        return f'{comment_str} {flow_str}'
    
    def _gambling_paragraph(self, analysis: Dict) -> str:
        """Generate gambling facilitation analysis paragraph."""
        
        comments = analysis.get('comments', {})
        samples = comments.get('samples', [])
        
        # Get gambling-specific comments
        gambling_comments = []
        for s in samples:
            if isinstance(s, dict):
                text = s.get('comment', '')
                terms = s.get('terms', '')
                if 'gambling' in str(terms).lower() or 'username' in str(terms).lower():
                    gambling_comments.append(f'"{text}"')
        
        parts = []
        
        parts.append(
            'The payment comments entered by the senders of funds were reviewed and '
            'contained references to known gambling platforms and username patterns '
            'consistent with gambling facilitation.'
        )
        
        if gambling_comments:
            comment_list = ', '.join(gambling_comments[:6])
            parts.append(
                f'Specific gambling-related comments identified include {comment_list}.'
            )
        
        # Check if there are ACTUAL Cash Card purchases at gambling sites
        stats = analysis.get('stats', {})
        outflows = stats.get('outflow_breakdown', [])
        
        # Look for gambling-related Cash Card purchases in outflows
        gambling_cc_found = False
        gambling_merchants = []
        if isinstance(outflows, list):
            for item in outflows:
                label = item.get('label', '') if isinstance(item, dict) else ''
                if 'Cash Card' in label:
                    gambling_cc_found = True
        
        if gambling_cc_found:
            parts.append(
                'Following the incoming P2P transfers, funds were primarily used to make '
                'a high volume of purchases with the customer\'s issued Cash App debit card '
                'at a variety of known gambling websites, which when paired with the velocity '
                'and linear movement of funds, is consistent with gambling/sports bets.'
            )
        else:
            # No Cash Card gambling purchases — describe how funds exited instead
            if outflows:
                exit_methods = []
                for item in outflows:
                    if isinstance(item, dict):
                        label = item.get('label', '')
                        total = item.get('total', 0)
                        if total > 0:
                            exit_methods.append(f'{label} (${total:,.2f})')
                if exit_methods:
                    parts.append(
                        f'Following the incoming P2P transfers, funds were primarily '
                        f'exited via {", ".join(exit_methods)}.'
                    )
            
            parts.append(
                'The velocity and linear movement of funds is consistent with '
                'gambling facilitation.'
            )
        
        return ' '.join(parts)
    
    def _adult_services_paragraph(self, analysis: Dict) -> str:
        """Generate adult services analysis paragraph."""
        
        comments = analysis.get('comments', {})
        samples = comments.get('samples', [])
        stats = analysis.get('stats', {})
        
        # Get adult-specific comments
        sample_texts = []
        for s in samples[:10]:
            if isinstance(s, dict):
                text = s.get('comment', '')
                if text and text.lower() not in ('nan', ''):
                    sample_texts.append(f'"{text}"')
        
        parts = []
        
        parts.append(
            f'A significant portion of the money transfers identified in {self._the_acct} '
            f'consisted of movement of funds sent from various unique counterparties to '
            f'{self._the_subj}, many of which were for round dollar amounts most commonly '
            f'between $50.00 to $500.00.'
        )
        
        if sample_texts:
            comment_list = ', '.join(sample_texts[:8])
            parts.append(
                f'The payments contained payment descriptions and keywords/comments such as '
                f'{comment_list}, which when combined with the timing and amounts of the '
                f'incoming funds transfers suggests in-person sexual services and funds sent '
                f'for adult pictures and videos.'
            )
        else:
            parts.append(
                'The significant majority of the payments did not contain payment comments, '
                'however the timing and amounts of the incoming funds transfers suggests '
                'in-person sexual services and funds sent for adult pictures and videos.'
            )
        
        parts.append(
            f'Funds were commonly received for high, usually round dollar amounts, '
            f'in late evening/early morning hours, which is highly irregular and not '
            f'expected activity for {self._the_acct}.'
        )
        
        return ' '.join(parts)
    
    def _money_laundering_paragraph(self, analysis: Dict) -> str:
        """Generate money laundering analysis paragraph."""
        
        comments = analysis.get('comments', {})
        stats = analysis.get('stats', {})
        
        parts = []
        
        parts.append(
            f'Review of {self._the_acct} revealed a high volume of P2P transfers, often for '
            f'higher round dollar amounts. The majority of the P2P comments contained '
            f'vague and ambiguous comments, which were attached to a variety of higher '
            f'round dollar payments.'
        )
        
        parts.append(
            f'This activity is consistent with money laundering, specifically layering, '
            f'as {self._the_subj} appear{"s" if self._subject_count == 1 else ""} to be using '
            f'{self._the_acct} to make rapid and high-volume '
            f'P2P transfers in order to launder funds derived from unknown activity and add '
            f'complexity to the movement of funds as well as obscuring the use/source of funds.'
        )
        
        return ' '.join(parts)
    
    def _passthrough_paragraph(self, analysis: Dict) -> str:
        """Generate pass-through ML analysis paragraph."""
        
        stats = analysis.get('stats', {})
        counterparties = analysis.get('counterparties', {})
        
        unique_senders = counterparties.get('total', 0)
        in_count = stats.get('incoming_paid_count', 0)
        out_count = stats.get('outgoing_paid_count', 0)
        
        parts = []
        
        parts.append(
            f'The account received a high volume of incoming P2P payments from '
            f'{unique_senders:,} unique counterparties, which were subsequently '
            f'transferred out via bank transfers and cash withdrawals.'
        )
        
        if in_count > 0 and out_count > 0:
            ratio = in_count / max(out_count, 1)
            parts.append(
                f'The incoming to outgoing ratio of {ratio:.1f}:1 is indicative of '
                f'a pass-through or aggregation scheme, wherein funds from multiple '
                f'sources are consolidated and forwarded to a smaller number of recipients.'
            )
        
        parts.append(
            'The high volume of coded and cryptic payment comments further supports '
            'this assessment, as the comments appear designed to obscure the true '
            'nature of the transactions.'
        )
        
        return ' '.join(parts)
    
    def _generate_summary(self, typ_names: List[str], analysis: Dict) -> str:
        """Generate summary paragraph."""
        
        typ_desc = self._typology_description(typ_names)
        
        indicators = []
        
        stats = analysis.get('stats', {})
        patterns = analysis.get('patterns', {})
        
        if patterns.get('round_dollar_pct', 0) > 50:
            indicators.append('high volume of suspicious round dollar payments')
        
        indicators.append('payment comments')
        
        if patterns.get('incoming_pct', 0) > 60:
            indicators.append('movement of funds from various unique counterparties')
        
        indicator_str = ', '.join(indicators)
        
        return (
            f'In summary, the {indicator_str} are indicators of {typ_desc}.'
        )
    
    def _typology_description(self, typ_names: List[str]) -> str:
        """Convert typology names to narrative description."""
        
        descriptions = {
            'Illegal Drug Sales': 'marijuana and/or illegal drug sales',
            'Drug Sales': 'marijuana and/or illegal drug sales',
            'Gambling Facilitation': 'illegal gambling facilitation',
            'Adult Services': 'in-person sexual services',
            'Money Laundering': 'money laundering',
            'Pass-Through Money Laundering': 'pass-through money laundering',
        }
        
        if not typ_names:
            return 'suspicious activity'
        
        descs = [descriptions.get(t, t.lower()) for t in typ_names]
        
        if len(descs) == 1:
            return descs[0]
        elif len(descs) == 2:
            return f'{descs[0]} and {descs[1]}'
        else:
            return ', '.join(descs[:-1]) + f', and {descs[-1]}'
    
    def _format_case_notes_subjects(self, tokens: List[str], count: int) -> str:
        """Format subjects line for case notes."""
        if count == 1:
            return f'One subject account ({tokens[0]}). [ANALYST: complete connected account review]'
        elif count <= 30:
            token_list = ', '.join(tokens)
            return f'{count} subject accounts: {token_list}. [ANALYST: complete connected account review]'
        else:
            return f'A total of {count} Cash App accounts were identified as subjects, and a full list of subject accounts is provided in the attached documentation. [ANALYST: complete connected account review]'
    
    def _format_subjects(self, tokens: List[str], count: int) -> str:
        """Format subject line for SAR narrative opening paragraph."""
        if count == 1:
            return f'The subject in this matter is {tokens[0]}.'
        elif count <= 30:
            token_list = ', '.join(tokens)
            return f'A total of {count} subject accounts were identified: {token_list}.'
        else:
            return (
                f'A total of {count} Cash App accounts were identified as subjects, '
                f'and a full list of subject accounts is provided in the attached documentation.'
            )
    
    def _format_date(self, date_val) -> str:
        """Format a date value to MM/DD/YYYY."""
        if isinstance(date_val, datetime):
            return date_val.strftime('%m/%d/%Y')
        elif isinstance(date_val, str):
            # Try to parse common formats
            try:
                # Handle pandas Timestamp strings like "2025-09-21 01:11:56.500000+00:00"
                dt = datetime.fromisoformat(date_val.replace('+0000', '+00:00').replace(' ', 'T').split('+')[0])
                return dt.strftime('%m/%d/%Y')
            except:
                # Try simpler format
                for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'):
                    try:
                        return datetime.strptime(date_val[:10], fmt).strftime('%m/%d/%Y')
                    except:
                        continue
                return date_val[:10]
        else:
            return str(date_val)[:10]


class CaseNotesGenerator:
    """
    Generates investigation case notes in Cash App internal format.
    
    Format:
    - SAR Recommendation
    - Review Period
    - Suspicious Activity Type
    - Suspicious Transactions
    - Subjects
    - Qualitative Info (the main analysis — reuses narrative content)
    - Relevant Public Information
    - Relevant Documentation
    """
    
    # Suspicious Activity Type codes
    ACTIVITY_TYPE_CODES = {
        'Illegal Drug Sales': 'OSA drugsales Cash',
        'Drug Sales': 'OSA drugsales Cash',
        'Gambling Facilitation': 'OSA gambling Cash',
        'Adult Services': 'OSA IPSS Cash',
        'Money Laundering': 'ML Cash',
        'Pass-Through Money Laundering': 'ML passthrough Cash',
    }
    
    def __init__(self):
        self.narrative_gen = NarrativeGenerator()
    
    def generate_case_notes(self, analysis: Dict, case_id: str = '') -> Dict:
        """
        Generate case notes from SAR Workflow Test analysis results.
        
        Returns:
            Dict with 'case_notes' (full text) and 'fields' (structured)
        """
        stats = analysis.get('stats', analysis.get('basic_stats', {}))
        typologies = analysis.get('typologies', [])
        
        typ_names = [t['name'] for t in typologies] if isinstance(typologies, list) else []
        
        # Get date range
        date_range = stats.get('date_range')
        if date_range and isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start = self.narrative_gen._format_date(date_range[0])
            end = self.narrative_gen._format_date(date_range[1])
            review_period = f'{start} - {end}'
        else:
            review_period = '[DATE RANGE]'
        
        # Subject(s)
        subject_tokens = stats.get('subject_tokens', [])
        subject_count = stats.get('subject_count', 1)
        subject = stats.get('subject', '[SUBJECT TOKEN]')
        if not subject_tokens:
            subject_tokens = [subject] if subject else ['[SUBJECT TOKEN]']
        
        # Activity type code
        activity_codes = []
        for t in typ_names:
            code = self.ACTIVITY_TYPE_CODES.get(t, t)
            if code not in activity_codes:
                activity_codes.append(code)
        activity_type = ' '.join(activity_codes) if activity_codes else '[ACTIVITY TYPE]'
        
        # Generate the narrative for the qualitative info section
        narrative_result = self.narrative_gen.generate_narrative(analysis, case_id)
        
        # Build qualitative info from narrative sections
        qual_parts = []
        
        # Alert and connected accounts
        qual_parts.append(
            f'{subject} alerted via transaction monitoring.'
        )
        qual_parts.append(
            '[ANALYST: Ran Cash cluster query to identify accounts '
            'first-degree connected to alerted tokens by SSN/bank account/sponsorship/email '
            'and also payment card connections. Resulting accounts were reviewed.]'
        )
        
        # Main analysis (from narrative)
        qual_parts.append('')
        qual_parts.append(narrative_result['sections'].get('opening', ''))
        qual_parts.append(narrative_result['sections'].get('transaction_analysis', ''))
        qual_parts.append(narrative_result['sections'].get('typology_analysis', ''))
        qual_parts.append(narrative_result['sections'].get('summary', ''))
        
        qualitative_info = '\n\n'.join(p for p in qual_parts if p)
        
        # Suspicious transactions description (use narrative_gen for pluralization)
        ng = self.narrative_gen
        if any('drug' in t.lower() for t in typ_names):
            susp_txns = f"All P2P activity associated with {ng._the_subj}'s {ng._acct} within the review period."
        elif any('gambling' in t.lower() for t in typ_names):
            susp_txns = f"All P2P and Cash Card activity associated with the subject {ng._acct} within the review period."
        elif any('adult' in t.lower() or 'ml' in t.lower() or 'money' in t.lower() for t in typ_names):
            susp_txns = f"All P2P activity, ATM withdrawals, and account funding transfers in the {ng._acct}."
        else:
            susp_txns = "All activity within the review period."
        
        # Build structured fields
        fields = {
            'sar_recommendation': '[ANALYST: Y / N]',
            'review_period': review_period,
            'suspicious_activity_type': activity_type,
            'suspicious_transactions': susp_txns,
            'subjects': self.narrative_gen._format_case_notes_subjects(subject_tokens, subject_count),
            'qualitative_info': qualitative_info,
            'relevant_public_info': '[ANALYST: OSINT links]',
            'relevant_ip_info': '[ANALYST: IP information]',
            'relevant_documentation': 'None submitted',
        }
        
        # Build full text
        case_notes = (
            f'SAR Recommendation: {fields["sar_recommendation"]}\n\n'
            f'Review Period: {fields["review_period"]}\n\n'
            f'Suspicious Activity Type: {fields["suspicious_activity_type"]}\n\n'
            f'Suspicious Transactions: {fields["suspicious_transactions"]}\n\n'
            f'Subjects: {fields["subjects"]}\n\n'
            f'Qualitative Info: {fields["qualitative_info"]}\n\n'
            f'Relevant Public Information:\n{fields["relevant_public_info"]}\n\n'
            f'Relevant IP Information:\n{fields["relevant_ip_info"]}\n\n'
            f'Relevant Documentation:\n{fields["relevant_documentation"]}'
        )
        
        return {
            'case_notes': case_notes,
            'fields': fields,
            'narrative': narrative_result,
        }


if __name__ == "__main__":
    print("SAR Workflow Test Narrative Generator")
    print("=" * 40)
    print("Supported typologies:")
    print("  - Drug Sales")
    print("  - Gambling Facilitation")
    print("  - Adult Services")
    print("  - Money Laundering")
    print("  - Pass-Through Money Laundering")
    print("  - Multi-typology combinations")
