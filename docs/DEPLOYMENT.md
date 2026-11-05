# Deployment

## Kubernetes

Set the image to your published immutable digest and set the egress DB CIDR in `deploy/kubernetes.yaml`. The provided image path is a deployment parameter example, not an existing registry claim. The policy requires an enforcing CNI; verify that your cluster honors NetworkPolicy. Namespace selectors permit ingress only from ingress-nginx and monitoring. Do not apply this to unrelated namespaces.

```powershell
kubectl create namespace dataguard --dry-run=client -o yaml | kubectl apply -f -
kubectl -n dataguard create secret generic dataguard-runtime --from-literal=DATABASE_URL="$env:DATABASE_URL" --from-literal=DATAGUARD_TOKEN="$env:DATAGUARD_TOKEN"
kubectl apply -f deploy/kubernetes.yaml
kubectl -n dataguard rollout status deployment/dataguard
kubectl -n dataguard port-forward service/dataguard 8003:8000
```

Secret literals above are convenient demonstration syntax; production should use an external secret controller or secure secret file so command history/process lists do not expose credentials. Configure HTTPS ingress with a trusted certificate and private/VPN access. The container starts HTTP before retrying v1 database bootstrap in the background; readiness joins that task for up to 15 seconds and still checks current database connectivity. See [probe budgets and isolated recovery evidence](readiness-cold-start.md). Keep one replica for bootstrap; separating all schema initialization into an administrative migration Job and using a restricted runtime DB identity remain deployment work. `DATAGUARD_AUTO_INIT=false` skips pipeline initialization only when background initialization is disabled; quality initialization still runs. No live cluster apply was performed during repository creation.

## AWS Terraform

Prerequisites: account credentials through your approved role, approved spend, an existing ACM certificate/domain, Secrets Manager operator-token secret, a populated ECR repository image, and a restricted operator source CIDR. This deploys paid ALB/RDS/Fargate resources and has deletion protection. No apply has been executed.

```powershell
terraform -chdir=infra fmt -check
terraform -chdir=infra init
terraform -chdir=infra validate
terraform -chdir=infra plan -out=approved.tfplan -var='image=ACCOUNT.dkr.ecr.REGION.amazonaws.com/dataguard@sha256:FULL_DIGEST' -var='certificate_arn=YOUR_ACM_ARN' -var='operator_token_secret_arn=YOUR_SECRET_ARN' -var='trusted_cidr=YOUR_VPN_PUBLIC_IP/32'
# Inspect the saved plan and costs before an authorized apply.
terraform -chdir=infra apply approved.tfplan
```

Use encrypted remote state with locking and tightly restricted access before team use. The starter has no backend configured so validation does not require a cloud account. The ECR repository is a useful bootstrap target; build/push an image before applying the complete service. A first deployment can bootstrap the ECR resource separately, then provide its image digest for the full reviewed plan. For an existing external ECR repository, the image variable can reference it, and the created repository can be used on later releases. The output is the ALB DNS name; add a DNS record for the ACM certificate's hostname before browser use (the ALB's generated hostname will not match your certificate).

Fargate tasks have public addresses solely for outbound registry/log/secret access without a NAT gateway. Their security group accepts port 8000 only from the ALB's security group, and RDS is in private subnets with no internet route. RDS credentials are managed by AWS. Operator token is pre-existing so Terraform does not receive or store its plaintext. RDS admin credentials currently serve schema bootstrap; introduce a dedicated migration Job and restricted runtime role before production. Keep the service at one replica until bootstrap is separated. Enable multi-AZ RDS and VPC endpoints according to availability/security needs; the starter uses a single RDS instance and has no live failover evidence.

## Optional release/deploy workflows

`release.yml` manually builds and publishes a commit-tagged image to GHCR after release environment approval. `deploy.yml` independently assumes an AWS OIDC role, validates a requested ECR sha256 digest, registers a new ECS task revision, updates only the configured service and waits for stability. It detects circuit-breaker rollback by checking the task revision. Configure production environment protection and variables AWS_DEPLOY_ROLE_ARN, AWS_REGION, ECR_REPOSITORY, ECS_CLUSTER, ECS_SERVICE and ECS_TASK_FAMILY. Build and push the ECR image separately; the GHCR workflow does not copy images to ECR.

Restrict OIDC trust to `repo:OWNER/REPO:environment:production` and token audience `sts.amazonaws.com`. Restrict deploy permissions to the relevant ECS service/task definitions and `iam:PassRole` for the task's exact execution role. CI never provisions cloud resources. The workflows are repository assets; remote execution results must be checked after publication.
