"""变式题库自检：结构合法性 + 抽样人工核对。

结构检查项（任一不满足即报错）：
  choice  恰好 4 个互不相同的选项，answer 逐字出现在 options 里，trap 非空
  fill    stem 含 ___，answer 非空，accept 至少含 answer
  所有     id 唯一、kp_id 正确、stem 不重复
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

import variants  # noqa: E402


def check(d: dict, errs: list[str]) -> None:
    if d["type"] == "choice":
        opts = d.get("options") or []
        if len(opts) != 4:
            errs.append(f"选项数 {len(opts)}：{d['stem']}")
        if len({o.strip().lower() for o in opts}) != len(opts):
            errs.append(f"选项重复：{d['stem']} -> {opts}")
        if d["answer"] not in opts:
            errs.append(f"答案不在选项里：{d['stem']} -> {d['answer']}")
        if not d.get("trap"):
            errs.append(f"缺 trap：{d['stem']}")
    elif d["type"] == "fill":
        if "___" not in d["stem"]:
            errs.append(f"填空缺 ___：{d['stem']}")
        if not (d.get("answer") or "").strip():
            errs.append(f"答案为空：{d['stem']}")
        if d["answer"] not in (d.get("accept") or []):
            errs.append(f"accept 未包含 answer：{d['stem']}")
    else:
        errs.append(f"未知题型：{d['type']}")
    if not d.get("explain"):
        errs.append(f"缺 explain：{d['stem']}")


def main() -> int:
    kps = variants.supported()
    errs: list[str] = []
    total = 0
    per_kp: dict[str, int] = {}
    stems: Counter = Counter()

    for kp in kps:
        got = variants.make(kp, 24, seed="selftest")
        per_kp[kp] = len(got)
        if not got:
            errs.append(f"{kp} 一道也生成不出来")
        for d in got:
            total += 1
            check(d, errs)
            stems[d["stem"]] += 1
            if d["kp_id"] != kp:
                errs.append(f"kp_id 错配 {kp} -> {d['kp_id']}")

    dup = [s for s, n in stems.items() if n > 3]
    print(f"覆盖知识点 {len(kps)} 个，生成 {total} 道，去重后 {len(stems)} 个不同题干")
    print(f"每题平均：{total / max(1, len(kps)):.1f} 道")
    thin = sorted((v, k) for k, v in per_kp.items() if v < 12)
    if thin:
        print(f"变式偏少（<12）的知识点 {len(thin)} 个：")
        for n, k in thin[:12]:
            print(f"   {n:3d}  {k}")
    if dup:
        print(f"重复题干超过 3 次的：{len(dup)} 个（示例 {dup[:3]}）")

    if errs:
        print(f"\n发现 {len(errs)} 个结构问题：")
        for e in errs[:40]:
            print("  -", e)
        return 1
    print("结构校验通过：0 问题")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
