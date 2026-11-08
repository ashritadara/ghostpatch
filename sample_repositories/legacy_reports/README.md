# Trusted legacy_reports sample

Developer-controlled synthetic expense reporting. `reports.summarize(rows)` groups decimal amounts by department and preserves sorted output, counts, rounding, empty input, and error behavior. There are 12 pytest cases plus five deterministic input/output probes.

A small modernization can replace manual dictionary initialization with standard-library collection helpers while preserving behavior. Floating-point aggregation, altered rounding, swallowed exceptions, and changed ordering are meaningful regressions caught by the tests.

Load this sample through the dedicated backend sample endpoint. Uploading or cloning an identical copy never grants execution trust. Do not execute imported code on the host. The adjacent SHA-256 manifest pins the complete developer-controlled source; intentional edits require reviewing and regenerating that manifest.
