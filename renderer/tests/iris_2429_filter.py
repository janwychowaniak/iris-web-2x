# The configuration of IRIS 2.4.29's filter for `html` attribute fields, copied verbatim from
# source/app/__init__.py at tag v2.4.29 (lines 93-103), where _sanitize_attribute_html applies it
# with bleach.clean(..., strip=True). CI checks that the block below still equals the image's.

_ATTR_HTML_ALLOWED_TAGS = [
    'a', 'abbr', 'b', 'blockquote', 'br', 'code', 'div', 'em', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 'span', 'strong',
    'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul',
]
_ATTR_HTML_ALLOWED_ATTRS = {
    '*': ['class', 'title'],
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
}
_ATTR_HTML_ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']
