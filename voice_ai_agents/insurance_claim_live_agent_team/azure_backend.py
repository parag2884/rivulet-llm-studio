"""Azure OpenAI replacements for Gemini Live, claim extraction, and sketches."""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncAzureOpenAI
from pydantic import BaseModel

from schemas import ClaimClassification, ClaimNarrative
from settings import azure_api_key, azure_api_version, azure_deployment, azure_endpoint

_CLIENT: AsyncAzureOpenAI | None = None

NORMALIZER_INSTRUCTION = """
You are the intake specialist for an AI Insurance Claim Intake Agent.

Read the user's messy insurance claim narrative and produce a structured
ClaimNarrative. Preserve facts exactly when possible. Do not invent policy
numbers, contacts, dates, locations, evidence, or dollar amounts.

Extraction rules:
- policyholder_name: claimant or policyholder name, otherwise "not specified".
- policy_number: policy/member number, otherwise "not specified".
- contact_method: phone, email, mailing address, or preferred channel, otherwise "not specified".
- date_of_loss: date or date range of the loss, otherwise "not specified".
- reported_date: date the user says they are reporting the claim, otherwise "not specified".
- loss_location: address, city, intersection, provider, or travel route, otherwise "not specified".
- loss_description: concise factual description of what happened.
- estimated_loss_usd: numeric USD estimate only if supplied.
- injuries_or_safety_concerns: include injuries, urgent medical care, unsafe housing, electrical hazards, sewage, mold, or no place to live.
- evidence_available: photos, video, receipts, report numbers, estimates, bills, carrier notices, EOBs, proof of payment, serial numbers, or similar evidence already mentioned.
- documents_mentioned: specific documents mentioned whether available or missing.
- missing_or_uncertain_facts: key facts the narrative says are unknown, vague, or incomplete.

This is an intake normalization step only. Do not confirm coverage or payment.
""".strip()

CLASSIFIER_INSTRUCTION = """
Classify this normalized claim for insurance intake routing.

Supported claim types:
- home_water_damage
- auto_collision
- theft_property_loss
- health_medical_reimbursement
- travel_delay_cancellation
- other

Severity rubric:
- low: complete, low-dollar, no injury/safety issue, routine documentation.
- medium: missing documents or moderate complexity.
- high: high estimated loss, unclear liability, missing core facts, or specialized handling likely.
- urgent: injury, unsafe living condition, emergency medical/safety concern, or time-sensitive mitigation.

Return only the structured ClaimClassification. This is classification, not a
coverage decision.
""".strip()


def azure_client() -> AsyncAzureOpenAI:
    global _CLIENT
    if _CLIENT is None:
        endpoint = azure_endpoint()
        key = azure_api_key()
        if not endpoint or not key:
            raise RuntimeError("Azure OpenAI endpoint and API key are required.")
        _CLIENT = AsyncAzureOpenAI(
            api_key=key,
            api_version=azure_api_version(),
            azure_endpoint=endpoint,
        )
    return _CLIENT


def openai_tool_declarations() -> list[dict[str, Any]]:
    """Same four intake tools, in the Chat Completions tools schema."""

    def fn(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    return [
        fn(
            "lookup_policy",
            "Verify an insurance policy number against the carrier policy directory.",
            {
                "policy_number": {
                    "type": "string",
                    "description": "Policy number exactly as the claimant said it, for example H0-44721.",
                }
            },
            ["policy_number"],
        ),
        fn(
            "sync_claim_packet",
            "Send the conversation and camera observations to the claim team for routing and open items.",
            {
                "reason": {
                    "type": "string",
                    "description": "Why you are syncing now, for example 'new loss facts' or 'injury mentioned'.",
                }
            },
            [],
        ),
        fn(
            "pin_evidence_photo",
            "Pin the current camera frame into the claim file with your observation and whether it confirms the claimant.",
            {
                "observation": {
                    "type": "string",
                    "description": "One or two concrete sentences describing only what you can actually see.",
                },
                "claimant_description": {
                    "type": "string",
                    "description": "What the claimant says this shows. Empty if they did not describe it.",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "True only if the frame clearly shows what the claimant described.",
                },
                "evidence_type": {
                    "type": "string",
                    "description": "damage, receipt, document, serial number, or scene.",
                },
            },
            ["observation", "confirmed"],
        ),
        fn(
            "draw_incident_sketch",
            "Draw a rough sketch of the incident scene into the claim file. Call again with corrections.",
            {
                "scene_description": {
                    "type": "string",
                    "description": "Illustrator brief: layout, what was damaged, and direction of impact or water.",
                }
            },
            ["scene_description"],
        ),
    ]


async def parse_structured(model_type: type[BaseModel], *, system: str, user: str) -> BaseModel:
    client = azure_client()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    parse = getattr(client.chat.completions, "parse", None)
    if parse is None:
        parse = client.beta.chat.completions.parse
    response = await parse(
        model=azure_deployment(),
        temperature=0,
        messages=messages,
        response_format=model_type,
    )
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError(f"Azure OpenAI returned no structured {model_type.__name__}.")
    return parsed


async def extract_claim(transcript: str) -> ClaimNarrative:
    return await parse_structured(
        ClaimNarrative,
        system=NORMALIZER_INSTRUCTION,
        user=(
            "Use this full claimant transcript as the source of truth. "
            "Do not invent missing facts.\n\n"
            f"{transcript}"
        ),
    )


async def classify_claim(claim: dict[str, Any], validation: dict[str, Any]) -> ClaimClassification:
    return await parse_structured(
        ClaimClassification,
        system=CLASSIFIER_INSTRUCTION,
        user=(
            "Normalized claim:\n"
            f"{json.dumps(claim, ensure_ascii=False, indent=2)}\n\n"
            "Validation:\n"
            f"{json.dumps(validation, ensure_ascii=False, indent=2)}"
        ),
    )


async def draw_svg_sketch(scene_description: str) -> bytes:
    """Ask the chat model for a clean line-drawing SVG, since this Azure setup has no image model."""

    prompt = (
        "Return ONLY a complete SVG document. No markdown, no explanation. "
        "Canvas 1024x640, white background #f4f7f8, ink #14202b, "
        "clean architectural lines (stroke-width 2). "
        "Small printed labels. Light teal #9ed9d0 wash only where water is, "
        "light coral #e8a39a wash only on impact damage. No people, no names, no dates, "
        "no addresses, no claim numbers. Scene: "
        f"{scene_description.strip()}"
    )
    response = await azure_client().chat.completions.create(
        model=azure_deployment(),
        temperature=0.4,
        messages=[
            {
                "role": "system",
                "content": "You output SVG markup only. The first character must be '<'.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    svg = (response.choices[0].message.content or "").strip()
    if svg.startswith("```"):
        svg = svg.strip("`")
        if svg.lower().startswith("svg"):
            svg = svg[3:].strip()
    if "<svg" not in svg.lower():
        raise RuntimeError("Azure OpenAI did not return SVG markup for the sketch.")
    start = svg.lower().find("<svg")
    svg = svg[start:]
    end = svg.lower().rfind("</svg>")
    if end != -1:
        svg = svg[: end + 6]
    return svg.encode("utf-8")
