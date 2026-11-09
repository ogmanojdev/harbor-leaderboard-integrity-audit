# Verifier image. The grader uses only the Python standard library, so nothing
# is installed here: the task is offline in both phases and a grade must never
# depend on reaching a package index.
#
# Harbor builds this image for the separate verifier and expects the tests to be
# bundled into it, which is what the COPY below does.
FROM python:3.12.7-slim-bookworm

WORKDIR /app
COPY . /tests/

# The submitted codec runs as `nobody` in short-lived child processes. It must
# be able to read the grader's runner, and must NOT be able to read the
# held-out corpus -- a codec that could open it would only have to index into
# it. The parent process runs as root and reads it on the children's behalf,
# passing each child only the data that phase is entitled to see.
RUN chmod -R a+rX /tests \
 && chmod 0755 /tests/runner.py /tests/verify.py \
 && chmod 0700 /tests/data \
 && chmod 0600 /tests/data/heldout.txt
