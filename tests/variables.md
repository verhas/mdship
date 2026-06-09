---
checksum: 70c60adc881eabc1887fe7f5513ca4bfa4ecccea94127c7c0f13b3ca1365c5e6
checksum_algorithm: sha256
---
<!--TOC
_terminate_: "TIC"
-->
- [1. Using variables in Markdown files](#1-using-variables-in-markdown-files)
  - [1.1. Variable without space in value](#11-variable-without-space-in-value)
  - [1.2. Variable with space in value](#12-variable-with-space-in-value)
  - [1.3. Complex variables](#13-complex-variables)
  - [1.4. Variables in MERMAID placeholders](#14-variables-in-mermaid-placeholders)
  - [1.5. Variable sources](#15-variable-sources)
    - [1.5.1. Front-matter](#151-front-matter)
    - [1.5.2. Variable source placeholders and their processing](#152-variable-source-placeholders-and-their-processing)
    - [1.5.3. Set a variable](#153-set-a-variable)
    - [1.5.4. Import variables](#154-import-variables)
    - [1.5.5. Sup one value](#155-sup-one-value)
    - [1.5.6. Slurp values](#156-slurp-values)
    - [1.5.7. Sipping values](#157-sipping-values)
    - [1.5.8. Specifying names](#158-specifying-names)
<!--/TIC-->

# 1. Using variables in Markdown files

`mdship` support variables in the markdown text.
A variable has a name and a string value.
When a variable name is referenced in an HTML comment like

## 1.1. Variable without space in value

```
<!--$variable-->variable_value
```

the value following and adjacent to the comment `variable_value` are updated with the actual value of the variable.
Such value MUST NOT contain space.
If it does, then the variable replacement will stop and signal an error.

## 1.2. Variable with space in value

To use variables that have a value with space in it you can use the form:

```
<!--$variable<END_MARKER>-->variable value<!--END_MARKER-->
```

where `END_MARKER` is an arbitrary string, so that `<​!--END_MARKER-->` does not appear in the value of the variable. 
The simplest and probably the most frequently used form is

```
<!--$variable<>-->variable value<!---->
```

Variable name space is a dictionary structure of arbitrary complexity.
The name can be any structural reference, like

```
<!--$fm.checksum_algorithm-->sha256
```

Variables can contain arrays.
In that case, the reference is like

```
<!--$elements[6]<>-->The sixth element<!---->
```

## 1.3. Complex variables

Variables can be used with the `$name.sub1.sub2...` form or `${name.sub1.sub2}` form in comments.

## 1.4. Variables in MERMAID placeholders

As the MERMAID handling code already preprocesses every `--\>` similarly it also has to replace every `$var` and `$var...` as well as `${var}` variable references replacing them with their actual values at the location of the mermaid markup before passing the text to the mermaid processor.

The variables are NOT replaced by their values inside the Markdown document.
The mermaid markup in the document remains as it is.


## 1.5. Variable sources

During the update command, the first thing update does is scanning the Markdown file for variable sources.
The process creates a hierarchical dictionary of the variables.
Later phases that depend on variables, like Mermaid processing or variable update use the values collected.

>Since variable source processing is done before anything else, it also means that it does not matter where a variable is defined in the document.
> Definition can be at the end of the document, and the variable can still be used at the start, preceding the definition.
> 
> That way, one may argue that these things are more like constants than variables.
> Their value is fixed during the processing of a single document, but they may have different values during different updates.

Variables can come from various sources.
These are listed in the following subchapters.

When a variable gets defined, it is an error to define a variable that already has value.
The only exception is the `SLURP` and `SIP` placeholders.
They may define a strategy to use the first, last, or all the values when a variable is defined multiple times within the processing of a single `SLURP` or `SIP`.
This is NOT the redefinition of the variable.
This is how a variable is defined in the operation.

Even if strategy is defined in `SLURP` or `SIP` other than `fail` it is an error to define a variable that was already defined before the placeholder.

### 1.5.1. Front-matter

The YAML structure of the front matter is available as `$fm`.
The variable name `fm` is reserved for this purpose.

Example:

```
<!--$fm.checksum-->70c60adc881eabc1887fe7f5513ca4bfa4ecccea94127c7c0f13b3ca1365c5e6
```

### 1.5.2. Variable source placeholders and their processing

Other variable sources are defined with placeholders.
These are

* `SET`
* `IMPORT`
* `SLURP`
* `SIP`

>These placeholders may be followed by a closing `<​!--/xxx-->​` comment, but it is ignored and not required.
> These placeholders are self-contained, and they do not generate output between the possible start and end marker comments.
> If there is a following end marker command and text between, the processing does not alter them.

### 1.5.3. Set a variable

The placeholder SET can define one or more variables.

```
<!--SET
variable1: value1
variable2: value2
...
-->
```

will set the value of the variable `variable1`, `variable2` and so on.

SET is a placeholder and is processed by the placeholder processing code.

The value can be a string or a YAML substructure, for example:

```
<!--SET
myStructure:
  degree: 3
  direction: "north"
  speed:
    unit: "m/s"
    value: 34
  altitude: 300  
otherVariable: "fun"
-->
```

and then the variables can be referenced as `<!​--$myStructure.degree-​->3` in the document.
The `<!​--$otherVariable-​->fun` will also be a variable with the actual value.


### 1.5.4. Import variables

```
<!--IMPORT
name: "myImported"
format: "json"
from: "filename.ext"
-->
```

will read the file `filename.ext` and load the data under the variable name `myImported`.
The format of the file is identified from the extension by default and can be overridden by `format`.

The extensions and the format they define:

* `.json` → JSON
* `.yaml`/`.yml` → YAML
* `.toml` → TOML
* `.xml` → XML

Data can be read from JSON, YAML, TOML and XML files.

When importing from XML files, the data may contain XML tags and also attributes.

```
<myStructure>
  <degree>3</degree>
  <speed unit="m/s">
    <value>34</value>
  </speed>
</myStructure>
```

In this case `<!​--$myStructure.degree-​->3` is okay but `<!​--$myStructure.speed.@unit-​->m/s` needs the `@` before the name to denote that the value comes from an attribute.
That way, a tag may have an attribute and a sub tage with the same name and still possible to reference them both.
In the implementation the `@` character simply becomes part of the name.

<!--SUP
name: "sup"
pattern: '^#+(.*?)\s+'
-->
### 1.5.5. Sup one value

A value can be supped from the document itself.
The placeholder `SUP` should define a `name` and a `pattern`, like
```
<!--SUP
name: "sup"
pattern: '^#+(.*?)\s+'
-->
```

The pattern must contain exactly one capturing group.
The pattern must match part of the next line (not necessary the whole line).
The value of the variable will be the substring captured by the group.
The name gives the name of the variable.

### 1.5.6. Slurp values

Values can be slurped from files.
Slurping is when the code scans the whole files and tries to find values on each line matching expressions.

```
<!--SLURP
name: "myVar"
from: "file name or directory name"
include: "glob pattern"
exclude: "glob pattern"
recurse: true
strategy: "fail"|"first"|"last"|"concatenate"
separator: "separator string in the case strategy is concatenate. default is empty string"
rules:
  - 'regular expression with exactly two gathering groups'
  - 'other pattern...'
-->
```
* `name` defines the top level name of the variable structure.
  If there is no `name` defined then the variables will be slurped to the top level.
  If there is a name define, for example `soup`, then the variable `x` will be `$soup.x`
  `name` is used to keep different slurping sepatare.
* `include` and `exclude` can only be specified if the `from` is a directory.
  They define the file patterns that have to be included or excluded in the slurping.
  A file is used if it matches the include pattern and NOT the exclude pattern.
* `recurse` default false, to recurse subdirectories.
  Can only be used when `from` is a directory.
* Files are processed in their alphabetical order in a directory and depth-first order when walking directories.
  This ordering is arbitrary but provides consistent behaviour in the case of multiple defined variables when the
  `strategy` is not `fail`.
* `rules` specify regular expression patterns.
  These patterns are matched against each line of each file.
  Each pattern must have exactly two capturing groups.
  When a line matches, the first group is used as the name of the variable and the second is the value of the variable.
  If the line structure is so that the name of the variable is later on the line following the value then two named capturing groups have to be used, like `(?P<val>\w+) (?P<var>\w+)` named `var` and `val`. 
* `strategy` defines the behavior if a variable is defined multiple times during slurping.
  Strategy does not govern the redefinition of variables that were already defined before the slurping.
  * `fail` means, the process should error
  * `first` the first definition prevails.
  * `last` the last definition prevails.
  * `concatenate` definitions are appended one after the other


### 1.5.7. Sipping values

Values can also be sipped from files.
It is similar to slurping, but the name of the variable is defined in the SIP placeholder and they do not come from the file.

<!--SIP
name: "project"
from: "../pyproject.toml"
vars:
  version: '^\s*version\s+=\s+"(.*)"$'
-->
<!--$project.version-->1.0.1
```
<!--SIP
name: "myVar"
from: "file name or directory name"
include: "glob pattern"
exclude: "glob pattern"
recurse: true
strategy: "fail"|"first"|"last"|"concatenate"
separator: "separator string in the case strategy is concatenate. default is empty string"
vars:
  variable1: 'regular expression with exactly one gathering groups'
  variable2: 'other pattern...'
  ...
-->
```

* `name`, `from`, `include`, `exclude`, `recurse`, `strategy` and `separator` work the same way as in the case of `SLURP`.
* Variables `variable1`, `variable2` and so on are defined by the regular expressions mathich the lines in the file or files.
  The regular expressions need only one capturing group since the line is only used to get the value for the variable.

<!--SUP {name: "chapter.names", pattern: '@heading'}-->
### 1.5.8. Specifying names

<!--TEMPLATE
content: |-
  ```
  $pattern
  ```
-->
```
{'heading': '^#+\\s+([\\d.]+)', 'version': 'v?(\\d+\\.\\d+\\.\\d+)'}
```
<!--/TEMPLATE-->

This chapter number is <!--$chapter.names-->1.5.8.

Several placeholders use the field `name` to specify a variable or structure name.
The general structure of such names is hierarchical as

```
x1.x2.x3. … .xN
```

The levels `x1 … x(N-1)` are automatically created if they do not exist yet.
It is an error if any of the `x1 … x(N-1)` levels already exist with a scalar (not a dictionary) value. 

For example

```
<!--SET
chapters:
  first: "Introduction"
  second: "History of the subject"
-->
<!--SUP
name: "chapters.first"
pattern: '#+\s*(.*?)\s*'
-->
```
will result an error because `chapters.first` is already defined.

Also, 

```
<!--SUP
name: "chapters.first.X"
pattern: '#+\s*(.*?)\s*'
-->
```

will result in error.
Although `chapters.first.X` does not exist, but it cannot be created in `chapters.first` because it is not a dictionary/map.