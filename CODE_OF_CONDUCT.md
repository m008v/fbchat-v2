# fbchat-v2 Code of Conduct

## Purpose

`fbchat-v2` is an open-source reverse-engineering project maintained by people with different backgrounds, experience levels, languages, and goals. We want issue discussions, pull requests, reviews, and community channels to remain useful, safe, and technically focused.

By participating, you agree to follow this Code of Conduct and help maintain an environment where people can contribute without harassment or intimidation.

## Scope

This Code applies to:

- GitHub issues, discussions, pull requests, reviews, and commit comments.
- Project-managed chat groups and community channels.
- Public communication made while representing the project.
- Private communication that directly affects a contributor's ability to participate safely.

It applies to maintainers, contributors, users, reviewers, and anyone else participating in project spaces.

## Expected behavior

Participants should:

- Be respectful and patient, especially when someone is learning the codebase or communicating in a second language.
- Focus criticism on code, behavior, evidence, and tradeoffs rather than on the person who wrote it.
- Provide reproducible information when reporting bugs: version, operating system, traceback, and a minimal example with secrets removed.
- Accept constructive feedback and correct mistakes without escalating a technical disagreement into a personal conflict.
- Respect maintainer decisions about scope, safety, licensing, and unsupported automation.
- Credit upstream work and preserve license notices.
- Protect cookies, credentials, tokens, TOTP secrets, E2EE keys, and other account data.
- Use reactions, humor, and informal language in ways that do not target or exclude another participant.

## Unacceptable behavior

The following behavior is not allowed:

- Harassment, threats, stalking, intimidation, or sustained personal attacks.
- Discrimination based on identity, background, disability, nationality, religion, gender, sexual orientation, or experience level.
- Sexualized language, imagery, or unwanted attention.
- Publishing another person's private information without explicit permission.
- Posting real Facebook cookies, passwords, access tokens, TOTP secrets, media keys, or device state.
- Pressuring maintainers or contributors to test with personal accounts or exposed credentials.
- Deliberately submitting malware, credential-stealing code, destructive payloads, or hidden telemetry.
- Encouraging spam, account abuse, evasion, or high-volume automation that harms users or platforms.
- Repeatedly derailing technical discussion after a maintainer asks to return to scope.
- Impersonating a maintainer or falsely presenting an unofficial build as an official project release.

## Technical feedback

Strong technical criticism is welcome when it is specific and actionable.

Good feedback:

> This parser indexes `payload[0]` without checking the response type. The attached test shows Facebook returning an error object. Please validate the object before indexing.

Unhelpful feedback:

> This is terrible. Rewrite everything.

Review the change, not the contributor. Explain the failure path, security impact, or maintenance cost and propose a practical next step.

## Handling sensitive data

This project works with account sessions, so accidental disclosure is a serious risk.

If a user posts a secret:

1. Do not quote or copy the value into another comment.
2. Ask the user to revoke or rotate it immediately.
3. Notify a maintainer so the content can be removed where possible.
4. Keep examples and tests synthetic after cleanup.

Security vulnerabilities should not be turned into public exploitation guides while users remain exposed. Contact the maintainers privately first when responsible disclosure is appropriate.

## Reporting a violation

Report conduct violations to the project team at `minhhuydev@icloud.com`. You may also contact [@mhuydev on Telegram](https://t.me/mhuydev).

Include, when possible:

- A link or screenshot of the incident.
- The date and project space where it occurred.
- A short description of the impact.
- Any immediate safety concern.

Do not include unrelated account credentials or private data in the report.

## Enforcement process

Maintainers will review reports in good faith and may:

1. Request clarification or additional evidence.
2. Remove or edit harmful content where the platform allows it.
3. Issue a private or public warning.
4. Temporarily restrict participation.
5. Permanently ban a participant from project spaces.
6. Escalate credible threats or illegal activity to the relevant platform or authority.

The response will be proportional to severity, history, intent, impact, and whether the participant takes responsibility and corrects the behavior.

Maintainers will make reasonable efforts to protect the reporter's privacy. Complete confidentiality cannot be guaranteed when evidence must be shared to investigate or when law requires disclosure.

## Maintainer responsibility

Maintainers are expected to apply this Code consistently. A maintainer who is directly involved in a report should recuse themselves when another maintainer can review it.

Project authority must not be used to retaliate against reporters, silence legitimate technical criticism, or favor friends. Enforcement decisions should be based on behavior and evidence.

## Appeals

A participant may appeal an enforcement decision by contacting the project team once with relevant context or evidence that was not previously considered. Repeated messages, harassment, or attempts to evade restrictions may result in additional action.

## Agreement

Participation in `fbchat-v2` project spaces means accepting this Code of Conduct. The goal is not to eliminate disagreement; it is to keep disagreement productive, evidence-based, and safe for the people doing the work.
