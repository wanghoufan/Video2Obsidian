#!/usr/bin/env python3
"""builder 自验：para-v2.6 分段收紧 + 三域预置词库一键导入。

只用外置 tmp + 合成数据；不碰用户真实目录与 OB 库。stdlib-only。
运行：python3 tests/selftest_v26_presets.py
全过 EXIT=0；任一断言失败 EXIT=1（坏例只看 exit 码，不看打印）。
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

FAILS = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


def load_server():
    spec = importlib.util.spec_from_file_location(
        "v2o_server", os.path.join(ROOT, "app", "server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def part1_formatter():
    from stage9 import formatter_v2 as fv

    check("version==para-v2.6", fv.FORMATTER_VERSION == "para-v2.6")
    p = fv.PARA_PARAMS_V2
    check("target=80", p["target_chars"] == 80)
    check("hard_max=120", p["hard_max_chars"] == 120)
    check("min_floor=30", p["min_paragraph_chars"] == 30)

    # 验收：450 字无标点合成段 -> 全部分段 <=120 且段数增加
    paras = fv.render_with_v2(
        [{"id": "s1", "text": "甲" * 450, "start": 0.0, "end": 30.0}])
    check("450字无标点: max<=120", max(len(x) for x in paras) <= 120)
    check("450字无标点: 段数增加(>1)", len(paras) > 1)
    check("450字无标点: 无空段", all(x for x in paras))
    check("450字无标点: 字面未改写",
          "".join(paras) == "甲" * 450)

    # 单源头：引擎包装 _engine_params 与生产后处理均读 PARA_PARAMS_V2
    ep = fv._engine_params()
    check("engine_params==PARA_PARAMS_V2(3键)",
          ep["target_chars"] == p["target_chars"]
          and ep["hard_max_chars"] == p["hard_max_chars"]
          and ep["pause_threshold_s"] == p["pause_threshold_s"])
    pp = fv.postprocess_paragraphs(["乙" * 300])
    check("postprocess cap<=120", max(len(x) for x in pp) <= 120)
    check("postprocess 决定论(同入同出)",
          pp == fv.postprocess_paragraphs(["乙" * 300]))

    # render profile revision bump（#30 五字段哈希随版本+参数变）
    prof = fv.new_render_profile()
    check("profile version bump",
          prof["paragraph_formatter_version"] == "para-v2.6")
    check("profile params==常量",
          prof["paragraph_parameters"] == dict(p))

    probes = fv.check_rule_order()
    check("check_rule_order.all_pass", probes["all_pass"] is True)

    short = fv.render_with_v2(
        [{"id": "m%d" % i, "text": "ab",
          "start": float(i * 10), "end": float(i * 10 + 1)}
         for i in range(3)])
    check("防碎下限30: 碎段并回一段", len(short) == 1)


def read_presets():
    preset_dir = os.path.join(ROOT, "app", "presets", "vocab")
    out = {}
    for name in sorted(os.listdir(preset_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(preset_dir, name), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        out[data["domain"]] = data
    return out


def part2_presets_files():
    presets = read_presets()
    for domain in ("finance", "programming", "crypto"):
        check("预置域存在:" + domain, domain in presets)
        if domain not in presets:
            continue
        entries = presets[domain]["entries"]
        check("域条目>=50:" + domain, len(entries) >= 50)
        check("错词>=2字:" + domain, all(len(e["wrong"]) >= 2 for e in entries))
        check("错词!=正词:" + domain,
              all(e["wrong"] != e["right"] for e in entries))
        check("同域错词去重:" + domain,
              len({e["wrong"] for e in entries}) == len(entries))
        check("含来源注明:" + domain,
              isinstance(presets[domain].get("source"), str)
              and len(presets[domain]["source"]) > 0)


def part2_extensible(server):
    tmp = tempfile.mkdtemp(prefix="v26p_")
    old = server.VOCAB_PRESET_DIR
    try:
        with open(os.path.join(tmp, "vocab-extra.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"domain": "extra", "label": "扩展",
                       "entries": [{"wrong": "测式", "right": "测试"}]},
                      fh, ensure_ascii=False)
        server.VOCAB_PRESET_DIR = tmp
        got = server._load_vocab_presets()
        check("可扩展:新增json即新增域",
              len(got) == 1 and got[0]["domain"] == "extra")
        check("坏文件不炸:跳过非json",
              server._read_vocab_preset(os.path.join(tmp, "nope.json")) is None)
    finally:
        server.VOCAB_PRESET_DIR = old
        shutil.rmtree(tmp, ignore_errors=True)


def part2_import(server, presets):
    data_root = tempfile.mkdtemp(prefix="v26d_")
    try:
        body = json.dumps({"data_root": data_root,
                           "domains": ["finance", "programming",
                                       "crypto"]}).encode("utf-8")
        code, res = server._handle_vocab_presets_import(body)
        uniq = len({e["wrong"] for d in ("finance", "programming", "crypto")
                    for e in presets[d]["entries"]})
        check("导入 HTTP200+ok", code == 200 and bool(res.get("ok")))
        check("导入条数==三域去重合计", res["added"] == uniq)
        check("真实预置零撞基表", res.get("rejected_base_count") == 0)
        check("revision bump 为用户哈希",
              str(res["revision"]).startswith("s9-corr-v2-user-"))
        check("vocab-user.json 落盘",
              os.path.isfile(os.path.join(data_root, "vocab-user.json")))

        code2, res2 = server._handle_vocab_presets_import(body)
        check("二次导入幂等 added==0", code2 == 200 and res2["added"] == 0)
        check("二次导入全跳过", res2["skipped_duplicate"] == uniq)
        check("二次导入 revision 不变", res2["revision"] == res["revision"])

        prof = server._norm_profile_for_new_jobs(data_root)
        check("新转写 profile 用用户 revision",
              prof["correction_rules_revision"] == res["revision"])

        from stage3 import normalize as nm
        out = nm.apply_corrections(
            [{"id": "t1", "text": "市盈绿偏高，美联署加息，区块连很热"}],
            res["revision"])
        txt = out["segments"][0]["text"]
        check("新转写自动替换(金融)",
              "市盈率" in txt and "美联储" in txt)
        check("新转写自动替换(币圈)", "区块链" in txt)

        # 坏例：空 domains -> 400
        c4, _ = server._handle_vocab_presets_import(
            json.dumps({"data_root": data_root, "domains": []}).encode())
        check("坏例:空domains->400", c4 == 400)
    finally:
        shutil.rmtree(data_root, ignore_errors=True)


def part2_base_reject(server):
    # 撞基表拒收 + 非法(错词<2字)在读取层被过滤：独立 data_root，互不污染
    tmp_preset = tempfile.mkdtemp(prefix="v26bp_")
    data_root = tempfile.mkdtemp(prefix="v26bd_")
    old = server.VOCAB_PRESET_DIR
    try:
        with open(os.path.join(tmp_preset, "vocab-basetest.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"domain": "basetest", "label": "撞基表",
                       "entries": [{"wrong": "Github", "right": "GitHubX"},
                                   {"wrong": "a", "right": "bb"},
                                   {"wrong": "合法错词", "right": "合法正词"}]},
                      fh, ensure_ascii=False)
        server.VOCAB_PRESET_DIR = tmp_preset
        code, res = server._handle_vocab_presets_import(
            json.dumps({"data_root": data_root,
                        "domains": ["basetest"]}).encode("utf-8"))
        check("撞基表拒收:回报Github",
              code == 200 and "Github" in (res.get("rejected_base") or []))
        check("撞基表拒收:不落入词库",
              all(e["wrong"] != "Github" for e in res.get("vocab") or []))
        check("错词<2字:读取层丢弃", res["added"] == 1)
        check("未知领域:全未知->400",
              server._handle_vocab_presets_import(
                  json.dumps({"data_root": data_root,
                              "domains": ["nope"]}).encode())[0] == 400)
    finally:
        server.VOCAB_PRESET_DIR = old
        shutil.rmtree(tmp_preset, ignore_errors=True)
        shutil.rmtree(data_root, ignore_errors=True)


def main():
    part1_formatter()
    presets = read_presets()
    part2_presets_files()
    server = load_server()
    part2_extensible(server)
    part2_import(server, presets)
    part2_base_reject(server)
    if FAILS:
        print("\nSELFTEST FAIL %d: %s" % (len(FAILS), FAILS))
        return 1
    print("\nSELFTEST ALL PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
