# Course Registration System

A small Django application for student course registration. Students identify
themselves by name and level, pick courses for their level, and print a
registration form for signing. Staff sign in to manage courses and view
students.


## Live demo

- Live site: https://schooltry-course-registration.onrender.com
- Source code: https://github.com/olanix2002/course-registration-system

The site runs on a free hosting plan, so the first request after a quiet period can take up to a minute while the service wakes up. After that it responds normally.

### Try it as a student (no login needed)

1. Open the live site, enter a name and a level (for example Amina Bello, 100 Level), and continue.
2. Tick the courses you are taking and press Save registration. Unticking a course removes it.
3. Open My courses to see your saved courses and the total credit units, then use Print form for the printable registration form.

Sample students already exist: Amina Bello (100 Level) and Bola Ade (300 Level).

### Try it as an administrator

1. Go to https://schooltry-course-registration.onrender.com/manage/login/
2. Sign in with the demo account:
   - Username: admin
   - Password: ifKtAQxhMVcImnY9
3. Create or edit courses and assign each osne to a level, activate or deactivate courses, and open Students to see every student and the courses they registered for.

The demo account and the sample data exist for review only.

## What it does

**Students** (no account needed)

1. Enter name and level. The same name and level returns to the same record,
   matched case-insensitively with whitespace tidied.
2. Tick courses. Only active courses at their level are listed, and the
   running total of credit units updates as courses are ticked.
3. Save. The previous selection is replaced in one transaction, so a failure
   leaves the earlier selection intact.
4. Print a registration form, or remove an individual course later.

**Staff** (sign in at `/manage/`)

- List, create and edit courses.
- Deactivate a course rather than delete it. Deleting a course that students
  have registered for is refused by the model.
- View each student and their registered courses.

## Requirements

- Python 3.12
- Django 5.2
- No JavaScript framework, no REST API, no Docker, no Celery, no Redis.
  Templates are rendered on the server.

## Running locally

Create a virtual environment and install the pinned packages:

```bash
python -m venv .venv
```

```bash
source .venv/bin/activate
```

On Windows, activate with `.venv\Scripts\activate` instead.

```bash
pip install -r requirements.txt
```

Create your local environment file from the example:

```bash
cp .env.example .env
```

Open `.env` and set `SECRET_KEY`. Generate one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Leave `DATABASE_URL` blank to use the local SQLite file. Set `ADMIN_USERNAME`
and `ADMIN_PASSWORD` to the staff account you want.

Then create the database tables, the staff account and some sample data:

```bash
python manage.py migrate
```

```bash
python manage.py create_admin
```

```bash
python manage.py seed_data
```

Start the server:

```bash
python manage.py runserver
```

The student pages are at http://127.0.0.1:8000/ and the staff area at
http://127.0.0.1:8000/manage/.

## Tests

```bash
python manage.py test
```

63 tests cover staff access and permissions, student identification, course
selection and its limits, re-submission and rollback, the models' own rules,
the printable form, and the sample data command.

## How it is put together

```
config/          settings, URLs, WSGI and ASGI entry points
registration/    the only app
  models.py      Course, Student, Registration
  forms.py       course form, student identification, staff login
  views.py       student pages and staff pages
  urls.py        staff URLs under /manage/
  student_urls.py student URLs at the site root
  tests.py       the test suite
  management/commands/
    create_admin.py   create or update the staff account
    seed_data.py      sample courses, students and registrations
  templates/registration/
    student/     identify, select, my_courses, print
    manage/      login, course list and form, student list and detail
```

### The data model

- **Course**: code (unique, stored uppercase), title, level (100 to 500),
  credit units (default 3), core or elective, active flag.
- **Student**: name, level, optional matric number. A name and level pair is
  unique, ignoring case.
- **Registration**: one row per student and course, unique together. Deleting a
  student removes their registrations; a course cannot be deleted while
  registrations point at it.

### The rules worth knowing

- Registration is replaced as a whole inside `transaction.atomic()`. If any
  part fails, nothing changes.
- A submission is rejected if it is empty, contains the same course twice,
  contains an inactive course, or contains a course from another level.
- There is a cap of 24 credit units. The running total in the browser and the
  check on the server agree, and the server is the one that decides.
- Students have no password. The name and level are kept in the session, which
  is why the printable form never offers an electronic signature.

## Deployment

Render for the web service, Neon for PostgreSQL. The steps are in
[DEPLOYMENT.md](DEPLOYMENT.md). `DATABASE_URL` takes the Neon **direct**
connection string, the one whose host has no `-pooler`.

Quick summary: `render.yaml` sets the build and start commands, `build.sh` runs
the build steps, and `.python-version` pins Python 3.12. Environment variables
hold every secret, and `SECRET_KEY` has no fallback in `settings.py`, so a
missing key stops the app instead of running with a known one.

Check the deployment settings locally with fake values:

```bash
python deploy_check.py
```

## Possible future enhancements

Ideas that were deliberately left out, to keep the project inside its brief:

- Student accounts with passwords, so a registration is tied to an
  authenticated person rather than a name and level.
- Prerequisites between courses.
- A registration window with open and close dates.
- Waitlists for full courses.
- Exporting registrations as CSV for the faculty office.
- Audit history showing who changed a course and when.
- Email confirmation of a submitted registration, which would need a task
  queue the brief rules out.
