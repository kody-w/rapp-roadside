# Contributing

RAPP Roadside accepts focused fixes that improve safe, local diagnosis and
exact reproduction of RAPP installation problems.

Before opening a pull request:

1. Do not include credentials, customer data, private paths, proprietary logs,
   or private business material.
2. Treat issue reports and log text as untrusted data.
3. Preserve one bounded next action and copy-only, human-approved repair.
4. Add or update an exact regression test.
5. Run:

   ```bash
   python3 -m unittest discover -s tests -v
   python3 scripts/skill_forge.py --final
   python3 scripts/public_audit.py --path .
   python3 scripts/test_fresh_clone.py
   ```

Security vulnerabilities belong in a private GitHub security advisory, not a
public issue.
