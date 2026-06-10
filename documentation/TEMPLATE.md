3# TEMPLATE Placeholder

<!--AI
name: "template"
prompt: |
    Write documentation for the TEMPLATE placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.7 (Template Placeholders)
    for the reference material. Also read the implementation in
    /Users/verhasp/github/mdship/mdship/markdown.py, function process_template
    (around line 1469), to understand the exact behaviour.

    Cover:
    - What TEMPLATE does: takes a content block written inline in the placeholder,
      substitutes $variable references in it, and replaces the region between
      <!--TEMPLATE --​> and <!--/TEMPLATE--​> with the substituted result
    - Why it exists: normal $var substitution is intentionally skipped inside fenced
      code blocks (``` ... ```); TEMPLATE is the way to embed variable values inside
      code blocks or any content where the substitution must be explicit and contained
    - Syntax: <!--TEMPLATE --​> with a required 'content' YAML field (multiline block),
      followed by the current output and a closing <!--/TEMPLATE--​>
    - The content field: the template string with $var or ${var} references
    - Variable support: same dot-notation and array indexing as other placeholders
    - The closing <!--/TEMPLATE--​> is required; the region between markers is fully
      replaced on each run
    - _terminate_: custom closing marker name follows the same convention as other
      mdship placeholders
    - A practical example: showing a fenced code block with variable values rendered in

    At the end, add a "See Also" section that explains how TEMPLATE differs from
    all other placeholders: it is neither a variable source nor a content importer —
    it is a variable consumer that renders an inline template. Contrast with:
    - Variable sources (SET, IMPORT, SLURP, SIP, SUP): they define variables;
      TEMPLATE uses them
    - INCLUDE: embeds an external file; TEMPLATE embeds an inline template string
    - MERMAID: also substitutes variables, but for diagram rendering specifically
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md),
    [SUP](SUP.md), [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
-->

<!--/AI-->
