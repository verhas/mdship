#!/usr/bin/env bash
#
# Build / release helper for mdship. Run './build.sh --help' for the full
# command list.

set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-/opt/homebrew/bin/python3}"
NOTES_FILE="RELEASES.md"

# The system curl rather than whichever comes first on PATH: a MacPorts curl
# built for another CPU sat ahead of it here, and every PyPI check failed.
CURL=/usr/bin/curl
[ -x "$CURL" ] || CURL=curl

# Opens every GitHub release body, above the version's own notes.
RELEASE_PREAMBLE='mdship keeps AI-written and generated parts of your Markdown in sync with their sources.

Install: `pip install mdship` (add the `mermaid` extra for diagrams: `pip install '"'"'mdship[mermaid]'"'"'`)

Docs: https://verhas.github.io/mdship/'

# ANSI colours, but only when stdout is a terminal, so piping stays clean.
if [ -t 1 ]; then
    BOLD=$'\033[1m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; OFF=$'\033[0m'
else
    BOLD=""; RED=""; GREEN=""; YELLOW=""; OFF=""
fi

info() { printf '%s==>%s %s\n' "$BOLD" "$OFF" "$*"; }
warn() { printf '%s==> %s%s\n' "$YELLOW" "$*" "$OFF"; }
ok()   { printf '%s==> %s%s\n' "$GREEN" "$*" "$OFF"; }
die()  { printf '%s==> %s%s\n' "$RED" "$*" "$OFF" >&2; exit 1; }

show_help() {
    cat <<EOF
${BOLD}Build / release helper for mdship${OFF}

Usage: ./build.sh [command] [args]

Everyday commands:
  build              sync dependencies, run the tests, and build the wheel and
                     sdist into dist/ -- what runs with no command at all
  test               sync dependencies and run the tests only
  clean              delete dist/

Release commands, in the order a release actually goes out:
  version [x.y.z]    show the current version, or bump to a new one
                     (pyproject.toml, mdship/__init__.py and uv.lock)
  notes              print the GitHub release text for the current version,
                     taken from its '## x.y.z' section of $NOTES_FILE
  build              as above; the release is built from this
  pypi               upload dist/mdship-<version>* to PyPI, once it has checked
                     everything is committed and pushed, the release notes
                     exist, and the build is no older than the source
  publish            create the v<version> GitHub release with the notes and
                     the dist files, after the same checks plus that the
                     version is already on PyPI

Environment variables:
  PYTHON             interpreter uv syncs with, default /opt/homebrew/bin/python3
  UV_PUBLISH_TOKEN   PyPI token; when unset it is read from ~/.pypirc [pypi]
EOF
}

# The [project] version in pyproject.toml -- the one source of truth that
# hatchling builds from and importlib.metadata later reports.
current_version() {
    sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml | head -1
}

sync_deps() {
    info "Syncing dependencies"
    uv sync --all-extras --python "$PYTHON"
}

run_tests() {
    sync_deps
    info "Running tests"
    uv run pytest tests/ -q || die "Tests failed"
    ok "Tests passed"
}

build() {
    run_tests

    local version
    version=$(current_version)
    [ -n "$version" ] || die "no version in pyproject.toml"

    if [ -n "$(git status --porcelain --untracked-files=all | grep '^??' || true)" ]; then
        warn "untracked files are not excluded from the sdist -- pypi will refuse it:"
        git status --porcelain | grep '^??' | sed 's/^/    /'
    fi

    info "Building mdship $version"
    rm -f dist/mdship-"$version"-*.whl dist/mdship-"$version".tar.gz
    uv build

    release_notes_section "$version" >/dev/null \
        || warn "$NOTES_FILE has no '## $version' section yet -- needed before pypi/publish"
    ok "Built mdship $version"
    ls -1 dist/mdship-"$version"* | sed 's/^/    /'
}

# Setting the version by hand is easy to half-do: pyproject.toml is what gets
# built, but uv.lock records mdship's own version too, and a stale lock makes
# the next 'uv sync --locked' fail; mdship/__init__.py carries a __version__
# that nobody would think to update.
show_or_set_version() {
    local wanted="${1:-}"
    local current
    current=$(current_version)
    [ -n "$current" ] || die "no version in pyproject.toml"

    if [ -z "$wanted" ]; then
        printf '%s\n' "$current"
        return
    fi

    [[ "$wanted" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "version must look like 1.2.3, not '$wanted'"
    [ "$wanted" != "$current" ] || die "the version already is $current"
    if git rev-parse -q --verify "refs/tags/v$wanted" >/dev/null; then
        die "tag v$wanted already exists -- that version has been released"
    fi

    sed -i '' "s/^version = \"$current\"$/version = \"$wanted\"/" pyproject.toml
    sed -i '' "s/^__version__ = \".*\"$/__version__ = \"$wanted\"/" mdship/__init__.py
    [ "$(current_version)" = "$wanted" ] || die "could not update pyproject.toml"
    uv lock --quiet || die "uv lock failed"

    ok "$wanted -- was $current"
    if ! release_notes_section "$wanted" >/dev/null; then
        printf '    %s\n' "Add a '## $wanted — $(date +%Y-%m-%d)' section to $NOTES_FILE before releasing"
    fi
}

# The body of the '## <version> — <date>' section of RELEASES.md: everything
# after the heading up to the '---' rule (or next release heading) closing it.
# Returns 1, printing nothing, when there is no such section.
release_notes_section() {
    local version="$1" body
    [ -f "$NOTES_FILE" ] || return 1
    body=$(awk -v v="$version" '
        found && (/^---[[:space:]]*$/ || /^## / || /^<!--\/AI-->/) { exit }
        found { print }
        index($0, "## " v " ") == 1 || $0 == "## " v { found = 1 }
    ' "$NOTES_FILE")
    # Trim leading and trailing blank lines.
    body=$(printf '%s\n' "$body" | sed -e '/./,$!d' | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}')
    [ -n "$body" ] || return 1
    printf '%s\n' "$body"
}

require_release_notes() {
    release_notes_section "$1" >/dev/null \
        || die "$NOTES_FILE has no '## $1' section -- write this release's notes first"
}

release_notes() {
    local version="$1" section
    require_release_notes "$version"
    section=$(release_notes_section "$version")
    # RELEASES.md writes placeholder syntax with a zero-width space after '<!'
    # and before '>' so mdship does not take it for a real marker; on GitHub
    # that would only break copy-paste, so it goes.
    printf '%s\n\n%s\n' "$RELEASE_PREAMBLE" "$section" | sed $'s/\xe2\x80\x8b//g'

}

# Released from what everyone else can also see, not from whatever this one
# checkout happens to be holding: nothing uncommitted, and nothing committed
# that has not reached the remote yet. Untracked files count too: hatchling
# puts every file .gitignore does not exclude into the sdist, tracked or not.
require_clean_and_pushed() {
    local dirty
    dirty=$(git status --porcelain)
    if [ -n "$dirty" ]; then
        printf '%s\n' "$dirty" | sed 's/^/    /'
        die "the working tree is not clean -- commit, discard or .gitignore these before releasing"
    fi
    local upstream ahead
    upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)
    [ -n "$upstream" ] || die "no upstream branch is configured for $(git branch --show-current | grep . || echo 'a detached HEAD')"
    git fetch --quiet
    ahead=$(git rev-list --count "$upstream"..HEAD)
    if [ "$ahead" != 0 ]; then
        git log --oneline "$upstream"..HEAD | sed 's/^/    /'
        die "$ahead commit(s) are not pushed to $upstream -- push before releasing"
    fi
}

# The wheel and the sdist for the version, both present and built after the
# last change to anything that goes into them -- 'build' and 'pypi' are
# separate steps, so an edit in between would otherwise ship unbuilt.
require_fresh_dist() {
    local version="$1"
    local wheel="dist/mdship-$version-py3-none-any.whl"
    local sdist="dist/mdship-$version.tar.gz"
    [ -f "$wheel" ] || die "$wheel does not exist -- run ./build.sh build first"
    [ -f "$sdist" ] || die "$sdist does not exist -- run ./build.sh build first"

    local newer
    newer=$(find mdship pyproject.toml README.md LICENSE* -type f \
                 -not -path '*/__pycache__/*' \( -newer "$wheel" -o -newer "$sdist" \) 2>/dev/null)
    if [ -n "$newer" ]; then
        printf '%s\n' "$newer" | sed 's/^/    /'
        die "the dist files are older than the file(s) above -- run ./build.sh build again"
    fi
}

# Whether the version is on PyPI: prints 'yes' (HTTP 200) or 'no' (HTTP 404),
# and dies on anything else -- a network failure must not read as "not there"
# and let an upload or a release go ahead on a guess.
on_pypi() {
    local status
    status=$("$CURL" -s -o /dev/null -w '%{http_code}' --max-time 20 \
                  "https://pypi.org/pypi/mdship/$1/json" || true)
    case "$status" in
        200) echo yes ;;
        404) echo no ;;
        *)   die "could not ask PyPI whether mdship $1 exists (HTTP ${status:-none})" ;;
    esac
}

publish_pypi() {
    local version
    version=$(current_version)
    [ -n "$version" ] || die "no version in pyproject.toml"

    require_clean_and_pushed
    require_release_notes "$version"
    require_fresh_dist "$version"

    # PyPI never accepts the same version twice, even after a delete.
    local published
    published=$(on_pypi "$version") || exit 1
    [ "$published" = no ] \
        || die "mdship $version is already on PyPI -- bump the version with ./build.sh version x.y.z"

    local token="${UV_PUBLISH_TOKEN:-}"
    if [ -z "$token" ]; then
        token=$(python3 -c "import configparser,os; c=configparser.ConfigParser(); c.read(os.path.expanduser('~/.pypirc')); print(c['pypi']['password'])" 2>/dev/null) \
            || die "no PyPI token: set UV_PUBLISH_TOKEN or add a [pypi] password to ~/.pypirc"
    fi

    info "Uploading mdship $version to PyPI"
    # The token goes in through the environment, not the command line, so it
    # never shows up in the process list.
    UV_PUBLISH_TOKEN="$token" uv publish \
        "dist/mdship-$version-py3-none-any.whl" "dist/mdship-$version.tar.gz"
    ok "mdship $version is on PyPI -- next: ./build.sh publish"
}

# Tags the release and creates it on GitHub. Separate from 'pypi' so that
# either step can be retried on its own when the other has already gone out.
publish_release() {
    local version tag
    version=$(current_version)
    [ -n "$version" ] || die "no version in pyproject.toml"
    tag="v$version"

    command -v gh >/dev/null 2>&1 || die "the GitHub CLI ('gh') is not installed"
    require_clean_and_pushed
    require_fresh_dist "$version"

    gh release view "$tag" >/dev/null 2>&1 && die "the $tag release already exists on GitHub"

    # A release on GitHub for a version pip cannot install would be a broken
    # promise; publish to PyPI first.
    local published
    published=$(on_pypi "$version") || exit 1
    [ "$published" = yes ] \
        || die "mdship $version is not on PyPI yet -- run ./build.sh pypi first"

    local head
    head=$(git rev-parse HEAD)
    if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
        [ "$(git rev-parse "$tag^{commit}")" = "$head" ] \
            || die "tag $tag exists but does not point at HEAD"
    fi

    local notes
    notes=$(mktemp -t mdship-notes)
    trap 'rm -f "$notes"; trap - RETURN' RETURN
    require_release_notes "$version"
    release_notes "$version" > "$notes"

    info "Creating the $tag release on GitHub"
    gh release create "$tag" \
        "dist/mdship-$version-py3-none-any.whl" "dist/mdship-$version.tar.gz" \
        --target "$head" --title "mdship $version" --notes-file "$notes"
    git fetch --quiet --tags
    ok "Released mdship $version"
}

case "${1:-build}" in
    -h|--help|help) show_help ;;
    build)   build ;;
    test)    run_tests ;;
    clean)
        info "Cleaning"
        rm -rf dist
        ok "Clean"
        ;;
    version) show_or_set_version "${2:-}" ;;
    notes)   release_notes "$(current_version)" ;;
    pypi)    publish_pypi ;;
    publish) publish_release ;;
    *)
        printf "unknown command '%s'\n\n" "$1" >&2
        show_help >&2
        exit 1
        ;;
esac
