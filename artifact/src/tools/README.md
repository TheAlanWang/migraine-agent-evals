# Author maintenance tools

These utilities create releases, redact retrieved text, prepare annotation or
clinical-review packages, and freeze archived results. They are not part of the
reader quickstart.

Before changing repository visibility, run:

```bash
python artifact/src/tools/check_release_ready.py --history
python artifact/reproduce.py
```

`artifact/src/tools/make_public_snapshot.py` exists because the internal working
repository
has a different history and must never be made public directly.
