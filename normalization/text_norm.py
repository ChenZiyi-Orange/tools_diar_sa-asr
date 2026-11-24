import html
import re
import unicodedata
from functools import lru_cache

from whisper_normalizer.english import EnglishTextNormalizer

from wetext import Normalizer as _ZhNormalizer

_ZH_NORMALIZER = _ZhNormalizer(lang="zh", operator="tn")

_EN_NORMALIZER = EnglishTextNormalizer()


_BRACKET_PAIRS = {'<': '>', '[': ']', '(': ')', '（': '）'}
_BRACKET_CLOSERS = {closer: opener for opener, closer in _BRACKET_PAIRS.items()}


def _strip_structure_tags(text):
    out = []
    stack = []
    for i, ch in enumerate(text):
        if ch in _BRACKET_PAIRS:
            stack.append((ch, len(out), i))
        elif ch in _BRACKET_CLOSERS:
            opener = _BRACKET_CLOSERS[ch]
            if stack and stack[-1][0] == opener:
                _, out_len, _ = stack.pop()
                del out[out_len:]
            else:
                out.append(ch)
        else:
            out.append(ch)
    return ''.join(out)


def strip_leading_sentence_punct(text):
    return re.sub(r'^[\s.,;:!?]+', '', text)


def _clean_markup(text):
    text = html.unescape(text)
    text = text.translate(str.maketrans({'＆': '&', '＃': '#', '＊': '*', '￥': '¥', '．': '.'}))
    text = text.replace('\xa0', ' ')
    text = re.sub(
        r'[\u200b-\u200f\u202a-\u202e\u2060\ufeff\u00ad\x00-\x1f\x7f]',
        '',
        text,
    )

    started_with_marker = bool(re.match(r'^\s*[*#&$%¥]', text))

    protected = {}
    used = set(text)

    def make_placeholder():
        for codepoint in range(0xE000, 0xF900):
            ch = chr(codepoint)
            if ch not in used:
                used.add(ch)
                return ch
        raise RuntimeError('markup placeholder space exhausted')

    def protect_pattern(pattern):
        nonlocal text
        def repl(match):
            ph = make_placeholder()
            protected[ph] = match.group(0)
            return ph
        text = pattern.sub(repl, text)

    for pattern in (_TARGET_URL, _TARGET_EMAIL, _TARGET_PATH, _TARGET_AMP_TOKEN, _STANDALONE_AMP):
        protect_pattern(pattern)

    text = text.replace('&%&', '')
    punct_marker = re.compile(
        r'([，。！？；：、,.!?;:])\s*(?:[*#]+|&[A-Za-z]?|&|[$%¥]+)+\s*[，。！？；：、,.!?;:]'
    )
    prev = None
    while text != prev:
        prev = text
        text = punct_marker.sub(r'\1', text)
    text = text.replace('#', '')
    text = text.replace('*', '')
    text = re.sub(r'&[A-Za-z](?=\s|[^\x00-\x7F]|$)', '', text)
    text = text.replace('&', '')
    text = re.sub(r'(?<!\d)\$(?!\s*\d)', '', text)
    text = re.sub(r'(?<!\d)¥(?!\s*\d)', '', text)
    def keep_percent(match):
        start = match.start()
        prev = text[start - 1] if start > 0 else ''
        if prev and prev.isdigit():
            return match.group(0)
        return ''

    text = re.sub(r'[ \t]*%', keep_percent, text)
    text = re.sub(r'\.+。', '。', text)
    if started_with_marker:
        text = re.sub(r'^(\s*)[，。！？；：、,.!?;:]+', r'\1', text)
    for ph, token in protected.items():
        text = text.replace(ph, token)
    return text


def _is_cjk(ch):
    o = ord(ch)
    return (
        0x4E00 <= o <= 0x9FFF
        or 0x3400 <= o <= 0x4DBF
        or 0x3040 <= o <= 0x30FF
        or 0xF900 <= o <= 0xFAFF
    )


_HYPHEN_TOKEN = re.compile(r'(?<![A-Za-z0-9])[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+(?![A-Za-z0-9])')
_LATIN = re.compile(r'[A-Za-z\u00C0-\u024F\u1E00-\u1EFF]')
_LATIN_CHAR = re.compile(r'[A-Za-z\u00C0-\u024F\u1E00-\u1EFF]')

_TARGET_TIME = re.compile(
    r"(?i)\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"\d{1,2})(?::\d{2})?\s+o'?clock\b"
)
_TARGET_URL = re.compile(r'https?://[^\s]+|www\.[^\s]+', re.I)
_TARGET_EMAIL = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
_TARGET_PATH = re.compile(r'(?:[A-Za-z]:\\[^\s]+|(?:/[\w.\-]+){2,})')
_TARGET_HASHTAG = re.compile(r'#[A-Za-z0-9_]+')
_TARGET_MENTION = re.compile(r'@[A-Za-z0-9_]+')
_TARGET_O_NAME = re.compile(r"(?<![A-Za-z])[OoDd]'[A-Za-z]+")
_TARGET_POSSESSIVE_NAME = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]*[A-Z][A-Za-z]*(?:'s|')(?![A-Za-z0-9])"
)
_TARGET_ACRONYM = re.compile(r'(?<![A-Za-z0-9])[A-Z]{2,}(?![A-Za-z0-9])')
_TARGET_AMP_TOKEN = re.compile(r'(?<![A-Za-z0-9])[A-Za-z0-9]+(?:&[A-Za-z0-9]+)+(?![A-Za-z0-9])')
_STANDALONE_AMP = re.compile(r'(?<=\s)&(?=\s)')
_CONTRACTION_STEMS = {
    'he', 'she', 'it', 'that', 'this', 'what', 'who', 'where', 'when',
    'why', 'how', 'let', 'here', 'there', 'one', 'everyone', 'someone',
    'nobody', 'anyone', 'everything', 'something', 'nothing', 'which',
}
_TARGET_INTERNAL_UPPER = re.compile(
    r'(?<![A-Za-z0-9])[A-Za-z]*[a-z][A-Z][A-Za-z]*(?![A-Za-z0-9])'
)
_TARGET_VERSION = re.compile(r'(?<![A-Za-z0-9])v?\d+(?:\.\d+){2,}(?![A-Za-z0-9])', re.I)
_TARGET_UNIT = re.compile(
    r'(?<![A-Za-z0-9])\d+(?:\.\d+)?\s*'
    r'(?:°C|°F|kg|mg|g|km/h|m/s|mph|Mbps|Gbps|KB|MB|GB|TB|'
    r'kHz|MHz|GHz|Hz|cm|mm|km|ms|h|m|s)\b',
    re.I,
)
_TARGET_ALNUM_TOKEN = re.compile(r'(?<![A-Za-z0-9])[A-Za-z0-9]+(?![A-Za-z0-9])')
_TARGET_NUMBER = re.compile(
    r"(?<![A-Za-z0-9])(?:[$¥€£]\s*)?[+-]?\d[\d,.]*"
    r"(?::\d{2}(?::\d{2})?)?(?:/\d+)?(?:[%‰])?"
    r"(?![A-Za-z0-9])"
)
_FULLWIDTH_MAP = {0x3000: ' ', 0xFF05: '%', 0xFF04: '$', 0xFF0B: '+', 0xFF0D: '-', 0xFF0F: '/', 0xFF06: '&', 0xFF03: '#', 0xFF0A: '*', 0xFFE5: '¥', 0xFF0E: '.'}
for _cp in range(0xFF10, 0xFF1A):
    _FULLWIDTH_MAP[_cp] = chr(ord('0') + _cp - 0xFF10)
for _cp in range(0xFF21, 0xFF3B):
    _FULLWIDTH_MAP[_cp] = chr(ord('A') + _cp - 0xFF21)
for _cp in range(0xFF41, 0xFF5B):
    _FULLWIDTH_MAP[_cp] = chr(ord('a') + _cp - 0xFF41)


def _normalize_target_ref_unicode(text):
    text = unicodedata.normalize('NFC', text)
    return text.translate(_FULLWIDTH_MAP)


_CJK_SPACE = re.compile(
    r'(?<=[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF\uF900-\uFAFF])'
    r'\s+'
    r'(?=[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF\uF900-\uFAFF])'
)


def _tn_segment_stm(seg, prev_lang):
    if any(_is_cjk(ch) for ch in seg):
        return _ZH_NORMALIZER.normalize(seg), 'zh'
    if _LATIN.search(seg):
        return _EN_NORMALIZER(seg), 'en'
    if prev_lang == 'zh':
        return _ZH_NORMALIZER.normalize(seg), 'zh'
    return _EN_NORMALIZER(seg), 'en'


def _tn_auto_stm(text):
    if not text:
        return ''
    pieces = []
    start = 0
    prev_lang = 'en'
    for i in range(1, len(text)):
        if _is_cjk(text[i]) != _is_cjk(text[i - 1]):
            normalized, prev_lang = _tn_segment_stm(text[start:i], prev_lang)
            pieces.append(normalized)
            start = i
    normalized, prev_lang = _tn_segment_stm(text[start:], prev_lang)
    pieces.append(normalized)
    return ''.join(pieces)


def _is_pua(ch):
    o = ord(ch)
    return 0xE000 <= o <= 0xF8FF


def _is_word_like(ch):
    return ch.isalnum() or _is_pua(ch)


def _lower_latin(text):
    return _LATIN_CHAR.sub(lambda m: m.group(0).lower(), text)


def _protect_target_ref(text):
    mapping = {}
    used = set(text)

    def make_placeholder():
        for codepoint in range(0xE000, 0xF900):
            ch = chr(codepoint)
            if ch not in used:
                used.add(ch)
                return ch
        raise RuntimeError('target-txt placeholder space exhausted')

    def replace(match, predicate=None):
        token = match.group(0)
        if predicate is not None and not predicate(token):
            return token
        placeholder = make_placeholder()
        mapping[placeholder] = token
        return placeholder

    def protect(pattern, predicate=None):
        nonlocal text
        text = pattern.sub(lambda m: replace(m, predicate), text)

    def has_alpha_and_digit(token):
        return any(ch.isalpha() for ch in token) and any(ch.isdigit() for ch in token)

    protect(_TARGET_TIME)
    protect(_TARGET_URL)
    protect(_TARGET_EMAIL)
    protect(_TARGET_PATH)
    protect(_TARGET_HASHTAG)
    protect(_TARGET_MENTION)
    protect(_TARGET_O_NAME)
    protect(
        _TARGET_POSSESSIVE_NAME,
        lambda token: token.rsplit("'", 1)[0].lower() not in _CONTRACTION_STEMS,
    )
    protect(_TARGET_AMP_TOKEN)
    protect(_TARGET_VERSION)
    protect(_TARGET_UNIT)
    protect(_HYPHEN_TOKEN)
    protect(_TARGET_ALNUM_TOKEN, has_alpha_and_digit)
    protect(_TARGET_ACRONYM)
    protect(_TARGET_INTERNAL_UPPER)
    protect(_TARGET_NUMBER)
    return text, mapping


def _restore_target_ref(text, mapping):
    for placeholder, token in mapping.items():
        text = text.replace(placeholder, token)
    return text


def _tn_target_ref_segment(seg):
    if any(_is_cjk(ch) for ch in seg):
        return _ZH_NORMALIZER.normalize(seg)
    if _LATIN.search(seg):
        return _EN_NORMALIZER(seg)
    return seg


def _tn_target_ref(text):
    if not text:
        return ''
    pieces = []
    start = 0
    for i in range(1, len(text)):
        if _is_cjk(text[i]) != _is_cjk(text[i - 1]):
            pieces.append(_tn_target_ref_segment(text[start:i]))
            start = i
    pieces.append(_tn_target_ref_segment(text[start:]))
    return ''.join(pieces)


def _normalize_cjk_spacing(text):
    text = _CJK_SPACE.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip()

    out = []
    for i, ch in enumerate(text):
        if i > 0:
            prev = text[i - 1]
            if (
                prev != ' '
                and ch != ' '
                and _is_cjk(prev) != _is_cjk(ch)
                and _is_word_like(prev)
                and _is_word_like(ch)
            ):
                out.append(' ')
        out.append(ch)
    text = ''.join(out)
    return re.sub(r'\s+', ' ', text).strip()


_CJK_PUNCT_MAP = {
    ',': '，',
    '?': '？',
    '!': '！',
    ';': '；',
    ':': '：',
}


def _restore_cjk_punct(text):
    out = []
    for i, ch in enumerate(text):
        if ch in _CJK_PUNCT_MAP:
            j = i - 1
            while j >= 0 and (
                text[j].isspace()
                or _is_pua(text[j])
                or (not text[j].isalnum() and not _is_cjk(text[j]))
            ):
                j -= 1
            if j >= 0 and _is_cjk(text[j]):
                ch = _CJK_PUNCT_MAP[ch]
        out.append(ch)
    return ''.join(out)


def _cleanup_punct_spacing(text):
    text = re.sub(r'\s+([,.!?;:，。！？；：、])', r'\1', text)
    text = re.sub(r'([，。！？；：、])\s+', r'\1', text)
    return text


def _normalize_ellipsis(text):
    cjk_count = sum(1 for ch in text if _is_cjk(ch))
    latin_count = len(_LATIN.findall(text))
    replacement = '……' if cjk_count > 0 and cjk_count >= latin_count else '...'
    return re.sub(r'\.{3,}', replacement, text)


def _space_after_english_punct(text):
    return re.sub(r'([,;:!?])(?=[A-Za-z])', r'\1 ', text)


def _replace_punct(text, keep_identifier_hyphen=True):
    digit_internal = set('.,:-/')
    percent_signs = set('%‰')
    out = []
    for i, ch in enumerate(text):
        if ch != "'" and unicodedata.category(ch).startswith('P'):
            left = text[i - 1] if i > 0 else ''
            right = text[i + 1] if i + 1 < len(text) else ''
            if ch in digit_internal and left.isdigit() and right.isdigit():
                out.append(ch)
            elif ch in '+-' and right.isdigit() and not left.isdigit():
                out.append(ch)
            elif ch in percent_signs and left.isdigit():
                out.append(ch)
            elif (
                keep_identifier_hyphen
                and ch == '-'
                and left.isalnum()
                and right.isalnum()
                and (left.isdigit() or right.isdigit())
            ):
                out.append(ch)
            else:
                out.append(' ')
        else:
            out.append(ch)
    return ''.join(out)


def _tokenize(text, to_char):
    if not to_char:
        return text.split()
    tokens = []
    buf = []
    for ch in text:
        if ch.isspace():
            if buf:
                tokens.append(''.join(buf))
                buf = []
        elif _is_cjk(ch):
            if buf:
                tokens.append(''.join(buf))
                buf = []
            tokens.append(ch)
        else:
            buf.append(ch)
    if buf:
        tokens.append(''.join(buf))
    return tokens


@lru_cache(maxsize=262144)
def normalize_metric(text, lang='auto', to_char=None, case_sensitive=False):
    if to_char is None:
        to_char = lang != 'en'
    text = _clean_markup(text)
    text = _strip_structure_tags(text)
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(
        r"(?<=[A-Za-z0-9\u00C0-\u024F\u1E00-\u1EFF])\u2019"
        r"(?=[A-Za-z\u00C0-\u024F\u1E00-\u1EFF])",
        "'",
        text,
    )
    text = re.sub(r'(?<=\d)[ \t]+(?=[%‰])', '', text)
    if lang == 'zh':
        text = _ZH_NORMALIZER.normalize(text)
    elif lang == 'en':
        text = _EN_NORMALIZER(text)
    else:
        text = _tn_auto_stm(text)
    text = _replace_punct(text, keep_identifier_hyphen=False)
    text = re.sub(r'\s+', ' ', text).strip()
    if not case_sensitive:
        text = text.upper()
    return ' '.join(_tokenize(text, to_char))


@lru_cache(maxsize=262144)
def normalize_target_txt(text, lang='auto', case_sensitive=False):
    text = _clean_markup(text)
    text = _strip_structure_tags(text)
    text = _normalize_target_ref_unicode(text)
    text = re.sub(
        r"(?<=[A-Za-z0-9\u00C0-\u024F\u1E00-\u1EFF])\u2019",
        "'",
        text,
    )
    text = re.sub(r'(?<=\d)[ \t]+(?=[%‰])', '', text)
    text, mapping = _protect_target_ref(text)
    text = _normalize_ellipsis(text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not case_sensitive:
        text = _lower_latin(text)
    text = _normalize_cjk_spacing(text)
    text = _restore_cjk_punct(text)
    text = _cleanup_punct_spacing(text)
    text = _space_after_english_punct(text)
    text = _restore_target_ref(text, mapping)
    return re.sub(r'\s+', ' ', text).strip()
