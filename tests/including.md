# INCLUDE placeholder test

<!--INCLUDE
from: "test_markdown.py"
range: "1..3"
prefix: "```python"
postfix: "```"
margin: 0
_content_generated_: 79:md5:83cef95d5163a345fdb0215261f40369
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
```python
"""Tests for markdown manipulation functions."""

import pytest
```
<!--/INCLUDE-->

This file demonstrates how to include some content in one file from another.

<!--INCLUDE
from: "test_markdown.py"
start:
  pattern: 'class\s+TestShiftHeadings'
  include: false
end: '^\s*$'
prefix: "```python"
postfix: "```"
margin: 0
_content_generated_: 203:md5:c14e754f47c1cd3759d289b9aaff6e7c
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
```python
def test_shift_down(self):
    content = "# Heading 1\n## Heading 2"
    result = shift_heading_levels(content, 1)
    assert "## Heading 1" in result
    assert "### Heading 2" in result
```
<!--/INCLUDE-->

The lines above are copied from the test_markdown.py file.

Another example in which we include from the file we are in, a recursive include with custom terminator:

<!--INCLUDE
from: "including.md"
start:
  pattern: '_terminate_: "WAPWAPWAP"'
  include: true
end: 
  pattern: '--\s*>'
  include: true
prefix: '```'
postfix: "```"
_terminate_ : "WAPWAPWAP"
_content_generated_: 637:md5:76c30e9ab6aaca431a85b181846f6a54
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
```
  pattern: '_terminate_: "WAPWAPWAP"'
  include: true
end: 
  pattern: '--\s*>'
  include: true
prefix: '```'
postfix: "```"
_terminate_ : "WAPWAPWAP"
_content_generated_: 323:md5:bafcbeb93dc7f8a6e754dcc07122fb08
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
  pattern: '_terminate_: "WAPWAPWAP"'
  include: true
end: 
  pattern: '--\s*>'
  include: true
prefix: '```'
postfix: "```"
_terminate_ : "WAPWAPWAP"
_content_generated_: 794:md5:eac9761002b363b71e48153955e96d9b
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
```
<!--/WAPWAPWAP-->




<!--INCLUDE
from: "test_markdown.py"
range: "1..5"
prefix: "```python"
postfix: "```"
_terminate_: "CODESNIPPET"
_content_generated_: 95:md5:caf70462414fee5d2d023e0b4fa0930a
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
```python
"""Tests for markdown manipulation functions."""

import pytest

import hashlib
```
<!--/CODESNIPPET-->

Done!
