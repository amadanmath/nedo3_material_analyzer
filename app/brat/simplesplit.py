import re
from brat.ssplit import regex_sentence_boundary_gen



# just in case
class Standoffizer:
    def __init__(self, text, subs, start=0):
        self.text = text
        self.subs = subs
        self.start = start

    def __iter__(self):
        offset = 0
        for sub in self.subs:
            pos = self.text.index(sub, offset)
            offset = pos + len(sub)
            yield (self.start + pos, self.start + offset)


def find_sentence_standoffs(text):
    return list(regex_sentence_boundary_gen(text))


NONSPACE_RE = re.compile(r'\S+')
def find_token_standoffs(text, pattern=NONSPACE_RE):
    # simple whitespace tokenizer is good enough as default
    return [
        (match.start(), match.end())
        for match in pattern.finditer(text)
    ]
