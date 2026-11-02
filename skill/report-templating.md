# Skill 3 — 用脚本填充比赛报告模板（而不是手写）

## 适用场景

主办方给了 `.docx` 模板，正文是「800 字内」「400 字内（可加重要图）」这类**提示文字**，
需要把提示逐条替换成实际内容，同时保留模板的样式、页眉、页脚、编号。

不适用：模板要求严格手工排版、或内容需要大量图文混排微调的场合。

## 使用方法

### 1. 先 dump 模板结构，不要直接改

```python
from docx import Document
d = Document(TPL)
for i, p in enumerate(d.paragraphs):
    if p.text.strip():
        print(i, p.style.name, p.text[:60])
```

看清「提示段落」的**原文与顺序**——它们就是你后面的锚点。

### 2. 用「锚点 + 插入」而不是「重建文档」

```python
def insert_paragraph_after(paragraph, text, style):
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    para = Paragraph(new_p, paragraph._parent)
    para.style = style
    if text: para.add_run(text)
    return para
```

插完**删除锚点段**。这样模板的章节标题、页眉页脚、分节全部保留。

### 3. 三个必须踩过的坑

| 坑 | 现象 | 解法 |
|---|---|---|
| **不挂样式会掉字号** | 新段落继承 `docDefaults`，字号比 Normal 大，正文宽度超出页面被截断 | 每段显式 `para.style = doc.styles["Normal"]` |
| **相同提示文字会串位** | 模板里三处都写「400 字内」，按文字匹配全撞第一个 | 相同文字改用**出现顺序计数器**，其余用唯一前缀 |
| **LibreOffice 渲染截断 ≠ 文档坏** | 转 PDF 后正文右侧被切掉 | 先用**原模板**渲染对照——若原模板同样截断，那是字体替换假象，Word 里正常 |

### 4. 图片与表格

- 图片：`run.add_picture(path, width=Inches(6.2))`，段落设居中
- 表格：查表头行数/列数后设列宽，交替行加浅底色，比纯黑白表格易读

### 5. 出稿后必做

- 结构检查：段落数、表格数、关键文本是否命中
- 无队伍信息检查（多数比赛要求提交的 PDF 里不能出现校名/队名/队员）

## 失效条件

- 模板里有**内容控件 / SmartArt / 复杂域** → python-docx 会丢失，必须手工处理
- 模板用**分节符**控制不同页的页眉 → 插入段落不会破坏，但插**表格**可能跨节，要检查
- 需要**精确页码控制** → python-docx 不分页，只能生成后人工检查

## 已验证效果

本项目从官方模板生成 16 页设计报告，含 2 张自动填充的表格
（性能指标表、九项特性实测表）与 8 张配图，报告要求字数全部符合。

## 提炼来源

`scripts/make_report.py`（本仓库）。踩坑记录见本文件第 3 节三行表格。

## 配套文件

- 脚本：`scripts/make_report.py`
- 配图生成：`scripts/make_diagrams.py`
- 图片嵌入：`scripts/embed_figures.py`
