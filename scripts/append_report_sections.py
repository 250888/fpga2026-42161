# -*- coding: utf-8 -*-
"""在已插图的报告 docx 末尾（第三部分末）追加两节：

    3.4  优化过程与资源对比
    3.5  大模型协作与技能包

只做「插入」，不改动任何既有段落与图片。
用法：python scripts/append_report_sections.py
"""
import os
import sys

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCX = os.path.join(ROOT, "doc", "瞬迹_作品报告.docx")

TABLE = [
    ["版本", "通道", "LUT", "FF", "BRAM", "DSP", "WNS", "说明"],
    ["4 通道原型", "4", "173", "240", "0", "0", "+4.765",
     "单帧 4 路验证，仅作参照"],
    ["16 通道首版", "16", "2048", "1301", "0", "0", "+0.976",
     "通道扩展 + 四阶段扫描 + 101 拍表决"],
    ["16 通道修复版", "16", "2119", "1564", "0", "0", "+1.408",
     "帧快照 / 按钮同步 / 学习门修复（提交版）"],
]

SEC34_INTRO = (
    "下表给出三个阶段的综合与实现结果。三者器件相同（XC7A35T-1CSG324C）、"
    "时钟约束相同（100 MHz），仅设计内容不同，可直接横向比较。"
)

SEC34_NOTE = (
    "解读：① 通道数由 4 增至 16（4 倍），LUT 由 173 增至 2048（约 11.8 倍），"
    "增幅高于通道倍数，原因是连接矩阵按 N² 存储（16 bit → 256 bit）且扫描状态机与"
    "滤波阵列同步扩展，这属于该架构的固有成本，而非实现冗余。"
    "② 复审修复引入帧矩阵快照与按钮/拨码二级同步器，LUT +3.5%、FF +20%，"
    "属于必要的正确性开销。③ 修复后重新实现的时序裕量由 +0.976 ns 提升至 +1.408 ns，"
    "是布线结果差异所致，新增逻辑集中在低扇出路径，未成为关键路径。"
    "④ 当前 LUT 仅占 XC7A35T 的 10.19%、BRAM 与 DSP 均未使用，仍有扩展余量；"
    "但因矩阵存储随通道数平方增长，扩展到 32 路需重新评估资源与扫描周期。"
)

SEC35_BODY = (
    "本项目全程使用大模型作为协作工具，覆盖四类用法：并行评审（RTL 与 XDC 一致性、"
    "协议与证据、PCB 三路独立审查）、单点深挖（硬件排障、时序分析、协议设计）、"
    "工具化生成（报告与海报按官方模板自动生成、框图绘制、打包脚本）、回归把关"
    "（每次改动后自动跑 pytest / iverilog / lint）。"
    "其中并行评审在项目中期抓到一处阻断级缺陷——帧发送时读取实时矩阵导致 CRC 与负载"
    "不同源，修复方式是发送触发沿锁存快照并补充回归用例。"
    "排障过程中也留下多次模型判断失误的记录（把主控板电源轨阻抗误判为外扩板漏电、"
    "把焊盘连通当成引脚连通等），最终都靠实测数据推翻，这些教训已固化为判据。"
)

SEC35_SKILL = (
    "开发过程中沉淀的可复用经验已提炼为技能包，置于仓库 skill/ 目录，共五项："
    "① FPGA 外扩板通道级排障清单（踩坑清单）；② 黄金帧双向回归（校验脚本）；"
    "③ 比赛报告模板填充（案例模板）；④ 官方 pptx 海报模板生成（案例模板）；"
    "⑤ 中文文件名上位机打包（工具）。每项均写明适用场景、使用方法、失效条件与"
    "已验证效果，且与本题目解耦，换一块板卡或换一个题目仍可使用。"
    "完整的提示词、模型回答与自我纠错轨迹见仓库 report/llm-collaboration-log.md。"
)


def main():
    doc = Document(DOCX)
    anchor = None
    for p in doc.paragraphs:
        if "第四部分" in p.text:
            anchor = p
            break
    if anchor is None:
        print("找不到「第四部分」锚点，放弃")
        sys.exit(1)

    normal = doc.styles["Normal"]
    try:
        h3 = doc.styles["Heading 3"]
    except KeyError:
        h3 = doc.styles["Heading 2"]

    def para(text, style=normal, bold_lead=None):
        p = anchor.insert_paragraph_before("", style=style)
        if bold_lead:
            r = p.add_run(bold_lead)
            r.bold = True
            r.font.size = Pt(10.5)
        r = p.add_run(text)
        r.font.size = Pt(10.5)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.first_line_indent = Inches(0.0)
        return p

    # ---- 3.4 优化过程与资源对比
    anchor.insert_paragraph_before("3.4  优化过程与资源对比", style=h3)
    para(SEC34_INTRO)

    # 表格（先追加到文末，再挪到锚点前）
    tbl = doc.add_table(rows=len(TABLE), cols=len(TABLE[0]))
    try:
        tbl.style = doc.styles["Table Grid"]
    except KeyError:
        pass
    # 关键：关闭自动调整，否则列宽会被渲染器压缩（说明列会变成竖排）
    tbl.autofit = False
    tbl.allow_autofit = False
    widths = [1.00, 0.42, 0.46, 0.46, 0.52, 0.42, 0.66, 2.44]   # 合计 6.38 in ≤ 版心 6.47
    for r, row in enumerate(TABLE):
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(str(val))
            run.font.size = Pt(8.5)
            run.font.bold = (r == 0)
            cell.width = Inches(widths[c])
    for c, w in enumerate(widths):
        tbl.columns[c].width = Inches(w)
    anchor._p.addprevious(tbl._tbl)
    para("")                      # 表后留一个空段
    para(SEC34_NOTE)

    # ---- 3.5 大模型协作与技能包
    anchor.insert_paragraph_before("3.5  大模型协作与技能包", style=h3)
    para(SEC35_BODY)
    para(SEC35_SKILL)

    doc.save(DOCX)
    print("已插入 3.4 / 3.5 两节 ->", DOCX)
    print("当前段落数:", len(doc.paragraphs), " 表格数:", len(doc.tables))


if __name__ == "__main__":
    main()
