# INCLUDE placeholder test

This file demonstrates how to include some content into one file from another.

<!--INCLUDE
from: "test_markdown.py"
start:
  pattern: 'class\s+TestShiftHeadings'
  include: false
end: '^\s*$'
prefix: "```python"
postfix: "```"
margin: 0
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
  pattern: "--INCLUDE"
  include: true
end: 
  pattern: '--\s*>'
  include: true
prefix: '```'
postfix: "```"
_terminate_ : "WAPWAPWAP"
-->
```
<!--INCLUDE
from: "test_markdown.py"
start:
  pattern: 'class\s+TestShiftHeadings'
  include: false
end: '^\s*$'
prefix: "```python"
postfix: "```"
margin: 0
-->
<!--INCLUDE
from: "including.md"
start:
  pattern: "--INCLUDE"
  include: true
end: 
  pattern: '--\s*>'
  include: true
prefix: '```'
postfix: "```"
_terminate_ : "WAPWAPWAP"
-->
<!--INCLUDE
from: "test_markdown.py"
range: "1..5"
prefix: "```python"
postfix: "```"
_terminate_: "CODESNIPPET"
-->
```
<!--/WAPWAPWAP-->




<!--INCLUDE
from: "test_markdown.py"
range: "1..5"
prefix: "```python"
postfix: "```"
_terminate_: "CODESNIPPET"
-->
```python
"""Tests for markdown manipulation functions."""

import pytest

from mdship.markdown import (
```
<!--/CODESNIPPET-->

Done!
