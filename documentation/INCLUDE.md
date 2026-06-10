# INCLUDE Placeholder

<!--AI
name: "include"
prompt: |
    Write documentation for the INCLUDE placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.10 (Including Files) for
    the reference material.

    Cover:
    - What INCLUDE does: embeds content from an external file between the opening
      <!--INCLUDE ... --​> and closing <!--/INCLUDE--​> markers
    - Syntax and all supported fields:
        - from: path to the file to include (required)
        - prefix/postfix: text inserted before/after the included content (e.g. fenced code block markers)
        - range: line range to include (e.g. "10..20")
        - _terminate_: custom closing marker name
    - How variable references in included content are also substituted
    - The closing <!--/INCLUDE--​> (or custom terminator) is required to delimit the region
    - Practical examples: including a plain file, including a code snippet with prefix/postfix,
      including a line range

    At the end, add a "See Also" section that compares INCLUDE to the variable source
    placeholders (SET, IMPORT, SLURP, SIP, SUP) and to TOC, MERMAID.
    Explain when to choose INCLUDE (embed entire file content) vs. IMPORT (load data as variables).
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md),
    [SUP](SUP.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
-->

<!--/AI-->
