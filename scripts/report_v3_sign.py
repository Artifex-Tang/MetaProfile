# -*- coding: utf-8 -*-
"""
编辑《系统测试报告_0616v3.docx》的测试记录表：
  1) 每个测试记录表（含 执行时间 + 结论 行）在「结论」行之前插入一行「执行人」（右格留空，供手签）。
  2) 「执行时间」单元格的时间减 16 小时。范围 scope = first（仅第 1 个记录表）/ all（全部记录表）。
就地保存。
用法：python report_v3_sign.py <first|all>
"""
from __future__ import annotations
import copy, sys
from datetime import datetime, timedelta
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

PATH = "系统测试报告_0616v3.docx"


def set_cell_text(tc, txt: str) -> None:
    """保留 tc 段落与单元格属性，仅替换正文 run。"""
    paras = tc.findall(qn("w:p"))
    for p in paras[1:]:
        tc.remove(p)
    p0 = paras[0]
    for r in p0.findall(qn("w:r")):
        p0.remove(r)
    if txt:
        r = OxmlElement("w:r")
        t = OxmlElement("w:t"); t.text = txt; t.set(qn("xml:space"), "preserve")
        r.append(t); p0.append(r)


def shift_time(tc, hours: int) -> str | None:
    """对执行时间单元格解析时间、减 hours，原格式回写。返回新串或 None。"""
    txt = "".join((e.text or "") for e in tc.iter(qn("w:t"))).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(txt, fmt)
        except ValueError:
            continue
        dt2 = dt - timedelta(hours=hours)
        new = dt2.strftime(fmt)
        set_cell_text(tc, new)
        return new
    return None


def main() -> int:
    scope = sys.argv[1] if len(sys.argv) > 1 else "first"
    doc = Document(PATH)

    record_tables = []
    for t in doc.tables:
        firsts = [r.cells[0].text.strip() for r in t.rows]
        if "执行时间" in firsts and "结论" in firsts:
            record_tables.append(t)

    n_sign = 0
    n_time = 0
    for idx, t in enumerate(record_tables):
        rows = t.rows
        # 1) 执行人 行：插在 结论 行之前（深拷贝结论行以继承边框/底纹）
        concl_tr = None
        for r in rows:
            if r.cells[0].text.strip() == "结论":
                concl_tr = r._tr; break
        if concl_tr is not None:
            new_tr = copy.deepcopy(concl_tr)
            tcs = new_tr.findall(qn("w:tc"))
            if len(tcs) >= 2:
                set_cell_text(tcs[0], "执行人")
                set_cell_text(tcs[1], "")
            concl_tr.addprevious(new_tr)
            n_sign += 1
        # 2) 执行时间 减 16h
        do_time = (scope == "all") or (scope == "first" and idx == 0)
        if do_time:
            for r in t.rows:
                if r.cells[0].text.strip() == "执行时间":
                    new = shift_time(r.cells[1]._tc, 16)
                    if new:
                        n_time += 1
                    break

    doc.save(PATH)
    print(f"scope={scope}: 执行人 rows inserted={n_sign}, 执行时间 shifted={n_time}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
