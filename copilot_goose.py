"""
SAR Workflow Test Copilot — Goose Backend

Routes copilot chat through Goose instead of OpenAI,
giving the copilot full Goose capabilities:
- Run Python code
- Read files and CSVs
- Execute shell commands
- Analyze data on the fly

RESTRICTION: Copilot cannot edit SAR Workflow Test source code files.
Only the administrator (via direct Goose session) can modify SAR Workflow Test.
"""

import subprocess
import json
import os
import tempfile


GOOSE_SYSTEM_PROMPT = """You are SAR Workflow Test copilot. You are an expert BSA/AML investigator embedded in the SAR Workflow Test platform at Block/Cash App.

HOW YOU COMMUNICATE:
- Lead with the answer in plain English, then provide supporting detail.
- Use exact numbers but write them naturally: "$172,644 across 394 transactions" not "total_amount 172644.0 txn_count 394".
- NEVER include raw code output, pandas DataFrames, dtype info, or technical formatting in your response. Translate everything into plain language.
- Give enough context to be useful — explain why a finding matters or what it could indicate.
- When you spot something interesting, flag it and connect the dots.
- Think like a senior investigator briefing their team — clear, precise, informative.
- Never explain your process. Never say "Let me analyze" or "Loading the data."
- No filler phrases like "I'd be happy to help" or "Great question."

WHAT YOU DO:
- Analyze transaction CSVs using Python — just run the code, never ask permission.
- Identify patterns: flow direction, amount clustering, comment analysis, timing, counterparty networks.
- Provide investigative context: what a pattern means, why it matters, what to look for next.
- Help draft narratives and case notes in Block's SAR writing style.
- Answer any question about the current case data with real computed answers.

CRITICAL RULE — NEVER GUESS DATA:
- When asked about specific numbers, counterparties, amounts, or counts — you MUST run Python code against the CSV to get the real answer.
- NEVER make up counterparty IDs, amounts, or counts from memory or context summaries.
- If you cannot run code for some reason, say "I need to analyze the CSV to answer that accurately" — do NOT guess.
- The CSV file path is provided in your context.
- ALWAYS start your Python code with: from copilot_csv_helper import load_case; data = load_case('CSV_PATH_HERE')
- This gives you clean pre-parsed data with: data['incoming_p2p'], data['top_senders'], data['multi_subject_cps'], data['subjects'], etc.
- The helper handles amount cleaning ($, commas), system token filtering, and format detection automatically.
- Run your code from the ~/Desktop/sar-workflow-test/ directory.

CRITICAL RULE — RESPONSE FORMAT:
- After running code, write ONLY your plain English answer. Do NOT repeat the code, do NOT show the raw output.
- Write your final answer to /tmp/sar_workflow_test_answer.txt using: open('/tmp/sar_workflow_test_answer.txt','w').write('your answer here')
- Your answer should read like a senior investigator speaking — natural, specific, no technical artifacts.

RULES:
- NEVER edit files in ~/Desktop/sar-workflow-test/ — those are SAR Workflow Test source code.
- NEVER recommend whether to file a SAR — that's the analyst's decision.
- Use "Potential" not "Suspicious" when describing detected activity.
- Include ALL attempted transactions in SAR totals (not just successful).
- When presenting data, use clean formatted output — no raw CSV dumps."""


def run_goose_query(message: str, case_context: str = '', csv_path: str = '') -> str:
    """
    Send a query to Goose and return the response.
    
    Args:
        message: The analyst's question
        case_context: Summary of current case data
        csv_path: Path to the current CSV file (if available)
    """
    
    # Build system context with everything SAR Workflow Test knows
    system_parts = [GOOSE_SYSTEM_PROMPT]
    
    if case_context:
        system_parts.append(f"\nSAR WORKFLOW TEST ANALYSIS RESULTS:\n{case_context}")
    
    # CSV path goes in the system prompt
    if csv_path and os.path.exists(csv_path):
        system_parts.append(f"\nCSV FILE: {csv_path}")
        system_parts.append("Run Python to analyze this file for any question about the raw data.")
    
    # Keep system prompt concise — long prompts confuse Goose
    system_text = '\n'.join(system_parts)
    if len(system_text) > 3000:
        system_text = system_parts[0] + '\n' + system_parts[-1] if len(system_parts) > 1 else system_parts[0]
    
    try:
        prompt_file = None
        
        # Clean up any stale answer file
        answer_file = '/tmp/sar_workflow_test_answer.txt'
        if os.path.exists(answer_file):
            os.unlink(answer_file)
        
        # Call goose run with system prompt + user text
        result = subprocess.run(
            [
                'goose', 'run',
                '--system', system_text,
                '--text', message,
                '--no-session',
                '--max-turns', '10',
                '--with-builtin', 'developer',
                '--no-profile',
                '--provider', 'openai',
                '--model', 'gpt-4o',
                '-q',
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        # Clean up temp file if not already cleaned
        if prompt_file and os.path.exists(prompt_file):
            os.unlink(prompt_file)
        
        # Check if Goose wrote a clean answer to the file
        answer_file = '/tmp/sar_workflow_test_answer.txt'
        if os.path.exists(answer_file):
            try:
                with open(answer_file, 'r') as f:
                    file_answer = f.read().strip()
                os.unlink(answer_file)
                if file_answer and len(file_answer) > 10:
                    return file_answer
            except:
                pass
        
        response = result.stdout.strip()
        
        if not response and result.stderr:
            return f"Error: {result.stderr[:500]}"
        
        if not response:
            return "I wasn't able to generate a response. Please try rephrasing your question."
        
        # Clean up Goose output — remove tool calls, code blocks, and raw data
        cleaned = clean_goose_response(response)
        
        return cleaned
        
    except subprocess.TimeoutExpired:
        return "The analysis took too long (>2 minutes). Try a more specific question."
    except FileNotFoundError:
        return "Goose CLI not found. Make sure goose is installed and in your PATH."
    except Exception as e:
        return f"Error running goose: {str(e)}"


def clean_goose_response(response: str) -> str:
    """
    Clean Goose output to remove tool calls, code, raw data.
    Only keep the final human-readable response.
    """
    import re
    
    # Strategy: split on tool call markers, take the last prose section
    # Goose output pattern: [tool calls + output] ... [final prose answer]
    
    # First, try to find the final answer after all tool blocks
    sections = response.split('▸ ')
    
    if len(sections) > 1:
        # Take the last section — this is usually the final answer
        last_section = sections[-1]
        lines = last_section.split('\n')
        
        # Find where the prose starts (skip tool name, command, output)
        prose_lines = []
        found_prose = False
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines before prose starts
            if not found_prose and not stripped:
                continue
            
            # Skip tool-related lines
            if not found_prose and (
                stripped.startswith('command:') or
                stripped.startswith('path:') or
                stripped.startswith('content:') or
                stripped.startswith('shell') or
                stripped.startswith('read') or
                stripped.startswith('write') or
                stripped.startswith('>>>') or
                stripped.startswith('import ') or
                stripped.startswith('df') or
                stripped.startswith('print(') or
                'COUNTERPARTY' in stripped or
                'USER_TOKEN' in stripped or
                'TARGET' in stripped
            ):
                continue
            
            # Skip raw data lines (C_ tokens in columns, CSV-like data)
            if not found_prose and stripped.startswith('C_') and '  ' in stripped:
                continue
            
            # Skip lines that look like code output
            if not found_prose and (stripped.startswith('(') and stripped.endswith(')')) :
                continue
            
            # This looks like prose
            if stripped and (stripped[0].isalpha() or stripped[0] in ('-', '•', '*', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
                found_prose = True
            
            if found_prose:
                prose_lines.append(line)
        
        result = '\n'.join(prose_lines).strip()
        if result and len(result) > 20:
            return result
    
    # Fallback: try to strip obvious non-prose from the full response
    lines = response.split('\n')
    clean = []
    for line in lines:
        stripped = line.strip()
        # Skip tool markers
        if stripped.startswith('▸ '):
            continue
        # Skip command lines
        if stripped.startswith('command:') or stripped.startswith('path:'):
            continue
        # Skip CSV headers and data
        if stripped.startswith('Date,') or stripped.startswith('﻿Date,') or stripped.startswith('FILING_'):
            continue
        if ',USD,' in line or ',COMPLETED,' in line or ',PAID_OUT,' in line:
            continue
        if stripped.startswith('C_') and '  ' in stripped and stripped.count('C_') >= 2:
            continue
        # Skip code
        if stripped.startswith('import ') or stripped.startswith('df =') or stripped.startswith('print(') or stripped.startswith('data =') or stripped.startswith('from copilot'):
            continue
        # Handle pandas output (dtype, Name:, DataFrame headers)
        if 'dtype:' in stripped:
            # Extract any prose stuck after "dtype: object" (often no space between)
            match = re.search(r'dtype:\s*(?:object|float64|int64|bool|str)', stripped)
            if match:
                after = stripped[match.end():].strip()
                if after and len(after) > 10:
                    clean.append(after)
            continue
            continue
        if stripped.startswith('Name:') or 'DataFrame' in stripped:
            continue
        # Skip raw pandas rows (column_name  value format)
        pandas_fields = ['total_amount', 'txn_count', 'subjects', 'subject_list', 'comments', 'amount', 'count', 'counterparty']
        if any(stripped.startswith(f) for f in pandas_fields) and any(c.isdigit() or c == '[' for c in stripped):
            continue
        # Skip lines that look like raw data: token + number (e.g., "C_5q28x8m3s 172644.0")
        if re.match(r'^C_\S+\s+[\d.]+$', stripped):
            continue
        # Skip any line that's just a number or token + number
        if re.match(r'^[\d.$,]+$', stripped):
            continue
        if re.match(r'^\S+\s+[\d.]+$', stripped) and not any(c.isalpha() and c not in 'CcBbMm_' for c in stripped.split()[0]):
            continue
        # Skip "Let me" / "Let's" process descriptions
        if stripped.startswith("Let me ") or stripped.startswith("Let's ") or stripped.startswith("Analyzing ") or stripped.startswith("Loading "):
            continue
        clean.append(line)
    
    result = '\n'.join(clean).strip()
    
    # Inline cleaning — remove raw data fragments stuck to prose
    # Remove patterns like "C_token 12345.0" at start of text
    result = re.sub(r'^[A-Z]_\S+\s+[\d.]+', '', result).strip()
    # Remove pandas-style output fragments
    result = re.sub(r'\b\w+\s+[\d.]+\nName:.*?dtype:.*?\n?', '', result).strip()
    # Remove standalone numbers/tokens at the start
    result = re.sub(r'^[\d.$,]+\s*', '', result).strip()
    # Remove "Name: X, dtype: object" anywhere (including stuck to next word)
    result = re.sub(r'Name:\s*\S+,?\s*dtype:\s*\w+', '', result).strip()
    # Remove "dtype: object" stuck to text
    result = re.sub(r'dtype:\s*\w+', '', result).strip()
    
    return result if result else response


if __name__ == "__main__":
    # Test
    response = run_goose_query("What is 2+2?")
    print(f"Response: {response}")
