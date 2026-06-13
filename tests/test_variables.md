---
title: Test Variables Feature
description: Comprehensive test of SET placeholder functionality
checksum: 8c75d4856825b6e1397775a178f0934837230d5cd4add677023db6ad964e490d
checksum_algorithm: sha256
---

<!--TOC
# this is comment
_content_generated_: 1260:md5:4983287d99127d07b05f86c131e8042a
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
- [1. Variables Feature Test](#1-variables-feature-test)
  - [1.1. Variables Definition](#11-variables-definition)
  - [1.2. Variable References](#12-variable-references)
    - [1.2.1. Simple Variables](#121-simple-variables)
    - [1.2.2. Nested Variables](#122-nested-variables)
    - [1.2.3. Nested Structure Variables](#123-nested-structure-variables)
    - [1.2.4. Deep Nesting](#124-deep-nesting)
  - [1.3. Variable Syntax Forms](#13-variable-syntax-forms)
    - [1.3.1. Dollar Sign Notation](#131-dollar-sign-notation)
    - [1.3.2. Bracketed Notation](#132-bracketed-notation)
  - [1.4. MERMAID with Variables](#14-mermaid-with-variables)
  - [1.5. Variable References in Markdown](#15-variable-references-in-markdown)
    - [1.5.1. Simple Variable Reference (No Spaces)](#151-simple-variable-reference-no-spaces)
    - [1.5.2. Variable Reference with Spaces](#152-variable-reference-with-spaces)
    - [1.5.3. Complex References](#153-complex-references)
    - [1.5.4. Important Notes](#154-important-notes)
  - [1.6. Documentation](#16-documentation)
  - [1.7. Testing Notes](#17-testing-notes)
  - [1.8. Additional Variables Example](#18-additional-variables-example)
  - [1.9. XML import](#19-xml-import)
  - [1.10. JSON import](#110-json-import)
<!--/TOC-->

# 1. Variables Feature Test

This document demonstrates the SET placeholder functionality in mdship.

## 1.1. Variables Definition

The following variables are defined at the start:

<!--SET
appName: "MyApplication"
# this is the application version
version: "2.5.1"
# this is a comment in the YAML meta-data of the placeholder
author: "Test Suite"
projectConfig:
  language: "Python"
  framework: "mdship"
  license: "MIT"
  authors:
    - "Alice"
    - "Bob"
    - "Charlie"
  settings:
    debug: true
    maxRetries: 3
-->

## 1.2. Variable References

Variables defined above can be referenced throughout the document.

### 1.2.1. Simple Variables

- Application Name: `$appName` (should show: MyApplication)
- Version: `$version` (should show: 2.5.1)
- Author: `$author` (should show: Test Suite)

### 1.2.2. Nested Variables

- Language: `$projectConfig.language` (should show: Python)
- Framework: `$projectConfig.framework` (should show: mdship)
- License: `$projectConfig.license` (should show: MIT)

### 1.2.3. Nested Structure Variables

- First author: `$projectConfig.authors[0]` (should show: Alice)
- Second author: `$projectConfig.authors[1]` (should show: Bob)
- Third author: `$projectConfig.authors[2]` (should show: Charlie)

### 1.2.4. Deep Nesting

- Debug enabled: `$projectConfig.settings.debug` (should show: true)
- Max retries: `$projectConfig.settings.maxRetries` (should show: 3)

## 1.3. Variable Syntax Forms

Variables support multiple syntax forms:

### 1.3.1. Dollar Sign Notation

- Simple: `$appName`
- Nested: `$projectConfig.language`
- Array: `$projectConfig.authors[1]`

### 1.3.2. Bracketed Notation

- Simple: `${appName}`
- Nested: `${projectConfig.framework}`
- Array: `${projectConfig.authors[0]}`

## 1.4. MERMAID with Variables

The following diagram uses variables for dynamic labels:

<!--MERMAID
file: "_test_diagram.svg"
diagram: |
  graph TD
    A["$appName v${version}"] --\> B["Language: $projectConfig.language"]
    B --\> C["Framework: $projectConfig.framework"]
    C --\> D["License: $projectConfig.license"]
    D --\> E["Author 1: $projectConfig.authors[0]"]
    E --\> F["Debug: $projectConfig.settings.debug"]
_content_generated_: 31:md5:f8f8aede57a29a432723042ba9aed83c
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
![diagram](_test_diagram.svg)
<!--/MERMAID-->

## 1.5. Variable References in Markdown

Variables can also be directly referenced in the markdown document using special comment syntax.

### 1.5.1. Simple Variable Reference (No Spaces)

For single-word values, use the format:

```
<!--$variable-->value_here
```

The value text will be replaced with the actual variable value.

Example in this document:

- Application: <!--$appName-->`MyApplication`
- Version: <!--$version-->2.5.1
- License: <!--$projectConfig.license-->MIT

### 1.5.2. Variable Reference with Spaces

For values containing spaces, use a marker:

```
<!--$variable<MARKER>-->placeholder<!--MARKER-->
```

The simplest form uses empty markers.

Examples in this document:

- Framework: <!--$projectConfig.framework<>-->``mdship``<!---->
- Language: <!--$projectConfig.language<>-->Python<!---->
- First author: <!--$projectConfig.authors[0]<>-->Alice<!---->
- Second author: <!--$projectConfig.authors[1]<>-->Bob<!---->
- Third author: <!--$projectConfig.authors[2]<>-->Charlie<!---->

You can also use any arbitrary marker string:

- Debug mode: <!--$projectConfig.settings.debug<DEBUG>-->True<!--DEBUG-->
- Max retries: <!--$projectConfig.settings.maxRetries<RETRY>-->3<!--RETRY-->

### 1.5.3. Complex References

Nested variables work the same way:

- Config language: <!--${projectConfig.language}-->Python
- Array element: <!--$projectConfig.authors[2]<>-->Charlie<!---->
- Deep nesting: <!--$projectConfig.settings.maxRetries-->3

### 1.5.4. Important Notes

- Variable references are updated by `mdship update` command
- They are NOT updated in MERMAID diagram source (MERMAID variables stay as-is in document)
- Markers must match exactly: opening marker `<X>` must have closing marker `<!--X-->`
- Without spaces form must have placeholder with no spaces

## 1.6. Documentation

Variables are collected during the first phase of `mdship update` command processing.
This allows:

- Defining variables anywhere in the document (position doesn't matter)
- Using variables in subsequent placeholders like MERMAID
- Complex nested structures with arrays and dictionaries
- Multiple syntax forms for flexibility

## 1.7. Testing Notes

To test this document, run:

```bash
mdship update tests/test_variables.md
```

This will:

1. Collect all variables from SET placeholders
2. Process any INCLUDE placeholders
3. Generate table of contents (if TOC markers present)
4. Render MERMAID diagrams with variable substitution

The resulting diagram file at `tests/_test_diagram.svg` should show the substituted values.

## 1.8. Additional Variables Example

For reference, here's what a more complex SET placeholder looks like:

```
<!--SET
deployment:
  production:
    host: "api.example.com"
    port: 443
    region: "us-east-1"
  staging:
    host: "staging-api.example.com"
    port: 8443
    region: "us-west-2"
features:
  - "authentication"
  - "caching"
  - "monitoring"
-->
```

Then you could reference:

- `$deployment.production.host` → "api.example.com"
- `$deployment.staging.region` → "us-west-2"
- `$features[1]` → "caching"

## 1.9. XML import

<!--IMPORT
name: "wood_catalog"
from: "sample_data.xml"
-->
<!--$wood_catalog.catalog.type.@publicNameOnRecord-->sapele
<!--$wood_catalog.catalog.type.@catalog<>-->wood directory<!---->
<!--$wood_catalog.catalog.items.item[0].name-->walnut
<!--$wood_catalog.catalog.items.item[0].@serial-->63512

## 1.10. JSON import

<!--IMPORT
name: "project_data"
from: "sample_data.json"
-->

|                       |                                                                                   |
|:----------------------|:----------------------------------------------------------------------------------|
| Project:              | <!--$project_data.project.name-->mdship
| Version:              | <!--$project_data.project.version-->1.0.0
| Description:          | <!--$project_data.project.description<😇>-->Markdown Mani Pulation Tool<!--😇-->  |
| Team Lead:            | <!--$project_data.team.lead<>-->Alice Johnson<!---->                              |
| First Developer:      | <!--$project_data.team.members[0].name<>-->Bob Smith<!---->                       |
| First Developer Role: | <!--$project_data.team.members[0].role-->Deviloper
| Python Version:       | <!--$project_data.config.python_version-->3.11+

