import re
from enum import Enum
from collections import defaultdict
from .annotation import TextAnnotations, TextBoundAnnotationWithText, EventAnnotation, BinaryRelationAnnotation
from .standoffizer import Standoffizer

_header_re = re.compile(r"^#(?P<name>FORMAT|Sentence.id|T_(?:SP|RL|CH)|Text)=(?P<content>.*)$")
_slot_re = re.compile(r"^(?:ROLE_([\w.]+):(?:Roles|links)_([\w.]+)|BT_([\w.]+)|(.*))$")
_anno_id_pattern = r"\d+-\d+(?:\.\d+)?"
_anno_id_re = re.compile(r"^(\d+)-(\d+)(?:\.(\d+))?$")
_ent_re = re.compile(r"^(?:_|([^\]\[\s]+)(?:\[([\d]+)\])?)$")
_rel_re = re.compile(rf"^(?:_|({_anno_id_pattern})(?:\[([\d]+)_([\d]+)\])?)$")
_chr_re = re.compile(rf".*->({_anno_id_pattern})")
_sc_sep_re = re.compile(r"(?<!\\);")
_pipe_sep_re = re.compile(r"(?<!\\)\|")




def first_label_strategy(vals_slots, header):
    candidates = [
        val.label
        for val, slot in vals_slots
        if val.label is not None and val.label != "*"
    ]
    if candidates:
        return candidates[0]
    else:
        return vals_slots[0][1].label


class Slot:
    class Kind(Enum):
        FTR = 1  # Plain feature
        ARC = 2  # Arc
        ART = 3  # Arc target
        REL = 4  # Relation
        REN = 5  # Relation Name
        CHR = 6  # Chain target

    def __init__(self, kind, col_ix, name):
        self.kind = kind
        self.col_ix = col_ix
        self.name = name
        self.label = "_" + name.rsplit('.', 1)[-1]

    @staticmethod
    def parse(raw, col_ix, after_arc, header_kind):
        evt_source, evt_target, rel_source, val_name = _slot_re.match(raw).groups()
        kind = (
            (rel_source and Slot.Kind.REL) or
            (header_kind == Header.Kind.RL and Slot.Kind.REN) or
            (after_arc and Slot.Kind.ART) or
            (val_name == "referenceRelation" and Slot.Kind.CHR) or
            (evt_target and Slot.Kind.ARC) or
            Slot.Kind.FTR
        )
        name = evt_target or rel_source or val_name
        return Slot(kind, col_ix, name)

    def __repr__(self):
        return f"<{self.kind.name}#{self.col_ix}:{self.name}>"


class Header:
    class Kind(Enum):
        SP = 1
        CH = 2
        RL = 3

    def __init__(self, kind, klass, slots):
        self.kind = kind
        self.klass = klass
        self.slots = slots
        self.label = "__" + klass.rsplit(".", 1)[-1]

    @staticmethod
    def parse(raw_kind, raw_slots, column):
        klass, *parts = _pipe_sep_re.split(raw_slots)
        slots = []
        after_arc = False
        kind = Header.Kind[raw_kind[2:]]
        for slot_ix, part in enumerate(parts):
            slot = Slot.parse(part, slot_ix + column, after_arc, kind)
            if slot_ix and slots[-1].kind == Slot.Kind.ARC:
                slot.kind = Slot.Kind.ART
            slots.append(slot)
            after_arc = slot.kind == Slot.Kind.ARC

        if kind == Header.Kind.CH and slots[0].kind == Slot.Kind.CHR:
            slots.reverse()
        return Header(Header.Kind[raw_kind[2:]], klass, slots)


    def __repr__(self):
        return f"<{self.kind.name}:{self.klass} {self.slots}>"


class AnnoId:
    def __init__(self, sentence_id, token_id, part_id):
        self.sentence_id = sentence_id
        self.token_id = token_id
        self.part_id = part_id

    def parse(full_anno_id):
        sentence_id, token_id, part_id = [part and int(part) for part in _anno_id_re.match(full_anno_id).groups()]
        return AnnoId(sentence_id, token_id, part_id)

    @property
    def sent_tok_id(self):
        return f"{self.sentence_id}-{self.token_id}"

    def __repr__(self):
        value = self.sent_tok_id
        if self.part_id is not None:
            value += f".{self.part_id}"
        return value


class Value:
    @staticmethod
    def parse(raw, slot):
        value_type = _value_types[slot.kind]
        parts = _pipe_sep_re.split(raw)
        return [value_type.parse(part) for part in parts]


class FeatureValue(Value):
    def __init__(self, label, dis_id):
        self.label = label
        self.dis_id = dis_id

    @staticmethod
    def parse(raw):
        label, raw_dis_id = _ent_re.match(raw).groups()
        dis_id = raw_dis_id and int(raw_dis_id)
        return FeatureValue(label, dis_id)

    def __repr__(self):
        return f'"{self.label}[{self.dis_id}]"'


class ArcValue(Value):
    def __init__(self, arcs):
        self.arcs = arcs

    def parse(raw):
        # foo;bar[1]
        parts = _sc_sep_re.split(raw)
        return ArcValue(parts)

    def __repr__(self):
        return f'"{";".join(self.arcs)}"'


class ArcTargetsValue(Value):
    def __init__(self, ids):
        self.targets = ids

    def parse(raw):
        # 1-2[1] -> FV
        parts = _sc_sep_re.split(raw)
        result = []
        for part in parts:
            raw_tgt_id, raw_tgt_dis_id = _ent_re.match(part).groups()
            tgt_id = AnnoId.parse(raw_tgt_id)
            tgt_dis_id = raw_tgt_dis_id and int(raw_tgt_dis_id)
            result.append((tgt_id, tgt_dis_id))
        return ArcTargetsValue(result)

    def __repr__(self):
        return f'"{";".join(f"{anno_id}[{dis_id}]" for anno_id, dis_id in self.targets)}"'


class RelSourceValue(Value):
    def __init__(self, source_id, dis_id, tgt_dis_id):
        self.source_id = source_id
        self.dis_id = dis_id
        self.tgt_dis_id = tgt_dis_id

    def parse(raw):
        # bar[1] -> FV
        raw_source_id, raw_src_dis_id, raw_tgt_dis_id = _rel_re.match(raw).groups()
        source_id = AnnoId.parse(raw_source_id)
        src_dis_id = int(raw_src_dis_id or 0)
        tgt_dis_id = int(raw_tgt_dis_id or 0)
        return RelSourceValue(source_id, src_dis_id, tgt_dis_id)

    def __repr__(self):
        return f'"{self.source_id}[{self.dis_id}_{self.tgt_dis_id}]"'


class ChainTargetValue(Value):
    def __init__(self, tgt_dis_id):
        self.tgt_dis_id = tgt_dis_id

    def parse(raw):
        raw_tgt_dis_id, = _chr_re.match(raw).groups()
        tgt_dis_id = AnnoId.parse(raw_tgt_dis_id)
        return ChainTargetValue(tgt_dis_id)

    def __repr__(self):
        return f'"*->{self.tgt_dis_id}"'


_value_types = {
    Slot.Kind.FTR: FeatureValue,
    Slot.Kind.REN: FeatureValue,
    Slot.Kind.ARC: ArcValue,
    Slot.Kind.ART: ArcTargetsValue,
    Slot.Kind.REL: RelSourceValue,
    Slot.Kind.CHR: ChainTargetValue,
}


def overlaps(offsets, new_start, new_end):
    for start, end in offsets:
        if new_start < end and new_end > start:
            return True
    return False


def preparse(lines):
    headers = []
    annos = []
    text = ""

    header_ixs_by_klass = {}
    header_col = 0
    token_ix = -1
    current_text = ""

    for line in lines:
        line = line.rstrip("\n")
        if not line:
            continue

        header_match = _header_re.match(line)
        if header_match:
            header_name = header_match.group("name")
            header_content = header_match.group("content")
            if header_name == "FORMAT":
                pass
            elif header_name == "Sentence.id":
                pass
            elif header_name == "Text":
                current_text += header_content + "\n"
            else:
                header = Header.parse(header_name, header_content, header_col)
                header_col += len(header.slots)
                header_ixs_by_klass[header.klass] = len(headers)
                headers.append(header)
        else:
            raw_anno_id, standoff, surface, *columns = line.split("\t")
            anno_id = AnnoId.parse(raw_anno_id)
            start, end = (int(part) for part in standoff.split("-"))
            if current_text:
                gap = start - len(text) - current_text.index(surface)
                text += " " * gap + current_text
                current_text = ""
            if anno_id.part_id is None:
                token_ix += 1
            anno = [anno_id, token_ix, (start, end), surface, columns]
            annos.append(anno)

    for header in headers:
        for slot in header.slots:
            if slot.kind == Slot.Kind.ART:
                slot.art_header_ix = header_ixs_by_klass[slot.name]

    return headers, annos, text


def collect_data(headers, annos, label_strategy=first_label_strategy):
    dis_ids = {}
    dis_id_by_anno_id = {}
    evts = []
    rels = []
    chains = []
    num_new_dis = 0
    # TODO dis_ids_by_anno_id
    for header in headers:
        token = None

        for anno in annos:
            anno_id, token_ix, (start, end), surface, all_cols = anno

            if anno_id.part_id is None:
                token = (token_ix, start, end)

            cols = [all_cols[slot.col_ix] for slot in header.slots]
            num_blanks = sum(1 for col in cols if col == "_")
            if num_blanks == len(cols):
                continue

            vals = [Value.parse(col, slot) for col, slot in zip(cols, header.slots)]
            # transpose, so we have all features of one stacked annotation in each row
            stack = [list(x) for x in zip(*vals)]
            for values in stack:
                values_slots = defaultdict(list)
                for value, slot in zip(values, header.slots):
                    values_slots[slot.kind].append((value, slot))

                # SPAN
                ftrs_slots = values_slots[Slot.Kind.FTR]
                if ftrs_slots:
                    label = ftrs_slots and label_strategy(ftrs_slots, header) or header.label
                    new_dis_id = None

                    # only treat first FTR column's dis_id seriously
                    dis_id = ftrs_slots and ftrs_slots[0][0].dis_id
                    at_token_end = token[2] == end
                    if dis_id:
                        dis_id = int(dis_id)
                        existing = dis_ids.get(dis_id)
                        if existing:
                            # previous token, prev token end is prev ann end, token start is ann start; or, right next to it
                            if existing[0] == token_ix - 1 and existing[2] and token[1] == start or existing[1][-1][1] == start:
                                existing[1][-1][1] = end
                            # make sure it's not one of those weird situations where a subtoken is also marked...?
                            elif not overlaps(existing[1], start, end):
                                existing[1].append([start, end])
                            existing[0] = token_ix
                            existing[2] = at_token_end
                        else:
                            # make a new span
                            new_dis_id = dis_id
                    else:
                        num_new_dis += 1
                        new_dis_id = -num_new_dis

                    if new_dis_id:
                        # last token id, offsets, at token end, anno id, label
                        dis_ids[new_dis_id] = [token_ix, [[start, end]], at_token_end, anno_id, label]
                        dis_id = new_dis_id

                    # this is just for cases where we have a single one,
                    # so we don't need to keep a list
                    dis_id_by_anno_id[anno_id.sent_tok_id] = dis_id

                # EVENTS
                for (arc_value, arc_slot), (art_value, art_slot) in zip(values_slots[Slot.Kind.ARC], values_slots[Slot.Kind.ART]):
                    evts.append((anno_id, dis_id, arc_slot, arc_value, art_value))

                # RELATIONS
                for (ren_value, ren_slot), (rel_value, rel_slot) in zip(values_slots[Slot.Kind.REN], values_slots[Slot.Kind.REL]):
                    rels.append((anno_id, ren_value, ren_slot, rel_value))

                # CHAINS
                for value, slot in values_slots[Slot.Kind.CHR]:
                    chains.append((anno_id, value, slot))

    return dis_ids, dis_id_by_anno_id, evts, rels, chains


def make_textspans(dis_ids, dis_id_by_anno_id, evts, rels, chains, doc):
    entities = []
    triggers = {}
    triggers_by_offset_label = {}
    # [token_ix, [[start, end]], at_token_end, anno_id, label]
    for dis_id, (_, offsets, _, anno_id, label) in dis_ids.items():
        offsets = tuple(map(tuple, offsets))
        trigger_fingerprint = (offsets, label)
        if trigger_fingerprint in triggers_by_offset_label:
            triggers[dis_id] = triggers_by_offset_label[trigger_fingerprint]
        else:
            triggers_by_offset_label[trigger_fingerprint] = dis_id
            entity = (label, offsets, anno_id, dis_id)
            entities.append(entity)
    entities.sort(key=lambda entity: entity[1])

    entity_map = {}
    for label, offsets, anno_id, dis_id in entities:
        ann_id = doc.get_new_id("T")
        entity_map[dis_id] = ann_id
        TextBoundAnnotationWithText(offsets, ann_id, label, doc)

    for (anno_id, source_dis_id, arc_slot, arc_value, art_value) in evts:
        ann_id = doc.get_new_id("E")

        if not source_dis_id:
            source_dis_id = dis_id_by_anno_id[anno_id.sent_tok_id]
        source = entity_map[source_dis_id]
        args = []
        for arc, (target_anno_id, target_dis_id) in zip(arc_value.arcs, art_value.targets):
            if not target_dis_id:
                target_dis_id = dis_id_by_anno_id[target_anno_id.sent_tok_id]
            target = entity_map.get(target_dis_id) or entity_map[triggers[target_dis_id]]
            args.append((arc, target))
        label = arc_slot.label # TODO
        ann_id = doc.get_new_id("E")
        ann = EventAnnotation(source, args, ann_id, label, tail="")
        doc.add_annotation(ann)

    for (target_anno_id, ren_value, ren_slot, rel_value) in rels:
        source_dis_id = rel_value.dis_id
        target_dis_id = rel_value.tgt_dis_id
        source = entity_map.get(source_dis_id or dis_id_by_anno_id[rel_value.source_id.sent_tok_id])
        target = entity_map.get(target_dis_id or dis_id_by_anno_id[anno_id.sent_tok_id])
        label = ren_value.label or ren_slot.label
        ann_id = doc.get_new_id("R")
        ann = BinaryRelationAnnotation(ann_id, label, "Arg1", source, "Arg2", target, tail="")
        doc.add_annotation(ann)

    if chains:
        # TODO
        pass


def from_lines(lines, text=None, modifier=None):
    headers, annos, tsv_text = preparse(lines)

    if modifier is not None or text is not None:
        if modifier is None:
            modifier = lambda x: x
        if text is None:
            text = modifier(tsv_text)

        tokens = []
        for anno in annos:
            anno[3] = modifier(anno[3])
            tokens.append(anno[3])
        standoffizer = Standoffizer(text, tokens, skip=True)
        new_annos = []
        for anno, token, standoff in zip(annos, tokens, standoffizer):
            if standoff:
                anno[2] = standoff
                new_annos.append(anno)
        annos = new_annos
    else:
        text = tsv_text

    dis_ids, dis_id_by_anno_id, evts, rels, chains = collect_data(headers, annos or 0)
    doc = TextAnnotations(text=text)
    make_textspans(dis_ids, dis_id_by_anno_id, evts, rels, chains, doc)
    return doc



if __name__ == "__main__":
    import sys

    with open(sys.argv[1], "rt") as r:
        lines = r.readlines()
    if len(sys.argv) >= 3:
        with open(sys.argv[2], "rt") as r:
            text = r.read()
    else:
        text = None

    doc = from_lines(lines, text)
    print(doc, end="")
