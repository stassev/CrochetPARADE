#Copyright (C) Svetlin Tassev

# This file is part of CrochetPARADE.

# CrochetPARADE is free software: you can redistribute it and/or modify it under 
# the terms of the GNU General Public License as published by the Free Software 
# Foundation, either version 3 of the License, or (at your option) any later version.

# CrochetPARADE is distributed in the hope that it will be useful, but WITHOUT 
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along 
# with CrochetPARADE. If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rewrite:
    rule: str
    before: str
    after: str


_RE_PAREN_TIMES = re.compile(r"^\((?P<body>.+)\)\s*(?P<n>\d+)\s+times\.?$", re.IGNORECASE)


def rewrite_repeats(line: str) -> tuple[str, list[Rewrite]]:
    rewrites: list[Rewrite] = []
    m = _RE_PAREN_TIMES.match(line.strip())
    if m:
        before = line
        body = m.group("body").strip()
        n = int(m.group("n"))
        after = f"REPEAT {n} TIMES: {body}"
        rewrites.append(Rewrite(rule="paren_times", before=before, after=after))
        return after, rewrites
    return line, rewrites

