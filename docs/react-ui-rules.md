# React Product UI Rules

This is the running list of cross-page presentation and interaction rules that are easy to lose when implementing individual React branches. API storage shapes remain documented in `docs/api.md`; these rules describe Product UI meaning.

## User identity and roles

- Owner is presented as the highest user role, above Manager.
- The API intentionally exposes `role` and `is_owner` separately. UI role displays resolve `is_owner` first and show `Owner`; they do not show a redundant separate Owner row.
- Use the shared user-role presentation helper so role precedence stays consistent across Profile and future user surfaces.
