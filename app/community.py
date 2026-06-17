from __future__ import annotations

import json
import re
import threading
import time
import uuid
from pathlib import Path

from .config import settings


SCENES = {
    "youth": {
        "label": "Z世代社交",
        "prompt": "方言表情包、宿舍配音、校园挑战榜",
    },
    "elder": {
        "label": "乡音陪伴",
        "prompt": "亲人声音数字人、方言童谣、怀旧问候模板",
    },
    "village": {
        "label": "古村导览",
        "prompt": "AI 方言导览员、文旅讲解、农产品 IP 配音",
    },
    "overseas": {
        "label": "侨乡寻根",
        "prompt": "海外华侨乡音地图、祖辈故事、侨校方言学习卡",
    },
}

DIALECTS = {"cantonese", "sichuanese", "hokkien"}

_LOCK = threading.Lock()


def _community_dir() -> Path:
    settings.community_dir.mkdir(parents=True, exist_ok=True)
    return settings.community_dir


def _posts_path() -> Path:
    return _community_dir() / "posts.json"


def _corrections_path() -> Path:
    return _community_dir() / "corrections.json"


def _now() -> int:
    return int(time.time())


def _read_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _write_list(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _clean_text(value: str | None, max_len: int) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    return cleaned[:max_len]


def _clean_media_url(value: str | None) -> str:
    cleaned = _clean_text(value, 500)
    if not cleaned:
        return ""
    if cleaned.startswith("/media/") or cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    return ""


def list_scenes() -> list[dict]:
    return [{"key": key, **value} for key, value in SCENES.items()]


def list_posts(scene: str | None = None, limit: int = 40) -> list[dict]:
    with _LOCK:
        posts = [post for post in _read_list(_posts_path()) if post.get("status", "visible") == "visible"]
    if scene:
        posts = [post for post in posts if post.get("scene") == scene]
    posts.sort(key=lambda item: (item.get("featured", False), item.get("created_at", 0)), reverse=True)
    return posts[: max(1, min(limit, 100))]


def create_post(payload: dict) -> dict:
    scene = _clean_text(payload.get("scene"), 24)
    dialect = _clean_text(payload.get("dialect"), 24)
    if scene not in SCENES:
        raise ValueError("请选择有效的社区场景")
    if dialect not in DIALECTS:
        raise ValueError("请选择有效的方言")

    title = _clean_text(payload.get("title"), 60)
    body = _clean_text(payload.get("body"), 220)
    dialect_text = _clean_text(payload.get("dialect_text"), 260)
    if len(title) < 2:
        raise ValueError("标题至少需要 2 个字")
    if len(dialect_text) < 2 and len(body) < 2:
        raise ValueError("请填写方言内容或作品说明")

    post = {
        "id": f"cp_{uuid.uuid4().hex[:10]}",
        "scene": scene,
        "scene_label": SCENES[scene]["label"],
        "dialect": dialect,
        "title": title,
        "body": body,
        "source_text": _clean_text(payload.get("source_text"), 260),
        "dialect_text": dialect_text,
        "audio_url": _clean_media_url(payload.get("audio_url")),
        "avatar": _clean_text(payload.get("avatar"), 24) or "sprout",
        "persona": _clean_text(payload.get("persona"), 36) or "乡音数字分身",
        "author": _clean_text(payload.get("author"), 24) or "方言守护者",
        "likes": 0,
        "bookmarks": 0,
        "comments": [],
        "corrections": 0,
        "status": "visible",
        "featured": bool(payload.get("featured", False)),
        "created_at": _now(),
        "updated_at": _now(),
    }
    with _LOCK:
        posts = _read_list(_posts_path())
        posts.append(post)
        _write_list(_posts_path(), posts)
    return post


def react_to_post(post_id: str, action: str) -> dict:
    if action not in {"like", "bookmark"}:
        raise ValueError("暂只支持点赞或收藏")
    with _LOCK:
        posts = _read_list(_posts_path())
        for post in posts:
            if post.get("id") == post_id and post.get("status", "visible") == "visible":
                key = "likes" if action == "like" else "bookmarks"
                post[key] = int(post.get(key, 0)) + 1
                post["updated_at"] = _now()
                _write_list(_posts_path(), posts)
                return post
    raise KeyError("作品不存在")


def add_comment(post_id: str, payload: dict) -> dict:
    text = _clean_text(payload.get("text"), 160)
    if len(text) < 2:
        raise ValueError("评论至少需要 2 个字")
    comment = {
        "id": f"cm_{uuid.uuid4().hex[:8]}",
        "author": _clean_text(payload.get("author"), 24) or "社区成员",
        "text": text,
        "created_at": _now(),
    }
    with _LOCK:
        posts = _read_list(_posts_path())
        for post in posts:
            if post.get("id") == post_id and post.get("status", "visible") == "visible":
                comments = post.setdefault("comments", [])
                comments.append(comment)
                post["updated_at"] = _now()
                _write_list(_posts_path(), posts)
                return comment
    raise KeyError("作品不存在")


def submit_correction(post_id: str, payload: dict) -> dict:
    suggestion = _clean_text(payload.get("suggestion"), 220)
    note = _clean_text(payload.get("note"), 160)
    if len(suggestion) < 2:
        raise ValueError("请填写更地道的方言表达")
    correction = {
        "id": f"cr_{uuid.uuid4().hex[:10]}",
        "post_id": post_id,
        "suggestion": suggestion,
        "note": note,
        "author": _clean_text(payload.get("author"), 24) or "母语者贡献",
        "status": "pending_review",
        "created_at": _now(),
    }
    with _LOCK:
        posts = _read_list(_posts_path())
        matched = None
        for post in posts:
            if post.get("id") == post_id and post.get("status", "visible") == "visible":
                matched = post
                break
        if matched is None:
            raise KeyError("作品不存在")
        correction.update(
            {
                "scene": matched.get("scene", ""),
                "dialect": matched.get("dialect", ""),
                "source_text": matched.get("source_text", ""),
                "current_dialect_text": matched.get("dialect_text", ""),
            }
        )
        corrections = _read_list(_corrections_path())
        corrections.append(correction)
        matched["corrections"] = int(matched.get("corrections", 0)) + 1
        matched["updated_at"] = _now()
        _write_list(_corrections_path(), corrections)
        _write_list(_posts_path(), posts)
    return correction


def seed_posts_if_empty() -> None:
    with _LOCK:
        if _read_list(_posts_path()):
            return
    samples = [
        {
            "scene": "youth",
            "dialect": "cantonese",
            "title": "宿舍晚点名粤语挑战",
            "body": "把普通话开场白转成粤语，用自己的音色做成班级挑战音频。",
            "source_text": "各位评委老师你们好，我们是声临其境项目组。",
            "dialect_text": "各位评委老师，你哋好。我哋係声临其境项目组嘅成员。",
            "avatar": "leaf",
            "persona": "校园方言玩家",
            "author": "暨南同乡会",
            "featured": True,
        },
        {
            "scene": "elder",
            "dialect": "sichuanese",
            "title": "给外婆的早安问候",
            "body": "用子女的声音生成四川话问候，适合每天早上播放。",
            "source_text": "外婆，今天记得按时吃饭，我们周末回来看你。",
            "dialect_text": "外婆，今天记得到点吃饭哈，我们周末回来看到你。",
            "avatar": "home",
            "persona": "亲情陪伴数字人",
            "author": "乡音陪伴计划",
            "featured": True,
        },
        {
            "scene": "village",
            "dialect": "hokkien",
            "title": "古厝入口闽南语导览",
            "body": "游客扫码听方言导览，农产品和村史一起被讲出来。",
            "source_text": "欢迎来到我们的古村，这里保存着百年的家族记忆。",
            "dialect_text": "欢迎来到咱厝的古村，这跤保存着百年的家族记忆。",
            "avatar": "guide",
            "persona": "古村方言导览员",
            "author": "古村导览样例",
            "featured": True,
        },
        {
            "scene": "overseas",
            "dialect": "cantonese",
            "title": "给海外表弟的第一句乡音",
            "body": "把祖辈常说的话做成学习卡，连接海外华裔的乡音记忆。",
            "source_text": "记得常回家看看，家乡的味道一直在这里。",
            "dialect_text": "记得成日返屋企睇下，家乡嘅味道一直喺度。",
            "avatar": "map",
            "persona": "侨乡寻根数字分身",
            "author": "侨校乡音社",
            "featured": True,
        },
    ]
    for sample in samples:
        create_post(sample)
