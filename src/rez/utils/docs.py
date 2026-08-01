# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DocumentedSetting:
    name: str
    lineno: int
    value_lines: List[str]
    comment_lines: List[str]
    section: Optional[str]
    section_description: str


def parse_documented_settings(source: str) -> List[DocumentedSetting]:
    """Parse documented top-level settings from a rezconfig source file."""
    lines = source.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if "__DOC_START__" in line),
        None,
    )
    end = next(
        (i for i, line in enumerate(lines) if "__DOC_END__" in line),
        None,
    )
    if start is None or end is None or start >= end:
        raise ValueError("rezconfig documentation sentinels were not found")

    assignments = {}
    for node in ast.parse(source).body:
        line_index = node.lineno - 1
        if not start < line_index < end:
            continue
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue

        names = [target.id for target in targets if isinstance(target, ast.Name)]
        if names:
            assignments[line_index] = (names, node.end_lineno or node.lineno)

    settings = []
    section = None
    section_description = ""
    section_header = None
    i = start + 1
    while i < end:
        line = lines[i]
        if line.startswith("##########") and i != section_header:
            if i + 1 >= end:
                raise ValueError("rezconfig documentation section has no title")
            section = lines[i + 1].split("#", 1)[-1].strip()
            description_lines = []
            description_line = i + 2
            while (
                description_line < end
                and not lines[description_line].startswith("##########")
            ):
                description_lines.append(
                    lines[description_line].split("#", 1)[-1].strip()
                )
                description_line += 1
            section_description = "\n".join(description_lines)
            section_header = description_line

        assignment = assignments.get(i)
        if assignment:
            names, end_lineno = assignment
            value_lines = lines[i:end_lineno]
            value_lines[0] = value_lines[0].split("=")[-1].strip()

            comment_start = i
            while comment_start > start + 1 and lines[comment_start - 1].startswith("#"):
                comment_start -= 1
            comment_lines = [
                comment[2:] if comment.startswith("# ") else comment[1:]
                for comment in lines[comment_start:i]
            ]

            for name in names:
                settings.append(DocumentedSetting(
                    name=name,
                    lineno=i + 1,
                    value_lines=value_lines,
                    comment_lines=comment_lines,
                    section=section,
                    section_description=section_description,
                ))
        i += 1

    return settings
