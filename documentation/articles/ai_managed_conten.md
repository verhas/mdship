<!--AI
prompt: |
  Write an article about mdship handling LLM managed content.
  Intended audience: technical writers who are familiar with markdown and may have used
  preprocessor-style documentation tools (like PET, Jamal, or similar). They are
  evaluating or starting to use AI-assisted documentation workflows.
  The article will be published on DZONE and on LinkedIn. Use an informative but
  conversational tone — not academic, not marketing copy.

  Structure the article with the following sections, in this order:

  - What is mdship?
    Introduce it as a CLI and MCP server tool for editing markdown files in place.
    Present the two models side by side: preprocessor (source → processing → separate
    output file, like PET or Jamal) vs. editor (source → processing → modified source,
    like every editor does). mdship is a special-purpose editor: it can perform
    structured operations — generate a table of contents, include external snippets,
    render diagrams — that normal editors leave to separate build steps.

  - Advantages and disadvantages of in-place editing vs. preprocessors.
    Merge this into the "What is mdship?" section or make it a direct follow-on so the
    comparison does not feel repeated. Cover:
    - In-place editing: single file, managed content is visible while editing (you see
      included snippets inline), portable, no build step — but you can accidentally edit
      managed sections.
    - Preprocessor: clean separation of concerns, harder to accidentally corrupt output,
      but requires a build step and the output is a separate file you do not edit directly.

  - How mdship protects managed content (content integrity).
    Explain that every time mdship writes to a managed section it records a checksum
    (_content_generated_) inside the opening placeholder marker. On the next run it
    verifies the checksum before overwriting. If the checksum does not match, mdship
    refuses to continue and reports an error — protecting any manual edits the author
    may have made. Keep this high-level: _content_generated_ is a checksum, full stop.
    No need to explain encoding details or edge cases.

  - How mdship supports LLM content generation (the AI placeholder).
    Introduce the <!--AI--​> placeholder: the author embeds a prompt inside the markdown
    document; an LLM (via the /ai-placeholder skill in Claude Code, called through MCP)
    reads the prompt and writes the content between the markers. The workflow is:
    check for manual changes (via mcp ai-check) → generate and write new content →
    seal with a new checksum (via mcp ai-fix). If the check fails, the skill instructs
    the LLM not to edit and reports the conflict to the user instead.

  - The prompt as living documentation.
    The prompt that drives content generation stays embedded in the file, in a
    non-rendered HTML comment, as part of the document itself. This means:
    - The prompt can be rerun at any time to regenerate the section.
    - The prompt can reference external files (other docs, source files, config). If
      those change, rerunning the same prompt produces updated content automatically.
    - The intent behind each section is preserved alongside the content, not in a
      separate ticket or commit message that may be hard to find later.

  - Conclusion.
    Tie together the two threads: mdship's in-place editing model and its LLM
    integration are two sides of the same design choice — keep everything in one file,
    protect it with checksums, and let the tooling (not the author) manage the
    regeneration cycle.
_content_generated_: 6766:md5:528140c74b662164ddd6feb7bada1d8b
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->

# When Your Documentation Manages Itself: mdship and AI-Assisted Markdown

If you write technical documentation in markdown, you already know the tension: some parts of your document are hand-written prose, while others — a table of contents, an included code snippet, a rendered diagram — are generated from somewhere else. How you handle that boundary says a lot about your workflow.

Most documentation toolchains resolve it the same way preprocessors like PET or Jamal do: separate the source from the output. You maintain a template file, run a build step, and get a rendered document as the result. Clean, predictable, and easy to reason about — but it adds a build step, and the output file is not the thing you actually edit or share.

mdship takes a different approach. It is a command-line tool and MCP server that edits your markdown **in place**: it reads the file, updates specific sections, and writes the result back to the same file. Everything else — your prose, your headings, your structure — is untouched. No separate output file, no build pipeline. The document you see is the document you ship.

Think of it less like a preprocessor and more like a very opinionated editor that knows how to regenerate a table of contents, pull in a code snippet from another file, or render a Mermaid diagram — all within the file you are already editing.

## One File: The Trade-off

Working in a single file has real advantages for technical writers. The managed content — included snippets, generated TOC entries — is visible inline while you are editing. You can read the full document as your readers will see it, without switching to a preview mode or running a build. There is no output file to track separately, and markdown-aware tools like GitHub or your IDE render it correctly wherever it lives.

The downside is equally real: because managed and hand-written content share the same file, it is easy to accidentally edit a section that is meant to be regenerated. You fix a typo in an included code snippet; on the next run, your fix is gone. You add a note inside a generated TOC block; mdship overwrites it without warning.

Preprocessor tools sidestep this entirely. The source is one file, the output is another, and you never edit the output directly. The separation of concerns is clean. But you pay for it: every change requires a build step, the output is not portable without that step, and contributors who are not familiar with the toolchain may not know which file to edit.

Neither model is universally better. mdship makes the pragmatic choice that for most documentation workflows, a single file with good guardrails beats a clean architecture that requires a build.

## Content Integrity: The Guardrail

The guardrail is a checksum.

Every time mdship writes content into a managed section — a TOC block, an INCLUDE block, a MERMAID block — it records a checksum of that content inside the opening placeholder marker, under a key called `_content_generated_`. On the next run, before overwriting anything, it verifies that the checksum still matches. If it does not, mdship stops and reports an error instead of silently discarding your edits.

```
ERROR: Placeholder TOC content was manually edited.
Hash mismatch detected.
Delete _content_generated_ line to override and accept data loss.
```

This turns an accidental overwrite — which would otherwise be invisible until you noticed the missing content — into an explicit decision. You can delete the `_content_generated_` line to tell mdship "I know, proceed anyway," or you can pass `--force` on the command line to skip the check for a single run. Either way, you are opting in, not being surprised.

## AI-Generated Sections: The Same Idea, Extended

The same pattern extends naturally to sections written by an LLM.

mdship supports an `<!--AI-->` placeholder: an HTML comment embedded in the markdown file that contains a prompt. When you invoke the `/ai-placeholder` skill in Claude Code, it reads the prompt and writes the generated content between the opening and closing markers — directly into the file, in place, just like any other mdship operation.

The workflow has three steps, enforced by the skill:

1. **Check**: before writing anything, the skill calls `mdship ai-check` via MCP to verify that the existing content has not been manually edited since it was last generated. If the checksum does not match, the skill stops and reports the conflict to you rather than overwriting your edits.
2. **Generate**: if the check passes (or there is no checksum yet, meaning the section is new), the LLM reads the prompt and writes the content.
3. **Seal**: after writing, the skill calls `mdship ai-fix` via MCP to record a new checksum for the freshly generated content, protecting it against accidental edits until the next intentional update.

The MCP integration means these calls happen automatically, as part of the skill's defined behavior — not as something the LLM has to remember to do.

## The Prompt Is Documentation Too

There is a subtler benefit to this approach that is easy to overlook.

The prompt that instructs the LLM stays embedded in the file, in a non-rendered HTML comment, right above the content it produced. It does not live in a commit message, a Jira ticket, or a separate prompt library that may be hard to find six months later. It is part of the document.

This has practical consequences. If you need to regenerate a section — because the underlying API changed, or a referenced file was updated, or you simply want a fresh pass — you re-run the same prompt against the same file. The instruction is already there; you do not have to reconstruct it.

The prompt can also reference external files: other documentation pages, source code, configuration files. If those change, rerunning the prompt picks up the changes automatically. The document becomes self-updating in the sense that the machinery to update it is built in.

## Conclusion

mdship's in-place editing model and its LLM integration are two expressions of the same design choice: keep everything in one file, protect it with checksums, and let the tooling manage the regeneration cycle rather than the author.

For technical writers, this means fewer context switches, no build step, and a document that carries both its content and the instructions for maintaining that content in a single portable file. The trade-off — shared space for managed and hand-written content — is managed by the checksum guardrail, which turns silent overwrites into explicit decisions.

Whether the content is generated by mdship itself or by an LLM following an embedded prompt, the contract is the same: write it, seal it, and trust that the next update will ask before it overwrites.

<!--/AI-->