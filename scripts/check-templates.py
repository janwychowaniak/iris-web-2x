"""Render IRIS's attribute tab buttons and panes, and resolve each button's target as
Bootstrap 4.6.2 does (SPEC §4.3). Runs inside a container of an image, from /iriswebapp,
with the image's own Jinja2 and lxml:

    python - [--html] < scripts/check-templates.py

It prints, as JSON, per template and tab name: the button's target, the pane it resolves
to, the pane it should open, and the button's attributes. check-image.py runs it on the
built image, where every button must open its pane, and on the stock image as the control,
where the resolver must reject what a browser rejects. With --html it prints the rendered
modals instead, for a page that loads them with IRIS's own jQuery and Bootstrap.

Bootstrap 4.6.2 takes the target from data-target, else from href, and opens nothing when
document.querySelector(target) throws or finds nothing. The resolver accepts the two forms
these templates produce, and nothing else: "#" followed by exactly one CSS identifier, and
[id="..."] with a CSS string. Anything else is a selector it does not resolve.
"""
import json
import re
import sys

import jinja2
import lxml.html

NAMES = ["VT Report", "1 leading digit", "Zażółć gęślą jaźń", 'Say "hi"', "Report (beta)",
         "v1.2", "back\\slash", "a'quote", "x:y", "line\nbreak"]
TEMPLATES = {
    "shared nav": ("modals/modal_attributes_nav.html", False, False),
    "case info": ("modal_case_info_from_case.html", True, False),
    "new case": ("modal_add_case.html", True, True),
}  # name: (template, render only its loop over the attributes, panes as on the case page)

env = jinja2.Environment(loader=jinja2.FileSystemLoader(
    ["app/templates", "app/blueprints/manage/templates"]), autoescape=True)
class _StandIns(dict):
    """Every filter or test name resolves: IRIS and Flask register theirs across the app,
    and none of them takes part in what is rendered here. A whole template then compiles
    when its syntax holds, whatever filters it names."""

    def __missing__(self, name):
        return lambda value=None, *args, **kwargs: value

    def get(self, name, default=None):
        return self[name]

    def __contains__(self, name):
        return True


env.filters = _StandIns(env.filters)
env.tests = _StandIns(env.tests)
ATTRIBUTES = {n: {"f": {"type": "input_string", "value": "x", "mandatory": False}} for n in NAMES}


def buttons_html(template, loop_only):
    if not loop_only:
        return env.get_template(template).render(attributes=ATTRIBUTES)
    source = env.loader.get_source(env, template)[0]
    loops = [body for body in re.findall(r"\{% for ca in attributes %\}(.*?)\{% endfor %\}", source, re.S)
             if "data-toggle" in body]
    assert len(loops) == 1, (template, len(loops))
    return env.from_string("{% for ca in attributes %}" + loops[0] + "{% endfor %}").render(attributes=ATTRIBUTES)


def panes_html(case_page):
    return env.get_template("modals/modal_attributes_tabs.html").render(
        attributes=ATTRIBUTES, is_case_page=case_page)


# --- CSS, as far as these selectors need it (CSS Syntax Level 3, §4.3) -----------------
HEX = re.compile(r"[0-9a-fA-F]{1,6}")


def _escape(s, i):
    """The code point of the escape at s[i] == "\\", and the index after it; None if invalid."""
    if i + 1 >= len(s) or s[i + 1] == "\n":
        return None
    m = HEX.match(s, i + 1)
    if m:
        cp, j = int(m.group(), 16), m.end()
        if j < len(s) and s[j] in " \t\n":
            j += 1
        return ("�" if cp == 0 or cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF else chr(cp)), j
    return s[i + 1], i + 2


def _name_char(c, start):
    return c == "_" or c.isascii() and c.isalpha() or not c.isascii() or not start and (c.isdigit() or c == "-")


def identifier(s):
    """s as one CSS identifier, or None when it is not exactly one."""
    if not s:
        return None
    out, i = [], 0
    if s[0] == "-":  # "-" starts an identifier when "-", a name-start character or an escape follows
        if len(s) < 2 or not (s[1] == "-" or _name_char(s[1], True) or s[1] == "\\" and _escape(s, 1)):
            return None
        out.append("-")
        i = 1
    first = True
    while i < len(s):
        c = s[i]
        if c == "\\":
            e = _escape(s, i)
            if e is None:
                return None
            out.append(e[0])
            i = e[1]
        elif _name_char(c, first and not out):
            out.append(c)
            i += 1
        else:
            return None
        first = False
    return "".join(out)


def css_string(body, quote):
    """The value of a CSS string's body, or None when the string is not valid."""
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c == quote or c == "\n":
            return None
        if c == "\\":
            if i + 1 < len(body) and body[i + 1] == "\n":
                i += 2
                continue
            e = _escape(body, i)
            if e is None:
                return None
            out.append(e[0])
            i = e[1]
        else:
            out.append(c)
            i += 1
    return "".join(out)


def resolve(selector, ids):
    """The id of the element document.querySelector(selector) would find, or None."""
    if selector.startswith("#"):
        name = identifier(selector[1:])
    else:
        m = re.fullmatch(r"\[id=([\"'])(.*)\1\]", selector, re.S)
        name = css_string(m.group(2), m.group(1)) if m else None
    return name if name is not None and name in ids else None


def elements(html, tag):
    """Every element with this tag in an HTML fragment, in document order."""
    for frag in lxml.html.fragments_fromstring(html):
        if not isinstance(frag, str):
            yield from frag.iter(tag)


def check():
    results = {}
    for label, (template, loop_only, case_page) in TEMPLATES.items():
        env.get_template(template)  # the whole template compiles, not only the part rendered here
        buttons = [a for a in elements(buttons_html(template, loop_only), "a")
                   if a.get("data-toggle") in ("pill", "tab") and a.get("href") != "#details"]
        panes = [d.get("id") for d in elements(panes_html(case_page), "div")
                 if "tab-pane" in (d.get("class") or "").split()]
        assert len(buttons) == len(NAMES) == len(panes), (label, len(buttons), len(panes))
        rows = []
        for name, a, pane in zip(NAMES, buttons, panes):
            target = a.get("data-target")
            if not target or target == "#":
                target = (a.get("href") or "").strip()
            rows.append({"name": name, "target": target, "resolves": resolve(target, set(panes)),
                         "pane": pane,
                         "button": {k: v for k, v in sorted(a.attrib.items()) if k != "data-target"},
                         "text": a.text_content()})
        results[label] = rows
    return results


if __name__ == "__main__":
    if "--html" in sys.argv:
        for label, (template, loop_only, case_page) in TEMPLATES.items():
            print('<section data-template="%s"><ul class="nav">%s</ul><div class="tab-content">%s</div></section>'
                  % (label, buttons_html(template, loop_only), panes_html(case_page)))
    else:
        json.dump(check(), sys.stdout, ensure_ascii=False)
