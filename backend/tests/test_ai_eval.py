"""Domain-skill evaluation against the LOCAL model (opt-in: AVIRA_LIVE_LLM_TESTS=1).

Each case in eval/cases.jsonl provides grounded context + a user turn and
asserts on the answer: required strings, forbidden strings/regexes, and
"any of" groups. This measures the prompts + local model behaviour on the
things that matter (grounding, currency, refusals, injection resistance).

Results are written to eval/last_run.json for the release-validation doc.
Also importable as a script:  python -m tests.test_ai_eval --report
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import re
import sys
import time

import pytest

CASES = pathlib.Path(__file__).parent / "eval" / "cases.jsonl"
OUT = pathlib.Path(__file__).parent / "eval" / "last_run.json"


def load_cases():
    return [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]


def check(case: dict, answer: str) -> list[str]:
    a = answer
    al = answer.lower()
    fails = []
    for s in case.get("must_include", []):
        if s.lower() not in al:
            fails.append(f"missing '{s}'")
    for s in case.get("must_not_include", []):
        if s.lower() in al:
            fails.append(f"forbidden '{s}'")
    for rx in case.get("must_not_match", []):
        if re.search(rx, a, re.I):
            fails.append(f"forbidden pattern /{rx}/")
    for key in ("must_include_any", "must_include_any_2"):
        opts = case.get(key)
        if opts and not any(o.lower() in al for o in opts):
            fails.append(f"none of {opts}")
    return fails


async def run_case(case: dict) -> dict:
    from app.ai.gateway import Gateway
    from app.ai.prompts import system_prompt
    from app.ai.schemas import ActorContext, AIRequest, DataClass, Message
    msgs = [Message("system", system_prompt(case["task"]))]
    if case.get("context"):
        msgs.append(Message("user", f"[TOOL RESULTS]\n{case['context']}\n[END TOOL RESULTS]"))
        msgs.append(Message("assistant", "Noted. I will use only these results."))
    msgs.append(Message("user", case["user"]))
    req = AIRequest(actor=ActorContext(user_id="eval"), task=case["task"], messages=msgs,
                    data_class=DataClass(case.get("data_class", "personal")), temperature=0.1, max_output_tokens=400, deadline_s=120,
                    cacheable=False)
    t0 = time.time()
    resp = await Gateway(db=None).complete(req)
    fails = check(case, resp.text)
    return {"id": case["id"], "task": case["task"], "model": resp.model, "latency_ms": int((time.time() - t0) * 1000),
            "pass": not fails, "fails": fails, "answer": resp.text[:1200]}


@pytest.mark.live_llm
@pytest.mark.parametrize("case", load_cases(), ids=lambda c: c["id"])
def test_eval_case(case):
    r = asyncio.run(run_case(case))
    _append(r)
    assert r["pass"], f"{r['fails']}\n--- answer ---\n{r['answer']}"


def _append(r: dict):
    data = json.loads(OUT.read_text()) if OUT.exists() else {"results": []}
    data["results"] = [x for x in data["results"] if x["id"] != r["id"]] + [r]
    data["summary"] = {"total": len(data["results"]), "passed": sum(1 for x in data["results"] if x["pass"])}
    OUT.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    async def main():
        results = []
        for c in load_cases():
            r = await run_case(c)
            results.append(r)
            print(("PASS" if r["pass"] else "FAIL"), r["id"], r["model"], f"{r['latency_ms']}ms", r["fails"] or "")
        OUT.write_text(json.dumps({"results": results, "summary": {"total": len(results), "passed": sum(r["pass"] for r in results)}}, indent=2))
        print(f"\n{sum(r['pass'] for r in results)}/{len(results)} passed → {OUT}")
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    asyncio.run(main())
