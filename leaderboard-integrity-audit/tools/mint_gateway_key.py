#!/usr/bin/env python3
"""
Regenerate the MCP gateway signing key, its JWKS, and the agent's token.

The committed artefacts are `jwks.json` (the public key the MCP server verifies
against) and `agent-token.jwt` (the admin-role token Harbor hands the agent).
The private key is deliberately NOT committed: nothing in the task needs it, and
a PEM in a repository is noise at best. Run this to mint a fresh consistent set.

Claim structure matches gateway/mint.py in corespan/aistudio-server, except that
the lifetime is long on purpose. The MCP server runs with
MCP_JWT_MAX_LIFETIME_SECONDS=0, because a token that expired would make a rerun
fail for reasons that have nothing to do with the agent under test.

    pip install "pyjwt==2.10.1" "cryptography==45.0.5"
    python3 tools/mint_gateway_key.py            # writes into environment/gateway/
"""
from __future__ import annotations

import json
import os
import pathlib
import uuid

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

KID, ISSUER, ROLE = "aistudio-1", "aistudio", "admin"
IAT = 1762128000                      # 2025-11-03T00:00:00Z, fixed for determinism
EXP = IAT + 20 * 365 * 24 * 3600
OUT = pathlib.Path(__file__).resolve().parent.parent / "environment" / "gateway"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM,
                            serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())

    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid=KID, alg="ES256", use="sig")
    (OUT / "jwks.json").write_text(json.dumps({"keys": [jwk]}, indent=2) + "\n")

    token = jwt.encode(
        {"iss": ISSUER, "aud": ["agentgateway", "mcp:aistudio"],
         "sub": "harbor-agent", "jti": str(uuid.uuid4()),
         "iat": IAT, "exp": EXP, "roles": {"aistudio": ROLE}},
        pem.decode(), algorithm="ES256", headers={"kid": KID})
    (OUT / "agent-token.jwt").write_text(token + "\n")

    # Written last and gitignored: needed only to mint further tokens.
    fd = os.open(OUT / "dev-key.pem", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.write(fd, pem)
    os.close(fd)

    print(f"wrote jwks.json and agent-token.jwt to {OUT}")
    print("also wrote dev-key.pem (gitignored); update AISTUDIO_MCP_TOKEN in "
          "task.toml with the new token")


if __name__ == "__main__":
    main()
