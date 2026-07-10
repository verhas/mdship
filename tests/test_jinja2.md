# Manual JINJA2 Placeholder Test

Run from the repository root:

```sh
mdship --no-bak update tests/test_jinja2.md
```

Expected checks after update:

- The generated report title is `# DemoApp Release Report`.
- Only enabled features are listed.
- The generated Python code block contains rendered scalar, nested, list, loop, conditional, and filter values.
- The literal `$not_replaced_by_jinja2` text remains unchanged, because JINJA2 uses `{{ variable }}` syntax rather than mdship `$var` substitution inside the template.

<!--SET
app:
  name: "DemoApp"
  version: "2.4.1"
  environment: "staging"
  owner:
    name: "Smart Alec"
    email: "alex@example.test"
features:
  - name: "api"
    enabled: true
  - name: "docs"
    enabled: true
  - name: "billing"
    enabled: false
ports:
  - 8000
  - 8443
-->

<!--JINJA2
content: |
  # {{ app.name }} Release Report

  Version: `{{ app.version }}`
  Environment: `{{ app.environment | upper }}`
  Owner: {{ app.owner.name }} <{{ app.owner.email }}>

  ## Enabled Features

  {% for feature in features if feature.enabled %}
  - {{ loop.index }}. {{ feature.name }}
  {% endfor %}

  ## Ports

  {% for port in ports %}
  - `{{ port }}`
  {% endfor %}

  ## Generated Code

  ```python
  APP_NAME = "{{ app.name }}"
  VERSION = "{{ app.version }}"
  ENVIRONMENT = "{{ app.environment }}"
  FIRST_PORT = {{ ports[0] }}
  ENABLED_FEATURES = [
  {% for feature in features if feature.enabled %}
      "{{ feature.name }}",
  {% endfor %}
  ]
  LITERAL_DOLLAR_VALUE = "$not_replaced_by_jinja2"
  ```
_content_generated_: 394:md5:fa30d7647e032a2fd3e607a70251132c
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
# DemoApp Release Report

Version: `2.4.1`
Environment: `STAGING`
Owner: Smart Alec <alex@example.test>

## Enabled Features


- 1. api

- 2. docs


## Ports


- `8000`

- `8443`


## Generated Code

```python
APP_NAME = "DemoApp"
VERSION = "2.4.1"
ENVIRONMENT = "staging"
FIRST_PORT = 8000
ENABLED_FEATURES = [

    "api",

    "docs",

]
LITERAL_DOLLAR_VALUE = "$not_replaced_by_jinja2"
```
<!--/JINJA2-->
