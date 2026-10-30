"""Score model predictions against a dataset split.

  python3 training/score.py training/data/eval.jsonl predictions.jsonl

predictions.jsonl has one {"prediction": "<model output>"} per line, in the same order
as the gold file. A row counts as correct when:
  - gold is a tool call: same tool and same arguments (text arguments compared
    lowercase without punctuation)
  - gold is a spoken reply: the model also replied in words (wording is not scored)
"""

import collections
import json
import re
import sys

from tools import parse_reply

TEXT_ARGS = {"label", "location", "query", "question"}


def norm_args(arguments):
    return {k: re.sub(r"[^\w\s]", "", v.lower()).strip() if k in TEXT_ARGS and isinstance(v, str) else v
            for k, v in arguments.items()}


def judge(gold_text, pred_text):
    """Return (correct, tool_name_correct, kind) for one row."""
    gold, pred = parse_reply(gold_text), parse_reply(pred_text)
    if pred[0] == "invalid":
        return False, False, "invalid"
    if gold[0] == "say":
        return pred[0] == "say", pred[0] == "say", "say"
    if pred[0] != "tool" or pred[1] != gold[1]:
        return False, False, "wrong_tool"
    ok = norm_args(pred[2]) == norm_args(gold[2])
    return ok, True, "ok" if ok else "wrong_args"


def score(gold_rows, predictions):
    assert len(gold_rows) == len(predictions), (len(gold_rows), len(predictions))
    per_intent = collections.defaultdict(lambda: [0, 0])
    kinds = collections.Counter()
    exact = name_ok = 0
    failures = []
    for row, pred in zip(gold_rows, predictions):
        gold_text = row["messages"][-1]["content"]
        ok, name, kind = judge(gold_text, pred)
        exact += ok
        name_ok += name
        kinds[kind] += 1
        per_intent[row["intent"]][0] += ok
        per_intent[row["intent"]][1] += 1
        if not ok:
            failures.append((row["messages"][1]["content"], gold_text, pred))
    n = len(gold_rows)
    return {
        "n": n,
        "exact": exact / n,
        "tool_name": name_ok / n,
        "invalid": kinds["invalid"] / n,
        "per_intent": {k: v[0] / v[1] for k, v in sorted(per_intent.items())},
        "failures": failures,
    }


def report(result, show_failures=15):
    print(f"rows {result['n']}  exact {result['exact']:.1%}  tool name {result['tool_name']:.1%}  "
          f"invalid {result['invalid']:.1%}")
    weak = {k: v for k, v in result["per_intent"].items() if v < 0.9}
    if weak:
        print("intents under 90%:", ", ".join(f"{k} {v:.0%}" for k, v in sorted(weak.items(), key=lambda x: x[1])))
    for utterance, gold, pred in result["failures"][:show_failures]:
        print(f"  {utterance!r}\n    gold {gold}\n    got  {pred}")


def main():
    gold_path, pred_path = sys.argv[1], sys.argv[2]
    gold_rows = [json.loads(line) for line in open(gold_path)]
    predictions = [json.loads(line)["prediction"] for line in open(pred_path)]
    report(score(gold_rows, predictions))


if __name__ == "__main__":
    main()
