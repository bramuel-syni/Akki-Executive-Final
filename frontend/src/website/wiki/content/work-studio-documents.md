# Work Studio · Documents

Documents are the evidence base Akki reasons over. When you upload a
file, it becomes part of the workspace's chain of citation.

## What it does

Akki parses what you upload — PDF, DOCX, CSV, XLSX — and stores both
the raw file and a structured index. The next chat or compile that
runs in this workspace can cite anything from inside that file. The
file never leaves your account.

## How to use it

1. Open Work Studio. Click "Add document" in the top-right.
2. Drop one or more files. Akki shows a per-file progress line
   through parsing.
3. When a file is ready it appears in the Document Journal on the
   right rail.
4. Reference a document by name in a thread or compile and Akki
   pulls the relevant excerpt into its working set.

**Worked example.** An NED uploaded three quarters of board papers
ahead of a Risk Committee meeting. Three minutes later all three
were parsed and indexed. The NED opened a Chat thread with the
question *"What's the recurring concern across these three
quarters?"* Akki returned a one-paragraph synthesis with six
specific citations — paper, section, page — and a follow-up
question. The NED took the citations and the question into the
meeting.

## Common questions

- **What file types are supported?** PDF, DOCX, CSV, XLSX, and plain
  text. Images and audio are not yet ingested.
- **What's the size limit?** 25 MB per file. Larger files should be
  split.
- **Does Akki re-parse a file if I upload it again?** Yes. The new
  upload replaces the prior version and any threads that cited it
  carry a marker.

## Troubleshooting

- **A file is stuck in "parsing".** Wait two minutes. If it does not
  finish, refresh — the parse worker may have lost the request and
  the file will retry.
- **A document is not appearing in citations.** Check that the
  thread or compile is in the same workspace as the document. Akki
  does not cite across workspace boundaries.
