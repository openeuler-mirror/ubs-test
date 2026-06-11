"""Table parser for CLI command output.

Migrated from: legency/testcase/ubse/lib/Common/RackControl/Foundational_Software_Framework/Cli_Module/AweTableParser.py
Provides fixed-width table text parsing for CLI command results.

Usage:
    from libs.utils.table_parser import AweTableParser
    
    result = node.run({"command": ["ubsectl display memory -t borrow_detail"]})
    stdout = result.get("stdout")
    parser = AweTableParser(stdout)
    records = parser.parse_text()
"""

import re
from typing import Dict, List, Optional


class AweTableParser:
    """Parser for fixed-width format table text.
    
    Parses CLI command output formatted as fixed-width tables:
        Name         Size(MB)  Status
        -----------  --------  -------
        test_mem     128       done
        other_mem    256       fault
    """

    def __init__(self, text: Optional[str] = None):
        """Initialize parser.
        
        Args:
            text: Table text to parse
        """
        self.text = text

    @staticmethod
    def _is_separator(line: str) -> bool:
        """Check if line is separator (continuous dashes)."""
        s = line.strip()
        return s and all(c == '-' for c in s)

    @staticmethod
    def _is_header_candidate(line: str) -> bool:
        """Check if line could be header."""
        fields = re.findall(r'\S+', line)
        if len(fields) < 2:
            return False
        return all(len(f) <= 20 for f in fields)

    @staticmethod
    def _parse_columns_from_header(header_line: str) -> Dict[str, tuple]:
        """Parse column positions from header line.
        
        Returns:
            Dict mapping column name to (start, end) position tuple
        """
        matches = list(re.finditer(r'\S+', header_line))
        columns = {}

        for i, m in enumerate(matches):
            name = m.group()
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else None
            columns[name] = (start, end)

        return columns

    def parse_text(self) -> List[Dict[str, str]]:
        """Parse table text into records.
        
        Returns:
            List of dicts, each dict represents one row
        """
        if not self.text:
            return []

        return self._parse_table_auto(self.text.splitlines(keepends=True))

    def _parse_table_auto(self, lines: List[str]) -> List[Dict[str, str]]:
        """Auto-parse table from lines."""
        header_index = self._find_header_index(lines)
        header_line = lines[header_index]
        cols = self._parse_columns_from_header(header_line)

        records = []
        current = None

        for line in lines[header_index + 1:]:
            if self._is_separator(line):
                continue

            if not line.strip():
                if current:
                    records.append(current)
                    current = None
                continue

            if current is None:
                current = {k: "" for k in cols}

            for k, (s, e) in cols.items():
                part = line[s:e].rstrip() if e else line[s:].rstrip()
                if part.strip():
                    current[k] += part.strip()

        if current:
            records.append(current)

        return records

    def _find_header_index(self, lines: List[str]) -> int:
        """Find header line index."""
        for i, line in enumerate(lines):
            if self._is_separator(line):
                continue
            if not self._is_header_candidate(line):
                continue
            return i

        raise ValueError("Cannot identify header line")