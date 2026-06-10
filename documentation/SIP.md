# SIP Placeholder

<!--AI
name: "sip"
prompt: |
    Write documentation for the SIP placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.6 (Variables) for the
    reference material. Focus on SIP specifically.

    Cover:
    - What SIP does: extracts predefined variables from a file using named regex patterns
      with 1 capturing group each — each pattern captures the value for a known variable name
    - How SIP differs from SLURP: SLURP discovers variable names from the file;
      SIP has fixed variable names defined in the placeholder, patterns extract values
    - Syntax: <!--SIP ... --​> with YAML body (name, from, vars fields)
    - The name field: namespace prefix for the extracted variables
    - The from field: path to the source file
    - The vars field: map of variable names to regex patterns (each with 1 capturing group)
    - A practical example showing source file and resulting variables

    At the end, add a "See Also" section that compares SIP to the other variable
    source placeholders (SET, IMPORT, SLURP, SUP) and to INCLUDE, TOC, MERMAID.
    Explain when to choose SIP (you know the variable names, just need to extract values)
    vs. SLURP (variable names are discovered from the file).
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SUP](SUP.md),
    [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
-->

<!--/AI-->
