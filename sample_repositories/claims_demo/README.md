# Fictional claims/eligibility sample

All code, inputs and usage events are synthetic. POLICY.md and policy.json are independent developer-approved oracle fixtures for this demonstration, not real medical/insurance requirements.

The six existing pytest tests intentionally miss the age-65 boundary. The legacy implementation uses age > 65 while policy includes age 65. Ghost Trials must discover the mismatch by executing the policy fixture, even while existing pytest tests pass. Ghost Signals demonstrates versioned, pseudonymous synthetic overrides/retries; those patterns are investigative leads, not policy authority.

Load this sample with the dedicated built-in sample endpoint. Uploaded/cloned copies are never executable. Only claims.py is editable; original tests, policy, scenarios and usage fixtures remain hash-pinned and protected.
