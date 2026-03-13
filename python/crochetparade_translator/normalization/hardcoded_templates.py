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

from .grammar import TEMPLATE_REWRITE_RULES
from .grammar import RegexRewrite
from .grammar import apply_rewrite_rules


TemplateRewrite = RegexRewrite
TEMPLATES: list[TemplateRewrite] = list(TEMPLATE_REWRITE_RULES)


def apply_templates(line: str) -> tuple[str, list[str]]:
    return apply_rewrite_rules(line, TEMPLATES)
