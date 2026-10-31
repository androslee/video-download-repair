# Security

This is an experimental local tool, not a sandbox. It opens media with FFmpeg and
Blender, runs local subprocesses and reads/writes files with the user's privileges.
Use maintained, trusted FFmpeg and Blender installations; exercise additional
caution with untrusted or malformed media. Source hashes detect changed inputs,
but do not establish that content is safe or authentic.

Reports may contain absolute local paths, media hashes, and, when explicitly
requested, original source filenames from a shuffler answer key. Review reports
before sharing. Generated videos, answer keys and private media should stay local unless explicitly reviewed for publication.

Please do not disclose a reproducible vulnerability or sensitive media in a public
issue. A private reporting channel must be configured and linked here before the
repository is made public. When reporting, include the version, OS, relevant tool
versions and a minimal safe reproduction.

Security review and vulnerability reporting infrastructure have not yet been
completed for a public release; see [the release checklist](docs/RELEASE_CHECKLIST.md).
