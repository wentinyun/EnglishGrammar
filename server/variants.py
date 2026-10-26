"""确定性变式题库：题面由模板拼出，答案由模板**算**出来。

三条硬约束
----------
1. 答案不是「选」出来的，是推导出来的。所以判分仍然走 grade.py 的精确匹配，
   不会因为学生写了另一种合法写法而被误判（模板只产生唯一正确形式）。
2. 变化来自槽位组合（主语 × 动词 × 宾语 × 时间标志），不是随机噪声。
   同一个知识点可以出几百道互不相同的题，但规则始终是同一条。
3. 生成结果只留在会话状态与 gen_drill 表里，不写回 content/，
   固定题库仍然是主干，变式只做补充。
"""
from __future__ import annotations

import hashlib
import random

# ------------------------------------------------------------------ 基础工具


def _rng(*parts) -> random.Random:
    raw = "::".join(str(p) for p in parts).encode("utf-8")
    return random.Random(int(hashlib.sha256(raw).hexdigest()[:16], 16))


def _choice(rng: random.Random, stem: str, answer: str, wrongs, explain: str,
            trap: str = "", diff: int = 2) -> dict:
    uniq: list[str] = []
    seen = {answer.strip().lower()}
    for w in wrongs:
        w = (w or "").strip()
        if not w or w.lower() in seen:
            continue
        seen.add(w.lower())
        uniq.append(w)
        if len(uniq) == 3:
            break
    if len(uniq) < 3:
        raise ValueError(f"干扰项不足：{stem}")
    opts = uniq + [answer]
    rng.shuffle(opts)
    return {"type": "choice", "stem": stem, "options": opts, "answer": answer,
            "explain": explain, "trap": trap, "difficulty": diff}


def _fill(stem: str, answer: str, explain: str, accept=None,
          diff: int = 2, hint: str = "") -> dict:
    acc: list[str] = []
    for a in (accept or [answer]):
        if a and a not in acc:
            acc.append(a)
    d = {"type": "fill", "stem": stem, "answer": answer,
         "accept": acc, "explain": explain, "difficulty": diff}
    if hint:
        d["hint"] = hint
    return d


# ------------------------------------------------------------------ 词表

# 动词五形：原形 / 三单 / 过去式 / 过去分词 / 现在分词
VERBS: dict[str, tuple[str, str, str, str]] = {
    "have": ("has", "had", "had", "having"),
    "work": ("works", "worked", "worked", "working"),
    "study": ("studies", "studied", "studied", "studying"),
    "live": ("lives", "lived", "lived", "living"),
    "play": ("plays", "played", "played", "playing"),
    "finish": ("finishes", "finished", "finished", "finishing"),
    "watch": ("watches", "watched", "watched", "watching"),
    "clean": ("cleans", "cleaned", "cleaned", "cleaning"),
    "visit": ("visits", "visited", "visited", "visiting"),
    "write": ("writes", "wrote", "written", "writing"),
    "make": ("makes", "made", "made", "making"),
    "buy": ("buys", "bought", "bought", "buying"),
    "bring": ("brings", "brought", "brought", "bringing"),
    "take": ("takes", "took", "taken", "taking"),
    "give": ("gives", "gave", "given", "giving"),
    "see": ("sees", "saw", "seen", "seeing"),
    "eat": ("eats", "ate", "eaten", "eating"),
    "speak": ("speaks", "spoke", "spoken", "speaking"),
    "break": ("breaks", "broke", "broken", "breaking"),
    "choose": ("chooses", "chose", "chosen", "choosing"),
    "forget": ("forgets", "forgot", "forgotten", "forgetting"),
    "begin": ("begins", "began", "begun", "beginning"),
    "teach": ("teaches", "taught", "taught", "teaching"),
    "catch": ("catches", "caught", "caught", "catching"),
    "build": ("builds", "built", "built", "building"),
    "send": ("sends", "sent", "sent", "sending"),
    "lose": ("loses", "lost", "lost", "losing"),
    "find": ("finds", "found", "found", "finding"),
    "leave": ("leaves", "left", "left", "leaving"),
    "meet": ("meets", "met", "met", "meeting"),
    "pay": ("pays", "paid", "paid", "paying"),
    "sell": ("sells", "sold", "sold", "selling"),
    "tell": ("tells", "told", "told", "telling"),
    "think": ("thinks", "thought", "thought", "thinking"),
    "repair": ("repairs", "repaired", "repaired", "repairing"),
    "plant": ("plants", "planted", "planted", "planting"),
    "deliver": ("delivers", "delivered", "delivered", "delivering"),
    "borrow": ("borrows", "borrowed", "borrowed", "borrowing"),
    "invite": ("invites", "invited", "invited", "inviting"),
}

# 主语池：布尔值表示第三人称单数
SUBJ = [
    ("He", True), ("She", True), ("Tom", True), ("My brother", True),
    ("The manager", True), ("Lucy", True),
    ("They", False), ("We", False), ("The students", False),
    ("My parents", False), ("Tom and I", False),
]

TENSE_LABEL = {
    "pres": "一般现在时", "past": "一般过去时", "perf": "现在完成时",
    "cont": "现在进行时", "fut": "一般将来时", "pastcont": "过去进行时",
    "futcont": "将来进行时", "perfcont": "现在完成进行时",
    "pastperf": "过去完成时", "futperf": "将来完成时",
}

# 各时态的收尾时间状语（放句末自然）
SIGNALS = {
    "pres": ["every day", "on Sundays", "twice a week"],
    "past": ["yesterday", "last week", "two days ago"],
    "perf": ["already", "so far", "up to now"],
    "cont": ["right now", "at the moment"],
    "fut": ["tomorrow", "next week", "in two days"],
    "pastcont": ["at eight last night", "at that moment"],
    "futcont": ["this time tomorrow", "at nine tomorrow"],
}

# 只用于时态题的「动词 + 宾语」组合，保证任何时态下都成立
TENSE_VERBS = [
    ("finish", ["the report", "the letter", "the task", "the survey"]),
    ("clean", ["the room", "the windows", "the kitchen", "the office"]),
    ("repair", ["the car", "the bike", "the computer", "the printer"]),
    ("deliver", ["the parcel", "the flowers", "the furniture"]),
    ("write", ["the email", "the article", "the summary", "the review"]),
    ("buy", ["the tickets", "the groceries", "a new laptop"]),
    ("visit", ["the museum", "the factory", "the new library"]),
    ("watch", ["the match", "the documentary", "the interview"]),
    ("plant", ["the trees", "the flowers", "the vegetables"]),
    ("invite", ["the neighbours", "the whole class", "his old friends"]),
]


def _conj(verb: str, tense: str, sing: bool) -> str:
    s3, past, pp, ing = VERBS[verb]
    if tense == "pres":
        return s3 if sing else verb
    if tense == "past":
        return past
    if tense == "perf":
        return ("has " if sing else "have ") + pp
    if tense == "cont":
        return ("is " if sing else "are ") + ing
    if tense == "fut":
        return "will " + verb
    if tense == "pastcont":
        return ("was " if sing else "were ") + ing
    if tense == "futcont":
        return "will be " + ing
    if tense == "perfcont":
        return ("has been " if sing else "have been ") + ing
    if tense == "pastperf":
        return "had " + pp
    if tense == "futperf":
        return "will have " + pp
    raise KeyError(tense)


# ------------------------------------------------------------------ 1. 名词复数

PLURALS = [
    ("book", "books", "s"), ("desk", "desks", "s"), ("cup", "cups", "s"),
    ("pen", "pens", "s"), ("chair", "chairs", "s"), ("ticket", "tickets", "s"),
    ("box", "boxes", "es"), ("watch", "watches", "es"), ("bus", "buses", "es"),
    ("dish", "dishes", "es"), ("class", "classes", "es"), ("brush", "brushes", "es"),
    ("baby", "babies", "y"), ("city", "cities", "y"), ("story", "stories", "y"),
    ("country", "countries", "y"), ("factory", "factories", "y"), ("family", "families", "y"),
    ("toy", "toys", "y2"), ("day", "days", "y2"), ("key", "keys", "y2"), ("boy", "boys", "y2"),
    ("leaf", "leaves", "ves"), ("knife", "knives", "ves"), ("wife", "wives", "ves"),
    ("shelf", "shelves", "ves"), ("thief", "thieves", "ves"),
    ("roof", "roofs", "f2"), ("chief", "chiefs", "f2"), ("belief", "beliefs", "f2"),
    ("proof", "proofs", "f2"),
    ("photo", "photos", "o2"), ("piano", "pianos", "o2"), ("radio", "radios", "o2"),
    ("zoo", "zoos", "o2"),
    ("hero", "heroes", "o"), ("potato", "potatoes", "o"), ("tomato", "tomatoes", "o"),
    ("echo", "echoes", "o"),
    ("man", "men", "irr"), ("woman", "women", "irr"), ("child", "children", "irr"),
    ("foot", "feet", "irr"), ("tooth", "teeth", "irr"), ("mouse", "mice", "irr"),
    ("goose", "geese", "irr"), ("ox", "oxen", "irr"),
    ("sheep", "sheep", "same"), ("deer", "deer", "same"), ("fish", "fish", "same"),
    ("means", "means", "same"), ("series", "series", "same"),
    ("phenomenon", "phenomena", "foreign"), ("criterion", "criteria", "foreign"),
    ("datum", "data", "foreign"), ("analysis", "analyses", "foreign"),
    ("crisis", "crises", "foreign"), ("basis", "bases", "foreign"),
]

PLURAL_RULE = {
    "s": "一般可数名词直接加 -s。",
    "es": "以 s / x / ch / sh 结尾的名词加 -es。",
    "y": "辅音字母 + y 结尾，变 y 为 i 再加 -es。",
    "y2": "元音字母 + y 结尾，直接加 -s。",
    "ves": "以 f / fe 结尾的部分名词，变 f / fe 为 v 再加 -es。",
    "f2": "roof / chief / belief / proof 等直接加 -s，不变成 ves。",
    "o": "hero / potato / tomato / echo 等加 -es。",
    "o2": "photo / piano / radio / zoo 等只加 -s。",
    "irr": "不规则变化，必须单独记。",
    "same": "单复数同形，词尾不变化。",
    "foreign": "外来词保留原来的复数形式。",
}


def _g_plural(rng: random.Random) -> dict:
    word, plural, cat = rng.choice(PLURALS)
    frame = rng.choice([
        "We need three ___ ({w}) by Friday.",
        "Three ___ ({w}) were missing from the list.",
        "The teacher collected twenty ___ ({w}) after class.",
    ])
    stem = frame.format(w=word)
    accept = [plural, plural.capitalize()]
    return _fill(stem, plural, f"{PLURAL_RULE[cat]}「{word}」的复数是 {plural}。", accept=accept)


# ------------------------------------------------------------------ 2. 复合名词复数

COMPOUNDS = [
    ("passer-by", "passers-by", "主体名词在前，只把 passer 变复数。"),
    ("looker-on", "lookers-on", "主体名词在前，只变 looker。"),
    ("brother-in-law", "brothers-in-law", "主体名词是 brother。"),
    ("editor-in-chief", "editors-in-chief", "主体名词是 editor。"),
    ("grown-up", "grown-ups", "没有主体名词，在词尾加 -s。"),
    ("stand-by", "stand-bys", "没有主体名词，在词尾加 -s。"),
    ("man doctor", "men doctors", "man / woman 作定语时两个成分都变复数。"),
    ("woman teacher", "women teachers", "woman 作定语时两个成分都变复数。"),
    ("girl student", "girl students", "girl 作定语时只变后面的主体名词。"),
    ("boy friend", "boy friends", "boy 作定语时只变后面的主体名词。"),
    ("tooth brush", "tooth brushes", "只变主体名词 brush。"),
    ("shoe shop", "shoe shops", "只变主体名词 shop。"),
]


def _g_compound_plural(rng: random.Random) -> dict:
    sing, plural, why = rng.choice(COMPOUNDS)
    frame = rng.choice([
        "Two ___ ({w}) were waiting at the gate.",
        "The street was full of ___ ({w}).",
        "We interviewed three ___ ({w}) yesterday.",
    ])
    return _fill(frame.format(w=sing), plural, why, accept=[plural])


# ------------------------------------------------------------------ 3. 名词所有格

POSSESS = [
    ("Please put the boxes in the ___ (children) room.", "children's", "不规则复数不以 s 结尾，加 's。"),
    ("I borrowed ___ (student) bicycle for the afternoon.", "the student's", "单数名词加 's。"),
    ("The ___ (students) projects were displayed in the hall.", "students'", "以 s 结尾的复数只加 '。"),
    ("The station is only a ___ (stone) throw from here.", "stone's", "表示距离的名词也可用 's 作定语。"),
    ("She is waiting at the ___ (doctor).", "doctor's", "表示诊所时常省略后面的名词。"),
    ("After a ___ (day) work, he went straight to bed.", "day's", "表示时间的名词用 's 作定语。"),
    ("It is ten ___ (minute) walk from the station.", "minutes'", "以 s 结尾的复数只加 '。"),
    ("The ___ (women) changing room is on the second floor.", "women's", "不规则复数加 's。"),
]


def _g_possessive(rng: random.Random) -> dict:
    stem, ans, why = rng.choice(POSSESS)
    return _fill(stem, ans, why, accept=[ans])


# ------------------------------------------------------------------ 4. a / an

AN_NPS = [
    ("honest man", "an"), ("hour", "an"), ("university", "a"), ("useful book", "a"),
    ("umbrella", "an"), ("European city", "a"), ("MBA", "an"), ("X-ray", "an"),
    ("one-way ticket", "a"), ("unusual story", "an"), ("hotel room", "a"),
    ("idea", "an"), ("egg", "an"), ("apple", "an"), ("island", "an"),
    ("uncle", "an"), ("unit", "a"), ("uniform", "a"), ("UFO", "a"),
    ("interesting job", "an"), ("old car", "a"), ("young engineer", "a"),
    ("heir", "an"), ("honor", "an"), ("useless tool", "a"),
    ("unhappy customer", "an"), ("European friend", "a"),
]


def _g_aan(rng: random.Random) -> dict:
    np_, ans = rng.choice(AN_NPS)
    subj, sing = rng.choice(SUBJ)
    stem = f"{subj} {'is' if sing else 'are'} looking for ___ {np_}."
    first = np_[0].lower()
    if first in "aeiou":
        why = f"「{np_}」虽然以元音字母开头，但要看读音：读元音音素才用 an。"
    else:
        why = f"「{np_}」以辅音字母开头，按读音判断用 a 还是 an。"
    if ans == "an":
        why = f"「{np_}」开头的音素是元音，用 an；拼写是否元音字母不是判据。"
    else:
        why = f"「{np_}」开头的音素是辅音（如 university 读 /juː/），用 a。"
    return _fill(stem, ans, why, accept=[ans])


# ------------------------------------------------------------------ 5. 冠词综合

ARTICLE_ITEMS: dict[str, list[tuple]] = {
    "definite-specific": [
        ("I bought a book yesterday. ___ book is about grammar.", "The", ["A", "An", "(不填)"],
         "上文已出现过的名词再次提到，用定冠词表特指。"),
        ("___ man standing at the gate is our new coach.", "The", ["A", "An", "(不填)"],
         "后置定语限定了是哪一个，属于特指。"),
        ("Please close ___ door behind you.", "the", ["a", "an", "(不填)"],
         "双方都清楚指的是哪扇门，用 the。"),
        ("She played ___ piano while we sang.", "the", ["a", "an", "(不填)"],
         "演奏乐器用 play the + 乐器。"),
    ],
    "definite-generic": [
        ("___ tiger is in danger of dying out.", "The", ["A", "An", "(不填)"],
         "the + 单数可数名词可表类指，指整个类别。"),
        ("___ computer has changed the way we work.", "The", ["A", "An", "(不填)"],
         "发明物、类指常用 the + 单数名词。"),
        ("___ young should respect ___ old.", "The; the", ["A; the", "The; an", "(不填); the"],
         "the + 形容词表一类人，两处都要 the。"),
    ],
    "zero-article": [
        ("He goes to ___ school by ___ bike every day.", "(不填); (不填)", ["the; a", "a; the", "the; the"],
         "go to school 表示上学这一活动，by bike 表示交通方式，都用零冠词。"),
        ("We had ___ breakfast at seven.", "(不填)", ["a", "the", "an"],
         "三餐名词前一般不用冠词。"),
        ("___ water is necessary for life.", "(不填)", ["A", "The", "An"],
         "物质名词表泛指时用零冠词。"),
        ("They arrived in ___ Beijing on ___ Monday.", "(不填); (不填)", ["the; the", "a; a", "the; a"],
         "专有名词与星期前用零冠词。"),
    ],
    "abstract-mass": [
        ("She has ___ good command of English.", "a", ["an", "the", "(不填)"],
         "抽象名词带修饰语表示「一种」时可用不定冠词。"),
        ("___ honesty is the best policy.", "(不填)", ["An", "The", "A"],
         "抽象名词泛指时用零冠词。"),
        ("He showed ___ great courage in the accident.", "(不填)", ["a", "an", "the"],
         "抽象名词被形容词修饰但仍表泛指时，通常不用冠词。"),
    ],
    "fixed-phrases": [
        ("___ first, I thought he was joking.", "At", ["In", "On", "For"],
         "at first 是固定短语，意为「起初」。"),
        ("He is ___ charge of the project.", "in", ["on", "at", "for"],
         "in charge of 是固定搭配。"),
        ("The meeting was held ___ purpose to discuss the plan.", "on", ["in", "at", "for"],
         "on purpose 意为「故意」。"),
        ("She burst into ___ tears when she heard the news.", "(不填)", ["a", "the", "an"],
         "burst into tears 是固定短语，不用冠词。"),
    ],
    "superlative-ordinal": [
        ("This is ___ best film I have ever seen.", "the", ["a", "an", "(不填)"],
         "形容词最高级前用 the。"),
        ("He was ___ first to arrive.", "the", ["a", "an", "(不填)"],
         "序数词前用 the。"),
        ("It is ___ only solution to the problem.", "the", ["a", "an", "(不填)"],
         "only 修饰名词时前面用 the。"),
    ],
    "a-most-vs-the-most": [
        ("It is ___ most interesting book.", "a", ["the", "an", "(不填)"],
         "a most + 形容词表示「非常」，相当于 very。"),
        ("It is ___ most interesting book on the shelf.", "the", ["a", "an", "(不填)"],
         "句末有范围限定，是最高级，用 the。"),
    ],
    "titles": [
        ("He was elected ___ chairman of the committee.", "(不填)", ["a", "the", "an"],
         "表示独一无二的职位作表语或补语时，不用冠词。"),
        ("___ President will visit our school tomorrow.", "The", ["A", "An", "(不填)"],
         "作主语时仍需冠词。"),
    ],
}


def _g_article(items):
    def g(rng: random.Random) -> dict:
        stem, ans, wrongs, why = rng.choice(items)
        return _choice(rng, stem, ans, wrongs, why,
                       trap="先判断泛指还是特指，再看名词是可数还是不可数。")
    return g


# ------------------------------------------------------------------ 6. 主谓一致

SIMPLE_FORM = {
    "be": ("is", "are"),
    "have": ("has", "have"),
    "do": ("does", "do"),
    "go": ("goes", "go"),
    "want": ("wants", "want"),
    "need": ("needs", "need"),
    "like": ("likes", "like"),
    "know": ("knows", "know"),
    "seem": ("seems", "seem"),
    "cost": ("costs", "cost"),
    "remain": ("remains", "remain"),
    "work": ("works", "work"),
}

FORM_POOL = {
    "be": ["is", "are", "was", "were"],
    "have": ["has", "have", "had", "having"],
    "do": ["does", "do", "did", "done"],
    "go": ["goes", "go", "went", "gone"],
    "want": ["wants", "want", "wanted", "wanting"],
    "need": ["needs", "need", "needed", "needing"],
    "like": ["likes", "like", "liked", "liking"],
    "know": ["knows", "know", "knew", "known"],
    "seem": ["seems", "seem", "seemed", "seeming"],
    "cost": ["costs", "cost", "costed", "costing"],
    "remain": ["remains", "remain", "remained", "remaining"],
    "work": ["works", "work", "worked", "working"],
}

# (主语, 动词, 后接成分, 单数?)
SVA_ITEMS: dict[str, list[tuple]] = {
    "grammatical": [
        ("The number of students", "be", "increasing", True),
        ("Each of the boys", "have", "a dictionary", True),
        ("Every one of the answers", "seem", "correct", True),
        ("The news", "be", "surprising", True),
        ("Mathematics", "be", "my favourite subject", True),
        ("My glasses", "be", "broken", False),
        ("The police", "be", "looking into the case", False),
        ("Cattle", "be", "raised on this farm", False),
    ],
    "notional": [
        ("The family", "be", "having dinner together", True),
        ("The team", "be", "playing much better now", True),
        ("Ten years", "be", "a long time", True),
        ("Five thousand dollars", "be", "more than I can afford", True),
        ("The class", "be", "taking notes", False),
    ],
    "proximity": [
        ("Neither the teacher nor the students", "be", "in the classroom", False),
        ("Either you or he", "have", "to take charge", True),
        ("Not only the students but also the teacher", "be", "invited", True),
        ("Neither he nor I", "know", "the answer", False),
    ],
    "remote": [
        ("The teacher, together with the students,", "be", "visiting the museum", True),
        ("The captain, as well as the players,", "want", "a rest", True),
        ("Nobody but the twins", "know", "the truth", True),
    ],
    "and-subjects": [
        ("Bread and butter", "be", "my favourite breakfast", True),
        ("The writer and poet", "be", "dead", True),
        ("Both the teacher and the students", "be", "satisfied", False),
        ("A knife and fork", "be", "needed for this dish", True),
    ],
    "indefinite-pronouns": [
        ("Everyone in the class", "have", "a copy of the handout", True),
        ("Nobody", "know", "the answer", True),
        ("Neither of the two answers", "be", "correct", True),
        ("Some of the water", "be", "wasted", True),
        ("Most of the students", "be", "from the countryside", False),
    ],
    "relative-clause": [
        ("He is one of the students who", "be", "from China", False),
        ("She is the only one of the girls who", "have", "a car", True),
        ("This is one of the books that", "be", "worth reading", False),
    ],
    "quantity-phrases": [
        ("Two thirds of the water", "be", "wasted", True),
        ("Two thirds of the students", "be", "from the city", False),
        ("Half of the money", "be", "spent", True),
        ("A pair of shoes", "be", "on the shelf", True),
        ("The rest of the food", "be", "thrown away", True),
    ],
}

SVA_WHY = {
    "grammatical": "语法一致：主语是单数（或形式上是单数），谓语就用单数。",
    "notional": "意义一致：主语形式是单数但表示复数成员时，谓语可用复数。",
    "proximity": "就近原则：谓语与最靠近它的那个主语保持一致。",
    "remote": "就远原则：together with / as well as / but 等结构不改变原主语的数。",
    "and-subjects": "and 连接的主语一般用复数；指同一人或同一整体时用单数。",
    "indefinite-pronouns": "不定代词作主语通常看作单数；most / some of + 复数则用复数。",
    "relative-clause": "one of + 复数名词 + 关系代词：从句谓语与复数名词一致。",
    "quantity-phrases": "分数、half、rest of 等：看 of 后面的名词是否可数复数。",
}


def _g_sva(rule: str):
    def g(rng: random.Random) -> dict:
        subj, verb, rest, sing = rng.choice(SVA_ITEMS[rule])
        ans = SIMPLE_FORM[verb][0 if sing else 1]
        pool = FORM_POOL[verb]
        wrongs = [x for x in pool if x != ans]
        stem = f"{subj} ___ ({verb}) {rest}."
        return _choice(rng, stem, ans, wrongs, SVA_WHY[rule],
                       trap="先找真正的主语，再看它被什么结构修饰。")
    return g


# ------------------------------------------------------------------ 7. 时态

def _g_tense(tenses):
    allowed = list(tenses)

    def g(rng: random.Random) -> dict:
        tense = rng.choice(allowed)
        sig = rng.choice(SIGNALS[tense])
        verb, objs = rng.choice(TENSE_VERBS)
        obj = rng.choice(objs)
        subj, sing = rng.choice(SUBJ)
        stem = f"{subj} ___ ({verb}) {obj} {sig}."
        ans = _conj(verb, tense, sing)
        cands = ["pres", "past", "perf", "cont", "fut", "pastcont", "futcont", "perfcont"]
        rng.shuffle(cands)
        wrongs: list[str] = []
        for t in cands:
            if t == tense:
                continue
            f = _conj(verb, t, sing)
            if f != ans and f not in wrongs:
                wrongs.append(f)
            if len(wrongs) == 3:
                break
        why = f"「{sig}」这个时间标志指向{TENSE_LABEL[tense]}，所以填 {ans}。"
        return _choice(rng, stem, ans, wrongs, why,
                       trap="先看时间状语限定了哪一段时间，再决定时态，最后才是形式。")
    return g


def _g_durative(cont: bool = False):
    """现在完成（进行）时的延续用法：for + 时间段 / since + 时间点。"""

    POOL = [
        ("live", "in Beijing", "since", "2015"),
        ("work", "in this company", "since", "2018"),
        ("study", "English", "since", "last September"),
        ("teach", "at this school", "since", "2019"),
        ("live", "here", "for", "three years"),
        ("work", "at the bank", "for", "six years"),
    ]

    def g(rng: random.Random) -> dict:
        verb, place, prep, tail = rng.choice(POOL)
        subj, sing = rng.choice(SUBJ)
        _s3, _past, pp, ing = VERBS[verb]
        if cont:
            ans = ("has been " if sing else "have been ") + ing
            why = "动作从过去持续到现在且仍将继续，用现在完成进行时。"
        else:
            ans = ("has " if sing else "have ") + pp
            why = "动作从过去延续到现在，用现在完成时；since 接时间点，for 接时间段。"
        stem = f"{subj} ___ ({verb}) {place} {prep} {tail}."
        accept = [ans]
        if ans.startswith("has "):
            accept.append("'s " + ans[4:])
        if ans.startswith("have "):
            accept.append("'ve " + ans[5:])
        return _fill(stem, ans, why, accept=accept)

    return g


def _g_verbform(kind: str):
    """动词形式：三单 / 过去式 / 过去分词 / 现在分词。"""

    WHY = {
        "3sg": "一般现在时中，第三人称单数主语后面的动词要加 -s / -es。",
        "past": "一般过去时用过去式，常与 yesterday、last week 这类确定过去时间连用。",
        "pp": "现在完成时由 have / has + 过去分词构成。",
        "ing": "现在进行时由 be + 现在分词构成。",
    }

    def g(rng: random.Random) -> dict:
        verb, objs = rng.choice(TENSE_VERBS)
        obj = rng.choice(objs)
        subj, sing = rng.choice(SUBJ)
        if kind in ("3sg", "ing"):
            subj, sing = rng.choice([x for x in SUBJ if x[1]])
        s3, past, pp, ing = VERBS[verb]
        if kind == "3sg":
            stem = f"{subj} ___ ({verb}) {obj} every day."
        elif kind == "past":
            stem = f"{subj} ___ ({verb}) {obj} yesterday."
        elif kind == "pp":
            stem = f"{subj} {'has' if sing else 'have'} ___ ({verb}) {obj} already."
        else:
            stem = f"{subj} {'is' if sing else 'are'} ___ ({verb}) {obj} right now."
        ans = {"3sg": s3, "past": past, "pp": pp, "ing": ing}[kind]
        return _fill(stem, ans, WHY[kind], accept=[ans])

    return g


# ------------------------------------------------------------------ 8. 被动语态

PASS_VERBS = [
    ("build", ["The bridge", "The new library", "The stadium"]),
    ("repair", ["The road", "The lift", "The roof"]),
    ("publish", ["The book", "The report", "The article"]),
    ("clean", ["The classroom", "The kitchen", "The windows"]),
    ("grow", ["The vegetables", "The flowers", "The rice"]),
    ("deliver", ["The parcel", "The furniture", "The flowers"]),
]

PASS_SIGNAL = {
    "pres": "every year",
    "past": "last year",
    "perf": "already",
    "fut": "next month",
    "cont": "right now",
    "pastperf": "before we arrived",
}


def _pass(v: str, tense: str) -> str:
    _, _, pp, _ = VERBS[v]
    return {
        "pres": "is " + pp,
        "past": "was " + pp,
        "perf": "has been " + pp,
        "fut": "will be " + pp,
        "cont": "is being " + pp,
        "pastperf": "had been " + pp,
    }[tense]


def _g_passive(tenses):
    allowed = list(tenses)

    def g(rng: random.Random) -> dict:
        tense = rng.choice(allowed)
        verb, subjs = rng.choice(PASS_VERBS)
        subj = rng.choice(subjs)
        sig = PASS_SIGNAL[tense]
        ans = _pass(verb, tense)
        cands = ["pres", "past", "perf", "fut", "cont"]
        rng.shuffle(cands)
        wrongs = []
        for t in cands:
            if t == tense:
                continue
            f = _pass(verb, t)
            if f != ans and f not in wrongs:
                wrongs.append(f)
        stem = f"{subj} ___ ({verb}) {sig}."
        why = f"{TENSE_LABEL.get(tense, tense)}的被动语态由 be 的相应形式 + 过去分词构成，答案是 {ans}。"
        return _choice(rng, stem, ans, wrongs, why,
                       trap="先定时态的 be 形式，再把主动词变成过去分词。")
    return g


PASSIVE_TRAPS = [
    ("A serious accident ___ at the crossroads last night.",
     "happened", ["was happened", "has happened", "is happened"],
     "happen 是不及物动词，没有被动语态。"),
    ("The old house ___ my grandfather.",
     "belongs to", ["is belonged to", "is belonging to", "was belonged by"],
     "belong to 不用被动，也不用进行时。"),
    ("The war ___ in 1939.",
     "broke out", ["was broken out", "was broke out", "is broken out"],
     "break out 是不及物短语动词，没有被动形式。"),
    ("This kind of cloth ___ well.",
     "sells", ["is sold", "is selling", "has sold"],
     "sell / wash / read 等表示主语特性时，主动形式表被动意义。"),
    ("The floor needs ___.",
     "cleaning", ["to clean", "cleaned", "being cleaned"],
     "need doing = need to be done，动名词主动形式表被动。"),
    ("The book is worth ___.",
     "reading", ["to read", "being read", "read"],
     "be worth doing 用动名词主动形式表被动。"),
    ("The window ___ by the boy with a stone.",
     "was broken", ["was broken by", "broke", "is breaking"],
     "by 引出动作执行者，with 引出工具。"),
    ("The soup ___ garlic.",
     "was flavoured with", ["was flavoured by", "flavoured by", "was flavouring with"],
     "by 接执行者，with 接原材料或工具。"),
]


def _g_passive_trap(rng: random.Random) -> dict:
    stem, ans, wrongs, why = rng.choice(PASSIVE_TRAPS)
    return _choice(rng, stem, ans, wrongs, why,
                   trap="先判断动词能不能被动，再看介词该用 by 还是 with。")


# ------------------------------------------------------------------ 9. 反意疑问句

TAG_PRON = {
    "He": "he", "She": "she", "Tom": "he", "My brother": "he",
    "The manager": "he", "Lucy": "she",
    "They": "they", "We": "we", "The students": "they",
    "My parents": "they", "Tom and I": "we",
}

TAG_VERBS = [
    ("like", "coffee"), ("want", "a break"), ("need", "help"),
    ("know", "the answer"), ("work", "here"), ("live", "in this city"),
]


def _g_tag(rng: random.Random) -> dict:
    verb, obj = rng.choice(TAG_VERBS)
    subj, sing = rng.choice(SUBJ)
    tense = rng.choice(["pres", "pres", "past", "perf"])
    main = _conj(verb, tense, sing)
    pron = TAG_PRON[subj]
    if tense == "pres":
        aux = "does" if sing else "do"
    elif tense == "past":
        aux = "did"
    else:
        aux = "has" if sing else "have"
    pred = f"{subj} {main} {obj}"
    stem = f"{pred}, ___?"
    ans = f"{aux}n't {pron}" if tense != "perf" else f"{aux}n't {pron}"
    # 正确写法：doesn't / don't / didn't / hasn't / haven't
    NEG = {"does": "doesn't", "do": "don't", "did": "didn't",
           "has": "hasn't", "have": "haven't"}
    ans = f"{NEG[aux]} {pron}"
    wrongs = [
        f"{aux} {pron}",
        f"{NEG[{'does': 'do', 'do': 'does', 'did': 'did', 'has': 'have', 'have': 'has'}[aux]]} {pron}",
        f"{NEG[aux]} it",
    ]
    why = f"前句肯定，附加部分用否定；前句谓语是 {main}，助动词取 {aux}，主语换成代词 {pron}。"
    return _choice(rng, stem, ans, wrongs, why,
                   trap="先找主句的助动词，再把主语换成对应的人称代词。")


# ------------------------------------------------------------------ 10. 倒装

# (适用知识点后缀, 题干, 答案, 干扰项, 解析)
INVERSION_ITEMS = [
    ("negative-fronting", "Never ___ I seen such a beautiful sunset.",
     "have", ["did", "had", "was"],
     "否定副词 never 置于句首，用部分倒装：助动词提到主语前。"),
    ("negative-fronting", "Hardly ___ he entered the room when the phone rang.",
     "had", ["has", "did", "was"],
     "hardly...when 句型中主句用过去完成时，并部分倒装。"),
    ("negative-fronting", "Not until midnight ___ the work finished.",
     "was", ["did", "had", "is"],
     "not until 置于句首，主句倒装；the work 作主语，用被动 was finished。"),
    ("negative-fronting", "Nowhere else ___ you find such a quiet place.",
     "can", ["do", "are", "will"],
     "否定意义的 nowhere 置于句首，主句部分倒装。"),
    ("only-adverbial", "Only then ___ he realize how serious the problem was.",
     "did", ["does", "had", "was"],
     "only + 状语置于句首，主句部分倒装，借助 did。"),
    ("only-adverbial", "Only when he got home ___ he realize his mistake.",
     "did", ["does", "had", "was"],
     "only + 状语从句置于句首，主句倒装。"),
    ("only-adverbial", "Only in this way ___ you improve your spoken English.",
     "can", ["do", "are", "will be"],
     "only + 方式状语置于句首，主句用 can 提前。"),
    ("so-neither-nor", "He can't swim. Neither ___ I.",
     "can", ["do", "am", "have"],
     "neither 引导部分倒装，助动词与前句保持一致。"),
    ("so-neither-nor", "She likes coffee. So ___ I.",
     "do", ["am", "can", "have"],
     "so + 助动词 + 主语，表示「我也是」。"),
    ("so-neither-nor", "If you don't go, neither ___ I.",
     "will", ["do", "am", "have"],
     "neither 引导的倒装要与前句的情态或时态对应。"),
    ("full-inversion", "Here ___ the bus we have been waiting for.",
     "comes", ["come", "is coming", "came"],
     "here 置于句首且主语是名词时用完全倒装，谓语与后面主语一致。"),
    ("full-inversion", "Under the tree ___ an old man sleeping.",
     "lay", ["lied", "laid", "lying"],
     "地点状语前置用完全倒装；lie（躺）的过去式是 lay。"),
    ("full-inversion", "On the wall ___ a map of China.",
     "hangs", ["hang", "hung", "hanging"],
     "表语前置完全倒装，主语 a map 是单数，谓语用 hangs。"),
    ("subjunctive-inversion", "___ I known the truth, I would have acted differently.",
     "Had", ["Have", "If", "Should"],
     "省略 if 的虚拟条件句把 had 提前，形成倒装。"),
    ("subjunctive-inversion", "___ he left earlier, he would have caught the train.",
     "Had", ["Have", "If", "Did"],
     "与过去事实相反，省略 if 后把 had 提到主语前。"),
    ("as-though-concession", "Child ___ he is, he knows a lot about computers.",
     "as", ["though", "although", "that"],
     "as 引导让步状语从句时必须把表语提前，形成倒装。"),
    ("as-though-concession", "Hard ___ he tried, he could not solve the problem.",
     "as", ["though", "although", "that"],
     "as 引导让步时把副词提前，结构是 副词 + as + 主语 + 谓语。"),
    ("such-so-fronting", "So loudly ___ he speak that everyone turned around.",
     "did", ["does", "had", "was"],
     "so + 副词置于句首，主句部分倒装。"),
    ("such-so-fronting", "Such ___ the force of the explosion that windows shattered.",
     "was", ["were", "is", "did"],
     "such 置于句首作表语，用完全倒装。"),
]


def _g_inversion(tag: str):
    items = [x for x in INVERSION_ITEMS if x[0] == tag]

    def g(rng: random.Random) -> dict:
        _t, stem, ans, wrongs, why = rng.choice(items)
        return _choice(rng, stem, ans, wrongs, why,
                       trap="先确认触发倒装的结构，再决定倒装的是助动词还是整个谓语。")

    return g


# ------------------------------------------------------------------ 11. 虚拟语气

SUBJ_VERBS = [
    ("know", "known", "the answer"),
    ("have", "had", "enough time"),
    ("be", "been", "more careful"),
    ("study", "studied", "harder"),
    ("leave", "left", "earlier"),
]

ACTIONS = ["accept the offer", "take the job", "tell him the truth",
           "buy the house", "join the club"]


def _g_subj_if(rng: random.Random) -> dict:
    verb, pp, obj = rng.choice(SUBJ_VERBS)
    action = rng.choice(ACTIONS)
    if verb == "be":
        stem = f"If I ___ (be) you, I would {action}."
        return _fill(stem, "were", "与现在事实相反的虚拟条件句，be 一律用 were。",
                     accept=["were"])
    mode = rng.choice(["now", "past"])
    if mode == "now":
        s3, past, _, _ = VERBS[verb]
        stem = f"If he ___ ({verb}) {obj}, he would {action}."
        return _fill(stem, past, "与现在事实相反：从句用过去式，主句用 would + 动词原形。",
                     accept=[past])
    stem = f"If he ___ ({verb}) {obj}, he would have {action_split(action)}."
    return _fill(stem, f"had {pp}", "与过去事实相反：从句用 had + 过去分词，主句用 would have + 过去分词。",
                 accept=[f"had {pp}", f"'d {pp}"])


def action_split(action: str) -> str:
    """把 'accept the offer' 变成过去分词短语 'accepted the offer'。"""
    PAST = {
        "accept": "accepted", "take": "taken", "tell": "told",
        "buy": "bought", "join": "joined",
    }
    head, _, rest = action.partition(" ")
    return f"{PAST.get(head, head + 'ed')} {rest}".strip()


def _g_wish(rng: random.Random) -> dict:
    verb, pp, obj = rng.choice(SUBJ_VERBS)
    subj, poss = rng.choice([("I", "I"), ("He", "he"), ("She", "she"), ("Tom", "he")])
    wish = "wish" if subj in ("I",) else "wishes"
    if verb == "be":
        stem = f"{subj} {wish} {poss} ___ (be) taller."
        return _fill(stem, "were", "wish 后与现在事实相反，be 一律用 were。", accept=["were"])
    mode = rng.choice(["now", "past"])
    if mode == "now":
        ans = VERBS[verb][1]
        why = "wish 后与现在事实相反，从句谓语用过去式。"
    else:
        ans = f"had {pp}"
        why = "wish 后与过去事实相反，从句谓语用 had + 过去分词。"
    stem = f"{subj} {wish} {poss} ___ ({verb}) {obj}."
    return _fill(stem, ans, why, accept=[ans])


# ------------------------------------------------------------------ 12. 定语从句

PEOPLE = ["man", "woman", "boy", "girl", "teacher", "engineer", "doctor"]
THINGS = ["book", "car", "house", "phone", "letter", "camera"]
PLACES = ["city", "village", "room", "school"]

REL_JOBS = ["lives next door", "works in the bank", "teaches us English",
            "won the prize", "comes from Canada"]


def _g_relative(rng: random.Random) -> dict:
    mode = rng.choice(["person-subj", "thing-obj", "possessive", "place"])
    if mode == "person-subj":
        person = rng.choice(PEOPLE)
        job = rng.choice(REL_JOBS)
        stem = f"The {person} ___ {job} is my neighbour."
        return _choice(rng, stem, "who", ["which", "whose", "whom"],
                       "先行词指人，且关系词在从句中作主语，用 who。",
                       trap="作宾语时才可能用 whom，作主语只能用 who。")
    if mode == "thing-obj":
        thing = rng.choice(THINGS)
        stem = f"The {thing} ___ I bought last week was stolen."
        return _choice(rng, stem, "which", ["who", "whose", "when"],
                       "先行词指物，关系词在从句中作宾语，用 which 或 that。",
                       trap="who 只指人；whose 表示所属。")
    if mode == "possessive":
        person = rng.choice(["girl", "boy", "man", "woman"])
        noun = rng.choice(["father", "mother", "brother", "sister"])
        stem = f"The {person} ___ {noun} is a doctor studies very hard."
        return _choice(rng, stem, "whose", ["who", "which", "whom"],
                       "表示「某人的……」，用 whose 作定语。",
                       trap="whose 后面必须紧跟名词。")
    place = rng.choice(PLACES)
    stem = f"This is the {place} ___ we first met."
    return _choice(rng, stem, "where", ["which", "when", "that"],
                   "先行词是地点，且关系词在从句中作地点状语，用 where。",
                   trap="从句缺宾语时用 which / that，只有缺状语才用 where。")


# ------------------------------------------------------------------ 13. 感叹句

EXCL_NOUNS = [
    ("beautiful day", "What a"), ("interesting book", "What an"),
    ("good idea", "What a"), ("tall buildings", "What"),
    ("lovely flowers", "What"), ("clever boy", "What a"),
]
EXCL_ADJS = ["beautiful", "wonderful", "fast", "carefully", "quickly", "kind"]


def _g_excl(rng: random.Random) -> dict:
    if rng.random() < 0.5:
        np_, ans = rng.choice(EXCL_NOUNS)
        stem = f"___ {np_} they are!"
        wrongs = ["What", "How", "How a"]
        if ans == "What a":
            wrongs = ["What", "How", "What an"]
        elif ans == "What an":
            wrongs = ["What", "How", "What a"]
        why = "感叹名词短语用 what；单数可数名词还要判断用 a 还是 an。"
        return _choice(rng, stem, ans, wrongs, why,
                       trap="what 修饰名词短语，how 修饰形容词或副词。")
    adj = rng.choice(EXCL_ADJS)
    stem = f"___ {adj} the children are!"
    return _choice(rng, stem, "How", ["What", "What a", "How a"],
                   "感叹形容词或副词用 how，结构是 How + adj./adv. + 主语 + 谓语。",
                   trap="what 后面必须接名词短语。")


# ------------------------------------------------------------------ 14. 比较级

ADJ = [
    ("tall", "taller", "tallest"), ("big", "bigger", "biggest"),
    ("hot", "hotter", "hottest"), ("easy", "easier", "easiest"),
    ("happy", "happier", "happiest"), ("thin", "thinner", "thinnest"),
    ("busy", "busier", "busiest"), ("narrow", "narrower", "narrowest"),
    ("beautiful", "more beautiful", "most beautiful"),
    ("expensive", "more expensive", "most expensive"),
    ("interesting", "more interesting", "most interesting"),
    ("good", "better", "best"), ("bad", "worse", "worst"),
]

CMP_NOUNS = ["room", "car", "book", "garden", "building", "bike"]


def _g_comparative(rng: random.Random) -> dict:
    adj, comp, sup = rng.choice(ADJ)
    if rng.random() < 0.5:
        stem = f"This one is ___ ({adj}) than that one."
        why = "两者比较用比较级：单音节加 -er，多音节前加 more。"
        return _fill(stem, comp, why, accept=[comp])
    stem = f"This is the ___ ({adj}) one of the three."
    why = "三者以上比较用最高级，最高级前要加 the。"
    return _fill(stem, sup, why, accept=[sup])


def _g_multiple(rng: random.Random) -> dict:
    noun = rng.choice(["room", "box", "garden", "bag"])
    n = rng.choice([2, 3, 4])
    stem = f"This {noun} is {n} times ___ that one."
    if rng.random() < 0.5:
        ans = "as large as"
        wrongs = ["as large", "larger as", "so large as"]
        why = f"倍数 + as + 形容词原级 + as，表示「是……的 {n} 倍大」。"
    else:
        ans = "larger than"
        wrongs = ["as large as", "large than", "more large than"]
        why = f"倍数 + 比较级 + than 也可以表达倍数关系。"
    return _choice(rng, stem, ans, wrongs, why,
                   trap="倍数词放在最前面，后面接 as...as 或比较级 + than。")


# ------------------------------------------------------------------ 15. there be

THERE_ITEMS = [
    ("There ___ (be) a book and two pens on the desk.", "is",
     "there be 遵循就近原则，靠近 be 的是 a book，用 is。"),
    ("There ___ (be) two pens and a book on the desk.", "are",
     "靠近 be 的是 two pens，用 are。"),
    ("There ___ (be) a meeting tomorrow afternoon.", "will be",
     "there be 的将来时是 there will be。"),
    ("There ___ (be) a lot of rain last summer.", "was",
     "rain 不可数，过去时用 was。"),
    ("There ___ (be) some milk in the fridge.", "is",
     "milk 不可数，用 is。"),
    ("There ___ (be) few students in the classroom now.", "are",
     "few students 是复数，用 are。"),
]


def _g_there(rng: random.Random) -> dict:
    stem, ans, why = rng.choice(THERE_ITEMS)
    return _fill(stem, ans, why, accept=[ans])


# ------------------------------------------------------------------ 16. 时间介词

PREP_TIME = [
    ("We will meet ___ Monday morning.", "on", ["in", "at", "by"],
     "具体到某一天的上午用 on。"),
    ("He was born ___ 2010.", "in", ["on", "at", "by"],
     "年份前用 in。"),
    ("The film starts ___ seven o'clock.", "at", ["in", "on", "by"],
     "钟点前用 at。"),
    ("She will be back ___ half an hour.", "in", ["after", "at", "on"],
     "in + 一段时间表示「多久以后」，用于将来时。"),
    ("We stayed there ___ the summer.", "in", ["on", "at", "by"],
     "季节前用 in。"),
    ("___ a cold winter morning, he left home.", "On", ["In", "At", "By"],
     "被修饰的某天早晨仍用 on。"),
    ("The shop is closed ___ night.", "at", ["in", "on", "by"],
     "at night 是固定搭配。"),
    ("I have been here ___ three years.", "for", ["since", "in", "during"],
     "for + 时间段。"),
]


def _g_prep_time(rng: random.Random) -> dict:
    stem, ans, wrongs, why = rng.choice(PREP_TIME)
    return _choice(rng, stem, ans, wrongs, why,
                   trap="in 用于年月季节等较长时段，on 用于具体某天，at 用于钟点。")


# ------------------------------------------------------------------ 17. 情态动词

MODAL_ITEMS = [
    ("Look at those dark clouds. It ___ rain at any moment.",
     "may", ["must", "can't", "needn't"], "对现在情况的可能性推测，用 may。"),
    ("He has been working for twelve hours. He ___ be tired.",
     "must", ["can't", "may", "needn't"], "有充分依据的肯定推测用 must。"),
    ("She ___ be at home. I saw her in the office just now.",
     "can't", ["mustn't", "needn't", "may not"], "否定推测用 can't，不用 mustn't。"),
    ("You ___ have told me earlier. I could have helped.",
     "should", ["must", "can", "need"], "should have done 表示「本应该做而没做」。"),
    ("He ___ have finished the work. The light is still on.",
     "can't", ["must", "should", "needn't"], "对过去的否定推测用 can't have done。"),
    ("You ___ have watered the flowers. It rained last night.",
     "needn't", ["mustn't", "can't", "shouldn't"], "needn't have done 表示「本来不必做却做了」。"),
]


def _g_modal(rng: random.Random) -> dict:
    stem, ans, wrongs, why = rng.choice(MODAL_ITEMS)
    return _choice(rng, stem, ans, wrongs, why,
                   trap="推测强度：must > should > may > might/could > can't。")


# ------------------------------------------------------------------ 18. 数词

NUM_ITEMS = [
    ("Two ___ (three) of the students passed the exam.", "thirds",
     "分数：分子用基数词，分母用序数词；分子大于 1 时分母加 -s。"),
    ("___ (hundred) of people gathered in the square.", "Hundreds",
     "hundreds of 表示泛指的「数以百计」，要加 -s 并接 of。"),
    ("There are three ___ (hundred) students in our grade.", "hundred",
     "前面有具体数字时 hundred 不加 -s，也不接 of。"),
    ("He was born in the ___ (1990).", "1990s",
     "表示某个年代用 in the + 年份 + s。"),
    ("She is in her ___ (thirty).", "thirties",
     "表示年龄的约数用 in one's + 十位数的复数。"),
    ("The population has increased by 20 ___ (percent).", "percent",
     "百分数用 percent，不随数字变化。"),
]


def _g_numeral(rng: random.Random) -> dict:
    stem, ans, why = rng.choice(NUM_ITEMS)
    return _fill(stem, ans, why, accept=[ans, ans.lower()])


# ------------------------------------------------------------------ 19. 动名词与不定式

GERUND_ITEMS = [
    ("I still remember ___ (see) the film for the first time.",
     "seeing", ["to see", "see", "seen"],
     "remember doing 表示记得做过某事（动作已发生）。"),
    ("Please remember ___ (lock) the door when you leave.",
     "to lock", ["locking", "lock", "locked"],
     "remember to do 表示记得去做某事（动作未发生）。"),
    ("He stopped ___ (smoke) three years ago.",
     "smoking", ["to smoke", "smoke", "smoked"],
     "stop doing 表示停止正在做的事。"),
    ("On the way home he stopped ___ (buy) some milk.",
     "to buy", ["buying", "buy", "bought"],
     "stop to do 表示停下来去做另一件事。"),
    ("I regret ___ (tell) him the bad news.",
     "telling", ["to tell", "tell", "told"],
     "regret doing 表示对已做的事感到后悔。"),
    ("We regret ___ (inform) you that your application was rejected.",
     "to inform", ["informing", "inform", "informed"],
     "regret to do 用于正式场合，表示遗憾地告知。"),
    ("Try ___ (restart) the computer if it doesn't work.",
     "restarting", ["to restart", "restart", "restarted"],
     "try doing 表示试试某种办法。"),
    ("He tried ___ (lift) the box but failed.",
     "to lift", ["lifting", "lift", "lifted"],
     "try to do 表示努力去做。"),
]


def _g_gerund(rng: random.Random) -> dict:
    stem, ans, wrongs, why = rng.choice(GERUND_ITEMS)
    return _choice(rng, stem, ans, wrongs, why,
                   trap="先判断动作发生在谓语之前还是之后，再决定用 doing 还是 to do。")


# ------------------------------------------------------------------ 20. so / such

SOSUCH = [
    ("It was ___ a hot day that we stayed indoors.", "such", ["so", "very", "too"],
     "such + a + 形容词 + 名词；so 后直接跟形容词。"),
    ("The day was ___ hot that we stayed indoors.", "so", ["such", "very", "too"],
     "so + 形容词 + that 从句。"),
    ("There were ___ many people that we couldn't get in.", "so", ["such", "very", "too"],
     "so many / so much / so few / so little 是固定搭配。"),
    ("It was ___ terrible weather that we cancelled the trip.", "such", ["so", "very", "too"],
     "weather 不可数，用 such + 形容词 + 不可数名词。"),
    ("It was ___ a beautiful morning that we decided to walk to school.", "such", ["so", "very", "too"],
     "空后是 a + 形容词 + 名词，用 such。"),
    ("The box was ___ heavy that nobody could lift it.", "so", ["such", "very", "too"],
     "空后直接是形容词 heavy，用 so。"),
    ("He spoke ___ quickly that I couldn't follow him.", "so", ["such", "very", "too"],
     "空后是副词 quickly，用 so。"),
    ("They are ___ kind people that everyone likes them.", "such", ["so", "very", "too"],
     "空后是形容词 + 复数名词，用 such。"),
    ("It is ___ good a film that I want to see it again.", "so", ["such", "very", "too"],
     "so + 形容词 + a + 名词 是固定语序，不能换成 such。"),
    ("We had ___ little time that we couldn't finish the work.", "so", ["such", "very", "too"],
     "little 表示「少」时用 so little + 不可数名词。"),
    ("There was ___ much noise that I couldn't sleep.", "so", ["such", "very", "too"],
     "so much + 不可数名词 是固定搭配。"),
    ("He is ___ a clever boy that everyone praises him.", "such", ["so", "very", "too"],
     "空后是 a + 形容词 + 单数名词，用 such。"),
    ("The weather was ___ bad that we stayed at home all day.", "so", ["such", "very", "too"],
     "空后直接是形容词 bad，用 so。"),
    ("It was ___ fine weather that we went out for a picnic.", "such", ["so", "very", "too"],
     "weather 是不可数名词，用 such + 形容词 + 名词。"),
    ("She ran ___ fast that nobody could catch her.", "so", ["such", "very", "too"],
     "空后是副词 fast，用 so。"),
    ("I have ___ few friends here that I often feel lonely.", "so", ["such", "very", "too"],
     "few 表示「少」时用 so few + 复数名词。"),
]


def _g_sosuch(rng: random.Random) -> dict:
    stem, ans, wrongs, why = rng.choice(SOSUCH)
    return _choice(rng, stem, ans, wrongs, why,
                   trap="先看空格后是名词短语还是形容词：名词用 such，形容词用 so。")


# ------------------------------------------------------------------ 21. some / any

SOMEANY = [
    ("Would you like ___ tea?", "some", ["any", "many", "much"],
     "表示邀请或请求的疑问句中用 some。"),
    ("I don't have ___ money with me.", "any", ["some", "many", "much"],
     "否定句中用 any。"),
    ("___ of the students have finished the task.", "Some", ["Any", "Much", "A"],
     "肯定句表示「一些」用 some。"),
    ("If you have ___ questions, please ask.", "any", ["some", "much", "a"],
     "条件句中用 any。"),
    ("He is ___ of a musician.", "something", ["anything", "some", "any"],
     "something of a + 名词，表示「有点像个……」。"),
]


def _g_someany(rng: random.Random) -> dict:
    stem, ans, wrongs, why = rng.choice(SOMEANY)
    return _choice(rng, stem, ans, wrongs, why,
                   trap="some 多用于肯定句与表示邀请的疑问句，any 多用于否定句与条件句。")


# ------------------------------------------------------------------ 22. 强调句

CLEFT_ITEMS = [
    ("___ was in the park that I met her.", "It", ["That", "This", "There"],
     "强调句结构是 It is / was ... that / who ...。"),
    ("It was not until midnight ___ he came back.", "that", ["when", "then", "which"],
     "not until 的强调句用 It was not until ... that ...。"),
    ("It was in 2015 ___ he graduated from college.", "that", ["when", "which", "then"],
     "强调时间状语时连接词仍用 that，不用 when。"),
]


def _g_cleft(rng: random.Random) -> dict:
    stem, ans, wrongs, why = rng.choice(CLEFT_ITEMS)
    return _choice(rng, stem, ans, wrongs, why,
                   trap="去掉 It is/was 和 that 后句子仍完整，才是强调句。")


# ------------------------------------------------------------------ 23. 副词与形容词

ADV_ITEMS = [
    ("He works ___ (hard) than anyone else in the team.", "harder",
     "hard 既是形容词也是副词，比较级是 harder，不是 hardlier。"),
    ("He ___ (hard) ever goes to the cinema.", "hardly",
     "hardly 意为「几乎不」，与 hard（努力地）意思完全不同。"),
    ("She arrived ___ (late) for the meeting.", "late",
     "late 本身就是副词，lately 意为「最近」。"),
    ("I haven't seen him ___ (late).", "lately",
     "lately 表示「最近」，常与完成时连用。"),
    ("The soup tastes ___ (good).", "good",
     "taste 是系动词，后接形容词作表语。"),
    ("He looked at me ___ (angry).", "angrily",
     "修饰动词 looked 要用副词。"),
]


def _g_adv(rng: random.Random) -> dict:
    stem, ans, why = rng.choice(ADV_ITEMS)
    return _fill(stem, ans, why, accept=[ans])




# ------------------------------------------------------------------ 24. 将来表达的选择

FUTURE_ITEMS = [
    ("Look at those dark clouds! It ___ rain at any moment.",
     "is going to", ["will", "is raining", "rains"],
     "有明显迹象的预测用 be going to。"),
    ("I have already decided. I ___ study medicine.",
     "am going to", ["will", "am studying", "study"],
     "事先已经决定好的打算用 be going to。"),
    ("The phone is ringing. I ___ answer it.",
     "will", ["am going to", "am answering", "answer"],
     "说话瞬间临时作出的决定用 will。"),
    ("Don't worry about the boxes. I ___ help you.",
     "will", ["am going to", "am helping", "help"],
     "当场给出的承诺用 will。"),
    ("We ___ visit the museum next Friday; the tickets are booked.",
     "are going to", ["will", "visit", "are visiting"],
     "已经安排好的计划用 be going to。"),
    ("The train ___ at 7:30 tomorrow morning.",
     "leaves", ["will leave", "is leaving", "left"],
     "按时刻表发生的将来动作用一般现在时。"),
    ("The film ___ at eight tonight.",
     "starts", ["will start", "is starting", "started"],
     "按节目表开始，用一般现在时表将来。"),
    ("School ___ on September 1st.",
     "begins", ["will begin", "is beginning", "began"],
     "校历、日程规定的将来动作用一般现在时。"),
]


def _g_future(rng: random.Random) -> dict:
    stem, ans, wrongs, why = rng.choice(FUTURE_ITEMS)
    return _choice(rng, stem, ans, wrongs, why,
                   trap="先判断是临时决定、事先计划，还是时刻表安排。")


# ------------------------------------------------------------------ 25. 时态呼应

AGREE_ITEMS = [
    ("He said that he ___ (be) busy that day.",
     "was", ["is", "has been", "will be"],
     "主句是过去时，从句表示同一时间，用一般过去时。"),
    ("She told me she ___ (finish) the work already.",
     "had finished", ["has finished", "finished", "will finish"],
     "主句过去时，从句动作发生在之前，用过去完成时。"),
    ("The teacher said that light ___ (travel) faster than sound.",
     "travels", ["traveled", "had traveled", "will travel"],
     "客观真理不受时态呼应限制，仍用一般现在时。"),
    ("He asked me when I ___ (come) back.",
     "would come", ["will come", "came", "have come"],
     "主句过去时，从句用过去将来时。"),
    ("She said she ___ (live) there since 2010.",
     "had lived", ["has lived", "lives", "was living"],
     "主句过去时，since 引出的持续到过去某时的状态用过去完成时。"),
]


def _g_agreement(rng: random.Random) -> dict:
    stem, ans, wrongs, why = rng.choice(AGREE_ITEMS)
    return _choice(rng, stem, ans, wrongs, why,
                   trap="先看主句时态，再判断从句动作与主句动作的先后。")


# ------------------------------------------------------------------ 26. 双宾语被动

DOUBLE_ITEMS = [
    ("A new bike ___ him on his birthday.",
     "was given to", ["was given", "gave to", "was given for"],
     "give sb sth 变被动：sb be given sth 或 sth be given to sb。"),
    ("He ___ a second chance after the interview.",
     "was offered", ["was offered to", "offered", "was offering"],
     "offer sb sth 变被动：sb be offered sth。"),
    ("The prize ___ the best student.",
     "was awarded to", ["was awarded", "awarded to", "was awarding"],
     "award sth to sb 变被动时保留 to。"),
    ("She ___ the news as soon as she arrived.",
     "was told", ["told", "was told to", "tells"],
     "tell sb sth 变被动：sb be told sth。"),
    ("A letter ___ her last week.",
     "was sent to", ["was sent", "sent to", "was sending to"],
     "send sb sth 变被动：sth be sent to sb。"),
]


def _g_double_object(rng: random.Random) -> dict:
    stem, ans, wrongs, why = rng.choice(DOUBLE_ITEMS)
    return _choice(rng, stem, ans, wrongs, why,
                   trap="双宾语动词有两种被动，介词 to / for 不能随手丢。")


# ------------------------------------------------------------------ 27. 非谓语：形式选择
#
# 非谓语这一块能模板化的前提是「空处的形式由结构唯一决定」。所以每个模板都
# 先锁定一个语法信号（介词、使役动词、序数词、too/enough、be said），再让
# 主语 × 动词 × 宾语去变。凡是 to do 与 doing 都说得通的空位，一律不做填空，
# 否则判分必然冤枉人。

# (原形, 现在分词, 过去分词, 宾语)
NF_VO = [
    ("finish", "finishing", "finished", "the report"),
    ("repair", "repairing", "repaired", "the bike"),
    ("clean", "cleaning", "cleaned", "the classroom"),
    ("write", "writing", "written", "the letter"),
    ("visit", "visiting", "visited", "the museum"),
    ("prepare", "preparing", "prepared", "the dinner"),
    ("deliver", "delivering", "delivered", "the parcel"),
    ("translate", "translating", "translated", "the passage"),
    ("paint", "painting", "painted", "the wall"),
    ("design", "designing", "designed", "the poster"),
    ("check", "checking", "checked", "the answers"),
    ("water", "watering", "watered", "the flowers"),
    ("build", "building", "built", "the house"),
    ("sell", "selling", "sold", "the old car"),
    ("fix", "fixing", "fixed", "the computer"),
    ("print", "printing", "printed", "the file"),
]

NF_PRON = ["him", "her", "them", "us", "me", "Tom", "Lucy"]

NF_SUBJ = [
    ("The manager", True), ("Miss Li", True), ("Tom", True), ("Lucy", True),
    ("My parents", False), ("The students", False), ("We", False), ("They", False),
]

# 接 sb to do 的动词（过去式）
NF_INF_PRED = ["asked", "told", "expected", "invited", "wanted",
               "advised", "reminded", "persuaded"]

# 接 doing 的动词 → (动词, 原形, 现在分词, 宾语)
# 这些动词后只能接动名词，接不定式是明确错误，所以填空答案唯一。
# 分词形式直接写在池里：靠 e 结尾 / 双写规则去拼，会在 open / visit / win
# 这类词上出错，宁可多写一列。
NF_GER_PAIRS = [
    ("enjoy", "read", "reading", "novels"),
    ("mind", "open", "opening", "the window"),
    ("avoid", "make", "making", "the same mistake"),
    ("finish", "write", "writing", "the report"),
    ("keep", "ask", "asking", "the same question"),
    ("practice", "speak", "speaking", "English"),
    ("consider", "change", "changing", "the plan"),
    ("imagine", "live", "living", "on the moon"),
    ("deny", "break", "breaking", "the window"),
    ("risk", "lose", "losing", "the job"),
]

# be + 形容词 + 介词 + doing
NF_PREP_PAIRS = [
    ("good at", "play", "playing", "basketball"),
    ("interested in", "learn", "learning", "English"),
    ("afraid of", "make", "making", "mistakes"),
    ("proud of", "win", "winning", "the prize"),
    ("tired of", "do", "doing", "the same work"),
    ("fond of", "collect", "collecting", "stamps"),
    ("crazy about", "play", "playing", "computer games"),
    ("worried about", "lose", "losing", "the job"),
]

# 固定句型里的动名词（答案唯一，因为句型本身锁死了形式）
NF_FIXED_GERUND = [
    ("It is no use", "argue", "arguing", "with him",
     "It is no use doing sth 是固定句型，it 是形式主语。"),
    ("It is no good", "stay", "staying", "up late",
     "It is no good doing sth 是固定句型。"),
    ("The film is worth", "see", "seeing", "",
     "be worth doing 用主动形式表达被动意义。"),
    ("He is busy", "prepare", "preparing", "the report",
     "be busy doing sth 表示忙于做某事。"),
    ("She couldn't help", "laugh", "laughing", "when she heard it",
     "can't help doing 表示忍不住做某事。"),
    ("I don't feel like", "eat", "eating", "anything",
     "feel like doing 表示想要做某事。"),
    ("He gave up", "smoke", "smoking", "last year",
     "give up doing 表示戒掉某事。"),
    ("They succeeded in", "solve", "solving", "the problem",
     "succeed in doing 表示成功做成某事。"),
    ("She is used to", "get", "getting", "up early",
     "be used to doing 表示习惯于做某事。"),
    ("The boy is afraid of", "stay", "staying", "at home alone",
     "be afraid of doing 表示害怕做某事。"),
]

# 不定式作定语：have sth to do / the first to do
NF_ATTR_HAVE = [
    ("a lot of homework", "do", "tonight"),
    ("a letter", "write", ""),
    ("a book", "read", ""),
    ("some clothes", "wash", ""),
    ("a report", "finish", "before Friday"),
    ("a question", "ask", ""),
    ("a bike", "repair", ""),
    ("some flowers", "water", ""),
]

NF_ATTR_ORD = [
    ("the first person", "arrive"),
    ("the last student", "leave"),
    ("the only person", "know the truth"),
    ("the first one", "answer the question"),
    ("the next person", "speak"),
    ("the only student", "pass the exam"),
    ("the first man", "walk on the moon"),
    ("the last one", "hand in the paper"),
]

# 不定式作目的状语
NF_ADV_PAIRS = [
    ("He got up early", "catch", "the first bus"),
    ("She saved money", "buy", "a new bike"),
    ("They went to the station", "meet", "their teacher"),
    ("We stayed up late", "finish", "the report"),
    ("He ran fast", "catch", "the train"),
    ("She turned down the music", "not wake", "the baby"),
    ("I came here", "see", "you"),
    ("He worked hard", "pass", "the exam"),
]

# too ... to do / adj + enough to do
NF_TOO = [
    ("The box is too heavy", "carry"),
    ("The coffee is too hot", "drink"),
    ("He was too tired", "walk any further"),
    ("The problem is too difficult", "solve"),
    ("The coat is too small", "wear"),
    ("The road is too narrow", "pass"),
]

NF_ENOUGH = [
    ("He is old enough", "drive"),
    ("She is strong enough", "lift the box"),
    ("The room is big enough", "hold fifty people"),
    ("The boy is tall enough", "reach the shelf"),
    ("The ice is thick enough", "walk on"),
    ("The soup is cool enough", "drink"),
]

# 用在「人」作主语的模板里，避免 The manager was the only student 这种身份错配
NF_PERSON = ["Tom", "Lucy", "He", "She", "My brother", "The boy", "The girl"]


def _nf_be(sing: bool) -> str:
    return "is" if sing else "are"


def _g_nf_obj(rule: str):
    """非谓语作主语 / 宾语 / 宾补 / 定语 / 状语的形式选择。"""

    def g(rng: random.Random) -> dict:
        subj, sing = rng.choice(NF_SUBJ)

        if rule == "want":
            pred = rng.choice(NF_INF_PRED)
            pron = rng.choice(NF_PRON)
            base, _ing, _pp, obj = rng.choice(NF_VO)
            stem = f"{subj} {pred} {pron} ___ ({base}) {obj}."
            return _fill(stem, f"to {base}",
                         "不定式作宾语补足语，说明宾语要做的动作；ask / tell / want 这类动词后必须带 to。")

        if rule == "make":
            pred = rng.choice(["made", "let"])
            pron = rng.choice(NF_PRON)
            base, _ing, _pp, obj = rng.choice(NF_VO)
            stem = f"{subj} {pred} {pron} ___ ({base}) {obj}."
            return _fill(stem, base,
                         "make / let 后接不带 to 的不定式作宾补，变被动时才把 to 还原。")

        if rule == "enjoy":
            v, _base, ing, obj = rng.choice(NF_GER_PAIRS)
            stem = f"{subj} {v}{'s' if sing else ''} ___ ({_base}) {obj}."
            return _fill(stem, ing,
                         "enjoy / mind / avoid / finish 这类动词只能接动名词作宾语。")

        if rule == "prep":
            adj, _base, ing, obj = rng.choice(NF_PREP_PAIRS)
            stem = f"{subj} {_nf_be(sing)} {adj} ___ ({_base}) {obj}."
            return _fill(stem, ing, "介词后面接动名词，不能用不定式。")

        if rule == "fixed":
            pre, base, ans, tail, why = rng.choice(NF_FIXED_GERUND)
            stem = f"{pre} ___ ({base}) {tail}." if tail else f"{pre} ___ ({base})."
            return _fill(stem, ans, why)

        if rule == "it-subj":
            adj = rng.choice(["important", "necessary", "difficult", "easy",
                              "useful", "impolite", "wise", "dangerous"])
            base, _ing, _pp, obj = rng.choice(NF_VO)
            stem = f"It is {adj} ___ ({base}) {obj}."
            return _fill(stem, f"to {base}",
                         "it 作形式主语，真正的主语是不定式短语 to do sth。")

        if rule == "attr-have":
            noun, base, tail = rng.choice(NF_ATTR_HAVE)
            s1 = rng.choice(NF_PERSON)
            stem = f"{s1} has {noun} ___ ({base}) {tail}." if tail else f"{s1} has {noun} ___ ({base})."
            return _fill(stem, f"to {base}",
                         "不定式作后置定语，修饰前面的名词；have sth to do 表示有某事要做。")

        if rule == "attr-ord":
            noun, base = rng.choice(NF_ATTR_ORD)
            s1 = rng.choice(NF_PERSON)
            stem = f"{s1} was {noun} ___ ({base})."
            return _fill(stem, f"to {base}",
                         "序数词、最高级、the only / the last 后的定语用不定式。")

        if rule == "adv":
            main, base, obj = rng.choice(NF_ADV_PAIRS)
            neg = base.startswith("not ")
            verb = base[4:] if neg else base
            ans = f"not to {verb}" if neg else f"to {verb}"
            return _fill(f"{main} ___ ({base}) {obj}.", ans,
                         "不定式作目的状语；否定形式是 not to do，not 要放在 to 前面。")

        if rule == "too-enough":
            if rng.random() < 0.5:
                pre, base = rng.choice(NF_TOO)
                why = "too + 形容词 + to do 表示「太……以致不能」。"
            else:
                pre, base = rng.choice(NF_ENOUGH)
                why = "形容词 + enough + to do 表示「足够……能做」。"
            return _fill(f"{pre} ___ ({base}).", f"to {base}", why)

        raise ValueError(rule)

    return g


# ------------------------------------------------------------------ 28. 非谓语：时态与语态

# (前半句, 原形, 过去分词, 宾语, 句末状语)
NF_SAY_PERF = [
    ("He seems", "finish", "finished", "the report", "already"),
    ("She is said", "leave", "left", "the country", ""),
    ("The team is believed", "win", "won", "the match", ""),
    ("He is reported", "break", "broken", "the record", ""),
    ("They seem", "know", "known", "the answer", ""),
    ("She appears", "forget", "forgotten", "the appointment", ""),
    ("He seems", "read", "read", "the book", "already"),
    ("They are said", "move", "moved", "to another city", ""),
]

# be said / be likely 后的被动不定式（答案写在池里，避免拼接出错）
NF_SAY_PASS = [
    ("The bridge is said", "build", "in 1990", "to have been built"),
    ("The book is believed", "translate", "into many languages", "to have been translated"),
    ("The castle is reported", "destroy", "in the war", "to have been destroyed"),
    ("The house is said", "sell", "already", "to have been sold"),
    ("She is likely", "choose", "as the new leader", "to be chosen"),
    ("The plan is expected", "accept", "by the committee", "to be accepted"),
    ("He is expected", "elect", "as the chairman", "to be elected"),
    ("The song is said", "write", "in 1980", "to have been written"),
]

# 动名词被动式 being done（主动形式在这里讲不通，答案唯一）
NF_GER_PASS = [
    ("He hates", "laugh", "at by others", "being laughed"),
    ("She is afraid of", "bite", "by the dog", "being bitten"),
    ("The boy remembered", "take", "to the park by his father", "being taken"),
    ("He dislikes", "treat", "like a child", "being treated"),
    ("She can't stand", "keep", "waiting", "being kept"),
    ("He was proud of", "choose", "as the team leader", "being chosen"),
    ("The girl is afraid of", "leave", "alone at home", "being left"),
    ("He complained about", "give", "too much homework", "being given"),
    ("He hates", "ask", "about his age", "being asked"),
    ("She is afraid of", "misunderstand", "by her friends", "being misunderstood"),
    ("He is tired of", "tell", "what to do", "being told"),
    ("She was proud of", "praise", "by the teacher", "being praised"),
]


def _g_nf_tv(rule: str):
    def g(rng: random.Random) -> dict:
        subj, _sing = rng.choice(NF_SUBJ)

        if rule == "to-perf":
            pre, base, pp, obj, tail = rng.choice(NF_SAY_PERF)
            stem = f"{pre} ___ ({base}) {obj} {tail}." if tail else f"{pre} ___ ({base}) {obj}."
            return _fill(stem, f"to have {pp}",
                         "不定式完成式 to have done 表示动作发生在谓语动词之前。")

        if rule == "to-pass":
            pre, base, tail, ans = rng.choice(NF_SAY_PASS)
            stem = f"{pre} ___ ({base}) {tail}."
            return _fill(stem, ans,
                         "不定式的被动式 to be done 表示被动；若动作先于谓语，用 to have been done。")

        if rule == "ger-pass":
            pre, base, tail, ans = rng.choice(NF_GER_PASS)
            stem = f"{pre} ___ ({base}) {tail}."
            return _fill(stem, ans,
                         "动名词的被动式 being done：逻辑主语是动作的承受者，不能用主动形式。")

        raise ValueError(rule)

    return g


# ------------------------------------------------------------------ 29. 非谓语：分词

# 现在分词作后置定语（名词 ... is ...）
NF_ING_ATTR = [
    ("The man", "stand", "standing", "at the gate", "is our headmaster"),
    ("The girl", "sing", "singing", "in the next room", "is my sister"),
    ("The boy", "play", "playing", "football on the playground", "is my cousin"),
    ("The woman", "talk", "talking", "to the teacher", "is Tom's mother"),
    ("The students", "read", "reading", "in the library", "are from Class Two"),
    ("The dog", "run", "running", "after the ball", "belongs to Lucy"),
    ("The car", "park", "parking", "outside the gate", "is mine"),
    ("The children", "dance", "dancing", "in the hall", "are from Grade One"),
    ("The bird", "fly", "flying", "over the lake", "is a wild goose"),
    ("The boy", "ride", "riding", "a bike", "is my brother"),
    ("The workers", "build", "building", "the bridge", "are from the city"),
    ("The girl", "draw", "drawing", "a picture", "is very quiet"),
]

# 过去分词作后置定语
NF_PP_ATTR = [
    ("The window", "break", "broken", "yesterday", "has been repaired"),
    ("The book", "write", "written", "by Lu Xun", "is very popular"),
    ("The bridge", "build", "built", "in 1990", "is still in use"),
    ("The car", "steal", "stolen", "last night", "was found this morning"),
    ("The letter", "type", "typed", "by the secretary", "is on the desk"),
    ("The house", "paint", "painted", "last year", "looks new"),
    ("The tree", "plant", "planted", "ten years ago", "is very tall now"),
    ("The song", "sing", "sung", "by the children", "was recorded"),
    ("The letter", "send", "sent", "last week", "has arrived"),
    ("The cake", "make", "made", "by my mother", "tastes delicious"),
    ("The road", "repair", "repaired", "last month", "is much smoother"),
    ("The photos", "take", "taken", "in Beijing", "are on the wall"),
]

# 现在分词作状语（逻辑主语与主句主语一致）
NF_ING_ADV = [
    ("walk", "along the street", "I met an old friend"),
    ("see", "the teacher coming", "the students stood up"),
    ("not know", "what to do", "she asked for help"),
    ("work", "in the factory for years", "he knows the process well"),
    ("hear", "the noise", "we ran out of the room"),
    ("not have", "enough money", "he couldn't buy the book"),
    ("look", "out of the window", "she saw a rainbow"),
    ("sing", "a song", "the children walked into the room"),
    ("feel", "very tired", "he went to bed early"),
    ("not want", "to be late", "she took a taxi"),
    ("smile", "at me", "he asked if I was ready"),
    ("lie", "on the grass", "we watched the clouds"),
]

# 过去分词作状语
NF_PP_ADV = [
    ("give", "Given", "more time", "we could do it better"),
    ("encourage", "Encouraged", "by the teacher", "he worked harder"),
    ("face", "Faced", "with difficulties", "he never gave up"),
    ("invite", "Invited", "to the party", "she felt very happy"),
    ("catch", "Caught", "in the rain", "he got a bad cold"),
    ("tell", "Told", "that the exam was cancelled", "the students cheered"),
    ("praise", "Praised", "by the manager", "he worked even harder"),
    ("lose", "Lost", "in thought", "he didn't hear the bell"),
    ("shock", "Shocked", "by the news", "she couldn't say a word"),
    ("leave", "Left", "alone at home", "the child began to cry"),
    ("move", "Moved", "by the film", "many people cried"),
    ("tire", "Tired", "after the long walk", "we sat down to rest"),
]

# 现在分词的完成式作状语
NF_PERF_ADV = [
    ("finish", "Having finished", "his homework", "he went out to play"),
    ("live", "Having lived", "there for years", "he knows the city well"),
    ("eat", "Having eaten", "his dinner", "he went to bed"),
    ("read", "Having read", "the letter twice", "she put it away"),
    ("work", "Having worked", "all day", "they were very tired"),
    ("lose", "Having lost", "his key", "he had to wait outside"),
    ("see", "Having seen", "the film twice", "she didn't want to watch it again"),
    ("finish", "Having finished", "the report", "she sent it to the manager"),
    ("wait", "Having waited", "for an hour", "he left the station"),
    ("spend", "Having spent", "all his money", "he walked home"),
    ("write", "Having written", "the letter", "he mailed it at once"),
    ("hear", "Having heard", "the news", "she burst into tears"),
]

# 过去分词作宾补：have / get / find + 宾语 + done
NF_OBJCOMP = [
    ("I had my hair", "cut", "cut", "yesterday",
     "have sth done 表示「让某事被别人做」，宾语与分词是被动关系。"),
    ("He found the door", "lock", "locked", "when he came back",
     "find sth done 表示发现某事已经被完成。"),
    ("We got the roof", "repair", "repaired", "last month",
     "get sth done 表示请别人做某事。"),
    ("She had her bike", "fix", "fixed", "yesterday",
     "have sth done 表示让别人修，不是自己修。"),
    ("They found the window", "break", "broken", "in the morning",
     "find sth done 表示发现宾语处于被完成的状态。"),
    ("I had my photo", "take", "taken", "at the studio",
     "have sth done：照片是被拍的。"),
    ("He had his car", "wash", "washed", "yesterday",
     "have sth done：车是被洗的。"),
    ("She found the room", "clean", "cleaned", "already",
     "find sth done：房间已经被打扫。"),
    ("We had the house", "paint", "painted", "last summer",
     "have sth done：房子是被粉刷的。"),
    ("They found the money", "hide", "hidden", "under the bed",
     "find sth done：钱是被藏起来的。"),
    ("He had his watch", "repair", "repaired", "in the shop",
     "have sth done：手表是被修的。"),
    ("She got her hair", "cut", "cut", "short last week",
     "get sth done：头发是被剪的。"),
]

# with 复合结构：doing / done / to do 由宾语与分词的关系决定
# 第 4 项是句末成分，保证题干本身是个完整句子
NF_WITH = [
    ("He sat there with his eyes", "fix", "fixed", " on the screen",
     "eyes 与 fix 是被动关系，用过去分词。"),
    ("With the work", "do", "done", ", we went home",
     "work 与 do 是被动关系，用过去分词。"),
    ("With so much homework", "do", "to do", ", he can't go out",
     "表示还没做的动作，用不定式。"),
    ("She fell asleep with the light", "burn", "burning", "",
     "light 与 burn 是主动进行关系，用现在分词。"),
    ("With the children", "play", "playing", ", she cleaned the room",
     "children 与 play 是主动关系，用现在分词。"),
    ("He stood there with his arms", "cross", "crossed", "",
     "arms 与 cross 是被动关系，用过去分词。"),
    ("With the door", "lock", "locked", ", nobody could get in",
     "door 与 lock 是被动关系，用过去分词。"),
    ("He sat there with nothing", "do", "to do", "",
     "表示「无事可做」，用不定式。"),
    ("With the meeting", "go on", "going on", ", nobody left the room",
     "meeting 与 go on 是主动进行关系。"),
    ("With his homework", "finish", "finished", ", he went out to play",
     "homework 与 finish 是被动关系。"),
    ("With the problem", "solve", "solved", ", we all felt relieved",
     "problem 与 solve 是被动关系。"),
    ("With all the windows", "close", "closed", ", the room was very hot",
     "windows 与 close 是被动关系。"),
]

# 独立主格：现在分词（名词与分词是主动关系）
NF_ABS_ING = [
    ("The bell", "ring", "ringing", ["the students left the classroom",
                                     "the class began", "we all looked up"]),
    ("The rain", "fall", "falling", ["we stayed indoors",
                                     "the ground was wet", "the match was cancelled"]),
    ("The sun", "set", "setting", ["we went home",
                                   "the sky turned red", "the air got cooler"]),
    ("The baby", "sleep", "sleeping", ["she cleaned the room quietly",
                                       "the house was quiet", "we spoke in a low voice"]),
    ("The dog", "bark", "barking", ["he woke up at once",
                                    "the thief ran away", "the neighbours complained"]),
    ("The teacher", "come in", "coming in", ["we all stood up",
                                             "the room fell silent", "everyone stopped talking"]),
    ("The wind", "blow", "blowing", ["the trees moved",
                                     "the windows shook", "the fire spread quickly"]),
    ("The children", "play", "playing", ["the room was noisy",
                                         "she couldn't read", "the afternoon passed quickly"]),
]

# 独立主格：过去分词（名词与分词是被动关系）
NF_ABS_PP = [
    ("The work", "finish", "finished", ["we went home",
                                        "they left the office",
                                        "she felt relieved"]),
    ("The homework", "finish", "finished", ["the children went out to play",
                                            "they watched TV",
                                            "she checked the answers"]),
    ("The report", "write", "written", ["she sent it to the manager",
                                        "he printed two copies",
                                        "the meeting began"]),
    ("The project", "complete", "completed", ["the team took a break",
                                              "we held a party",
                                              "the client was satisfied"]),
    ("The task", "complete", "completed", ["everyone went home",
                                           "he felt relaxed",
                                           "the manager praised the team"]),
    ("The job", "do", "done", ["we closed the shop",
                               "they went for dinner",
                               "she locked the door"]),
    ("The letter", "write", "written", ["he put it in the envelope",
                                        "she mailed it at once",
                                        "it was ready to send"]),
    ("The plan", "make", "made", ["we started to work",
                                  "the team moved quickly",
                                  "everyone knew what to do"]),
]


def _nf_ing(v: str) -> str:
    """句首用，需要大写；不规则拼写直接查表，别指望加 ing 规则。"""
    neg = v.startswith("not ")
    base = v[4:] if neg else v
    ing = {"have": "having", "see": "seeing", "be": "being",
           "die": "dying", "lie": "lying", "free": "freeing"}.get(base, base + "ing")
    return ("Not " + ing) if neg else ing


def _g_nf_part(rule: str):
    """分词类：定语 / 状语 / 完成式 / 宾补 / with / 独立主格。"""

    def g(rng: random.Random) -> dict:
        if rule == "ing-attr":
            noun, base, ing, tail, pred = rng.choice(NF_ING_ATTR)
            return _fill(f"{noun} ___ ({base}) {tail} {pred}.", ing,
                         "现在分词短语作后置定语，名词与分词是主动关系。")

        if rule == "pp-attr":
            noun, base, pp, tail, pred = rng.choice(NF_PP_ATTR)
            return _fill(f"{noun} ___ ({base}) {tail} {pred}.", pp,
                         "过去分词短语作后置定语，名词与分词是被动关系。")

        if rule == "ing-adv":
            v, tail, main = rng.choice(NF_ING_ADV)
            # 括号里保留 not，否则「Having」与「Not having」都说得通，答案不唯一
            return _fill(f"___ ({v}) {tail}, {main}.", _nf_ing(v),
                         "现在分词作状语，逻辑主语必须与主句主语一致；否定形式把 not 放最前面。")

        if rule == "pp-adv":
            _v, pp, tail, main = rng.choice(NF_PP_ADV)
            return _fill(f"___ ({_v}) {tail}, {main}.", pp,
                         "过去分词作状语，主句主语是动作的承受者。")

        if rule == "perf-adv":
            v, ing, tail, main = rng.choice(NF_PERF_ADV)
            return _fill(f"___ ({v}) {tail}, {main}.", ing,
                         "现在分词的完成式 having done 表示动作发生在谓语之前。")

        if rule == "objcomp":
            pre, v, pp, tail, why = rng.choice(NF_OBJCOMP)
            return _fill(f"{pre} ___ ({v}) {tail}.", pp, why)

        if rule == "with":
            pre, v, ans, tail, why = rng.choice(NF_WITH)
            return _fill(f"{pre} ___ ({v}){tail}.", ans, why)

        if rule == "abs-ing":
            noun, v, ing, mains = rng.choice(NF_ABS_ING)
            main = rng.choice(mains)
            return _fill(f"{noun} ___ ({v}), {main}.", ing,
                         "独立主格：名词与分词是主动关系，用现在分词；名词自带主语，不与主句共用。")

        if rule == "abs-pp":
            noun, v, pp, mains = rng.choice(NF_ABS_PP)
            main = rng.choice(mains)
            return _fill(f"{noun} ___ ({v}), {main}.", pp,
                         "独立主格：名词与分词是被动关系，用过去分词；不能再出现第二个谓语。")

        raise ValueError(rule)

    return g


# ------------------------------------------------------------------ 30. 非谓语：判定类

# 非谓语在句中作什么成分
NF_FUNC = [
    ('在 "He came to see me." 中，to see me 作什么成分？', "目的状语",
     ["宾语", "定语", "宾语补足语"], "不定式表示来的目的，作状语。"),
    ('在 "I have a letter to write." 中，to write 作什么成分？', "定语",
     ["状语", "宾语", "宾语补足语"], "修饰名词 letter，作后置定语。"),
    ('在 "She asked me to wait." 中，to wait 作什么成分？', "宾语补足语",
     ["宾语", "定语", "状语"], "补充说明宾语 me 要做的动作，作宾补。"),
    ('在 "Swimming is good for health." 中，Swimming 作什么成分？', "主语",
     ["宾语", "定语", "状语"], "动名词在句首作主语。"),
    ('在 "The man standing there is my uncle." 中，standing there 作什么成分？', "定语",
     ["状语", "宾语补足语", "主语"], "修饰 the man，作后置定语。"),
    ('在 "He sat by the window, reading a book." 中，reading a book 作什么成分？', "伴随状语",
     ["定语", "宾语补足语", "主语"], "与主句动作同时发生，作伴随状语。"),
    ('在 "I had my bike repaired." 中，repaired 作什么成分？', "宾语补足语",
     ["定语", "状语", "谓语"], "补充说明宾语 my bike 的状态，作宾补。"),
    ('在 "Given more time, we can do it better." 中，Given more time 作什么成分？', "条件状语",
     ["定语", "宾语", "宾语补足语"], "过去分词短语表示条件，作状语。"),
    ('在 "He is said to have left the country." 中，to have left the country 作什么成分？', "主语补足语",
     ["宾语", "定语", "状语"], "被动句中补充说明主语 he，作主语补足语。"),
    ('在 "The boy was seen playing football." 中，playing football 作什么成分？', "主语补足语",
     ["宾语补足语", "定语", "状语"], "主动句的宾补在被动句里变为主语补足语。"),
    ('在 "There is nothing to worry about." 中，to worry about 作什么成分？', "定语",
     ["状语", "宾语", "主语"], "修饰 nothing，作后置定语。"),
    ('在 "He left, saying nothing." 中，saying nothing 作什么成分？', "伴随状语",
     ["定语", "宾语", "主语"], "表示离开时的伴随动作，作状语。"),
]

# 一句一谓语：非谓语不能当谓语用
# 题干必须逐条不同，否则 make() 会把它们当成同一道题去重掉。
NF_BOUNDARY = [
    ("下面哪句用非谓语作后置定语，语法正确？", "The man standing there is my uncle.",
     ["The man stands there is my uncle.",
      "The man is standing there is my uncle.",
      "The man stood there is my uncle."],
     "一个句子只能有一个谓语，其余动词要用非谓语形式或加关系词。"),
    ("下面哪句的定语从句用法正确？", "The girl who is singing is my sister.",
     ["The girl sings is my sister.",
      "The girl is singing is my sister.",
      "The girl who singing is my sister."],
     "两个谓语之间必须有关系词连接，且关系词后要有完整谓语。"),
    ("下面哪句用分词作原因状语，语法正确？", "Being ill, he didn't come to school.",
     ["Being ill, so he didn't come to school.",
      "He was ill, didn't come to school.",
      "He being ill, so he didn't come to school."],
     "分词短语已经表达原因，不能再保留连词 so。"),
    ("下面哪句的独立主格结构正确？", "The work finished, we went home.",
     ["The work was finished, we went home.",
      "The work finishing, we went home.",
      "The work finishes, we went home."],
     "独立主格用非谓语，不能再出现第二个谓语 was。"),
    ("下面哪句用分词作伴随状语，语法正确？", "He sat there, reading a newspaper.",
     ["He sat there, read a newspaper.",
      "He sat there and reading a newspaper.",
      "He sat there, reads a newspaper."],
     "同一主语的第二个动作要用现在分词作伴随状语。"),
    ("下面哪句用过去分词作后置定语，语法正确？",
     "The letter written by Tom was sent yesterday.",
     ["The letter wrote by Tom was sent yesterday.",
      "The letter writing by Tom was sent yesterday.",
      "The letter was written by Tom was sent yesterday."],
     "letter 与 write 是被动关系，用过去分词作定语。"),
    ("下面哪句用完成式分词作状语，语法正确？", "Having finished his work, he went home.",
     ["Finished his work, he went home.",
      "Having finished his work, and he went home.",
      "He having finished his work, went home."],
     "动作先于谓语用 having done；分词短语后不能再用 and。"),
    ("下面哪句用过去分词作宾语补足语，语法正确？", "I had my bike repaired yesterday.",
     ["I had my bike repair yesterday.",
      "I had my bike repairing yesterday.",
      "I had my bike be repaired yesterday."],
     "have sth done：宾语与分词是被动关系。"),
]

# 悬垂修饰：分词短语的逻辑主语必须与主句主语一致
NF_DANGLING = [
    ("Walking down the street, ____", "I saw a beautiful garden.",
     ["the trees were green.", "the weather was fine.", "a dog ran past me."],
     "walking 的发出者必须是主句主语。"),
    ("Looking out of the window, ____", "she saw a rainbow.",
     ["the sky was clear.", "the rain had stopped.", "a bird flew by."],
     "looking 的发出者必须是主句主语。"),
    ("Having finished the work, ____", "we went out for dinner.",
     ["the evening came.", "it was already dark.", "the office was empty."],
     "having finished 的发出者是 we。"),
    ("Encouraged by the teacher, ____", "he worked even harder.",
     ["his grades improved.", "the exam was easy.", "the class was quiet."],
     "encouraged 的承受者是 he。"),
    ("To pass the exam, ____", "you must work harder.",
     ["hard work is necessary.", "the exam must be easy.", "more time is needed."],
     "不定式的逻辑主语应与主句主语一致。"),
    ("While reading the book, ____", "I found many useful expressions.",
     ["the phone rang.", "it began to rain.", "the room was quiet."],
     "reading 的发出者是 I，不能换成别的名词。"),
    ("Frightened by the noise, ____", "the girl ran out of the room.",
     ["the room was empty.", "it was very dark.", "the door was open."],
     "frightened 的承受者是 the girl。"),
    ("Sitting under the tree, ____", "we talked about our plans.",
     ["the sun was hot.", "the wind blew hard.", "the afternoon was long."],
     "sitting 的发出者是 we。"),
    ("Standing on the top of the tower, ____", "we could see the whole city.",
     ["the city looked beautiful.", "the wind was strong.", "it was very cold."],
     "standing 的发出者是 we。"),
    ("Having read the book twice, ____", "she could answer every question.",
     ["the questions were easy.", "the book was interesting.", "it took her a week."],
     "having read 的发出者是 she。"),
    ("Surprised by the news, ____", "he didn't know what to say.",
     ["the news spread quickly.", "it was hard to believe.", "the room fell silent."],
     "surprised 的承受者是 he。"),
    ("Driving to work this morning, ____", "I heard the news on the radio.",
     ["the traffic was heavy.", "it began to rain.", "the road was closed."],
     "driving 的发出者是 I。"),
]

# 并列结构：形式必须一致
NF_PARALLEL = [
    ("He likes swimming, playing football and ____.", "riding a bike",
     ["to ride a bike", "ride a bike", "rides a bike"],
     "并列成分都用动名词，形式一致。"),
    ("She spent the afternoon cleaning the room and ____.", "washing the clothes",
     ["wash the clothes", "to wash the clothes", "washed the clothes"],
     "spend time doing 结构中 and 前后都是动名词。"),
    ("She went home, took a shower and ____.", "went to bed",
     ["going to bed", "to go to bed", "go to bed"],
     "并列谓语都用过去式。"),
    ("To finish the work on time, we should plan carefully and ____.", "work hard",
     ["working hard", "to work hard", "worked hard"],
     "and 前后都是不定式结构，第二个省略 to。"),
    ("He is good at singing and ____.", "dancing",
     ["to dance", "dance", "danced"],
     "介词 at 后并列两个动名词。"),
    ("The job requires patience, care and ____.", "hard work",
     ["working hard", "to work hard", "work hard"],
     "前面并列的是名词，后面也要用名词。"),
    ("She enjoys singing and ____.", "dancing",
     ["to dance", "dance", "danced"],
     "enjoy 后并列两个动名词，前面给了 singing，后面必须是 -ing。"),
    ("He wants to join the club and ____ a member.", "become",
     ["becoming", "became", "becomes"],
     "and 前后都是不定式，第二个省略 to，动词用原形。"),
    ("He asked me to sit down and ____ for a moment.", "wait",
     ["waiting", "waited", "waits"],
     "ask sb to do and (to) do，第二个 to 可省略，动词仍用原形。"),
    ("She is responsible for cleaning the office and ____ the mail.", "answering",
     ["answer", "to answer", "answered"],
     "for 后并列两个动名词。"),
    ("He spent two hours ____ the report and checking the data.", "writing",
     ["write", "to write", "wrote"],
     "spend time doing 结构中 and 前后都是动名词。"),
    ("The film was exciting, moving and ____.", "well acted",
     ["well acting", "to act well", "act well"],
     "并列形容词性成分，过去分词也可作形容词。"),
]

# -ing 形容词 vs -ed 形容词
NF_ING_ED = [
    ("The film is very ___.", "interesting",
     ["interested", "interest", "interests"], "物作主语用 -ing 形容词，表示「令人……的」。"),
    ("I am ___ in the film.", "interested",
     ["interesting", "interest", "interests"], "人作主语用 -ed 形容词，表示「感到……的」。"),
    ("The lecture was so ___ that half the class fell asleep.", "boring",
     ["bored", "bore", "bores"], "lecture 令人困，用 -ing。"),
    ("The students looked ___ at the boring lecture.", "bored",
     ["boring", "bore", "bores"], "students 感到无聊，用 -ed。"),
    ("The news was ___ to everyone.", "surprising",
     ["surprised", "surprise", "surprises"], "news 令人吃惊，用 -ing。"),
    ("We were ___ at the news.", "surprised",
     ["surprising", "surprise", "surprises"], "人感到吃惊，用 -ed。"),
    ("The journey was long and ___.", "tiring",
     ["tired", "tire", "tires"], "journey 令人疲劳，用 -ing。"),
    ("The children felt ___ after the long journey.", "tired",
     ["tiring", "tire", "tires"], "children 感到疲劳，用 -ed。"),
    ("The result was ___ to all of us.", "disappointing",
     ["disappointed", "disappoint", "disappoints"], "result 令人失望，用 -ing。"),
    ("She was ___ with the result.", "disappointed",
     ["disappointing", "disappoint", "disappoints"], "人感到失望，用 -ed。"),
    ("The story was so ___ that we all laughed.", "amusing",
     ["amused", "amuse", "amuses"], "story 令人发笑，用 -ing。"),
    ("We were ___ to hear the good news.", "delighted",
     ["delighting", "delight", "delights"], "人感到高兴，用 -ed。"),
]

# 状语从句 → 独立主格
NF_CONV = [
    ('"Because the work was finished, we went home." 改写为独立主格，正确的是：',
     "The work finished, we went home.",
     ["The work finishing, we went home.",
      "The work was finished, we went home.",
      "Finished the work, we went home."],
     "从句主语与主句主语不同，保留从句主语 + 过去分词。"),
    ('"Because the weather was fine, we went out." 改写为独立主格，正确的是：',
     "The weather being fine, we went out.",
     ["The weather was fine, we went out.",
      "Being fine, we went out.",
      "The weather fine, we went out."],
     "表状态时要用 being，不能直接省略。"),
    ('"After the meeting was over, we left." 改写为独立主格，正确的是：',
     "The meeting being over, we left.",
     ["The meeting over, we left.",
      "The meeting was over, we left.",
      "Over the meeting, we left."],
     "be over 要用 being over 构成独立主格。"),
    ('"If time permits, we will visit the museum." 改写为独立主格，正确的是：',
     "Time permitting, we will visit the museum.",
     ["Time permitted, we will visit the museum.",
      "If time permitting, we will visit the museum.",
      "Permitting time, we will visit the museum."],
     "主动关系用现在分词，Time permitting 是固定表达。"),
    ('"Since the signal was given, the train started." 改写为独立主格，正确的是：',
     "The signal given, the train started.",
     ["The signal giving, the train started.",
      "Giving the signal, the train started.",
      "The signal was given, the train started."],
     "被动关系用过去分词。"),
    ('"Because the homework was finished, the children went out to play." 改写为独立主格，正确的是：',
     "The homework finished, the children went out to play.",
     ["The homework finishing, the children went out to play.",
      "Finished the homework, the children went out to play.",
      "The homework was finished, the children went out to play."],
     "homework 与 finish 是被动关系，用过去分词。"),
    ('"As the teacher came in, we all stood up." 改写为独立主格，正确的是：',
     "The teacher coming in, we all stood up.",
     ["The teacher come in, we all stood up.",
      "The teacher came in, we all stood up.",
      "Coming in the teacher, we all stood up."],
     "teacher 与 come 是主动关系，用现在分词。"),
    ('"When the sun had set, we went home." 改写为独立主格，正确的是：',
     "The sun having set, we went home.",
     ["The sun setting, we went home.",
      "The sun set, we went home.",
      "The sun was set, we went home."],
     "先于主句动作，用 having done 构成独立主格。"),
    ('"When the bell rang, the students left the classroom." 改写为独立主格，正确的是：',
     "The bell ringing, the students left the classroom.",
     ["The bell rang, the students left the classroom.",
      "The bell rung, the students left the classroom.",
      "Ringing the bell, the students left the classroom."],
     "bell 与 ring 是主动关系，用现在分词。"),
    ('"Because the weather was terrible, the flight was cancelled." 改写为独立主格，正确的是：',
     "The weather being terrible, the flight was cancelled.",
     ["The weather was terrible, the flight was cancelled.",
      "Being terrible, the flight was cancelled.",
      "The weather terrible, the flight was cancelled."],
     "表状态用 being，不能直接省略。"),
    ('"After the tickets had been sold out, we went home." 改写为独立主格，正确的是：',
     "The tickets sold out, we went home.",
     ["The tickets selling out, we went home.",
      "The tickets were sold out, we went home.",
      "Selling out the tickets, we went home."],
     "tickets 与 sell out 是被动关系，用过去分词。"),
    ('"Because his leg was injured, he couldn\'t walk." 改写为独立主格，正确的是：',
     "His leg injured, he couldn't walk.",
     ["His leg injuring, he couldn't walk.",
      "His leg was injured, he couldn't walk.",
      "Injuring his leg, he couldn't walk."],
     "leg 与 injure 是被动关系，用过去分词。"),
]

# 逻辑主语判定：-ing 还是 -ed
NF_LOGICAL = [
    ("see", "from the top of the hill", "the city looks beautiful", "Seen",
     "city 与 see 是被动关系，用过去分词。"),
    ("see", "the snake", "the girl ran away", "Seeing",
     "girl 与 see 是主动关系，用现在分词。"),
    ("compare", "with his brother", "he is more diligent", "Compared",
     "he 与 compare 是被动关系。"),
    ("compare", "the two answers", "she found a mistake", "Comparing",
     "she 与 compare 是主动关系。"),
    ("face", "with so many problems", "he felt helpless", "Faced",
     "be faced with 变分词用 Faced with。"),
    ("face", "the difficulty", "he didn't give up", "Facing",
     "he 主动面对困难，用现在分词。"),
    ("lose", "in thought", "he didn't hear the bell", "Lost",
     "be lost in 变分词用 Lost in。"),
    ("hear", "the good news", "they jumped with joy", "Hearing",
     "they 主动听到，用现在分词。"),
    ("satisfy", "with the result", "the manager praised the team", "Satisfied",
     "manager 感到满意，用过去分词（be satisfied with）。"),
    ("satisfy", "all the requirements", "the product was put on the market", "Satisfying",
     "product 主动满足要求，用现在分词。"),
    ("tire", "after the long journey", "the children fell asleep at once", "Tired",
     "children 感到疲劳，用过去分词。"),
    ("excite", "by the good news", "everyone jumped with joy", "Excited",
     "everyone 被好消息激励，用过去分词。"),
]


def _g_nf_judge(rule: str):
    """判定类：成分、句式合法性、悬垂、并列、-ing/-ed、从句转化。"""

    def g(rng: random.Random) -> dict:
        if rule == "function":
            stem, ans, wrongs, why = rng.choice(NF_FUNC)
            return _choice(rng, stem, ans, wrongs, why,
                           trap="先找被修饰或被说明的词，再看非谓语与它的关系。",
                           diff=2)

        if rule == "boundary":
            stem, ans, wrongs, why = rng.choice(NF_BOUNDARY)
            return _choice(rng, stem, ans, wrongs, why,
                           trap="数一数句子里有几个谓语：一个句子只能有一个。",
                           diff=3)

        if rule == "dangling":
            pre, ans, wrongs, why = rng.choice(NF_DANGLING)
            return _choice(rng, pre, ans, wrongs, why,
                           trap="先问「分词表示的动作用谁发出」，主句主语必须是那个人或物。",
                           diff=3)

        if rule == "parallel":
            stem, ans, wrongs, why = rng.choice(NF_PARALLEL)
            return _choice(rng, stem, ans, wrongs, why,
                           trap="把 and / or 两边的成分摆成一条线，形式必须对齐。",
                           diff=2)

        if rule == "ing-ed":
            stem, ans, wrongs, why = rng.choice(NF_ING_ED)
            return _choice(rng, stem, ans, wrongs, why,
                           trap="主语是人还是物：人「感到」用 -ed，物「令人」用 -ing。",
                           diff=1)

        if rule == "conv":
            stem, ans, wrongs, why = rng.choice(NF_CONV)
            return _choice(rng, stem, ans, wrongs, why,
                           trap="从句主语保留、谓语变分词；主动用 -ing，被动用 -ed。",
                           diff=3)

        if rule == "logical":
            v, tail, main, ans, why = rng.choice(NF_LOGICAL)
            return _fill(f"___ ({v}) {tail}, {main}.", ans, why)

        raise ValueError(rule)

    return g


# 不定式符号 to 的保留与省略
NF_TO_RET = [
    ("The little boy was made ___ the old man.", "to apologize",
     ["apologize", "apologizing", "apologized"], "make sb do 变被动后要还原 to。"),
    ("He was seen ___ the building at nine.", "to enter",
     ["enter", "entering", "entered"], "see sb do 变被动后还原 to。"),
    ("You had better ___ a doctor at once.", "see",
     ["to see", "seeing", "saw"], "had better 后接不带 to 的不定式。"),
    ("Why not ___ the teacher for help?", "ask",
     ["to ask", "asking", "asked"], "Why not 后接不带 to 的不定式。"),
    ("I would rather ___ at home tonight.", "stay",
     ["to stay", "staying", "stayed"], "would rather 后接不带 to 的不定式。"),
    ("He did nothing but ___ all day.", "complain",
     ["to complain", "complaining", "complained"], "do nothing but 后接不带 to 的不定式。"),
    ("She has no choice but ___ for him.", "to wait",
     ["wait", "waiting", "waited"], "no choice but 后接带 to 的不定式。"),
    ("I'm looking forward to ___ from you.", "hearing",
     ["hear", "heard", "be heard"], "look forward to 的 to 是介词，后接动名词。"),
    ("He is used to ___ up early.", "getting",
     ["get", "got", "be got"], "be used to 的 to 是介词，后接动名词。"),
    ("The boss made him ___ the report again.", "rewrite",
     ["to rewrite", "rewriting", "rewrote"], "主动句中 make 后省 to。"),
    ("He was heard ___ the song in the next room.", "to sing",
     ["sing", "singing", "sang"], "hear sb do 变被动后还原 to。"),
    ("— Will you join us? — I'd love ___, but I'm busy.", "to",
     ["to join", "join", "joining"], "承前省略时保留 to，避免重复动词。"),
]

# 动名词复合结构（物主代词 / 名词所有格 + 动名词）
NF_COMPOUND = [
    ("____ late for class made the teacher angry.", "His coming",
     ["He coming", "Him coming", "His came"], "动名词复合结构作主语，用物主代词。"),
    ("Would you mind ____ the window?", "my opening",
     ["me open", "my open", "I opening"], "mind 后接动名词，复合结构用物主代词。"),
    ("We are looking forward to ____ the museum.", "Tom's visiting",
     ["Tom visit", "Tom visiting", "Tom's visit"], "介词后接动名词复合结构。"),
    ("____ the news made her cry.", "His telling",
     ["He telling", "Him told", "His told"], "动名词复合结构作主语。"),
    ("I don't mind ____ here.", "your waiting",
     ["you wait", "your wait", "you waited"], "mind + 动名词复合结构。"),
    ("____ so much noise annoyed the neighbours.", "Their making",
     ["They making", "Them making", "Their made"], "动名词复合结构作主语。"),
    ("The teacher was angry about ____ late again.", "Tom's being",
     ["Tom be", "Tom being", "Tom's be"], "介词后接动名词复合结构。"),
    ("Do you mind ____ the door?", "my closing",
     ["me close", "my close", "I closing"], "mind + 动名词复合结构。"),
    ("____ the prize made his parents proud.", "His winning",
     ["He winning", "Him winning", "His won"], "动名词复合结构作主语用物主代词。"),
    ("We insisted on ____ the work alone.", "his doing",
     ["he do", "him do", "his do"], "insist on 后接动名词复合结构。"),
    ("I still remember ____ me with my homework.", "his helping",
     ["he help", "him help", "his help"], "remember doing 的复合结构。"),
    ("____ the truth at last surprised everyone.", "Her telling",
     ["She telling", "Her told", "She told"], "动名词复合结构作主语。"),
]


def _g_nf_choice(pool):
    def g(rng: random.Random) -> dict:
        stem, ans, wrongs, why = rng.choice(pool)
        return _choice(rng, stem, ans, wrongs, why,
                       trap="先看空前的词：是及物动词、介词、还是省略结构，再定形式。")
    return g


# ================================================================== 从句（一）定语从句
#
# 通则：关系词由三件事共同决定——先行词指人还是指物、关系词在从句中作什么成分、
# 从句是限制性还是非限制性。三者确定，答案就唯一。凡是两种说法都通的空位
# （the same...as/that、prefer 型），一律不做填空，改四选一或直接换题。


def _g_pool_choice(pool, trap: str = ""):
    """把一个 (题干, 答案, 干扰项, 解析) 池包成生成器。"""
    def g(rng: random.Random) -> dict:
        stem, ans, wrongs, why = rng.choice(pool)
        return _choice(rng, stem, ans, wrongs, why, trap=trap)
    return g


def _g_pool_fill(pool, trap: str = ""):
    """把一个 (题干, 答案, 解析) 池包成生成器。"""
    def g(rng: random.Random) -> dict:
        stem, ans, why = rng.choice(pool)
        return _fill(stem, ans, why, hint=trap)
    return g


def _g_adv_time(rng: random.Random) -> dict:
    if rng.random() < 0.3:
        stem, ans, why = rng.choice(ADV_TIME_FILL)
        return _fill(stem, ans, why,
                     hint="主句是过去时，as 从句也要用过去时。")
    stem, ans, wrongs, why = rng.choice(ADV_TIME)
    return _choice(rng, stem, ans, wrongs, why,
                   trap="先判断动作是瞬间还是持续：瞬间用 when，持续用 while，"
                        "「随着」用 as。")



RC_AS_WHICH = [
    ("___ is often the case with beginners, he made a few silly mistakes.",
     "As", ["Which", "That", "It"],
     "as 引导的非限制性定语从句可以放在主句之前，指代整个主句；which 不能置于句首。"),
    ("___ is often the case in winter, the roads become icy before dawn.",
     "As", ["Which", "That", "It"],
     "as 在句首指代后面整个主句，是固定用法（as is often the case）。"),
    ("___ we all know, the earth moves around the sun.",
     "As", ["Which", "That", "What"],
     "as we all know 是插入式的非限制性定语从句，位置可在句首。"),
    ("___ is known to all, the Great Wall is one of the wonders of the world.",
     "As", ["Which", "That", "It"],
     "as is known to all 为固定结构，只能用 as。"),
    ("___ had been expected, the harvest was poor that year.",
     "As", ["Which", "That", "It"],
     "as had been expected 位于句首，指代主句内容，用 as。"),
    ("He was late again, ___ made his teacher rather angry.",
     "which", ["as", "that", "what"],
     "位于主句之后、指代整个主句的非限制性定语从句用 which；as 多用于「正如」类固定结构。"),
    ("He failed the exam, ___ was a great disappointment to his parents.",
     "which", ["as", "that", "what"],
     "which 指代前面整件事，在从句中作主语。"),
    ("He didn't say a word, ___ made the situation even worse.",
     "which", ["as", "that", "what"],
     "which 指代前面整个句子，作从句主语。"),
    ("The weather turned out to be fine, ___ was more than we could hope for.",
     "which", ["as", "that", "what"],
     "指代整句内容且位于句末，用 which。"),
    ("The boy was late for school again, ___ his teacher found strange.",
     "which", ["as", "that", "what"],
     "which 在从句中作 found 的宾语，指代主句整件事。"),
    ("The plan, ___ was expected, turned out to be a success.",
     "as", ["which", "that", "what"],
     "as was expected 是固定插入结构，表示「正如预料的那样」。"),
    ("The number of smokers, ___ is reported, has dropped in recent years.",
     "as", ["which", "that", "what"],
     "as is reported 为固定被动结构，插在主谓之间指代整个主句。"),
    ("This is such a difficult problem ___ nobody can solve.",
     "as", ["that", "which", "what"],
     "solve 后面缺宾语，说明是从句而非结果状语从句，such...as 引导定语从句。"),
    ("This is such a difficult problem ___ nobody can solve it.",
     "that", ["as", "which", "what"],
     "从句成分完整（solve 已有宾语 it），所以是 such...that 引导的结果状语从句。"),
    ("Such books ___ you mentioned are worth reading.",
     "as", ["that", "which", "what"],
     "such + 名词 + as 引导限制性定语从句，as 在从句中作 mentioned 的宾语。"),
    ("___ often happens in such cases, the patient recovered quickly.",
     "As", ["Which", "That", "It"],
     "as often happens 是句首的非限制性定语从句，指代主句内容。"),
]


# 介词 + 关系代词：先行词决定用 which 还是 whom，介词由从句里的动词搭配决定
RC_PREP = [
    ("The method", "by", False, "the team solved the problem", "was surprisingly simple."),
    ("The rate", "at", False, "prices are rising", "is worrying."),
    ("The tool", "with", False, "we cut the wire", "has gone missing."),
    ("The speed", "at", False, "light travels in a vacuum", "is about 300,000 km per second."),
    ("The subject", "about", False, "they argued for hours", "was a minor one."),
    ("The room", "in", False, "the meeting was held", "is on the second floor."),
    ("The book", "for", False, "I paid twenty dollars", "turned out to be a bargain."),
    ("The drawer", "in", False, "she keeps her letters", "is always locked."),
    ("The company", "to", False, "he applied last month", "has rejected him."),
    ("The village", "in", False, "she was born", "has changed a great deal."),
    ("The professor", "from", True, "I learned most of what I know", "retired last year."),
    ("The person", "to", True, "he was talking", "turned out to be a spy."),
    ("The colleague", "with", True, "I share the office", "is very helpful."),
    ("The man", "for", True, "the police are looking", "is in his fifties."),
    ("The friend", "with", True, "I travelled to Tibet", "now lives in Canada."),
    ("The neighbour", "about", True, "she often complains", "has moved away."),
]


def _g_rc_prep(rng: random.Random) -> dict:
    head, prep, human, clause, tail = rng.choice(RC_PREP)
    stem = f"{head} {prep} ___ {clause} {tail}"
    if human:
        ans = f"{prep} whom"
        wrongs = ["whom", f"{prep} which", f"{prep} that"]
        why = "先行词指人，介词提到前面后只能用 whom，不能用 who。"
    else:
        ans = f"{prep} which"
        wrongs = ["which", f"{prep} whom", f"{prep} that"]
        why = "先行词指物，介词后只能用 which；that 不能紧跟在介词后面。"
    return _choice(rng, stem, ans, wrongs, why,
                   trap="介词提前后，后面只接 which / whom；that 永远不能跟在介词后。")


RC_NONREST = [
    ("My grandfather, ___ fought in the war, never talked about it.",
     "who", ["that", "which", "whom"],
     "逗号隔开的是非限制性定语从句，指人作主语用 who，不能用 that。"),
    ("My sister, ___ works in a hospital, is coming home this weekend.",
     "who", ["that", "which", "whose"],
     "非限制性定语从句指人作主语，用 who。"),
    ("The volunteers, most of ___ had no medical training, worked around the clock.",
     "whom", ["who", "which", "that"],
     "most of 后面指人用 whom，who 不能直接跟在介词后。"),
    ("He has two sons, both of ___ are doctors.",
     "whom", ["who", "which", "that"],
     "both of + 关系代词，指人用 whom。"),
    ("The students, some of ___ come from rural areas, live on campus.",
     "whom", ["who", "which", "that"],
     "some of 后面指人用 whom。"),
    ("The book, ___ was published last year, has sold a million copies.",
     "which", ["that", "who", "what"],
     "非限制性定语从句指物作主语用 which，不能用 that。"),
    ("Her house, ___ is being rebuilt, looks empty at the moment.",
     "which", ["that", "who", "whose"],
     "非限制性定语从句指物，用 which。"),
    ("Beijing, ___ I have visited twice, is a beautiful city.",
     "which", ["that", "where", "who"],
     "visit 是及物动词，从句缺宾语，用 which；where 只能作地点状语。"),
    ("The play, ___ we saw last night, was rather boring.",
     "which", ["that", "who", "what"],
     "指物作 saw 的宾语，非限制性从句用 which。"),
    ("This machine, ___ we bought only last month, has broken down twice.",
     "which", ["that", "who", "whose"],
     "指物作 bought 的宾语，用 which。"),
    ("The lecture, ___ lasted nearly three hours, put half the audience to sleep.",
     "which", ["that", "who", "what"],
     "指物作主语，非限制性从句用 which。"),
    ("Tom, ___ father is a lawyer, wants to study law.",
     "whose", ["who", "which", "whom"],
     "表示「汤姆的父亲」，用 whose 作定语。"),
    ("The old tree, ___ branches were broken in the storm, has been cut down.",
     "whose", ["who", "which", "that"],
     "表示「树的枝干」，用 whose 指代所属关系。"),
    ("These apples, none of ___ is ripe, should not be picked.",
     "which", ["that", "whom", "who"],
     "none of + 关系代词，指物用 which。"),
]


# 定语从句的主谓一致：one of + 复数名词 + who/that + 复数谓语；
# the only one of + 复数名词 + who/that + 单数谓语。谓语形式由 who 的先行词唯一决定。
RC_AGREE_SUBJ = [
    ("She", "students"), ("He", "candidates"), ("Tom", "players"),
    ("Mary", "singers"), ("Lucy", "volunteers"), ("Jack", "workers"),
    ("My sister", "teachers"), ("My brother", "members"),
    ("The girl", "applicants"), ("The boy", "readers"),
    ("Anna", "dancers"), ("Peter", "drivers"),
]

RC_AGREE_TAIL = [
    ("be", "willing to work overtime", ("are", "is"),
     "who 的先行词是复数名词，从句谓语用复数；只有 the only one of 时先行词才是单数。"),
    ("have", "a driving licence", ("have", "has"),
     "one of + 复数名词时，who 指复数名词，谓语用复数形式。"),
]


def _g_rc_agree(rng: random.Random) -> dict:
    subj, noun = rng.choice(RC_AGREE_SUBJ)
    verb, tail, (plural, singular), why = rng.choice(RC_AGREE_TAIL)
    only = rng.random() < 0.5
    if only:
        stem = f"{subj} is the only one of the {noun} who ___ ({verb}) {tail}."
        ans, other = singular, plural
        explain = ("the only one of + 复数名词时，who 的先行词是 the only one，"
                   "从句谓语用单数。")
    else:
        stem = f"{subj} is one of the {noun} who ___ ({verb}) {tail}."
        ans, other = plural, singular
        explain = why
    return _fill(stem, ans, explain, accept=[ans],
                 hint="先找 who 的先行词：是前面的复数名词，还是 the only one？")


RC_IDENT = [
    ("The news ___ the company was closing down spread within an hour.",
     "that", ["which", "what", "when"],
     "从句成分完整、that 不作任何成分，说明是同位语从句而非定语从句。"),
    ("She hid the letter in a place ___ nobody would think of looking.",
     "where", ["which", "that", "what"],
     "从句缺地点状语，先行词是 place，用 where 引导定语从句。"),
    ("It was in the park ___ I met him yesterday.",
     "that", ["where", "which", "when"],
     "去掉 It was 后句子仍完整，是强调句，用 that；不是定语从句。"),
    ("It was not until midnight ___ he came back.",
     "that", ["when", "which", "then"],
     "not until 的强调句固定用 that 连接。"),
    ("Was it in this room ___ the meeting was held?",
     "that", ["where", "which", "when"],
     "强调句的疑问形式，仍用 that。"),
    ("The reason ___ he gave was not convincing.",
     "that", ["why", "because", "what"],
     "give 后面缺宾语，关系词作宾语用 that / which；why 只能作原因状语。"),
    ("The reason ___ he was late was that his car broke down.",
     "why", ["that", "because", "which"],
     "从句成分完整（he was late），缺原因状语，用 why。"),
    ("It is the third time ___ he has been late this week.",
     "that", ["when", "which", "what"],
     "It is the + 序数词 + time + that 是固定句型。"),
    ("There was a time ___ people had no television at all.",
     "when", ["that", "which", "where"],
     "先行词是 time，从句缺时间状语，用 when。"),
    ("The day ___ we had been looking forward to came at last.",
     "that", ["when", "where", "what"],
     "look forward to 缺宾语，关系词作宾语用 that；when 只能作状语。"),
    ("Do you still remember the village ___ we visited last year?",
     "that", ["where", "when", "what"],
     "visit 是及物动词，从句缺宾语，用 that；where 不能作宾语。"),
    ("This is the very book ___ I have been looking for.",
     "that", ["which", "what", "whose"],
     "the very 修饰先行词时，关系代词只能用 that。"),
    ("All ___ we need is a good rest.",
     "that", ["which", "what", "who"],
     "先行词是不定代词 all 时，关系代词只能用 that。"),
    ("The first thing ___ I noticed was his smile.",
     "that", ["which", "what", "when"],
     "先行词有序数词修饰时，关系代词只能用 that。"),
]


RC_REDUCE = [
    ("The girl ___ (sing) on the stage is my cousin.", "singing",
     "girl 与 sing 是主动关系且动作进行，用现在分词作定语。"),
    ("The man ___ (stand) at the door is my uncle.", "standing",
     "man 主动站立，用现在分词。"),
    ("The children ___ (dance) in the hall are from Grade One.", "dancing",
     "children 主动跳舞，用现在分词。"),
    ("The problems ___ (discuss) at yesterday's meeting remain unsolved.", "discussed",
     "problems 与 discuss 是被动关系，且动作已完成，用过去分词。"),
    ("The book ___ (write) by a famous professor sells well.", "written",
     "book 是被写的，用过去分词。"),
    ("The car ___ (repair) last week runs smoothly now.", "repaired",
     "car 与 repair 是被动关系，用过去分词。"),
    ("The letter ___ (send) yesterday arrived this morning.", "sent",
     "letter 是被寄出的，用过去分词。"),
    ("The tree ___ (plant) ten years ago is very tall now.", "planted",
     "tree 是被栽种的，用过去分词。"),
    ("The house ___ (build) now will be a library.", "being built",
     "house 正在被建，被动进行用 being done。"),
    ("The question ___ (discuss) at the moment is rather difficult.", "being discussed",
     "question 正在被讨论，被动进行用 being done。"),
    ("The meeting ___ (hold) tomorrow is very important.", "to be held",
     "会议尚未召开且是被动的，用 to be done 表示将来的被动。"),
    ("She is always the first ___ (arrive) at the office.", "to arrive",
     "序数词 first 后用不定式作定语。"),
    ("He was the only one ___ (know) the truth.", "to know",
     "the only one 后用不定式作定语。"),
    ("The last person ___ (leave) the room should turn off the lights.", "to leave",
     "the last 后用不定式作定语。"),
    ("She has a lot of homework ___ (do) tonight.", "to do",
     "have sth to do 结构中用不定式作定语，表示还没做的事。"),
]


# ================================================================== 从句（二）名词性从句
#
# 名词性从句的空位只有两类：连接词（that / whether / if / what / which / who /
# 连接副词）和语序（一律陈述语序）。连接词的选择靠「从句是否缺成分、缺什么成分」
# 判定；语序靠「疑问词 + 主语 + 谓语」判定。两者都能做到答案唯一。

NC_SUBJECT = [
    ("___ he will accept the position remains uncertain.",
     "Whether", ["If", "That", "What"],
     "句首的主语从句只能用 whether，不能用 if。"),
    ("___ she will marry him is still a question.",
     "Whether", ["If", "That", "What"],
     "句首主语从句表示「是否」用 whether。"),
    ("___ the plan will work remains to be seen.",
     "Whether", ["If", "That", "What"],
     "句首不能用 if 引导主语从句。"),
    ("___ we should go or stay has not been decided.",
     "Whether", ["If", "That", "What"],
     "与 or 连用表示选择时只能用 whether。"),
    ("___ is reported that the bridge will reopen next spring.",
     "It", ["That", "What", "As"],
     "that 从句作主语时，常用 it 作形式主语后置。"),
    ("___ we need most is more time.",
     "What", ["That", "Which", "It"],
     "从句缺宾语（need 缺宾语），用 what 引导主语从句。"),
    ("___ he said at the meeting surprised everyone.",
     "What", ["That", "Which", "It"],
     "said 缺宾语，用 what；that 引导的从句不缺成分。"),
    ("___ makes him so popular is his sense of humour.",
     "What", ["That", "Which", "It"],
     "从句缺主语，用 what。"),
    ("___ matters is not the result but the effort.",
     "What", ["That", "Which", "It"],
     "matters 缺主语，用 what 引导主语从句。"),
    ("It is a pity ___ you missed such a good film.",
     "that", ["what", "whether", "which"],
     "it 作形式主语，真正主语是 that 从句；从句成分完整用 that。"),
    ("It is said ___ the company will move abroad.",
     "that", ["what", "whether", "which"],
     "It is said that 是固定句型，用 that。"),
    ("It seems ___ he is right.",
     "that", ["what", "whether", "which"],
     "It seems that 是固定句型。"),
    ("It doesn't matter ___ he comes or not.",
     "whether", ["that", "if", "what"],
     "与 or not 连用只能用 whether。"),
    ("It is unknown ___ they have finished the work.",
     "whether", ["that", "if", "what"],
     "表示「是否」且在 it 之后，用 whether；此处用 that 会改变语义。"),
]


NC_OBJ_TENSE = [
    ("The teacher told us that the sun ___ (rise) in the east.", "rises",
     "宾语从句表示客观真理时，即使主句是过去时，从句仍用一般现在时。"),
    ("Our teacher said that practice ___ (make) perfect.", "makes",
     "谚语、客观规律不受主句时态影响，用一般现在时。"),
    ("The guide explained that the earth ___ (go) around the sun.", "goes",
     "客观事实用一般现在时。"),
    ("The teacher said light ___ (travel) faster than sound.", "travels",
     "科学事实用一般现在时。"),
    ("He said that he ___ (be) busy at that moment.", "was",
     "主句是过去时，从句表示那时的状态，用过去时。"),
    ("She asked whether I ___ (finish) the work.", "had finished",
     "从句动作发生在主句之前，用过去完成时。"),
    ("I didn't know that she ___ (leave) already.", "had left",
     "already 与过去完成时呼应，表示在主句动作之前已完成。"),
    ("He asked me what I ___ (do) at that time.", "was doing",
     "at that time 表示过去某时正在进行，用过去进行时。"),
    ("She said she ___ (come) back the next day.", "would come",
     "主句过去时，从句表示将来用过去将来时。"),
    ("He wondered why she ___ (refuse) the offer.", "had refused",
     "拒绝发生在犹豫之前，用过去完成时。"),
    ("He told me he ___ (live) in Beijing since 2010.", "had lived",
     "since 引导的时间起点配合过去完成时，表示持续到过去某时。"),
    ("I thought you ___ (be) in Shanghai last week.", "were",
     "主句过去时，从句表示过去的状态用过去时。"),
]


NC_PREDICATIVE = [
    ("The reason he gave for his absence was ___ he had missed the early bus.",
     "that", ["because", "why", "what"],
     "表语从句说明 reason 的内容，用 that；because 引导的是原因状语从句。"),
    ("The reason why he was late is ___ he missed the bus.",
     "that", ["because", "why", "what"],
     "主语是 the reason 时，表语从句用 that，不用 because。"),
    ("The question is ___ we should tell him the truth now.",
     "whether", ["if", "that", "what"],
     "表语从句表示「是否」用 whether；if 一般不用在表语从句。"),
    ("The problem is ___ we can finish it on time.",
     "whether", ["if", "that", "what"],
     "表示「是否」的表语从句用 whether。"),
    ("That is ___ he was late — his car broke down on the way.",
     "why", ["because", "that", "what"],
     "That is why 表示「这就是……的原因」，后接结果。"),
    ("That is ___ I disagree with him.",
     "where", ["that", "what", "which"],
     "where 引导表语从句表示抽象地点「在这一点上」。"),
    ("It looks ___ it is going to rain.",
     "as if", ["that", "whether", "like"],
     "look as if 表示「看起来好像」，后接从句用 as if。"),
    ("The trouble is ___ we don't have enough money.",
     "that", ["because", "what", "whether"],
     "说明 trouble 的具体内容，用 that。"),
    ("This is ___ I want to say.",
     "what", ["that", "which", "how"],
     "say 缺宾语，用 what 引导表语从句。"),
    ("That is ___ he told me yesterday.",
     "what", ["that", "which", "how"],
     "told 缺直接宾语，用 what。"),
    ("The fact is ___ he has never been abroad.",
     "that", ["what", "whether", "which"],
     "从句成分完整，用 that 引导表语从句。"),
    ("It seems ___ he knows the answer.",
     "that", ["what", "whether", "which"],
     "It seems that 为固定句型。"),
    ("The point is ___ we must act now.",
     "that", ["what", "whether", "how"],
     "说明 point 的内容，从句完整用 that。"),
    ("It appears ___ the rumour is true.",
     "that", ["what", "whether", "which"],
     "It appears that 为固定句型。"),
]


NC_APPOS = [
    ("The news ___ the factory would close down soon shocked the workers.",
     "that", ["which", "what", "when"],
     "that 在从句中不作成分，说明 news 的具体内容，是同位语从句。"),
    ("The fact ___ she has never been abroad surprises her classmates.",
     "that", ["which", "what", "whether"],
     "从句成分完整，that 不作成分，是同位语从句。"),
    ("The idea ___ we should work together is a good one.",
     "that", ["which", "what", "whether"],
     "that 说明 idea 的内容，不作成分。"),
    ("Word came ___ the team had won the championship.",
     "that", ["which", "what", "whether"],
     "word 表示「消息」，后接同位语从句用 that。"),
    ("The question ___ we should go or not has not been settled.",
     "whether", ["that", "if", "which"],
     "表示「是否」的同位语从句用 whether。"),
    ("There is no doubt ___ he will succeed.",
     "that", ["whether", "which", "what"],
     "no doubt 后的同位语从句用 that。"),
    ("The belief ___ hard work leads to success is widespread.",
     "that", ["which", "what", "whether"],
     "that 说明 belief 的内容，不作成分。"),
    ("The possibility ___ he might fail never occurred to him.",
     "that", ["which", "what", "whether"],
     "that 引导同位语从句说明 possibility 的内容。"),
    ("The order ___ the troops should withdraw was given at dawn.",
     "that", ["which", "what", "whether"],
     "order 表示「命令」，同位语从句用 that。"),
    ("The suggestion ___ we start early was accepted by all.",
     "that", ["which", "what", "whether"],
     "suggestion 后接同位语从句用 that，从句用原形动词。"),
    ("He made a promise ___ he would never tell a lie.",
     "that", ["which", "what", "whether"],
     "promise 后接同位语从句用 that。"),
    ("The hope ___ they would meet again kept her going.",
     "that", ["which", "what", "whether"],
     "that 说明 hope 的内容，不作成分。"),
    ("The news ___ he told me turned out to be false.",
     "that", ["what", "where", "when"],
     "told 缺宾语，关系词作宾语，是定语从句，用 that。"),
    ("The fact ___ he mentioned in the report is important.",
     "that", ["what", "where", "when"],
     "mentioned 缺宾语，是定语从句，关系词用 that。"),
]


NC_WHETHER = [
    ("The success of the project depends on ___ the team can cooperate well.",
     "whether", ["if", "that", "what"],
     "介词后面只能用 whether，不能用 if。"),
    ("___ he will attend the meeting or not has not been decided yet.",
     "Whether", ["If", "That", "What"],
     "句首且与 or not 连用，只能用 whether。"),
    ("It depends on ___ we have enough time.",
     "whether", ["if", "that", "what"],
     "介词 on 后面用 whether。"),
    ("I wonder ___ to accept the offer.",
     "whether", ["if", "that", "what"],
     "不定式前面只能用 whether，不能用 if。"),
    ("The question is ___ it is worth trying.",
     "whether", ["if", "that", "what"],
     "表语从句表示「是否」用 whether。"),
    ("___ to tell him the truth is a difficult decision.",
     "Whether", ["If", "That", "What"],
     "whether + 不定式作主语，if 不能这样用。"),
    ("I'm worried about ___ he is safe.",
     "whether", ["if", "that", "what"],
     "介词 about 后面用 whether。"),
    ("___ she comes or not, the meeting will go on.",
     "Whether", ["If", "That", "What"],
     "让步状语从句中与 or not 连用，用 whether。"),
    ("There is some doubt ___ he is the right person.",
     "whether", ["that", "which", "what"],
     "doubt 在肯定句中接 whether 从句。"),
    ("He hasn't decided ___ to go or stay.",
     "whether", ["if", "that", "what"],
     "whether + 不定式表示「是否」。"),
    ("The problem of ___ to tell him the truth remains.",
     "whether", ["if", "that", "what"],
     "介词 of 后面用 whether。"),
    ("It doesn't matter ___ we start now or later.",
     "whether", ["if", "that", "what"],
     "与 or 连用的选择结构用 whether。"),
    ("We are not sure ___ he will come.",
     "whether", ["that", "which", "what"],
     "表示「不确定是否」，用 whether 引导宾语从句。"),
    ("He asked ___ I had finished the work.",
     "whether", ["that", "which", "what"],
     "表示「是否」的宾语从句用 whether。"),
]


NC_PRON = [
    ("___ he told us at the meeting turned out to be a lie.",
     "What", ["That", "Which", "It"],
     "told 缺直接宾语，用 what 引导主语从句。"),
    ("___ of the two plans is more practical remains to be seen.",
     "Which", ["What", "Who", "That"],
     "在有限范围内选择，用 which of。"),
    ("___ breaks the law will be punished.",
     "Whoever", ["Who", "Whomever", "Whatever"],
     "引导主语从句表示「无论谁」，且在从句中作主语，用 whoever。"),
    ("You may choose ___ you like.",
     "whichever", ["whatever", "whoever", "which"],
     "在给定范围内随便选，用 whichever。"),
    ("___ he needs most is a good rest.",
     "What", ["That", "Which", "It"],
     "needs 缺宾语，用 what。"),
    ("___ he is has nothing to do with me.",
     "Who", ["Whoever", "What", "That"],
     "从句缺表语且指人，用 who。"),
    ("Give it to ___ comes first.",
     "whoever", ["whomever", "who", "whatever"],
     "介词后引导从句且在从句中作主语，用 whoever。"),
    ("I'll take ___ of the two books you recommend.",
     "whichever", ["whatever", "whoever", "which"],
     "在两者中任选，用 whichever。"),
    ("___ he did was beyond my understanding.",
     "What", ["That", "Which", "It"],
     "did 缺宾语，用 what。"),
    ("___ wins the game will get the prize.",
     "Whoever", ["Who", "Whomever", "Whatever"],
     "从句缺主语且表示「无论谁」，用 whoever。"),
    ("You can take ___ you need.",
     "whatever", ["whoever", "which", "that"],
     "表示「无论什么」且没有范围限制，用 whatever。"),
    ("___ of the three answers is correct is still unknown.",
     "Which", ["What", "Who", "That"],
     "三者中选一，用 which of。"),
    ("She is not ___ she used to be.",
     "what", ["that", "which", "who"],
     "表示「不再是过去的样子」，what 指身份与状态。"),
    ("___ makes him so confident is his experience.",
     "What", ["That", "Which", "It"],
     "makes 缺主语，用 what。"),
]


NC_ADV = [
    ("Nobody knows exactly ___ the meeting will last.",
     "how long", ["how often", "how soon", "how far"],
     "last 表示持续时间，问长度用 how long。"),
    ("That is ___ he was late — his car broke down.",
     "why", ["when", "where", "how"],
     "表示原因，用 why 引导表语从句。"),
    ("This is ___ we first met.",
     "where", ["when", "which", "what"],
     "表示地点，用 where。"),
    ("I don't know ___ he will arrive.",
     "when", ["where", "why", "how"],
     "表示时间，用 when。"),
    ("___ he managed to finish it in one day is a mystery.",
     "How", ["Why", "When", "Where"],
     "表示方式，用 how 引导主语从句。"),
    ("Tell me ___ the box weighs.",
     "how much", ["how many", "how long", "how far"],
     "weight 不可数，问重量用 how much。"),
    ("Do you know ___ it is from here to the station?",
     "how far", ["how long", "how soon", "how much"],
     "问距离用 how far。"),
    ("___ often he goes to the gym is none of my business.",
     "How", ["Why", "When", "Where"],
     "how often 表示频率，整体作主语从句的连接词。"),
    ("Nobody told me ___ to get to the airport.",
     "how", ["what", "which", "why"],
     "how + 不定式表示方式。"),
    ("That is ___ I want to see you.",
     "why", ["how", "when", "where"],
     "表示原因，用 why。"),
    ("I still remember ___ we lived when I was a child.",
     "where", ["when", "how", "which"],
     "lived 后缺地点状语，用 where。"),
    ("___ soon he will be back depends on the traffic.",
     "How", ["Why", "When", "Where"],
     "how soon 表示「多久以后」，整体引导主语从句。"),
    ("She asked ___ I had been waiting.",
     "how long", ["how often", "how soon", "how far"],
     "问等待持续时间用 how long。"),
    ("This is ___ the accident happened.",
     "where", ["when", "why", "how"],
     "表示事故发生的地点，用 where。"),
]


NC_ORDER = [
    ("He asked me ___.", "what I thought of the new plan",
     ["what did I think of the new plan", "what I think of the new plan did",
      "what thought I of the new plan"],
     "宾语从句一律用陈述语序：疑问词 + 主语 + 谓语。"),
    ("I wonder ___.", "whether he will come to the party",
     ["whether will he come to the party", "whether he comes to the party will",
      "if will he come to the party"],
     "从句用陈述语序，主语放在助动词之前。"),
    ("Do you know ___?", "when the concert will begin",
     ["when will the concert begin", "when the concert begins will",
      "when does the concert begin"],
     "宾语从句不倒装。"),
    ("Nobody knows ___.", "where he has gone",
     ["where has he gone", "where did he go", "where he has gone to"],
     "从句用陈述语序，且 go 后不再加 to。"),
    ("She wanted to know ___.", "why I had refused the offer",
     ["why had I refused the offer", "why I had refused the offer for", "why did I refuse the offer"],
     "主句过去时，从句用过去完成时，且为陈述语序。"),
    ("Can you tell me ___?", "how much this coat costs",
     ["how much does this coat cost", "how much this coat cost does",
      "how much costs this coat"],
     "从句用陈述语序，助动词不再出现。"),
    ("The teacher asked ___.", "who had broken the window",
     ["who did broke the window", "whom had broken the window",
      "who has broke the window"],
     "who 在从句中作主语，后直接接谓语；主句过去时，从句用过去完成时。"),
    ("I have no idea ___.", "what he is doing now",
     ["what is he doing now", "what he doing now", "what does he do now"],
     "同位语从句同样用陈述语序。"),
    ("He didn't tell me ___.", "when he would leave",
     ["when would he leave", "when he will left", "when did he leave"],
     "主句过去时，从句用过去将来时并保持陈述语序。"),
    ("We are not sure ___.", "whether they will join us",
     ["whether will they join us", "that they join us will", "whether do they join us"],
     "表示「是否」用 whether，且用陈述语序。"),
    ("Please tell me ___.", "where I can find the nearest bank",
     ["where can I find the nearest bank", "where I could found the nearest bank",
      "where I can find the nearest bank to go"],
     "祈使句后的宾语从句用陈述语序，助动词不再提到主语前面。"),
    ("He wondered ___.", "how long the journey would take",
     ["how long would the journey take", "how long the journey would takes",
      "how long did the journey take"],
     "主句过去时，从句用过去将来时并保持陈述语序。"),
    ("The question is ___.", "whether we can finish it on time",
     ["whether can we finish it on time", "that we can finish it on time",
      "whether we can finished it on time"],
     "表语从句用陈述语序；表示「是否」用 whether，不用 that。"),
    ("I don't understand ___.", "why she is so angry",
     ["why is she so angry", "why she angry is", "why does she be so angry"],
     "从句用陈述语序，be 动词直接跟在主语后。"),
]


# ================================================================== 从句（三）状语从句
#
# 状语从句的空位考的是「逻辑关系 + 主将从现」。逻辑关系由前后分句的语义唯一确定：
# 时间点用 when、持续过程用 while、随着变化用 as；条件用 if/unless；让步用
# although/as/however。主将从现则是硬规则——从句里不能出现 will。

ADV_TIME = [
    ("___ the goalkeeper caught the ball, the referee blew his whistle.",
     "When", ["While", "Until", "Even if"],
     "caught 是瞬间动作，用 when；while 后接持续动作。"),
    ("___ I was walking home, it began to rain.",
     "While", ["When", "Until", "As soon as"],
     "was walking 是持续过程，用 while 表示「在……期间」。"),
    ("___ he was reading, his sister was watching TV.",
     "While", ["When", "Until", "Before"],
     "两个持续动作同时进行且形成对比，用 while。"),
    ("I was about to leave ___ the phone rang.",
     "when", ["while", "until", "before"],
     "be about to do ... when 表示「正要做某事，这时……」，是固定结构。"),
    ("We were having dinner ___ the lights went out.",
     "when", ["while", "until", "since"],
     "主句进行时 + when 引出突然发生的动作。"),
    ("___ time went by, things got better.",
     "As", ["While", "Until", "Since"],
     "表示「随着」的变化过程，用 as。"),
    ("He sang ___ he walked.",
     "as", ["while", "until", "before"],
     "表示「一边……一边」，用 as。"),
    ("Don't get off the bus ___ it has stopped.",
     "until", ["when", "while", "as"],
     "not ... until 表示「直到……才」。"),
    ("She waited ___ the rain stopped.",
     "until", ["when", "while", "as"],
     "等待持续到某个时间点，用 until。"),
    ("___ he had finished his homework, he went out to play.",
     "After", ["While", "Until", "Since"],
     "作业完成在前，出去玩在后，用 after。"),
    ("___ I got home, I found the door open.",
     "When", ["While", "Until", "Since"],
     "got home 是瞬间动作，用 when。"),
    ("He jumped up ___ he heard the news.",
     "when", ["while", "until", "since"],
     "heard 是瞬间动作，用 when。"),
]


ADV_TIME_FILL = [
    ("As she ___ (grow) older, she became more tolerant of others' mistakes.", "grew",
     "主句 became 是过去时，as 从句同样用过去时。"),
    ("As time ___ (pass), the pain became easier to bear.", "passed",
     "主句为过去时，as 从句保持一致。"),
    ("As he ___ (get) older, he became more patient.", "got",
     "主句 became 是过去时，从句也用过去时。"),
]


ADV_FUTURE = [
    ("We will not leave the classroom until the rain ___ (stop).", "stops",
     "时间状语从句中主句用将来时，从句用一般现在时。"),
    ("As soon as the report ___ (finish), it will be sent to the manager.", "is finished",
     "从句用一般现在时的被动形式代替将来时的被动。"),
    ("I will call you when I ___ (arrive) in Beijing.", "arrive",
     "时间状语从句遵守主将从现。"),
    ("If it ___ (rain) tomorrow, we will stay at home.", "rains",
     "条件状语从句用一般现在时表示将来。"),
    ("He will tell her the news the moment she ___ (come) back.", "comes",
     "the moment 引导时间状语从句，同样主将从现。"),
    ("We will start the meeting as soon as everyone ___ (arrive).", "arrives",
     "as soon as 从句用一般现在时。"),
    ("Unless he ___ (apologize), she will never speak to him again.", "apologizes",
     "unless 引导条件状语从句，主语三单用一般现在时。"),
    ("I will wait here until you ___ (come) back.", "come",
     "until 从句用一般现在时表示将来。"),
    ("Before you ___ (leave), please turn off the lights.", "leave",
     "before 从句用一般现在时。"),
    ("The game will be cancelled if it ___ (snow) tomorrow.", "snows",
     "if 从句用一般现在时表示将来。"),
    ("She will be happy when she ___ (hear) the news.", "hears",
     "when 从句用一般现在时。"),
    ("We will go out after the rain ___ (stop).", "stops",
     "after 从句用一般现在时表示将来。"),
    ("He will call you before he ___ (leave) for London.", "leaves",
     "before 从句用一般现在时，主语三单加 s。"),
    ("If you ___ (not hurry), you will miss the train.", "don't hurry",
     "if 从句的否定形式用 don't + 原形。"),
]


ADV_PLACE = [
    ("The medicine should be kept ___ children cannot reach it.",
     "where", ["which", "that", "in which"],
     "没有先行词，这是地点状语从句，用 where。"),
    ("___ you go, remember to send me a postcard.",
     "Wherever", ["Where", "Which", "Whatever"],
     "表示「无论去哪里」，用 wherever。"),
    ("Put the book ___ it was.",
     "where", ["which", "that", "when"],
     "表示「在原来的地方」，用 where 引导地点状语从句。"),
    ("He made a mark ___ he had found the treasure.",
     "where", ["which", "that", "when"],
     "标记做在发现宝藏的地方，用 where。"),
    ("You should put the tools ___ they belong.",
     "where", ["which", "that", "what"],
     "表示「工具该在的地方」，用 where。"),
    ("___ there is a will, there is a way.",
     "Where", ["Which", "That", "When"],
     "谚语 Where there is a will, there is a way，用 where。"),
    ("The accident happened ___ the two roads meet.",
     "where", ["which", "that", "when"],
     "表示两条路交汇的地点，用 where。"),
    ("___ he goes, he takes his dog with him.",
     "Wherever", ["Where", "Which", "Whatever"],
     "表示「无论去哪儿」，用 wherever。"),
    ("Stay ___ you are and don't move.",
     "where", ["which", "that", "when"],
     "表示「待在原地」，用 where。"),
    ("We found the keys ___ we had left them.",
     "where", ["which", "that", "when"],
     "留下钥匙的地方，用 where。"),
    ("___ there are many people, there is noise.",
     "Where", ["Which", "That", "When"],
     "表示「在人多的地方」，用 where。"),
    ("She put the vase ___ no one could knock it over.",
     "where", ["which", "that", "when"],
     "表示放置的位置，用 where。"),
    ("___ possible, I like to walk to work.",
     "Where", ["When", "Which", "That"],
     "where possible 是 where it is possible 的省略形式。"),
    ("He followed her ___ she went.",
     "wherever", ["where", "which", "that"],
     "表示「无论她去哪里」，用 wherever。"),
]


ADV_CAUSE = [
    ("The match was cancelled ___ the heavy rain.",
     "because of", ["because", "so", "for"],
     "空格后是名词短语，用介词短语 because of；because 后必须接句子。"),
    ("He lost his job ___ his carelessness.",
     "because of", ["because", "since", "so"],
     "carelessness 是名词，用 because of。"),
    ("The flight was put off ___ the storm.",
     "because of", ["because", "as", "so"],
     "the storm 是名词短语，用 because of。"),
    ("He couldn't attend the meeting ___ his illness.",
     "because of", ["because", "so", "for"],
     "his illness 是名词短语，用 because of。"),
    ("It was ___ the traffic was heavy that we arrived late.",
     "because", ["because of", "so", "for"],
     "强调句中被强调的是原因状语从句，用 because。"),
    ("It is ___ he is honest that everyone trusts him.",
     "because", ["because of", "so", "as"],
     "强调原因状语从句用 because。"),
    ("We can't go out ___ it is raining.",
     "because", ["because of", "so", "for"],
     "空格后是完整句子，用连词 because。"),
    ("He was punished ___ he had broken the rules.",
     "because", ["because of", "so", "for"],
     "后接完整句子，用 because。"),
    ("She looks tired ___ she has been working all night.",
     "because", ["because of", "so", "for"],
     "后接完整句子，用 because。"),
    ("The decision was made ___ we had no other choice.",
     "because", ["because of", "so", "for"],
     "后接完整句子，用 because。"),
    ("___ you have grown up, you should support yourself.",
     "Now that", ["Because of", "So that", "Even if"],
     "表示「既然」，用 now that 引导原因状语从句。"),
    ("___ everyone is here, let's begin the meeting.",
     "Now that", ["Because of", "So that", "In order that"],
     "表示「既然人都到齐了」，用 now that。"),
    ("___ it is raining hard, we had better stay indoors.",
     "Since", ["Because of", "So", "In order that"],
     "表示「既然」，用 since 引导原因状语从句。"),
    ("He didn't pass the exam ___ he didn't work hard.",
     "because", ["because of", "so", "for"],
     "后接完整句子，用 because。"),
]


ADV_PURPOSE = [
    ("She whispered ___ wake the sleeping baby.",
     "so as not to", ["so that not to", "in order that not", "lest to"],
     "不定式的否定形式是 so as not to do，not 放在 to 前。"),
    ("He left the door open ___ the cat could come in.",
     "so that", ["so as to", "in order to", "lest"],
     "空格后是从句（有主语 the cat），用 so that。"),
    ("He studied hard ___ pass the exam.",
     "in order to", ["so that", "so as to", "for to"],
     "空格后是动词原形，用不定式 in order to。"),
    ("Take an umbrella ___ it rains.",
     "in case", ["so that", "in order to", "even if"],
     "表示「以防」，用 in case 引导目的状语从句。"),
    ("She got up early ___ she could catch the first bus.",
     "so that", ["in order to", "so as to", "in case"],
     "后接从句，用 so that。"),
    ("___ the baby could sleep, she turned off the TV.",
     "So that", ["So as to", "In order to", "In case"],
     "句首接从句表示目的，用 so that。"),
    ("He saved money ___ buy a new car.",
     "in order to", ["so that", "in case", "lest"],
     "后接动词原形，用 in order to。"),
    ("Speak louder ___ everyone can hear you.",
     "so that", ["in order to", "so as to", "in case"],
     "后接从句，用 so that。"),
    ("I'll write it down ___ I forget.",
     "in case", ["so that", "in order to", "so as to"],
     "表示「以防忘记」，用 in case。"),
    ("They started early ___ arrive before dark.",
     "so as to", ["so that", "in case", "lest"],
     "后接动词原形，用 so as to。"),
    ("___ not to wake the children, she walked quietly.",
     "In order", ["So as", "So that", "In case"],
     "in order not to do 可以置于句首；so as not to do 一般不放在句首。"),
    ("She left a note ___ he would know where she was.",
     "so that", ["in order to", "so as to", "in case"],
     "后接从句，用 so that。"),
    ("Bring some money ___ you need it.",
     "in case", ["so that", "in order to", "so as to"],
     "表示「以防你需要」，用 in case。"),
    ("He ran fast ___ catch the bus.",
     "so as to", ["so that", "in case", "lest"],
     "后接动词原形，用 so as to。"),
]


ADV_CONDITION = [
    ("___ you practise every day, you will not make real progress.",
     "Unless", ["If", "Provided that", "As long as"],
     "表示「除非」，用 unless 引导条件状语从句。"),
    ("You can use my laptop ___ you do not change any settings.",
     "as long as", ["unless", "even if", "in case"],
     "表示「只要」，用 as long as。"),
    ("___ it rains tomorrow, the match will be cancelled.",
     "If", ["Unless", "Even if", "In case"],
     "表示「如果」，用 if。"),
    ("___ I were you, I would accept the offer.",
     "If", ["Unless", "Though", "Because"],
     "虚拟条件句用 if 引导。"),
    ("___ you had studied harder, you would have passed.",
     "If", ["Unless", "Even if", "In case"],
     "与过去事实相反的虚拟条件句用 if。"),
    ("Send me a message ___ you need help.",
     "in case", ["unless", "even if", "so that"],
     "表示「以防你需要帮助」，用 in case。"),
    ("I'll lend you the book ___ you return it by Friday.",
     "on condition that", ["unless", "even if", "in case"],
     "表示「条件是」，用 on condition that。"),
    ("___ it snows, the roads will be blocked.",
     "If", ["Unless", "Even though", "In case"],
     "表示假设条件，用 if。"),
    ("You will fail ___ you work harder.",
     "unless", ["if", "as long as", "in case"],
     "表示「除非你更努力」，用 unless。"),
    ("___ you take a taxi, you will be late.",
     "Unless", ["If", "As long as", "Even if"],
     "表示「除非打车」，用 unless。"),
    ("Take a map with you ___ you get lost.",
     "in case", ["unless", "even if", "as long as"],
     "表示「以防迷路」，用 in case。"),
    ("___ we leave now, we can catch the train.",
     "If", ["Unless", "Even if", "In case"],
     "表示假设条件，用 if。"),
    ("I don't mind ___ you keep quiet.",
     "as long as", ["unless", "even if", "in case"],
     "表示「只要」，用 as long as。"),
    ("___ you promise to be careful, you can borrow my bike.",
     "Provided that", ["Unless", "In case", "Even if"],
     "表示「只要你保证」，用 provided that。"),
]


ADV_CONCESSION = [
    ("___ the journey was exhausting, they arrived in high spirits.",
     "Although", ["But", "Despite", "However"],
     "后接完整句子且表示让步，用 although。"),
    ("Hard ___ he tried, he could not solve the puzzle.",
     "as", ["although", "because", "so"],
     "as 引导让步状语从句时要倒装：形容词/副词 + as + 主语 + 谓语。"),
    ("___ hard he tried, he could not solve it.",
     "However", ["Whatever", "Although", "As"],
     "however + 形容词/副词 + 主语 + 谓语，表示「无论多么」。"),
    ("Child ___ he is, he knows a lot.",
     "as", ["although", "though", "because"],
     "名词提前 + as 引导让步状语从句。"),
    ("Even ___ it rains, we will go.",
     "if", ["as", "although", "so"],
     "even if 表示「即使」。"),
    ("___ the fact that he was tired, he kept working.",
     "Despite", ["Although", "However", "Because"],
     "空格后是名词短语，用介词 despite。"),
    ("No matter ___ hard it rains, we will go.",
     "how", ["what", "which", "who"],
     "no matter how + 形容词/副词，表示「无论多么」。"),
    ("___ he is young, he is very experienced.",
     "Though", ["But", "Despite", "However"],
     "后接完整句子，用 though 引导让步状语从句。"),
    ("Try ___ he might, he could not open the door.",
     "as", ["although", "though", "however"],
     "动词原形提前 + as 引导让步状语从句。"),
    ("___ you say, I won't change my mind.",
     "Whatever", ["However", "Whenever", "Wherever"],
     "表示「无论你说什么」，用 whatever。"),
    ("___ tired he was, he kept walking.",
     "However", ["Whatever", "Although", "As"],
     "however + 形容词 + 主语 + 系动词。"),
    ("Much ___ I respect him, I disagree with him here.",
     "as", ["although", "though", "however"],
     "much 提前 + as 引导让步状语从句。"),
    ("___ it was raining, they went out for a walk.",
     "Although", ["But", "Despite", "However"],
     "后接完整句子，用 although。"),
    ("___ the bad weather, the match went on.",
     "Despite", ["Although", "However", "Because"],
     "空格后是名词短语，用 despite。"),
]


ADV_MANNER = [
    ("Do ___ the instructions say.",
     "as", ["like", "what", "that"],
     "as 引导方式状语从句，表示「按照」。"),
    ("He speaks ___ he had witnessed the whole accident.",
     "as if", ["as", "like", "that"],
     "表示「好像」，用 as if 引导方式状语从句。"),
    ("She looks ___ she were ill.",
     "as if", ["as", "like", "that"],
     "as if 后用虚拟语气 were，表示与事实相反。"),
    ("He did the work ___ I had told him.",
     "as", ["like", "what", "that"],
     "表示「按照我告诉他的方式」，用 as。"),
    ("The more you read, ___ you will write.",
     "the better", ["better", "the best", "the more good"],
     "the + 比较级, the + 比较级 表示「越……越……」。"),
    ("The harder you work, ___ progress you will make.",
     "the more", ["more", "the most", "much more"],
     "the + 比较级结构，后半句同样用比较级。"),
    ("She sings ___ a bird.",
     "like", ["as", "that", "what"],
     "空格后是名词短语，用介词 like；as 后接从句。"),
    ("___ you sow, so shall you reap.",
     "As", ["Like", "That", "What"],
     "谚语 As you sow, so shall you reap。"),
    ("He acted ___ nothing had happened.",
     "as if", ["as", "like", "that"],
     "表示「好像什么都没发生」，用 as if。"),
    ("Leave everything ___ it is.",
     "as", ["like", "that", "what"],
     "表示「保持原样」，用 as 引导方式状语从句。"),
    ("The more we get together, ___ we will be.",
     "the happier", ["happier", "the happiest", "more happy"],
     "the + 比较级, the + 比较级 结构。"),
    ("It looks ___ it is going to snow.",
     "as if", ["as", "like", "that"],
     "表示「看起来好像要下雪」，用 as if。"),
    ("He treats me ___ I were a child.",
     "as if", ["as", "like", "that"],
     "as if 后接虚拟语气 were，表示与事实相反。"),
    ("___ expected, the results were excellent.",
     "As", ["Like", "That", "What"],
     "as expected 是固定结构，表示「正如预料」。"),
]


# ================================================================== 从句（四）从句对比
#
# 这三个点考的不是单个连接词，而是「同一串词在不同句法位置上是哪种从句」。
# 判定顺序固定：先看空格前有没有先行词 → 再看从句缺不缺成分 → 最后看缺的是
# 主/宾/表/状语。顺序一固定，答案就唯一。

CONTRAST_APPOS = [
    ("The evidence ___ he was nowhere near the scene convinced the jury.",
     "that", ["which", "what", "whether"],
     "从句成分完整、that 不作成分，是同位语从句说明 evidence 的内容。"),
    ("The proposal ___ the committee put forward will be voted on Friday.",
     "that", ["what", "whether", "how"],
     "put forward 缺宾语，关系词作宾语，是定语从句。"),
    ("The fact ___ he lied is obvious.",
     "that", ["which", "what", "whether"],
     "从句完整，that 不作成分，是同位语从句。"),
    ("The suggestion ___ we start early was accepted.",
     "that", ["which", "what", "whether"],
     "从句完整，that 说明 suggestion 的内容，是同位语从句。"),
    ("The plan ___ they came up with was rejected.",
     "that", ["what", "whether", "how"],
     "came up with 缺宾语，是定语从句。"),
    ("The news ___ he told me was false.",
     "that", ["what", "where", "when"],
     "told 缺宾语，是定语从句。"),
    ("The belief ___ he will succeed never changed.",
     "that", ["which", "what", "whether"],
     "从句完整，that 不作成分，是同位语从句。"),
    ("The book ___ he recommended is worth reading.",
     "that", ["what", "whether", "how"],
     "recommended 缺宾语，是定语从句。"),
    ("The rumour ___ the factory would close spread quickly.",
     "that", ["which", "what", "whether"],
     "从句完整，that 说明 rumour 的内容，是同位语从句。"),
    ("The idea ___ came to him was brilliant.",
     "that", ["what", "how", "whether"],
     "came to 缺主语，关系词作主语，是定语从句。"),
    ("The promise ___ he made was soon forgotten.",
     "that", ["what", "where", "when"],
     "made 缺宾语，是定语从句。"),
    ("The hope ___ we would win kept us going.",
     "that", ["which", "what", "whether"],
     "从句完整，that 说明 hope 的内容，是同位语从句。"),
    ("The reason ___ he explained was reasonable.",
     "that", ["why", "what", "how"],
     "explained 缺宾语，关系词作宾语用 that；why 只能作原因状语。"),
    ("The order ___ the soldiers should advance was given.",
     "that", ["which", "what", "whether"],
     "从句完整，that 说明 order 的内容，是同位语从句。"),
]


CONTRAST_ADV = [
    ("This is the factory ___ my father worked for thirty years.",
     "where", ["which", "that", "when"],
     "有先行词 the factory 且从句缺地点状语，是定语从句，用 where。"),
    ("He promised ___ he would never be late again.",
     "that", ["which", "where", "when"],
     "promised 后接宾语从句，用 that。"),
    ("Put it ___ you can find it again.",
     "where", ["which", "that", "when"],
     "没有先行词，是地点状语从句，用 where。"),
    ("This is the house ___ we lived in last year.",
     "which", ["where", "when", "what"],
     "lived in 缺宾语，关系词作介词宾语，用 which。"),
    ("I will go ___ you go.",
     "where", ["which", "that", "when"],
     "表示「你去哪我就去哪」，是地点状语从句。"),
    ("Tell me ___ you will be back.",
     "when", ["which", "where", "that"],
     "tell me 后接宾语从句，缺时间状语，用 when。"),
    ("This is the day ___ we first met.",
     "when", ["which", "that", "where"],
     "先行词是 the day，从句缺时间状语，用 when。"),
    ("He went ___ the traffic was heaviest.",
     "where", ["which", "that", "when"],
     "没有先行词，表示「去车最多的地方」，是地点状语从句。"),
    ("She didn't tell me ___ she was crying.",
     "why", ["which", "where", "that"],
     "宾语从句缺原因状语，用 why。"),
    ("That is the reason ___ he gave.",
     "that", ["why", "what", "how"],
     "gave 缺宾语，关系词作宾语用 that。"),
    ("Stay ___ you are.",
     "where", ["which", "that", "when"],
     "没有先行词，是地点状语从句。"),
    ("This is the village ___ I was born.",
     "where", ["which", "that", "when"],
     "先行词是 village，从句缺地点状语，用 where。"),
    ("I know ___ he is honest.",
     "that", ["which", "what", "where"],
     "know 后接宾语从句，从句完整用 that。"),
    ("The school ___ he teaches is very famous.",
     "where", ["which", "that", "when"],
     "teaches 后缺地点状语，用 where 引导定语从句。"),
]


CONTRAST_NEST = [
    ("___ surprised us was that the man who spoke first had once lived where the floods were worst.",
     "What", ["That", "It", "Which"],
     "主语从句缺主语，用 what；后面依次嵌套了 that 表语从句、who 定语从句和 where 状语从句。"),
    ("She said ___ she would call me when she arrived.",
     "that", ["which", "what", "where"],
     "said 后是宾语从句，从句完整用 that；when 引导时间状语从句。"),
    ("He asked me ___ I thought of the plan that the manager had proposed.",
     "what", ["that", "which", "how"],
     "thought of 缺宾语，用 what；that 引导定语从句修饰 plan。"),
    ("The book ___ I read last year, which was written by a famous professor, changed my view.",
     "that", ["what", "who", "whose"],
     "read 缺宾语，第一层定语从句用 that；which 引导非限制性定语从句。"),
    ("___ he told me was that he had lost the key to the room where the documents were kept.",
     "What", ["That", "It", "Which"],
     "主语从句缺宾语，用 what；表语从句用 that；where 引导定语从句。"),
    ("I don't know ___ the man who called you yesterday wanted.",
     "what", ["that", "which", "who"],
     "wanted 缺宾语，宾语从句用 what；who 引导定语从句修饰 man。"),
    ("She told me ___ she had no idea when he would come back.",
     "that", ["which", "what", "when"],
     "told me 后是宾语从句，从句完整用 that；when 引导同位语从句。"),
    ("The fact ___ he didn't know where she lived surprised me.",
     "that", ["which", "what", "whether"],
     "从句完整，that 引导同位语从句；where 引导宾语从句。"),
    ("___ he said was that he would help whoever needed it.",
     "What", ["That", "It", "Which"],
     "主语从句缺宾语用 what；whoever 引导宾语从句并在从句中作主语。"),
    ("He wondered ___ the girl who had smiled at him was.",
     "who", ["that", "which", "what"],
     "从句缺表语且指人，用 who；who 同时引导定语从句修饰 girl。"),
    ("I believe ___ what he said is true.",
     "that", ["which", "what", "whether"],
     "believe 后接宾语从句，从句完整用 that；what 引导主语从句。"),
    ("The news ___ the man who had won the prize was my neighbour spread fast.",
     "that", ["which", "what", "whether"],
     "同位语从句用 that；who 引导定语从句修饰 man。"),
    ("She asked me ___ I had seen the boy who broke the window.",
     "whether", ["that", "which", "what"],
     "表示「是否」的宾语从句用 whether；who 引导定语从句。"),
    ("___ matters is that we are together.",
     "What", ["That", "It", "Which"],
     "主语从句缺主语用 what；表语从句用 that。"),
]


# ------------------------------------------------------------------ 注册表

KP_GEN: dict[str, list] = {}


def _reg(kp: str, fn) -> None:
    KP_GEN.setdefault(kp, []).append(fn)


# 名词
_reg("morph.nouns.plural-forms", _g_plural)
_reg("morph.nouns.compound-plural", _g_compound_plural)
_reg("morph.nouns.possessive", _g_possessive)

# 冠词
_reg("morph.articles.a-an-sound", _g_aan)
for _suffix, _items in ARTICLE_ITEMS.items():
    _reg(f"morph.articles.{_suffix}", _g_article(_items))

# 主谓一致
for _rule in SVA_ITEMS:
    _reg(f"syntax.subject_verb_agreement.{_rule}", _g_sva(_rule))

# 时态
_reg("tense_voice.present_simple.core-meaning", _g_tense(["pres"]))
_reg("tense_voice.present_simple.future-meaning", _g_tense(["pres", "fut"]))
_reg("tense_voice.past_simple.core-meaning", _g_tense(["past"]))
_reg("tense_voice.present_continuous.core-meaning", _g_tense(["cont"]))
_reg("tense_voice.past_continuous.time-reference", _g_tense(["pastcont"]))
_reg("tense_voice.future_simple.will-vs-going-to", _g_future)
_reg("tense_voice.present_simple.future-meaning", _g_future)
_reg("tense_voice.tense_agreement.sequence", _g_agreement)
_reg("tense_voice.present_perfect.durative", _g_durative(False))
_reg("tense_voice.present_perfect_continuous.meaning", _g_durative(True))

# 动词形式
_reg("tense_voice.present_simple.third-person-s", _g_verbform("3sg"))
_reg("morph.verbs.four-forms", _g_verbform("past"))
_reg("tense_voice.past_simple.past-vs-participle", _g_verbform("pp"))
_reg("tense_voice.present_continuous.ing-form", _g_verbform("ing"))

# 被动
_reg("tense_voice.passive.formation", _g_passive(["pres", "past", "perf", "fut"]))
_reg("tense_voice.passive.usage", _g_passive(["pres", "past", "perf"]))
_reg("tense_voice.passive.double-object", _g_double_object)
_reg("tense_voice.passive.no-passive-verbs", _g_passive_trap)
_reg("tense_voice.passive.active-form", _g_passive_trap)
_reg("tense_voice.passive.by-vs-with", _g_passive_trap)

# 特殊句式
_reg("special.tag_question.basic-formation", _g_tag)
_reg("special.tag_question.negative-words", _g_tag)
_reg("special.inversion.negative-fronting", _g_inversion("negative-fronting"))
_reg("special.inversion.only-adverbial", _g_inversion("only-adverbial"))
_reg("special.inversion.subjunctive-inversion", _g_inversion("subjunctive-inversion"))
_reg("special.inversion.so-neither-nor", _g_inversion("so-neither-nor"))
_reg("special.inversion.full-inversion", _g_inversion("full-inversion"))
_reg("special.inversion.as-though-concession", _g_inversion("as-though-concession"))
_reg("special.inversion.such-so-fronting", _g_inversion("such-so-fronting"))
_reg("special.subjunctive.counterfactual-tenses", _g_subj_if)
_reg("special.subjunctive.wish", _g_wish)
_reg("special.emphasis.it-cleft", _g_cleft)
_reg("syntax.it_usage.cleft", _g_cleft)
_reg("special.exclamation.what-how", _g_excl)
_reg("syntax.sentence_types.exclamation", _g_excl)
_reg("special.comparison.multiples", _g_multiple)

# 从句
_reg("clause.relative_clause.who-whom-whose", _g_relative)
_reg("clause.relative_clause.that-vs-which", _g_relative)
_reg("clause.relative_clause.relative-adverbs", _g_relative)

# 句法
_reg("syntax.there_be.existential-agreement", _g_there)
_reg("syntax.there_be.tense-modal", _g_there)
_reg("morph.prepositions.time-in-on-at", _g_prep_time)
_reg("morph.verbs.modal-speculation", _g_modal)
_reg("morph.verbs.modal-perfect", _g_modal)

# 词法
_reg("morph.adj_adv.comparative-superlative-forms", _g_comparative)
_reg("morph.adj_adv.superlative-scope", _g_comparative)
_reg("morph.adj_adv.adverb-vs-adjective", _g_adv)
_reg("morph.numerals.fraction-decimal-percent", _g_numeral)
_reg("morph.numerals.years-ages", _g_numeral)
_reg("morph.numerals.dozen-score-hundred", _g_numeral)

# 非谓语（27 个知识点全覆盖）
_reg("nonfinite.overview.three-forms", _g_nf_judge("function"))
_reg("nonfinite.overview.boundary-with-predicate", _g_nf_judge("boundary"))

_reg("nonfinite.infinitive.subject", _g_nf_obj("it-subj"))
_reg("nonfinite.infinitive.object-complement", _g_nf_obj("want"))
_reg("nonfinite.infinitive.object-complement", _g_nf_obj("make"))
_reg("nonfinite.infinitive.attributive", _g_nf_obj("attr-have"))
_reg("nonfinite.infinitive.attributive", _g_nf_obj("attr-ord"))
_reg("nonfinite.infinitive.adverbial", _g_nf_obj("adv"))
_reg("nonfinite.infinitive.adverbial", _g_nf_obj("too-enough"))
_reg("nonfinite.infinitive.tense-voice", _g_nf_tv("to-perf"))
_reg("nonfinite.infinitive.tense-voice", _g_nf_tv("to-pass"))
_reg("nonfinite.infinitive.to-retention", _g_nf_choice(NF_TO_RET))

_reg("nonfinite.gerund.subject-object", _g_nf_obj("fixed"))
_reg("nonfinite.gerund.gerund-only-verbs", _g_nf_obj("enjoy"))
_reg("nonfinite.gerund.gerund-only-verbs", _g_nf_obj("prep"))
_reg("nonfinite.gerund.compound-structure", _g_nf_choice(NF_COMPOUND))
_reg("nonfinite.gerund.tense-voice", _g_nf_tv("ger-pass"))
_reg("nonfinite.gerund.gerund-vs-infinitive", _g_gerund)

_reg("nonfinite.present_participle.attributive", _g_nf_part("ing-attr"))
_reg("nonfinite.present_participle.adverbial", _g_nf_part("ing-adv"))
_reg("nonfinite.present_participle.perfect-form", _g_nf_part("perf-adv"))
_reg("nonfinite.present_participle.independent-structure", _g_nf_part("abs-ing"))
_reg("nonfinite.past_participle.attributive", _g_nf_part("pp-attr"))
_reg("nonfinite.past_participle.adverbial", _g_nf_part("pp-adv"))
_reg("nonfinite.past_participle.object-complement", _g_nf_part("objcomp"))
_reg("nonfinite.past_participle.vs-present-participle", _g_nf_judge("ing-ed"))

_reg("nonfinite.absolute.formation", _g_nf_part("abs-pp"))
_reg("nonfinite.absolute.with-structure", _g_nf_part("with"))
_reg("nonfinite.absolute.clause-conversion", _g_nf_judge("conv"))

_reg("nonfinite.nonfinite_traps.dangling-modifier", _g_nf_judge("dangling"))
_reg("nonfinite.nonfinite_traps.logical-subject", _g_nf_judge("logical"))
_reg("nonfinite.nonfinite_traps.parallel-forms", _g_nf_judge("parallel"))

# 搭配
_reg("clause.adverbial_clause.result-so-such", _g_sosuch)

# 定语从句（补 6 个点）
_reg("clause.relative_clause.as-vs-which",
     _g_pool_choice(RC_AS_WHICH,
                    "先看空在句首还是句末：句首用 as，句末指代整个主句用 which。"))
_reg("clause.relative_clause.prep-plus-relative", _g_rc_prep)
_reg("clause.relative_clause.restrictive-nonrestrictive",
     _g_pool_choice(RC_NONREST,
                    "有逗号就不能用 that；介词后面指人用 whom、指物用 which。"))
_reg("clause.relative_clause.agreement", _g_rc_agree)
_reg("clause.relative_clause.identification",
     _g_pool_choice(RC_IDENT,
                    "先看空在从句里作不作成分：不作成分的多半是同位语从句或强调句。"))
_reg("clause.relative_clause.reduction",
     _g_pool_fill(RC_REDUCE,
                  "主动用 doing，被动用 done，将来被动用 to be done，序数词后用 to do。"))

# 名词性从句（补 8 个点）
_reg("clause.noun_clause.subject-clause",
     _g_pool_choice(NC_SUBJECT,
                    "句首表示「是否」只能用 whether；从句缺成分才用 what。"))
_reg("clause.noun_clause.object-clause-tense",
     _g_pool_fill(NC_OBJ_TENSE,
                  "客观真理永远用一般现在时；其余按主句时态往过去推一步。"))
_reg("clause.noun_clause.predicative-clause",
     _g_pool_choice(NC_PREDICATIVE,
                    "说明内容用 that；表示「是否」用 whether；缺宾语才用 what。"))
_reg("clause.noun_clause.appositive-vs-relative",
     _g_pool_choice(NC_APPOS,
                    "that 在从句里不作成分 → 同位语从句；作成分 → 定语从句。"))
_reg("clause.noun_clause.that-whether-if",
     _g_pool_choice(NC_WHETHER,
                    "介词后、句首、不定式前、or not 前，一律只能用 whether。"))
_reg("clause.noun_clause.connective-pronouns",
     _g_pool_choice(NC_PRON,
                    "从句缺成分用 what / which / who；有范围限制用 which；"
                    "表示「无论谁」用 whoever。"))
_reg("clause.noun_clause.connective-adverbs",
     _g_pool_choice(NC_ADV,
                    "先问缺的是时间、地点、原因还是方式，再定 when / where / why / how。"))
_reg("clause.noun_clause.order-punctuation",
     _g_pool_choice(NC_ORDER,
                    "从句一律陈述语序：疑问词 + 主语 + 谓语；标点由主句决定。"))

# 状语从句（补 7 个点，result-so-such 已有）
_reg("clause.adverbial_clause.time-when-while-as", _g_adv_time)
_reg("clause.adverbial_clause.future-in-subordinate",
     _g_pool_fill(ADV_FUTURE,
                  "主句用将来时，时间 / 条件状语从句一律用一般现在时。"))
_reg("clause.adverbial_clause.place",
     _g_pool_choice(ADV_PLACE,
                    "没有先行词就是地点状语从句，用 where；有先行词才考虑 which。"))
_reg("clause.adverbial_clause.cause",
     _g_pool_choice(ADV_CAUSE,
                    "空后是名词短语选 because of；是完整句子选 because / since / now that。"))
_reg("clause.adverbial_clause.purpose",
     _g_pool_choice(ADV_PURPOSE,
                    "空后是从句用 so that / in case；是动词原形用 in order to / so as to。"))
_reg("clause.adverbial_clause.condition",
     _g_pool_choice(ADV_CONDITION,
                    "unless 相当于 if not；in case 表示「以防」而不是「如果」。"))
_reg("clause.adverbial_clause.concession",
     _g_pool_choice(ADV_CONCESSION,
                    "让步从句看词性：完整句子用 although / though，名词短语用 despite。"))
_reg("clause.adverbial_clause.manner-comparison",
     _g_pool_choice(ADV_MANNER,
                    "空后是名词短语用 like；是从句用 as；表示「好像」用 as if。"))

# 从句对比（补 3 个点）
_reg("clause.clause_contrast.attributive-vs-appositive",
     _g_pool_choice(CONTRAST_APPOS,
                    "判定顺序：有没有先行词 → 从句缺不缺成分 → 缺的是哪种成分。"))
_reg("clause.clause_contrast.adverbial-vs-attributive",
     _g_pool_choice(CONTRAST_ADV,
                    "有先行词且缺状语才是定语从句；没有先行词就是状语从句。"))
_reg("clause.clause_contrast.nesting-levels",
     _g_pool_choice(CONTRAST_NEST,
                    "从最外层往里拆：先定主句缺什么，再逐层判断每个从句的功能。"))
_reg("morph.pronouns.some-any", _g_someany)


# ------------------------------------------------------------------ 对外接口


def _finalize(raw: dict, kp_id: str) -> dict:
    d = dict(raw)
    d["kp_id"] = kp_id
    key = f"{kp_id}|{d.get('stem','')}|{d.get('answer','')}"
    d["id"] = "v." + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    d["generated"] = True
    d.setdefault("difficulty", 2)
    return d


def has(kp_id: str) -> bool:
    return bool(KP_GEN.get(kp_id))


def supported() -> list[str]:
    return sorted(KP_GEN)


def make(kp_id: str, n: int, seed: str = "") -> list[dict]:
    """生成 n 道互不相同的变式题；不足则返回能生成的全部。"""
    gens = KP_GEN.get(kp_id)
    if not gens or n <= 0:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for i in range(n):
        for attempt in range(12):
            rng = _rng(kp_id, seed, i, attempt)
            fn = gens[attempt % len(gens)]
            try:
                d = _finalize(fn(rng), kp_id)
            except Exception:
                continue
            if d["stem"] in seen:
                continue
            seen.add(d["stem"])
            out.append(d)
            break
    return out


# ================================================================== 池数据包
#
# 词法 / 时态语态 / 句法 / 特殊句式 / 搭配 里还没做模板化的知识点，
# 统一走「纯数据池 + _g_pool_choice」这条路：数据写在 vp_*.py，
# 一个知识点一个 12 条的池，注册只在这里做一句循环。
#
# 之所以把数据挪出去：本文件已经三千多行，模板类知识点（非谓语、从句）
# 的生成逻辑必须留在这里复用，纯题库再往里塞就没人找得到了。

import importlib as _importlib
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

_POOL_MODULES = ("vp_special", "vp_syntax", "vp_tense",
                  "vp_morph", "vp_morph2", "vp_morph3", "vp_colloc")

for _mod_name in _POOL_MODULES:
    try:
        _mod = _importlib.import_module(_mod_name)
    except ModuleNotFoundError as _exc:
        if _exc.name != _mod_name:   # 模块内部依赖缺失要立刻暴露，不能静默吞掉
            raise
        continue
    for _kp_id, _pool in getattr(_mod, "P", {}).items():
        if _kp_id in KP_GEN:          # 已有模板生成器的点不覆盖
            continue
        _hint = (getattr(_mod, "T", {}) or {}).get(_kp_id, "")
        _reg(_kp_id, _g_pool_choice(_pool, _hint))
