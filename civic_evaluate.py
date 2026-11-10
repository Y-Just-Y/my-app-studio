#!/usr/bin/env python3
"""Run one frozen, bounded civic evaluation; real calls require explicit opt-in.

The answer judgments require subsequent evidence review. Mechanical checks and
retrieval coverage are not a human peer review or a proof of general accuracy.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from dotenv import load_dotenv
import httpx

from app import civic_ai, civic_store, civic_vectors

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "docs" / "research" / "newark-results.json"
TOP_K = 5
QUESTIONS = [
    {
        "id": "Q1",
        "kind": "exact-term",
        "question": (
            "What scheduled time and location are listed for the Newark Municipal "
            "Council meeting on November 5, 2026?"
        ),
        "expected_source_ids": ["newark-meeting-302232"],
        "expected_facts": ["12:30 PM", "America/New_York", "Council Chamber"],
        "criterion": (
            "Report the scheduled details without claiming the meeting occurred."
        ),
    },
    {
        "id": "Q2",
        "kind": "paraphrase",
        "question": (
            "For the council session dated November 5, 2026, where were residents "
            "told to go, and what local clock time was listed?"
        ),
        "expected_source_ids": ["newark-meeting-302232"],
        "expected_facts": ["12:30 PM", "Council Chamber"],
        "criterion": "Recover the same schedule evidence despite the wording change.",
    },
    {
        "id": "Q3",
        "kind": "relationship",
        "question": (
            "Which council meeting listed ordinance 26-0816, and what was that "
            "meeting's scheduled start time?"
        ),
        "expected_source_ids": ["newark-agenda-517475", "newark-meeting-302232"],
        "expected_facts": ["26-0816", "November 5, 2026", "12:30 PM"],
        "criterion": (
            "Link the agenda item to the schedule; do not infer final passage."
        ),
    },
    {
        "id": "Q4",
        "kind": "comparison",
        "question": (
            "Were the November 5, 2026 and October 21, 2026 Newark council "
            "sessions scheduled at the same local time? State both listed times."
        ),
        "expected_source_ids": ["newark-meeting-302232", "newark-meeting-302231"],
        "expected_facts": ["12:30 PM", "6:30 PM"],
        "criterion": "Preserve both dates and the different local scheduled times.",
    },
    {
        "id": "Q5",
        "kind": "unanswerable",
        "question": (
            "What is the total approved City of Newark budget for 2026 in dollars?"
        ),
        "expected_source_ids": [],
        "expected_facts": [],
        "criterion": (
            "Declare insufficient evidence; invent no amount and cite no support."
        ),
    },
]


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(chunks):
    records = [
        {
            key: row[key]
            for key in ("chunk_id", "content_hash", "source_hash", "version")
        }
        for row in sorted(chunks, key=lambda row: row["chunk_id"])
    ]
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def _ranking(rows, expected):
    sources = {row["source_id"] for row in rows}
    return {
        "ranked_chunks": [
            {
                "rank": rank,
                "chunk_id": row["chunk_id"],
                "source_id": row["source_id"],
                "score": row["score"],
                **(
                    {"vector_distance": row["vector_distance"]}
                    if "vector_distance" in row
                    else {}
                ),
            }
            for rank, row in enumerate(rows, 1)
        ],
        "expected_source_coverage_at_5": (
            len(sources.intersection(expected)) / len(expected) if expected else None
        ),
        "all_expected_sources_present": (
            set(expected).issubset(sources) if expected else None
        ),
    }


def _fusion(keyword, semantic):
    scores, records = {}, {}
    for ranking in (keyword, semantic):
        for rank, row in enumerate(ranking, 1):
            identifier = row["chunk_id"]
            records[identifier] = row
            scores[identifier] = scores.get(identifier, 0) + 1 / (60 + rank)
    return [
        {**records[identifier], "score": scores[identifier]}
        for identifier in sorted(scores, key=lambda key: (-scores[key], key))[:TOP_K]
    ]


def _chunk_experiment(database, chunks):
    result = []
    for document in civic_store.snapshot(database, limit=50)["documents"]:
        text = document["text"]
        actual = [
            row["text"] for row in chunks if row["source_id"] == document["source_id"]
        ]
        fixed = [text[offset : offset + 1600] for offset in range(0, len(text), 1600)]
        schedule = None
        if document["metadata"].get("kind") == "meeting":
            start = text.index("Meeting date:")
            end = text.index("\nAgenda publication status:")
            schedule = text[start:end]
        result.append(
            {
                "source_id": document["source_id"],
                "source_hash": document["content_hash"],
                "input_characters": len(text),
                "paragraph_chunks": len(actual),
                "fixed_chunks": len(fixed),
                "schedule_span": schedule,
                "paragraph_schedule_together": (
                    any(schedule in part for part in actual) if schedule else None
                ),
                "fixed_schedule_together": (
                    any(schedule in part for part in fixed) if schedule else None
                ),
            }
        )
    return {
        "units": "Unicode characters, not model tokens",
        "maximum_characters": 1600,
        "overlap_characters": 0,
        "comparison": (
            "Actual heading/paragraph chunks versus fixed 1600-character windows"
        ),
        "records": result,
        "limitation": (
            "Boundary inspection only; no answer-quality advantage is inferred."
        ),
    }


def _plan(database, configuration):
    chunks = civic_store.list_chunks(database)
    identifiers = {row["source_id"] for row in chunks}
    expected = {
        item for question in QUESTIONS for item in question["expected_source_ids"]
    }
    if not expected.issubset(identifiers):
        raise ValueError(
            "The frozen question set requires source IDs missing from this import."
        )
    index = civic_vectors.index_status(database, configuration["embedding_model"])
    if not index["complete"]:
        raise ValueError(
            "Complete the compatible real embedding index before evaluation."
        )
    return {
        "schema_version": 1,
        "phase": "planned",
        "plan_frozen_at_utc": _utc_now(),
        "date_context": "2026-11-10 America/New_York",
        "scope": (
            "Local real-source/real-model evaluation; not hosted or human peer evidence"
        ),
        "source_fingerprint": _fingerprint(chunks),
        "models": {
            "chat_model": configuration["chat_model"],
            "embedding_model": configuration["embedding_model"],
            "dimensions": index["dimensions"],
            "resolved_provider_snapshot": "Not exposed by the current gateway receipt.",
        },
        "corpus": [
            {
                key: row[key]
                for key in (
                    "chunk_id",
                    "source_id",
                    "content_hash",
                    "source_hash",
                    "version",
                    "url",
                    "fetched_at",
                )
            }
            for row in chunks
        ],
        "question_plan": QUESTIONS,
        "limits": {
            "generation_calls_maximum": 5,
            "query_embedding_calls_maximum": 5,
            "top_k": TOP_K,
            "generation_output_token_cap": 1536,
            "automatic_retries": 0,
            "reported_cost": (
                "No dollar total measured here; consult the OpenAI project usage."
            ),
        },
        "calls_attempted": {"query_embedding": 0, "generation": 0},
        "results": [],
        "chunk_boundary_experiment": _chunk_experiment(database, chunks),
        "source_link_checks": [],
    }


def _save(report, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def _checks(question, chunks, answer):
    available = {row["chunk_id"]: row for row in chunks}
    cited = answer["citation_ids"]
    cited_sources = {available[identifier]["source_id"] for identifier in cited}
    return {
        "citations_within_supplied_context": all(key in available for key in cited),
        "all_expected_sources_cited": (
            set(question["expected_source_ids"]).issubset(cited_sources)
            if question["expected_source_ids"]
            else None
        ),
        "unanswerable_refusal_and_no_citations": (
            answer["insufficient_evidence"] and not cited
            if question["kind"] == "unanswerable"
            else None
        ),
        "support_judgment": (
            "Pending evidence review; ID validation is not claim-level faithfulness."
        ),
    }


def _run_question(report, question, database, destination):
    result = {"id": question["id"], "status": "in_progress"}
    report["results"].append(result)
    lexical = civic_store.search(database, question["question"], limit=TOP_K)
    report["calls_attempted"]["query_embedding"] += 1
    _save(report, destination)
    vector = civic_ai.embed_texts([question["question"]])[0]
    semantic = civic_vectors.search_vectors(
        database, vector, report["models"]["embedding_model"], limit=TOP_K
    )
    hybrid = _fusion(lexical, semantic)
    result.update(
        {
            "keyword": _ranking(lexical, question["expected_source_ids"]),
            "vector": _ranking(semantic, question["expected_source_ids"]),
            "hybrid_rrf_60": _ranking(hybrid, question["expected_source_ids"]),
            "generation_context": hybrid,
        }
    )
    if not hybrid:
        raise ValueError(
            "The evaluation had no generation context; no answer was fabricated."
        )
    if _fingerprint(civic_store.list_chunks(database)) != report["source_fingerprint"]:
        raise ValueError(
            "The source snapshot changed during evaluation; stop and inspect."
        )
    report["calls_attempted"]["generation"] += 1
    _save(report, destination)
    answer = civic_ai.generate_answer(question["question"], hybrid)
    result.update(
        {
            "status": "completed",
            "completed_at_utc": _utc_now(),
            "actual_answer": answer,
            "mechanical_checks": _checks(question, hybrid, answer),
            "support_review": {
                "reviewer": "AI implementation agent; not a human peer",
                "status": "pending",
                "reason": "Inspect actual claims against the cited source text.",
            },
        }
    )
    _save(report, destination)


def _check_links(report):
    urls = list(dict.fromkeys(row["url"] for row in report["corpus"]))[:7]
    with httpx.Client(timeout=12, follow_redirects=False, trust_env=False) as client:
        for url in urls:
            record = {"url": url, "checked_at_utc": _utc_now()}
            try:
                with client.stream("GET", url) as response:
                    record["status"] = response.status_code
                    record["redirect"] = response.headers.get("location")
            except httpx.HTTPError:
                record["status"] = None
                record["error"] = "Source link could not be reached in this check."
            report["source_link_checks"].append(record)


def _experiment_markdown(experiment):
    meeting_records = [
        row for row in experiment["records"] if row["schedule_span"] is not None
    ]
    paragraph_total = sum(row["paragraph_chunks"] for row in experiment["records"])
    fixed_total = sum(row["fixed_chunks"] for row in experiment["records"])
    intact_paragraph = sum(
        row["paragraph_schedule_together"] for row in meeting_records
    )
    intact_fixed = sum(row["fixed_schedule_together"] for row in meeting_records)
    return [
        "",
        "## Executed chunk-boundary comparison",
        "",
        f"At equal 1600-character caps and zero overlap, the paragraph method "
        f"produced {paragraph_total} chunks and fixed windows produced "
        f"{fixed_total}. The complete date/time/location span stayed together "
        f"in {intact_paragraph}/{len(meeting_records)} meeting records with "
        f"paragraph splitting and {intact_fixed}/{len(meeting_records)} "
        "with fixed windows.",
        "These observations establish no retrieval/answer-quality advantage. "
        "The sources were short; tokenizer-aware and broader quality "
        "experiments remain open.",
    ]


def _write_markdown(report, destination):
    lines = [
        "# Newark civic RAG: executed local evaluation",
        "",
        "Machine-readable evidence: [newark-results.json](newark-results.json).",
        "Frozen question expectations precede model calls. This is AI-reviewed local",
        "evidence, not human peer feedback, instructor grading or hosted availability.",
        "",
        f"Run phase: **{report['phase']}**. Models: `{report['models']['chat_model']}`",
        f"and `{report['models']['embedding_model']}` "
        f"({report['models']['dimensions']} dimensions).",
        f"Actual attempted calls: {report['calls_attempted']['query_embedding']} "
        "query embedding,",
        f"{report['calls_attempted']['generation']} generation. No automatic retries.",
        "",
        "| Question | Keyword required-source coverage@5 | Vector coverage@5 | "
        "Hybrid coverage@5 | Evidence-review status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report["results"]:
        values = []
        for method in ("keyword", "vector", "hybrid_rrf_60"):
            score = row.get(method, {}).get("expected_source_coverage_at_5")
            values.append("Not applicable" if score is None else f"{score:.0%}")
        lines.append(
            f"| {row['id']} | {' | '.join(values)} | "
            f"{row.get('support_review', {}).get('status', row['status'])} |"
        )
    if "summary" in report:
        lines.extend(["", report["summary"]["generalization_limit"]])
    for row in report["results"]:
        question = next(q for q in QUESTIONS if q["id"] == row["id"])
        lines.extend(
            ["", f"## {row['id']}: {question['kind']}", "", question["question"], ""]
        )
        if "actual_answer" in row:
            lines.extend([row["actual_answer"]["answer"], ""])
            cited = set(row["actual_answer"]["citation_ids"])
            for chunk in row["generation_context"]:
                if chunk["chunk_id"] in cited:
                    lines.append(f"- [{chunk['chunk_id']}]({chunk['url']})")
            lines.append("")
            lines.append("AI evidence judgment: " + row["support_review"]["reason"])
        else:
            lines.append("No completed model answer recorded.")
    lines.extend(["", "## Source-link checks", ""])
    for check in report["source_link_checks"]:
        code = check.get("status") or "Unavailable"
        label = next(
            row["source_id"] for row in report["corpus"] if row["url"] == check["url"]
        )
        lines.append(f"- HTTP {code}: [{label}]({check['url']})")
    lines.extend(_experiment_markdown(report["chunk_boundary_experiment"]))
    lines.extend(
        [
            "",
            "## Limits and next check",
            "",
            "Seven public sources/eight chunks are a small recent-record snapshot.",
            "Nearest neighbors may be irrelevant; missing budget data cannot establish",
            "a budget amount. Source ID validity alone does not establish answer "
            "support.",
            "This run uses hybrid context for generation; it does not compare "
            "generated",
            "answer quality across all retrievers. Dollar spend and latency "
            "were not measured.",
            "Required-source coverage@5 is not precision: irrelevant retrieved "
            "passages can remain even when every required source is present.",
            "Chunk comparison uses equal 1600-character caps, not tokenizer "
            "tokens; inspect",
            "the JSON boundary experiment before claiming a quality difference.",
            "A human peer, an expanded question set and hosted end-to-end checks "
            "remain necessary.",
        ]
    )
    if "error" in report:
        lines.extend(["", "Stopped safely: " + report["error"]])
    destination.with_suffix(".md").write_text("\n".join(lines) + "\n")


def main(arguments=None):
    """Freeze expectations first and refuse to overwrite executed evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=ROOT / "runtime" / "civic.sqlite3"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--confirm-api-usage", action="store_true")
    args = parser.parse_args(arguments)
    if not args.prepare_only and not args.confirm_api_usage:
        parser.error(
            "Add --prepare-only, or explicitly permit up to five model calls "
            "with --confirm-api-usage."
        )
    load_dotenv(ROOT / ".env", override=False)
    configuration = civic_ai.configuration_status()
    if not configuration["configured"]:
        parser.error(
            "Configure the API key privately before this real-model evaluation."
        )
    report = _plan(args.database, configuration)
    if args.output.exists():
        previous = json.loads(args.output.read_text())
        if previous["phase"] != "planned":
            parser.error(
                "Executed evidence already exists. "
                "Do not silently rerun or overwrite it."
            )
        if (
            previous["question_plan"] != QUESTIONS
            or previous["source_fingerprint"] != report["source_fingerprint"]
        ):
            parser.error(
                "The frozen question plan or corpus changed; "
                "inspect it before any calls."
            )
        report = previous
    _save(report, args.output)
    if args.prepare_only:
        _write_markdown(report, args.output)
        print("Five question expectations frozen; no model calls were made.")
        return 0
    report["phase"] = "in_progress"
    _save(report, args.output)
    try:
        for question in QUESTIONS:
            _run_question(report, question, args.database, args.output)
            print(question["id"] + " completed", flush=True)
        _check_links(report)
        report["phase"] = "completed"
        report["completed_at_utc"] = _utc_now()
    except (
        civic_ai.ModelServiceError,
        civic_ai.ModelNotConfigured,
        ValueError,
        OSError,
    ) as error:
        report["phase"] = "stopped_after_error"
        report["error"] = str(error)
        print("Stopped without retry: " + str(error), file=sys.stderr)
    _save(report, args.output)
    _write_markdown(report, args.output)
    print(
        json.dumps(
            {"phase": report["phase"], "calls_attempted": report["calls_attempted"]}
        )
    )
    return 0 if report["phase"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
