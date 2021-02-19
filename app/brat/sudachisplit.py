from sudachipy import tokenizer
from sudachipy import dictionary

from .standoffizer import Standoffizer


tokenizer_obj = dictionary.Dictionary().create()
mode = tokenizer.Tokenizer.SplitMode.C


def find_token_standoffs(text):
    morphemes = tokenizer_obj.tokenize(text, mode)
    subs = [m.surface() for m in morphemes]
    subs = [s for s in subs if not all(c.isspace() for c in s)]
    return list(Standoffizer(text, subs))
