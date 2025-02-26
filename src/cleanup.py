from datetime import datetime, timezone
from typing import Dict, List, Tuple
from github import Github
from github.Repository import Repository
from github.GitRelease import GitRelease
from dateutil.relativedelta import relativedelta
import os


def process_releases(repo: Repository) -> None:
    """处理 Release 清理逻辑"""
    current_time: datetime = datetime.now(timezone.utc)  # 使用 UTC 时区
    all_releases: List[GitRelease] = list(repo.get_releases())

    # 排除最近 2 小时内的新发布
    recent_cutoff: datetime = current_time - relativedelta(hours=2)
    old_releases: List[GitRelease] = [
        r for r in all_releases
        if r.created_at.astimezone(timezone.utc) < recent_cutoff  # 统一时区比较
    ]

    # 时间阈值计算（保持时区一致）
    six_months_ago: datetime = current_time - relativedelta(months=6)
    three_months_ago: datetime = current_time - relativedelta(months=3)

    # 过期 Release 存储结构
    expired_releases: Dict[Tuple[int, int], List[GitRelease]] = {}

    for release in old_releases:
        created: datetime = release.created_at.astimezone(timezone.utc)  # 转换为 UTC 时区
        if created < six_months_ago:
            process_expired_release(expired_releases, release)
        elif three_months_ago < created < six_months_ago:
            add_expiry_warning(release, created)

    purge_old_releases(expired_releases)


def process_expired_release(
        expired_dict: Dict[Tuple[int, int], List[GitRelease]],
        release: GitRelease
) -> None:
    """处理已过期 Release（带时区转换）"""
    created: datetime = release.created_at.astimezone(timezone.utc)
    key: Tuple[int, int] = (created.year, created.month)
    expired_dict.setdefault(key, []).append(release)


def add_expiry_warning(release: GitRelease, created_date: datetime) -> None:
    """添加过期警告到 Release 描述（带时区转换）"""
    expiry_date: datetime = created_date + relativedelta(months=6)
    notice: str = f"⚠️ 已过期，将在 {expiry_date.strftime('%Y-%m-%d %H:%M UTC')} 删除"

    if notice not in release.body:
        new_body: str = f"{release.body}\n\n{notice}" if release.body else notice
        release.update_release(body=new_body)


def purge_old_releases(expired_dict: Dict[Tuple[int, int], List[GitRelease]]) -> None:
    """清理旧版本 Release"""
    for monthly_releases in expired_dict.values():
        # 按创建时间降序排序
        sorted_releases: List[GitRelease] = sorted(
            monthly_releases,
            key=lambda x: x.created_at,
            reverse=True
        )

        # 保留最新版本，删除其他
        for old_release in sorted_releases[1:]:
            print(f"Deleting {old_release.tag_name} ({old_release.created_at})")
            old_release.delete_release()


if __name__ == "__main__":
    # 初始化 GitHub 连接
    gh_token: str = os.getenv("GITHUB_TOKEN")
    repository: str = os.getenv("GITHUB_REPOSITORY")

    if not gh_token or not repository:
        raise ValueError("Missing required environment variables")

    github = Github(gh_token)
    repo = github.get_repo(repository)

    process_releases(repo)