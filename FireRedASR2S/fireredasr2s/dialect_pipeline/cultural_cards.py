from __future__ import annotations

from typing import Any


_CARDS: list[dict[str, Any]] = [
    {
        "id": "yue_gau_dim",
        "target_dialect": "yue",
        "term": "搞掂",
        "aliases": ["搞定", "搞惦"],
        "meaning": "办妥、处理好、完成一件事。",
        "cultural_note": "粤语日常表达里常用来表示事情已经解决，语气比书面语更轻快、利落。",
        "usage_example": "呢件事我今晚搞掂。",
        "register": "口语",
        "source_label": "粤语常用词资料整理",
        "source_url": "https://www.gdwsw.gov.cn/wsgdjpsk/content/post_41879.html",
    },
    {
        "id": "yue_m4_goi1",
        "target_dialect": "yue",
        "term": "唔该",
        "aliases": ["麻烦你", "多谢"],
        "meaning": "可表示感谢，也常用于请求别人帮忙时的礼貌用语。",
        "cultural_note": "在粤语语境里，唔该经常对应服务、帮忙、递东西等轻量互动，比普通话的单一“谢谢”更依赖场景。",
        "usage_example": "唔该，帮我攞杯水。",
        "register": "礼貌口语",
        "source_label": "粤语礼貌表达资料整理",
        "source_url": "https://www.gdwsw.gov.cn/wsgdjpsk/content/post_41879.html",
    },
    {
        "id": "yue_dim2_gaai2",
        "target_dialect": "yue",
        "term": "点解",
        "aliases": ["为什么", "为乜"],
        "meaning": "为什么、什么原因。",
        "cultural_note": "点解是粤语高频疑问词，常见于口语问因果，也能带出追问、吐槽或不解的语气。",
        "usage_example": "你点解今日咁早返嚟？",
        "register": "口语",
        "source_label": "粤语疑问词资料整理",
        "source_url": "https://www.gdwsw.gov.cn/wsgdjpsk/content/post_41879.html",
    },
    {
        "id": "yue_mou5",
        "target_dialect": "yue",
        "term": "冇",
        "aliases": ["没有", "无"],
        "meaning": "没有。",
        "cultural_note": "冇是粤语核心否定词之一，日常对话中极常见，也是粤语文字化时最容易被识别的特征词。",
        "usage_example": "我今日冇时间。",
        "register": "口语",
        "source_label": "粤语基础词资料整理",
        "source_url": "https://www.gdwsw.gov.cn/wsgdjpsk/content/post_41879.html",
    },
    {
        "id": "yue_mai6_hai6",
        "target_dialect": "yue",
        "term": "唔系",
        "aliases": ["不是", "唔係"],
        "meaning": "不是。",
        "cultural_note": "唔系承担粤语里的基础判断否定，常和句末语气词组合形成更细的态度表达。",
        "usage_example": "唔系我讲嘅。",
        "register": "口语",
        "source_label": "粤语基础词资料整理",
        "source_url": "https://www.gdwsw.gov.cn/wsgdjpsk/content/post_41879.html",
    },
    {
        "id": "sichuan_bashi",
        "target_dialect": "sichuan",
        "term": "巴适",
        "aliases": ["安逸", "舒服"],
        "meaning": "舒服、合适、令人满意。",
        "cultural_note": "巴适常用来表达巴蜀生活里的舒适感和满足感，也能夸食物、天气、安排或体验。",
        "usage_example": "这个火锅吃起巴适。",
        "register": "口语",
        "source_label": "四川话文化资料整理",
        "source_url": "https://chiculture.org.hk/sc/china-five-thousand-years/984",
    },
    {
        "id": "sichuan_yao_de",
        "target_dialect": "sichuan",
        "term": "要得",
        "aliases": ["可以", "行", "好"],
        "meaning": "可以、行、同意。",
        "cultural_note": "要得是四川话里很有代表性的应答词，既可以表示许可，也可以表达爽快答应。",
        "usage_example": "明天早点出发，要得。",
        "register": "口语",
        "source_label": "四川方言资料整理",
        "source_url": "https://www.sc.gov.cn/10462/12771/2016/5/18/10380886.shtml",
    },
    {
        "id": "sichuan_sa_zi",
        "target_dialect": "sichuan",
        "term": "啥子",
        "aliases": ["什么", "啥"],
        "meaning": "什么。",
        "cultural_note": "啥子是四川话常见疑问词，语感直接、生活化，常用于询问事物、原因或对话确认。",
        "usage_example": "你说的是啥子意思？",
        "register": "口语",
        "source_label": "四川方言资料整理",
        "source_url": "https://www.sc.gov.cn/10462/12771/2016/5/18/10380886.shtml",
    },
    {
        "id": "sichuan_wei_sa_zi",
        "target_dialect": "sichuan",
        "term": "为啥子",
        "aliases": ["为什么", "为啥"],
        "meaning": "为什么。",
        "cultural_note": "为啥子在四川话中承担原因追问，常带有自然、亲近的聊天语气。",
        "usage_example": "你为啥子不早点说？",
        "register": "口语",
        "source_label": "四川方言资料整理",
        "source_url": "https://www.sc.gov.cn/10462/12771/2016/5/18/10380886.shtml",
    },
    {
        "id": "sichuan_mo_de",
        "target_dialect": "sichuan",
        "term": "莫得",
        "aliases": ["没有", "没得"],
        "meaning": "没有。",
        "cultural_note": "莫得是四川话常见否定表达，用在生活对话里比书面“没有”更口语、更地方化。",
        "usage_example": "今天莫得空。",
        "register": "口语",
        "source_label": "四川方言资料整理",
        "source_url": "https://www.sc.gov.cn/10462/12771/2016/5/18/10380886.shtml",
    },
]


def match_cultural_cards(text: str, *, target_dialect: str) -> list[dict[str, Any]]:
    if not text:
        return []
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card in _CARDS:
        if card["target_dialect"] != target_dialect:
            continue
        terms = [card["term"], *card.get("aliases", [])]
        hit_terms = [term for term in terms if term and term in text]
        if not hit_terms or card["id"] in seen:
            continue
        payload = dict(card)
        payload["matched_terms"] = hit_terms
        matched.append(payload)
        seen.add(card["id"])
    return matched


def cultural_card_terms(cards: list[dict[str, Any]]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for card in cards:
        term = str(card.get("term") or "")
        if term and term not in seen:
            terms.append(term)
            seen.add(term)
    return terms
