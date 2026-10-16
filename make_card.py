#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
展示小卡生成器 — 手机阅读尺寸（CSS 540×960 → 截图 1080×1920 PNG）
定位：展示**较多句话的思考/段落文章**的阅读卡（不是金句卡），文字放不下自动分页。
支持图文卡（配图 base64 内嵌，HTML 自包含）。

用法示例：
  # 纯文字阅读卡（默认纸墨橙）
  python3 make_card.py --text "多段思考…" --tag 随笔 --out card --png card.png

  # 自动分页：超过单页容量时拆成多张，页码标记 1/N
  python3 make_card.py --text-file essay.txt --out essay --png png路径前缀

  # 图文卡：配图在上（默认），文在下；fill 为整卡背景图+文字压暗部（仅限单页）
  python3 make_card.py --text "…" --image photo.jpg --img-pos top --out card --png card.png
  python3 make_card.py --text "…" --image photo.jpg --img-pos bottom --out card --png card.png
  python3 make_card.py --text "…" --image photo.jpg --img-pos fill --out card --png card.png
  # 配图高度可调（240-560，默认 400）

  # 六套配色各出一张（给用户挑）
  python3 make_card.py --text "…" --theme-all --outdir preview/

  # 批量：cards.json（数组，字段同 CLI，含 image/img_pos/img_h）
  python3 make_card.py --cards cards.json

文本内支持：\n\n 分段；\n 段内换行；**重点词** 高亮为强调色加粗
"""
import argparse, base64, json, os, re, subprocess, sys, time

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ============ 推荐配色（7 套） ============
# "key" = 重点色：末段最后一句、段首 "! " 标记的段落（2026-10-16 浥之命名）
# "body" = 正文普通色：除重点色位置外的全部正文（与重点色相对，2026-10-16 浥之命名）
THEMES = {
    "azure":  {"name": "白底亮蓝（默认）", "bg": "#FFFFFF", "bg2": "#DEEBF9", "ink": "#1F5AB8",
               "acc": "#2E7CE6", "hl": "#1F5AB8", "mute": "#7C9BD4", "line": "#D5E5F9",
               "body": "#1F5AB8", "panel": "#EDF4FC", "key": "#D9320D"},
    "paper":  {"name": "纸墨橙",   "bg": "#F7F4ED", "bg2": "#F7F4ED", "ink": "#17150F", "acc": "#E8420A",
               "mute": "#8F887B", "line": "#DCD5C6", "body": "#33302B", "panel": "#FCF0E8", "key": "#C21A0A"},
    "noir":   {"name": "墨夜金",   "bg": "#17171B", "bg2": "#17171B", "ink": "#F3F0E7", "acc": "#D9A441",
               "mute": "#8B8A82", "line": "#2F2F37", "body": "#D8D5CC", "panel": "#22222A", "key": "#E6452E"},
    "mist":   {"name": "雾霭蓝",   "bg": "#F0F4F8", "bg2": "#F0F4F8", "ink": "#1B2733", "acc": "#33689B",
               "mute": "#7D8B98", "line": "#D3DDE6", "body": "#2C3A46", "panel": "#E8F1F9", "key": "#C0392B"},
    "matcha": {"name": "抹茶",     "bg": "#F1F5EC", "bg2": "#F1F5EC", "ink": "#22301F", "acc": "#4E7C43",
               "mute": "#87977E", "line": "#D5E0CB", "body": "#31402C", "panel": "#EAF2E3", "key": "#C0392B"},
    "blush":  {"name": "玫瑰",     "bg": "#FAF1F0", "bg2": "#FAF1F0", "ink": "#3A2226", "acc": "#B4434E",
               "mute": "#A08889", "line": "#ECD8D6", "body": "#4A3236", "panel": "#F7E7E6", "key": "#A61B2B"},
    "mono":   {"name": "极简黑白", "bg": "#FFFFFF", "bg2": "#FFFFFF", "ink": "#111111", "acc": "#111111",
               "mute": "#9A9A9A", "line": "#E4E4E4", "body": "#2A2A2A", "panel": "#F4F4F4", "key": "#C41E10"},
    # ---- 2026-10-16 扩展：围绕「正文普通色 + 重点色」双色体系设计 ----
    "linen":  {"name": "亚麻纸",   "bg": "#FBF7EF", "bg2": "#F2EADB", "ink": "#2E2416",
               "acc": "#B8742C", "hl": "#4A3B2A", "mute": "#A89478", "line": "#E5DCC9",
               "body": "#4A3B2A", "panel": "#F6EFDF", "key": "#1F6E68"},
    "pine":   {"name": "松烟",     "bg": "#F5F9F3", "bg2": "#E3EEDD", "ink": "#1E3522",
               "acc": "#4F7D52", "hl": "#2F5233", "mute": "#8AA087", "line": "#D4E3CD",
               "body": "#2F5233", "panel": "#ECF4E6", "key": "#9B2242"},
    "plum":   {"name": "紫檀",     "bg": "#FBF9FD", "bg2": "#EFE9F7", "ink": "#332653",
               "acc": "#7A5FB8", "hl": "#4C3B78", "mute": "#9C90B8", "line": "#E0D7F0",
               "body": "#4C3B78", "panel": "#F4EEFB", "key": "#B8721E"},
    "graphite": {"name": "石墨",   "bg": "#FFFFFF", "bg2": "#F0F1F3", "ink": "#16181D",
               "acc": "#4A4E57", "hl": "#2E3138", "mute": "#9095A0", "line": "#E2E4E8",
               "body": "#2E3138", "panel": "#F2F3F5", "key": "#D93A1E"},
    "dusk":   {"name": "暮蓝（深）", "bg": "#191D26", "bg2": "#12141C", "ink": "#EDF0F6",
               "acc": "#6B87C7", "hl": "#EDF0F6", "mute": "#7A8699", "line": "#2B3040",
               "body": "#C2CAD9", "panel": "#1F2431", "key": "#FF8A4C"},
}

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".webp": "image/webp", ".gif": "image/gif"}

# 可选字号（大到小）与对应行高（2026-10-16 信息密度调优：行高全档下调 +0.1 内收，加 17px 档）
FS_LIST = [22, 20, 18, 17, 16, 15]
LH = {22: 1.8, 20: 1.85, 18: 1.9, 17: 1.9, 16: 1.9, 15: 1.9}
MAX_PAGES = 4
# 画布尺寸（CSS 像素，截图 ×2）
CARD_W = 540
CARD_H = 720             # 4:3 定稿（2026-10-16 浥之拍板）：卡片越方越矮，手机屏宽约束下整卡显示越完整、字体体感越大——字号像素不是目的，读者体感才是
# 盒模型常量（与 TPL 中的 padding/间距保持一致）
CONTENT_W = 472          # 540 - 34*2
CONTENT_H = 644          # 720 - 42 - 34
ANCHOR_H = 24            # 顶部锚点短横线 3 + 下间距 20（无配图且无品牌水印时才有）
TOP_ROW = 40             # 顶部行高（品牌/邮箱）+ 分隔线 1.5 + 下内距 10 + 下间距 10
TITLE_BLOCK = 96         # 标题 28px*1.4 + 上边距28 + 强调条4 + 下边距24
FOOT_BLOCK = 44          # 页脚上边距 6 + 页脚线 1.5 + padding 10 + 一行备注

TPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  html,body{width:__CW__px;height:__CH__px;overflow:hidden;}
  body{font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;background:linear-gradient(180deg,__BG__ 0%,__BG2__ 100%);}
  .card{position:relative;width:100%;height:100%;display:flex;flex-direction:column;overflow:hidden;}
  .media{flex:none;width:100%;height:__MH__px;overflow:hidden;position:relative;background:__LINE__;}
  .media img{width:100%;height:100%;object-fit:cover;display:block;}
  .media.fill{position:absolute;top:0;left:0;height:__CH__px;}
  .scrim{position:absolute;top:0;left:0;right:0;bottom:0;background:linear-gradient(180deg,rgba(0,0,0,.18) 0%,rgba(0,0,0,.38) 50%,rgba(0,0,0,.84) 100%);}
  .content{flex:1;min-height:0;padding:42px 34px 34px;display:flex;flex-direction:column;position:relative;}
  .anchor{width:28px;height:3px;background:__ACC__;border-radius:2px;margin-bottom:20px;flex:none;}
  .top{display:flex;align-items:center;justify-content:space-between;gap:10px;flex:none;border-bottom:1.5px solid __LINE__;padding-bottom:10px;margin-bottom:10px;}
  .dogear{position:absolute;right:0;bottom:0;width:__DS__px;height:__DS__px;line-height:0;pointer-events:none;}
  .top .left{display:flex;align-items:center;gap:10px;}
  .top .right{display:flex;align-items:center;gap:14px;}
  .pill{background:__INK__;color:__BG__;font-size:11px;font-weight:700;letter-spacing:.18em;padding:5px 13px;border-radius:99px;}
  .src{font-size:10px;color:__MUTE__;letter-spacing:.14em;font-weight:600;text-align:right;}
  .brand{font-size:12.5px;font-weight:500;color:__MUTE__;letter-spacing:.1em;}
  .top .email{font-size:12.5px;color:__MUTE__;letter-spacing:.1em;font-weight:500;white-space:nowrap;}
  .panel{background:__PANEL__;border-left:3px solid __ACC__;border-radius:0 10px 10px 0;padding:14px 16px;margin:0 0 0.75em;}
  .panel:last-child{margin-bottom:0;}
  .title{font-size:28px;font-weight:900;color:__INK__;line-height:1.4;white-space:pre-line;margin:28px 0 6px;letter-spacing:.01em;}
  .trule{width:34px;height:4px;background:__ACC__;border-radius:2px;margin-bottom:24px;}
  .body{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:flex-start;}
  .text{font-size:__FS__px;line-height:__LH__;color:__BODY__;letter-spacing:.02em;text-align:justify;}
  .text p{margin:0 0 0.75em;}
  .text p:last-child{margin-bottom:0;}
  .text b{color:__HL__;text-decoration:underline;text-decoration-color:__ACC__;text-decoration-thickness:1.5px;text-underline-offset:5px;}
  .text .endmark{display:inline-block;width:7px;height:7px;background:__ACC__;margin-left:8px;border-radius:1px;}
  .text .final{color:__KEY__;}
  .text p.keyp{color:__KEY__;}
  .datemark{position:absolute;right:22px;bottom:4px;font-family:"Didot","Baskerville",Georgia,serif;font-style:italic;font-size:70px;line-height:1;letter-spacing:.02em;color:__MUTE__;opacity:.30;pointer-events:none;white-space:nowrap;}
  .text .leadin{}
  .text .dropcap{font-size:1.85em;color:__INK__;line-height:1;display:inline-block;vertical-align:-.06em;}
  .foot{margin-top:6px;border-top:1.5px solid __LINE__;padding-top:10px;display:flex;align-items:center;gap:10px;flex:none;}
  .foot .bar{width:26px;height:4px;background:__ACC__;border-radius:2px;flex:none;}
  .foot .note{font-size:10.5px;color:__MUTE__;letter-spacing:.04em;line-height:1.5;}
  .foot .date{margin-left:auto;margin-right:8px;font-size:12.5px;color:__MUTE__;letter-spacing:.1em;font-weight:500;white-space:nowrap;font-variant-numeric:tabular-nums;}
  __EXTRA__
</style>
</head>
<body>
  <div class="card">
    __DOGEAR__
    __DATEMARK__
    __MEDIA_PRE__
    <div class="content">
      __ANCHORHTML____TOPHTML__
      __TITLEHTML__
      <div class="body"><div class="text">__TEXT__</div></div>
      __FOOT__
    </div>
    __MEDIA_POST__
  </div>
</body>
</html>
"""

FILL_EXTRA = """
  .card .content{justify-content:flex-end;}
  .card .top{position:absolute;top:0;left:0;right:0;padding:42px 34px 0;}
  .card .anchor{display:none;}
  .card .dogear{display:none;}
  .card .datemark{display:none;}
"""

# 右下角折角线：单条 mute 色斜线（无三角面，2026-10-16 浥之定稿：线内外颜色不变）。
# 位于 content 之下（背景层）：日期脚注压在线上面。
# 尺寸 68px：斜线左端到 (右-68, 底)。安全边界校验：正文右边缘在距右边 34px 处，
# 正文最底一行距底约 65px（有页脚）/ 34px（无页脚），此时斜线分别位于距右边 3px / 34px，
# 均不侵入正文；日期脚注区域允许重叠，不避让。
DOGEAR_SIZE = 68
DOGEAR = (f'<div class="dogear"><svg width="{DOGEAR_SIZE}" height="{DOGEAR_SIZE}" '
          f'viewBox="0 0 {DOGEAR_SIZE} {DOGEAR_SIZE}" '
          'xmlns="http://www.w3.org/2000/svg">'
          f'<path d="M0 {DOGEAR_SIZE} L{DOGEAR_SIZE} 0" stroke="__MUTE__" '
          'stroke-opacity="0.55" stroke-width="1.6" fill="none"/>'
          '</svg></div>')

# 正文衬线开关（--serif）：正文/标题换宋体，四角家具保持黑体——出版感 A/B 用
SERIF_EXTRA = """
  .text,.title{font-family:"Songti SC","Noto Serif SC","STSong",serif;}
"""

# MiSans 几何中文（小米，免费商用）：科技/商业感的正文字体，B 方案定稿
# 实现：本地 fonts/MiSans.css（unicode-range 子集 100 片），URL 已重写为 jsdelivr CDN，
# 渲染时 Chrome 只拉取正文用到的子集（几十 KB）。离线渲染会静默回落苹方。
MISANS_CSS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "MiSans.css")
_MISANS_CACHE = None


def misans_css() -> str:
    global _MISANS_CACHE
    if _MISANS_CACHE is None:
        css = open(MISANS_CSS, encoding="utf-8").read()
        _MISANS_CACHE = css + """
  body{font-family:MiSans,-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB",sans-serif;}
"""
    return _MISANS_CACHE


CJK = r"㐀-鿿　-〿＀-｟"


def smart_quotes(s: str) -> str:
    """渲染层智能引号：成对半角双引号 → 全角“”（不动原文文本）。"""
    return re.sub(r'"([^"]*)"', lambda m: "“" + m.group(1) + "”", s)


def pangu(s: str) -> str:
    """盘古之白：中西文/数字与中文之间的间隙统一。
    先收敛边界处的半角空格，再插入窄空格（只影响视觉，不动原文文本）。"""
    s = re.sub(f"([{CJK}])[ \\t]+([A-Za-z0-9])", r"\1\2", s)
    s = re.sub(f"([A-Za-z0-9])[ \\t]+([{CJK}])", r"\1\2", s)
    THIN = "\u2009"  # 窄空格
    s = re.sub(f"([{CJK}])([A-Za-z0-9])", lambda m: m.group(1) + THIN + m.group(2), s)
    s = re.sub(f"([A-Za-z0-9])([{CJK}])", lambda m: m.group(1) + THIN + m.group(2), s)
    return s


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rich(s: str) -> str:
    """转义 HTML、字面 \\n 变真实换行、\\n\\n 分段、**xx** 变强调色 <b>。返回 <p> 列表 HTML。"""
    s = esc(s).replace("\\n\\n", "\n\n").replace("\\n", "\n")
    paras = [p.strip() for p in re.split(r"\n{2,}", s) if p.strip()]
    out = []
    for p in paras:
        p = p.replace("\n", "<br>")
        p = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", p)
        out.append(f"<p>{p}</p>")
    return "".join(out)


def paras_of(text: str):
    """按 \\n\\n 分段；段首 '> ' 标记为重点面板块（markdown 引用语法），标记保留在段文本里。"""
    s = text.replace("\\n\\n", "\n\n").replace("\\n", "\n")
    return [p.strip() for p in re.split(r"\n{2,}", s) if p.strip()]


def plain_len(s: str) -> int:
    if s.startswith("> ") or s.startswith("! "):
        s = s[2:]
    return len(re.sub(r"[\n*]", "", s))


def capacity(fs: int, media_h: int, has_title: bool, has_note: bool,
             n_paras: int, has_top: bool = True, has_anchor: bool = True) -> int:
    """按盒模型精确估算该页可容纳的字符数。fill 模式传 media_h=600 近似（文字压底部约四成区域）。"""
    usable = CONTENT_H - (TOP_ROW if has_top else 0) \
        - (TITLE_BLOCK if has_title else 0) \
        - (FOOT_BLOCK if has_note else 0) - media_h \
        - (ANCHOR_H if (has_anchor and not media_h) else 0)
    if usable < fs * 3:
        return 0
    line_h = fs * LH[fs]
    lines = usable / line_h
    para_overhead = n_paras * 0.75 / LH[fs]  # 每段 margin 0.75em（信息密度调优）
    text_lines = max(1.0, lines - para_overhead)
    cpl = CONTENT_W / (fs * 1.04)  # letter-spacing 补偿
    return int(text_lines * cpl)


def fits(group, fs: int, media_h: int, has_title: bool, has_note: bool,
         has_top: bool = True, has_anchor: bool = True) -> bool:
    n = sum(plain_len(p) for p in group)
    # 面板块有 28px 内边距，按每块 +1.5 段开销折算
    n_paras_eff = len(group) + sum(1.5 for p in group if p.startswith("> "))
    cap = int(capacity(fs, media_h, has_title, has_note, n_paras_eff,
                       has_top, has_anchor) * 0.97)  # 3% 安全余量
    return n <= cap


def paginate(text: str, media_h: int, has_title: bool, has_note: bool,
             has_top: bool = True, has_anchor: bool = True):
    """按容量顺序装箱分页，逐页精确校验。返回 [(段列表, fs, lh)]。配图只算在第一页。"""
    paras = paras_of(text)
    n = sum(plain_len(p) for p in paras)

    def try_fs(fs: int):
        groups, cur = [], []
        for p in paras:
            trial = cur + [p]
            if fits(trial, fs, media_h if not groups else 0,
                    has_title, has_note, has_top, has_anchor):
                cur = trial
            else:
                groups.append(cur)
                cur = [p]
                if not fits(cur, fs, 0, has_title, has_note, has_top, has_anchor):
                    return None  # 单段都放不下，字号无效
        groups.append(cur)
        return groups

    for pages in range(1, MAX_PAGES + 1):
        for fs in FS_LIST:
            groups = try_fs(fs)
            if groups is None:
                continue
            if len(groups) <= pages:
                return [(g, fs, LH[fs]) for g in groups]
    sys.exit(f"文本约 {n} 字，超过 {MAX_PAGES} 页容量。请精简或手动拆分。")


def media_html(card: dict):
    """返回 (html片段, {"pos":..., "h":...})；无图返回 ("", None)。图片 base64 内嵌。"""
    img = str(card.get("image", "")).strip()
    if not img:
        return "", None
    path = os.path.expanduser(img)
    if not os.path.exists(path):
        sys.exit(f"配图不存在: {path}")
    ext = os.path.splitext(path)[1].lower()
    mime = MIME.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    pos = str(card.get("img_pos", "top"))
    if pos not in ("top", "bottom", "fill"):
        sys.exit(f"img_pos 只支持 top/bottom/fill，收到: {pos}")
    tag = f'<img src="data:{mime};base64,{b64}">'
    if pos == "fill":
        return f'<div class="media fill">{tag}<div class="scrim"></div></div>', {"pos": pos, "h": CARD_H}
    h = max(240, min(560, int(card.get("img_h", 400))))
    block = f'<div class="media" style="height:{h}px">{tag}</div>'
    return block, {"pos": pos, "h": h}


def render_page(card: dict, page_paras, fs: int, lh: float,
                page_no: int, total_pages: int, t: dict, extra: str,
                media: str, minfo) -> str:
    # page_paras 已是 HTML 片段（<p> 或 .panel 块）
    text_html = "".join(page_paras)

    tag = str(card.get("tag", "")).strip()
    src = str(card.get("src", "")).strip()
    brand = str(card.get("brand", "")).strip()
    email = str(card.get("email", "")).strip()
    date = str(card.get("date", "")).strip()
    note = str(card.get("note", "")).strip()
    title = str(card.get("title", "")).strip()

    # 顶部行：左上品牌水印 + 胶囊，右侧来源。全空则整行不渲染。
    if total_pages > 1 and tag:
        tag = f"{tag} {page_no}/{total_pages}"
    left_items = []
    if brand:
        left_items.append(f'<span class="brand">{esc(pangu(brand))}</span>')
    if tag:
        left_items.append(f'<span class="pill">{esc(tag)}</span>')
    left = "".join(left_items)
    right_items = []
    if src:
        right_items.append(f'<span class="src">{esc(src)}</span>')
    if email:
        right_items.append(f'<span class="email">{esc(email)}</span>')
    if left or right_items:
        right = f'<span class="right">{"".join(right_items)}</span>' if right_items else ""
        tophtml = f'<div class="top"><span class="left">{left}</span>{right}</div>'
    else:
        tophtml = ""
    titlehtml = (f'<div class="title">{esc(pangu(title)).replace(chr(92)+"n", "<br>")}</div>'
                 f'<div class="trule"></div>') if title else ""
    # 日期形态（date_style）：mark = 右下大字 Didot 水印（定稿默认）；small = 旧版页脚小日期
    date_style = card.get("date_style") or "mark"
    datemark = ""
    if date_style == "mark":
        if date:
            m = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$", date)
            wm = f"{m.group(1)}.{int(m.group(2)):02d}.{int(m.group(3)):02d}" if m else date
            datemark = f'<div class="datemark">{esc(wm)}</div>'
        dtxt = f"{page_no}/{total_pages}" if total_pages > 1 else ""
    else:
        dparts = [date] if date else []
        if total_pages > 1:
            dparts.append(f"{page_no}/{total_pages}")
        dtxt = pangu(" · ".join(dparts))
    foot = ""
    if note or dtxt:
        date_html = f'<span class="date">{esc(dtxt)}</span>' if dtxt else ""
        note_html = f'<span class="note">{esc(pangu(note))}</span>' if note else ""
        foot = f'<div class="foot"><span class="bar"></span>{note_html}{date_html}</div>'

    media_pre = media if (minfo and minfo["pos"] in ("top", "fill")) else ""
    media_post = media if (minfo and minfo["pos"] == "bottom") else ""
    # 顶部锚点短横线：无配图且无品牌水印时才需要（品牌水印本身就是顶部锚点）
    anchorhtml = "" if (media_pre or brand) else '<div class="anchor"></div>'

    html = TPL
    for k, v in {
        "__BG__": t["bg"], "__BG2__": t.get("bg2", t["bg"]), "__INK__": t["ink"], "__ACC__": t["acc"],
        "__MUTE__": t["mute"], "__LINE__": t["line"], "__BODY__": t["body"],
        "__PANEL__": t.get("panel", t["bg"]), "__HL__": t.get("hl", t["acc"]),
        "__KEY__": t.get("key", t["acc"]),
        "__TOPHTML__": tophtml, "__ANCHORHTML__": anchorhtml, "__TITLEHTML__": titlehtml,
        "__TEXT__": text_html, "__FS__": fs, "__LH__": lh,
        "__FOOT__": foot,
        "__MEDIA_PRE__": media_pre, "__MEDIA_POST__": media_post,
        "__DOGEAR__": DOGEAR.replace("__BG__", t["bg"]).replace("__MUTE__", t["mute"]),
        "__DATEMARK__": datemark,
        "__DS__": DOGEAR_SIZE,
        "__MH__": minfo["h"] if minfo else 0, "__EXTRA__": extra,
        "__CW__": CARD_W, "__CH__": CARD_H,
    }.items():
        html = html.replace(k, str(v))
    return html


def render(card: dict):
    """返回该卡的 HTML 列表（自动分页时多张）。"""
    theme_key = card.get("theme", "azure")
    if theme_key not in THEMES:
        sys.exit(f"未知主题: {theme_key}（可选: {', '.join(THEMES)}）")
    t = dict(THEMES[theme_key])
    text = str(card.get("text", "")).strip()
    if not text:
        sys.exit("text 为空")

    media, minfo = media_html(card)
    pos = minfo["pos"] if minfo else None
    if pos == "fill":
        media_h = int(CARD_H * 0.55)  # fill 模式文字压底部约四成区域，容量按此近似
    else:
        media_h = minfo["h"] if minfo else 0

    # fill 模式：文字压在暗部渐变上，整体转白色系
    extra = ""
    if pos == "fill":
        t.update(ink="#FFFFFF", mute="rgba(255,255,255,.72)",
                 line="rgba(255,255,255,.28)", body="#F5F5F5")
        extra = FILL_EXTRA
    if card.get("serif"):
        extra += SERIF_EXTRA
    if card.get("misans"):
        extra += misans_css()

    has_title = bool(str(card.get("title", "")).strip())
    has_note = bool(str(card.get("note", "")).strip())
    has_brand = bool(str(card.get("brand", "")).strip())
    has_top = bool(has_brand or str(card.get("tag", "")).strip()
                   or str(card.get("src", "")).strip()
                   or str(card.get("email", "")).strip())
    has_foot = bool(has_note or str(card.get("date", "")).strip())
    pages = paginate(text, media_h, has_title, has_foot, has_top,
                     has_anchor=not has_brand)
    if pos == "fill" and len(pages) > 1:
        sys.exit("fill 模式仅支持单页。文字过长请改用 top/bottom 或精简。")

    # 多页时配图只放第一页，其余页纯文字
    outs = []
    total = len(pages)
    for i, (pg_paras, fs, lh) in enumerate(pages, 1):
        pg_media = media if i == 1 else ""
        pg_minfo = minfo if i == 1 else None
        # **xx** 高亮；段首 "> " 渲染为浅色面板块；段首冒号在 22 字内 → 引导词深蓝加粗；
        # 整段只有引导词（如「我近年来的思考：」）→ kicker 行（深蓝加粗、字号 +1）
        pg_html = []
        for j, p in enumerate(pg_paras):
            first = (i == 1 and j == 0)  # 全篇首字：只在第一页第一段放大
            last = (i == total and j == len(pg_paras) - 1)  # 全篇末段 → 结束符
            is_panel = p.startswith("> ")
            is_key = p.startswith("! ")  # 段首 "! " → 整段重点色（2026-10-16 浥之命名）
            body = p[2:] if (is_panel or is_key) else p
            body = pangu(body)  # 盘古之白
            body = smart_quotes(body)  # 智能引号（仅渲染层）
            # 引导句：段内第一句以冒号结束（≤60 字，句内可有逗号）→ 加下划线
            m = re.match(r"^([^：]{1,60})：(.*)$", body)
            lead, rest = (m.group(1), m.group(2)) if (m and not is_panel) else ("", body)

            def hl(s):
                return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>",
                              esc(s).replace("\\n", "<br>"))

            def tail_red(s: str) -> str:
                """末段最后一句染橘红试验（2026-10-16）：按句终符切分，最后一句包 span.final。"""
                parts = [p for p in re.split(r"(?<=[。！？])", s) if p]
                if len(parts) > 1:
                    return (hl("".join(parts[:-1]))
                            + f'<span class="final">{hl(parts[-1])}</span>')
                return hl(s)

            if lead and rest.strip():
                if last:
                    # 全篇末段：收尾性质，引导句不加下划线（浥之定稿）
                    head = (f'<span class="dropcap">{esc(lead[0])}</span>{esc(lead[1:])}：'
                            if first else f'{esc(lead)}：')
                elif first:
                    head = f'<span class="leadin"><span class="dropcap">{esc(lead[0])}</span>{esc(lead[1:])}：</span>'
                else:
                    head = f'<span class="leadin">{esc(lead)}：</span>'
                inner = head + (tail_red(rest) if (last and not first) else hl(rest))
            elif lead:  # 纯引导词 → kicker 导入行
                if first:
                    inner = (f'<span class="kicker"><span class="dropcap">{esc(lead[0])}</span>'
                             f'{esc(lead[1:])}：</span>')
                else:
                    inner = f'<span class="kicker">{esc(lead)}：</span>'
                pg_html.append(
                    f'<p class="kick" style="margin-bottom:0.95em">{inner}</p>')
                continue
            else:
                if last and not first:
                    inner = tail_red(body)
                elif first:
                    inner = f'<span class="dropcap">{esc(body[0])}</span>{hl(body[1:])}'
                else:
                    inner = hl(body)
            if is_panel:
                pg_html.append(f'<div class="panel"><p>{inner}</p></div>')
            elif is_key:
                pg_html.append(f'<p class="keyp">{inner}</p>')
            else:
                pg_html.append(f"<p>{inner}</p>")
        # 标题只在第一页出现
        card_pg = dict(card)
        if i > 1:
            card_pg["title"] = ""
        html = render_page(card_pg, pg_html, fs, lh, i, total,
                           t, extra, pg_media, pg_minfo)
        outs.append(html)
    return outs


def shot(html_path: str, png_path: str) -> bool:
    os.makedirs(os.path.dirname(os.path.abspath(png_path)), exist_ok=True)
    cmd = [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
           "--disable-dev-shm-usage", "--hide-scrollbars",
           "--force-device-scale-factor=2", f"--window-size={CARD_W},{CARD_H}",
           f"--screenshot={png_path}", f"file://{os.path.abspath(html_path)}"]
    for attempt in (1, 2):  # Chrome 偶发挂起，超时重试一次
        try:
            subprocess.run(cmd, capture_output=True, timeout=90)
        except subprocess.TimeoutExpired:
            if attempt == 1:
                print(f"RETRY（截图超时）: {png_path}")
                continue
        if os.path.exists(png_path):
            return True
    return False


def shot_batch(jobs):
    """jobs: [(html, png)]。实测 Chrome 连续 6+ 次会被 SIGTERM，按 5 张一批、批间停 2s。"""
    results = []
    for i in range(0, len(jobs), 5):
        if i > 0:
            time.sleep(2)
        for h, p in jobs[i:i + 5]:
            ok = shot(h, p)
            results.append((p, ok))
            print(("OK  " if ok else "FAIL") + " " + p)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text")
    ap.add_argument("--text-file")
    ap.add_argument("--title", default="")
    ap.add_argument("--tag", default="", help="胶囊标签；默认空=不显示")
    ap.add_argument("--src", default="")
    ap.add_argument("--brand", default="", help="页脚右侧品牌脚注（如 Yizhi的AI Notes）")
    ap.add_argument("--email", default="", help="顶部行右侧邮箱脚注（如 yizhizhang@agent.qq.com）")
    ap.add_argument("--date", default="", help="日期（如 2026年10月16日；mark 式转大字水印，small 式进页脚）")
    ap.add_argument("--date-style", default="mark", choices=["mark", "small"],
                    help="日期形态：mark = 右下大字 Didot 水印（默认）；small = 页脚右下小日期（旧版）")
    ap.add_argument("--serif", action="store_true", help="正文/标题换宋体（出版感 A/B）")
    ap.add_argument("--misans", action="store_true", help="MiSans 几何中文字体（科技/商业感，需联网拉子集）")
    ap.add_argument("--note", default="")
    ap.add_argument("--theme", default="azure", help="默认 azure（浥之钦定默认方案）；--theme-all 出全部 12 套")
    ap.add_argument("--theme-all", action="store_true", help="六套配色各出一张")
    ap.add_argument("--image", default="", help="配图路径（base64 内嵌）")
    ap.add_argument("--img-pos", default="top", choices=["top", "bottom", "fill"],
                    help="配图位置：top 图上文下 / bottom 文上图下 / fill 整卡背景（仅单页）")
    ap.add_argument("--img-h", type=int, default=400, help="top/bottom 配图高度 240-560，默认 400")
    ap.add_argument("--out", default=None, help="输出基础路径（分页时自动加 _p1/_p2）")
    ap.add_argument("--png", default=None, help="PNG 输出基础路径（给了就截图）")
    ap.add_argument("--outdir", default=None, help="--theme-all 时的输出目录")
    ap.add_argument("--cards", default=None, help="批量 JSON 文件（数组，每项字段同 CLI）")
    args = ap.parse_args()

    groups = []  # (base_html, base_png, card_dict)

    if args.cards:
        with open(args.cards, encoding="utf-8") as f:
            cards_in = json.load(f)
        for i, c in enumerate(cards_in, 1):
            if c.get("text_file"):  # 支持从文件读正文（与 --text-file 等价）
                with open(os.path.expanduser(c["text_file"]), encoding="utf-8") as tf:
                    c = dict(c, text=tf.read())
            base = (c.get("out") or f"card_{i:02d}")
            groups.append((base, c.get("png"), c))
    else:
        text = args.text
        if args.text_file:
            with open(args.text_file, encoding="utf-8") as f:
                text = f.read()
        if not text:
            ap.error("需要 --text 或 --text-file 或 --cards")
        card = {"text": text, "title": args.title, "tag": args.tag,
                "src": args.src, "note": args.note, "brand": args.brand,
                "email": args.email, "date": args.date, "date_style": args.date_style,
                "serif": args.serif,
                "misans": args.misans,
                "image": args.image, "img_pos": args.img_pos, "img_h": args.img_h}
        if args.theme_all:
            outdir = args.outdir or "preview"
            os.makedirs(outdir, exist_ok=True)
            for key in THEMES:
                c = dict(card, theme=key)
                groups.append((os.path.join(outdir, f"card_{key}"),
                               os.path.join(outdir, f"card_{key}.png"), c))
        else:
            base = (args.out or "card")
            if base.endswith(".html"):
                base = base[:-5]
            c = dict(card, theme=args.theme)
            groups.append((base, args.png, c))

    # 生成 HTML（每卡可能分页多张）
    shot_jobs = []
    for base_html, base_png, c in groups:
        htmls = render(c)
        png_base = base_png
        if png_base and png_base.endswith(".png"):
            png_base = png_base[:-4]
        multi = len(htmls) > 1
        for i, h in enumerate(htmls, 1):
            hp = f"{base_html}_p{i}" if multi else base_html
            hp += ".html"
            with open(hp, "w", encoding="utf-8") as f:
                f.write(h)
            print("HTML " + hp)
            if base_png:
                pp = f"{png_base}_p{i}.png" if multi else f"{png_base}.png"
                shot_jobs.append((hp, pp))

    if shot_jobs:
        fails = [p for p, ok in shot_batch(shot_jobs) if not ok]
        if fails:
            sys.exit(1)


if __name__ == "__main__":
    main()
