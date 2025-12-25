#!/bin/bash
# =============================================================================
# MIRROR ALL REPOS - ONE BY ONE
# =============================================================================
# This script mirrors every single repository from the design document,
# one at a time, with proper error handling and progress tracking.
#
# Usage: ./mirror_all_repos.sh [--dry-run] [--start-from N]
#   --dry-run     : Show what would be mirrored without actually doing it
#   --start-from N: Start from repo number N (useful for resuming)
# =============================================================================

set -e

REPO="kevin-toles/code-reference-engine"
WORKFLOW="mirror-single.yml"
DRY_RUN=false
START_FROM=1

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --start-from)
      START_FROM="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# =============================================================================
# COMPLETE REPOSITORY LIST (92 repos from design document)
# Format: "source_owner/source_repo:target_path"
# =============================================================================

declare -a REPOS=(
  # ---------------------------------------------------------------------------
  # GAME DEV - ENGINES (4 repos)
  # ---------------------------------------------------------------------------
  "godotengine/godot:game-dev/engines/godot"
  "urho3d/Urho3D:game-dev/engines/urho3d"
  "OGRECave/ogre:game-dev/engines/ogre"
  "OpenMW/openmw:game-dev/engines/openmw"

  # ---------------------------------------------------------------------------
  # GAME DEV - SYSTEMS (4 repos)
  # ---------------------------------------------------------------------------
  "skypjack/entt:game-dev/systems/entt"
  "libsdl-org/SDL:game-dev/systems/sdl"
  "glfw/glfw:game-dev/systems/glfw"
  "ocornut/imgui:game-dev/systems/imgui"

  # ---------------------------------------------------------------------------
  # GAME DEV - RENDERING (5 repos)
  # ---------------------------------------------------------------------------
  "bkaradzic/bgfx:game-dev/rendering/bgfx"
  "google/filament:game-dev/rendering/filament"
  "ConfettiFX/The-Forge:game-dev/rendering/the-forge"
  "KhronosGroup/Vulkan-Samples:game-dev/rendering/vulkan-samples"
  "microsoft/DirectX-Graphics-Samples:game-dev/rendering/directx-samples"

  # ---------------------------------------------------------------------------
  # GAME DEV - PHYSICS (3 repos)
  # ---------------------------------------------------------------------------
  "bulletphysics/bullet3:game-dev/physics/bullet"
  "NVIDIA-Omniverse/PhysX:game-dev/physics/physx"
  "erincatto/box2d:game-dev/physics/box2d"

  # ---------------------------------------------------------------------------
  # GAME DEV - AI (3 repos)
  # ---------------------------------------------------------------------------
  "recastnavigation/recastnavigation:game-dev/ai/recast"
  "BehaviorTree/BehaviorTree.CPP:game-dev/ai/behaviortree-cpp"
  "opensteer/opensteer:game-dev/ai/opensteer"

  # ---------------------------------------------------------------------------
  # C++ CORE (3 repos)
  # ---------------------------------------------------------------------------
  "boostorg/boost:cpp/core/boost"
  "abseil/abseil-cpp:cpp/core/abseil"
  "facebook/folly:cpp/core/folly"

  # ---------------------------------------------------------------------------
  # C++ MATH (2 repos)
  # ---------------------------------------------------------------------------
  "eigenteam/eigen:cpp/math/eigen"
  "g-truc/glm:cpp/math/glm"

  # ---------------------------------------------------------------------------
  # C++ ECS (1 repo - also in game-dev but canonical location)
  # ---------------------------------------------------------------------------
  "skypjack/entt:cpp/ecs/entt"

  # ---------------------------------------------------------------------------
  # BACKEND - FRAMEWORKS (10 repos)
  # ---------------------------------------------------------------------------
  "spring-projects/spring-boot:backend/frameworks/spring-boot"
  "django/django:backend/frameworks/django"
  "tiangolo/fastapi:backend/frameworks/fastapi"
  "pallets/flask:backend/frameworks/flask"
  "expressjs/express:backend/frameworks/express"
  "koajs/koa:backend/frameworks/koa"
  "rails/rails:backend/frameworks/rails"
  "laravel/laravel:backend/frameworks/laravel"
  "dotnet/aspnetcore:backend/frameworks/aspnetcore"
  "phoenixframework/phoenix:backend/frameworks/phoenix"

  # ---------------------------------------------------------------------------
  # BACKEND - MICROSERVICES (4 repos)
  # ---------------------------------------------------------------------------
  "dotnet-architecture/eShopOnContainers:backend/microservices/eshop-on-containers"
  "GoogleCloudPlatform/microservices-demo:backend/microservices/online-boutique"
  "microservices-patterns/ftgo-application:backend/microservices/ftgo"
  "spring-projects/spring-petclinic:backend/microservices/spring-petclinic"

  # ---------------------------------------------------------------------------
  # BACKEND - EVENT-DRIVEN (2 repos)
  # ---------------------------------------------------------------------------
  "gschmutz/event-driven-microservices-demo:backend/event-driven/kafka-demo"
  "apache/kafka:backend/event-driven/kafka"

  # ---------------------------------------------------------------------------
  # BACKEND - SERVERLESS (2 repos)
  # ---------------------------------------------------------------------------
  "aws-samples/aws-serverless-airline-booking:backend/serverless/aws-airline"
  "openfaas/faas:backend/serverless/openfaas"

  # ---------------------------------------------------------------------------
  # BACKEND - DDD (1 repo)
  # ---------------------------------------------------------------------------
  "citerus/dddsample-core:backend/ddd/cargo-sample"

  # ---------------------------------------------------------------------------
  # FRONTEND - FRAMEWORKS (4 repos)
  # ---------------------------------------------------------------------------
  "facebook/react:frontend/frameworks/react"
  "angular/angular:frontend/frameworks/angular"
  "vuejs/core:frontend/frameworks/vue"
  "sveltejs/svelte:frontend/frameworks/svelte"

  # ---------------------------------------------------------------------------
  # FRONTEND - MICRO-FRONTENDS (1 repo)
  # ---------------------------------------------------------------------------
  "single-spa/single-spa:frontend/micro-frontends/single-spa"

  # ---------------------------------------------------------------------------
  # INFRASTRUCTURE (6 repos)
  # ---------------------------------------------------------------------------
  "kubernetes/kubernetes:infrastructure/kubernetes"
  "kelseyhightower/kubernetes-the-hard-way:infrastructure/k8s-hard-way"
  "moby/moby:infrastructure/docker"
  "hashicorp/terraform:infrastructure/terraform"
  "ansible/ansible:infrastructure/ansible"
  "helm/helm:infrastructure/helm"

  # ---------------------------------------------------------------------------
  # DATABASES (5 repos)
  # ---------------------------------------------------------------------------
  "postgres/postgres:databases/postgresql"
  "redis/redis:databases/redis"
  "apache/cassandra:databases/cassandra"
  "cockroachdb/cockroach:databases/cockroachdb"
  "opensearch-project/OpenSearch:databases/opensearch"

  # ---------------------------------------------------------------------------
  # SECURITY (3 repos)
  # ---------------------------------------------------------------------------
  "keycloak/keycloak:security/keycloak"
  "hashicorp/vault:security/vault"
  "zaproxy/zaproxy:security/owasp-zap"

  # ---------------------------------------------------------------------------
  # MONITORING (4 repos)
  # ---------------------------------------------------------------------------
  "prometheus/prometheus:monitoring/prometheus"
  "grafana/grafana:monitoring/grafana"
  "jaegertracing/jaeger:monitoring/jaeger"
  "grafana/loki:monitoring/loki"

  # ---------------------------------------------------------------------------
  # TESTING (6 repos)
  # ---------------------------------------------------------------------------
  "SeleniumHQ/selenium:testing/selenium"
  "cypress-io/cypress:testing/cypress"
  "apache/jmeter:testing/jmeter"
  "locustio/locust:testing/locust"
  "junit-team/junit5:testing/junit5"
  "pytest-dev/pytest:testing/pytest"

  # ---------------------------------------------------------------------------
  # ML - FRAMEWORKS (6 repos)
  # ---------------------------------------------------------------------------
  "tensorflow/tensorflow:ml/frameworks/tensorflow"
  "pytorch/pytorch:ml/frameworks/pytorch"
  "scikit-learn/scikit-learn:ml/frameworks/scikit-learn"
  "huggingface/transformers:ml/frameworks/transformers"
  "dmlc/xgboost:ml/frameworks/xgboost"
  "ray-project/ray:ml/frameworks/ray"

  # ---------------------------------------------------------------------------
  # ML - OPS (3 repos)
  # ---------------------------------------------------------------------------
  "mlflow/mlflow:ml/ops/mlflow"
  "kubeflow/kubeflow:ml/ops/kubeflow"
  "apache/airflow:ml/ops/airflow"

  # ---------------------------------------------------------------------------
  # BUILD SYSTEMS (4 repos)
  # ---------------------------------------------------------------------------
  "Kitware/CMake:build-systems/cmake"
  "premake/premake-core:build-systems/premake"
  "bazelbuild/bazel:build-systems/bazel"
  "fastbuild/fastbuild:build-systems/fastbuild"

  # ---------------------------------------------------------------------------
  # NETWORKING (2 repos)
  # ---------------------------------------------------------------------------
  "lsalzman/enet:networking/enet"
  "ValveSoftware/GameNetworkingSockets:networking/steam-networking"
)

# =============================================================================
# FUNCTIONS
# =============================================================================

trigger_and_wait() {
  local source=$1
  local target=$2
  local num=$3
  local total=$4
  
  echo ""
  echo "=========================================="
  echo "[$num/$total] Mirroring: $source"
  echo "         Target: $target"
  echo "=========================================="
  
  if [ "$DRY_RUN" = true ]; then
    echo "  [DRY RUN] Would trigger: gh workflow run $WORKFLOW --repo $REPO"
    echo "            -f source_url=https://github.com/$source"
    echo "            -f target_path=$target"
    return 0
  fi
  
  # Trigger the workflow
  gh workflow run "$WORKFLOW" \
    --repo "$REPO" \
    -f source_url="https://github.com/$source" \
    -f target_path="$target"
  
  if [ $? -ne 0 ]; then
    echo "❌ Failed to trigger workflow for $source"
    return 1
  fi
  
  # Wait for the run to be created
  echo "  Waiting for workflow to start..."
  sleep 10
  
  # Get the latest run ID
  RUN_ID=$(gh run list --workflow="$WORKFLOW" --repo "$REPO" --limit 1 --json databaseId --jq '.[0].databaseId')
  
  if [ -z "$RUN_ID" ]; then
    echo "❌ Could not get run ID"
    return 1
  fi
  
  echo "  Run ID: $RUN_ID"
  echo "  Waiting for completion..."
  
  # Wait for the run to complete (with timeout)
  local elapsed=0
  local timeout=600  # 10 minutes max per repo
  
  while [ $elapsed -lt $timeout ]; do
    STATUS=$(gh run view "$RUN_ID" --repo "$REPO" --json status --jq '.status')
    
    if [ "$STATUS" = "completed" ]; then
      CONCLUSION=$(gh run view "$RUN_ID" --repo "$REPO" --json conclusion --jq '.conclusion')
      if [ "$CONCLUSION" = "success" ]; then
        echo "  ✅ SUCCESS: $source"
        return 0
      else
        echo "  ❌ FAILED: $source (conclusion: $CONCLUSION)"
        echo "  View logs: gh run view $RUN_ID --repo $REPO --log"
        return 1
      fi
    fi
    
    echo "  Status: $STATUS (elapsed: ${elapsed}s)"
    sleep 15
    elapsed=$((elapsed + 15))
  done
  
  echo "  ⏰ TIMEOUT: $source (exceeded ${timeout}s)"
  return 1
}

# =============================================================================
# MAIN
# =============================================================================

TOTAL=${#REPOS[@]}
SUCCESS=0
FAILED=0
SKIPPED=0

echo "============================================"
echo "CODE REFERENCE ENGINE - MIRROR ALL REPOS"
echo "============================================"
echo "Total repos: $TOTAL"
echo "Starting from: $START_FROM"
echo "Dry run: $DRY_RUN"
echo "============================================"
echo ""

# Create progress file
PROGRESS_FILE="/tmp/mirror_progress_$(date +%Y%m%d_%H%M%S).log"
echo "Progress file: $PROGRESS_FILE"
echo ""

for i in "${!REPOS[@]}"; do
  NUM=$((i + 1))
  
  # Skip if before start point
  if [ $NUM -lt $START_FROM ]; then
    ((SKIPPED++))
    continue
  fi
  
  ENTRY="${REPOS[$i]}"
  IFS=':' read -r SOURCE TARGET <<< "$ENTRY"
  
  if trigger_and_wait "$SOURCE" "$TARGET" "$NUM" "$TOTAL"; then
    ((SUCCESS++))
    echo "$NUM:SUCCESS:$SOURCE:$TARGET" >> "$PROGRESS_FILE"
  else
    ((FAILED++))
    echo "$NUM:FAILED:$SOURCE:$TARGET" >> "$PROGRESS_FILE"
    
    # Ask whether to continue on failure
    if [ "$DRY_RUN" = false ]; then
      echo ""
      echo "⚠️  Do you want to continue? (y/n/skip)"
      read -r answer
      case $answer in
        n|N)
          echo "Stopping at repo $NUM"
          break
          ;;
        skip|s|S)
          echo "Skipping to next repo..."
          ;;
        *)
          echo "Continuing..."
          ;;
      esac
    fi
  fi
  
  # Small delay between repos to avoid rate limiting
  if [ "$DRY_RUN" = false ]; then
    echo "  Waiting 5s before next repo..."
    sleep 5
  fi
done

# =============================================================================
# SUMMARY
# =============================================================================

echo ""
echo "============================================"
echo "COMPLETE"
echo "============================================"
echo "✅ Succeeded: $SUCCESS"
echo "❌ Failed:    $FAILED"
echo "⏭️  Skipped:   $SKIPPED"
echo ""
echo "Progress log: $PROGRESS_FILE"
echo ""

if [ $FAILED -gt 0 ]; then
  echo "Failed repos:"
  grep ":FAILED:" "$PROGRESS_FILE" | while read -r line; do
    echo "  - $line"
  done
  echo ""
  echo "To resume from a specific repo, run:"
  echo "  ./mirror_all_repos.sh --start-from N"
fi
