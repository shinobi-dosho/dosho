# Security Policy

## Supported versions

dosho is early-beta software. Security fixes are applied to the latest
`0.x` release only; there are no long-term-support branches yet.

| Version | Supported |
| ------- | --------- |
| latest `0.x` | :white_check_mark: |
| older       | :x: |

## Reporting a vulnerability

**Please do not report security issues in public GitHub issues.**

Report vulnerabilities privately by email to **sphemakh@gmail.com** (or via
GitHub's [private vulnerability reporting][ghsa] on this repository, if
enabled). Include enough detail to reproduce — affected version, backend,
inputs, and the impact you observed.

We aim to acknowledge reports within a reasonable time, work with you on a fix,
and credit you in the release notes if you'd like.

[ghsa]: https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability

## Security posture

Cab-loading and authoring rules are described in
[`CONTRIBUTING.md`](CONTRIBUTING.md#before-adding-a-cab). The security boundaries
are:

- **Cab definitions are treated as untrusted data.** Loading them parses static
  declarations without evaluating or executing their contents.
- Only the `binary` cab flavour is executed; other flavours are rejected by
  `build_argv()` with `UnsupportedFlavourError` *before* any argv is built.
- Backends invoke commands with **list-form** `subprocess.run` — never
  `shell=True`, never string interpolation into a shell.
- Compiled offload scripts embed exec-form argv only (via `shlex.join`) with
  charset-validated job names.

If you find a way around any of these guarantees, it's a security issue — please
report it as above.

## Static compiler ownership

From v0.2.0b1 Dosho owns static cab parsing, parameter model generation and
argv formatting. Its validation extra never imports Shinobi. Caller-supplied
trusted dtype bindings preserve strict framework annotations; known framework
dtypes without bindings are refused. Framework declaration fragments are inert
JSON until the Shinobi adapter validates its authoritative models.

Composition never imports packages or evaluates commands or schema hooks.
Package-root containment, cycle detection, unsupported-flavour refusal and
explicit output/write declarations remain enforced. Detached Shinobi workers
stage and digest both packages and validate frozen cab semantics. That source
digest does not replace scientific cache, dataset or attempt identities.
