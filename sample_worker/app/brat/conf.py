import re


def _parse_attrs(maybe_attribute_text, labels):
    if maybe_attribute_text:
        attributes = dict(item.strip().split(':') for item in maybe_attribute_text[0].split(','))
    else:
        attributes = {}
    attributes['labels'] = labels
    return attributes


def parse_visual_conf_file(filename):
    """
    Reads simple brat visual configuration files.
    Just simple ones. No macros, defaults...
    """

    with open(filename, "rt") as r:
        text = r.read()
    return parse_visual_conf(text)


_SECTION_RE = re.compile(r'^\s*\[(.*?)\]', flags=re.MULTILINE)
def parse_visual_conf(text):
    """
    Reads simple brat visual configuration files.
    Just simple ones. No macros, defaults...
    """

    it = iter(_SECTION_RE.split(text))
    next(it)

    sections = dict((key, [
            line for line in
                (line.strip() for line in text.strip().split("\n"))
            if line and not line.startswith('#')
        ]) for key, text in zip(it, it))
    labels = {
        name.strip(): [label.strip() for label in labels]
        for name, *labels
        in (line.split('|') for line in sections.get('labels', []))
    }
    attributes = {
        name: _parse_attrs(maybe_attributes, labels.get(name))
        for name, *maybe_attributes
        in (line.split('\t', 2) for line in sections.get('drawing', []))
    }
    return attributes


_NUMBERLESS_RE = re.compile(r'(.*?)\d*$')
def _numberless(type):
    match = _NUMBERLESS_RE.match(type)
    return match.group(1)


def _add_default_class(visual_conf, types, defaults):
    return {
        type: {
            **defaults,
            **visual_conf.get(type, {})
        } for type in types
    }


def add_defaults(visual_conf, doc):
    span_types = {
        ann.type for ann
        in [*doc.get_textbounds(), *doc.get_relations()]
    }
    arc_types = {
        _numberless(type)
        for ann in doc.get_events()
        for type, id in ann.args
    } | {
        ann.type for ann in doc.get_equivs()
    }
    span_default = visual_conf.get("SPAN_DEFAULT", {})
    arc_default = visual_conf.get("ARC_DEFAULT", {})
    return {
        **_add_default_class(visual_conf, span_types, span_default),
        **_add_default_class(visual_conf, arc_types, arc_default),
    }


if __name__ == "__main__":
    visual_conf = parse_visual_conf("data/visual.conf")
    print(visual_conf)
