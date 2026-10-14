#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把中文 Markdown 转 PDF（用 reportlab + 内置 CJK 字体）"""
import re
import sys
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
)
from reportlab.lib import colors

# 注册中文字体
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

MD_PATH = Path(r"C:/Users/lwr/Music/各种简历/个人简历/LinWangRu.github.io/restart/重启_双战斗体系_系统策划案_v1.4.md")
PDF_PATH = Path(r"C:/Users/lwr/Music/各种简历/个人简历/LinWangRu.github.io/restart/重启_双战斗体系_系统策划案_v1.4.pdf")

# 中文样式
styles = getSampleStyleSheet()
style_h1 = ParagraphStyle(
    'cn_h1', parent=styles['Heading1'],
    fontName='STSong-Light', fontSize=20, leading=28,
    spaceBefore=20, spaceAfter=14, alignment=TA_LEFT,
)
style_h2 = ParagraphStyle(
    'cn_h2', parent=styles['Heading2'],
    fontName='STSong-Light', fontSize=15, leading=22,
    spaceBefore=14, spaceAfter=8, alignment=TA_LEFT,
)
style_h3 = ParagraphStyle(
    'cn_h3', parent=styles['Heading3'],
    fontName='STSong-Light', fontSize=12, leading=18,
    spaceBefore=10, spaceAfter=6, alignment=TA_LEFT,
)
style_body = ParagraphStyle(
    'cn_body', parent=styles['Normal'],
    fontName='STSong-Light', fontSize=9.5, leading=14,
    spaceAfter=4, alignment=TA_LEFT,
)
style_bullet = ParagraphStyle(
    'cn_bullet', parent=style_body,
    leftIndent=14, bulletIndent=4, spaceAfter=2,
)
style_quote = ParagraphStyle(
    'cn_quote', parent=style_body,
    leftIndent=18, rightIndent=14,
    textColor=colors.HexColor('#444'),
    backColor=colors.HexColor('#F5F5F5'),
    borderPadding=6, spaceBefore=6, spaceAfter=6,
)
style_code = ParagraphStyle(
    'cn_code', parent=style_body,
    fontName='STSong-Light',
    backColor=colors.HexColor('#F0F0F0'),
    leftIndent=10, rightIndent=10,
    borderPadding=4, spaceBefore=4, spaceAfter=4,
    textColor=colors.HexColor('#333'),
)
style_caption = ParagraphStyle(
    'cn_caption', parent=style_body,
    fontSize=8, textColor=colors.grey, alignment=TA_CENTER,
)

def esc(s: str) -> str:
    """转义 reportlab Paragraph XML 特殊字符"""
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return s

def inline_md(s: str) -> str:
    """处理粗体 / 代码 / 链接（轻量级）"""
    s = esc(s)
    # 行内代码 `...` —— 保留中文字体（Courier 渲染不了中文），仅加底色和等宽视觉
    s = re.sub(r'`([^`]+)`',
               r'<font backColor="#F0F0F0">\1</font>', s)
    # 粗体 **...**
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    # 斜体 *...*（粗体优先，避免重复匹配）
    s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', s)
    # 链接 [text](url) → text
    s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
    return s

def md_to_paragraphs(md_text: str):
    """将 Markdown 文本转为 reportlab flowables。"""
    flow = []
    lines = md_text.split('\n')
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue
        # 水平分割线 ---
        if line.strip() == '---':
            flow.append(Spacer(1, 8))
            i += 1
            continue
        # 围栏代码块 ``` ... ```
        if line.lstrip().startswith('```'):
            j = i + 1
            code_lines = []
            while j < n and not lines[j].lstrip().startswith('```'):
                code_lines.append(lines[j])
                j += 1
            code_text = '\n'.join(code_lines)
            for cl in code_text.split('\n'):
                flow.append(Paragraph(esc(cl).replace('\n', '<br/>'), style_code))
            flow.append(Spacer(1, 6))
            i = j + 1
            continue
        # 标题 # / ## / ###
        if line.startswith('### '):
            flow.append(Paragraph(inline_md(line[4:]), style_h3))
            i += 1
            continue
        if line.startswith('## '):
            flow.append(Paragraph(inline_md(line[3:]), style_h2))
            i += 1
            continue
        if line.startswith('# '):
            flow.append(Paragraph(inline_md(line[2:]), style_h1))
            i += 1
            continue
        # 引用 > ...
        if line.startswith('> '):
            quote_text = line[2:]
            j = i + 1
            while j < n and lines[j].startswith('> '):
                quote_text += '<br/>' + lines[j][2:]
                j += 1
            flow.append(Paragraph(inline_md(quote_text), style_quote))
            i = j
            continue
        # 表格：表头 + 分隔行 + 数据行
        if '|' in line and i + 1 < n and re.match(r'^\|?[\s\-:|]+\|?$', lines[i+1]):
            tbl_lines = []
            j = i
            while j < n and '|' in lines[j] and lines[j].strip():
                tbl_lines.append(lines[j])
                j += 1
            if len(tbl_lines) >= 2:
                # 第一行是表头，第二行是分隔，后面是数据
                def split_row(row):
                    s = row.strip()
                    if s.startswith('|'): s = s[1:]
                    if s.endswith('|'): s = s[:-1]
                    return [c.strip() for c in s.split('|')]
                header = split_row(tbl_lines[0])
                data = [split_row(r) for r in tbl_lines[2:]]
                # Paragraph 化每个 cell
                header_p = [Paragraph(inline_md(c), style_body) for c in header]
                data_p = [[Paragraph(inline_md(c), style_body) for c in row] for row in data]
                tbl = Table([header_p] + data_p, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ('FONTNAME', (0,0), (-1,-1), 'STSong-Light'),
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E8E8E8')),
                    ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#999')),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('LEFTPADDING', (0,0), (-1,-1), 4),
                    ('RIGHTPADDING', (0,0), (-1,-1), 4),
                    ('TOPPADDING', (0,0), (-1,-1), 3),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ]))
                flow.append(tbl)
                flow.append(Spacer(1, 8))
                i = j
                continue
        # 数字列表 1. 2. 3. ...
        if re.match(r'^\s*\d+[.)]\s+', line):
            item_text = re.sub(r'^\s*\d+[.)]\s+', '', line)
            flow.append(Paragraph(inline_md(item_text), style_bullet))
            i += 1
            continue
        # 列表 - ... 或 * ...
        if re.match(r'^\s*[-*]\s+', line):
            bullet_text = re.sub(r'^\s*[-*]\s+', '', line)
            flow.append(Paragraph('• ' + inline_md(bullet_text), style_bullet))
            i += 1
            continue
        # 普通段落：合并连续行
        para = [line]
        j = i + 1
        while j < n and lines[j].strip() and not (
            lines[j].startswith('#') or lines[j].startswith('>') or
            lines[j].startswith('-') or lines[j].startswith('*') or
            '|' in lines[j]
        ):
            para.append(lines[j].strip())
            j += 1
        flow.append(Paragraph(inline_md('<br/>'.join(para)), style_body))
        i = j
    return flow

def main():
    md_text = MD_PATH.read_text(encoding='utf-8')
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm,
        title='重启 双战斗体系系统策划案 v1.4',
        author='林王儒',
    )
    flow = md_to_paragraphs(md_text)
    doc.build(flow)
    print(f"OK: {PDF_PATH}")

if __name__ == '__main__':
    main()