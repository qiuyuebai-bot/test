#!/usr/bin/env python3
"""
Phase 6 (CI/CD 管道) 验证脚本
检查项：
1. .github/workflows/docker-images.yml 存在且 YAML 合法
2. deploy/argocd/ 目录下两个 Application manifest 存在且 YAML 合法
3. .dockerignore 正确保留 deploy/nginx/nginx.conf
4. 前后端 Dockerfile 含 # syntax=docker/dockerfile:1 指令
5. 前后端 Dockerfile 含 --mount=type=cache BuildKit cache mount
6. workflow 包含关键 jobs (build-frontend, build-backend, scan-*, update-helm-values)
7. ArgoCD Application 配置了正确的 syncPolicy
"""
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

checks_passed = 0
checks_failed = 0


def ok(msg):
    global checks_passed
    checks_passed += 1
    print(f"  [OK] {msg}")


def fail(msg):
    global checks_failed
    checks_failed += 1
    print(f"  [FAIL] {msg}")


print("=" * 60)
print("Phase 6 CI/CD 管道 - 验证报告")
print("=" * 60)

# ---- 1. workflow YAML ----
print("\n[1/7] 检查 docker-images.yml workflow...")
workflow_path = ROOT / ".github" / "workflows" / "docker-images.yml"
if not workflow_path.exists():
    fail(f"workflow 文件不存在: {workflow_path}")
else:
    try:
        with open(workflow_path, encoding="utf-8") as f:
            wf = yaml.safe_load(f)
        ok(f"workflow YAML 合法，name={wf.get('name')}")
        jobs = wf.get("jobs", {})
        required_jobs = ["build-frontend", "build-backend", "scan-frontend", "scan-backend"]
        for j in required_jobs:
            if j in jobs:
                ok(f"job '{j}' 已定义")
            else:
                fail(f"缺少 job: {j}")
        if "sign-images" in jobs:
            ok("可选 job 'sign-images' 已定义 (cosign 签名)")
        if "update-helm-values" in jobs:
            ok("job 'update-helm-values' 已定义 (自动更新 Helm tag)")
        if "notify-argocd" in jobs:
            ok("job 'notify-argocd' 已定义 (触发 ArgoCD 同步)")
        # 触发条件
        triggers = wf.get(True, {})  # 'on' parsed as True by YAML 1.1
        if isinstance(triggers, dict):
            if "push" in triggers:
                ok("workflow 配置 push 触发")
            if "workflow_dispatch" in triggers:
                ok("workflow 配置手动触发 (workflow_dispatch)")
    except yaml.YAMLError as e:
        fail(f"workflow YAML 解析失败: {e}")

# ---- 2. ArgoCD manifests ----
print("\n[2/7] 检查 ArgoCD Application manifests...")
argocd_dir = ROOT / "deploy" / "argocd"
argocd_files = {
    "staging": argocd_dir / "knowledge-system-staging.yaml",
    "prod": argocd_dir / "knowledge-system-prod.yaml",
}
for env, path in argocd_files.items():
    if not path.exists():
        fail(f"ArgoCD manifest 缺失: {path}")
        continue
    try:
        with open(path, encoding="utf-8") as f:
            app = yaml.safe_load(f)
        if app.get("kind") != "Application":
            fail(f"{env} manifest kind 不是 Application")
            continue
        if app.get("apiVersion") != "argoproj.io/v1alpha1":
            fail(f"{env} apiVersion 不正确: {app.get('apiVersion')}")
            continue
        sync_policy = app.get("spec", {}).get("syncPolicy", {})
        if env == "staging":
            if sync_policy.get("automated"):
                ok(f"{env} 启用 automated sync (auto-deploy)")
            else:
                fail(f"{env} 未启用 automated sync")
        else:
            if not sync_policy.get("automated"):
                ok(f"{env} 禁用 automated sync (生产手动确认)")
            else:
                fail(f"{env} 应禁用 automated sync (生产安全)")
        ok(f"{env} Application manifest YAML 合法")
    except yaml.YAMLError as e:
        fail(f"{env} manifest YAML 解析失败: {e}")

# ---- 3. .dockerignore 保留 nginx.conf ----
print("\n[3/7] 检查 .dockerignore 保留 deploy/nginx/nginx.conf...")
di = ROOT / ".dockerignore"
if not di.exists():
    fail(".dockerignore 不存在")
else:
    content = di.read_text(encoding="utf-8")
    if "deploy" in content and "!deploy/nginx" in content:
        ok(".dockerignore 排除 deploy/ 但保留 deploy/nginx/")
    else:
        fail(".dockerignore 未正确配置 deploy/nginx 例外")
    if "Dockerfile" in content:
        ok(".dockerignore 排除 Dockerfile")
    else:
        fail(".dockerignore 应排除 Dockerfile")

# ---- 4. Dockerfile # syntax 指令 ----
print("\n[4/7] 检查 Dockerfile # syntax 指令...")
dockerfiles = {
    "frontend": ROOT / "Dockerfile",
    "backend": ROOT / "backend" / "Dockerfile",
}
for name, path in dockerfiles.items():
    if not path.exists():
        fail(f"{name} Dockerfile 不存在: {path}")
        continue
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    if first_line.startswith("# syntax=docker/dockerfile:1"):
        ok(f"{name} Dockerfile 含 # syntax BuildKit 指令")
    else:
        fail(f"{name} Dockerfile 缺 # syntax 指令，首行: {first_line!r}")

# ---- 5. --mount=type=cache ----
print("\n[5/7] 检查 Dockerfile --mount=type=cache cache mount...")
for name, path in dockerfiles.items():
    if not path.exists():
        continue
    content = path.read_text(encoding="utf-8")
    if "--mount=type=cache" in content:
        ok(f"{name} Dockerfile 使用 BuildKit cache mount")
    else:
        fail(f"{name} Dockerfile 未使用 cache mount")

# ---- 6. workflow 关键步骤 ----
print("\n[6/7] 检查 workflow 关键步骤...")
if workflow_path.exists():
    wf_text = workflow_path.read_text(encoding="utf-8")
    required_features = [
        ("docker/build-push-action", "镜像构建与推送"),
        ("docker/metadata-action", "镜像 tag 元数据生成"),
        ("docker/setup-buildx-action", "Buildx 设置"),
        ("aquasecurity/trivy-action", "Trivy 镜像扫描"),
        ("github/codeql-action/upload-sarif", "SARIF 上传到 Security tab"),
        ("sigstore/cosign-installer", "cosign 签名工具"),
        ("cache-from: type=gha", "GitHub Actions 缓存 (pull)"),
        ("cache-to: type=gha", "GitHub Actions 缓存 (push)"),
        ("platforms: linux/amd64,linux/arm64", "多架构构建 (amd64 + arm64)"),
        ("type=semver,pattern={{version}}", "SemVer tag 策略"),
        ("type=sha,prefix=main-", "SHA tag 策略"),
    ]
    for token, desc in required_features:
        if token in wf_text:
            ok(f"workflow 含 {desc}")
        else:
            fail(f"workflow 缺 {desc}: {token}")

# ---- 7. PIP_NO_CACHE_DIR 不再阻碍 cache mount ----
print("\n[7/7] 检查后端 Dockerfile PIP_NO_CACHE_DIR 配置...")
backend_df = dockerfiles["backend"]
if backend_df.exists():
    bd_text = backend_df.read_text(encoding="utf-8")
    # 检查 builder 阶段不再有 PIP_NO_CACHE_DIR=1
    builder_section = bd_text.split("# ---- 运行阶段")[0]
    if "PIP_NO_CACHE_DIR=1" not in builder_section:
        ok("builder 阶段不再有 PIP_NO_CACHE_DIR=1 (允许 pip cache mount 生效)")
    else:
        fail("builder 阶段仍有 PIP_NO_CACHE_DIR=1，会禁用 pip cache mount")

# ---- 总结 ----
print("\n" + "=" * 60)
print("验证总结")
print("=" * 60)
print(f"  通过: {checks_passed} 项")
print(f"  失败: {checks_failed} 项")
if checks_failed == 0:
    print("\n所有 Phase 6 (CI/CD 管道) 检查通过！")
    sys.exit(0)
else:
    print(f"\n{checks_failed} 项检查失败，请修复后再继续。")
    sys.exit(1)
