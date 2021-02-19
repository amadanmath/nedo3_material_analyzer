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
