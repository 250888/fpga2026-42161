from docx import Document

path = r"D:\UserFolders\Desktop\嵌赛FPGA\瞬迹_完整可行技术路线_EGO1开发板版_V1.9.docx"
doc = Document(path)
print(f"paragraphs={len(doc.paragraphs)} tables={len(doc.tables)}")
print("=" * 80)

for i, p in enumerate(doc.paragraphs):
    t = p.text
    style = p.style.name if p.style else ""
    if t.strip() or "Heading" in style:
        print(f"[P{i:03d}|{style}] {t}")

print("=" * 80)
for ti, table in enumerate(doc.tables):
    print(f"\n--- TABLE {ti} ({len(table.rows)}x{len(table.columns)}) ---")
    for ri, row in enumerate(table.rows):
        cells = [c.text.replace("\n", " / ").strip() for c in row.cells]
        print(f"  R{ri}: " + " | ".join(cells))
