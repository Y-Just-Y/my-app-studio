# Nightly official-source refresh

This is an application background job on the existing Civic host. It is not a
Codex chat automation. It checks only the fixed Newark council feed (five recent
meetings and selected agenda items) and the selected 2026 introduced-budget URL.
It does not crawl arbitrary links, index accounts, run OCR, answer questions or
make embedding/model requests. Source search is refreshed; semantic indexing
may lag until an operator explicitly reviews API usage and indexes changed text.

The job uses the running app's immutable image ID, the existing public runtime
location and no published ports. It receives no private `.env` or OpenAI key.
The one-off container has a 192 MiB memory limit. The service has a five-minute
timeout, no restart/retry loop, and removes only its own labeled job container
on exit. A nonblocking OS lock coordinates scheduled and admin/CLI imports.

A failed fetch, including HTTP 403 or an HTML response, preserves that source's
last saved records and successful fetch date. A changed budget PDF requires
manual review of its extraction before replacement. An independently successful
council refresh may still be committed; the receipt reports partial failure or
review required. All-source extraction failure does not erase the corpus.
Repeating unchanged source material preserves source versions and chunk IDs.
Only `civic.sqlite3`, its lock and a sanitized refresh receipt are used; accounts,
sessions and request-limit data are not copied or modified.

## Enable after deployment review

Copy this directory with the reviewed application to the marked existing host
checkout `/opt/newark-civic-pulse`. The Compose image must contain
`civic_refresh.py`, `civic_budget_import.py` and `app/data/`. Then run there:

```sh
sudo bash deploy/civic/refresh/install.sh --enable-nightly
```

The timer is 03:15 America/New_York with up to five minutes of randomized delay.
`Persistent=true` permits one catch-up after downtime. It never starts a second
instance of an already active service. Set `CIVIC_REFRESH_SCHEDULE=nightly` in
the private deployment configuration and recreate the application during the
reviewed release so the website reports the declared schedule. This flag is not
a live systemd health check: use the recorded attempt time/result as execution
evidence. Default `disabled` makes no claim that the timer is installed.

Inspect actual operation without sending a model request:

```sh
sudo systemctl list-timers civic-refresh.timer --no-pager
sudo systemctl status civic-refresh.service --no-pager
sudo journalctl -u civic-refresh.service -n 30 --no-pager
curl --fail https://civic.lwdgyasteri.com/api/civic/status
```

An operator may make one immediate attempt with
`sudo systemctl start civic-refresh.service`. A partial/error/review-required
result exits nonzero so it is visible in service status; a busy attempt is
skipped. Fix the source or review the changed PDF before an explicit retry.
To stop future attempts: `sudo systemctl disable --now civic-refresh.timer`.
The installer never creates cloud resources or changes DNS, proxy or app origin.

The public receipt is `refresh_status(database)`: timestamps, fixed official
source URLs, per-source outcome, load/corpus counts and semantic readiness at
completion. It exposes no runtime paths, keys, raw exceptions or tracebacks.
Nov 10 evaluation artifacts stay immutable; a later corpus refresh is a new
snapshot, not a rerun of that historical experiment.

References: [systemd timers](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html),
[Unix file locking](https://docs.python.org/3.12/library/fcntl.html), and
[Windows nonblocking file locking](https://docs.python.org/3.12/library/msvcrt.html).
