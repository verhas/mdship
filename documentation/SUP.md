# SUP Placeholder

<!--AI
name: "sup"
prompt: |
    Write documentation for the SUP placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.6 (Variables) for the
    reference material. Focus on SUP specifically.

    Cover:
    - What SUP does: extracts a single value from the very next line in the document
      using a regex pattern with 1 capturing group
    - Why it is useful: allows capturing values that are already present as document
      content (e.g. the text of the next heading) without duplicating them in a SET
    - Syntax: <!--SUP ... --​> with YAML body (name, pattern fields), followed immediately
      by the line to extract from
    - The name field: the variable name to assign the captured value to
    - The pattern field: regex with exactly 1 capturing group
    - A practical example showing how to capture a heading title as a variable

    At the end, add a "See Also" section that compares SUP to the other variable
    source placeholders (SET, IMPORT, SLURP, SIP) and to INCLUDE, TOC, MERMAID.
    Explain when to choose SUP (value already exists in the document, no external file needed)
    vs. the others.
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md),
    [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
-->

<!--/AI-->
