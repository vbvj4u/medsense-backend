# medsense-backend

Application tier of MedSense: a FastAPI app that runs both locally
(`uvicorn`) and on AWS Lambda (via [Mangum](https://github.com/jordaneremieff/mangum)),
behind the API Gateway HTTP API that [medsense-infra](../medsense-infra)
provisions. Data lives in DynamoDB (`DYNAMODB_TABLE` env var).

Sibling repos: [medsense-infra](../medsense-infra) (Terraform),
[medsense-frontend](../medsense-frontend) (React UI).

## Endpoints

| Method | Path                    | Description               |
|--------|-------------------------|----------------------------|
| GET    | `/health`                | Liveness check              |
| GET    | `/api/medicines?search=` | Search medicines by name    |
| GET    | `/api/medicines/{id}`    | Fetch one medicine          |
| POST   | `/api/medicines`         | Create a medicine record    |

## Secrets

API keys and DB passwords are never stored in code, `.env` files, or
plain Lambda environment variables. Terraform writes them to **SSM
Parameter Store** as `SecureString` values (KMS-encrypted at rest) and
grants this function's IAM role `ssm:GetParameter` on just those
parameters; only the *parameter name* (e.g. `MEDICINE_API_KEY_PARAM`)
is passed in as an env var. `app/secrets.py` resolves that name to the
real value at call time and caches it for the life of the Lambda
execution environment. See `medsense-infra/modules/secrets` for why
Parameter Store is used instead of AWS Secrets Manager (cost, staying
inside the AWS free tier) and how to set the real value after
`terraform apply`.

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

export DYNAMODB_TABLE=medsense-dev-medicines
export AWS_REGION=ap-southeast-2
# requires AWS credentials that can read/write that table, e.g.:
#   aws sso login --profile medsense-dev && export AWS_PROFILE=medsense-dev

uvicorn app.main:app --reload
```

## Tests

```bash
pytest -v      # unit tests use moto to mock DynamoDB - no AWS creds needed
ruff check .
```

## CI/CD

- **`ci.yml`** - lint + test on every PR/push to `main`.
- **`_deploy-reusable.yml`** - zips the app + dependencies and calls
  `aws lambda update-function-code`, authenticated via GitHub OIDC
  (no long-lived AWS keys stored in the repo).
- **`deploy-dev.yml`** - runs the above automatically on push to `main`.
- **`deploy-staging.yml` / `deploy-prod.yml`** - same job, manually
  triggered (`workflow_dispatch`); wire these up once those AWS
  accounts exist. Add required reviewers on the `prod` GitHub
  Environment to gate it behind approval.

Each environment (`dev` / `staging` / `prod`) is a separate
[GitHub Environment](../../settings/environments) with its own
secrets, populated from the matching `medsense-infra` Terraform
outputs:

| Repo secret            | Terraform output               |
|-------------------------|---------------------------------|
| `AWS_DEPLOY_ROLE_ARN`   | `backend_deploy_role_arn`       |
| `LAMBDA_FUNCTION_NAME`  | `backend_lambda_function_name`  |

Terraform itself creates the OIDC-federated `AWS_DEPLOY_ROLE_ARN` role,
scoped (see `medsense-infra/modules/github_oidc`) to only
`lambda:UpdateFunctionCode` on this one function - this repo's CI can
never touch anything else in the AWS account.
