from pydantic import BaseModel

from contree_mcp.resources.guide import SECTIONS


class GetGuideOutput(BaseModel):
    section: str
    content: str
    available_sections: list[str]


async def get_guide(section: str) -> GetGuideOutput:
    """
    Get agent guide sections for Contree best practices. Free (no VM).

    TL;DR:
    - PURPOSE: Access documentation and best practices for using Contree
    - SECTIONS: workflow, reference, quickstart, state, async, tagging, errors
    - COST: Free (no VM)

    USAGE:
    - Get workflow patterns: get_guide(section="workflow")
    - Get tool reference: get_guide(section="reference")
    - Get quick start examples: get_guide(section="quickstart")
    - Get state management guide: get_guide(section="state")
    - Get async execution guide: get_guide(section="async")
    - Get tagging convention: get_guide(section="tagging")
    - Get error handling guide: get_guide(section="errors")

    RETURNS: section, content, available_sections

    AVAILABLE SECTIONS:
    - workflow: Complete workflow patterns with decision tree
    - reference: Tool reference with parameters and data flow
    - quickstart: Quick examples for common operations
    - state: State management and rollback patterns
    - async: Parallel execution and wait_operations
    - tagging: Tagging convention for prepared environments
    - errors: Error handling and debugging guide

    RESOURCE ALTERNATIVE:
    - contree://guide/{section} - Same content as MCP resource (if your agent supports resources)
    """

    available = sorted(SECTIONS.keys())

    if section not in SECTIONS:
        raise ValueError(f"Unknown guide section '{section}'. Available sections: {', '.join(available)}")

    return GetGuideOutput(
        section=section,
        content=SECTIONS[section],
        available_sections=available,
    )
