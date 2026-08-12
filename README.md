# Feedback API — AWS Serverless Starter Project

A deliberately simple REST API, built to teach you the four things you flagged as gaps:
**containers, deployment, CI/CD pipelines, and running real infrastructure on AWS.**

The app itself is boring on purpose (submit feedback, list feedback). The *point* is the
path from your laptop to a live, auto-deploying cloud service — the exact muscle a Forward
Deployed Engineer uses, and material that overlaps heavily with the AWS Solutions Architect syllabus.

**Architecture:** FastAPI (the app) → Lambda (runs it) → API Gateway (HTTP front door) → DynamoDB (database),
packaged by AWS SAM, deployed automatically by GitHub Actions.

Everything here stays inside the new-account $200 credit + always-free allowances. Lambda,
API Gateway, and DynamoDB were chosen specifically because they don't have the silent-billing
traps that EC2/RDS/NAT Gateways do.

> **These commands are written for Windows PowerShell.** If you follow a tutorial written for
> macOS/Linux, the differences that matter are: `$env:VAR = "x"` instead of `export VAR=x`,
> `.venv\Scripts\Activate.ps1` instead of `source .venv/bin/activate`, and `curl` being a
> PowerShell alias for something else entirely (see the note in Phase 3).

---

## Prerequisites (install once)

- **Python 3.12+**
- **Docker Desktop** (needed for Phase 2, and for `sam local` in Phase 3)
- **AWS CLI** — `aws --version`
- **AWS SAM CLI** — `sam --version`
- A **GitHub account**
- Your **admin IAM user's** access keys (you already created this user — good)

Configure the CLI with your admin IAM user (NOT root):
```powershell
aws configure
# paste Access Key ID, Secret Access Key, region = ap-southeast-1, output = json
```

Check it took:
```powershell
aws configure list
aws sts get-caller-identity   # should print your admin IAM user's ARN
```

**Region for this project is `ap-southeast-1` (Singapore)** — the closest region to Hanoi.
Every command below assumes it. Mixing regions is the classic beginner confusion: resources
created in one region are simply invisible from another, including in the console.

---

## Phase 0 — Safety first (do this before anything else)

1. **Set a budget alarm.** Billing → Budgets → create a small budget (e.g. $5) with an
   email alert at 80%. This is your seatbelt. It also earns one of the $20 onboarding credits.
2. **Confirm MFA is on** for your root account, and that you're working as your admin IAM user.
3. **Confirm the region selector** in the top-right of the AWS console says **Singapore**.

---

## Phase 1 — Run the app locally (no cloud yet)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r app\requirements.txt uvicorn

# A dummy table name is fine here — the endpoints that hit DynamoDB won't have a
# real table yet, but the health endpoint proves the app runs.
$env:TABLE_NAME = "FeedbackTable"
uvicorn app.main:app --reload
```

> If `Activate.ps1` is blocked with a script-execution error, run
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and try again.
> `-Scope Process` means the relaxation dies with the window.

Open http://127.0.0.1:8000 → you should see the health JSON.
Open http://127.0.0.1:8000/docs → FastAPI's auto-generated API tester.

Stop the server with `Ctrl+C` when you're done.

**What you learned:** how a web service runs and exposes endpoints.

---

## Phase 2 — Containerize it (understand what a container is)

```powershell
docker build -t feedback-api .
docker run -p 8000:8000 -e TABLE_NAME=FeedbackTable -e AWS_DEFAULT_REGION=ap-southeast-1 feedback-api
```

Hit http://127.0.0.1:8000 again — same app, now running inside a container.

The `AWS_DEFAULT_REGION` matters: the container is an isolated filesystem, so it *cannot*
see the `~/.aws/config` on your host. Anything AWS-related that your host provides implicitly
has to be passed in explicitly. That realization is most of what containers are about.

`/feedback` will return a 503 here — the container has no AWS credentials and there's no
table yet. That's expected and correct; the health endpoint still works.

Stop it with `Ctrl+C`.

**What you learned:** a container packages your app + its dependencies into one portable unit.
This Dockerfile is for understanding only; the AWS deploy uses Lambda instead.

---

## Phase 3 — Test the full serverless stack locally with SAM

Docker Desktop must be running — SAM emulates Lambda using containers.

```powershell
sam build
sam local start-api
```

This spins up Lambda + API Gateway locally on port 3000. In a **second** terminal:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:3000/feedback -Method Post `
  -ContentType "application/json" `
  -Body '{"author":"me","message":"first feedback"}'

Invoke-RestMethod -Uri http://127.0.0.1:3000/feedback
```

> **Why not `curl`?** In PowerShell, `curl` is an alias for `Invoke-WebRequest`, which does not
> understand `-X`, `-H`, or `-d`. You can use the real thing by calling `curl.exe` explicitly,
> but the JSON quoting gets ugly:
> ```powershell
> curl.exe -X POST http://127.0.0.1:3000/feedback -H "Content-Type: application/json" -d '{\"author\":\"me\",\"message\":\"first feedback\"}'
> ```
> `Invoke-RestMethod` is cleaner on Windows and parses the JSON response into an object for you.

**What you learned:** how the pieces (function + API + table) fit together before spending a cent.

---

## Phase 4 — First real deploy to AWS

```powershell
sam build
sam deploy --guided
```

Answer the prompts:

| Prompt | Answer |
|---|---|
| Stack Name | `feedback-api` |
| AWS Region | `ap-southeast-1` |
| Confirm changes before deploy | `y` (see what it will do before it does it) |
| Allow SAM CLI IAM role creation | `y` |
| Disable rollback | `N` |
| FeedbackFunction has no authentication. Is this okay? | `y` (it's a public demo API) |
| Save arguments to configuration file | `y` |

After ~2 minutes it prints an **ApiUrl** in the Outputs table. Use it:

```powershell
$api = "https://YOUR-API-ID.execute-api.ap-southeast-1.amazonaws.com/Prod"

Invoke-RestMethod -Uri "$api/feedback" -Method Post `
  -ContentType "application/json" `
  -Body '{"author":"me","message":"hello from the cloud"}'

Invoke-RestMethod -Uri "$api/feedback"
```

**This is the moment your app is live on the internet, backed by a real database.**
Deploying a Lambda also earns another $20 onboarding credit.

Worth doing now, while it's fresh: open the AWS console (region: Singapore) and find the
three things you just created — **CloudFormation** → your `feedback-api` stack, **Lambda** →
your function, **DynamoDB** → your table with the item you just wrote. Seeing that one
`sam deploy` produced all of it is the whole idea of infrastructure-as-code.

Your answers are saved to `samconfig.toml`, so future deploys are just `sam deploy`.
That file is gitignored because it's machine-local.

---

## Phase 5 — The pipeline (the FDE-relevant part)

1. Create a **new GitHub repo** and push this project. Run this from *this* folder — the one
   containing `template.yaml`:
   ```powershell
   git init
   git add .
   git commit -m "Feedback API starter"
   git branch -M main
   git remote add origin https://github.com/YOU/feedback-api.git
   git push -u origin main
   ```
2. **Create a dedicated IAM user for CI** — do *not* reuse your own credentials. In the IAM console:
   - Users → Create user → name it `github-actions-feedback-api`
   - Do **not** give it console access; it only ever needs programmatic access
   - Attach `AdministratorAccess` for now (see the note below)
   - Open the user → Security credentials → Create access key → **Application running outside AWS**
   - Copy both values immediately. The secret is shown **once** and never again

   > Why a separate user: it can be deleted the moment the project ends, without touching your
   > own access, and if the key ever leaks you revoke one thing rather than locking yourself out.
   >
   > `AdministratorAccess` is broader than this pipeline needs. Scoping it properly means granting
   > CloudFormation, Lambda, API Gateway, DynamoDB, S3, and `iam:CreateRole` + `iam:PassRole` —
   > fiddly to get right, and a good later exercise. Start broad, narrow it once the pipeline works.

3. In the repo: **Settings → Secrets and variables → Actions → New repository secret.**
   Add two secrets from the key you just created:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

   The region is already defaulted to `ap-southeast-1` in the workflow, so you only need an
   `AWS_REGION` secret if you ever move regions.
4. Make any small change (edit the health message string in `app/main.py`), commit, and push.
5. Go to the repo's **Actions** tab and watch it build and deploy automatically. Then hit your
   ApiUrl again and see the change live.

   > The workflow deploys to the **same stack** you created by hand (`feedback-api-serverless`),
   > so it updates your existing resources rather than creating a second copy. If the stack name
   > in [deploy.yml](.github/workflows/deploy.yml) ever drifts from your real stack, CI will
   > silently build a duplicate set of everything.

**What you learned:** CI/CD — code goes from `git push` to live with zero manual steps. Gap closed.

---

## Phase 5.5 — Kill the long-lived keys (do this once the pipeline is green)

Storing permanent access keys in GitHub is the part of the setup above that a reviewer would
flag. The modern fix is **GitHub OIDC**: GitHub proves its identity to AWS and receives a
short-lived token, so no static secret exists anywhere. You create an IAM identity provider
for `token.actions.githubusercontent.com`, an IAM role trusting *only* your repo, and then
swap the two secrets in `deploy.yml` for `role-to-assume`.

Do this *after* the basic pipeline works — debugging an OIDC trust policy on your first-ever
deploy is a bad time. It's directly on the SA syllabus and it's the single most impressive
detail you can mention about this project.

---

## Phase 6 — Clean up

```powershell
sam delete --stack-name feedback-api-serverless
```

This deletes the Lambda, the API Gateway, and the DynamoDB table (including your test data).
Then check Billing shows ~$0 drawn. Deleting when done is the single best habit for
keeping credits intact.

---

## After this works: optional Phase 7 (SA-exam bonus)

The serverless stack never touches EC2, RDS, or VPC — which are heavily tested on the
Solutions Architect Associate exam, and are also two of the remaining $20 onboarding tasks.
As a deliberate, short-lived exercise:

- Launch a tiny **EC2** instance (t3.micro), SSH in, then **terminate it the same day**.
- Spin up a small **RDS** database, connect to it once, then delete it.

Do these knowingly and tear them down immediately so credits don't drain. Unlike the
serverless stack, these bill for every hour they exist whether you use them or not — that
difference *is* the lesson. Set a phone reminder before you start.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then retry |
| `curl: A parameter cannot be found that matches '-X'` | PowerShell's `curl` alias. Use `Invoke-RestMethod`, or `curl.exe` |
| `503 DynamoDB unavailable` locally | Expected before Phase 4 — no table exists yet. Health endpoint still works |
| `503 ... Unable to locate credentials`, but `aws sts get-caller-identity` works | You signed in with `aws login`, which caches temporary credentials. boto3 needs `pip install "botocore[crt]"` to read that cache, and boto3 ≥ 1.43 |
| `Unable to locate credentials` and the CLI fails too | Your session expired — run `aws login` again |
| `sam local` / `sam build` hangs or errors on Docker | Docker Desktop isn't running |
| Resources missing in the console | Wrong region — set the console's region selector to **Singapore** |
| `/docs` says "Failed to load API definition", 403 on `/openapi.json` | API Gateway serves the app under the `/Prod` stage. FastAPI needs `root_path` to generate links that include it — set via the `ROOT_PATH` env var in `template.yaml` |
| 403 from the API generally | API Gateway returns 403 (not 404) for a path that matches no route. Usually a wrong path, not a credentials problem |
| Deploy fails: stack in `ROLLBACK_COMPLETE` | Failed first-ever create. `sam delete --stack-name feedback-api-serverless`, then deploy again |

---

## What you can say after finishing

"I built a REST API, containerized it, deployed it to AWS as a serverless app with a
DynamoDB backend, and set up a GitHub Actions pipeline that auto-deploys on every commit."

That one sentence demonstrates deploy + pipelines + cloud infra — and every piece is real
SA syllabus material.
