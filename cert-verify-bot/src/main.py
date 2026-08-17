import asyncio
import os
import re

import httpx
from dotenv import load_dotenv

from microsoft_teams.api import MessageActivity, TypingActivityInput
from microsoft_teams.apps import ActivityContext, App

load_dotenv()

# This bot is just a thin Teams-facing front door. All the actual
# verification logic lives in the existing FastAPI service (lnd-verification-
# service) -- this process only parses the chat message and calls that
# service's REST API, exactly like any other client of it would.
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")

app = App()

HELP_TEXT = (
    "Send me a certificate to verify, one field per line:\n\n"
    "Name: Jahnavi Patel\n"
    "Email: jahnavi.patel@intuitive.ai\n"
    "Cert: Claude Certified Architect - Foundations\n"
    "Proof: https://www.credly.com/badges/<uuid>/public_url\n\n"
    "Name is only needed the first time for a given email -- after that "
    "I'll recognize the email and reuse the existing employee record."
)

_FIELD_RE = re.compile(
    r"^\s*(name|email|cert|certification|proof|url|link)\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _parse_fields(text: str) -> dict:
    fields = {}
    for key, value in _FIELD_RE.findall(text):
        key = key.lower()
        if key in ("certification",):
            key = "cert"
        if key in ("url", "link"):
            key = "proof"
        fields[key] = value
    return fields


async def _find_or_create_employee(client: httpx.AsyncClient, email: str, name: str | None):
    resp = await client.get(f"{BACKEND_URL}/employees")
    resp.raise_for_status()
    for employee in resp.json():
        if employee["email"].lower() == email.lower():
            return employee, None

    if not name:
        return None, (
            f"I don't have an employee on file for {email} yet -- "
            "include a Name: line the first time so I can create one."
        )

    resp = await client.post(f"{BACKEND_URL}/employees", json={"name": name, "email": email})
    if resp.status_code >= 400:
        return None, f"Couldn't create an employee record: {resp.text}"
    return resp.json(), None


@app.on_message_pattern(re.compile(r"^\s*(hi|hello|help)\s*$", re.IGNORECASE))
async def handle_greeting(ctx: ActivityContext[MessageActivity]) -> None:
    await ctx.send(HELP_TEXT)


@app.on_message
async def handle_message(ctx: ActivityContext[MessageActivity]) -> None:
    await ctx.reply(TypingActivityInput())

    fields = _parse_fields(ctx.activity.text)
    email = fields.get("email")
    cert = fields.get("cert")
    proof = fields.get("proof")

    if not email or not cert or not proof:
        await ctx.send(
            "I need an Email, a Cert, and a Proof link to run a verification.\n\n" + HELP_TEXT
        )
        return

    async with httpx.AsyncClient(timeout=30) as client:
        employee, error = await _find_or_create_employee(client, email, fields.get("name"))
        if error:
            await ctx.send(error)
            return

        resp = await client.post(
            f"{BACKEND_URL}/verify",
            json={
                "employee_id": employee["id"],
                "certification_name": cert,
                "proof_url": proof,
            },
        )

    if resp.status_code >= 400:
        await ctx.send(f"Verification request failed: {resp.text}")
        return

    result = resp.json()
    await ctx.send(
        f"**{result['status'].upper()}** -- {employee['name']} / {cert}\n\n{result['notes']}"
    )


def main():
    asyncio.run(app.start())


if __name__ == "__main__":
    main()
