# Password Policy

- Store only Argon2 hashes.
- Verify using constant-time library behavior.
- Never log password values.
- Support future rehashing when parameters change.
- Reject known-compromised passwords when the product reaches public deployment.
- Consider administrator-enforced reset and account lock controls.
