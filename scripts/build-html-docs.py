#!/usr/bin/env python3
import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    (ROOT / "README.md", ROOT / "docs/html/index.html", "Koplyx"),
    (ROOT / "docs/TEST_RELEASE.md", ROOT / "docs/html/test-release.html", "Tester et publier Koplyx"),
    (ROOT / "docs/PUBLIC_RELEASE.md", ROOT / "docs/html/public-release.html", "Publication publique"),
]
LOGO_SOURCE = ROOT / "assets/icons/dev.limax.koplyx.svg"
LOGO_TARGET = ROOT / "docs/html/assets/dev.limax.koplyx.svg"


def inline(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def markdown_to_html(markdown: str) -> str:
    out: list[str] = []
    in_ul = False
    in_ol = False
    in_code = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                close_lists()
                out.append("<pre><code>")
                in_code = True
            continue

        if in_code:
            out.append(html.escape(line))
            continue

        if not line.strip():
            close_lists()
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            close_lists()
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            continue

        bullet = re.match(r"^-\s+(.+)$", line)
        if bullet:
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline(bullet.group(1))}</li>")
            continue

        numbered = re.match(r"^\d+\.\s+(.+)$", line)
        if numbered:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{inline(numbered.group(1))}</li>")
            continue

        close_lists()
        out.append(f"<p>{inline(line)}</p>")

    close_lists()
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="icon" href="assets/dev.limax.koplyx.svg" type="image/svg+xml">
  <style>
    :root {{
      color-scheme: dark;
      --bg: #111614;
      --surface: #171d1b;
      --text: #eef3ef;
      --muted: #8fa099;
      --accent: #73e6a2;
      --border: #2a3531;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 15px/1.6 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 860px;
      margin: 0 auto;
      padding: 42px 22px 64px;
    }}
    h1, h2, h3 {{
      color: #dff7ea;
      line-height: 1.2;
    }}
    a {{ color: var(--accent); }}
    code {{
      background: #202925;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 1px 5px;
    }}
    pre {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: auto;
      padding: 14px;
    }}
    pre code {{
      background: transparent;
      border: 0;
      padding: 0;
    }}
    li {{ margin: 5px 0; }}
    p, li {{ color: var(--text); }}
    header {{
      border-bottom: 1px solid var(--border);
      margin-bottom: 28px;
      padding-bottom: 12px;
    }}
    .nav {{
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 13px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 18px;
    }}
    .brand img {{
      width: 44px;
      height: 44px;
      border-radius: 10px;
    }}
    .brand span {{
      color: #dff7ea;
      font-size: 20px;
      font-weight: 800;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="brand">
        <img src="assets/dev.limax.koplyx.svg" alt="Logo Koplyx">
        <span>Koplyx</span>
      </div>
      <div class="nav">
        <a href="index.html">README</a>
        <a href="test-release.html">Tests</a>
        <a href="public-release.html">Publication</a>
      </div>
    </header>
    {body}
  </main>
</body>
</html>
"""


def main() -> int:
    LOGO_TARGET.parent.mkdir(parents=True, exist_ok=True)
    LOGO_TARGET.write_text(LOGO_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"wrote {LOGO_TARGET.relative_to(ROOT)}")
    for source, target, title in SOURCES:
        target.parent.mkdir(parents=True, exist_ok=True)
        body = markdown_to_html(source.read_text(encoding="utf-8"))
        target.write_text(page(title, body), encoding="utf-8")
        print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
