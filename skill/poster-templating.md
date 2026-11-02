# Skill 4 — 从官方 pptx 模板生成中英双语海报

## 适用场景

主办方给了 `.pptx` 海报模板（含品牌标识、色块标题条、装饰元素），
要求提交「中英文各一页」的 PPTx。

不适用：模板是纯图片、无可编辑图元的场合。

## 关键判断：改模板，还是重建版面

**先试原位改字，但要做好放弃的准备。**

原位改字的典型翻车点（本项目实测）：

| 现象 | 原因 |
|---|---|
| 标题残留黄色高亮 | 模板的提示文字带 `highlight`，换文字不清高亮 |
| 正文替换不生效 | 按坐标/名字匹配形状，模板里有多个同名同尺寸文本框 |
| 图注溢出 | 原文短、译文长，固定宽度文本框装不下 |
| 竖排装饰字母错位 | 模板用特殊字体（如 Aharoni）逐字母堆叠，缺字体就乱 |

**若上述问题超过两处，直接重建版面**：用基本图元（矩形 + 文本框 + 连接线 + 图片）
复制模板的视觉语言（深色标题条、细分隔线、三栏网格），比逐个形状调更可控。

## 使用方法

### 1. 提取模板里的可用资产

模板的品牌标识常常藏在 **slideMaster / slideLayout** 里，不在 slide 上，
所以按 slide 的形状遍历找不到它。直接解压 pptx 看 `ppt/media/`：

```python
import zipfile
z = zipfile.ZipFile("template.pptx")
for n in z.namelist():
    if n.startswith("ppt/media/"):
        print(n, z.getinfo(n).file_size)
```

- 位图/矢量标识：直接 `add_picture` 复用
- EMF/WMF：python-pptx 能插入，但某些渲染器（LibreOffice）会渲染异常 → 优先找 PNG 版本

### 2. 中英双语两页，各自从头 build

**不要复制幻灯片**。python-pptx 复制含图片的页需要连 rels 一起复制，
而 `_Relationships.add_relationship` 在 1.0.x 里不存在，复制出来的页图片全丢。

正确做法：写一个 `build_slide(prs, data)`，中英文各传一份数据字典：

```python
build_slide(prs, CN)
build_slide(prs, EN)
```

### 3. 版面自检：**用 PDF 量，不要信 PNG 预览**

某些渲染器对自定义 16:9 尺寸的 PNG 预览会**等比放大**，看起来像版面溢出。
用 `convert` 出 PDF 再量版心才准：

```python
import pymupdf
d = pymupdf.open("poster.pdf")
print(d[0].rect)                       # 应为 960x540 pt（13.333x7.5 in）
blocks = d[0].get_text("blocks")
print(max(b[2] for b in blocks))       # 最右文字，应 < 页宽
```

### 4. 队伍信息放哪里（容易搞错）

比赛常有两套要求，**适用对象不同**：

| 用途 | 是否含队伍信息 |
|---|---|
| 上传到评审系统的海报 | 通常**可以**含校名/校标/队员 |
| 决赛现场打印的 A4 海报 | 通常**不得**含队伍信息 |

务必分别核对，做两个版本。

## 失效条件

- 模板含**动画 / SmartArt** → 重建会丢失，需人工在 PowerPoint 里补
- 主办方要求「必须使用模板文件的原始形状」→ 只能原位改，接受上述翻车点
- 需要**CMYK 印刷** → PPTX 是 RGB，最终印刷需另转

## 已验证效果

本项目用「重建版面」法生成中英各一页海报（13.333×7.5 in），
含官方 AMD 标识（从模板母版 `ppt/media/image1.png` 提取）、校标、三栏内容与实测数据表，
结构检查通过、PDF 实测版心 960×540 pt 无溢出。

## 提炼来源

`scripts/make_poster.py`（本仓库），以及本项目第一次「原位改模板」失败的全过程。
