# SLURP Placeholder

<!--AI
name: "slurp"
prompt: |
    Write documentation for the SLURP placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.6 (Variables) for the
    reference material. Focus on SLURP specifically.

    Cover:
    - What SLURP does: scans a file line by line using regex patterns with 2 capturing
      groups — the first group becomes the variable name, the second becomes the value
    - Syntax: <!--SLURP ... --​> with YAML body (name, from, strategy, rules fields)
    - The name field: namespace prefix under which extracted variables are stored
    - The from field: path to the source file
    - The strategy field: "first" (keep first match per key) or "last" (keep last)
    - The rules field: list of regex patterns, each with exactly 2 capturing groups
    - How extracted variables are accessed
    - A practical example showing source file content and resulting variables

    At the end, add a "See Also" section that compares SLURP to the other variable
    source placeholders (SET, IMPORT, SIP, SUP) and to INCLUDE, TOC, MERMAID.
    Explain when to choose SLURP (variable names come from the file itself, not known upfront)
    vs. SIP (variable names are known, only values are extracted).
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SIP](SIP.md), [SUP](SUP.md),
    [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
-->

<!--/AI-->
