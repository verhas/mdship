# Mdship Feature: Content Integrity Checking with _content_generated_

## Goal
Implement hash-based integrity checking for mdship placeholders to prevent accidental manual edits to managed content.

## Feature Specification

### Metadata Key: `_content_generated_`

Add support for a new optional metadata key in placeholder opening comments:

```html
<!--TOC
_content_generated_: 20:md5:af27b3d8e1f9a4c2...
# ⚠️  MANAGED CONTENT: Edits will be lost. 
# danger zone: Delete _content_generated_ to override.
-->
[MANAGED CODE HERE]
<!--/TOC-->
```

>`TOC` is an example placeholder.
> The feature is supported by all placeholders that have a closing html comment placeholder.
> These are the placeholders that also support the `_terminate_` parameter.

### Behavior: Fail-Hard Policy

1. **User does not add it:** 
   - The user is not supposed to add this key to the YAML meta data of the placeholder.
   - If the user adds it, treat it like it was added by mdship
   - Metadata and the whole opening placeholder HTML comment is untouched by mdship: `_content_generated_` is an exception.
  
1. **First Run (no `_content_generated_` present):**
   - Extract and insert managed content normally
   - This is the same functionality as in past versions before the introduction of `_content_generated_`
   - Compute MD5 hash of the inserted content
   - Compute the length of the inserted content
   - Add `_content_generated_: <length>:md5:<hash>` to the opening comment metadata
   - Add the warning comment lines (2 lines, as shown above, verbatim including the warning sign)

2. **Subsequent Runs (hash present):**
   - Extract the stored hash from metadata
   - Compute MD5 hash of current managed content
   - **If hashes match:** Update content normally, recompute hash, update metadata
   - **If hashes DON'T match:** FAIL with an error message (exit with non-zero code)
     - Error message: `"ERROR: Placeholder <name> content was manually edited. Hash mismatch detected. Delete _content_generated_ line to override and accept data loss."`

3. **User Override:**
   - User manually deletes the `_content_generated_: md5:...` line
   - Next mdship run: Hash is absent, treated as "first run", proceeds normally
   - User has explicitly acknowledged they're discarding edits

### Implementation Details

- Use MD5 for hashing (standard, available in Python)
- Hash should be computed on the **exact content** (preserve whitespace)
- Metadata format: `_content_generated_: md5:<hex-string>`
- Warning comment is always 2 lines, always uses this exact format:
  ```
  # ⚠️  MANAGED CONTENT: Edits will be lost. 
  # danger zone: Delete _content_generated_ to override.
  ```
- the hash update should happen in these steps:
  1. The code has to find the line that contains the `_content_generated_`
  2. Delete this line from the placeholder opening
  3. Insert the `_content_generated_` line with the updated length and hash code before the warning or
     at the end of the comment before the closing `-->` tag.
  4. Add the warning comment if they were not there.
- the update of the metadata `_content_generated_` happens parsing the text line by line to reserve user comments
- if the code does not find the `_content_generated_` line, 
  but there is a `_content_generated_` key in the metadata parsed from yaml, 
  then it is likely inside a valid YAML that does not put the key on a separate line.
  In this case an error has to be displayed, and the operation has to be aborted the same way as if the content was not matching the hash code.

### Integration Points

- Update the `Placeholder` class (or equivalent) to include the `_content_generated_` field
- Update placeholder parsing to extract hash from metadata YAML
- Update placeholder writing to compute and insert/update hash
- Update content extraction logic to compare hashes before updating
- raise ValueError (or appropriate exception) on hash mismatch, or if the hash cannot be updated safely

### Testing

1. **New placeholder (no hash):**
   - Run mdship, verify hash is computed and inserted correctly
   - Run again, verify hash persists and content updates cleanly

2. **Detect manual edits:**
   - Run mdship to create placeholder with hash
   - Manually edit the managed content
   - Run mdship again, verify it fails with an appropriate error message

3. **Recovery (delete hash):**
   - Edit managed content, delete `_content_generated_` line
   - Run mdship, verify it proceeds and recomputes the hash

4. **Idempotency:**
   - Run mdship multiple times without manual edits
   - Verify hash remains stable and content updates are safe

### Documentation

- Add section to `tests/variables.md` under the placeholder types spec
- Include the example above and explain the three scenarios
- Document the fail-hard behavior explicitly

## Acceptance Criteria

- [ ] Hash computation and storage working
- [ ] Hash validation on subsequent runs (fail-hard on mismatch)
- [ ] Warning comment properly formatted and preserved
- [ ] All edge cases handled (first run, updates, user override)
- [ ] Tests pass for all scenarios
- [ ] Spec updated in tests/variables.md
- [ ] Error messages are clear and actionable
```
