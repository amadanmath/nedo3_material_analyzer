from brat.annotation import TextAnnotations, TextBoundAnnotationWithText
from brat.simplesplit import find_sentence_standoffs, find_token_standoffs
import re
from time import sleep



visual_conf = """
[labels]
Word | Word
[drawing]
SPAN_DEFAULT\tfgColor:black, bgColor:lightgreen, borderColor:darken
"""



def setup():
    # prepare classifiers etc
    pass


def process(text):
    doc = TextAnnotations(text=text)

    # find words of at least 4 characters
    word_re = re.compile(r'\w{4,}')
    for start, stop in find_token_standoffs(text, word_re):
        id = doc.get_new_id("T")
        # add annotation
        TextBoundAnnotationWithText([[start, stop]], id, "Word", doc)

    # return visual configuration as a string
    # and a TextAnnotations object
    sleep(1)
    return (visual_conf, doc)
