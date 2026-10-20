"""Routing matcher library shared (by vectors) with the pi skill-router extension.

Stdlib only. Behaviour is pinned by skill-creator/references/routing-vectors.json.
"""

import re

# --------------------------------------------------------------------------
# Frontmatter
# --------------------------------------------------------------------------

_KEY_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*):(?:\s+(.*)|\s*)$")
_BLOCK_RE = re.compile(r"^([>|])([+-]?)$")


def _scalar(raw):
    v = raw.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return re.sub(r'\\(["\\])', r"\1", v[1:-1])
    if len(v) >= 2 and v[0] == "'" and v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def _indent(line):
    return len(line) - len(line.lstrip(" \t"))


def parse_frontmatter(text):
    """Parse the leading ``---`` frontmatter block into a dict.

    Problems are reported in ``result["errors"]`` (only present if non-empty).
    """
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end = idx
            break
    if end is None:
        return {}
    body = lines[1:end]
    result = {}
    errors = []
    i = 0
    while i < len(body):
        line = body[i]
        if not line.strip() or line.lstrip().startswith("#") or _indent(line) > 0:
            i += 1
            continue
        m = _KEY_RE.match(line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), (m.group(2) or "").strip()
        i += 1
        # collect indented/blank continuation lines
        block = []
        while i < len(body) and (not body[i].strip() or _indent(body[i]) > 0):
            block.append(body[i])
            i += 1
        while block and not block[-1].strip():
            block.pop()
        bm = _BLOCK_RE.match(val)
        if bm:
            style, chomp = bm.groups()
            items = [b.strip() for b in block]
            if style == ">":
                paras, cur = [], []
                for it in items:
                    if it:
                        cur.append(it)
                    elif cur:
                        paras.append(" ".join(cur))
                        cur = []
                if cur:
                    paras.append(" ".join(cur))
                out = "\n".join(paras)
            else:
                out = "\n".join(items)
            result[key] = out if chomp == "-" else out + "\n"
        elif key == "metadata" and not val:
            meta = {}
            base = None
            for b in block:
                if not b.strip() or b.lstrip().startswith("#"):
                    continue
                ind = _indent(b)
                if base is None:
                    base = ind
                s = b.strip()
                if ind > base or s.startswith("- "):
                    errors.append(f"metadata: unsupported nested value: {s!r}")
                    continue
                km = _KEY_RE.match(s)
                if not km:
                    errors.append(f"metadata: cannot parse line: {s!r}")
                    continue
                mk, mv = km.group(1), (km.group(2) or "").strip()
                if not mv or mv[0] in "[{" or _BLOCK_RE.match(mv):
                    errors.append(f"metadata.{mk}: value must be a string")
                    continue
                meta[mk] = _scalar(mv)
            result[key] = meta
        elif not val:
            result[key] = ""
        elif key == "disable-model-invocation":
            low = val.lower()
            if low in ("true", "false"):
                result[key] = low == "true"
            else:
                errors.append(f"{key}: expected true or false")
        else:
            result[key] = _scalar(val)
    if errors:
        result["errors"] = errors
    return result


# --------------------------------------------------------------------------
# Keywords (route-prompt)
# --------------------------------------------------------------------------


def _word_regex(word, wildcard, hyphen):
    parts = []
    for ch in word:
        if ch == "*":
            parts.append(wildcard)
        elif ch == "-":
            parts.append(hyphen)
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def _split_spec(spec, what):
    if not isinstance(spec, str) or not spec.split():
        raise ValueError(f"empty {what} spec")
    return spec.split()


def compile_keywords(spec):
    words = _split_spec(spec, "keyword")
    pats = []
    for w in words:
        if not w.strip("*-"):
            raise ValueError(f"invalid keyword: {w!r}")
        pre = r"(?<![\w-])" if (w[0].isalnum() or w[0] in "_*") else ""
        post = r"(?![\w-])" if (w[-1].isalnum() or w[-1] in "_*") else ""
        pats.append(pre + _word_regex(w, ".*", "[- ]") + post)
    return re.compile("|".join(f"(?:{p})" for p in pats), re.IGNORECASE | re.DOTALL)


def match_prompt(matcher, text):
    return matcher.search(text) is not None


# --------------------------------------------------------------------------
# Command position (route-commands)
# --------------------------------------------------------------------------


class CommandMatcher:
    def __init__(self, regexes):
        self.regexes = regexes


def compile_commands(spec):
    words = _split_spec(spec, "command")
    regexes = []
    for w in words:
        if not w.strip("*-"):
            raise ValueError(f"invalid command keyword: {w!r}")
        regexes.append(
            re.compile(
                r"^" + _word_regex(w, ".*", r"[-\s]") + r"(?:\s|$)",
                re.IGNORECASE | re.DOTALL,
            )
        )
    return CommandMatcher(regexes)


_HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?", re.ASCII)


def strip_shell_non_commands(cmd):
    result = cmd
    heredocs = []
    for hm in _HEREDOC_RE.finditer(result):
        delim = hm.group(1)
        nl = result.find("\n", hm.end())
        if nl == -1:
            continue
        em = re.compile(r"^" + delim + r"\s*$", re.M).search(result[nl + 1 :])
        if not em:
            continue
        heredocs.append((nl, nl + 1 + em.start() + len(em.group(0))))
    for start, end in reversed(heredocs):
        result = result[:start] + result[end:]

    out = []
    i = 0
    n = len(result)
    while i < n:
        ch = result[i]
        if ch == "$" and i + 1 < n and result[i + 1] == "'":
            j = i + 2
            while j < n:
                if result[j] == "\\":
                    j += 2
                    continue
                if result[j] == "'":
                    break
                j += 1
            i = j + 1
            continue
        if ch == "'":
            end = result.find("'", i + 1)
            if end == -1:
                i += 1
                continue
            i = end + 1
            continue
        if ch == '"':
            j = i + 1
            while j < n:
                if result[j] == "\\":
                    j += 2
                    continue
                if result[j] == '"':
                    break
                j += 1
            i = j + 1
            continue
        if ch == "#":
            eol = result.find("\n", i)
            if eol == -1:
                break
            i = eol
            continue
        out.append(ch)
        i += 1
    return "".join(out)


_SPLIT_RE = re.compile(r"[;\n]|&&|\|\||\|")
_ASSIGN_RE = re.compile(r"^\w+=\S*\s+", re.ASCII)
_WRAP_RE = re.compile(r"^(?:sudo|env|command|exec)\s+")


def _segments(cmd):
    stripped = strip_shell_non_commands(cmd)
    for seg in _SPLIT_RE.split(stripped):
        for sub in seg.split("("):
            yield sub.strip()


def _strip_prefixes(s):
    while _ASSIGN_RE.match(s):
        s = _ASSIGN_RE.sub("", s, count=1)
    while _WRAP_RE.match(s):
        s = _WRAP_RE.sub("", s, count=1)
    return s


def match_command(matcher, command):
    for seg in _segments(command):
        s = _strip_prefixes(seg)
        if any(r.search(s) for r in matcher.regexes):
            return True
    return False


_SHORT_OPT = re.compile(r"^-[CcP]\s+\S+\s*")
_LONG_EQ = re.compile(r"^--[a-z][a-z0-9-]+=\S*\s*")
_LONG_SEP = re.compile(r"^--(?:git-dir|work-tree|exec-path|namespace)\s+\S+\s*")
_LONG_BOOL = re.compile(
    r"^--(?:no-pager|bare|paginate|no-replace-objects|literal-pathspecs"
    r"|glob-pathspecs|noglob-pathspecs|no-optional-locks)\s*"
)


def _segment_is_git_commit(seg):
    s = _strip_prefixes(seg)
    if not s.startswith("git") or (len(s) > 3 and re.match(r"\w", s[3], re.ASCII)):
        return False
    rest = s[3:].lstrip()
    while rest:
        for rx in (_SHORT_OPT, _LONG_EQ, _LONG_SEP, _LONG_BOOL):
            m = rx.match(rest)
            if m:
                rest = rest[m.end() :].lstrip()
                break
        else:
            if rest.startswith("-P") and (len(rest) == 2 or rest[2].isspace()):
                rest = rest[2:].lstrip()
                continue
            break
    m = re.match(r"^(\S+)", rest)
    return m is not None and m.group(1) == "commit"


def is_real_git_commit(cmd):
    return any(_segment_is_git_commit(s) for s in _segments(cmd))


# --------------------------------------------------------------------------
# Globs (route-paths)
# --------------------------------------------------------------------------


def _glob_to_regex(glob):
    out = []
    i, n = 0, len(glob)
    while i < n:
        ch = glob[i]
        if ch == "*":
            if glob.startswith("**/", i):
                out.append("(?:.*/)?")
                i += 3
            elif glob.startswith("**", i):
                out.append(".*")
                i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        elif ch == "[":
            j = i + 1
            if j < n and glob[j] in "!^":
                j += 1
            if j < n and glob[j] == "]":
                j += 1
            while j < n and glob[j] != "]":
                j += 1
            if j >= n:
                out.append(re.escape(ch))
                i += 1
            else:
                inner = glob[i + 1 : j]
                neg = inner[:1] in ("!", "^")
                if neg:
                    inner = inner[1:]
                inner = inner.replace("\\", "\\\\")
                if inner.startswith("]"):
                    inner = "\\" + inner
                inner = inner.replace("[", "\\[")
                out.append("[" + ("^" if neg else "") + inner + "]")
                i = j + 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("^" + "".join(out) + "$", re.DOTALL)


def compile_globs(spec):
    return [_glob_to_regex(g) for g in _split_spec(spec, "glob")]


def match_path(matcher, path, root=None):
    if root:
        prefix = root.rstrip("/") + "/"
        if path.startswith(prefix):
            rel = path[len(prefix) :]
            return any(r.match(rel) for r in matcher)
    candidates = [path]
    for idx, ch in enumerate(path):
        if ch == "/":
            candidates.append(path[idx + 1 :])
    return any(r.match(c) for r in matcher for c in candidates)
