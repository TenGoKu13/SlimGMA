"""Génération du rapport HTML autonome (fonctions pures)."""


def build_html_report(report: dict) -> str:
    """Construit un rapport HTML autonome (thème clair/sombre) à partir d'un
    dict `report` déjà traduit. Fonction pure et testable."""
    import html as _html

    def esc(s) -> str:
        return _html.escape(str(s))

    title = report.get('title', 'Rapport')
    subtitle = report.get('subtitle', '')
    s = report.get('summary', {})
    parts: list[str] = []

    # Cartes de synthèse
    cards = [
        (report['labels']['original'], s.get('original', '—')),
        (report['labels']['final'],    s.get('final', '—')),
        (report['labels']['saved'],    s.get('reduction', '—')),
        (report['labels']['files'],    s.get('files', '—')),
    ]
    cards_html = ''.join(
        f'<div class="card"><div class="k">{esc(k)}</div>'
        f'<div class="v">{esc(v)}</div></div>' for k, v in cards)
    parts.append(f'<div class="cards">{cards_html}</div>')

    # Rôles des textures
    roles = report.get('roles', [])
    if roles:
        blocks = []
        for label, items in roles:
            lis = ''.join(f'<li>{esc(p)}</li>' for p in items)
            blocks.append(
                f'<details open><summary>{esc(label)} '
                f'<span class="badge">{len(items)}</span></summary>'
                f'<ul class="files">{lis}</ul></details>')
        parts.append(_section(report['labels']['sec_roles'], ''.join(blocks)))

    # Orphelins
    orphans = report.get('orphans', [])
    if orphans:
        badge = report['labels']['removed'] if report.get('removed') else report['labels']['kept']
        lis = ''.join(f'<li>{esc(p)}</li>' for p in orphans)
        body = (f'<p class="tag {"del" if report.get("removed") else "keep"}">'
                f'{esc(badge)}</p><ul class="files">{lis}</ul>')
        parts.append(_section(report['labels']['sec_orphans'], body))

    # Doublons
    dups = report.get('duplicates', [])
    if dups:
        blocks = []
        for group in dups:
            lis = ''.join(f'<li>{esc(p)}</li>' for p in group)
            blocks.append(f'<details><summary>{len(group)}×</summary>'
                          f'<ul class="files">{lis}</ul></details>')
        parts.append(_section(report['labels']['sec_dups'], ''.join(blocks)))

    # Audit
    audit = report.get('audit', [])
    if audit:
        rows = ''.join(
            f'<tr><td>{esc(a["path"])}</td><td>{esc(a["label"])}</td>'
            f'<td>{esc(a["detail"])}</td></tr>' for a in audit)
        lbl = report['labels']
        table = (f'<table><thead><tr><th>{esc(lbl["col_texture"])}</th>'
                 f'<th>{esc(lbl["col_issue"])}</th>'
                 f'<th>{esc(lbl["col_detail"])}</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table>')
        parts.append(_section(lbl['sec_audit'], table))

    body = '\n'.join(parts) or f'<p>{esc(report["labels"]["empty"])}</p>'
    return _HTML_TEMPLATE.format(
        title=esc(title), subtitle=esc(subtitle), body=body)


def _section(title: str, inner: str) -> str:
    import html as _html
    return (f'<section><h2>{_html.escape(title)}</h2>{inner}</section>')


_HTML_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --bg:#f4f6fb; --fg:#1b2430; --sub:#5b6675; --card:#ffffff;
    --accent:#3b82f6; --border:#e2e8f0; --del:#ef4444; --keep:#10b981;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#0f141b; --fg:#e6edf3; --sub:#93a1b0; --card:#161d26;
      --accent:#60a5fa; --border:#26313d; --del:#f87171; --keep:#34d399;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:32px; background:var(--bg); color:var(--fg);
    font-family:'Segoe UI',system-ui,sans-serif; line-height:1.5; }}
  header {{ margin-bottom:24px; }}
  h1 {{ margin:0; font-size:22px; }}
  .sub {{ color:var(--sub); font-size:14px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
    gap:12px; margin-bottom:28px; }}
  .card {{ background:var(--card); border:1px solid var(--border);
    border-radius:12px; padding:14px 16px; }}
  .card .k {{ color:var(--sub); font-size:12px; text-transform:uppercase;
    letter-spacing:.04em; }}
  .card .v {{ font-size:22px; font-weight:700; margin-top:4px; }}
  section {{ background:var(--card); border:1px solid var(--border);
    border-radius:12px; padding:16px 20px; margin-bottom:18px; }}
  h2 {{ margin:0 0 12px; font-size:16px; border-left:3px solid var(--accent);
    padding-left:10px; }}
  details {{ margin:6px 0; }}
  summary {{ cursor:pointer; font-weight:600; }}
  .badge {{ background:var(--accent); color:#fff; border-radius:10px;
    padding:1px 8px; font-size:12px; margin-left:6px; }}
  ul.files {{ margin:8px 0 8px 4px; padding-left:18px; }}
  ul.files li {{ font-family:ui-monospace,monospace; font-size:12.5px;
    color:var(--sub); word-break:break-all; }}
  .tag {{ display:inline-block; padding:2px 10px; border-radius:8px;
    font-size:12px; font-weight:700; }}
  .tag.del {{ background:var(--del); color:#fff; }}
  .tag.keep {{ background:var(--keep); color:#04231a; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ text-align:left; padding:7px 8px; border-bottom:1px solid var(--border);
    word-break:break-all; }}
  th {{ color:var(--sub); font-weight:600; }}
</style>
</head>
<body>
  <header><h1>{title}</h1><div class="sub">{subtitle}</div></header>
  {body}
</body>
</html>
"""
