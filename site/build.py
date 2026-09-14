"""Build the mdship website from README.md and documentation/.

    python site/build.py [--out _site]

Renders the Markdown with markdown-it-py (heading ids use mdship's own anchor
algorithm, so in-document links keep working), highlights code with Pygments,
rewrites links between .md files to site pages, and then checks every
internal link and fragment in the generated site. Exits non-zero on a
broken internal link.
"""

from __future__ import annotations

import argparse
import html
import posixpath
import re
import shutil
import sys
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from mdship.markdown.toc import _generate_anchor

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
REPO_URL = "https://github.com/verhas/mdship"
CODE_STYLE = "github-dark"
SITE_BASE = "/mdship/"  # GitHub Pages project path; only the 404 page needs it

# Sidebar navigation: (section, [(source file relative to ROOT, label or None)]).
# A label of None uses the page's first heading.
NAV = [
    ("Get started", [
        ("README.md", "Overview & quickstart"),
        ("documentation/AI.md", "AI placeholders"),
        ("documentation/GITHUB_ACTIONS.md", "CI with GitHub Actions"),
    ]),
    ("Concepts", [
        ("documentation/placeholder.md", "Placeholders in Markdown"),
        ("documentation/content_integrity.md", "Content integrity"),
        ("documentation/PYTHON.md", "Python scripting"),
    ]),
    ("Placeholders", [
        ("documentation/INCLUDE.md", "INCLUDE"),
        ("documentation/TOC.md", "TOC"),
        ("documentation/SET.md", "SET"),
        ("documentation/IMPORT.md", "IMPORT"),
        ("documentation/SLURP.md", "SLURP"),
        ("documentation/SIP.md", "SIP"),
        ("documentation/SUP.md", "SUP"),
        ("documentation/JINJA2.md", "JINJA2"),
        ("documentation/MERMAID.md", "MERMAID"),
        ("documentation/TEMPLATE.md", "TEMPLATE (deprecated)"),
    ]),
    ("Reference", [
        ("documentation/REFERENCE.md", "Full reference"),
    ]),
    ("Articles", [
        ("documentation/articles/ai_managed_conten.md", "When documentation manages itself"),
    ]),
]

COMMAND_GROUPS = [
    ("AI workflow", ["ai-list", "ai-check", "ai-fix", "ai-comments", "ai-context-and-update"]),
    ("Content", ["update", "init", "scripts", "mcp"]),
    ("Structure", ["fix-headings", "shift-headings", "number", "unnumber"]),
    ("Formatting", ["reflow", "semantic-line-breaks", "format-tables"]),
    ("Reading & editing", [
        "list-headings", "get-section", "replace-section", "get-lines", "insert-lines",
        "delete-lines", "get-paragraphs", "find-replace", "extract-table", "update-table",
        "frontmatter-get", "frontmatter-set",
    ]),
    ("Checking", ["validate", "sum", "verify"]),
]

CALLOUTS = {
    "deprecated": "warn", "warning": "warn", "important": "warn",
    "note": "info", "tip": "tip",
}


@dataclass
class Page:
    source: Path
    url: str
    label: str
    section: str
    title: str = ""
    body: str = ""
    summary: str = ""
    toc: list[tuple[int, str, str]] = field(default_factory=list)
    ids: set[str] = field(default_factory=set)


def page_url(source: Path) -> str:
    rel = source.relative_to(ROOT).as_posix()
    if rel == "README.md":
        return "docs/index.html"
    rel = rel.removeprefix("documentation/")
    stem = rel.removesuffix(".md").lower().replace("_", "-")
    return f"docs/{stem}.html"


def relative(from_url: str, to_url: str) -> str:
    """Relative link from one site page to another (site is served under a sub-path)."""
    return posixpath.relpath(to_url, posixpath.dirname(from_url) or ".")


# --- Markdown preprocessing -------------------------------------------------

FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
TOC_OPEN = re.compile(r"^<!--TOC\b(.*?)-->\n", re.S | re.M)
TERMINATE = re.compile(r"""_terminate_:\s*["']?([A-Za-z0-9_]+)""")


def strip_managed_toc(text: str) -> str:
    """Remove TOC placeholders and their generated lists; the site has its own navigation."""
    while (m := TOC_OPEN.search(text)) is not None:
        term = TERMINATE.search(m.group(1))
        closing = f"<!--/{term.group(1)}-->" if term else "<!--/TOC-->"
        end = text.find(closing, m.end())
        if end == -1:
            break
        text = text[: m.start()] + text[end + len(closing):].lstrip("\n")
    return text


# --- Rendering ----------------------------------------------------------------

class Renderer:
    def __init__(self, pages_by_source: dict[Path, Page], out: Path):
        self.pages_by_source = pages_by_source
        self.out = out
        self.formatter = HtmlFormatter(nowrap=True)
        self.md = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
        rules = self.md.renderer.rules
        rules["fence"] = self.render_fence
        rules["code_block"] = self.render_fence
        rules["code_inline"] = self.render_code_inline
        rules["html_block"] = self.render_html
        rules["html_inline"] = self.render_html
        rules["heading_open"] = self.render_heading_open
        rules["link_open"] = self.render_link_open
        rules["image"] = self.render_image
        rules["table_open"] = lambda *a: '<div class="table-wrap"><table>\n'
        rules["table_close"] = lambda *a: "</table></div>\n"
        rules["blockquote_open"] = self.render_blockquote_open

    # Per-page state is set in render().
    def render(self, page: Page) -> None:
        self.page = page
        text = page.source.read_text(encoding="utf-8")
        text = strip_managed_toc(FRONT_MATTER.sub("", text, count=1))
        tokens = self.md.parse(text)
        self.slugs: dict[str, int] = {}
        page.toc = []
        page.body = self.md.renderer.render(tokens, self.md.options, {})
        page.ids = set(self.slugs)
        if not page.title:
            h1 = next((t for i, t in enumerate(tokens)
                       if t.type == "inline" and tokens[i - 1].type == "heading_open"
                       and tokens[i - 1].tag == "h1"), None)
            page.title = h1.content if h1 else page.label
        first_paragraph = next((tokens[i + 1].content for i, t in enumerate(tokens)
                                if t.type == "paragraph_open" and tokens[i + 1].type == "inline"
                                and not tokens[i + 1].content.startswith(("<!--", "!["))), "")
        plain = re.sub(r"`|\*\*|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", first_paragraph)
        sentence = re.split(r"(?<=[.!?])\s", " ".join(plain.split()), maxsplit=1)[0]
        page.summary = sentence if len(sentence) <= 140 else sentence[:137].rsplit(" ", 1)[0] + "…"

    def render_fence(self, tokens, idx, options, env):
        token = tokens[idx]
        code = token.content.replace("​", "")
        lang = (token.info or "").split()[0] if token.info else ""
        try:
            lexer = get_lexer_by_name(lang) if lang else get_lexer_by_name("text")
        except ClassNotFound:
            lexer = get_lexer_by_name("text")
        highlighted = highlight(code, lexer, self.formatter)
        label = html.escape(lang or "text")
        return (
            f'<div class="code"><div class="code-bar"><span class="code-lang">{label}</span>'
            f'<button class="copy" type="button" aria-label="Copy code">Copy</button></div>'
            f'<pre class="highlight"><code>{highlighted}</code></pre></div>\n'
        )

    def render_code_inline(self, tokens, idx, options, env):
        return f"<code>{html.escape(tokens[idx].content.replace(chr(0x200B), ''))}</code>"

    def render_html(self, tokens, idx, options, env):
        content = tokens[idx].content
        # Drop mdship control comments (placeholder configs, AI prompts, variable markers).
        stripped = re.sub(r"<!--.*?-->", "", content, flags=re.S)
        return "" if not stripped.strip() else stripped

    def render_heading_open(self, tokens, idx, options, env):
        token = tokens[idx]
        inline = tokens[idx + 1]
        children = inline.children or []
        text = "".join(c.content for c in children if c.type in ("text", "code_inline"))
        base = _generate_anchor(text) or "section"
        slug = base
        n = self.slugs.get(base, 0)
        while slug in self.slugs:
            n += 1
            slug = f"{base}-{n}"
        self.slugs[base] = n
        self.slugs[slug] = 0
        level = int(token.tag[1])
        if level in (2, 3):
            self.page.toc.append((level, slug, re.sub(r"^[\d.]+\.?\s+", "", text)))
        anchor = f'<a class="anchor" href="#{slug}" aria-hidden="true">#</a>'
        opening = f'<{token.tag} id="{slug}">{anchor}'
        # Show "2.3." heading numbers as a coloured badge.
        if inline.children and inline.children[0].type == "text":
            m = re.match(r"^(\d+(?:\.\d+)*)\.?\s+", inline.children[0].content)
            if m and level > 1:
                inline.children[0].content = inline.children[0].content[m.end():]
                return f'{opening}<span class="num">{m.group(1)}</span>'
        return opening

    def render_blockquote_open(self, tokens, idx, options, env):
        # "> **Deprecated:** ..." becomes a coloured callout.
        for t in tokens[idx + 1: idx + 4]:
            if t.type == "inline":
                m = re.match(r"^\*\*(\w+)", t.content)
                kind = CALLOUTS.get(m.group(1).lower()) if m else None
                if kind:
                    return f'<blockquote class="callout callout-{kind}">\n'
                break
        return "<blockquote>\n"

    def resolve(self, href: str) -> str:
        if not href or href.startswith(("#", "http://", "https://", "mailto:")):
            return href
        path, _, fragment = href.partition("#")
        target = (self.page.source.parent / path).resolve()
        frag = f"#{fragment}" if fragment else ""
        if target in self.pages_by_source:
            return relative(self.page.url, self.pages_by_source[target].url) + frag
        if target == (ROOT / "documentation/commands").resolve():
            return relative(self.page.url, "docs/commands/index.html") + frag
        try:
            rel = target.relative_to(ROOT).as_posix()
        except ValueError:
            return href
        if target.exists():
            kind = "tree" if target.is_dir() else "blob"
            return f"{REPO_URL}/{kind}/master/{rel}{frag}"
        return href

    def render_link_open(self, tokens, idx, options, env):
        token = tokens[idx]
        href = self.resolve(token.attrGet("href") or "")
        token.attrSet("href", href)
        if href.startswith(("http://", "https://")):
            token.attrSet("class", "external")
        return self.md.renderer.renderToken(tokens, idx, options, env)

    def render_image(self, tokens, idx, options, env):
        token = tokens[idx]
        src = token.attrGet("src") or ""
        if src and not src.startswith(("http://", "https://", "data:")):
            source = (self.page.source.parent / src).resolve()
            if source.is_file():
                dest_url = "assets/" + source.relative_to(ROOT).as_posix().replace("/", "-")
                (self.out / "assets").mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, self.out / dest_url)
                token.attrSet("src", relative(self.page.url, dest_url))
        alt = html.escape("".join(c.content for c in token.children or []))
        return f'<img src="{html.escape(token.attrGet("src") or "")}" alt="{alt}" loading="lazy">'


# --- Site assembly ------------------------------------------------------------

def collect_pages() -> tuple[list[tuple[str, list[Page]]], list[Page]]:
    sections: list[tuple[str, list[Page]]] = []
    everything: list[Page] = []
    for section, entries in NAV:
        pages = []
        for rel, label in entries:
            source = (ROOT / rel).resolve()
            page = Page(source=source, url=page_url(source), label=label or "", section=section)
            pages.append(page)
        sections.append((section, pages))
        everything.extend(pages)
    listed = {name for _, names in COMMAND_GROUPS for name in names}
    on_disk = {p.stem for p in (ROOT / "documentation/commands").glob("*.md")}
    if listed != on_disk:
        sys.exit(f"COMMAND_GROUPS out of sync with documentation/commands: "
                 f"missing {sorted(on_disk - listed)}, unknown {sorted(listed - on_disk)}")
    for group, names in COMMAND_GROUPS:
        for name in names:
            source = (ROOT / f"documentation/commands/{name}.md").resolve()
            everything.append(Page(source=source, url=page_url(source), label=name,
                                   section=f"Commands · {group}"))
    return sections, everything


def site_facts() -> dict:
    import typer

    from mdship.cli import app

    commands = [n for n, c in typer.main.get_group(app).commands.items() if not c.hidden]
    tools = re.findall(r"^\s*def ([a-z_]+)\(", (ROOT / "mdship/mcp_server.py").read_text(), re.M)
    tools = [t for t in tools if not t.startswith("_") and t != "main"]
    return {"commands": len(commands), "mcp_tools": len(tools), "version": version("mdship")}


def check_links(out: Path) -> list[str]:
    ids: dict[Path, set[str]] = {}
    problems = []
    pages = sorted(out.rglob("*.html"))
    for p in pages:
        ids[p] = set(re.findall(r'\bid="([^"]+)"', p.read_text(encoding="utf-8")))
    for p in pages:
        for href in re.findall(r'\b(?:href|src)="([^"]+)"', p.read_text(encoding="utf-8")):
            if href.startswith(("http://", "https://", "mailto:", "data:")):
                continue
            path, _, frag = html.unescape(href).partition("#")
            if path.startswith(SITE_BASE):
                target = (out / path.removeprefix(SITE_BASE)).resolve()
                if target.is_dir():
                    target = target / "index.html"
            else:
                target = (p.parent / path).resolve() if path else p
            if not target.exists():
                problems.append(f"{p.relative_to(out)}: missing target {href}")
            elif frag and target.suffix == ".html" and frag not in ids.get(target, set()):
                problems.append(f"{p.relative_to(out)}: missing anchor {href}")
    return problems


def build(out: Path) -> int:
    if out.exists():
        shutil.rmtree(out)
    (out / "static").mkdir(parents=True)
    for asset in (SITE / "static").iterdir():
        shutil.copyfile(asset, out / "static" / asset.name)
    code_css = HtmlFormatter(style=CODE_STYLE).get_style_defs(".highlight")
    (out / "static" / "code.css").write_text(code_css)
    (out / ".nojekyll").write_text("")

    sections, pages = collect_pages()
    renderer = Renderer({p.source: p for p in pages}, out)
    for page in pages:
        renderer.render(page)
        page.label = page.label or page.title

    env = Environment(loader=FileSystemLoader(SITE / "templates"), autoescape=True)
    env.globals.update(repo_url=REPO_URL, relative=relative, facts=site_facts())

    nav = [(section, [p for p in section_pages]) for section, section_pages in sections]
    by_name = {p.source.stem: p for p in pages if p.section.startswith("Commands")}
    commands_nav = [(group, [by_name[n] for n in names]) for group, names in COMMAND_GROUPS]

    commands_index = Page(source=ROOT / "documentation/commands", url="docs/commands/index.html",
                          label="All commands", section="Commands", title="Commands")
    ordered = ([p for _, ps in nav for p in ps] + [commands_index]
               + [p for _, ps in commands_nav for p in ps])

    def write(page: Page, template: str, **extra):
        target = out / page.url
        target.parent.mkdir(parents=True, exist_ok=True)
        i = ordered.index(page) if page in ordered else -1
        prev_page = ordered[i - 1] if i > 0 else None
        next_page = ordered[i + 1] if 0 <= i < len(ordered) - 1 else None
        html_text = env.get_template(template).render(
            page=page, nav=nav, commands_nav=commands_nav, commands_index=commands_index,
            root=extra.pop("root", relative(page.url, "index.html").removesuffix("index.html")),
            prev_page=prev_page, next_page=next_page,
            edit_url=f"{REPO_URL}/edit/master/{page.source.relative_to(ROOT).as_posix()}"
            if page.source.suffix == ".md" else None,
            **extra,
        )
        target.write_text(html_text, encoding="utf-8")

    for page in pages:
        write(page, "doc.html")
    write(commands_index, "commands.html")
    landing = Page(source=ROOT / "README.md", url="index.html", label="mdship", section="",
                   title="mdship")
    write(landing, "landing.html", docs_home=pages[0])
    write(Page(source=ROOT / "README.md", url="404.html", label="Not found", section="",
               title="Page not found"),
          "404.html", root=f"{SITE_BASE}")

    problems = check_links(out)
    for problem in problems:
        print(f"broken link: {problem}", file=sys.stderr)
    print(f"built {len(list(out.rglob('*.html')))} pages into {out}"
          + (f" with {len(problems)} broken internal link(s)" if problems else ""))
    return 1 if problems else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "_site")
    sys.exit(build(parser.parse_args().out.resolve()))


if __name__ == "__main__":
    main()
