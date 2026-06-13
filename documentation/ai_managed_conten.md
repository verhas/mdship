<!--AI
prompt: |
  Write an article about mdship handling LLM managed content.
  The intended audience is technical writers.
  The article will be published on DZONE and on LinkedIn.
  Use the following topics/sections:

  - What is mdship?
    It is a command line and mcp server tool to edit markdown files.
    Briefly compare source -> processing -> output like the project pet or Jama, or other preprocessors and
                    source -> processing -> modified source, like every editor does.
    mdship is a special editor that can perform special operations
  - What are the advantages and the disadvantages of the two solutions
    - In-place editing: you have only one file, markdown specific, you see the managed content, like included snippest while editing, but the same time you may also accidentally edit it
    - Preprocessor: cleaner, more pragmatic way
  - How mdship implements content integrity. Do not go into the details, like what happens if the included content contains a closing tag. That is too detailed for an article. Also there is no need to mention the handling of the length. _content_generated_ is a "checksum".
  - How mdship supports LLM content generation using the AI placeholder. Workflow: check for manual change, update, seal with the new checksum. If check fails: LLM skill instructions: "don't edit!" Mention it is called via mcp.
  - Explain how this approach keeps the propt used to generate the sections part of the documentation, though not rendered into the output. The advantage is that the prompt can be reused. Note that the prompt may reference external files, like other documentation items. If they change, the same prompt will generate new content.
  - Conclusion
-->

<!--/AI-->