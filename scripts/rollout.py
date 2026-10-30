"""OIDC workflow rollout using AWS CLI argument arrays; no shell interpolation."""

import json
import os
import re
import subprocess


def aws(*args):
    return json.loads(subprocess.check_output(["aws", *args, "--output", "json"], text=True))


digest = os.environ["IMAGE_DIGEST"]
if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
    raise ValueError("image_digest must be a sha256 digest")
task = aws("ecs", "describe-task-definition", "--task-definition", os.environ["ECS_TASK_FAMILY"])[
    "taskDefinition"
]
for field in [
    "taskDefinitionArn",
    "revision",
    "status",
    "requiresAttributes",
    "compatibilities",
    "registeredAt",
    "registeredBy",
    "deregisteredAt",
]:
    task.pop(field, None)
task["containerDefinitions"][0]["image"] = os.environ["ECR_REPOSITORY"] + "@" + digest
revision = aws("ecs", "register-task-definition", "--cli-input-json", json.dumps(task))[
    "taskDefinition"
]["taskDefinitionArn"]
aws(
    "ecs",
    "update-service",
    "--cluster",
    os.environ["ECS_CLUSTER"],
    "--service",
    os.environ["ECS_SERVICE"],
    "--task-definition",
    revision,
)
subprocess.run(
    [
        "aws",
        "ecs",
        "wait",
        "services-stable",
        "--cluster",
        os.environ["ECS_CLUSTER"],
        "--services",
        os.environ["ECS_SERVICE"],
    ],
    check=True,
)
service = aws(
    "ecs",
    "describe-services",
    "--cluster",
    os.environ["ECS_CLUSTER"],
    "--services",
    os.environ["ECS_SERVICE"],
)["services"][0]
if service["taskDefinition"] != revision:
    raise RuntimeError("Deployment rolled back to previous revision")
print(json.dumps({"task_definition": revision, "status": "stable"}))
