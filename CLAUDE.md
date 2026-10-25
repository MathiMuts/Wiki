# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Wiki2 is a single-app Django 5.2 wiki (project `wiki2_project`, app `wiki2`) with Markdown pages, per-page file attachments, image-archive galleries, page visibility levels, and printable QR labels. The UI is server-rendered Django templates in `templates/` (not inside the app) plus vanilla JS/CSS in `static/wiki/`. The README and some code comments are in Dutch.

## Commands

Local development (uses SQLite and an in-memory cache when no `.env` DB settings are present; `venv/` is a Windows venv):

```
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
python manage.py test wiki2                       # all tests
python manage.py test wiki2.tests.ChunkedUploadTests.test_full_upload_in_chunks   # a single test
```

If a local `.env` points the DB at the Docker host `db`, tests can't connect. `load_dotenv` does not override variables that are already set, so prefix the command with `DB_ENGINE=django.db.backends.sqlite3 DB_HOST=` to run against SQLite.

- `requirements.txt` is UTF-16 LE encoded. Keep that encoding when editing it, or convert the whole file deliberately.
- `STATIC_ROOT` and `MEDIA_ROOT` are hardcoded to `/app/staticfiles` and `/app/media` (container paths), so uploads in local dev land on the drive root.
- There is no linter or formatter configured.

Docker (production stack: postgres, redis, gunicorn `web`, nginx, cron `backups`):

```
docker compose up -d --build
docker exec -it wiki_django_app bash     # shell into the app container
```

`entrypoint.sh` runs `migrate` and `collectstatic --clear` on every container start. The required `.env` variables are listed in README.md. `DJANGO_DEBUG` must be exactly the string `True` to enable debug. When debug is off, settings switch to the Redis cache and turn on `SECURE_SSL_REDIRECT`/secure cookies.

Backup management commands (run inside the container from `/app`):

```
python manage.py create_wiki_backup --output-dir /app/backups
python manage.py prune_backups --backup-dir /app/backups
python manage.py restore_backup ./backups/<yyyy-mm-dd-hh-mm>.zip --dry-run [--delete-unmatched]
```

The `backups` container schedules `run_backup_job.sh` (backup, then prune) through cron at `BACKUP_TIME` (`HH:MM` or a cron expression, default 03:00).

## Deployment

Every push to `main` deploys to production automatically (`.github/workflows/deploy.yml`). The workflow SSHes into the server, runs `git reset --hard origin/main`, rebuilds with `--no-cache`, and restarts the stack. Treat commits to `main` as releases; feature work goes through PRs.

## Architecture

**Pages and routing.** `WikiPage` is addressed by slug at `/<slug>/`. The catch-all slug routes in `wiki2/urls.py` must stay below the fixed routes (`search/`, `profile/`, `all/`, `create/`, `files/...`). `/` redirects to the page with slug `home` (`constants.ROOT_WIKI_PAGE_SLUG`). Requesting a missing slug redirects to the create form with the slug pre-filled. `WikiPage.save()` auto-generates a unique slug.

**Visibility.** Pages are `PUBLIC`, `LOGGED_IN` (default), or `PRIVATE`. Staff see everything. `PRIVATE` pages are visible only to `author`, and `save()` overwrites `author` from `last_modified_by` (or clears it when the page is not private). So the owner is whoever last saved the page as private. The filtering logic exists twice: `WikiPageManager.get_visible_by_user` in `models.py` and `get_visible_pages` in `views.py`. Change both together. Edit, delete, and file-delete views only require login; they do not check visibility.

**Markdown rendering** (`services.render_markdown_to_html`). Before markdown2 runs, a regex pre-pass rewrites links outside code spans and fences (regexes are in `constants.py`). It batch-resolves targets in one query:
- `[[Target]]` and `[[Text|Target]]` become wikilinks. A missing target becomes a "(create)" link.
- `[text](target)` with a relative target resolves to a page first, then to a file attached to the *current* page, and otherwise becomes a create link.
- `![alt](file)` on an attachment renders an `<img>`, a PDF `<iframe>` (the title string carries whitelisted PDF params), or, for `.zip` archives, a gallery via `templates/wiki/modules/_archive_gallery.html`. Gallery images are served by `view_image_in_archive`, which converts HEIC to PNG and caches the result.

**Menu from a wiki page.** The sidebar menu is not stored in a model. The `wiki_menu` context processor (`context_processors.py`, runs on every request) reads the JSON array inside the `menu-config` page's content. It auto-creates that page from `constants.DEFAULT_MENU_CONFIG` if the page is missing, caches the parsed result keyed on the page's `updated_at`, and filters items per user by visibility and `login_required`. It also injects `all_wiki_pages_json` for client-side search, cached per user type for 10 minutes. Cache keys embed `updated_at` timestamps rather than being explicitly invalidated.

**Files.** `WikiFile` uploads go to `media/wiki_files/<page-slug>/<filename-slug><ext>`. Signals in `signals.py` (registered in `apps.py` `ready()`) delete the file from disk when its row is deleted, remove a page's media directory when the page is deleted, and auto-create a `Profile` for each new `User`. The attachment UI is inline JS in `templates/wiki/pages/wiki_form.html` and talks to JSON endpoints.

**Chunked uploads.** Attachments are never sent in one request. `static/wiki/JS/chunked_upload.js` calls `<slug>/upload/` (init) and then POSTs raw 10 MB slices to `<slug>/upload/<uuid>/` with an `X-Upload-Offset` header. Every response returns `received` (bytes on disk), so the client retries and resumes from there. It finishes with `.../complete/` (or `.../cancel/`). State is kept on disk in `MEDIA_ROOT/.chunked_uploads/<uuid>/` (`meta.json` + `data.part`), not in the cache, so all gunicorn workers share it. The finished file is *moved* into place (`services._StagedFile`), which is why staging lives inside `MEDIA_ROOT`. The dot-prefix keeps nginx from serving it. Abandoned uploads are purged after 24h, triggered whenever a new upload starts. Logic is in the "Chunked Upload Service" section of `services.py`, and the tests are in `wiki2/tests.py`.

**Other.** Page deletion sends an ntfy.sh notification (`NTFY_*` in settings). `LabelIcon` (managed in admin) supplies icons for the printable QR label page (`<slug>/label/`). Auth uses `django.contrib.auth.urls` under `/accounts/`, with templates in `templates/registration/`.
