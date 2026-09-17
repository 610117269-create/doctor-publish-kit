#!/usr/bin/env python3
"""Render local article JSON into Markdown and inline-styled HTML. No network."""
import argparse
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, quote


def require(ok, message):
    if not ok:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def check_date(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), '日期必须为YYYY-MM-DD')
    date.fromisoformat(value)


def validate(d):
    require(isinstance(d, dict), '根节点必须是对象')
    require(d.get('schema_version') == 1, 'schema_version必须为1')
    for key in ('title', 'summary', 'audience', 'updated'):
        require(nonempty(d.get(key)), f'缺少文本字段：{key}')
    check_date(d['updated'])
    require(d.get('status') in ('draft', 'needs_clinician_review', 'clinician_reviewed'), '无效状态')
    if d['status'] == 'clinician_reviewed':
        review = d.get('review', {})
        require(isinstance(review, dict), 'review必须是对象')
        for key in ('reviewer', 'date', 'version'):
            require(nonempty(review.get(key)), f'已审核状态缺少：{key}')
        check_date(review['date'])
    brand = d.get('brand')
    require(isinstance(brand, dict), '缺少brand')
    require(nonempty(brand.get('name')), '缺少品牌名')
    require(isinstance(brand.get('byline'), str), '署名必须是文本，可为空')
    require(isinstance(brand.get('color'), str) and re.fullmatch(r'#[0-9a-fA-F]{6}', brand['color']), '无效品牌颜色')
    sources = d.get('sources')
    require(isinstance(sources, list) and len(sources) > 0, '缺少来源')
    ids = set()
    for source in sources:
        require(isinstance(source, dict), '来源必须是对象')
        for key in ('id', 'institution', 'title', 'url', 'accessed'):
            require(nonempty(source.get(key)), f'来源缺少：{key}')
        require(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', source['id']), '来源ID仅允许字母数字下划线和连字符')
        require(source['id'] not in ids, '来源ID重复')
        ids.add(source['id'])
        url = urlsplit(source['url'])
        require(url.scheme in ('https', 'http') and bool(url.netloc) and not any(c.isspace() for c in source['url']), '来源URL必须是HTTP/HTTPS地址')
        check_date(source['accessed'])
    sections = d.get('sections')
    require(isinstance(sections, list) and len(sections) > 0, '缺少正文')
    for section in sections:
        require(isinstance(section, dict) and nonempty(section.get('heading')), '缺少章节标题')
        paragraphs = section.get('paragraphs')
        require(isinstance(paragraphs, list) and len(paragraphs) > 0, '空章节')
        for p in paragraphs:
            require(isinstance(p, dict) and nonempty(p.get('text')), '缺少段落文本')
            refs = p.get('source_ids')
            require(isinstance(refs, list) and all(isinstance(r, str) for r in refs), 'source_ids必须是字符串数组')
            require(all(r in ids for r in refs), '正文引用不存在的来源ID')
    return d


def markdown_text(value):
    # Treat user content as plain text even when a Markdown viewer allows HTML.
    value = html.escape(value, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>-])", r"\\\1", value).replace("\n", " ")


def markdown_url(value):
    return quote(value, safe=":/?=&%#@+;,_~-")


def render(d):
    esc = html.escape
    mt = markdown_text
    color = d['brand']['color']
    status = {'draft': '初稿', 'needs_clinician_review': '待医生审核', 'clinician_reviewed': '已登记医生审核'}[d['status']]
    meta = f"{d['brand']['name']} · {d['updated']} · {status}"
    md = [f"# {mt(d['title'])}", mt(meta), mt(d['summary']), f"适用读者：{mt(d['audience'])}"]
    chunks = [f'<p style="font-size:12px;color:#68716e">{esc(meta)}</p>', f'<h1 style="font-size:28px;line-height:1.4;color:#172b28">{esc(d["title"])}</h1>', f'<p style="padding:16px;background:#eef6f3;border-left:4px solid {color}">{esc(d["summary"])}</p>', f'<p style="font-size:13px;color:#68716e">适用读者：{esc(d["audience"])}</p>']
    source_map = {s['id']: s for s in d['sources']}
    for section in d['sections']:
        md.append(f"## {mt(section['heading'])}")
        chunks.append(f'<h2 style="margin-top:30px;font-size:21px;color:{color}">{esc(section["heading"])}</h2>')
        for p in section['paragraphs']:
            refs = ' '.join(f'[{r}]({markdown_url(source_map[r]["url"])})' for r in p['source_ids'])
            md.append(mt(p['text']) + (' ' + refs if refs else ''))
            links = ' '.join(f'<a style="color:{color}" href="{esc(source_map[r]["url"], quote=True)}">[{esc(r)}]</a>' for r in p['source_ids'])
            chunks.append(f'<p style="margin:18px 0;line-height:1.9">{esc(p["text"])} <span style="font-size:12px">{links}</span></p>')
    md.append('## 来源')
    chunks.append('<h2 style="font-size:18px;margin-top:32px">来源</h2>')
    for s in d['sources']:
        text = f'{s["id"]} · {s["institution"]} · {s["title"]} · 查阅：{s["accessed"]}'
        md.append(f'[{mt(text)}]({markdown_url(s["url"])})')
        chunks.append(f'<p style="font-size:12px;line-height:1.7;overflow-wrap:anywhere"><a style="color:{color}" href="{esc(s["url"], quote=True)}">{esc(text)}</a></p>')
    footer = '本文用于一般健康科普，不能替代针对个人的诊疗。专业审核状态见页首。'
    if d['status'] == 'clinician_reviewed':
        r = d['review']
        record = f'审核记录：{r["reviewer"]} / {r["date"]} / {r["version"]}'
        md.append(mt(record))
        chunks.append(f'<p style="font-size:12px">{esc(record)}</p>')
    md.extend([mt(d['brand']['byline']), mt(footer)])
    chunks.append(f'<p style="margin-top:30px;font-size:12px;color:#68716e">{esc(d["brand"]["byline"])}<br>{esc(footer)}</p>')
    body = '\n'.join(chunks)
    page = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(d['title'])}</title></head>
<body style="margin:0;background:#f4f5f2;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;color:#243a35"><main style="max-width:680px;margin:24px auto;padding:28px 22px;background:white;box-sizing:border-box;overflow-wrap:anywhere">{body}</main></body></html>
'''
    return '\n\n'.join(x for x in md if x) + '\n', page


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('article', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--overwrite', action='store_true', help='允许覆盖已有排版输出；不覆盖JSON输入')
    args = parser.parse_args()
    try:
        d = validate(json.loads(args.article.read_text(encoding='utf-8')))
        md, page = render(d)
        targets = [args.out / 'article.md', args.out / 'wechat.html']
        require(args.article.resolve() not in [p.resolve() for p in targets], '输出不能覆盖输入')
        require(args.overwrite or not any(p.exists() for p in targets), '输出文件已存在；请换目录或明确使用--overwrite')
        args.out.mkdir(parents=True, exist_ok=True)
        targets[0].write_text(md, encoding='utf-8')
        targets[1].write_text(page, encoding='utf-8')
    except (ValueError, OSError, TypeError, KeyError) as exc:
        parser.exit(2, f'未生成：{exc}\n')
    print('已生成article.md和wechat.html；仅完成结构/引用ID检查，医学结论与微信效果需另行确认。')


if __name__ == '__main__':
    main()
