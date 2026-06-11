# AI Review Skill

## Invocation

The user has invoked `/ai-review`. Parse the argument to determine what to review:

- **`/ai-review <file>`** — review the entire file.
- **`/ai-review <file> <section>`** — review only the part of the document described by `<section>`. This may be an exact heading name or a descriptive location (e.g. "the part that talks about MCP server invocation", "every subsection that references other files").
- **No argument** — ask the user which file to review, which section (if any), and any revision guidance (see below).

In all forms the user may append free-form revision guidance after the file/section, for example:
- which other files contain relevant reference information
- a particular aspect to focus on (accuracy, completeness, tone, structure)
- things to ignore or treat as intentional

Read the file, insert `//AI:` annotations where you have suggestions, and report how many you added.

---

## What this skill does

`/ai-review` examines a document and inserts inline `//AI:` comments wherever there is a specific, actionable suggestion. It does **not** modify the actual content — it only annotates it. The author reads the comments, adjusts or removes any they disagree with, then runs `/ai-fix` to apply the rest.

## Comment format

Each annotation is a single line placed immediately before the text it refers to (or on the line directly after, if the comment describes something missing that should follow):

```
//AI: <suggestion> — <reasoning>
```

- **Suggestion**: the specific change — what to add, remove, reword, or restructure.
- **Reasoning**: why this change improves the text. This must be included so the author can evaluate the suggestion and so `/ai-fix` can apply it correctly without the current conversation as context.

Example:
```markdown
//AI: Replace "substituted" with "updated" — the operation replaces only the value portion of the marker, not the marker itself; "substitution" implies the whole expression is replaced.
Variable references are substituted by `mdship update`.
```

## Rules

1. **Do not modify content.** Only insert `//AI:` lines. The document content between annotations must be byte-for-byte identical to the input.
2. **Only annotate where you have a genuine suggestion.** Do not add comments for things that are already correct.
3. **Be specific.** "Clarify this" is not a valid comment. State exactly what to change and why.
4. **One comment per issue.** Do not stack multiple `//AI:` lines for the same location — fold them into one.
5. **Comments must be self-contained.** A future session running `/ai-fix` will see only the file. The reasoning must be sufficient to act on the comment without this conversation.
6. **Do not comment on style preferences.** Only suggest changes that improve correctness, clarity, or accuracy.

## After inserting comments

Report:
- How many `//AI:` comments were inserted.
- A brief summary of the main themes (e.g. "3 factual corrections, 2 clarity improvements").
