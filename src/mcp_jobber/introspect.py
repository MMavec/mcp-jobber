"""`mcp-jobber-introspect` — dump the Jobber schema bits the tools depend on.

Uses whatever auth you already configured (OAuth refresh token or bearer token)
to run a GraphQL introspection query, then prints the fields/args of the types
that `queries.py` builds on (Client, Quote, Invoice, Job, the matching filter
inputs, and the status enums) plus the names of any `note*` mutations. Use it to
confirm — and, where needed, correct — the documents in `queries.py`.

    $ JOBBER_CLIENT_ID=... JOBBER_CLIENT_SECRET=... JOBBER_REFRESH_TOKEN=... mcp-jobber-introspect
"""

from __future__ import annotations

import asyncio
import json
import sys

from .auth import JobberAuth
from .client import JobberClient
from .config import load_settings

_INTROSPECTION = """
query Introspect {
  __schema {
    queryType { name }
    mutationType {
      fields { name args { name type { ...TypeRef } } }
    }
    types {
      kind
      name
      enumValues { name }
      inputFields { name type { ...TypeRef } }
      fields { name args { name type { ...TypeRef } } type { ...TypeRef } }
    }
  }
}
fragment TypeRef on __Type {
  kind name
  ofType { kind name ofType { kind name ofType { kind name } } }
}
"""

INTERESTING_TYPES = {
    "Client",
    "Quote",
    "Invoice",
    "Job",
    "ClientFilterAttributes",
    "QuoteFilterAttributes",
    "InvoiceFilterAttributes",
    "JobFilterAttributes",
    "ClientEditInput",
    "QuoteStatusTypeEnum",
    "InvoiceStatusTypeEnum",
    "JobStatusTypeEnum",
}


def _unwrap(type_ref: dict | None) -> str:
    if not type_ref:
        return "?"
    name = type_ref.get("name")
    if name:
        return name
    return _unwrap(type_ref.get("ofType"))


def _print_type(t: dict) -> None:
    name = t.get("name")
    kind = t.get("kind")
    print(f"\n=== {name} ({kind}) ===")
    if t.get("enumValues"):
        print("  values:", ", ".join(v["name"] for v in t["enumValues"]))
    for f in t.get("inputFields") or []:
        print(f"  input {f['name']}: {_unwrap(f['type'])}")
    for f in t.get("fields") or []:
        args = ", ".join(f"{a['name']}: {_unwrap(a['type'])}" for a in (f.get("args") or []))
        suffix = f"({args})" if args else ""
        print(f"  field {f['name']}{suffix} -> {_unwrap(f.get('type'))}")


async def _run() -> int:
    settings = load_settings()
    auth = JobberAuth(settings)
    client = JobberClient(settings, auth)
    try:
        data = await client.execute(_INTROSPECTION)
    finally:
        await client.aclose()
        await auth.aclose()

    schema = data["__schema"]
    by_name = {t["name"]: t for t in schema["types"] if t.get("name")}

    for name in sorted(INTERESTING_TYPES):
        if name in by_name:
            _print_type(by_name[name])
        else:
            print(f"\n=== {name} === NOT FOUND in schema (name may differ)")

    note_mutations = [
        f for f in (schema.get("mutationType") or {}).get("fields", [])
        if "note" in f["name"].lower()
    ]
    print("\n=== note* mutations ===")
    for f in note_mutations:
        args = ", ".join(f"{a['name']}: {_unwrap(a['type'])}" for a in (f.get("args") or []))
        print(f"  {f['name']}({args})")
    if not note_mutations:
        print("  (none found)")

    if "--json" in sys.argv:
        print("\n--- raw introspection JSON ---")
        print(json.dumps(schema, indent=2))
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
